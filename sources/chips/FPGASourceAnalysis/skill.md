# NSFOCUS FPGA 智能网卡 RTL 源码分析 Skill

基于 `ips_test_2025_add_mpls_6que`（Xilinx KU060，Vivado 2022.1）的模块化深度分析索引，聚焦 SmartNIC 数据面：DMA 引擎、PCIe 桥、转发流水线、DDR 会话表、QoS 六队列、黑名单与仿真体系。

## 全局配置

```yaml
source_zip:    Q:\AI\ips_test_2025_fpga.zip
extract_work:  Q:\AI\fpga_work\ips_test_2025_add_mpls_6que\
source_commit: SVN（工程含 .svn 元数据，无 git hash）
author:        luoanchen  dev_ver: 01_02_06_04  nic_ver: 03_0D_0014  date: 2026_0605
device:        xcku060-ffva1156-2-e（Kintex UltraScale+）
tool:          Vivado 2022.1 + QuestaSim 10.7c
analysis_lang: zh-CN
file_size_limit: 8KB（超限按 _part1/_part2 拆分）
top_kb_page:   50-reference/sources/chips/ips_test_2025_fpga（顶层一页式综述，本知识库为补深）
```

## AI 使用流程

1. 先读综述页（`50-reference/sources/chips/ips_test_2025_fpga.md`）确立工程全貌。
2. 按下表「功能/接口」找对应模块分析，进入后优先看 `## 0.` 或第一小节建立架构图景。
3. `ch[95:0]` / `tuser` 位域跨模块查阅：`03-dataplane/ch-protocol.md`。
4. LBS 寄存器地址/字段：`05-qos-memmap/lbs-register-map.md`。
5. 排查问题先查 `faq.md` 的「已知坑」，再在对应模块文件的 `## 疑点/待核实` 小节核实。
6. 本知识库为**源码事实记录**，不补写源码未明确给出的内容；多处「待核实」标注需对照 Vivado project 或实测确认。

## 全局约定

- RTL 路径统一写作相对 `ips_test_2025_add_mpls_6que/rtl/` 的形式（如 `top.sv`、`dma/ndma_core.v`）。
- 数据总线：`BUS#(DW,CHW)::A/B/C/D`四级变体（`user_bus_def.sv`）；256-bit 数据 + `ch[95:0]` 侧带是全工程统一「包护照」（详见 `03-dataplane/ch-protocol.md`）。
- **已知死代码**：`blacklist_tcam`（`if(0)` 不综合）、`qos_block`（top 注释）、`pkt_tracing_mem_map`（top 注释）、`Axis2Avls`/`Eth_package`/`Message_package`（遗留）、DDR 第二片 `ddr4_1_dns`（注释）。
- **命名陷阱**：`mtu_comb.sv` 模块名实为 `mut_comb`；`host_intf.v` 模块名实为 `host_inft`；`pkt_tracing_hit.sv` 实为 `pkt_tracing_detection`；目录 `updata`（非 update）。
- 全局配置只在此处声明；模块文件出现可配置值时仅引用，不重复定义。
- 每个模块文件 ≤ 8KB；超限按 `_part1`/`_part2` 拆分，分片文件末尾含继续链接。

## 子文档索引

### 00 - 顶层总览

| 功能/接口 | 文件路径 |
|---|---|
| 顶层端口/CHNL_NUM generate/时钟复位/ETH 调度 | [00-overview/top-dataflow_part1.md](00-overview/top-dataflow_part1.md) |
| 数据面 17 级流水 / mem_out 槽位全表 / 控制面 AXI 链 | [00-overview/top-dataflow_part2.md](00-overview/top-dataflow_part2.md) |
| TLV 路径 / DDR 实例 / NUMA 双卡 / bypass_en 位定义 | [00-overview/top-dataflow_part3.md](00-overview/top-dataflow_part3.md) |
| ver_define 宏 / BUS# 变体 / DDR#/MEM#/AXI# 接口 / ETH_FIELD | [00-overview/defines-params_part1.md](00-overview/defines-params_part1.md) |
| pci_bus_def / TLP fmt/type / arid 编码 / bus_pci# 结构 | [00-overview/defines-params_part2.md](00-overview/defines-params_part2.md) |
| 覆盖率审计矩阵（rtl 逐文件已覆盖 / 浅覆盖 / 未覆盖） | [00-overview/coverage-audit.md](00-overview/coverage-audit.md) |

### 01 - common/ 通用原语

| 功能/接口 | 文件路径 |
|---|---|
| bus_c_sch / pkt_with_rdy_sch / rd_req_sch 调度仲裁 | [01-common/arbiters.md](01-common/arbiters.md) |
| sc_fifo_ctrl/idx / dc_fifo_across/ctrl / dff / reg_axi_b | [01-common/fifo-primitives_part1.md](01-common/fifo-primitives_part1.md) |
| reg_axi_b ETH 扇出 / top_mem_map 全寄存器窗口 | [01-common/fifo-primitives_part2.md](01-common/fifo-primitives_part2.md) |
| position_check CRC16 协议识别 / axis_rxq_demux / sdip_hash_gen / CRC 簇 | [01-common/parse-hash-demux_part1.md](01-common/parse-hash-demux_part1.md) |
| CRC 簇续 / eth_pkt_gen / crc_adjust | [01-common/parse-hash-demux_part2.md](01-common/parse-hash-demux_part2.md) |
| clk_rst_ctrl 复位链 / timeout_gen / pps_async_cnt / xadc_capture | [01-common/reset-util.md](01-common/reset-util.md) |

### 02 - dma/ DMA 引擎

| 功能/接口 | 文件路径 |
|---|---|
| ndma_core 描述符环 / defines.v 队列常量 / design_bd_wrapper 封装 | [02-dma/core-descriptor.md](02-dma/core-descriptor.md) |
| up_stream_block/unit 上行取描述符 / rx_info_gen / WrReq 转换 | [02-dma/up-stream_part1.md](02-dma/up-stream_part1.md) |
| axi_master_new（WR_FSM / outstanding）/ st_gp_fifo_w360 | [02-dma/up-stream_part2.md](02-dma/up-stream_part2.md) |
| down_stream_block/unit 描述符 FIFO 与读请求 FSM | [02-dma/down-stream_part1.md](02-dma/down-stream_part1.md) |
| ptr_poll_block / ptr_update_block / axis_demux / abtr_4to1 / RdReq 转换 | [02-dma/down-stream_part2.md](02-dma/down-stream_part2.md) |
| axi_lite_slave / axi_master_0_axi_periph / design_bd_wrapper 跨钟与实例 | [02-dma/down-stream_part3.md](02-dma/down-stream_part3.md) |

### 03 - dataplane/ 数据面流水

| 功能/接口 | 文件路径 |
|---|---|
| slp_decode / Forward_shunt / Forward_lbs / Dma_Ses_mux / ch_trf / 遗留模块 | [03-dataplane/forward-gap.md](03-dataplane/forward-gap.md) |
| Eth_bypass / add / ckes_calc / Ingress/Egress 补充细节 | [03-dataplane/io-egress-gap.md](03-dataplane/io-egress-gap.md) |
| ch[95:0] 全库位域契约（A/B 方言 + ovb / session / dma 变体） | [03-dataplane/ch-protocol.md](03-dataplane/ch-protocol.md) |

### 04 - pci/ PCIe 桥

| 功能/接口 | 文件路径 |
|---|---|
| pci_top / pci_xil_wrapper(_top) / xil_cc/cq/rc/rq 四队列通道 | [04-pci/bridge-queues.md](04-pci/bridge-queues.md) |
| axi_data_split / d_slide_left/right / s_axi_r/w / m_axi_lite_r/w / axi_reg | [04-pci/axi-lite-access.md](04-pci/axi-lite-access.md) |

### 05 - qos-memmap/ QoS 与寄存器地图

| 功能/接口 | 文件路径 |
|---|---|
| QoS 三级令牌桶 / fc_bucket BRAM 表项 / pkt_info / host_inft 寄存器窗 | [05-qos-memmap/qos-engine.md](05-qos-memmap/qos-engine.md) |
| LBS 地址分配全表（0x08_0000 起各槽）/ 各 *_mem_map 寄存器逐偏移 | [05-qos-memmap/lbs-register-map.md](05-qos-memmap/lbs-register-map.md) |

### 06 - lookup-config/ 查表与配置

| 功能/接口 | 文件路径 |
|---|---|
| session_t_sch 查表 FSM / dout0~3 场景 / st_sch_mem_map 寄存器全表 | [06-lookup-config/session-table.md](06-lookup-config/session-table.md) |
| TLV 链路总览 / cfg_pkt_check（ch[1:0] 归类）/ tl_parsing（ type 表 / adj 分发） | [06-lookup-config/tlv-config-path_part1.md](06-lookup-config/tlv-config-path_part1.md) |
| cfg_ip_parsing（h_field 偏移/协议/字段提取）| [06-lookup-config/tlv-config-path_part2.md](06-lookup-config/tlv-config-path_part2.md) |
| t_hash_gen 4 深流水 CRC32 / DDR 写背压 / session_t_sch TLV 对接 | [06-lookup-config/tlv-config-path_part3.md](06-lookup-config/tlv-config-path_part3.md) |
| tcam_mem_map 寄存器 / blacklist_proc if(0) 死代码 / blacklist_filter DDR 流水 | [06-lookup-config/filters-portgroup-replay_part1.md](06-lookup-config/filters-portgroup-replay_part1.md) |
| blacklist_tcam（TCAM 死代码细节）/ pkt_rply_defines 常量 / pkt_rply 写侧 | [06-lookup-config/filters-portgroup-replay_part2.md](06-lookup-config/filters-portgroup-replay_part2.md) |
| port_group 查表改写（pg_top/port_group LBS）| [06-lookup-config/filters-portgroup-replay_part3.md](06-lookup-config/filters-portgroup-replay_part3.md) |
| pg_tab DL 下发表 / pg_req FIFO 配对 / pkt_rprx_comb 二选一 | [06-lookup-config/filters-portgroup-replay_part4.md](06-lookup-config/filters-portgroup-replay_part4.md) |

### 07 - firmware-build/ 固件与构建

| 功能/接口 | 文件路径 |
|---|---|
| update/spi_ctrl / Qspi 命令集 / SAXI_LITE2LBS 桥 | [07-firmware-build/fw-update_part1.md](07-firmware-build/fw-update_part1.md) |
| reload/Reload_program ICAP IPROG / ping-pong 升级数据流 | [07-firmware-build/fw-update_part2.md](07-firmware-build/fw-update_part2.md) |
| Makefile / build_lib TCL / msim_setup / com_*.tcl 编译流程 | [07-firmware-build/build-system.md](07-firmware-build/build-system.md) |

### 08 - constraint/ 约束文件

| 功能/接口 | 文件路径 |
|---|---|
| timing.xdc 时钟/false path / pin.xdc 引脚/多引导 / pin_golden.xdc / UCF / Pango .fdc | [08-constraint/constraints.md](08-constraint/constraints.md) |

### 09 - sim-testbench/ 仿真体系

| 功能/接口 | 文件路径 |
|---|---|
| tb_nic_top.sv 解剖 / AXI VIP / cfg_queue / log2file / modal TB | [09-sim-testbench/tb-nic-top.md](09-sim-testbench/tb-nic-top.md) |
| testcase_inc.svh（BSC/cfg 任务/eth_pkt_gen）/ tc_drivers generate / tc_tasks | [09-sim-testbench/testcase-infra.md](09-sim-testbench/testcase-infra.md) |
| 29 用例逐条语义：端口配置 / 转发模式 / 判定谓词 / 现状 | [09-sim-testbench/testcase-semantics.md](09-sim-testbench/testcase-semantics.md) |
| tb_dma env/driver/pcap / tb_model ddr/dma/eth/pcie 行为模型 | [09-sim-testbench/tb-dma-models.md](09-sim-testbench/tb-dma-models.md) |

### 10 - eth-parse/ 以太网解析器

| 功能/接口 | 文件路径 |
|---|---|
| eth_ul_pkt_parsing v1/v2：接口与 ch[124:0] 布局 / VLAN-QINQ-MPLS 头检测 / 8~10 级字段提取流水 / mod_field 与 etype / check_en 协议位置检测 / v1↔v2 差异 | [10-eth-parse/eth-parsing_part1.md](10-eth-parse/eth-parsing_part1.md) |
| 5 元组哈希 hash_32b_gen 输入时序 / pkt_parsing_sch 4→1 / pkt_parsing_mem_map 0x08_5000 寄存器 / eth_reset 5MHz 复位 / data_led | [10-eth-parse/eth-parsing_part2.md](10-eth-parse/eth-parsing_part2.md) |

### 11 - ddr-ctrl/ DDR4 调度器

| 功能/接口 | 文件路径 |
|---|---|
| ddr_ctrl：接口全表 / app_addr[27:0] 字段 / hash_inv 位反转 / 写优先 FSM / 0x5a POST 自检 / CDC / 死信号 | [11-ddr-ctrl/ddr-ctrl_part1.md](11-ddr-ctrl/ddr-ctrl_part1.md) |
| rd_res_demux：addr[0] 与通道位次组合解码 / 2 级寄存器流水 / 调试跨钟链路 | [11-ddr-ctrl/ddr-ctrl_part2.md](11-ddr-ctrl/ddr-ctrl_part2.md) |

> 本页即 Skill 入口 | [faq.md](faq.md)
