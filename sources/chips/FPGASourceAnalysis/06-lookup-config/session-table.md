# 会话表查询引擎：session_t_sch（查表 FSM 与输出路由）

> 源路径：`rtl/table/session_t_sch.sv`
> 定位：数据面 256-bit 总线管线中段，top 挂 `mem_out[i][6]`；本模块内 `st_sch_mem_map` BASE_ADDR=`24'h8_6000`（clk_100m 域）。上游 eth_sta，下游 blacklist_proc。top 上 `bypass_en=r_bypass_en[i][5]|r_table_clear[i][0]`（非固定旁路）。**st_sch_mem_map 全寄存器 / RSS 配置 / 老化 / 线速限速见 [session-table_part2.md](session-table_part2.md)。**

## 1. 接口一览

| 信号 | 类型 | 方向 | 说明 |
|---|---|---|---|
| eth_din | BUS#(256,96)::C | in | 输入流，ch[95:0] 见 §2 |
| eth_dout0 | BUS#(256,72)::C | out | 首包/采样/SYN-FIN 刷新/超时/MAC 未命中包（去 CPU） |
| eth_dout2 | BUS#(256,205)::C | out | 命中转发包（带 205b 元数据） |
| eth_dout3 | BUS#(256,72)::C | out | ARP/免查包（不查 DDR） |
| d_rd_req | BUS#(28,0)::B | out | 五元组哈希→DDR 读；data=hash[27:3]<<3 |
| d_rd_res | DDR#(512,28)::RES | in | DDR 512-bit 会话条目 + 28b addr |
| ddr_wr_sch_in | BUS#(512,28)::C | out | SYN/FIN 时间戳刷新写 |
| sl_wr_req/sl_rd_res | BUS#(16,21)::D / BUS#(1,24)::D | out/in | 线速限速字节计数回路（见 part2 §9） |
| macid_addr/vld | 17b/1b | out/in | 邻接表查询：{vld,MACID[15:0]} |
| st_timeout/gbl_timeout/gbl_us_out | 32b/48b/20b | in | 超时配置与全局 48-bit 时间基点 |

## 2. 输入 ch[95:0] 布局（会话键上游契约）

| 位 | 宽 | 含义 |
|---|---|---|
| [95] | 1 | ttl<=1 或 frag 或特殊 tcp_flag 或广播 DMAC（免查标记） |
| [94] | 1 | pkt_tracing_hit |
| [93:92] | 2 | reserved |
| [91:64] | 28 | five_tuple_hash_direction（RSS 键） |
| [63:36] | 28 | five_tuple_hash（DDR 行号源，高 25 位<<3 作地址） |
| [35:28] | 8 | port_shift（L4 相对偏移，字节） |
| [27:20] | 8 | ip_shift（L3 相对偏移，字节） |
| [19:12] | 8 | mod_field：b7=bypass/jumbo，b6=crc error，b5:0=URG/ACK/PSH/RST/SYN/FIN |
| [11:4] | 8 | etype：b7:6=VLAN 层数，b5=tcp，b4=udp，b3=frag/broadcast，b2:0=1 ipv4/2 ipv6/4 arp/5·6 mark |
| [3:0] | 4 | eth_id（源端口） |

代码常量：`HASH_FLAG=63`、`RSS_FLAG=91`、`MARK_DROP=6`（ch[6]=无效 DMAC 标记，路由丢包条件）、`F_CTRL_FLAG=19`、`TCP=6/UDP=17`。

## 3. 查表流水级次（三级移位 + FIFO 排队）

- **L0（din_d[0]）**：`etype_encode` 分类 `{b2=免查}`：① bypass_en 或 ch[95] 置位 ② ARP（ch[6:4]==4）③ 非 TCP/UDP（ch[9:8]==0）→ 免查；否则查 DDR。免查包不进 fifo、不发 d_rd_req、不建 pkt_ft_in，直接 dout3 旁路。
- **L1（din_d[1].sop）**：`st_e_feild` 提取。按 etype_encode[1]：ipv4 取 `eth_d_comb[767-ip_shift*8-:32]`/`-32`，p_id 由 ch[9:8] 译码（10→TCP6、01→UDP17），tcp_flag 取 ch[12+:8]；ipv6 取 128-bit；arp 取 32-bit。sport/dport 按 `port_shift`。同拍算 `vlan_tag={tag1,tag0}`（ch[11:10]==2/1/0）与 `eth_id_i_gbl`（非 switch：`ch[3:1]==0?local_sid+ch[0]:ovc_sid+ch[2:0]-2`；switch：`data[255-96-24-:8]-100`）。
- **L2（din_d[2].sop）**：组 210-bit `pkt_ft_in`、发 d_rd_req，进 4 个 FIFO：`ddr_resp_fifo`(472×7)、`ft_info_fifo`(238×9)、`eth_data_fifo`(61+data×10)、`byte_cnt_fifo`(16×9)。四队列同序配对；`ddr_rd_rdy` 按 `rd_gap_lvl`(1~2 拍) 动态背压（短包带宽 64×75%/67.5%/60%）。

### pkt_ft_in[209:0] 比较键布局

| 位 | 内容 | 位 | 内容 |
|---|---|---|---|
| [209] | ipv6 标志 | [103:72] | ipv6?sip[127:96]:{8'hff,smac[23:0]} |
| [208] | trunk_port | [71:40] | sip[31:0] |
| [207:168] | vlan_tag+eth_id_i_gbl | [39:24] | dport |
| [167:136] | ipv6?dip[127:96]:{8'hff,smac[47:24]} | [23:8] | sport |
| [135:104] | dip[31:0] | [7:0] | p_id |

## 4. DDR 条目 512-bit 布局（会话键字段）

| 位 | 字段 | 用途 |
|---|---|---|
| [511:480] | DIP H32 | 比较 dip 高 32 |
| [479:448] | VLAN | 比较 vlan_tag |
| [447:416] | TIMESTAMP0 | 时间戳（SYN 写） |
| [415:384] | DIP L32 | 比较 dip 低 32 |
| [383:352] | SIP H32 | 比较 sip 高 32 |
| [351:320] | VLAN#2 | 代码强制`[320+:32]='h0` |
| [319:288] | TIMESTAMP1 | 时间戳 |
| [287:256] | SIP L32 | 比较 sip 低 32 |
| [255:216] | DPORT+SPORT+P_ID | 端口/协议比较 |
| [215] | safe_zone（高位） | 与 trunk 共同门控 b5 |
| [214:208] | ETHID_I 低 7 | 与入向全局口比较 |
| [207:192] | MACID | macid_addr；dout2 macid |
| [191:184] | FLAG | 0x18 虚拟线/0x51 DNAT/0x52 SNAT；b[188:186]==100→路由；b189=丢弃 |
| [183:176] | ETHID_O | 出向口（-local_sid/-ovc_sid/+1-100 三口径） |
| [175:48] | NATIP | 16B NAT IP |
| [47:32] | NATPORT | 2B NAT 端口 |
| [31:0] | F_CTRL | 强制`[7:0]='h0`；b[27:8]→dout2 tc_en/line_fc_id/fc_id |

> 注：`ddr_resp_fifo` 只存 {data[511:352],data[319:8]}，[351:320] 与 [7:0] 读回恒 0；addr 不经 FIFO，`ddr_ft_info.addr<=d_rd_res.addr`。

## 5. 匹配与状态判定

`pkt_ft_match[5:0]`：b0 比 40b（dport+sport+pid）；b1~b4 比 sipL/sipH/dipL/dipH（sipH/dipH 允许 0 或 ipv6 取高 32）；b5 合并 vlan/trunk/safe_zone/ethid：
```systemverilog
pkt_ft_match[5] <= (模式款!=4'd4 || ~mark_drop) &&
                   (vlan 匹配 || pkt_ft_out[209]) &&
                   (pkt_ft_out[208] || safe_zone 关 || ethid 比较);
```
`session_state[4:0]` 在 `ddr_ft_info_d.vld` 更新：
- 全匹配（`==6'h3f`）→ `[4]=0`；`[3]=sample_pkt_hit`（采样使能 `s_rate_cfg[16]` 且 `~w_fwd_act[1]`）；`[2]=(FLAG[188:186]==100 且 ~w_fwd_act[4])` 路由模式；`[1]=~FLAG b189`（1=转发）；`[0]=0`。
- 超时 `pkt_timeout_info[0:3]` + 端口 down（`eth_link_up/up_ovc` 或 switch `link_status_switch`）→ `5'h11`。
- 不匹配 → `5'h1`（首包）。

## 6. 输出路由（dout0/dout2/dout3 各自场景）

| 场景 | dout0(CPU) | dout2(转发) | dout3(旁路) | 说明 |
|---|---|---|---|---|
| 首包（命中失败） | ✓ | ✗ | ✗ | state[0]，CPU 建会话 |
| 采样 | ✓ | ✗ | ✗ | state[3]，ch 打 3'b110 |
| 命中转发 | ✗ | ✓ | ✗ | state[1]=1 且 ~state[3] |
| 路由且 MAC 未命中 | ✓ | ✗ | ✗ | `state[2]&~macid_vld` |
| 命中即丢 | ✗ | ✗ | ✗ | state[1:0]=00，dout_ft_drop |
| 超时 | ✓ | ✗ | ✗ | state[0]=1，ch b22=timeout |
| ARP/免查/bypass | ✗ | ✗ | ✓ | etype_encode[2][2]=1，无 DDR 等待 |
| 线速限速(sl_rd_res.data) | 抑制 | 抑制 | — | dout_sl_drop 计数 |

- **dout0 ch**(72b)：`{哈希方向28b,port/ip_shift,rss,tracing(b23),b22:21={timeout,mac未命中}(sop拍),低码}`；CPU/未命中→3'h0，采样→3'h6；经 `sl_rd_res.data` 门控输出。
- **dout2 ch**(内部 236b，输出截低 205b `ch[204:0]`)：`{vlan_tag32b,rss4b,tracing1b,input_eth_id4b,macid+flag+ethid+natip+natport 176b,tc_en/is_down/per_ip_en+line_fc_id+fc_id 20b}`。sop 拍由 `ddr_ft_info` 拼装；`FLAG==0x18`（虚拟线）时 macid 区全 0、模式区写 8'h18。
- **dout3 ch**：`{hash_dir28b,port/ip_shift,rss,tracing,eth_id,etype}`(44b)。
- 软件门控 `w_fwd_act[0..3]`(FWD_ACT)，pps 计数 `dout_sop_inc[0:3]`=首包/采样/ft_drop/sl_drop → `i_dout0~3_sop`、`p0/p1_drop_cnt`。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
