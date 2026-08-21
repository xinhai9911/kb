---
aliases: ["ips-test-2025-fpga", "ips_test_2025_add_mpls_6que", "NSFOCUS FPGA 网卡"]
title: NSFOCUS FPGA 智能网卡 RTL 工程分析（ips_test_2025）
tags: [reference, sources, chip, fpga, xilinx, smartnic, nic, mpls, verilog, systemverilog, active]
created: 2026-08-20
updated: 2026-08-21
summary: >-
    NSFOCUS FPGA 智能网卡（SmartNIC）RTL 工程 ips_test_2025_add_mpls_6que 源码分析：Xilinx KU060/UltraScale+ 平台、2×40G + 4×10G 以太网、2×PCIe Gen3 x8、DDR4 会话表、MPLS + 6 队列 QoS、NAT/虚拟线/交换/路由转发流水线、29 个仿真用例与 Vivado/Questa 构建体系。
category: reference
source_dir: Q:\AI\ips_test_2025_fpga.zip
sources:
  - Q:/AI/ips_test_2025_fpga.zip
base_confidence: 0.8
lifecycle: reviewed
---

# NSFOCUS FPGA 智能网卡 RTL 工程分析

> 原始输入为压缩包 `Q:\AI\ips_test_2025_fpga.zip`（内含 `ips_test_2025_add_mpls_6que/`）。这是**源码级工程分析**，非资料蒸馏；目标是从 RTL 提取可复用的架构知识点，为 SmartNIC / FPGA 网络数据面设计提供参考。

## 1. 工程定位

| 项 | 值 |
|---|---|
| 名称 | ips_test_2025_add_mpls_6que（MPLS + 6 流量队列） |
| 厂商 | NSFOCUS（绿盟） |
| 器件 | Xilinx xcku060-ffva1156-2-e（Kintex UltraScale+；ver_define 为 `NSFOCUS_KU060`，兼容 KU040/KU15P/VU13P） |
| 工具链 | Vivado 2022.1 + QuestaSim（export_simulation） |
| 工程名 | ec_8x10_nf_v1 |
| 版本 | DEF_NIC_REV `01_02_06_04`，DEF_NIC_VER `03_0D_0014`，DATE `2026_0605`，TIME `0011_0326` |
| 作者 | luoanchen |

### 1.1 硬件特性（来自 CLAUDE.md）
- 2× **PCIe Gen3 x8**（`PCIE_DUAL`，双卡/双通道 NUMA）
- 2× **40G QSFP**（`l_ethernet`）+ 4× **10G SFP+**（`xxv_ethernet`），合计 8 个以太网口
- 2× **DDR4 SODIMM**（128-bit `ddr4_0_dns` 用于会话表；16-bit `ddr4_1_dns` 已注释禁用）
- **MPLS** 转发、流/会话表（哈希 + DDR）、QoS 6 队列、RSS 哈希、NAT（SNAT/DNAT/NNAT）、流量采样

## 2. 目录结构

```
ips_test_2025_add_mpls_6que/
├── rtl/                    # RTL 源码（.sv/.v）
│   ├── top.sv              # 顶层（2385 行，CHNL_NUM 通道 generate 复用）
│   ├── def/                # ver_define.svh、user_bus_def.sv、pci_bus_def.sv
│   ├── common/             # 总线调度、FIFO、DDR、哈希、MTU、QoS token bucket
│   ├── dma/                # 6 队列 DMA 引擎（描述符环）
│   ├── pci/                # PCIe AXI 封装（TLP 生成/completion/tag 管理）
│   ├── eth/                # 上行包解析（VLAN/QINQ、IPv4/6、协议位置检测）
│   ├── i_e_gress/          # 出入口通道（Core_rx/tx_side、checksum 链）
│   ├── forward/            # 转发流水线（路由/NAT/替换 MAC-IP-端口/校验和）
│   ├── qos/                # QoS 6 队列 + 流控 token bucket
│   ├── table/              # 会话表调度、哈希生成
│   ├── tlv/                # TLV 配置报文解析（表项下发）
│   ├── blacklist/          # 黑名单过滤（DDR 哈希；TCAM 为死代码）
│   ├── ddr_ctrl/           # DDR 读写调度、响应解复用、跨时钟 FIFO
│   ├── pkt_tracing/        # 报文追踪/统计
│   ├── pkt_replay/         # 报文回放（寄存器写入发包）
│   ├── payload_hash/       # 载荷哈希（CRC16/CRC32）
│   ├── port_group/         # 端口组 RAM 仲裁
│   ├── share_ram/          # 跨卡共享 RAM 链接表
│   ├── mtu/                # MTU 检查/分片
│   └── updata/             # SPI/QSPI 固件升级 + ICAP reload（非表更新）
├── sim/
│   ├── nic_top/            # 整卡仿真：tb_nic_top.sv + testcase/（tc0~tc25, tc32~tc34）
│   ├── tb_top.sv           # 单元级测试
│   ├── tb_unit/pg/mtu/ram_share/position_check/sdip_hash_gen.sv
│   ├── sim_lib/            # Typdef_pkg / NF_task_pkg / Inf_def / Eth_pkg / Busdri_pkg
│   ├── tb_dma/             # DMA 测试平台（xge_intf/driver/env）
│   └── tb_model/           # dma/pcie/ddr/eth 行为模型
├── constraint/             # timing.xdc / pin.xdc / pin_golden.xdc / 80G_PG3T500.ucf
├── build/                  # ec_8x10_nf_v1.xpr + Makefile（switch/golden 板变体）
├── build_lib/              # bin_gen/set_version/set_version_golden/multiboot TCL
└── ip/                     # axi_vip / ddr4_0_dns / tcam_64p / bd
```

## 3. 顶层数据流（top.sv）

每个通道（CHNL_NUM，`PROC_GEN` generate 循环）的报文流水线：

```
以太网 RX (40G/10G MAC)
  → eth_rx_pkt_sch        (3→4 路以太网调度)
  → eth_ul_pkt_parsing    (VLAN/QINQ/IPv4/6/ARP 头解析 + 5 元组哈希 + 协议位置检测)
  → pkt_parsing_sch       (4→1 合并)
  → position_check        (CRC16 协议识别：telnet/ftp/imap/pop3/http/mysql)
  → eth_sta               (RX 统计 + 未知包旁路)
  → session_t_sch         (会话表查询：哈希→DDR→会话状态→路由/丢弃)   [mem_out[6]]
  → blacklist_proc        (黑名单过滤，DDR 哈希匹配)                  [mem_out[7]]
  → Forward_top           (转发流水线：替换 MAC/IP/端口、TCP 校验和、DMA/SES mux、跨卡) [mem_out[8]]
  → up_numa / sdip_hash_gen / dma_full_bypass   (NUMA 跨卡、RSS 哈希、DMA 满旁路)
  → design_bd_wrapper     (PCIe DMA，2× Gen3 x8)
  → Egress_chnl / Core_tx_side → 以太网 TX
```

控制/配置路径：PCIe AXI-Lite（`axi2pci`）→ `top_mem_map`（LBS，BASE 0x08_0000）→ 各模块 `*_mem_map` 寄存器堆 + TLV 配置包下发（`tl_parsing` → 会话/ACL/黑名单/邻接表）。

### 3.1 mem_out 槽位（LBS 寄存器挂接）
| 槽 | 模块 | LBS BASE |
|---|---|---|
| [6] | session_t_sch | 0x08_0000 |
| [7] | blacklist_proc | 0x08_9000（TCAM） |
| [8] | Forward_top | 0x084_000 |
| [9]/[10] | update（SPI 主/从） | 0x08_3000 / 0x08_3800 |
| [11] | axis_rxq_demux | — |
| [12] | QSPI | 0x001_000 |

## 4. 核心子系统

### 4.1 数据面基础（common/）
- `user_bus_def.sv`：虚拟类 `BUS#(DW,CHW)`，变体 A(vld/sop/eop/data)、B(+left)、C(+ch)、D(+ch 无 left)；`DDR#(DW,CHW)::RES`、`MEM#(32)::IN/OUT`、`AXI_256`、`axi_lite_if`、`ETH_FIELD`。
- `bus_c_sch` / `pkt_with_rdy_sch`：带优先级仲裁的 N→1 包调度器（FSM IDLE/SEL/WAIT，round-robin + 优先级选择）。
- `sc_fifo_ctrl` / `sc_fifo_idx`：同步 FIFO（读写请求/响应地址）；`dc_fifo_across` / `dc_fifo_c_ctrl`：异步跨时钟 FIFO。
- `ddr_ctrl`：DDR 写调度（hash_inv 校验、self_check `0x5a`），4 级流水线 CRC32 哈希。
- `hash_32b_gen`：32-bit LFSR CRC（init 0xffffffff）；`crc16_d64` / `crc16_pipeline`：CRC16。
- `qos_block` / `fc_bucket`：QoS 6 队列 + 流控 token bucket（CIR）。
- `mtu.sv` / `mtu_comb.sv`：MTU 检查/分片流水线。

### 4.2 转发流水线（forward/）
- `Forward_top`：流水线顶层，含 TCP 校验和过滤器、MTU、IPv4 校验和、包追踪检测。
- `Route_mux`：SESc（会话）+ Bpsc（黑名单）→ 每口 eth_tx 复用；转发模式由 `ruser[164:157]` 解码：`0x18` 虚拟线 / `0x14` 交换 / `0x12` SNAT / `0x52` SNAT+port / `0x11` DNAT / `0x51` DNAT+port；输出 `Eth_tx_user_tmp[1:0]`：00 虚拟 / 01 路由 / 10 交换 / 11 DMA。
- `Replace_mac` / `Replace_ip` / `Replace_port`：按邻接表/NAT 标志替换 MAC/IP/端口。
- `Tcp_decode` → `Tcp_ckes_calc` → `Tcp_ckes_replace`：TCP/UDP 校验和增量重算。
- `crs_crd` / `crs_crd_numa` / `up_numa`：跨卡（local_sid ↔ ovc_sid）转发与 NUMA 交叉开关（N_NUM=2）。
- `mac_rep_tab`（全局实例）：邻接表，TLV 配置（`adj_tab_vld/val`），flag 查询（macid_addr）+ 数据查询（97b/flag）+ 寄存器查询；统计 `mac_rep_nofind_cnt` / `mac_rep_err_cnt`。

### 4.3 会话表（table/）
- `session_t_sch`：每包会话查询——哈希五元组 → DDR 读 → 会话状态 → 转发/丢弃；输出 4 路（dout0 首包/刷新、dout2 转发带元数据、dout3 ARP/DDR 未命中）。
- 会话匹配键：DIP_H32+VLAN+T0+DIP_L32+SIP_H32+VLAN+T1+SIP_L32+DPORT+SPORT+P_ID+ETHID_I+MACID+FLAG+ETHID_O+NATIP+NATPORT+F_CTRL。
- `t_hash_gen`：4 深流水线 CRC32 哈希写 DDR 会话表；`st_sch_mem_map`：会话 CSR/统计（含 RSS_CFG、FT_DB 读回、GBL_TIMEOUT、AGING_CFG）。

### 4.4 配置下发（tlv/）
- `tl_parsing`：解析 type(2B)/len(2B) TLV，分发给哈希生成或邻接表；type 151/152=黑名单、161/162=会话、171/172=ACL、196/197=邻接（奇 add / 偶 del）。
- `cfg_pkt_check`：AXIS→BUS-C 配置分类器（0=黑名单、1=会话/MAC 替换、2=非法）。
- `cfg_ip_parsing`：从以太网/IP 头提取字段偏移（no-VLAN/1-VLAN/QinQ，IPv4/6/ARP），构建会话/黑名单键。

### 4.5 DMA（dma/）
- `ndma_core`：6 队列 DMA（`QUEUE_COUNT=6`），UL 描述符环 + DL 描述符环。
- `up_stream_unit` / `down_stream_unit`：描述符取回 FSM、`axi_master_new`（256-bit AXI4 主，WR_FSM_NORMAL/STOPONE）。
- tuser 定义（`single_port_dma`）：b15 rss、b10 timedout、b9 mac-not-found、b8 across-card、b7:3 eth 端口、b2 会话刷新、b1 ACL、b0 黑名单。
- 寄存器：UP/DOWN_ADDR/LEN（0x080-0x0C0）、DMA_RESET 0x4000、PTR_START 0x4500、CHNL_NUM 0x4600、RX/DROP_PKT_CNT 0x4700+。

### 4.6 PCIe（pci/）
- `axi2pci`：PCIe 顶层胶水，实例化 `pci_xil_wrapper` + AXI 写/读通道 + AXI-Lite 主/从 + `axi_reg`（配置/统计寄存器）。
- TLP 处理：`mwr`（写 TLP）、`mrd`（读 TLP）、`mreq`（RQ 合并）、`scompd`（completion 数据路径）、`tag_manger`（标签分配/回收）。
- W_MAX_TLP_LEN = 256/512（SIM），R_MAX_TLP_LEN=256，R_MAX_USR_LEN=9216/2048。
- `pci_xil_core_wrapper`：SUBSYS_VEND_ID=0x8066，PCIe Gen3（KU060）/ Gen4（KU15P/VU13P）选择。
- `pci_bus_def`：`bus_pci#(DW,AD_W)::avl_ch`，arid 编码：xx0=DL 描述符请求、xx1=DL 数据读、xx2=UL 描述符请求、xx3=DL 配置请求。

### 4.7 以太网解析（eth/）
- `eth_ul_pkt_parsing`（v1/v2）：VLAN/QINQ、IPv4/6/ARP 头提取、DMAC 配置匹配、5 元组哈希、协议位置检测（Telnet+24/FTP+33/IMAP+42/POP3+19/HTTP+38/MySQL+34）。
- `eth_sta`：RX 统计 + `ipv4_ckes_filter` + 4× 包追踪检测。
- `eth_reset`：PHY/MAC 复位控制器（100ms 延迟、链路状态判定）；`data_led`：活动指示。

### 4.8 黑名单（blacklist/）
- `blacklist_proc`：2 路黑名单流调度，实例化 `blacklist_filter`；TCAM 路径 `if(0)` 死代码，被 `axi_cam_slave`（仿真 CAM）替代；top 上 `bypass_en` 置 1（整链旁路）。
- `blacklist_filter`：DDR 哈希匹配（键 = sipH32+sipL32+sport+pid），命中即丢。
- `blacklist_tcam`：Xilinx TCAM IP（`tcam_64p`）包装，64b 键查找，保留未用。

### 4.9 固件升级（updata/）
- `update` / `spi_ctrl`：SPI 主/从（mst/slv 级联），LBS 0x08_3000。
- `Qspi_top` / `Qspi_lbs` / `Qspi_upgrade` / `Qspi_cmd` / `Qspi_dri`：QSPI flash 命令（rdid/erase/page program/rd/wr）、双 RAM ping-pong 升级。
- `reload` / `Reload_program`：ICAP/CSIB Xilinx IPROG 序列（SYNC_WORD=AA995566、IPROG_CMD=0000000F、WBSTAR）实现 FPGA 重加载。

### 4.10 出入口通道（i_e_gress/）
- `Ingress_chnl`：MAC 核侧 AXI-S 收包入口，跨时钟域（sys_clk/coreclk）+ 位宽归一化到 256-bit 用户总线；参数化 DW（40G 口=256 / 10G 口=64），sop 延迟 = `INGRESS_PKT_GAP+1`（64b 口 gap=7，256b 口 gap=1）；输出 `BUS#(256,6)::C eth_rx` + bypass 流；统计 pkts/byts/crc/min/jumbo/fc。
- `Egress_chnl`：发送出口，用户 256-bit → MAC 核侧 AXI-S；`eth_link_up` 门控；bypass 流来自相邻端口（索引 `i^3'b001` 交叉配对）；汇聚 MAC `stat_tx_*` 错误统计。
- `Core_rx_side`：PCIe/DMA 下行接收侧适配器（`AXI#(256,1)::S` → 256-bit 用户总线），2 态 FSM IDLE/TRF。
- `Core_tx_side`：发送方向 256→64 位宽下变换 + tkeep 展开 + tpfull 反压。
- `dma_full_bypass`：**DMA 满防丢包硬件回环**——`dma_afull & en` 时 mux 切换，上行流直接导入下行输出口绕过主机内存；通道 `AXI#(256,20)::S` 上行 / `AXI#(256,8)::S` 下行。
- `tcp_ckes_filter`：转发路径 TCP 校验和处理直通管道（两级打拍）；ch[95:0] 布局含 port_shift/ip_shift/pid/eth_outid/etype/tracing。
- `ipv4_ckes_filter`：IPv4 头校验和增量计算与回写（DSP_EN=1 用 DSP 累加，REPLACE=1 改写 total_length/checksum）；etype 编码 [7:6]=VLAN 层数、[5]=tcp、[4]=udp、[2:0]=协议类型。
- `eth_sta`：端口状态聚合中心——收包元数据解析分发（`din.ch[95:0]`=ses+pak_tracing+sip_hash[27:0]+five_tuple_hash[27:0]+port_shift+ip_shift+mod_field+etype+eth_id）→ 去会话表；未知包走 `pkt_unkown_sch_in`（bps2dma）；mod_field1(16b)：rss/tracing/timeout/mac-not-found/across-card/port/refresh/ACL/blacklist 位域。

### 4.11 MTU 引擎（mtu/）
- `mtu.sv`：按 4 组软件可配阈值 `mtu_num[3:0][15:0]` 判定超长包；写 RAM 缓存报文 + `MTU_PKT_INFO` FIFO 缓存包描述符（结构体含 saddr/length/mtu_length/l3_offset/l4_offset/ipv4_length/flags/fragment）。
- `mtu_comb.sv`（注意模块名实为 **`mut_comb`**）：读出/重组核心，三路 FSM `IDLE → RD_BYPASS/RD_PRI/RD_SED`（分片包二次读取补包头跨行数据）；函数 `instr()` 在 sop 行替换 IPv4 length/flags/fragment 半字，`clr_data()` 清 padding 与行尾无效字节；4 级描述符随行流水。

### 4.12 报文追踪与共享 RAM（pkt_tracing/ share_ram/ port_group/）
- `pkt_tracing_detection`：双时钟命中计数器（clk0=traffic clk 计数，clk1=sample clk 采样快照）；`pkt_tracing_mem_map` 提供寄存器接口。
- `ram_share`：跨卡共享包缓存——链表管理（`link_tab` 空闲块链）+ `hdr_pointer_fifo` 存包头指针 + XPM_SDP_RAM 大缓冲（RAM_D=2048×RAM_W=1024）；`ram_wr` 按通道分发写入（DISPATCH_MODE="port"）、`ram_rd` 按 OCN 出口读出、`ram_sour` 资源计数；反压用 pfull 阈值。
- `pg_top`/`port_group`：端口组配置——LBS 寄存器（BASE+offset 0x0=id/0x4=cfgw/0x8=cfgr_id/0xc=cfgr 读回/0x10=当前 pg_id/0x14=表值）驱动 `pg_tab` 表项，`pg_req` 发起查询；用于按卡号（local_sid/ovc_sid）动态映射出口端口。

### 4.13 报文回放引擎（pkt_replay/）
- `pkt_rply.v`：**寄存器接口注入报文**的调试工具——CPU 经 LBS（BASE 24'h9_0000）逐字写入报文内容与长度（`PKT_LENB`），存入 512×72b BRAM（每字节 9-bit：tlast + 尾拍低 3 位字节数内嵌于最后一拍）；系统时钟域写、网口时钟域读（toggle 同步 + HARD_SYNC），读 FSM `RD_IDLE→FIRST_WORD→LOAD_FETCH→TX→EOF` 重构 AXIS-S 输出；状态寄存器 BUSY/W_CNTR/R_CNTR/PW_ERR（必须从地址 0 写起否则置错）。用途：无流量源时手工构造报文验证数据面。

### 4.14 载荷哈希（payload_hash/）
- `payload_hash_gen.sv`：RX 分类前端（axis_rxq_demux 内实例化），对每包并行算 **3 种 CRC-32**（Ethernet 多项式 0x04C11DB7、初值全 1、64bit/拍）：①载荷哈希（4 lane 并行吃 256-bit 流，窗口头/尾偏移可配 `HASH_CAL_CFG`）②四元组去源端口 ③四元组去目的端口（各 2 实例处理 128-bit key）；结果拼进 sop 拍 data[255:0] 随流下发（含 HASH_ADD_CFG 加法盐、HASH_QUE_CFG 字段掩码），供 QoS 6 队列分类作键；3 组 sc_fifo_idx 配对哈希结果与报文流。
- `payload_hash_mem_map.sv`：寄存器堆 BASE 24'h8_a000——DIN/DOUT 统计、HASH_INFO_0~5 状态、HASH_CAL_CFG/HASH_QUE_CFG/HASH_ADD_CFG 配置。

### 4.15 QoS 主机接口与包信息（qos/ 补充）
- `host_intf.v`（模块名实为 `host_inft`）：QoS 的 CPU 寄存器窗 BASE 24'h8_8000——4 个 48-bit 包计数（S0/S1/M0/M1 高低字）、令牌桶表项间接读写（WDATA_2/1/0+WADDR 共 67-bit 表项经异步 FIFO 送 fc_bucket 表）、TIMOUT_EN/OVER_FLOW 状态。
- `pkt_info.v`：256-bit 流透传级（零开销，tready 直通），eop 拍测包长（累加 32B+尾拍 left），从 tuser[19:0] 提取 QoS 分类字段（tc_en/up_dn/per_ip_en/line_fc_id[16:13]/fc_id[12:0]）交 6 队列调度，输出剥掉 QoS 位仅留 sop 下传。
- `ddr_ctrl/rd_res_demux.sv`：DDR 读响应按 addr[0] 标签分发——0=会话表直通 out[0]、黑名单直通 out[1]、1=主机调试读（dc_fifo_across 跨时钟送 top_mem_map 的 DDR_DB_RD_A0 调试口）。

## 5. 仿真与测试

### 5.1 测试平台
- `sim/nic_top/tb_nic_top.sv`：整卡 TB，DUT `inst_top`；时钟 250M/100M/80.03M/312.5M；AXI VIP `m_agent[1:0]` + `axi_wr/axi_wr32/axi_rd/axi_rd32`；`log2file` 记录。
- `tc_drivers.svh`：40G/10G 队列驱动（`axis_eth_40g_rx` / `axis_eth_10g_rx`，`#8us` 后于 `posedge eth_tx_clk` 弹包）。
- 共享任务：`cfg_session_table`（3-beat AXI_256 TLV，fwd_mode 选 map/swap/route）、`cfg_mac_adj`（TLV 196）、`cfg_ip_blackboard`（TLV 151）、`eth_pkt_gen`（512-bit 队列，eth_id 0-1→40G / 2-5→10G，支持 0800/86dd/0806、VLAN 1-2 层、TCP flags、icmp、dns）。

### 5.1a 仿真库（sim/sim_lib/）
- `Typdef_pkg.sv`：L2/L3 协议常量（8100/0800/86dd/0806、TCP=06/UDP=11）+ 枚举 Eth_L2_t/Eth_L3_t/**SES_MODE**（VIRUTAL_LINE/EXCHANGE/ROUTE）/NAT_MODE（SNAT/DNAT/NNAT）/PORT_MODE + common_bus 结构体。
- `Inf_def.sv`：`AXIS_if#(DW,UW)` 与 `AVAL_if#(DW,UW)` interface——含 mst/slave clocking block 与 modport，TB 与 DUT 的标准握手界面。
- `Busdri_pkg.sv`：`axi_bus_dri`（m_axis_dri 发包/s_axis_dri 收包）与 `avl_bus_dir`（m_/s_aval_dri）两类 driver class，封装 virtual interface 驱动。
- `Eth_pkg.sv`（113KB，最大库）：`pkt_ctrl`（send_pkt/rec_pkt/calc_checksum）、`pkt_buf`（clr/comp 比对）、`Eth_frame_gen`（gen_randc_pkts 随机帧、NF_SES_GEN 会话帧 180-bit 元数据、eth_frame_compare）、`Eth_frame_decode`（逐层解码）、`mtu_c` 等。
- `NF_task_pkg.sv`：空壳（仅 import Typdef_pkg），预留扩展。
- 单元 TB（sim/ 根目录散置）：`tb_unit.sv`（20KB 汇总单元测试）、`tb_mtu.sv`、`tb_pg.sv`、`tb_position_check.sv`（50KB 最大）、`tb_ram_share.sv`、`tb_sdip_hash_gen.sv`、`tb_top.sv`；另有 `tb_dma/`（15 文件 DMA 专用 TB）与 `README.txt`。

### 5.2 测试用例（29 个：tc0~tc25, tc32~tc34）
| 用例 | 内容（以文件头 Description 为准） |
|---|---|
| tc0 | 光口 0~3 上行 IPv4 TCP 报文统计出口（bypass） |
| tc1 | 虚拟线模式全转发（唯一记录 PASS：`tc_summary.log` 2026-07-15） |
| tc2~tc3 | 虚拟线 / 交换模式 |
| tc4 | 路由模式 |
| tc5~tc25 | 交换/路由 + 会话刷新 + 采样 + 双卡 DMA 等（tc23：5 轮 IPv4 TCP 96B 双卡 DMA 路由转发 + 采样校验） |
| tc32~tc34 | 新版用例（自带 BSC 函数、三元 dip 布局） |

判定谓词示例：`tc0: [4:0]==~5'd0`、`tc1: [3:0]==~4'd0`、`tc16: [2:0]==3'b111`、`tc19: [5:0]=='b11_1111`。

### 5.3 构建体系
- `sim/nic_top/Makefile`：BOARD 选 `nsfocus_ku060_switch`（→pin_nsfocus_ku060_switch.xdc + `NSFOCUS_KU060_SWITCH`）或默认（pin.xdc + `NSFOCUS_KU060`）。
- `build/Makefile`：BOARD 选 `nsfocus_ku060_golden`（→pin_golden.xdc + `GOLDEN` + 版本 0D02_0301）；GRAPH=on→GUI / off→batch `synth_1`→`impl_1`→bitstream。
- `build.tcl`：`export_simulation -simulator questa` + `launch_runs synth_1 -jobs 10`。
- `msim_setup.tcl` / `com_dma.tcl`：Questa 库编译（xilinx_vip/xpm/axi_vip/cam/gtwizard/design_1 bd/tcam_64p）。
- `build_lib/bin_gen.tcl`：发布 bin `01_02_06_04_03_0D_260605_0011_0326_0014.bin`；`set_version_golden.tcl` 写入 `define GOLDEN` 并改 AXI VIP OUTSTANDING 2→1。
- `multiboot_address_table.tcl`：XAPP1246/1247 式 multiboot 表（256kB 扇区、timer image 1kB）。

## 6. 约束要点
- `timing.xdc`：clk_100m 10ns、MMCM 输出 100/200/5MHz、gt_40g/gt_10g 参考 6.4ns、PCIe 参考 10ns、跨时钟域 false path。
- `pin.xdc`：multiboot Pro（NEXT_CONFIG_ADDR 0x0、CONFIGFALLBACK、SPIx8、CONFIGRATE 40）、clk_100m=AG12。
- `pin_golden.xdc`：NEXT_CONFIG_ADDR 0x00F7FE00 + NEXT_CONFIG_REBOOT。
- `80G_PG3T500.ucf`：SFP0~7、PCIE_L4~L7、DDR4D_*、FPGA_P* 引脚 LOC。
- `timing.fdc` / `pin.fdc`：Pango（紫光同创）`define_attribute` 引脚/时序文件。

## 7. 关键设计模式提炼（可复用）
1. **BUS 宏数据结构**：用 `virtual class BUS#(DW,CHW)` + typedef 封装 A/B/C/D 四级总线变体，全工程统一参数化接口——降低端口连线复杂度。
2. **统一 256-bit 数据面 + ch 元数据"包护照"**：模块间用户总线固定 256-bit 数据 + 96-bit `ch` 侧带；各阶段只改写自己负责的 ch 字段（sip_hash/five_tuple_hash → mod_field/etype → pid/port_shift → ovb），下游按位切片解码——新增处理阶段只需扩展位域，不改总线协议。
3. **generate 通道复用**：顶层用 `CHNL_NUM` generate 循环实例化整条数据面，配合 `mem_out[slot]` 槽位按地址挂 LBS 寄存器，扩展通道数只改参数。
4. **哈希 + DDR 表**：流/会话/黑名单统一走「CRC32 哈希 → DDR 读 → 状态判定」，与 TCAM 方案互补（TCAM 留给黑名单但当前被 DDR 哈希替代）。
5. **三级旁路保护**：① 端口级 bypass（Ingress/Egress 交叉端口直通，索引 `i^3'b001`）；② DMA 满硬件回环（dma_full_bypass 绕过主机内存防丢包）；③ 功能级旁路（ckes_bps/mtu bypass/黑名单 bypass_en）——任一环节故障流量仍可达。
6. **校验和流水线**：`Tcp_decode → Tcp_ckes_calc → Tcp_ckes_replace` 三段增量重算 + `ipv4_ckes_filter` DSP 反码和累加，避免整包重算。
7. **跨卡 NUMA**：`crs_crd` + `up_numa` 交叉开关在卡间转发表项与报文（local_sid ↔ ovc_sid），实现双 PCIe 通道负载分担。
8. **QSPI/ICAP 升级**：SPI 主从级联 + QSPI 双 RAM ping-pong + IPROG reload 构成完整 OTA/多引导方案。
9. **链表式共享缓存**：ram_share 用「空闲块链表 link_tab + 包头指针 FIFO + 大 SDP RAM」实现多出口共享包缓冲，比固定分区 FIFO 节省内存且天然支持变长包。
10. **仿真体系**：单元 TB（tb_*）+ 整卡 TB（tb_nic_top）+ 29 个自检用例，`tc_*.sv` 每个用例独立 `module`，用 `log2file` + 状态谓词判定。

## 8. 已知注意事项
- `readme.txt`（sim/nic_top/testcase/）已过时（只写 tc0~tc4），以用例文件头 `// Description` 为准。
- TCL 脚本路径为 Linux（`/home/xilinx/Vivado/2022.1`、`/opt/xilinx/dev_lib`），Windows checkout 下不可直接执行，需改路径。
- `GOLDEN` 宏用于 golden 版本（仿真置 `init_calib_complete/ui_rst/self_check`，禁用真实 DDR4 MIG）。
- `ddr4_1_dns`（16-bit SODIMM）已注释禁用，仅用 128-bit 会话 DDR。
- 黑名单 TCAM 为死代码（`if(0)`），实际匹配走 DDR 哈希；`bypass_en` 在 top 被置 1。
- **命名陷阱**：文件名 `mtu_comb.sv` 但模块名为 `mut_comb`；`host_intf.v` 模块名为 `host_inft`；目录名 `i_e_gress`；`ckes` 是 checksum 的拼写变体；`pkt_tracing_hit.sv` 文件头注释与实际模块名 `pkt_tracing_detection` 不符。

## 相关链接
- **深度模块分析（本综述补深）**：[[sources/chips/FPGASourceAnalysis/skill|FPGASourceAnalysis Skill 索引]]（43 个模块文件，覆盖全部 RTL 子目录 + 仿真 + 约束）
- 资料蒸馏对照：[[50-reference/sources/chips/NIC DPDK|网卡与 DPDK]]
- 架构对照：[[50-reference/sources/chips/SmartNIC DPU|SmartNIC 与 DPU]]
- 同类国产 FPGA：[[50-reference/sources/chips/Centec CTC 7132|盛科 CTC7132 交换芯片]]
- 方法论：[[synthesis/FPGA 芯片 设计 系统性 指南|FPGA 完整芯片代码构建综述]]
- 基础：[[20-protocols/FPGA AXI 4 总线|AXI4 总线协议]]、[[20-protocols/FPGA DDR 内存|DDR 存储器接口]]