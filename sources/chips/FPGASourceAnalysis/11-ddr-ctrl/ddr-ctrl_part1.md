# ddr_ctrl：DDR4 读写 UI 接口调度器（rtl/ddr_ctrl/ddr_ctrl.sv）

> 源路径：`rtl/ddr_ctrl/ddr_ctrl.sv`（359 行）。综述 §4.1 只给一句（"DDR 写调度（hash_inv 校验、self_check 0x5a）、4 级流水线 CRC32 哈希"），本文补成完整调度器分析。CRC32 4 级流水线在 `rtl/tlv/t_hash_gen.sv`（上游产写哈希），不在本模块。读响应解复用见 `ddr-ctrl_part2.md`。

## 0. 位置与数据流（顶层 sys_clk / ui_clk 双域）

```
写: 4路写源(bus_c_sch合成仅i==0)→ ddr_wr_sch_out → dc_fifo_c_ctrl(ddr_cfg_fifo, sys→ui) → t_ddr_in ─┐
读: 会话表/黑名单 d_rd_req + 主机DDR_DB_RD_A0 ─ rd_req_sch(2源合1) → dc_fifo_across(cfg_req_fifo, sys→ui) → d_rd_req ─┤
                                                                                        ddr_ctrl(ui_clk) ─→ MIG UI app_*
读响应: app_rd_data → d_rd_res → dc_fifo_across(cfg_res_fifo, ui→sys) → rd_res_demux → {out0会话表, out1黑名单, out2调试}
```

当前 DUT 仅启用第 1 片 DDR（j=0）；`ddr_ctrl_1`/`ddr4_1_dns` 整段注释，j=1 读响应被驱动为 0（见 part2 §7 坑）。

## 1. 接口全表

参数 `APP_DATA_WIDTH=512`（MC UI 数据宽）、`APP_ADDR_WIDTH=28`、`HASHW=APP_ADDR_WIDTH-3=25`、`SIM_MODE=0`。

| 信号 | 方向/位宽 | 说明 |
|---|---|---|
| clk / rst | in | `ui_clk`（MIG UI 用户时钟）、`ui_rst`（UI 复位） |
| clr | in | `sys_rst`；仅作例化内读配 FIFO `sc_fifo_idx` 的 rst（见 §5 坑） |
| t_ddr_clear | in | `r_table_clear[i][0]` 会话表清空触发（打 2 拍成 t_ddr_clear_d） |
| t_ddr_in | in `BUS#(512,28)::C` | 写请求：vld/sop/eop/left[5:0]/data[511:0]/ch[27:0]（ch 载哈希） |
| t_ddr_empty | in | 未使用（悬空输入） |
| t_ddr_rdy | out | `app_rdy & app_wdf_rdy`，写 FIFO 读使能 |
| d_rd_req / d_rd_req_rdy | in `DDR#(512,28)::REQ`(vld+addr[27:0]) / out | 读请求与读侧反压 |
| d_rd_res / ddr_fifo_afull | out `DDR#(512,28)::RES`(vld+addr+data[511:0]) / out | 读响应；配对 FIFO 伪满 |
| init_calib_complete | in | UI 校准完成，自检门控 |
| self_check_ok | out | 0x5a 自检结果 |
| app_addr/app_cmd/app_en | out 28/3/1 | MIG UI 命令口；顶接 `{1'b0,app_addr}` 成 29bit，app_hi_pri=0 |
| app_wdf_wren/data/end/mask | out 1/512/1/64 | MIG UI 写数据口 |
| app_wdf_rdy / app_rdy | in | UI 写数据 FIFO 就绪 / 命令 FIFO 就绪 |
| app_rd_data_valid/end/data | in 1/1/512 | UI 读回；app_rd_data_end 未使用 |

写 1 路（BUS#(512,28)::C）、读 1 路（单拍 REQ）——多源合并在顶层：写侧 i==0 用 `bus_c_sch`(N=4) 合 4 源；读侧 `rd_req_sch`(N=2) 把「会话表/黑名单」与「主机调试」合成 1 路。

## 2. app_addr[27:0] 字段与 hash_inv

头注释声明格式（L10-20）：`[27:3]`=hash 行地址（25bit）、`[2:1]`=mask_sel（4 个 64-bit 掩码通道选择）、`[0]`=debug（默认 0）。

**实际实现（L119-123）[2:0] 恒为 0**，mask_sel/debug 位未使用：

```systemverilog
assign app_addr = ~self_check_cnt[7] ? {{19{1'b0}}, self_check_cnt[5:0], 3'h0} :   // 自检：0,8,…,504
                  t_ddr_clear_d[1]   ?  app_addr_pre :                              // 清表
                  t_ddr_in.vld       ? {hash_inv(t_ddr_in.ch[27-:25]), 3'h0}:       // 写
                                       {hash_inv(d_rd_req.addr[27-:25]), 3'h0};     // 读
```

上游 `t_hash_gen.v` 同样 `v_dout0.ch <= {hash_out[31-:25],3'h0}`，ch[2:0] 也为 0。故头注释的 mask_sel/debug 是预留格式（**待核实**：是否曾用于按掩码通道分写）。

**hash_inv 是位反转函数（L92-98），不是校验和**：`hash_inv[i]=din[HASHW-1-i]`，把哈希 25bit 位序反转当行地址，做地址扩散（打散连续哈希到不同 row/bank 减冲突）。综述"hash_inv 校验"不精确。它亦用于 `app_addr_pre` 的 SIM 起始偏移（`hash_inv('h9173_5b1f>>7)-16` / `'he3fc_6fb8` 魔法常量，SIM_MODE=1/2）。

## 3. 读写仲裁状态机

8 态枚举：`INIT_IDLE/INIT_WRITE/INIT_READ/INIT_WAIT/IDLE/WRITE/READ/WAIT`；`SIM_MODE==0` 复位进 INIT_IDLE，否则直接 IDLE。

- IDLE：`t_ddr_in.vld | t_ddr_clear_d[1]` → WRITE，否则 `d_rd_req.vld` → READ（写优先）；校准未完成停 IDLE。
- WRITE：写请求持续则保持，清空后按 `d_rd_req.vld` 转 READ 或回 IDLE。
- READ：**新写请求随时抢占**（写绝对优先，非 round-robin）；持续读则保持。
- WAIT：不可达（无转移入）。

```systemverilog
// app_en/app_wdf_wren 组合门控（L105-133）
app_en      = (next_state==WRITE||INIT_WRITE) ? (app_rdy&app_wdf_rdy) :
              (next_state==READ ||INIT_READ ) ?  app_rdy : 1'b0;
app_cmd     = (next_state==READ||INIT_READ) ? 3'd1 : 3'd0;   // 1=READ 0=WRITE
app_wdf_wren= (next_state==WRITE||INIT_WRITE) && app_rdy && app_wdf_rdy;
app_wdf_end = app_wdf_wren;   // 4:1 分频 + BL8 时两信号同拍
```

## 4. 写路径

**掩码 app_wdf_mask（L233-254，64 字节，1=屏蔽）由 `t_ddr_in.left` 选**：

| left | 数据类别 | mask 位段（高→低） | 实际写入 |
|---|---|---|---|
| left[4]=1 | 黑名单 16B | `{~48'h0, 16'h0}` | 低 16 字节 |
| left[3]=1 | 会话时间戳 8B | `{~8'h0, 4'h0, ~52'h0}` | 字节 52~55 |
| 其它 | 52B 常规 | `{8'h0, ~4'h0, 52'h0}` | 低 52 字节 |

**t_ddr_clear 清表**：t_ddr_clear 打 2 拍；上升沿把 `app_addr_pre` 载入 SIM 相关起始偏移，之后每命令 `+=8` 顺序清零全表；清零时 data=0 mask=0。`app_addr_pre` 在自检阶段同步累加、INIT_IDLE/INIT_WAIT 又清零——只在清表时真正用于 app_addr。

**outstanding**：写侧无计数管理，靠 `t_ddr_rdy=app_rdy&app_wdf_rdy` 逐拍握手（两 FIFO 同时就绪才消费一拍）。

## 5. 0x5a 自检与读路径

**自检 = 校准后一次性 POST，不是周期性**（综述"周期性写读回自检"不精确）：INIT→IDLE 只走一次，此后 `self_check_cnt[7]=1` 常驻。流程：

1. INIT_IDLE 等校准完成；INIT_WRITE 以 `app_addr={self_check_cnt[5:0],3'b0}`（0..504 步进 8）写 `app_wdf_data=8'h5a<<(cnt*8)`（每 512-bit 位置仅下标字节填 0x5a，mask=0）。
2. `self_check_cnt[6]`（到 64）触发跃进、计清重来；INIT_READ 读回。
3. `data_check_cnt` 随 `app_rd_data_valid` 累加；读回检查 `app_rd_data[cnt*8 +:8]==8'h5a`，不等则 `self_check_ok<=0`；`data_check_cnt[6]` 后经 INIT_WAIT 进 IDLE。

**读输出门控（L100）**：`d_rd_res.vld = app_rd_data_valid & self_check_cnt[7]`——自检读回不送出。`self_check_cnt` 复位：`~init_calib_complete` 清 0；`next_state==IDLE` 载 `8'h80`。

**读请求来源（顶层 DDR_GEN）**：每通道经 `rd_req_sch`(N=2, 固定端口 0 优先) 合成 2 源——(a) 会话表 / 黑名单查询读；(b) 主机 `top_mem_map.DDR_DB_RD_A0` 调试读（顶接写 `addr={wr_data[28:1],1'b1}`，bit[28]=DDR 片选、bit[0]=1 打 debug 标签）。合成后 `cfg_req_fifo` 跨到 ui_clk 成 `d_rd_req`。

**响应配对（本模块不跨域）**：`sc_fifo_idx #(DW=28, DEPTH=6, AFULL=10, distributed)` 入=`d_rd_req{i.vld,addr}`、出=`d_rd_res.vld` 弹出 → `d_rd_res.addr` 与请求一一配对；`ddr_fifo_afull`=伪满（L292-307）。**坑：此 FIFO 的 rst 接 `clr`(sys_rst)，与 ui_clk 域复位不一致**——CDC 复位风险**待核实**。读反压 `d_rd_req_rdy = app_rdy & ~t_ddr_clear_d[1] & ~t_ddr_in.vld`（写忙/清表时不许新读进）。outstanding 容量=FIFO 深度 6；另 `synthesis translate_off` 内 `ddr_req_cnt/ddr_res_cnt` 按 `addr[0]` 分类累计 in/out（L319-357，不综合）。

死信号：`error_flag/error_status`（L84-85；L310-318 赋值被注释）——error_status 无驱动，纯遗留。

## 6. 时钟与 CDC

模块整体**单时钟（clk=ui_clk）**，内部无跨域。CDC 全在顶层 FIFO：写 `dc_fifo_c_ctrl`(ddr_cfg_fifo, sys→ui)、读请求 `dc_fifo_across`(cfg_req_fifo, sys→ui)、读响应 `dc_fifo_across`(cfg_res_fifo, ui→sys)。ddr_ctrl 只做"单域内把写/读命令灌进 MIG UI"。

> 继续：[ddr-ctrl_part2.md](ddr-ctrl_part2.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)