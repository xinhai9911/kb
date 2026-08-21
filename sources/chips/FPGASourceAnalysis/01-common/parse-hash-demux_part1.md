# 协议识别/哈希/解复用（common/parse-hash-demux）– part1

> 覆盖 rtl/common/ 的 `position_check`（CRC16 协议识别）、`axis_rxq_demux`（AXIS 收包解复用）、`sdip_hash_gen`（RSS 四元组哈希）。CRC16/CRC32 原语簇与 `eth_pkt_gen` 见 [part2](parse-hash-demux_part2.md)。源路径统一记 rtl/common/xxx.sv。

## 1. position_check —— CRC16 协议识别 + 命中分流

数据面位置：`pkt_parsing_sch`(4→1) 之后、`eth_sta` 之前（top.sv `PROC_GEN`），输入 `BUS#(256,125)::C`（ch[124]=check_enable、ch[123:110]=check_start_point、ch[109:96]=check_end_point，起点由 eth_ul_pkt_parsing 的协议位置检测给出），输出双路：普通流 `BUS#(256,96)::C eth_dout`（未命中）与命中流 `BUS#(256,48)::C eth_dout_match`（进 DMA）。

**流水结构**（全 9 拍对齐）：
1. `eth_din_d[2:0]` 三级移位 + `eth_din_sop_d/eop_d` 9 位移位寄存器；`pkt_cnt` 逐拍递增。
2. `check_start_match/check_end_match` = `pkt_cnt == point[13:5] && check_enable`（[13:5] 为包内行号，[4:0] 行内字节偏移）。
3. CRC 窗口拼接：`data_selt_tmp = {din_d[1].data, din_d[0].data}`（64B 对齐），`crc16_data_tmp = data_selt_tmp[(64-check_start_point_d1[4:0])*8 -: 256]` —— 从行内偏移处切 32B 窗口；`crc16_data_mask` 按 `check_end_point_d1[4:0]` 生成 0~256 bit 掩码表，结束行掩尾。
4. `crc16_vld`（restart→end_match/eop 之间）、`crc16_restart`（起始行）、`crc16_clear`（eop 后）送 `crc16_pipeline`，得 16 位 CRC。

**协议判决**（`crc_dout` 阈值比对，eop 后第 8 拍打点）：

| 协议 | CRC16 魔值 | ch 中协议号 data_check_id |
|---|---|---|
| telnet | e6f5 | 1 |
| ftp | c225 | 2 |
| imap | 9049 | 3 |
| pop3 | b3e4 | 4 |
| http | 231c | 5 |
| mysql | 3074 | 6 |

- `data_check_wen` 在 eop 后 8 拍置位，`data_check_match=1` 时 `match_cnt+1`（top_mem_map `POSITION_MATCH` 读）。
- 两路对齐：数据流 `presch_fifo`(DEPTH=9) 与结果 `presch_fifo_result`(DW=4, DEPTH=9) 配对，`data_check_rdy = data_dout_rdy&&vld&&eop` 同步出数。
- 匹配包 `eth_dout_match.ch[47:0] = {data_check_dout, sport_shift, sip_shift, mod_field, etype, eth_id}`，其中 `mod_field = {rss, pak_tracing, …, eth_id, …}`；**rss 由 dma_chnl_num 动态解码** `ch[91 -:10]`（chnl 3/6 为分段门限桶 0~13、chnl 4 取 `&4'b1011`、其余直取 `ch[91-:4]`）——按 DMA 通道数自适应 4-bit RSS。
- 元素提取：`sport_shift=ch[35-:8]`、`sip_shift=ch[27-:8]`、`eth_id=ch[19-:4]`、`etype=ch[31-:8]`、`pak_tracing=ch[94]`。
- bypass=1（`r_bypass_en[i][14]`）恒判定不命中。

## 2. axis_rxq_demux —— 收包解复用/降维（PU 边界）

- 输入 `BUS#(256,44)::C`，先经 `payload_hash_gen`（**内嵌**，算 3 种 CRC32 载荷哈希、把 RSS 等写入 sop 数据，见综述 §4.14），再压成输出 `AXI#(256,20)::S`：`user[19:16]`=DMA 队列号（取 `ch[27-:4]`）、`user[15:0]`=dma_field（`ch[27-:16]`）。
- 关键生成块 `DATA_SCH_GEN`/`CH_DATA_GEN` 的 **genvar i<1** —— 尽管 N_NUM 默认 4，当前实际只展开第 0 路（其余 `pkt_dout[i]=bus_pkt_dout[i]` 悬空）。`fifo_afull_db=|fifo_afull`。
- **降位宽**：44b 解析侧 ch 浓缩为 20b DMA user；`dma_feild_db`（sop 采样 `{12'h0,ch[3:0], ch[12+:16]}`）供驱动观察。
- 跨时钟：`dc_fifo_across`(block, DEPTH=9, AFULL=296) `wr_clk→rd_clk`（top 里 wr=rd=sys_clk，架构上预留 MAC/DMA 时钟差异）。
- 输出 AXIS 化：`keep=left2keep(left)`（left=0 全 1，否则 `0xffffffff<<(32-left)`）、`last=eop`、`user=ch[19:0]`；`din_no_drop` 与调度器同款「sop 拍 afull 即整包丢」。
- 字节顺序：`bsc()` 对 data 做 4×8B 组内字节反转（大端化），配合 AXI-S 网络序。
- 附带 4× `pkt_tracing_detection`（N_NUM=1, DW=16），按 `user[17:16]` 队列号把 `user[11]` 命中各记 16b，出 `pkt_tracing_db[1:0][31:0]`；双时钟 `{clk_100m_in, rd_clk}` 计数。
- 寄存器：`mem_out` 透给 payload_hash_gen（HASH_* 配置），`bypass_en`=`r_bypass_en[i][10]`。
- top 实例：`inst_axis_rxq_demux`（N_NUM=CHNL_ETH_NUM, CHW=48），入 `axis_rxq_in`、出 4×`ul_dma_in[i*4+:4]` → DMA 上行。

## 3. sdip_hash_gen —— RSS 四元组哈希 + 跨卡槽位注入

- 输入 `AXI#(256,8)`（AXI_EN=1 时 `trf_data()` 字节反转转 BUS::C），经 XPM_AXIS_FIFO（32 深、common_clock、**PACKET_FIFO=false**）缓冲，`pkto.user` 被哈希结果改写。
- 头解析：`din_ff[0].data` 以太类型逐层读 `8100`(1~3 层 VLAN)、`0800`(IPv4)、`86dd`(IPv6)，生成 `sip_shift/dip_shift`（无 VLAN: 26/30B；1/2/3 VLAN 依次 +4），IPv6 再 +8/+16。
- 三拍窗口 `din_ff_comb={din_ff[1],din_ff[0],din}`（768b），`din_ff_cnt` 指示行号，`din_ff_cnt == shift[5]` 时从 `din_ff_comb[767-shift[4:0]*8 -:32]` 取 `sip/dip`。
- `hash_32b_gen`（rst=ip_vld_ff1 每包重初始化、crc_en=ip_vld）对 `{sip,dip}` 算 CRC32；`result_wd=crc_out[2:0]`（非 IP 用 `ip_no_vld_cnt`），经 3bit `sc_fifo_idx` 与 `result_empty` 门控输出。
- **槽位注入**：`pkto.user = bypass? pkt.user : (result_rd[2]==0 ? local_sid[0]+result_rd[1:0] : local_sid[1]+result_rd[1:0])` —— CRC 低 3 位选卡侧与 4 子槽，实现 RSS 跨卡均匀。
- 调试输出全 `hash_gen_*`（sip/dip/result/port + `hash_gen_d={user_abort,out_of_range,pkto_rdy,pkti_rdy,i/o_pcnt,i/o_lcnt_max}`）→ top_mem_map（HASH_SIP…HASH_D）；`out_of_range` 检 user[7:2]∉{0,5}、`user_abort` 检非首拍 user 突变。
- top 实例：每通道一个，插在 `crs_crd`→`numa_din` 前（pcie_axi_aclk 域），对应综述「RSS 哈希分布」。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)