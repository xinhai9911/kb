# 黑名单 / 端口组 / 报文回放：blacklist_*、port_group、pkt_replay 深读

> 源路径：`rtl/blacklist/{blacklist_filter.sv, blacklist_proc.sv, blacklist_tcam.sv, tcam_mem_map.sv}`、`rtl/port_group/{pg_req.sv, pg_tab.sv, pg_top.sv, port_group.sv}`、`rtl/pkt_replay/{pkt_rply.v, pkt_rply_defines.v, pkt_rprx_comb.v}`
> 定位：综述 §4.8（blacklist DDR 哈希键=sipH32+sipL32+sport+pid、命中丢；TCAM 死代码）、§4.12（port_group LBS 寄存器）、§4.13（pkt_rply 回放）。本文补深三者的**寄存器位图、流水时序、常量/解析逻辑**，不复述综述。top 上 `bypass_en=r_bypass_en[i][5]|r_table_clear[i][0]`（见综述，非恒定）。

## 1. tcam_mem_map 寄存器位图

`rtl/blacklist/tcam_mem_map.sv`。BASE_ADDR 参数化，blacklist_tcam 实例处 `BASE_ADDR=24'h8_9000`（clk_100m 域，复位用 `clk_100m_unlock`）。32-bit 读写，只读计数器 + 一个写寄存器。

| 偏移(BASE+...) | 名称 | 方向 | 位宽 | 说明 |
|---|---|---|---|---|
| 0x00 | DIN0_SOP | RO | 32 | `i_din0_sop[31:0]`（入包 sop 计数） |
| 0x04 | DOUT0_SOP | RO | 32 | `i_dout0_sop[31:0]`（出包 sop 计数） |
| 0x08 | DOUT1_SOP | RO | 32 | `i_dout1_sop[31:0]`（drop_flag[1] 计数，DDR 溢出丢包） |
| 0x0c | DOUT2_SOP | RO | 32 | `i_dout2_sop[31:0]`（drop_flag[2] 计数，fifo 满丢包） |
| 0x10 | TCAM_INFO_0 | RO | 32 | `{12'h0, fifo_afull[1:0], fifo_empty[1:0], 6'h0, sbiterr, dbiterr, debug_status[7:0]}` |
| 0x14 | TCAM_INFO_1 | RO | 32 | `st_e_feild.sip[31:0]`（最近一条 sip 低 32） |
| 0x18 | TCAM_INFO_2 | RO | 32 | `m_axis_lkup_tdata[103-:32]`（TCAM 查找响应高 32） |
| 0x1c | TCAM_INFO_3 | RO | 32 | `buf_afull_cnt`（缓冲满计数，见 §3） |
| 0xfc | BUS_CHECK | RO/W | 32 | 写时存 `mem_in.wr_data`，读回自身 |

- 读通路两级流水：`rd_req`→`rd_data_pre`→`rd_vld/rd_data` 各一拍（`rd_vld<=rd_vld_pre`）。
- 写：仅 `BUS_CHECK` 可写；`case({mem_in.address[23:2],2'd0})` 把地址低 2 位清零参与译码，故 word 地址按 4 字节对齐。
- 注意 `i_din0_sop` 等在 blacklist_tcam 内部是 48-bit `dsp_macro_cnt` 输出，此处只取低 32；`i_tcam_info[1]` 依赖 TCAM 死代码内的 `st_e_feild`（§2 说明 `if(0)` 分支里该逻辑也被裁剪，实际回填 0 — **待核实**）。

## 2. blacklist_proc：generate if(0) 死代码与 AXI 旁路

`rtl/blacklist/blacklist_proc.sv` 是 total 与 filter 间的壳层，含两处关键：

- **`bus_c_sch` 调度器**：`N_NUM=2, DEPTH=8, DW=256, CHW=72`，把两路 `b_list_in[0:1]`（CHW=72）合一路 `eth_din`（CHW=72）送入 blacklist_filter。
- **`generate if(0) ... else`**：综述已述 TCAM 死代码。此处补细节：`TCAM_ADD` 分支永远不综合，实际走 else 分支：
  - `eth_dout0 = eth_tcam_in`（filter 的 eth_dout0 直通，无 TCAM）——即 TCAM 数据通路被 `eth_tcam_in` 直连取代。
  - `mem_out = mem_out_pre[0]`（filter）`| mem_out_pre[1]`（TCAM 恒 `'h0`），故 TCAM 寄存器全部失效。
  - **AXI 被 `axi_cam_slave` 吸走**：只取 `wdata[7:0]`/`rdata[7:0]`、`wstrb[0]`、awaddr/araddr 高位置 19'h0——即 AXI 总线在顶层被一个 8-bit 空壳 CAM 从机挂死（配置无效，合法握手但数据不落地）。`axi_tcam.awaddr` 位宽 13、`wdata` 32 在注释里为 tcam_64p 保留。

对比 `blacklist_filter.sv` 是**当前生效**的黑名单查表主体（§3），`blacklist_tcam.sv` 是**不综合**的 TCAM 版本（§4）。

## 3. blacklist_filter：DDR 黑名单查表流水

`rtl/blacklist/blacklist_filter.sv`。三级移位 `din_d[2:0]` + 链路对齐的 FTP/FIFO，思想同 session 查表但**键更短、无 NAT**。

### 3.1 ch 与键布局

| 位 | 宽 | 含义 |
|---|---|---|
| [71:44] | 28 | sip_hash（HASH_FLAG=71，`ch[71 -:25]<<3` 作 DDR 读地址） |
| [43:36] | 8 | port_shift（L4 偏移，字节） |
| [35:28] | 8 | ip_shift（L3 偏移，字节） |
| [27:12] | 16 | mod_field：b15:12=rss，b11=pkt_tracing_hit，b10=timeout，b9=mac 未命中，b8=跨卡，b7:3=eth 口，b2=会话表刷新，b1=ACL，b0=blacklist |
| [11:4] | 8 | etype：b7:6=vlan 层数，b5=tcp，b4=udp，b3=frag/bcast-dmac，b2:0=1 ipv4/2 ipv6/4 arp/5·6 mark |
| [3:0] | 4 | eth_id |

DDR 比较键（`pkt_ft_in.data` ≤128b）：`{sip[127:96], sip[31:0], sport, p_id}`，即 **sipH32 + sipL32 + sport(16b) + p_id(8b)**——比综述的 "sipH32+sipL32+sport+pid" 更精确：p_id 是协议号（8b），**DPORT 不参与黑名单比较**。局部量 `TCP=1/UDP=6/ICMP=17`（注意 session 表里 TCP=6/UDP=17，此处协议号映射相反 — 与上游契约一致，勿混淆）。

### 3.2 三级流水与字段提取

- **L0（din_d[0].sop）**：`bypass_en` → `etype_encode[0]=4'h7`（全旁路编码）；否则 0。`st_e_feild.eth_type <= eth_din.data[255-96-:16]`。
- **L1（din_d[0]/din_d[1]）**：按 `din_d[0].ch[4+:3]` 分 ipv4(1/5)/ipv6(2/6)/arp(4)：
  - ipv4/arp：`sip<=eth_d_comb[511-ip_shift*8 -:32]`、`dip<=…-32`、`p_id<=eth_d_comb[511-ip_shift*8+24 -:8]`。
  - ipv6：sip/dip 各 128-bit，`p_id<=eth_d_comb[511-ip_shift*8+16 -:8]`。
  - sport/dport 在 `din_d[1].sop`（L1）用 `port_shift` 取：`ch[5:4]>0 ? eth_d_comb[767-port_shift*8 -:16] : 16'h0`。
- **L2（din_d[2].sop）**：`fifo_din` 门控 `din_no_drop[2] & ~etype_encode[2][2]`（etype b2=0 才进，即黑名单只处理 ipv4/ipv6，arp/mark 被滤）；`pkt_ft_in.addr <= {ch[71 -:25],3'h0}`；发 `d_rd_req`（sop/eop/vld 同拍）。`d_rd_req.data={hash_o_pre[31-:25],3'h0}`，其中 `hash_o_pre` 来自 `hash_32b_gen` CRC，输入 `hash_queue`：
  ```systemverilog
  case({din_d[2].sop,din_d[1].sop})
    'h1 : hash_queue = {1'b1,1'b1,1'b0, st_e_feild.sip[127 -: 64]}; // sipH64
    'h2 : hash_queue = {1'b1,1'b0,1'b1, st_e_feild.sip[0   +: 64]}; // sipL64
  ```
  即先对 sip 高 64 做一轮 CRC，再对低 64 做一轮，最终 `d_rd_req.data` 为该两轮状态（`rst=din_d[0].sop` 每包清零）。DDR 行地址 = CRC 高 25 位 `<<3`（512-bit 行）。

### 3.3 三个 FIFO 与匹配

| FIFO | RAM | DEPTH/AFULL | 内容 |
|---|---|---|---|
| ddr_resp_fifo | distributed | 6/6 | 88b：`d_rd_res.data[127-:88]`（DDR 响应键段） |
| ft_info_fifo | block | 8/184 | 88b：`pkt_ft_in.data[127-:88]`（CPU 配置的期望键） |
| eth_data_fifo | block | 9/48 | 整包数据+muxed ch（44b） |

- 匹配在 `pkt_ft_out.vld`（ft_info_fifo 读出）时做 4 位比较 `pkt_ft_match[3:0]`：
  - b3=sipH32 相等；b2=sipL32 相等。
  - b1=sport 相等 **或 DDR sport==0（通配）**。
  - b0=p_id 相等 **或 DDR p_id==0（通配）**。
- 全匹配 `pkt_ft_match==4'hf` → `session_state[3:0]='h0`（命中即丢，不转发、不送 CPU）；不匹配 → `'h1`（首包，`eth_dout0` 去 CPU 建表）。
- `session_state[3]=sample_pkt_hit`（采样命中；`s_rate_cfg[16]` 使能且 `~w_fwd_act[1]` 时）。

### 3.4 输出

- **eth_dout0（ch 44b→内部 `CHW+4`）**：`(session_state[0]|session_state[3])` 门控，即首包或采样才出；ch 拼装时把 `session_state[3]` 写进 `ch[12]`（`{4'h0, ch[43:13], session_state[3], ch[11:0]}`）作采样标识。
- **eth_dout1（ch 44b）**：bypass/超时旁路 —— `din_d[0] & (din_no_drop[0] ? etype_encode[0][2] : 1'b1)`（旁路时 etype_encode[0][2]=1 放行）。
- **w_fwd_act[0]**：ST_SCH 寄存器 `o_fwd_act[0]` 置位时强清 `eth_dout0_pre`（丢该包），实现开关丢包。
- 计数：`dsp_macro_cnt` CE 分别打在入 sop / `dout_sop_inc[0]`(首包) / `dout_sop_inc[1]`(采样) / `dout_sop_inc[2]`(命中丢 p0_drop) / eth_dout1.sop（bypass）。`pkt_tracing_detection` 三级生成 `pkt_tracing_db[1:0]`。

> **仅命中丢、无修改字段**：黑名单不查 NAT、不翻 MACID，命中只在 `mux_vld&tab_vld` 处把包丢弃（`pkt_ft_match==4'hf` → dout0 不发）。DDR 回写 `ddr_ft_info_db.data={data[24+:488],24'h?}` 只在 `db_fwd_cfg[1]` 与匹配方向组合时置 24'h1/0 —— **DDR 写路径实际使能与否取决于 `o_db_fwd_cfg`，源码未闭环**（待核实）。


> 继续：[part2](filters-portgroup-replay_part2.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
