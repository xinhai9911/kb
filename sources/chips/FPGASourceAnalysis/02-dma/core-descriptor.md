# ndma_core 与 defines.v：6 队列 DMA 描述符环核心

源文件：rtl/dma/ndma_core.v、rtl/dma/defines.v

## 1. 工程常量（defines.v）

| 宏 | 值 | 说明 |
|---|---|---|
| `NSFOCUS_KU060X2` | 1 | 器件宏（KU060×2 板卡）；`QUE_SHARE` 未定义 → 队列不共享 |
| `QUEUE_COUNT` | 6 | DMA 队列数（工程名 *6que*）；`TRUE_QUE_CNT=QUEUE_COUNT<2?2:6` |
| `UP_STREAM` / `DOWN_STREAM` | 1'b1 / 1'b0 | 流量方向标志，编码进 tdest[1] 与读请求 tid[1] |
| `DESC_BUFF_DEPTH` | 512 | 每队列描述符缓存条目数 |
| `REG_ADDR_WIDTH` / `DATA_WIDTH` | 16 / 32 | AXI-Lite 地址/数据位宽 |

寄存器偏移（axi_lite_slave 译码用）：`DOWN_ADDR_L_0/H_0/LEN_0 = 0x020/0x040/0x060`，`UP_ADDR_L_0/H_0/LEN_0=0x080/0x0A0/0x0C0`（队列 j 再加 `j*256`）；`DMA_RESET=0x4000`；`PTR_START[L/H]=0x4500/4520`、`PTR_START2[L/H]=0x4540/4560`（队列指针区起始地址，由软件配置）；`CHNL_NUM_0..3=0x4600/4620/4640/4660`；`RX_PKT_CNT_n/DROP_PKT_CNT_n=0x4700+8n`；`AM_BW=0x7044`、`UP_BUF_PE=0x7048`、`DOWN_BUF_PE=0x704C`、`TR_IG=0x7050`、`CNTR_DW=0x7074`（abtr 仲裁窗口位选择）；`DEBUG_0..49=0x5000..0x5364`（读回统计）。

## 2. 参数与接口

参数：`SI_TUSR_W=16`（RX tuser 位宽）、`PPLN_STAGE=2`（透传通道拍数）。描述符/指针总线：

| 信号 | 位宽 | 说明 |
|---|---|---|
| down/up_descriptor | 1280 | 16 队列×80 位描述符（§3） |
| down/up_desc_load | 16 | 每队列一条「软件已提交」脉冲（axi_lite_slave 三次写齐后产生） |
| down/up_desc_hdr | 1024 | 每队列 64 位软件侧累计计数（只进 py ptr_poll_block） |
| down_desc_til | 512 | 16 队列×32 位「已取走描述符」计数（供软件回读） |

AXIS 通道：`s0_axis`=主机下发（描述符+下行报文复用，256b/tdest[8:0]）；`s1_axis`=RX 收包（256b/tdest[4:0]/tuser）；`m0_axis`=上行回写主机（直连 up_stream 的 m_axis）；`m1_axis`=下行业务报文；`m2_axis`=下行镜像/配置报文。native 请求：写 PCIe `wr_addr=up_m_addr`（`wr_length` 源已注释、停用）；读 PCIe `rd_length/rd_addr/rd_req/rd_tid/rd_ack`。

## 3. 描述符环与 1280 位描述符格式

每队列 80 位，`addr[63:0]` 在 `[i*80+63-:64]`、`desc_num[15:0]` 在 `[i*80+79-:16]`：

```verilog
assign down_desc_start_addr[i] = down_descriptor[i*80+63 -: 64];
assign down_desc_num[i]        = down_descriptor[i*80+79 -: 16];
```

- `start_addr`：环基址（软件配置，对齐 8B）；`desc_num`：环深度（2 的幂，默认档 512）。
- `desc_hdr[63:0]` 每队列为**计数值不是地址**（注释原文），= 软件已写入描述符累计数；与硬件 Tail 偏移 `desc_til_ofst` 之差即待取描述符数。
- 环翻转：AXI MASTER 的 burst 为 INCR 型，队列指针到结尾反转时**只取 Tail→环尾**一段（up/down_stream_unit 均如此），靠 2 幂深度使偏移自然回绕归零。
- `TRUE_QUE_CNT=6`，但描述符总线与 debug 寄存器仍按 16 队列索引（部分未用）。

## 4. 通道拆分：s0_axis_tdest[1:0] 译码

| tdest[1:0] | 去向 | 说明 |
|---|---|---|
| 2'b10（`{UP_STREAM,1'b0}`） | up_stream_block s0 | 上行描述符输入 |
| 2'b00（`{DOWN_STREAM,1'b0}`） | down_stream_block s0 | 下行描述符输入 |
| 2'b01（`{DOWN_STREAM,1'b1}`） | m1_axis 透传 | 下行业务报文；`m1_trdy_ignr` 可忽略 m1_tready |
| 2'b11 | m2_axis 透传 | 下行镜像/配置报文 |

```verilog
assign up_s_axis_tvalid = s0_axis_tvalid & ({`UP_STREAM,1'b0}==s0_axis_tdest[1:0]);
m1_axis_tdest_sr[0]     = {2'd0, s0_axis_tdest[8:2]}; // [8:4] port id、[3:2] 队列0~3、[1:0]=00
```
m1/m2 各经 `PPLN_STAGE=2` 级移位寄存器（tdata/tkeep/tdest/tlast/tvalid）输出；`s0_axis_tready` 按四路 ready 组合译码。m1 的 tdest 由 s0 描述符 tdest 派生 → 下行报文的 port id/队列号回传由描述符流携带。

## 5. PCIe 读请求汇聚

up/down 两侧读请求经 `axis_interconnect_2to1 mux_Req_Rd`（Xilinx IP）合并：S00=上行（up_s_req/TID）、S01=下行；`S01_ARB_REQ_SUPPRESS(up_s_req)` 实现上行优先。合并输出 `{length[15:0], addr[63:0]}`（80b）→ `rd_length=TDATA[79:64]`、`rd_addr=TDATA[63:0]`、`rd_tid=TID`。写方向仅收包（上行）做 PCIe 写。

## 6. 调试/统计

- `down_pkt_cntr`：m1 通道完整报文计数。
- `down_desc_til_reg[i]`：s0 流中 tdest[0]=1 且 tdest[$clog2(TRUE_QUE_CNT)+1:2]==i 的完成计数（debug 只读）。
- 输出 `down/up_desc_hdr_til_diff_[0..3]`（hdr 与 til 差）、`down/up_desc_til_ofst_[0..3]` 供 AXI-Lite DEBUG 寄存器。
- `up_str_drop_cntr` 在本版 up_stream_block.v 为悬空输出（未驱动，待核实），ndma_core 仅透传。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)