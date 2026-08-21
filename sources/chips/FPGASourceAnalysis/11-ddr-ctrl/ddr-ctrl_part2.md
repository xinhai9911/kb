# rd_res_demux：DDR 读响应解复用（rtl/ddr_ctrl/rd_res_demux.sv）

> 源路径：`rtl/ddr_ctrl/rd_res_demux.sv`（70 行）。综述 §4.1（"DDR 读响应按 addr[0] 标签分发——0=会话表、黑名单；1=主机调试读"）只给一句，本文精确到「输入通道位次 + addr[0]」的组合解码、流水级数与调试跨钟链路。上篇 `ddr-ctrl_part1.md` 覆盖 ddr_ctrl 本体的调度与自检。

## 1. 接口与参数

| 参数 | 值 | 说明 |
|---|---|---|
| I_NUM / N_NUM | 2 / 3 | 输入 2 路、输出 3 路 |
| DW / CHW | 512 / 28 | 数据位宽 / 地址位宽 |

| 信号 | 方向 | 说明 |
|---|---|---|
| clk_100m | in | 宿主 100MHz（`clk_100m_in`），调试输出域 |
| clk | in | `sys_clk`（数据面时钟），主处理域 |
| rst | in | `sys_rst` |
| pkt_din | in `[I_NUM-1:0][DW+CHW:0]` | 展平 `DDR#(512,28)::RES`×2：**两条 DDR 通道的响应流** |
| pkt_dout | out `[N_NUM-1:0][DW+CHW:0]` | `DDR#(512,28)::RES`×3：会话表 / 黑名单 / 主机调试 |

顶接（top.sv DDR_GEN）：`pkt_din = d_rd_res_o[i*2 +:2]`（已由 cfg_res_fifo 从 ui 域跨回 sys 域）；`bus_pkt_dout[0]→session_t_sch.d_rd_res`、`[1]→blacklist_proc.d_rd_res`、`[2]→top_mem_map.ddr_db_rd_res`（DDR_DB_RD_A0 窗口 0x8_009C 与 DDR_DB_RD_D0..D15）。

## 2. 解码逻辑：输入通道位次 + addr[0] 标签

输入 [0] 对应 DDR 通道 j=0 响应、输入 [1] 对应通道 j=1（本工程被注释，恒 0）。每路响应的 `addr[0]` 是源标签：0=表查询、1=主机调试（顶接写入 `{wr_data[28:1],1'b1}` 保证 debug=1）。

| 输出 | 选通条件（L43-52） | 去向 |
|---|---|---|
| out[0] | `pkt_in_d[0].vld & ~pkt_in_d[0].addr[0]` | 会话表 d_rd_res |
| out[1] | `pkt_in_d[1].vld & ~pkt_in_d[1].addr[0]` | 黑名单 d_rd_res |
| out[2] | `(pkt_in_d[0].vld&addr[0]) \| (pkt_in_d[1].vld&addr[0])` | 主机调试，跨钟到 clk_100m |

```systemverilog
// addr[0]=1 的调试响应：端口 0 优先合流（L35-41）
pkt_in_db.vld <= (pkt_in_d[0].vld&pkt_in_d[0].addr[0]) | (pkt_in_d[1].vld&pkt_in_d[1].addr[0]);
pkt_in_db.data<= pkt_in_d[0].vld ? pkt_in_d[0].data : pkt_in_d[1].data;   // addr 同理
```

即综述"0=会话表直通 out[0]、黑名单直通 out[1]、1=调试"成立，但前提是**输入路序固定**；debug=1 的两路调试读汇成一条 out[2]。

## 3. 流水级数

- **非调试路**：`pkt_din → pkt_in_d（打一拍）→ 组合译码 → bus_pkt_dout[0]/[1]（再打一拍）` = **2 级寄存器**流水（都在 sys_clk 域）。
- **调试路**：`pkt_in_d → pkt_in_db（打一拍）→ dc_fifo_across #(DW=540=28+512, DEPTH=5, distributed, AFULL=6, fifo_rdy=1) → bus_pkt_dout[2]`；内部 `fifo_dc` 真异步 FIFO（写侧另有一级寄存 fifo_in_d），**跨到 clk_100m 域**给 top_mem_map 的 DDR 调试读回窗。

## 4. 坑（值得进 faq.md）

- **out[1]（黑名单）实际构建不出数**：其输入 pkt_in_d[1] 来自 DDR 通道 j=1 的响应；当前工程 `ddr_ctrl_1`/`ddr4_1_dns` 整段注释，`d_rd_res[i*2+1]` 强制 0、`init_calib_complete[i*2+1]=0`、`ui_rst[i*2+1]=1`（SIM_MODE=0）→ j=1 读请求永无响应回，`pkt_in_d[1].vld=0`。黑名单若走 DDR 哈希读取，数据出不来（**待核实**：blacklist_proc 是否有独立回读路径或依赖启用 j=1）。同理 j=1 片的主机调试读也失效。
- demux 对「输入路」的固化对应使疑似 swap D0/D1 这类接线错位直接错到别的表——改接时注意 `i*2+/i*2+1` 与 `i*3/ i*3+1/i*3+2` 的位次约定。

## 5. 综述口径修正小结（两文件合）

| 综述表述 | 源码实际 |
|---|---|
| "hash_inv 校验" | 位反转地址映射（地址扩散），非校验和 |
| 周期性 0x5a 自检 | 校准后一次性 POST |
| "4 级流水线 CRC32 哈希" | 在 t_hash_gen 上游，本模块只消费 ch[27:0] |
| "rd_res_demux 按 addr[0] 分发" | 按「输入通道位次 + addr[0]」组合解码 |

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)