# 上行数据流：up_stream_block / up_stream_unit / rx_info_gen 与写请求转换

源文件：rtl/dma/up_stream_block.v、rtl/dma/up_stream_unit.v、rtl/dma/rx_info_gen.v、rtl/dma/axis_to_native_WrReq.v、rtl/dma/native_WrReq_to_axis.v

## 1. up_stream_block 职责

模块头注释三条：①感知软件对描述符队列的更新（寄存器写）；②从主机取描述符（起始地址）；③向主机**回写描述符（标志位+长度值，共 4 字节）并与报文合并上传**。接线 16 队列×（load/start_addr/num/hdr），参数 `SI_TUSR_W=16`、`QUEUE_COUNT=TRUE_QUE_CNT=6`。

### 1.1 描述符输入整形与分发
`s0`(256b) → `fifo_sync_axis_256x512` → `axis_dwidth_converter_1`（256→64）→ 6 个 up_stream_unit。每拍按 `s_axis_tdest_nrw[$clog2(QUEUE_COUNT)+1:2]`（=tdest[4:2]）选队列分发；`s_axis_tready_nrw` 由目标单元回。未用单元（QUEUE_COUNT..15）读请求恒 0。单元内描述符地址 FIFO（`fifo_addr_out` 64x512）由 `m_ack` 弹出，prog_empty 阈值 `desc_buf_pe_th`。

### 1.2 报文长度缓存
`fifo_sync_fwft_18x1k pkt_length_fifo`：`din={2'd0,rx_len}`、`wr=rx_len_we`（来自 rx_info_gen）、`rd=m_ack`；`m_ack=s1_axis_tlast&s1_axis_tvalid&s1_axis_tready`（整包收毕）。满置 `pkt_length_fifo_full_r`（丢包背压）。注释中长度上传（`m_length`）已停用（ndma_core 里 `wr_length` 也注释），本块只上送地址。

### 1.3 收包队列选择与回写地址
`sof_int_reg` 标记每包 SOF；SOF 拍按 `s1_axis_tdest[$clog2(QUEUE_COUNT)-1:0]`（=tdest[2:0]）查 `desc_no_empty_unit[]`：
- 有队列描述符（FIFO 非空）→ 锁存队列号到 `axis_tdest_tmp`；
- 否则保持旧队列（`QUE_SHARE` 未定义，不做跨队列共享分配）。
`desc_out_unit_d`（描述符地址再寄存一拍）按 `axis_tdest_tmp[2:0]` 选出写地址：`m_addr=desc_out_unit_d[axis_tdest_tmp[2:0]]`。`fifo_addr_out_valid = desc_valid_unit[s1_axis_tdest[2:0]]`。

### 1.4 4 字节描述符 + 报文合并上传
两拍流水 `tdata_sr`[287:0]、`tkeep_sr`[35:0]、`tlast_sr`[1:0]。SOF 拍低 32 位构造回写头：

```verilog
tdata_sr[31:0] <= {s1_axis_tdata, 8'd0, tmp[4:0], pkt_length_fifo_odata[10:0],
                   1'b0, s1_axis_tuser[10:8], s1_axis_tuser[2:0], 1'b1};
```
- bit0=报文有效标志 1；[3:1]=user[2:0]（ACL/黑名单等）；[6:4]=user[10:8]；[11]=0；[22:12]=报文长度（rx_len 缓存）；[27:23]=端口号；[35:28]=0；高 224b 为首拍 28B 数据。
- `tmp` = `tuser[8]?tuser[7:3]:tuser[7:3]`（两分支相同，跨卡标志选择待核实）。
- `m_axis_tvalid` 由 `fifo_addr_out_valid & pkt_length_fifo_valid & s1_axis_tvalid | tlast_sr[1]` 保持；`m_axis_tready_int=m_axis_tready|~tvalid_reg`；`s1_axis_tready = fifo_addr_out_valid & pkt_length_fifo_valid & m_axis_tready_int & ~tlast_sr[1]`。
- `up_str_drop_cntr` 声明未驱动（悬空，待核实）。

### 1.5 读请求两级 4合1 合并
`abtr_4to1`（TDATA_DW=80,TID_DW=9）三级：rd_req_mux0（单元0/1/2，s03 悬空）、rd_req_mux1（单元3/4/5）、rd_req_mux2 合并两路级联输出。mux 输入 tid 抬为 `{s_tid_unit[i][8:1],1'b1}`（bit0 置 1，供 abtr 只统计本类请求——见 down-stream_part2 §4），输出再还原 `s_tid={m1_axis_tid[8:1],1'b0}`。读请求 tdata=`{s_length,s_addr}`，s_req/s_ack 接 ndma_core 的 2to1 汇流。

## 2. up_stream_unit：取描述符 FSM

参数 `DESC_CNT_LEN=13`（环深最大 8192）、`DIFF_DW=14`、`MAX_DESC_NUM=128`。

| 关键量 | 含义 |
|---|---|
| `desc_hdr`[63:0]（入） | 软件已提交描述符累计计数 |
| `desc_til_ofst` | 本单元已取数（Tail 偏移，每 s_axis_tvalid +1） |
| `desc_hdr_til_diff` | = hdr−til，待取数量 |
| `desc_end_til_diff` | = num−til 截断（到环尾距离；按 `up_desc_num[6:13]` 截位，默认 512 档） |
| `num_reg` | min(两 diff)，一次最多取到环尾 |
| `desc_cntr_delta` | 本次请求条数 = `num_reg≥可装空间?可装空间:0`（整批取满策略）；可装空间按 `data_count+MAX<DESC_BUFF_DEPTH-1` 计算 |
| `s_length` | `{3'b0,desc_cntr_delta,3'b000}` = 条数×8B |
| `s_addr` | `{start[63:48], {start[47:3],3'h0} + {ofst_trunc,3'b000}}`（8B 原子对齐，256GB 空间） |

请求仲裁（注释三点）：req 侧 `s_req_seq`（s_req&s_ack 自增）与响应侧 `s_ack_seq`（`s_axis_tvalid&s_axis_tlast` 经 3 拍移位 `desc_ack_seq_incr_sr[2]` 自增）相等，即**上一轮描述符已全部返回**；且 FIFO `prog_empty`（低于 `desc_buf_pe_th`）；且 `|desc_cntr_delta`。满足时 `s_req <= ena`（`ena` 由 `up_desc_load` 置 1）。`s_axis_tready=1'b1` 恒通；溢出（tvalid&full）置 `desc_fifo_overflow`、取到零地址置 `desc_err`。`desc_no_empty=~fifo_addr_out_e`；`s_tid={1'b0,UNIT_NUM[5:0],UP_STREAM,1'b0}`（bit0=0 描述符、bit1=1 上行）。`desc_hdr_til_diff_r` 为调试组合 `{fifo_data_count[3:0],2'h0,fifo_addr_out_data_count[9:0]}`。

## 3. rx_info_gen：RX 收包信息打包

- 输入 256b 收包+tuser，`PPLN_STAGE` 拍缓存；输出整拍**字节反转**（`m_axis_tdata[7+l*8-:8]=s_axis_tdata_int[255-l*8-:8]`）。
- `rx_len`：每拍 +32、tlast 归零；tlast 拍按 `tkeep[7+i*8-:8]`（4 组 8B lane）查表得 `rx_last_cnt[i]`（1..8 有效字节）；`rx_len = rx_len_i + Σrx_last_cnt`，`rx_len_we` 延后一拍置位。`pkt_tdest={1'b0,tdest_int}`。
- 统计：`s_axis_tready_cnt`（1 万拍窗口）、`rx_pkt_cntr`（EOP 计）、`rx_len_max`。输出 rx_len/rx_len_we 供 up_stream_block 长度 FIFO；m_axis 直通 tuser/tdest。

## 4. AXI4 写请求协议转换（纯组合，无寄存）

| 文件 | 转换 | 位布局 |
|---|---|---|
| native_WrReq_to_axis.v | native→AXIS | `m_axis_tdata={data[255:0],addr[63:0],length[15:0]}`(336b)；`m_axis_tkeep={data_keep[31:0],10'h3ff}`(42b) |
| axis_to_native_WrReq.v | AXIS→native | `m_axis_tdata=TDATA[335:80]`；`wr_addr=TDATA[79:16]`；`wr_length=TDATA[15:0]`；`m_axis_tkeep=TKEEP[41:10]` |

即 336 位写请求字统一为 `{数据,地址,长度}`，tkeep 低 10 位固定 0x3ff（地址+长度恒有效）。valid/tready 直通。

> 继续：[up-stream_part2.md](up-stream_part2.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)