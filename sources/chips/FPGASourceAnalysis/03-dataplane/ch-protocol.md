# 「包护照」ch[95:0] / tuser / mod_field / etype 全链位域契约

> 全库字段契约章：汇总裁在 user_bus_def.sv(BUS#/AXI# 宏)、eth/ table/ blacklist/ forward/ i_e_gress/ ddr_ctrl/、dma 各文件头注释与代码位切片的**唯一位域地图**。源路径见各表「写入→消费」。综述 + 模块分析均以此为轴。

## 1. 数据面分段与两种 ch 方言

用户总线统一 256-bit 数据 + 可变 CHW 侧带。ch 沿流水线**两种方言**，语义不重叠：

```
Ingress_chnl(6b) → eth_ul_pkt_parsing_v2(125b) → eth_sta(96b) → [session_t_sch(72b)/blacklist(44b)]
     → crs_crd 185b/181b 会话元数据 → Route_mux(取 187b user) → slp_decode(type) → ch_trf(96b B)
     → tcp_ckes_filter(96b) → mtu → ipv4_ckes_filter(96→97b) → Forward_shunt(44b ovb + 3×96b)
     → Dma_Ses_mux(仅取 sop，ch 弃用)
A 方言（查表段）：sip_hash / five_tuple / mod_field0 / etype8
B 方言（转发段）：ovb / port_shift / ip_shift / pid / eth_outid_globel / etype4 / tracing
```

## 2. 主线 ch[95:0] — 查表前 A 方言（MSB 对齐切片）

来源：eth_ul_pkt_parsing(_v2)/eth_sta/session_t_sch/ipv4_ckes_filter(ul) 头注释。**位值经 eth_sta 交叉验证**（`unsup=ch[19]`、`crc_err=ch[18]` ⇔ mod_field0 b7/b6）。bit60-47 下界待核实。

| 字段 | 位切片 | 写入者 → 消费者 | 说明 |
|---|---|---|---|
| e_f/特殊标志 | [95] | eth_ul_pkt_parsing：ttl<=1\|frag\|tcp_flag\|broadcast_dmac → eth_sta/session | eth_sta 复位置 ses 语义（见 §4） |
| pkt_tracing_hit | [94] | eth_ul_pkt_parsing/position_check → session(→dout2[180])/mod_field1[11] | 采样命中 |
| reserved | [93:92] | — | — |
| sip_hash | [91:64] | eth_ul_pkt_parsing（源 IP/三元组哈希）→ blacklist_proc/session key | 28b |
| five_tuple_hash | [63:36] | eth_ul_pkt_parsing（五元组哈希）→ session_t_sch | 28b；DDR 键 |
| port_shift | [35:28] | eth_ul_pkt_parsing（4b 网口 + L4 偏移）→ position_check/blacklist | 1B |
| ip_shift | [27:20] | eth_ul_pkt_parsing（L3 偏移）→ 同上 | 1B |
| mod_field0 | [19:12] | eth_ul_pkt_parsing | b7=bypass/jumbo、b6=crc err、b5:0=URG/ACK/PSH/RST/SYN/FIN |
| etype | [11:4] | eth_ul_pkt_parsing → 全链 | 8b，见 §5 |
| eth_id | [3:0] | Ingress_chnl(ETH_ID 拼入)/eth_ul_pkt_parsing → 各查表层 | 入口口号 |

## 3. 转发段 B 方言（ch_trf 重编码，Forward_shunt 消费）

来源：ch_trf.sv 赋值表达式 + Forward_shunt.sv 头注释（两处一致）。

| 字段 | 位切片 | 写入者 → 消费者 | 说明 |
|---|---|---|---|
| res | [95:80] | ch_trf 恒 0 | 16b |
| ovb | [79:40] | ch_trf（rss/over_bord/globe_tx_port）→ Forward_shunt 判定 dout_ovb | 40b，子域见下 |
| port_shift | [39:32] | ch_trf（slp_decode l4_offset）→ 刷新/写回阶段 | 1B |
| ip_shift | [31:24] | ch_trf（l3_offset：ipv4 +12 / ipv6 +8）→ 同上 | 1B |
| pid | [23:16] | ch_trf（协议号 17/6/0）→ ipv4_ckes_filter（伪首部） | 1B |
| eth_outid_globel | [15:8] | Route_mux/Replace（源 user[167:160]）→ Forward_shunt **sid 匹配**（同 local_sid/ovc_sid±） | 会话目标 ID |
| etype | [7:4] | ch_trf（type 映射 4b 协议码）→ Forward_shunt/dout_ovb | 见 §5 |
| res | [3:1] | — | 3b |
| tracing | [0] | user[2] 透传 → Forward_shunt（ovb 出口/命中计数） | 1b |

ovb[39:0] 子域（Forward_shunt 注释 + ch_trf 组装式）：

| 位切片 | 字段 | 写人→消费 | 说明 |
|---|---|---|---|
| [39:24] | res | ch_trf 恒 0 | 16b |
| [23:20] | rss | user[187:184] → session/DMA | 4b RSS |
| [19:16] | ovb_flag | ch_trf `{3'b0,user[159]}` → Forward_shunt `ch[59:56]==4'b1` 判出界 | b16=over_bord |
| [15:11] | globe_tx_port | user[164:160] → 跨卡出口 | 5b |
| [10:8] | res | ch_trf 0 | 3b |
| [7:0] | res | ch_trf 0 | 8b |

## 4. 各见网 ch 变体与 mod_field1（全链最一致位域）

`mod_field1[15:0]` 四源吻合（session_t_sch/session 216b、eth_sta、Forward_shunt dout_ovb、dma/single_port_dma tuser）：**b[15:12]rss、b11=pkt_tracing_hit、b10=timeout、b9=mac-not-found、b8=across-card、b7:3=eth port、b2=session refresh、b1=ACL、b0=blacklist**。DMA tuser 布局 b15 rss、b10 timedout、b9 mac-not-found、b8 across-card、b7:3 eth、b2 refresh、b1 ACL、b0 blacklist 与之一一对齐。

| 形态（CHW） | 位切片 | 写入 → 消费 |
|---|---|---|
| ingress ch[5:0] | b5=jumbo、b4=crc、b3:0=eth_id | Ingress_chnl → eth_ul_pkt_parsing_v2（din.ch 注释一致） |
| parsing_v2 ch[124:0] | ch[124]=check_en、[123:110]=check_start、[109:96]=check_end、再下为 A 方言 96b | eth_ul_pkt_parsing_v2 → position_check + 下行 |
| session_t_sch din 96b | A 方言 | eth_sta → session_t_sch |
| session dout0/dout3 ch[71:0] | [71:44]=five_tuple_hash_direction、[43:36]=port_shift、[35:28]=ip_shift、[27:12]=mod_field1、[11:4]=etype、[3:0]=eth_id | session → 后续转发 |
| session dout2 ch[216:0] | [216:185]=vlan_tag0/1、[184:181]=rss、[180]=pkt_tracing_hit、[179:176]=input_eth_id、[175:0]=macid+flag+ethid+natip(16B)+natport(2B)、[19:0]=tc_en+is_down+per_ip_en+line_fc_id+fc_id | 转发元数据（经 crs_crd/qos 携带） |
| crs_crd din ch[184:0] | [184:181]=RSS、[180]=pak_tracing、[179:176]=input_eth_id、[175:0]=macid/flag/ethid/natip/natport、[19:0]=QoS fc 域 | crs_crd（跨卡） |
| crs_crd dout ch[180:0] | 同上除 input_eth_id 改为保留到 [179:176] 可重写 | crs_crd → qos/Route_mux |
| blacklist din ch[71:0] | [71:44]=sip_hash、[43:36]=port_shift、[35:28]=ip_shift、[27:12]=mod_field1、[11:4]=etype、[3:0]=eth_id | session 输出 → blacklist_proc |
| blacklist dout ch[43:0] | [43:36]=port_shift、[35:28]=ip_shift、[27:12]=mod_field1、[11:4]=etype、[3:0]=eth_id | blacklist → Route_mux/bps 流 |
| Forward_shunt dout_ovb ch[43:0] | 同上 | Forward_shunt → 跨卡链路（ovbc_tx） |
| ddr_ctrl rd_res | `DDR#(512,28)` addr[0]=标签：0=session/blacklist 直通、1=主机调试 → fifo 出 dout[2] | ddr_ctrl/rd_res_demux → 各查表层 |

## 5. etype 编码（8b 主版 / 4b 转发版）

| 位 | 8b 主版（查表层/A） | 4b 转发版（B） |
|---|---|---|
| 7:6 | VLAN 层数（0/1/2） | 无（4b 仅协议码） |
| 5 | tcp | — |
| 4 | udp | — |
| 3 | frag 或 broadcast_dmac（v2 亦含 other/未知） | — |
| 2:0 | 0=reserved 1=0x0800(ipv4) 2=0x86dd(ipv6) 4=0x0806(arp) 5=mark ipv4 6=mark ipv6 | 同协议码（1/2/4/5/6） |

B 方言 etype4 是否保留 b7:4 待核实（头注释按 8b 写，但 ch_trf 只给 4b）。

## 6. 187b tuser 位域（Route_mux 输出 / Replace 链携带 / ch_trf 输入）

来源：ch_trf.sv 头注释。`ruser[164:157]` 转发模式译码见综述 §4.2（0x18 虚拟线/0x14 交换/0x12 SNAT/0x52 SNAT+port/0x11 DNAT/0x51 DNAT+port，出 mode[1:0] 00 虚拟/01 路由/10 交换/11 DMA）。

| 位切片 | 字段 | 写入→消费 |
|---|---|---|
| [187:184] | rss | Route_mux/Replace(MAC/IP 改写不触碰) → ch_trf.ovb[23:20] |
| [183:168] | macid_ext | Replace_mac（邻接表 MAC 扩展 ID）→ 下游 |
| [167:160] | eth_outid_globel | Route_mux 会话目标 ID → ch_trf.ch[15:8] → Forward_shunt sid 匹配 |
| [159] | over_bord | 跨卡判定 → ch_trf.ovb b16 |
| [158:143] | port | Replace_port（NAT 端口 16b）→ 改写 |
| [142] | port_flag | NAT 端口标志 → Replace_port |
| [141:134] | macid | 邻接表索引 → Replace_mac |
| [133:6] | ip | 128b 源/目的 IP → Replace_ip（SNAT/DNAT） |
| [5:4] | nat_flag | 00 无/01 snat/10 dnat → Replace_ip |
| [3] | res | — |
| [2] | tracing | pkt_tracing 命中 → ch_trf.ch[0] |
| [1:0] | mode | Route_mux 输出 → 各段行为 |

## 7. 待核实清单

- A 方言 eth_sta 输出若与 parsing 输出位偏移相同但 [95] 重定义为 ses，是否影响下游 session 键——按注释逐位对齐（一致）。
- blacklist/eth_sta 的 48b 旁路流（eth_rx_out_bps2dma）精确位切片。
- Forward_shunt `dout_ovb_lat` 采样 ch[31:0] 的语义。
- B 方言 etype4 位 4..7。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)