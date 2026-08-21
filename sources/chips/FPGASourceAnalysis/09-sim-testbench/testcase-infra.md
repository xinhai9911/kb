# testcase 公共设施（testcase_inc / tc_tasks / tc_prelude / tc_drivers）

> 源路径 `sim/nic_top/testcase/{testcase_inc.svh, tc_tasks.svh, tc_prelude.svh, tc_drivers.svh}`。
> 29 个 `tc*.sv` 各自自带一套相同函数/任务定义（冗余人肉拷贝），这些 .svh 是整理版。tc_prelude 与 testcase_inc 内容高度重叠（tc_tasks 为其扩展版）。

## 1. 字节序转换 BSC 系列

```systemverilog
function automatic logic [63:0]  BSC_64 (input logic [63:0]  din);
  for(int i=0;i<8;i++)  BSC_64[i*8+:8]  = din[63-i*8-:8];
function automatic logic [255:0] BSC_256(input logic [255:0] din);
  for(int i=0;i<32;i++) BSC_256[i*8+:8] = din[255-i*8-:8];
function automatic logic [63:0]  BSC   (input logic [63:0]  din); // 别名→BSC_64
```
网络序（大端）逐字节小端反转。tc_prelude.svh 还定义队列字类型：
- `axis_40g_word_t = bit[290:0]` = {vld(1),last(1),keep(32),data(256),user(1)}
- `axis_10g_word_t = bit[ 74:0]` = {vld(1),last(1),keep(8) ,data(64) ,user(1)}
- 队列数组 `axis_40g_queue_t[1:0][$]`、`axis_10g_queue_t[3:0][$]`（tc1 等用 `bit[290:0] axis_eth_40g_rxq[1:0][$]`、`bit[74:0] axis_eth_10g_rxq[3:0][$]`）。

## 2. TLV 配置任务（3-beat 入 cfg_queue）

三个配置任务把配置写成 cfg_queue 的 3 个 256b beat（i==1 为 beat1，i==2 为 beat2/last，i==0 全 0）：

```
task cfg_session_table(int iter, string fwd_mode, string ip_type);
  // 依据 fwd_mode 装配 tb_nic_top.ft_monitor（512b 期望特征）
  // "map" / "swap" / "route" 三种（block 在 tc12 用到但 ft_monitor 无分支→默认）
  beat1: tlv_din.data = {16'd161, 8'd64, ft_monitor[511-:232]};  // {16b,len?,8b?,ft[279:0]}
  beat2: tlv_din.data = ft_monitor[279-:256];
```

| 任务 | beat1 数据的首 24b | 语义 |
|------|------------------|------|
| cfg_session_table | `16'd161,8'd64` | 会话表 TLV，fwd_mode 决定 ft_monitor |
| cfg_mac_adj | `16'd196,8'd14,16'h10,{6 fa},{6 ba},...` | MAC 地址调整（改写 dMAC=fafafa…/sMAC=bababa…） |
| cfg_ip_blackboard | `16'd151,8'd16,{16 data_8b},~104'h0` | IP 黑板 TLV（tc16/17 用） |

fwd_mode → ft_monitor 尾字段差异（516+? 位核心）：map 尾部 `8'h18,{17 da}…`；swap `8'h14,8'h1,{16 da},16'hffff…`；route `16'h10,8'h51,8'h4,96'h0,32'dada_dadd,16'hffff…`。

## 3. eth_pkt_gen / eth_pkt_gen_10g（发包变体）

`task eth_pkt_gen(eth_id, iter, eth_type(16b), vlan_num, ip_type, fir_mode, len)`：
- `eth_id<2` → 40G 端口：驱动 `axis_eth_40g_rxq[eth_id]`，每 beat 256b，`len` 表示 32B beats；取 `eth_queue[511-256*(i%2)-:256]`（i%2 在高半/低半往返取）。
- `eth_id≥2` → 10G 端口：驱动 `axis_eth_10g_rxq[eth_id-2]`，每 beat 64b，`len` 表示 8B beats；取 `eth_queue[511-64*(i%8)-:64]`。
- **VLAN 语义**：`vlan_num=0` 无 tag；`=1` 1 层；`=2` Q-in-Q 2 层，靠 `eth_queue[511-96:0] << ((2-vlan_num)*32)` 去掉多余 32b 区域。
- eth_type：`0x0800` IPv4、`0x86dd` IPv6、`0x0806` ARP、`0x8847` MPLS（tc19/20/22）。
- `fir_mode`：fin/fin_ack/syn/syn_ack/rst/ack/icmpv4/icmpv6/dns_q/dns_r/tcp/udp/ip_in_ip/mpls → 决定 tcp_flag、dport/sport(53=dns 或 4234/5234)。
- 40G beat 边界：`i==0` vld=1/last=0/keep=~0；`i==len-1` vld=1/last=1/keep=0x01ff_ffff；`i>=len` vld=0。
- 10G beat：`i==len-1` keep=8'h1；`i>=len` vld=0。

tc_tasks.svh 的 packed struct 版（`eth_fixed_hdr_t/vlan_tag_t/ipv4_hdr_t/ipv6_hdr_t/tcp_hdr_t/udp_hdr_t` + `str_to_tcp_flags()`）功能等价，用结构化拼包。其他变体：
- `eth_pkt_gen_10g` / `eth_pkt_gen` 在 tc16/17/20/24/25 中的简化签名（去掉 fir_mode，或对象是统一 64b `axis_eth_rxq[$]`，见 §5）。
- tc32~34 的 6-口 40G 分支用 `eth_queue[767-64*(i%12)-:64]` 12-beat 展开（应对超长）。

## 4. tc_drivers.svh generate 模板（驱动块）

用 generate-if（非 `if）兼容 QuestaSim 10.7c。四个可覆写宏 + undef：

```
`define TC_NUM_40G 0      // 40G 端口数
`define TC_NUM_10G 4      // 10G 端口数
`define TC_10G_CLK_OFFSET 2 // 40G 有口时 10G 驱动仍从 eth_tx_clk[0..] 偏移
`define TC_HAS_40G 0      // 是否含 40G
```
- 40G 块：`if (TC_HAS_40G) for(i<TC_NUM_40G)` 每口一个 `initial`：`#8us`→`@(posedge eth_tx_clk[i])`→ while 弹 `axis_eth_40g_rxq[i]`，写 `inst_top.axis_eth_40g_rx[i]`（vld&last 则清），每 beat 一拍归零。
- 10G 块：`if (TC_NUM_10G)` 每口 `@(posedge eth_tx_clk[i+TC_10G_CLK_OFFSET])`，驱动 `axis_eth_10g_rx[i]`（64b）。
- 宏随后 `undef`（防跨用例污染）。

## 5. 端口接线约定与兼容性

- 当前 RTL top 口：`axis_eth_40g_rx[1:0]`(256b,即网口0~1)、`axis_eth_10g_rx[3:0]`(64b,即网口2~5)。40G=2×，10G=4×（2×40G+4×10G=6 口）。
- **老式用例兼容性坑**：tc16/17/20/24/25 驱动的是统一 `inst_top.axis_eth_rx[i]`（64b×4），而当前 `rtl/top.sv` **没有** `axis_eth_rx` 口（只有 axis_eth_40g_rx/axis_eth_10g_rx）→ 这些用例若直接 vlog 会因层次口不存在而无法驱动报错，属旧 RTL 接口残留（见 testcase-semantics / faq）。
- 三个 6-口新式用例 tc32/33/34 的 10G 驱动用 `eth_tx_clk[i+4]`（第 5~8 个 eth 时钟位）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
