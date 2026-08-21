# 转发流水线补深：slp_decode / Forward_shunt / Forward_lbs / Dma_Ses_mux / ch_trf / Axis2Avls / 封装底座

> 补综述 §4.2 未覆盖的 forward/ 模块；ch 布局见 [[03-dataplane/ch-protocol|ch 协议章]]。源路径 rtl/forward/。

## 1. slp_decode — 协议偏移译码（非 SRAM 链路表）

名字易误判为链路表读侧；**实为逐包头译码**：识别 VLAN 层数/IPv4/IPv6/UDP/TCP，输出 `Eth_tx_type_out[23:0]` = `{type(8b), l3_offset(8b), l4_offset(8b)}`，供 Replace_port/ch_trf 定位改写偏移。

| 字段 | 位宽 | 说明 |
|---|---|---|
| type[23:16] | 8b | 0=none 1=ipv4 2=ipv6 3=ipv4+udp 4=ipv4+tcp 5=ipv6+udp 6=ipv6+tcp |
| l3_offset[15:8] | 8b | IP 头起始字节（无 VLAN=14，1 层=18，2 层=22） |
| l4_offset[7:0] | 8b | UDP/TCP 头；IPv4=`{2'b0,data[255-14*8-4 -:4],2'b0}+l3_offset`（IHL×4），IPv6=`l3_offset+40` |

- 数据/left/user/tlast 四级打拍直通（in→d1→d2=u→out_u→out_d1→out_d2），**5 拍延迟**，无 ready 反压。
- 译码仅 `cnt==0` 首拍执行；cnt 随包计数（上限 0xf，tlast 归零）。Ethertype 位 offset 12；VLAN 层在 offset 12/16/20；协议号 IPv4 在 offset 23（+1VLAN 27、+2VLAN 31）、IPv6 在 20（+VLAN 24/28）。
- 实例：Forward_top（Replace_ip 后、Replace_port 前）。

## 2. Forward_shunt — 转发分流：ovb 旁路 + sid 三通道

出口决策器：读 `ch`，出界/跨卡（ovb）包导 `dout_ovb`，其余按 `eth_outid_globel` 匹配 local/ovc sid 分 `dout[0..2]`；兼做包追踪命中计数。参数 `CARD_ID`。

| 端口 | 位宽 | 说明 |
|---|---|---|
| din | BUS#(256,97)::C | ch[96]=ipv4_ckes_err（ipv4_ckes_filter 追加）；ch[95:0] 见 ch 章 |
| dout_ovb | BUS#(256,44)::C | 43b ch 重构：port_shift+ip_shift(8b×2)+mod_field(16b)+etype(8b)+eth_id(4b) |
| dout[2:0] | BUS#(256,96)::C | 三路出口流（ch 同宽透传） |

- ovb 使能：`ch[59:56]==4'b1`（ovb 子域 ovb_flag）或 `ch[0]==1`（tracing）→ 走 dout_ovb。
- sid 匹配键 = `ch[95-80 -:8]` = **ch[15:8] eth_outid_globel**：CARD_ID==0 时 `dout[0]`⇔local_sid、`dout[1]`⇔ovc_sid、`dout[2]`⇔ovc_sid+1；CARD_ID≠0 时 ⇔local_sid+1 / ovc_sid+2 / ovc_sid+3。
- 进 dout 门控：`ch[59:56]==0`（非 ovb）且 `ch[0]==0`（非 tracing）且 sid 命中；**一包只进一条通道**。
- 统计：`dout_ovb_cnt`（ovb eop）、`dout_ovb_lat`（ovb vld 采样 ch[31:0]）。
- `pkt_tracing_detection`×2（N_NUM=1,DW=16）：db[31:16]=ovb 命中（ch[59:56]==1 eop）、db[15:0]=非 ovb；pkt_hit=ch[0]。
- 实例：Forward_top（ipv4_ckes_filter 后、Dma_Ses_mux 前）。

## 3. Forward_lbs — 转发寄存器/统计/MTU 配置堆

LBS 从站：聚合 50+ 统计/状态字、邻接表读回、MTU 配置。参数 `FORWARD_BADDR`（模块默认 12'h1，**top.sv 实例化时覆写为 12'h084**→地址页 [23:12]=0x084、基址 0x084_000，top_mem_map 槽 8）、`ETH_NUM`、`VLAN_ID`。

| 内部偏移 | 内容 |
|---|---|
| 0x100~0x198 | Route_mux/Replace_ip/Replace_mac/Tcp_*/Forward_shunt 计数与状态 |
| 0x200~0x218 | 邻接读回：写 ADDR_ADJ_RADDR 触发 `Adj_rden+raddr[12:0]`，回读 97b 项拆 `{有效位,32/32/32}`（ADJ_VAL/VLD0/1/2） |
| 0x230~0x27c | ovb 计数、exchange 出口、字节数高/低字（64b） |
| 0x280~0x28c | 功能级 flag 计数（route/mac/tcp_ckes_in/out） |
| 0x290~0x2ac | MTU：BYPASS（上电 1=旁路）、ICNT/OCNT/UNP_CNT、MTU_NUM0~3 |
| 0x300~0x314 | crs_crd/up_numa 调试 ×6 |
| 0x320~0x328 | MTU RAM 端口（VLAN_ID 分支） |

- 读路径：rd_req 一拍出 `tmp_rd`，`tmp_rdv` 对齐后注册出 `local_out`；非本 BASE rd_req 回 0。
- MTU 阈值写钳位 `[128,1600]`，默认 1500。
- `VLAN_ID=1` 时 generate `tdp_ram`（distributed、6b×16b、read_first）：上电 `mut_cfg_init` 自动灌 64 项 1500 初值；B 口挂 sys_clk 供 mtu 流式查 `mtu_num_sw`。VLAN_ID=0 不生成。
- 实例：Forward_top；`mtu_bypass/mtu_num` 接 mtu 模块。

## 4. Dma_Ses_mux — DMA/SES 出口复用

每出口收尾级：DMA 流（AXI-S、dma_clk 域）与转发/SES 流（clk 域）复合成单路 256-bit Eth。Forward_top generate 3 路（i=0..2），i=3 恒置 `tpfull=0、tready=1`。

| 端口 | 位宽 | 说明 |
|---|---|---|
| DMAc_tx_* | 256b AXI-S | keep 有效掩码；whole 包缓存 |
| SESc_tx_* | valid/data/left/tuser/tlast | 来自 dout_eth[i]（tuser=sop、tlast=eop） |
| Eth_tx_* | 256b+left+user+last | 至 dout[i]，ready=dout_rdy[i] |

- 写侧：SESc 两拍对齐后经 `SESCing` 门控入 `SESC_AXIS_FIFO`（common_clock，512×256b，tuser=`{ruser,rleft}`，PF 512-50）；DMA 侧 `DMAC_AXIS_FIFO`（independent_clock，512×256b，PF 512-70，PACKET_FIFO）。
- 仲裁：1bit FSM `IDLE/PKTS_FORWARD`+`cyc`；两 FIFO 同有包时 `DMAC_rcount<=SESC_rcount+128` 判先后（留余量）；rready 只拉选中通道（不撕裂整包）。
- 数据改造：DMA 路 `change_byte_seq()` 低位字节序→256b 大端，`left=keep2left(keep)`；SES 路直通。
- 统计：`in_bcnt`（64b，非尾 +32B/尾拍 `left+4` 含 FCS）、`*_incnt`（eop）、`sesc_fccnt`（tpfull 拒绝）、`outcnt`；state=`{31'b0,c_state}`。pkt_tracing_db 恒 0。

## 5. ch_trf — wire→BUS-C 及 ch 护照主装配

把 Replace_port 的 wire 握手转成 `BUS#(256,96)::C` 并按 type 组 ch[95:0]——**Forward_shunt 之前唯一的 ch 构造点**。

- 输出 ch：`res(16b) ovb(40b) port_shift(8b) ip_shift(8b) pid(8b) eth_outid_globel(8b)(user[167:160]) etype(4b) res(3b) tracing(1b)(user[2])`；`ip_shift=l3_offset+12`(ipv4)/`+8`(ipv6)；pid=17/6/0。
- `ovb={16'b0, rss(user[187:184]), {3'b0,over_bord(user[159])}, {user[164:160],3'b0}, 4'b0,4'b0}`。
- 输入 user 位域：`[187:184]rss [183:168]macid_ext [167:160]eth_outid_globel [159]over_bord [158:143]port+[142]port_flag+[141:134]macid+[133:6]ip+[5:4]nat(00无/01snat/10dnat) [2]tracing [1:0]mode(00虚拟 01路由 10交换 11dma)`。
- 时序：`dout_u→dout_d1→dout_d2` 两拍；`din_sop` 由 tlast 复位标志拍对齐。
- 实例：Forward_top（Replace_port 与 tcp_ckes_filter 之间）。

## 6. Axis2Avls — AXI-Stream→Avalon 适配（遗留原语）

```systemverilog
assign Avls.sop = 0;                    // 无 sop 输出
// vld/eop 各一拍注册；left<=keep2left(Axis.keep)
// data<=change_byte_seq(Axis.data)；ch<=Axis.user(2b)
```

无 ready 反压（吞掉 tready），下游需自推包边界。与 Ingress_chnl/Core_rx_side 内 AXI→用户总线变换同套路。**RTL 未实例化**（仅工程编译），活跃路径在 Ingress_chnl/Route_mux 内部适配。

## 7. Eth_package.sv / Message_package.sv — 封装底座（验证/遗留）

- `Eth_package.sv` **是 package+class `Eth_frame_tx` 而非模块**（激励库）：枚举 `Eth_vlan_t(VLAN0/1/2)`、`Eth_L2_t(L2_DAT/IPV4/IPV6/ARP)`、`Eth_L3_t(L3_DAT/TCP)`；`eth_dat_gen()` 逐字节拼 MAC 头（14/18/22B，QinQ 双 0x8100）+IPv4/IPv6+TCP，按 16b 反码和算 IPv4/TCP 校验和回写，帧体 `$urandom` 并逐字节 `$display`。纯验证，RTL 不实例化（对应 sim 库 `Eth_pkg/Eth_frame_gen`）。
- `Message_package.sv` **旧版整链 wrapper**：`Tcp_decode→Replace_port→Tcp_ckes_calc→Tcp_ckes_replace→Forward_shunt`（旧接口），输出 `Eth_tx_valid_out[ETH_NUM-1:0]` 数组+`*_ovb`，聚合 14 个统计口。
  - **接口漂移坑**：内部 `Forward_shunt #(.ETH_NUM(ETH_NUM))` 与现版 CARD_ID 签名不匹配，Forward_top 不使用；其价值为保留前 4 段等效接线模板。

## 8. 事实核对与坑

- `Forward_shunt` 新旧两版同名：现版 CARD_ID（Forward_top 用）；旧版 ETH_NUM 仅 Message_package 引用（遗留，不可综合对接）。
- `Axis2Avls`/`Eth_package`/`Message_package` 均不入当前数据面但随工程编译，勿当作活跃路径。
- Forward_lbs 的 Tcp_decode_*/Tcp_ckes_* 统计口在 Forward_top 被置 `'d0`，读回恒零属预期。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)