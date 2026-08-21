# TLV 配置下发链路（续 2/3）：cfg_ip_parsing

## 4. cfg_ip_parsing —— 以太/IP 字段定位与表项重组

输入 `BUS#(256,2)::C`，输出 `BUS#(256,1)::C`。三级移位 `eth_din_d[3:0]`；`eth_d_comb={eth_din_d[0].data, eth_din.data}`（512b）。

### 4.1 h_field[7:0][10:0] 偏移（**位**偏移，自报文起始）

| 索引 | 含义 | 说明 |
|---|---|---|
| [0] | etype 位偏移 | 无 VLAN=96(12B)；1 VLAN=128(16B)；QinQ=160(20B) |
| [1] | pid_shift | IP 协议号偏移 |
| [2] | ip_shift | SIP/DIP 偏移 |
| [3] | port_shift | sport/dport 偏移（依 IHL/固定） |
| [4] | ttl_shift | TTL 偏移 |

依据 `eth_din.data`（f0 拍）SOP 判 VLAN 层数写 h_field[0]/`pkt_has_vlan`；判 L3 类型在 `eth_din_d[0].sop` 拍写 h_field[1..4] 与 `st_e_feild`。`arp_ipv4 = eth_din_d[0].data[255-h_field[0]-32-:16]==IPV4`（判断 ARP 是否 IPv4 封装，非 IPv4 的 ARP 视为旁路）。

### 4.2 L3 各型字段定位公式（记 E=h_field[0]）

**Ethernet 公共（SOP 拍，st_e_feild）：**
- `dmac=data[255-:48]`；`smac=data[255-48-:48]`。

**IPv4**（IHL 由 `eth_d_comb[511-E-20-:4]*32` 得第 4 字段为"每字 32b"）：

| 字段 | 提取式（512b eth_d_comb / 256b data 窗口） |
|---|---|
| frag | `data[255-E-64-:16]`（第 3 个 16b 组） |
| TTL | `data[255-E-80-:8]` |
| P_ID | `data[255-E-88-:8]` |
| SIP | `eth_d_comb[511-E-112-:32]` |
| DIP | `eth_d_comb[511-E-144-:32]` |
| h[1] pid | `E+16+72` |
| h[2] ip | `E+16+96` |
| h[3] port | `E+16 + (IHL 半字节×32)`，即 `E+16+eth_d_comb[511-E-20-:4]*32` |
| h[4] ttl | `E+16+64` |

**IPv6**（固定 40B 头）：

| 字段 | 提取式 |
|---|---|
| TTL | `data[255-E-72-:8]` |
| P_ID | `data[255-E-64-:8]`（next header） |
| SIP | `eth_d_comb[511-E-80-:128]` |
| DIP | `eth_d_comb[511-E-208-:128]` |
| h[1] pid | `E+16+48` |
| h[2] ip | `E+16+64` |
| h[3] port | `E+16+320`（128+128=256b IP，再 +2×32b 作端口起始 → 320b） |
| h[4] ttl | `E+16+56` |

**ARP**（视为 IPv4 封装 `arp_ipv4`）：

| 字段 | 提取式 |
|---|---|
| SIP | `eth_d_comb[511-E-128-:32]` |
| DIP | `eth_d_comb[511-E-208-:32]` |
| h[1] pid | 0 |
| h[2] ip | `E+16+112` |
| h[3] port | `'d256`（哨兵：走 `eth_bypass`，端口不读） |
| h[4] ttl | `'d256` |

**其它（default，非 IPv4/6/ARP）**：`eth_bypass=1`，所有 h_field=0、st_e_feild 清零、eth_type=OTHERS。

`eth_bypass = r_bypass_en || <pid/frag 无效标志>`（IPv4 用 `ipv4_p_id_invld`、IPv6 用 `ipv6_p_id_invld`、ARP 用 `~arp_ipv4`），三者**恒赋值 'b0**（源码里直连 0，即当前不触发旁路；`r_bypass_en` 默认 0，`~arp_ipv4` 在 ARP 且 IPv4 封装时为 0）→ 本版黑色名单基本全走哈希路径。

### 4.3 L2 端口与哈希队列

- `eth_din_d[1].sop`：`sport/dport = eth_d_comb[767-h_field[3]-:16]/[-16-:16]`（仅 IPv4/IPv6；ARP 取 0）；每拍算 `is_tcp_or_udp = p_id==TCP(1? 见下)||p_id==UDP`。

> ⚠️ `cfg_ip_parsing` 顶部 `localparam TCP=8'd1、UDP=8'd6、ICMP=8'd17`——**疑似与 `user_bus_def` / 数据面的 TCP=6、UDP=17 定义相反/错位**。本模块 `is_tcp_or_udp`、`hash_queue` 用此处 localparam（TCP=1/UDP=6）。与 `session_t_sch` 的 `TCP=8'd6、UDP=8'd17` 不一致，属跨模块命名歧义，**待核实**（黑名单表项组装时按此 localparam 判定是否填 sport）。

- 哈希队列 `hash_queue[1:2]`（64b ×2 路，sip/dip CRC32 并联 `hash_32b_gen`，`crc_en=hash_queue[i].vld`，`rst=eth_din.sop&vld`）：
  - `hash_queue[2]`：`{1'b1,1'b1,1'b0,dip[127-:64]}`（IPv6 取高 64）或 `{1'b1,1'b0,1'b1,dip[0+:64]}`（IPv4 取低 64），依 `{eth_din_d[2].sop,eth_din_d[1].sop}=='h1/'h2`。
  - `hash_queue[1]`：同构，改取 sip。
  - 输出 `hash_o_pre[1:2]` 送 `t_hash_gen`（注意本文件两个 CRC 实例兜底，另有 `t_hash_gen` 内 4 路 CRC）。

### 4.4 输出重组（L3 拍，case = {dout[3].sop,dout[2].sop,dout[1].sop})

| case | 行为 |
|---|---|
| 'h1（仅 dout[1].sop，帧首） | `sop=dout[1].ch[0]?1:0`；`data=dout[0].data`（透传）；`ch=dout[1].ch[0]` |
| 'h2（仅 dout[2].sop，帧中） | 组单拍表项：若 `ch[0]`（会话/mac 替换）→ 透传 `data=dout[0].data`、`ch='b1`；否则（黑名单 add/del）→ 合成 `{16'd151|152, 8'd16, sip[127:0], sport(is_tcp_or_udp), p_id, 80'h0}`、`ch='b0`。**type 151(加)/152(删) 由 `add_cfg` 选** |
| 'h4（仅 dout[3].sop，帧尾） | `eop=1`，`data=dout[0].data` 透传，`ch=dout[1].ch[0]` |
| 其它 | `eth_dout='h0` |

> 即：**会话/ACL/邻接 TLV**→`cfg_ip_parsing` 近似透传（仅重排/打 SOP/EOP），黑名单则在此被合成为原生 151/152 单拍载荷（含 sip+sport+pid）。`ch[0]` 语义：0=黑名单、1=会话/mac 替换。


> 继续：[part3](tlv-config-path_part3.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
