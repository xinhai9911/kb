# 上行数据流：axi_master_new（AXI4 主）与 st_gp_fifo_w360（收包跨时钟缓存）

源文件：rtl/dma/axi_master_new.v、rtl/dma/st_gp_fifo_w360.v

## 1. axi_master_new（模块名 `axi_master`）总览

256-bit AXI4 full 主接口。写方向：`s_axis`(收包)+`wr_addr` → AW/W/B；读方向：`rd_req/rd_addr/rd_length/rd_tid/rd_ack` → AR/R，回读数据走 `m_axis`（`m_axis_tdest = m_axi_rid_int`，透传路由 ID=txn 的 tid，下游据此分队列）。固定：`awid=arid=0`、`awsize=arsize=5`(32B)、`awburst=arburst=1`(INCR)。写请求带宽控制：`clk_cntr` 按 `m_axi_aw_bw_ctrl`（寄存器 AM_BW）周期翻转 `aw_phase`，`m_axi_awvalid=fifo_val_1&aw_phase`（限制 AW 发射速率）。

## 2. 写通道：4K 分段 + WR_FSM_NORMAL/STOPONE

- **长度来源**：`wdata_len = {4'b0, s_axis_tdata[18:8]} + 4`，取收包首拍内嵌长度字段（up_stream_block 合并头 [22:12] 的低位），+4B 为 4 字节描述符回写头。
- **4K 分段**：第一片地址即 `wr_addr`，第二片 `wr_addr_frgmnt={wr_addr[63:12],12'd0}+4096`。`wr_awlen_frgmnt` 第一片 = `(wr_addr[11:0]+wdata_len)>4096 ? 127-wr_addr[11:5] : m_axi_awlen_int`；第二片按 `wr_total_addr_byte_len=wr_addr[11:0]+wdata_len-4096` 取整。写请求 FIFO（`fifo_sync_fwft_72x512`，72b={awlen,addr}）跨片时写两条（`wr_desc_fifo_we=wr_cntr_incr | wr_cntr_incr_ff1&~total[12]&|total[11:0]`）；`m_axi_awaddr/awlen` 取 fifo 头，`m_axi_awvalid=fifo_val_1&aw_phase`。
- **写数据两级流水**：stage1 拼 512b 数组（`s_tdata_r1`，`s_sof` 标记 SOF）；`wr_data_stopone_i` = 地址低 7 位+长度低 7 位 ≥64 → 末拍后多填一拍。状态机：
  - `WR_FSM_NORMAL`(2'h1)：`m_axi_wready&tvalid&tlast&stopone` → `WR_FSM_STOPONE`
  - `WR_FSM_STOPONE`(2'h2)：补一拍（valid=1,buffer 右移 256b），wready → NORMAL
  stage2 按 `wr_addr_r1[4:0]` 对齐出 256b（`s_tdata_r2`）。
- **4K 边界插 tlast**：`wr_curr_addr_ls12b` 跟踪当前拍 Byte0 低 12 位（SOF 用 `{wr_addr[11:5],5'b0}` 初始化）；`s_axis_tlast_frgmnt=(12'hFE0==wr_curr_addr_ls12b)`；`m_axi_wlast = s_tlast_r2 | s_axis_tlast_frgmnt`。
- **反压**：`s_axis_tready = m_axi_wready & (WR_FSM_NORMAL==wr_fsm_curr)`（STOPONE 停收输入）。写响应：`m_axi_bready` 在 bvalid 后一拍置位收下（无一拍留空）。

## 3. 读通道：4K 分段、tkeep 对齐与 ID 追踪

- **4K 分段**：`rd_req_stopone`、`rd_addr_frgmnt`（第二片 +4096）、`rd_length_frgmnt`；`rd_bytes_delta=rd_length_frgmnt+rd_addr_frgmnt[4:0]`，`m_axi_arlen=bytes_delta[12:5]-1+|bytes_delta[4:0]`。
- **异常检查**：宏 ERR_CHK 恒为 1'b1；`m_axi_arvalid = rd_req_frgmnt & ERR_CHK` 丢弃 0 地址/0 长度请求；`rd_req_error`/`wr_addr_err` 在分片地址低 40 位 `< start_addr[39:0]` 时置位（`end_addr` 只声明未用）。
- **`rd_ack = m_axi_arready & ~rd_req_stopone`**（跨 4K 时仅第一片回调给请求源，unit 据此增 `s_ack_seq`）。`rd_frgmnt_type[1:0]`（bit1 是否分段、bit0 是否第一片）与 `rd_addr_frgmnt[4:0]`、`bytes_delta_minus_one[4:0]` 打包 18b 进 `rd_descriptor_fifo`，rlast 时弹出。
- **`rid_fifo`**(18x1k) 在 AR 握手时入 `arid`，rlast 时弹，`m_axi_rid_int` 作为当前返回拍路由 ID → m_axis_tdest。
- **`rd_back_data_fifo`**（xpm，257b，深度 32，fwft，distributed）把 rvalid 与 m_axis_tready 解耦（`m_axi_rready=~full`，`m1_axi_rready=m_axis_tready`）。
- **tkeep 生成**：`m_axis_tkeep_tmp` 按 `{m_axi_sof_int, m_axis_tlast_tmp}` 四态用 FIFO 首/末偏移位（[9:5]=末偏移、[4:0]=首偏移）构造掩码；`m_axis_tlast = tlast_r1 | tlast_tmp & ~tkeep_tmp[off]`；`m_axis_tvalid` 组合逻辑处理分段间 valid 拉低/重拉高的三态；输出从 512b 组合数组 `{m1_axi_rdata, m_axis_tdata_r1}` 按偏移截取。
- **统计**：250MHz 每秒（`cntr_to_250m`=249,999,999 计时）输出 `desc_beat_cnt_ps/pkt_beat_cnt_ps/read_req_cnt_ps/read_resp_cnt_ps/desc_req_cnt_ps/pkt_req_cnt_ps/ptr_req_cnt_ps/arready_cnt_ps`；`awready_cnt_p10k_clks` 按 1 万拍窗口。分类按 `rid_int`/`arid_int` 的 bit8/bit0：`!{id[8],id[0]}`→desc、`id[0]`→pkt、`id[8]`→ptr（指针类请求来源待核实）。累积计数器 `aw_cntr/w_cntr/ar_cntr/r_cntr`。

## 4. st_gp_fifo_w360：收包跨时钟缓存（带丢包）

模块头注释：数据流通用异步 FIFO，带丢包功能，可用位宽 360b，由 5 个 BRAM36K 构成。参数 `TUSER_DW=16、TDEST_DW=5、LEN_CHK_DW=1、PORT_CNT=8`；`NSFOCUS_KU15P_FRAME` 分支深度 4096，否则 `ADDR_WIDTH=10`（1024 深，本工程）。

- **存储**：`xpm_memory_sdpram`（360×深，block 原语）；写词 `rx_fifo_wdata = {49'b0, tdest[4:0], tuser[15:0], sof(289), tlast(288), tkeep[31:0](287:256), data[255:0]}`；读侧 `[310:290]={tdest,tuser}`、`[288]`=tlast。读地址灰度码 `bin2gray/bin gray2bin` 同步，`addr_diff=rd_addr_bin-wr_addr` 判定满。
- **写侧**：`wr_axis_tready=1'b1` 恒通（由丢包替代反压）；`rx_enable` 由 `|up_desc_load[QUEUE_COUNT-1:0]` 置位（软件配完队列使能后放行）；`val_frm_chk`（LEN_CHK=1：tlast 前是否出现过数据拍）做最小长度校验。**丢包 3 条件**：①`bram_full`（写指针多转一圈追近读指针：`addr_diff[ADDR_WIDTH-1:3]==0 & |addr_diff[2:0]`，写指针回退到 `wr_addr_start`）；②`~val_frm_chk` 长度非法；③未使能。每收一合法包 `wr_tgl` 翻转（跨时钟做 frm_wr）、`rx_len_we→o_rx_len_we` 脉冲、`wr_drop_flag` 在未使能/近写满时拉高。
- **读侧**：5 态 FSM `RD_IDLE→RD_FIRST_WORD→RD_LOAD_FETCH→RD_TX→RD_EOF`（预取 2 拍找 SOF），`rd_axis_tvalid=rx_fifo_ok`；包计数 `pkt_cnt` 在 frm_wr/frm_rd 增/减，`pkt_cnt_mt1`（>1）保证不早读；`rx_done_rd=ram_do[288]`（tlast）。
- **统计**：端口 ID `wr_port_id=wr_axis_tuser[7:3]-block_ofst`；GEN_STATISTICS 生成 8 计数器，按 `wr_port_id[4:2]==0?k<4:k>=4` 把 8 个 `rx_eof_cnt/drop_frm_cnt` 映射到两组 4 端口（每块 4 口），`k[1:0]==wr_port_id[1:0]` 精确匹配。读侧 `tx_eof_cnt` 采样 `rx_fifo_rdata[72]`（tdata 数据位，待核实）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)