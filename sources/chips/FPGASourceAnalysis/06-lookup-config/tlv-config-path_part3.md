# TLV 配置下发链路（续 3/3）：t_hash_gen 与背压

## 5. t_hash_gen —— 4 深流水 CRC 哈希与 DDR 写背压

输入 `v_din=BUS#(256,6)::C`（来自 tl_parsing.v_dout），输出 `v_dout0/v_dout1=BUS#(512,28)::C`、`ddr_db_wr=DDR#(512,29)::RES`。`DP=4` 路并行 FSM。

### 5.1 4 路 FSM（cur_st[next_st]/next_st0/next_st1）

```
IDLE ──(wr_pkt_cnt==i && din_d0.vld && din_d0.eop)──▶ HASH_CALC
HASH_CALC ──(rd_dout[i].eop && rd_cnt[1:0]==2)──▶ HASH_DONE
HASH_DONE ──(rd_64b[i].eop)──▶ DATA_OUT
         └─(rd_cnt==0)──▶ IDLE
DATA_OUT ──(dout_cnt >= v_len-1)──▶ IDLE
```
- 每个 FSM 服务一个"配置表项包"，用 `wr_pkt_cnt`（写包计数）把第 i 个包路由到第 i 路 FSM（`wr_vld[i]=(wr_pkt_cnt==i)&din_d0_vld`）。
- `ram_sdp`（distributed, DEPTH=2, DW=$bits(wr_din[i])）每路存当前表项数据；写地址 `wr_addr` 在 HASH_DONE 清 0。
- 读地址：HASH_CALC 用 `rd_cnt[3:2]`、否则 `rd_cnt[1:0]`（循环读）。

### 5.2 rd_64b 与 CRC（哈希输入逐 64b）

按 `rd_dout[i].ch[3:0]` 定每表项 64b 组数 `rd_64b_len`：

| ch[3:0] | 表 | rd_64b_len（64b 组） |
|---|---|---|
| 0 | 会话 | 5 |
| 1 | ACL | 5 |
| 2 | 黑名单 | 2 |
| 3 | 邻接 | 1 |
| 4 | 空 | 1 |

每 64b 的选取沿 `rd_cnt_d1[1:0]`：cnt0 按表型取（黑名单=整个低 64b `data[191-:64]`；会话/ACL 若 `data[255-:8]==8'hff` 则置 0 否则取 `{data[255-:32],32'h0}`）；cnt1 取 `data[128+:64]`；cnt2 若 `data[127-:8]==8'hff` 置 0 否则取 `{data[127-:32],32'h0}`；cnt3 取 `data[0+:64]`。`hash_32b_gen` 逐 64b `crc_en=rd_64b[i].vld`，`rst=hash_32b_rst[i](=wr_vld[i])`，输出 `hash_out[i]`（pw 多项式见 rtl/common/hash_32b_gen.sv 头）。

`v_len[i]`：会话/ACL（ch[3:0]==0/1）→ 2；否则→1（决定 DATA_OUT 拍数 / v_dout0 载荷节拍）。

### 5.3 v_dout0（会话/ACL）与 v_dout1（黑名单）拼装

- 汇聚：`rd_sop_mix=|d_sop_pre`、`rd_eop_mix=|d_eop_pre`、`d_vld_mix=|d_vld_pre`；`rd_pkt_sel` 依随 `(v_dout0.eop|v_dout1.eop)` 递增，选当前路 `rd_dout_d1[rd_pkt_sel]`。
- **v_dout0**（`~ch[1]` 才会出拍，即会话/ACL 之外？——见下）：`sop/eop/vld = rd_eop_mix & d_vld_mix & ~rd_dout_d1[rd_pkt_sel].ch[1]`。SOP 拍 `ch<={hash_out[rd_pkt_sel][31-:25],3'h0}`——**25b 哈希作表基址**（`ch[28]=type`、`ch[27:3]=ddr 地址`、`ch[2:0]=0`，模块头注释；SOP 拍只给一次，其它拍 ch 保持）。`data` 在 EOP 拍拼装：`{上 64b, 32'h0, data[159-:96], SIM_MODE?0:cfg_timeout_sel[47-:32], data[31:0], rd_dout_d1.data[255:32], [30:24]=tc_en/is_down/per_ip_en, [19:16]=line_fc_id, [12:0]=fc_id, 8'h0}`。
  - `v_flag=data[511-320-:8]`：`ddr_cfg_cnt += (v_dout0.sop & v_flag[4])`（计数）。
- **v_dout1**（`ch[1]` 置位即黑名单/邻接）：`sop/eop/vld = rd_eop_mix & d_vld_mix & rd_dout_d1[rd_pkt_sel].ch[1]`。SOP 拍 `left='d16`、`ch<={hash_out[31-:25],3'h0}`；`data={4{data[255-:32], data[159-:56], 40'h0}}`（512b 重复 4 份）。

### 5.4 超时选择（写 DDR 条目的时间戳段）

`cfg_timeout_sel[47:0]` 按老化档位拼 `gbl_timeout[31:0]` 与哈希低 16b：

| 条件 | 取值 |
|---|---|
| `acc_aging_hold`（加速老化） | `{gbl_timeout[31:0],16'h0}` |
| `timeout_gt_64s`（st_timeout[15:6]>0） | `{gbl_timeout[31:6], hash_out[rd_pkt_sel][31-:22]}` |
| `st_timeout[5]`（32s 档） | `{gbl_timeout[31:5], hash_out[...][31-:21]}` |
| 默认（≤16s） | `{gbl_timeout[31:0],16'h0}` |

`acc_aging_hold` 由 `session_t_sch` 输出（`acc_aging_hold_tcp|udp`，见 rtl/table/session_t_sch.sv L574 老化逻辑）。

### 5.5 与 ddr_ctrl 的交互与背压

- `v_dout0/v_dout1` 经 top.sv `bus_c_sch`(N=4 汇聚) → `dc_fifo_c_ctrl`（DEPTH=6，**册 sys_clk→DDR ui_clk**，`fifo_afull=fifo_afull_db`）→ `t_ddr_fifo` → ddr_ctrl 表写通道。**下游 ddr 队列 afull 即上游停顿**（`fifo_rdy` 反压 bus_c_sch）。
- `ddr_db_wr(512,29)::RES`：`v_dout0.vld ? {1'h0,v_dout0.ch,data} : {1'h1,v_dout1.ch,data}`（高 1b 为 DB 通道标志）。经 `dc_fifo_across`（**sys_clk→clk_100m**，DEPTH=5）→ `cfg_req_fifo`（同域）→ 进 `rd_req_sch`/`cfg_req_fifo` 到 ddr_ctrl 的 DB 请求队列。写侧 `fifo_rdy=1'b1`（clk_100m 侧慢域，靠双 FIFO 深度吸收）。
- 配置数据 FIFO `cfg_data_fifo`（读侧 `fifo_rd_rdy`）按 `fifo_rd_gap[2]`（空拍/afull 回退）动态背压 tl_parsing 端；`fifo_rd_gap` 根据前包/后包是否换表型决定 **1~4 拍**间隔，避免 `ram_sdp` 读写碰撞并让该表 CRC 重新累积。

## 6. session_t_sch 侧带校验的 TLV 关系（对照）

`session_t_sch`（数据面查表）不直接消费 TLV，但两者共享**哈希/表地址契约**，且 TLV 写出的 DDR 条目正是数据面读的条目，契约点：

- **表地址 = 25b 哈希**：`t_hash_gen` 把 `hash_out` 高 25b 打入 `v_dout0.ch[27:3]`（即 `ch[28]=type、ch[27:3]=base`）；数据面 `d_rd_req`/`pkt_ft_in.addr = {ch[HASH_FLAG-:25],3'd0}`（HASH_FLAG=63，即 `five_tuple_hash` 高 25b<<3）——**同一条 28b 表地址**。
- **rss_rd**：`session_t_sch` L228 `rss_rd = BSC_12(din_d[0].ch[RSS_FLAG-:12])`——数据面下行哈希方向，与 TLV 无关（会话配置写入时不影响 rss 键）。
- **配置的 macid/vlan/sip/dip**：TTLV 条目经 ddr_ctrl 落地后的 512b 布局与数据面 `ddr_ft_info` 比较键（见 [session-table.md](session-table.md) §4）一致时，数据面查表才命中——TTLV 是"写入侧"，`session_t_sch` 是"读取侧"。
- 背压信号串联：`session_t_sch` 输出 `acc_aging_hold` 直接驱动 `t_hash_gen.cfg_timeout_sel` 档位；`session_t_sch` 读 `fifo_afull_db`、`dma_feild_db` 等，与 TLV 写侧共用同一 DDR 请求仲裁（`rd_req_sch` / `cfg_req_fifo`）。

## 7. 疑点与待核实

1. **`cfg_ip_parsing` 的 TCP/UDP localparam 疑似错位**：`TCP=8'd1、UDP=8'd6`，与数据面 `session_t_sch`/`user_bus_def` 的 `TCP=6、UDP=17` 相反。影响 `is_tcp_or_udp`（黑名单填不填 sport）。**待核实**。
2. `cfg_ip_parsing` 的 `ipv4_p_id_invld/ipv6_p_id_invld` 恒赋 0、`arp_ipv4` 仅在 ARP 才判——`eth_bypass` 逻辑在此版本几乎恒 0（黑名单全走哈希）。
3. `tl_parsing` 注释 `ch[5:4]` 写 "1->add;2->del"，但赋值为 `{2'd1,...}/{2'd2,...}`，位序是 `[5]=del/`[4]=add（big-endian [5:4]）。
4. `adj_dout.data` 在 type<196（add 邻接）时 `{96b,144'b0}` 的 96b 具体字段语义未在本文件注释——**待核实**（邻接表 downstream）。
5. `t_hash_gen` 的 `v_dout0` 由 `~rd_dout_d1[rd_pkt_sel].ch[1]` 门控，但 `ch[1]` 对会话(0)/ACL(1)/黑名单(2)/邻接(3) 的落区（bit1 置位=黑名单/邻接）暗示会话语义可能受 `rd_pkt_sel` 交错影响——多路数据混选时 `rd_pkt_sel` 是否逐包严格对齐，**待核实**。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
