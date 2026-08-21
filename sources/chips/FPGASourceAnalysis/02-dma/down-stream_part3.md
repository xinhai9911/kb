# 寄存器配置通路：axi_lite_slave、axi_master_0_axi_periph 与 BD 封装

源文件：rtl/dma/axi_lite_slave.v、rtl/dma/axi_master_0_axi_periph.v、rtl/dma/bd/design_bd_wrapper.sv

## 1. axi_lite_slave：DMA 控制/状态寄存器从

AXI-Lite 从：写地址+写数据同拍才拉 `wready/awready` 并锁存 `wr_reg_addr_in/reg_data_in`，下一拍 `reg_wr_in` 产生一次写译码。读 `s_axi_arready` 一 拍脉冲、`s_axi_rvalid/rdata` 次拍送上。核心功能：

| 地址 | 字段 |
|---|---|
| 0x000 | test_reg（默认 0x2025） |
| 0x4500/4520 | `desc_queue_hdr_srart_addr`（HDR 指针区基址，软件写） |
| 0x4540/4560 | `desc_queue_til_srart_addr`（TIL 区基址） |
| 0x4600..4666 | `channel_num_reg_0..3`，钳位到 [1, QUEUE_COUNT=6] |
| 0x4000 | `DMA_RESET`：写 bit0=1（或写 DEBUG_49）置 `resetn_sr=0` → 8 级移位后 `dma_resetn` 拉低复位 |
| 0x7044 AM_BW | `m_axi_aw_bw_ctrl`（钳 ≤1000，默认 1）→ axi_master_new 写带宽门 |
| 0x7048 / 704C | `dma_up_desc_buf_pe_th`（默认 320）/ `dma_down_desc_buf_pe_th`（默认 70），钳 ≤510 → 各描述符 FIFO 的 `prog_empty_thresh` |
| 0x7050 / 7074 | `m1_trdy_ignr`（忽略 m1_axis_tready）、`cntr_dw`（abtr 窗口位，默认 20） |

**描述符装载与 load 产生**：队列 j 基址 `DOWN_ADDR_L0=0x020/H0=0x040/LEN0=0x060`、UP `0x080/0x0A0/0x0C0`，各 +j*256。每次写命中对应 `tx_addr_we_l/h/desc[j]`（上拍寄存）→ 3bit 计数器 `tx_addr_we_cntr[j]`，**三次写齐**（ADDR_L、ADDR_H、LEN）后 `down_desc_load[j]=&cntr`；up 侧同（`rx_addr_we_cntr`）。`down_descriptor[j]/up_descriptor[j]`（80b={`len[15:0],addr[63:0]`}）拼成 `down/up_descriptor_0[1279:0]` 输出。`desc_queue_hdr_load/til_load` 为 PTR_START(2) 的 L、H 都写过才拉高（2bit 计数）。

**读译码**：descriptor0 六条、PTR 四条、CHNL、`RX_PKT_CNT_0..7`/`DROP_PKT_CNT_0..7`（来自 st_gp_fifo_w360 的 rx_eof_cnt/drop_frm_cnt）、AM_BW/阈值/TR_IG/CNTR_DW、`DEBUG_0..7`（down/up hdr_til_diff 0..3）、`DEBUG_10`（down_tx_pkt_cnt_qu0）、`DEBUG_24..44`（rxinfo 最大长度、aw/w/ar/r 计数、每秒统计、til_ofst 0..3 down/up）；`default` 返回全 1（广播未定义区）。

## 2. axi_master_0_axi_periph：配置总线路由（AXI-Lite 跨接）

把软件一条配置总线（S00，250MHz，AXI-Lite）经 FIFO 缓冲拆成两段扇出：

- **FIFO 层**：写地址 `sc_fifo_ctrl`（64b 深 5）、写数据 `dc_fifo_across`（地址+数据合 64b 跨钟到 M02 域）、读地址 `sc_fifo_idx`、读数据回 `dc_fifo_across`；`SIM_MODE=1` 时 S00 禁用、由 S01 替代（逻辑镜像）；正常模式 S01 全 0。
- **地址分流**：`ADDR_AREA=48'h10000`。`<0x10000` → `M00_AXI`（DMA 寄存器域，S00 时钟，b 响应同钟）；`>=0x10000` → 异步 FIFO → `M02_AXI`（m02 域，100MHz，接另一外设/表项空间）。`M01` 未用（恒 0）。
- **宽度适配**：S00 数据 256b 但只抛 32b 字——写用 `wdata[w_addr_hold[4:2]*32+:32]` 按地址低 5 位选字，读用 `{8{M00_AXI_rdata}}` 复制 32b 到 256b。
- 两句 FSM（`wr_state` 0=idle 1=wr）处理写握手；`s_axi_awrdy/s_axi_wrdy/s_axi_arrdy` 均一拍脉冲。

## 3. design_bd_wrapper：XDMA/BD 封装壳

Vivado 生成的顶层 wrapper（参数 `SIM_MODE`=0 板卡 / 1 全芯片系统仿真 / 3 TLP 仿真；`ID`=卡号用于仿真模型选端口）。generate 三段结构：

| 分支 | 内容 |
|---|---|
| MODEL_GEN | SIM_MODE=1：`design_1_xdma_0_0`（XDMA 行为模型）兜底 AXI↔TLP；3：`axi_vip_m0` 兜底 |
| WRAPPER_GEN | 例化 `design_1`（BD，DMA/描述符/指针寄存器全在此，网表无 RTL） |
| TLP_PROC_GEN | SIM_MODE=0/3：`axi2pci`（AXI-full ↔ XDMA TLP 流：RQ/RC/CQ/CC）+ `pci_xil_core_wrapper`（8 lane，ref_clk 差分，`user_clk→pcie_axi_clk`、`user_reset→pcie_axi_rst`）；否则（=1）reg_axi_core 全 0 |

**角色接线**：
- DMA 主口 `dma_m_axi`（256b AXI-full，来自 axi_master_new）：→ axi2pci 的 s_axi（到主机内存）；axi2pci 的 m_axi 侧 → `dma_s_axi` 交回 BD（主机侧描述符/表项读回通路；方向以 BD 网表为准，待核实）。
- 对外业务口：`s_axis_0`（RX 收包，tdest 4b 拼 `{1'b0,tdest}` 成 5b）、`m_axis_0`（TX 下行报文，tdest[8:0]）、`cfg_axis_0`（下行表配置 AXIS）、`wr_drop_flag`（st_gp_fifo_w360 丢弃指示）、`channel_num[3:0]`。
- 寄存器口三路：`reg_axi_0`（主控软件）、`reg_axi_1/2`（其他卡块/外设，在 BD 内经 axi_master_0_axi_periph 分发）、`reg_axi_core`（内部，axi2pci 的寄存器空间入口）。
- 时钟：`m02_clk`（100MHz 外设域）、`m_dna_clk`（DNA 读）、`cfg_axis_0_aclk`（配置域）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)