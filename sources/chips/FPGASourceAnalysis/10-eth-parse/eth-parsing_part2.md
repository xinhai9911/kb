# eth 解析的哈希·调度·寄存器·复位·LED（part 2）

> 承接 [part 1](eth-parsing_part1.md)：解析相关六文件的哈希输入时序、4→1 调度、LBS 寄存器、PHY/MAC 复位、活动 LED。源路径统一记 `rtl/eth/xxx.sv` 或 `rtl/common/xxx.sv`。

## 1. 5 元组哈希：hash_32b_gen 输入时序

`hash_32b_gen`（`rtl/common/hash_32b_gen.sv`）为 64-bit 输入 CRC32（`crc[31:0]=1+x^1+x^2+...+x^32`，见文件头多项式）；寄存器 `c` 初值 0xFFFF_FFFF，`crc_en` 时 `c<=lfsr_c` 累进。解析器 `generate` 例化 2 个（i=0/1）：

| 连接 | 源码 |
|---|---|
| `.rst` | `eth_din.sop & eth_din.vld`——新包 SOP 到 `eth_din` 即清零累加器（先于喂数约 6~7 拍） |
| `.crc_en` | `hash_queue[i].vld`（5 个数据字的使能） |
| `.d` | `hash_queue[i].data`(64b) |
| `.crc_out` | `hash_o_pre[i]`(32b) |

`hash_queue`=`BUS#(64,0)::A[2:0]`（{vld,sop,eop,data}），`eth_dsop_d[6:2]` 单热窗一拍一字共 5 拍：

| dsop_d[6:2] | queue[0]（固定序） | queue[1]（方向归一） |
|---|---|---|
| 01 | `{1,1,0, dip[127-:64] & 64'hffff_ffff_0000_0000}` | `hash_direct ? dip高 : sip高` |
| 02 | `{1,1,0, dip[0 +:64]}`（IPv4 即 {0,ip32}） | `hash_direct ? dip低 : sip低` |
| 04 | `{1,1,0, sip[127-:64] & mask}` | `hash_direct ? sip高 : dip高` |
| 08 | `{1,1,0, sip[0 +:64]}` | `hash_direct ? sip低 : dip低` |
| 10 | `{1,1,0, {dport,sport,pid,24'h0}}` | `rss_port_en ?(顺/反排端口): 64'b0` |

要点：
- IPv4 的 sip/dip 存 `{96'h0,32b}`：高半掩 32 喂 0、真实 IP 走低 64b 字（哈希输入序列 = `{0,dip, 0,sip, 端口}`）；IPv6 高半掩断在 /32 前缀。
- `hash_direct = {dip[127-:32],dip[31:0]} > {sip[127-:32],sip[31:0]}`（IPv4 即 32b 数值比较）——使 queue[1]（ch 的 sip_hash）与流向无关。
- `rss_port_en`=0 时第 5 字恒 0，哈希退化为仅 IP 维。
- 采样：C8（`eth_din_d[8].sop`）取 `hash_available[6] ? crc_out[31-:28] : {4'b0,crc_out[29-:24]}`（非 IP fallback 低 24 位），填 ch[91:64](q1)/ch[63:36](q0)。`hash_available[0]` 恒 0、[1]=C2 判 IP、[6:2] 移位链对齐 C8。

## 2. pkt_parsing_sch —— 4→1 合并（无仲裁）

`rtl/eth/pkt_parsing_sch.sv`（56 行）：默 `N_NUM=4,DW=256,CHW=120`；top 实例 `CHW=125,BUSW=256+125+5+3=389`。**调用方：`top.sv` `PROC_GEN`，每通道 1 个（共 2）**——入 `pkt_parsing_sch_in[i*4 +:4]`（4 个解析器输出），出 `position_check_in[i]` → `position_check`。

| BUS 位 | 来源 | 逻辑 |
|---|---|---|
| [BUSW-1]/[-2]/[-3] | 各路 vld/sop/eop | `\|` 合并 |
| [BUSW-4:CHW]={left,data} | **恒取 din[0]** | 透传通道 0 数据 |
| [CHW-1:0]=ch | 各路 `bus_pkt_vld[i]` | **固定优先级 0>1>2>3**，首路有效者全程 |

特性：**非包级调度**（vld/sop/eop 全体 OR、ch 取首个有效且不轮转）；依赖上游同一时刻仅一路有包（`eth_rx_pkt_sch` 3→4 + 「SOP 间隔≥8 拍」）。`rst` 悬空未用；输出为 `BUS#` 打拍寄存。

## 3. pkt_parsing_mem_map —— 解析器 LBS 寄存器

`rtl/eth/pkt_parsing_mem_map.sv`（168 行），`BASE_ADDR=24'h8_5000+ETH_ID*24'h100`（每卡 4 例，槽 [1]~[4]），clk=clk_100m_in、rst=clk_100m_unlock；地址 `{mem_in.address[23:2],2'd0}` 译码，写单拍、读两级打拍。

| 偏移 | 寄存器 | R/W | 内容 |
|---|---|---|---|
| 0x00/04/08 | DIN0_SOP / DOUT0_SOP / DOUT1_SOP | RO | 入/出包计数（`dsp_macro_cnt`；DOUT1 恒 0） |
| 0x0c~0x2c | DMAC_H/L SMAC_H/L ETH_TYPE FRAG_TTL P_ID DIP_32B SIP_32B | RO | st_e_feild 快照（DMAC_H 高 16=`dmac_drop_cnt`） |
| 0x30/0x34 | DPORT / SPORT | RO | `{vlan_tag[31:16],dport}` / `{vlan_tag[15:0],sport}` |
| 0x38 | TCP_FLAG | RO | `{16'h0,l4_h_len,4'h0,tcp_flag}` |
| 0x3c | PKT_DB_INFO | RO | b0=less64、b2:1=vlan、b3=ttl≤1、b4=frag、b5=tcp_flag、b6=非TCP/UDP、b7=bcast、b8=crc、b9=jumbo/bypass、b10=bypass、[31:16]=len |
| 0x40~0x7c | DMAC_CFG_H/L0~7 | RW | 8×48-bit DMAC 白名单（`_H`=`wr_data[15:0]→[47:32]`） |
| 0x80 | DMAC_CHECK | RW | bit0 使能匹配（0 时解析器恒判 dmac 有效） |
| 0x90 | RSS_PORT_EN | RW | bit0 使能端口哈希分量 |
| 0xa0 | SEOP_CHECK | RO | 入/出 4×8b SOP-EOP 平衡计数 |
| 0xfc | BUS_CHECK | RW | 自检回环字 |

源清单**无** CRC/MIN/JUMBO/FC 统计与 BYPASS_EN——分属 `Ingress_chnl` 的 `eth_rx_pkts_crc/min/jumbo/fc` 与 `top_mem_map` 的 BYPASS_EN，勿混。

## 4. eth_reset —— 5MHz 计数式 PHY/MAC 复位

`rtl/eth/eth_reset.sv`（99 行），实例 `clk_rst_ctrl.sv` 每口 1 个：`.clk(clk_005m_in)`(5MHz)、`.rst(pll_unlock_pre[0]|eth_core_rst[i])`、`.gt_reset_out→eth_rst`、`.mac_reset_out→eth_mac_rst`、`.eth_status→eth_led_en`、`.lnkdwn_cnt→eth_lnkdwn_cnt`、`.clear_lnkdwn_cnt('d0)`。

- localparam：`CLK_FREQ=5_000_000`（1s 水印，cntr 23b）、`RST_PERIOD=50_000`（10ms GT 脉冲）、`CNT_MAX=500_000`（100ms MAC 释放延时，time_cnt 19b）。
- `eth_status = stat_rx_status & stat_rx_block_lock & ~bad_code & ~local_fault & ~remote_fault`，3 级 `(*async_reg*)` 同步（_r1..r3）。
- `eth_reset_status`（**内部信号，非输入**）= `~stat_rx_block_lock | stat_rx_local_fault`。`cntr` 计到 1s 水印；到水印且链路坏则归零重计，好则保持。
- `gt_reset_out=(cntr<RST_PERIOD)`：上电/自动复位即 10ms GT；此后每 1s 水印若链路仍坏再触发一轮（周而复始）。
- MAC：`time_cnt` 于 `~gt_reset_out` 计向 CNT_MAX；`mac_reset_pre`=复位期间 1，或 `time_cnt∈[CNT_MAX-16,CNT_MAX)` 再高 16 拍后释放 0。即「10ms GT →100ms 后再脉冲 16 拍 → MAC 释放」。
- `lnkdwn_cnt`(32b) 在 `eth_status_r3 & ~eth_status_r2`（同步后链路下降沿）计数，`clear_lnkdwn_cnt` 清零（top 接 'd0，软件清零通道未引出，**待核实**）。

## 5. data_led —— 活动/链路状态 LED

`rtl/eth/data_led.sv`（53 行）：`clk=eth_tx_clk[i]`、`clk_led=clk_005m_in`、`ena=eth_led_en[i]`(=eth_status)、`data_1=axis_tx.vld&rdy`、`data_2=axis_rx.vld`、`led_out=led&ena`。top：`eth_led[i]=led_out[i] && ~stat_rx_remote_fault[i]`（仅 i<2 与 i≥4 分支；i∈[2,4) 置 0）。

- `data_vld = data_1|data_2|data_1_d[3]|data_2_d[3]|data_1_d[7]|data_2_d[7]`——eth 域 8 级移位拉伸活动脉冲，再跨入 clk_led 域（LED 容忍亚稳态，未做正规 CDC）。
- clk_led 域：`count` 每 `CLK_HZ/LIGHT_FREQ-1=2.5M`（0.5s）回绕；`led = count>=CLK_HZ/(LIGHT_FREQ*2)=1.25M`。行为：data_vld=1→**2Hz 闪烁**（0.25s 亮/0.25s 灭，LIGHT_FREQ=2）；data_vld=0→count 继续计到 max-1 后停住→**常亮**；`ena=0`（链路断）→**熄灭**，与头注释一致。

## 6. 疑点 / 待核实

- v2（2026-06-25）编译通过但**全工程无例化**（top.sv 8 口全用 v1）——确认计划切换或删除。
- check_en 综述标注 Telnet/FTP/IMAP vs 源码 sport 23/21/143/110（FTP-Ctl/FTP-Data/SIP/POP3）：协议名待核实。
- `clear_lnkdwn_cnt` 接 'd0，lnkdwn_cnt 无软件清零通道（可能经 eth_sta local 端，未追）。
- `eth_reset` MAC 段 100ms 前 16 拍重新拉高的用意，源码无注释。
- 哈希 28b 截取（IPv4 第 1/3 字恒 0）的键范围需与 `session_t_sch` 键一致——见 `06-lookup-config/session-table.md`。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)。