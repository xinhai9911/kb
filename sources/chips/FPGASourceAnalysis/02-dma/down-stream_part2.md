# 指针轮询/回写寄存器库、RXQ 解复用与 4 合 1 仲裁、读请求转换

源文件：rtl/dma/ptr_poll_block.v、rtl/dma/ptr_update_block.v、rtl/dma/axis_demux.sv、rtl/dma/abtr_4to1.v、rtl/dma/axis_to_native_RdReq.v、rtl/dma/native_RdReq_to_axis.v

## 1. ptr_poll_block：描述符环**头指针**（desc_hdr）寄存器库

软件经 AXI-Lite 写入的头指针镜像（HDR 计数值，64 位/队列），供 ndma_core 的 `up/down_desc_hdr[1023:0]`。接口为 AXI-Lite 从（12b 地址）：`wready` 由 aw+w 同时有效脉冲（`reg_wr_in=~wready & awvalid & wvalid & !awaddr[1:0]`）；读 `s_axi_rvalid/rdata` 由 `rready`（=arvalid 一拍）驱动。

寄存器布局（字选择 = `wr_reg_addr_in[11:2]`，j 以 2 步进，覆盖 `QUEUE_COUNT=6` 个队列）：

| 字地址 | 内容 |
|---|---|
| 偶字（j）| 块 0·`up_desc_hdr_0[j*32+:32]` |
| 奇字（j+1）| 块 0·`down_desc_hdr_0[j*32+:32]` |
| +32 字 | 块 1（up/down_desc_hdr_1） |
| +64 / +96 字 | 块 2 / 块 3（up/down_desc_hdr_2/3） |

即 `up_desc_hdr_0~3`、`down_desc_hdr_0~3` 共 8×1024b 输出；每队列 64b 分高/低两次写。读回 `reg_data_out = rd_data_array[31+32*rd_reg_addr_in[6:2] -: 32]`，其中 `rd_data_array` 只组装**块 0**（`up_desc_hdr_0[k*64+:32]` 与 `down_desc_hdr_0[k*64+32+:32]`，块 1~3 读回已注释，待核实）。**机制：软件写 HDR 区 → 库同步 → ndma_core 按 hdr 增量取描述符，实现无门铃轮询（DMA 自查计数差）**。

## 2. ptr_update_block：描述符环**尾指针**（desc_til）回读库

`down_desc_til_0[511:0]`（16×32b，来自各 down_stream_unit 的 `desc_used`）拼接为 `down_desc_til = {3*512'h0, down_desc_til_0}`（2048b）；软件读任意字 `reg_data_out = down_desc_til[rd_reg_addr_in[5:0]*8 +31 -: 32]`。写/读握手逻辑与 ptr_poll_block 相同但**无写寄存器译码**（写通路空闲）。对应「DMA 回写 TIL、软件轮询读」的完成通知路径。

## 3. axis_demux：RXQ 1→4 解复用

纯组合（无寄存）：按 `s_axis_tdest[1:0]` 选通 4 路 `m_axis_*_tvalid`，tdata/tkeep/tuser/tlast 整体复制到 4 路；`s_axis_tready` 按 `m_axis_*_tready & (tdest[1:0]==x)` 组合。输出 `m_axis_X_tdest = {1'b0, s_axis_tdest[6:0]}`（保留下行 port id 字段、高位清零；`local_sid` 端口声明未用）。用于把下行报文/配置 AXIS 分配到 4 个 RX 队列。

## 4. abtr_4to1：4 合 1 加权仲裁（流量均衡）

设计思路（头注释）：在一定时间间隔内按 4 路请求**长度累计和进行优先级排序**，以期流量均衡。要点：

- 窗口：`cntr` 为 32b 计数器，`acc_clr = cntr[cntr_dw]`（`cntr_dw` 寄存器选窗口位，默认 20 → 约 1M 拍）；`timer_pulse=acc_clr`。
- 统计：`len_acc[i] += req_len[i]`（`req_len` 取 `tdata[TDATA_DW-1:64]`），**仅 `s_axis_tid[i][0]==1` 的请求记入窗口**——这正是 up_stream_block 把读描述符请求 tid[0] 临时抬 1 的原因。窗口终了快照 `req_x_bytes_ps/req_x_times_ps`。
- 排序：3 级流水线。stage1 两路两两比出 `{max,min}`；stage2 大值比大值得最大值、小值比小值得最小值；stage3 比较中间两个完成全排序 → `id_lsd_r3 ≤ id_lsd2_r3 ≤ id_msd2_r3 ≤ id_msd_r3`（按累计长度升序的服务优先级）。
- 调度：`tval_vector[i]` 从 `info_ppln_r0`（同步寄存的 4 路 valid）按排序 id 取；`s0X_axis_tready = m00_axis_tready_int & (id 匹配 & 对应优先级位有效)`；`m00_axis_tready_int = m00_tready | ~m00_tvalid`（一次性押注转发，单拍）。合并输出 tdata/tid 按各口 tready 掩码相或在组合逻辑中完成（非"或"BUG：每拍唯一选中）。

## 5. 读请求 native↔AXIS 转换（纯组合，无寄存）

| 文件 | 方向 | 映射 |
|---|---|---|
| native_RdReq_to_axis.v | native→AXIS | `tdata={rd_length,rd_addr}`(80b)、`tid=rd_tid`、`valid=rd_req`、`rd_ack=tready` |
| axis_to_native_RdReq.v | AXIS→native | `rd_length=TDATA[79:64]`、`rd_addr=TDATA[63:0]`、`rd_tid=TID`、`rd_req=tvalid`、`tready=rd_ack` |

即 80 位读请求字 `{长度,地址}` + 9b tid 在 AXIS 单令牌与 native req/ack 之间直接映射，可任意插入/替换总线段的封装。

> 继续：[down-stream_part3.md](down-stream_part3.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)