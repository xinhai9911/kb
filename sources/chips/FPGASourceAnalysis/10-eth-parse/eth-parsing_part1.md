# eth_ul_pkt_parsing v1/v2 上行包解析深度分析（part 1：解析器本体）

> 覆盖 `rtl/eth/eth_ul_pkt_parsing.sv`（v1，2023-02-22，727 行）与 `eth_ul_pkt_parsing_v2.sv`（v2，2026-06-25，836 行，重构候选）。综述 §4.7 一句话覆盖，本文补成专章。`pkt_parsing_sch`/`pkt_parsing_mem_map`/`eth_reset`/`data_led` 见 [part 2](eth-parsing_part2.md)。源路径统一记 `rtl/eth/xxx.sv`，行号指源码。

数据面位置（每通道 4 口）：`eth_rx_pkt_sch`(3→4) → 本解析器 ×4 → `pkt_parsing_sch`(4→1) → `position_check`(CRC16) → `eth_sta`。top.sv `ETH_PARSER_GEN`：`.ETH_ID(i%4)`、入 `eth_rx_sch_in[i]`（`BUS#(256,6)::C`）、出 `pkt_parsing_sch_in[i]`（`BUS#(256,125)::C`）、`mem_out[i/4][i%4+1]`。bypass_en 三档（i<4：`{r_bypass_en[1][2:1],r_bypass_en[0][1]}`；i≥4：`{r_bypass_en[1][4:3],r_bypass_en[0][2]}`）。

## 1. 接口与输出布局：v1/v2 完全一致

两版**端口列表逐位相同**（v1:44-54、v2:43-53）：`clk/rst`、`bypass_en[2:0]`、`pkt_tracing_cfg`、`pkt_tracing_db`、入 `eth_din`、出 `eth_dout0`、`clk_100m_in/clk_100m_unlock`、`MEM#(32)` 配置口。背景「v2=AXIS→BUS」**与源码不符**：两版 `eth_din` 均已是 `BUS#(256,6)::C`（AXIS→BUS 转换发生在更上游 `Ingress_chnl`）。

`din.ch[5:0]`：b5=jumbo、b4=crc err、b3:0=eth_id。`dout0.ch[124:0]` 两版**布局逐位相同**（头注释与代码切片均一致）=「检控头 + A 方言 96b」：

| 位切片 | 字段 | 说明 |
|---|---|---|
| [124] | check_en | 协议深检使能，进 `position_check` |
| [123:110] | check_start | 14-bit 包内字节偏移（检控窗口起点=载荷偏移） |
| [109:96] | check_end | 14-bit 字节偏移 = start + 检长 |
| [95] | 特殊标志 | ttl≤1 \| frag \| tcp_flag[2:0] \| broadcast_dmac |
| [94] | pkt_tracing_hit | 解析器恒写 0，由 `pkt_tracing_detection` 采样计数 |
| [93:92] | reserved | 恒 0 |
| [91:64] / [63:36] | sip_hash / five_tuple_hash | 方向归一化 / 固定序哈希，各 28b |
| [35:28] / [27:20] | port_shift / ip_shift | h_field[3]/[2] 低 8 位（L4/L3 偏移） |
| [19:12] | mod_field | b7=bypass/jumbo、b6=crc err、b5:0=TCP flags |
| [11:4] / [3:0] | etype / eth_id | 见 §5；eth_id 透传 |

下游消费见 `03-dataplane/ch-protocol.md` §2、`01-common/parse-hash-demux_part1.md` §1。

## 2. 以太头检测：h_field[0]（VLAN/MPLS）

SOP 首拍按 256-bit 总线 MSB 对齐判以太类型（`data[255-96 -:16]`）。v1 三块手写 always_ff；v2 重构为 `vlan_mpls_detect()/vlan_count()/vlan_tag_val()` 函数（语义等价）。

| 条件（逐级） | 含义 | h_field[0] | pkt_has_mpls | pkt_has_vlan |
|---|---|---|---|---|
| =8100 && [255-16B]=8100 && [255-20B]=8100 | 3 VLAN | 24 | 0 | 3 |
| =8100 && [255-16B]=8100 | V-QINQ | 20 | 0 | 2 |
| =8100 | 单 VLAN | 16 | 0 | 1 |
| =8847/8848 && bit120 | 1 MPLS | 18 | 1 | — |
| …&& ~bit120 && bit88 | 2 MPLS | 22 | 2 | — |
| …&& ~bit88 && bit56 | 3 MPLS | 26 | 3 | — |
| 其余 | 无 tag | 12 | 0 | 0 |

`vlan_tag(32b)`={最外层 TCI, 次层 TCI}（单 VLAN 高 16 补 0）供 mem_map 端口读口。`h_field[0]` 用 `eth_din.data` 判、`pkt_has_vlan/vlan_tag` 用 `eth_din_d[0].data` 判（差一拍，v2 注释「保留原时序」）。

## 3. 8~10 级流水：字段提取

`eth_din_d[12:0]`、`eth_dsop_d[8:0]` 同移；两拍合并窗 `eth_d_comb_pre={din_d[0],din}`、`eth_d_comb={din_d[1],din_d[0]}` 供桶式取字段。

| 阶段 | 触发 | 动作 |
|---|---|---|
| C0 | `din.sop` | h_field[0]/pkt_has_mpls；bypass 三档（ch[2:1]==00→en[0]；~ch[0]→en[1]；ch[0]→en[2]）；pkt_len_cnt<=2 |
| C1 | `dsop_d[0]` | 锁 DMAC/SMAC；8×48b `dmac_cfg_table` 逐字节比对；pkt_has_vlan；**IPv4/ARP 解析**→`st_e_feild_pre`+`h_field_pre[1..4]` |
| C2 | `dsop_d[1]` | **IPv6 解析**（`ip_head_data_d1[335-:16]==86DD`，或 4b==6&&MPLS）；否则透传 pre；h_field[1..4] |
| C3 | `dsop_d[2]` | hash_available[1]=属 IP；sport/dport（TCP/UDP）、tcp_flag（TCP，偏移-104B）、l4_h_len（TCP 偏移-96B，否则 4'h2） |
| C4 | `dsop_d[3]` | h_field[5]=h_field[3]+l4_h_len*4（非 TCP/UDP=0） |
| C2~C6 | `dsop_d[2..6]` | 五元组 5 字喂 `hash_32b_gen`（见 part 2 §1） |
| C7 | `dsop_d[7]` | pkt_less_64（`din_d[6].eop && 0<left<28`）、broadcast_dmac=`din_d[7].data[248]` |
| C8 | `din_d[8].sop` | 组装 ch[95:0]+check_en；data 透传 |
| C9/C10 | — | `pre[1]<=pre[0]`；`eth_dout0<=pre[1]` |

头注「相邻两包 SOP 间隔≥8 拍」：C7 才判 broadcast/less_64、C8 组装，间隔不足时这些标志/数据窗错位。

## 4. L3 字段提取

`ip_head_data`(256b)=`eth_d_comb_pre[511-h_field[0]*8 -:256]`（v2 等价 `>>(256-h_field[0]*8)`）；`ip_head_data_d1`(336b) 再补 `eth_d_comb` 低 80b（h=24/26 跨界 `eth_din.data` 补高位）。`st_e_feild`=`ETH_FIELD`（`user_bus_def.sv:99-114`）。

| 协议 | 判据 | 字段位移（h_field） |
|---|---|---|
| IPv4 | 头16b==0800 | l3_h_len=IHL 半字节、l3_len、frag、ttl、p_id、sip/dip={96'h0,32b}；pid=h0+11、ip=h0+14、port=h0+2+IHL*4、ttl=h0+10 |
| IPv4-MPLS | 头4b==4 && mpls | 同上各 +16B；pid=h0+9、ip=h0+12、port=h0+IHL*4、ttl=h0+8 |
| IPv6 | 头16b==86DD | l3_h_len=10、sip/dip 128b；pid=h0+8、ip=h0+10、port=h0+42、ttl=h0+9 |
| IPv6-MPLS | 头4b==6 && mpls | 同上 +16B；pid=h0+6、ip=h0+8、port=h0+40、ttl=h0+7 |
| ARP | 头16b==0806 | sip={96'h0,[128]32b}、dip={96'h0,[208]32b}；pid=0、ip=h0+16、port/ttl=256 |
| 未知 | else | 全 0、`eth_bypass_pre[0]=1` |

sport/dport 非 TCP/UDP 置 0；tcp_flag 非 TCP 置 0；ARP 非 IPv4（`arp_ipv4` 0）强制 bypass。

## 5. ch 组装：mod_field / etype

`ch[19:12]`=mod_field0：b7=`eth_bypass[6]|din_d[8].ch[5]`（bypass/jumbo）、b6=`din_d[8].ch[4]`（crc）、b5:0=`tcp_flag[5:0]`=URG/ACK/PSH/RST/SYN/FIN。

`ch[11:4]`=etype8（ch[7:6]=VLAN 层数、[5]=tcp、[4]=udp、[3]=frag\|broadcast、[2:0]=协议码）：

| eth_type | ch[11:10] | ch[9] | ch[8] | ch[7] | ch[6:4] |
|---|---|---|---|---|---|
| IPv4 | pkt_has_vlan | p_id==TCP | p_id==UDP | frag\|bcast | dmac_vld_d[6]? 1（ipv4）: 5（mark） |
| IPv6 | 同上 | 同上 | 同上 | 同上 | dmac_vld_d[6]? 2: 6 |
| ARP | 0 | 0 | 0 | bcast | 4 |
| 其它 | — | — | — | — | 整字节 8（未知） |

`dmac_vld_d` 链：d0=6 组 cfg 任一全字节 `&`；d[5:1] 移位；d6=`vld[5]|~dmac_check`；d7=`dsop_d[8]&&bcast` 强制 1 否则 vld[6]。`dmac_drop_cnt`(16b) 在 `din_d[9].sop && ~vld[7]` 计数（读口 DMAC_H 高 16）。`eth_bypass` 7 位链：`sip==0` 时置 1。

## 6. check_en 协议位置检测（14-bit 语义）

check_en 标「需 CRC16 深检区间」，进 `position_check` 后 `start[13:5]`=包内行号（32B/行）、`[4:0]`=行内字节；position_check 把 end 再减 `ch[114:110]`（=start[4:0]）。两值=**相对帧头字节偏移**，`start`=载荷偏移 `h_field_d1[5][10:0]`。

| sport | 名称 | IPv4 min l3_len→检长 | IPv6 min→检长 |
|---|---|---|---|
| 23 | FTP-Ctl | 77→24 | 57→24 |
| 21 | FTP-Data | 86→33 | 66→33 |
| 143 | SIP | 95→42 | 75→42 |
| 110 | POP3 | 72→19 | 52→19 |
| 80 | HTTP | ≥1258→38 | ≥1258→38 |
| 3306 | MySQL | ≥125→34 | ≥106→34 |

HTTP start=`l3_len - l3_h_len*4 - l4_h_len*4 - 729 + h_field[5]`（IPv4；IPv6 无 l3_h_len 项）；MySQL start=`h_field[5]+7`。v1 12 分支 else-if；v2 参数化 `check_en_cfg_t`+`CHECK_CFG[4]`+for（`~found` 独立判断，等价）。**综述 §4.7「Telnet+24/FTP+33/IMAP+42」与 v2 名称映射不符（源码 23=FTP-Ctl/21=FTP-Data/143=SIP/110=POP3），命名待核实**。

## 7. v1↔v2 差异速查

| 维度 | v1 | v2 | 行为 |
|---|---|---|---|
| 例化 | top.sv ×8 在用 | 全库 grep 仅 sim 编译清单，**未例化** | 重构候选 |
| VLAN/MPLS 判定 | 3 手写 always_ff | 3 个 function | 等价 |
| ip_head_data | case 8 分支 | `>>(256-h_field[0]*8)`+`unique case` | 等价 |
| check_en | 12 else-if | 参数表+for+`~found` | 等价 |
| 常量化 | 魔法字面量 | DMAC_H/ETH_TYPE_H/MPLS_BOS_* localparam | 可读性 |
| data 透传 | 独立 always_ff | 并入组装块 | 等价 |

两版 `hash_direct/hash_available/pkt_len_cnt/i_pkt_db_info`、`seop_check`（4×8b SOP/EOP 平衡）、子模块（`pkt_parsing_mem_map` BASE 0x8_5000+ETH_ID*0x100、2×`hash_32b_gen`、2×`dsp_macro_cnt`、2×`pkt_tracing_detection`）一致。

> 继续：[part 2：哈希 / 调度 / 寄存器 / 复位 / LED](eth-parsing_part2.md)