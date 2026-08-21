# 出入口补深：Eth_bypass / add / ckes_calc + Ingress_chnl / Egress_chnl 未展开细节

> 补综述 §4.10：交叉旁路接线、校验和原语、两通道模块内部细节。源路径 rtl/i_e_gress/；顶层接线 rtl/top.sv。

## 1. Eth_bypass — 端口级交叉旁路（回环自测原语）

按奇偶交叉把相邻端口收包直通到邻口发送：**偶数 i 的 `Eth_rx_gress[i]` 洗入 `Eth_tx_gress[i+1]`，奇数 i 的洗入 `Eth_tx_gress[i-1]`**（等价 `i^3'b001` 配对：0↔1、2↔3…），同时本口数据面收侧 `Eth_rx_user[i]` 在与旁路使能时被清零（不重复进数据面）。

| 信号 | 位宽 | 说明 |
|---|---|---|
| loop_en | 1b | 回环总开关（使能条件见下） |
| Eth_rx_user[ETH_NUM-1:0] | BUS#(256,0)::B | 本口数据面收总线（给 Ingress 之后） |
| Eth_tx_user[ETH_NUM-1:0] | BUS#(256,0)::B | 本口数据面发总线（给 Egress 数据面路径） |
| Eth_rx_gress[ETH_NUM-1:0] | BUS#(256,0)::B | MAC 核侧收（旁路源） |
| Eth_tx_gress[ETH_NUM-1:0] | BUS#(256,0)::B | MAC 核侧发（旁路目标） |

- **使能条件**（每口独立 `bypass_mode[i]`）：`~Eth_tx_user[相邻口].vld && ~Eth_rx_gress[i].vld`（邻口数据面无收发占用）时拍锁 `loop_en`；否则维持原值。空闲才允许旁路，避免与正常流量打架。
- 旁路模式下 `Eth_tx_gress` 选相邻口收流、本口 `Eth_rx_user[i].sop/eop/vld` 清零；非旁路恢复直通。left/data 恒直通本口（注意 `Eth_rx_user[i].left/data` 始终跟随 `Eth_rx_gress[i]`）。
- **接线事实**：本模块在 rtl/ 无实例化（遗留）。现网的交叉旁路在 top.sv `ETH_CH_GEN` 里直接实现——`Egress_chnl` 的 `eth_rx_bypass` 接 `eth_rx_bypass[i^3'b001]`（i=0..7，含 40G×2+10G×4），旁路使能即 Ingress_chnl 的 `bypass_en = r_bypass_en[0/1][0]`；`r_bypass_en[ch]` 其余位是功能级旁路（如 [5]=session 查表、[8]=ckes_bps、[12]=crs_crd、[14]=mtu bypass）。位置注意：10G 口 i=4..7 接 `axis_eth_10g_rx[i-4]`，40G 口 i=0..1 接 `axis_eth_40g_rx[i]`。

## 2. add — 16→1 全宽加法树原语

16 个 32-bit 字求和归一到 32-bit 的四级二元加法树，使用 Xilinx `ADD_3232_32` 原语（DSP48 加法），`din_vld` 打 4 拍对齐 `dout_vld`（每级一拍）。

| 级 | 加法器数 | 输入 |
|---|---|---|
| st0 | 8 | `din[(2i)*32+:32]`、`din[(2i+1)*32+:32]` |
| st1/~st3 | 4/2/1 | 逐级对折 |

- 输出 `dout[31:0]`（自然进位，不折叠）。消费方仅 ckes_calc（USE_DSP 分支）——把 16 路 DSP 乘积高位 P 的 32b 段求和。
- 注意与 `port_group/port_group.sv` 内同名 `function add()`（16b 位）无关。

## 3. ckes_calc — 校验和累加原语（反码和）

对 256-bit 流按「每 16b 字 × ch 掩码」逐拍累加，eop 拍收尾折叠取反，输出 16-bit Internet checksum。参数 `DSP_EN` 选两条实现，均先清后累。

- 输入 `BUS#(256,16)::D din`：`din.ch[15:0]` 为逐字 keep（`ch[i]==1` 该 16b 字参与累加）；`extend_in[15:0]` 为追加的伪首部字（TCP/UDP pseudo-header + len），在 eop 拍并入。
- **DSP_EN=0（NO_DSP）**：4 路 32-bit `tmp_ckes0..3` 独立累加（每路吃 64b×4 keep），`CKES_CALC0()` 逐 16b 字按 keep 求和；eop 后一拍 `tmp_ckes = c0+c1+c2+c3`，再一拍 `CKES_CALC1(tmp_ckes+extend_in)`（`d[31:16]+d[15:0]` 两次折叠后取反）→ `ckes_out[15:0]`，`ckes_out_vld` 与 eop_ff2 对齐。流水 3 拍。
- **DSP_EN=1（USE_DSP，tcp_ckes_filter/ipv4_ckes_filter 实参）**：`C_W=16` 路 `DSP_A16_M_B16_A_P32`——A=`{1'b0,data[16b]}`(17b 信号), B=`{15'b0,ch[i]&vld}`，P 48b，`SCLR=eop_ff1|rst` 置 0；eop 拍锁存 `extend_in_lat`；16 路 32b `add_din`（lane0 加 extend_in_lat）经 `add` 树汇成 32b `sum`，`sum_vld` 后 `CKES_ADD()` 折叠取反输出。流水=1(eop 采样)+4(add 树)。
- 位宽/级数小结：DSP lane A 17b×B 16b、P 48b（取低 32）、加法树 4 级、最终 16b。
- TODO 注释（2023/5/17）：`extend_in` 与 eop 存在组合时序风险，需同步/取 `extend_in_lat`——现行 NO_DSP 分支 eop_ff2 时并行 `tmp_ckes+extend_in` 组合加，是已知软点。
- 实例化者：`ipv4_ckes_filter`（extend_in=0）、`tcp_ckes_filter`（extend_in=伪首部）；`ckes_in.ch` 由各自 `flag()` 函数按偏移/长度置 keep。

## 4. Ingress_chnl — 收侧细节（补 doc 未展开）

参数：`ETA_ID[3:0]`、`VLAN_ID`、`DW`（40G 口 256 / 10G 口 64）、`BUSW=DW+DW/8+3`（256b 口 291、64b 口 75）、`INGRESS_PKT_GAP = DW==64 ? 7 : 1`，**sop 延迟 = GAP+1**（64b 口 8 拍、256b 口 2 拍）。

- MAC 侧 `axi_eth_rx[BUSW-1:0]` 打包 `{vld,last,keep[DW/8],data[DW],user}`；DW==64 时数据左扩 `{192'h0,...}` 归一 256b。
- 双时钟结构：coreclk 采样 → `Core_rx_side`（归一化）→ `ing` 整包门控（首拍 user 后不得断流，`eth_rx_pfull` 反压；被拒包计 `eth_rx_pkts_fc`）→ `ETH_CDC_AXIS_FIFO`（独立时钟 512×256b）→ sysclk 侧 FSM `IDLE/RD` 读出（`dly_cnt` 到 GAP-1 才起读，`eth_rx_rdy` 同时受 `eth_rx_info_rdv` 门控）。包属性 3b `{unp? idx0=crc, idx1=min, idx2=jumbo}` 走 `XPM_PTKSINFO_ASYNC_FIFO`（512×3b）。
- `rx_enable` 4 级移位错拍（`rx_enable_d[3]`），在包首拍采样门控整包使能。
- 输出 `eth_rx = {eth_rx_ff2, ETH_ID[3:0]}` → `ch[5:0]`：**b5=jumbo、b4=crc、b3:0=eth_id**（与 eth_ul_pkt_parsing_v2 的 din.ch 注释一致）；正常流过滤 `~unp & ~bypass_mode & ~jumbo`（min 包弃、bypass/jumbo 走旁路流）。
- bypass 流 `eth_rx_bypass`：`(bypass_mode | jumbo)` 包；VLAN_ID=1 时 sop 且 Ethertype=S0x8100 做 **VLAN 改写**（`{vlan_id[15:1], ~vlan_id[0]}` 翻转最低位，适配旁路环回后 VLAN 感知），其余直通 `byte_seq()` 大端化。
- 统计：`eth_rx_pkts/byts` 63-bit（bit63 恒 0、高半字进位扩展）、`pkts_crc/min/jumbo`、`pkts_fc`；`ingress_out_vld_flag[19:0]` 调试位（长度 >47、非 sop 起包、sop+eop 单拍等异常）。

## 5. Egress_chnl — 收侧细节（补 doc 未展开）

- 双 FIFO 合并：`bypass_tx_fifo`（PACKET_FIFO=false，`bypass_wen_enable` 在 bypass sop 起按 pfull 决定整包是否写，被拒计 `eth_tx_pkts_fc`）+ `ETH_CDC_AXIS_FIFO_eth_tx`（普通数据流，`eth_tx_rdy=~normal_fifo_pfull`）。读侧 FSM `IDLE→RD_BYPSSS/RD_NORMAL`，**bypass 优先**，单帧完成才回 IDLE；`final_tx_*` 逐拍 mux 二选一。
- DW==256 口：1024×256b `independent_clock` FIFO 直驱 MAC（coreclk 侧拆回 BUSW 线），写侧 `byte_seq()` 还原 MAC 字节序、`left2keep()` 重建 keep。DW==64 口：512×256b `common_clock` FIFO → `Core_tx_side`（256→64 下变换 + keep 展开 + tpfull 门控）。
- 统计：`eth_tx_pkts/byts` 受 `eth_link_up & final_tx_vld&eop` 门控（64b 口字节数 +4 含 FCS）；`eth_tx_boardcast_cnt` = sop 且 DMAC 全 1 或 ethertype==0x0806；`eth_tx_core_cnt[4:0][7:0]` 在 coreclk 逐脉冲累加 MAC 的 stat_tx_total/good_packets/frame_error/packet_small/large 五个事件。
- 注意：**`bypass_en` 形参在模块体内未使用**——旁路完全由外部 `eth_rx_bypass[i^3'b001]` 接线决定（top.sv 中已论）。

## 6. 事实核对与坑

- 现网交叉旁路的「使能」在 Ingress 侧 `bypass_en`（top `r_bypass_en[ch][0]`），Egress 只做流合并；Eth_bypass 模块本身是同期封装、未实例化。
- `ckes_calc` 两条实现均有周期级流水差异（3 vs 1+4），替换 DSP_EN 需重验收拍对齐。
- Ingress ch[5:0] 的 b4=b=jumbo、b5=crc 顺序（即 bit5=C2=jumbo、bit4=C0=crc）与 eth_ul_pkt_parsing_v2 注释逐位一致，别与 8b etype 位序混淆。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)