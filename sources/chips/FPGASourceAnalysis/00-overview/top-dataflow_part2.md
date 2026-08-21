# top.sv 深度解剖（part 2：数据面级联 / mem_out 槽位 / 控制面）

> 承接 part 1。行号均指 `rtl/top.sv`。TLV/DDR/NUMA/bypass 见 part 3。综述的数据流图只到模块名，这里补到**总线位宽与跨通道切片**。

## 1. 数据面流水级联（每通道 PROC_GEN，括号内=总线类型）

| 级 | 模块（实例） | 输入→输出 | 备注 |
|---|---|---|---|
| 入口 | `Ingress_chnl`（×活跃口，40G DW=256/10G DW=64） | MAC `AXI#(256或64,1)::S` → `eth_rx BUS#(256,6)::C` + `eth_rx_bypass BUS#(256,0)::B` | bypass 流供 Egress 交叉口（`i^3'b001` 配对） |
| 调度 | `eth_rx_pkt_sch`（AFULL=64） | 3 口（`{eth_rx[i*2+5:i*2+4],eth_rx[i]}`）→ `eth_rx_sch_in[i*4+:4]` 4 路 | 口 2/3 无入口流 |
| 解析 | `eth_ul_pkt_parsing` ×8（DW=256,CHW=0） | `eth_rx_sch_in[i]` → `pkt_parsing_sch_in[i] BUS#(256,125)::C` | 125b ch 含协议摘要/五元组哈希 |
| 合并 | `pkt_parsing_sch`（N=4） | 4→1 → `position_check_in[i]` | |
| 校验 | `position_check`（bypass=`r_bypass_en[i][14]`） | → `ul_sta_in BUS#(256,96)::C` + `position_check_match BUS#(256,48)::C` | CRC16 协议识别；匹配包上报 DMA |
| 统计 | `eth_sta`（UNKNOW=GOLDEN?1:0） | → `session_t_sch_in BUS#(256,96)::C` + `pkt_unkown_sch_in[i*4+:4]` | ckes_bps=`r_bypass_en[i][8]` |
| 会话 | `session_t_sch`（bypass=`r_bypass_en[i][5]\|r_table_clear[i][0]`） | dout0→`b_list_in[i*2]`、dout2→`route_sel_in[i]`(185b)+`route_sel_dummy`、dout3→`b_list_in[i*2+1]`；写侧 `ddr_wr_sch_in[i*2+1]`；读侧 `rd_req_sch_in[i*4]` | DDR 查表 |
| 黑名单 | `blacklist_proc`（bypass 硬置 1） | → `b_list_out0/1[i] BUS#(256,48)::C` | 实际走 DDR 哈希；TCAM 走 axi_tcam 为死路径 |
| 上行 mux | `ul_dma_sch_mux1`（N=4） | `ul_dma_sch_in[i*5+:4]`（b_list_out1/unkown/Eth_tx_ovb/position_check_match）→ `axis_rxq_in[i]` | 四类候选合成 DMA 上行流 |
| DMA 分发 | `axis_rxq_demux`（bypass=`r_bypass_en[i][10]`） | 1→4 → `ul_dma_in[i*4+:4] AXI#(256,20)::S` | 每口一个上行队列 |
| 跨卡 UL | `up_numa`（全卡 1 个，bypass=`{r[1][13],r[0][13]}`） | `{ul_dma_in[4],ul_dma_in[0]}` → `up_ul_dma_in[1:0]` | 端口 4、0 硬连线汇聚 |
| 满旁路 | `dma_full_bypass`（每通道） | `up_ul_dma_in→dma_bypass_axi`；DL `dma_dn_axi→dma_dout`（回环 mux） | `dma_afull&en` 时上行直接回下游出口 |
| 收侧 | `design_bd_wrapper`（每通道 `DMA_GEN`） | `s_rx_axis`（=dma_bypass_axi）上游 / `m_axis`（=dma_dn_axi）下发 / `cfg_axis` 出 / `reg_axi_0/1/2` 寄存器口 | PCIe XDMA BD 拓扑 |
| 路由 | `crs_crd`（bypass=`r_bypass_en[i][12]`） | `route_sel_in[i]` → `SESc_tx BUS#(256,181)::C` + `ovbc_tx`（对卡） | local_sid/ovc_sid 双卡选路 |
| 缓冲 | `crs_crd_numa`（全卡 1 个）→`ram_share` | `numa_din[2]→axi_in[2]→axi_out[2][4]`（RAM_D=2048） | 跨卡共享包缓存；`axi_out[i][0..3]`→`DMA_axis[i*4+0..3]` |
| 哈希 | `sdip_hash_gen`（bypass=~VLAN_ID=1'b1） | `pkti_axi`（自 dma_full_bypass）→ `numa_din` | RSS/五元组哈希；结果回 top_mem_map（hash_gen_sip/dip/result/port/d） |
| 转发 | `Forward_top`（FORWARD_BADDR=12'h084） | `SESc_tx/ovbc/DMA_axis` → `eth_tx_user`（256b 无 ch）+ `Eth_tx_ovb BUS#(256,44)` | 替换 MAC/IP/端口、checksum；`{eth_tx_user[i*2+4+:2],eth_tx_user[i]}` |
| 出口 | `Egress_chnl` | `eth_tx_user[i]` → MAC `AXI` | `eth_link_up` 门控 |

DMA_axis 两卡映射：`axi_out_pfull[0][0..3]=DMA_axis_tpfull[0..3]`、`DMA_axis[0..3]=axi_out[0][0..3]`（top.sv:483-506）；KU060 下第二卡 `DMA_axis[4..7]` 同理取 `axi_out[1][0..3]`。

## 2. mem_out[槽位] × LBS 地址全表（每通道 16 槽）

| 槽 | 驱动模块（顶层连线） | LBS 基址（顶层可见） | 备注 |
|---|---|---|---|
| [0] | `top_mem_map` | `BASE_ADDR=24'h8_0000` | 每卡寄存器文件（主译码） |
| [1]..[4] | `eth_ul_pkt_parsing`（4 口各一） | 顶层不可见 | 槽=`i%4+1`；解析/位置检测寄存器 |
| [5] | `eth_sta` | 顶层不可见 | 端口统计 |
| [6] | `session_t_sch` | 顶层不可见 | 会话表寄存器（综述记 0x08_0000 疑与 [0] 混同） |
| [7] | `blacklist_proc` | 顶层不可见（综述记 0x08_9000 TCAM） | 黑名单/TCAM 配置 |
| [8] | `Forward_top` | `FORWARD_BADDR=12'h084`（12b 裁断偏移） | 转发/NAT 表 |
| [9] | `update`（mst） | `24'h08_3000` | SPI 主（升级主闪存） |
| [10] | `update`（slv） | `24'h08_3800` | SPI 从 |
| [11] | `axis_rxq_demux` | 顶层不可见 | DMA 队列/RXQ 寄存器 |
| [12] | SIM 模式固定 'h0 | 规划 `qos_block 24'h8_8000`（已注释） | 真实构建下无驱动（见坑） |
| [13] | generate 内固定 'h0 | 规划 `pkt_tracing_mem_map 24'h8_f000`（已注释，top.sv:949-959） | |
| [14] | 仅 SIM 分支清 'h0 | 顶层不可见 | 真实构建下无驱动（见坑） |
| [15] | 全局 `mem_out[0][15]='h0`（仅卡 0，top.sv:1689） | — | 卡 1[15] 仅 SIM 分支清 |

读回机制：`reg_axi_rdata[i] = mem_out[i][0..15].rd_data` 逐槽**逻辑或**（top.sv:555-571）；`reg_axi_arready[i] = &mem_spi_rdy`（两片 update 都就绪才应答，top.sv:554）。

## 3. 控制面挂接（regbus 链）

```
design_bd_wrapper（每通道，Xilinx BD）
  ├─ reg_axi_0（主寄存器 AXI-Lite）
  │     └─ reg_axi_b（AXI-Lite 写桥 + axi_eth 扇出，reg_axi_b.sv；CHNL_ETH_NUM=4）
  │           ├─ mem_in[i]（MEM#(32)::IN，address=$wvalid?awaddr[23:0]:araddr[23:0]）→ 各 *_mem_map（槽位表）
  │           └─ axi_eth_aw*/w*/ar*/r* → eth_sta → 4 个 MAC 的 s_axi 寄存器口
  ├─ reg_axi_1（TCAM）→ axi_tcam[i] → blacklist_proc.axi_tcam（死路径）
  └─ reg_axi_2（BCAM）→ axi_bcam[i] → axi_cam_slave（仿 CAM，axi_bcam.rdata[31:8]='h0）
```

`top_mem_map` 出：`r_bypass_en/r_table_clear/r_st_timeout/r_user_rst/eth_core_rst/core_rx_enable/dma_chnl_num[3:0]/port_cfg/port_cfg_rd/eth_pkt_ctrl/link_status_switch/r_eth_port_map/pcie_channel_id_en`（`pcie_channel_id_in` 接对卡 `pcie_channel_id[1-i]`）；入：`w_card_status/xadc_temp/hash_gen_{sip,dip,result,port,d}/ddr_rd_db[3:0]/ddr_cfg_cnt[6:0]/position_check_cnt/dma_full_bypass_{en,cnt}/local_sid`。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)。