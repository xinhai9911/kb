# 覆盖率审计：现有综述 vs 本次深度分析

> 输入：`Q:\AI\ips_test_2025_fpga.zip`（内含 `ips_test_2025_add_mpls_6que/`）。基准为知识库既有综述 [[50-reference/sources/chips/ips_test_2025_fpga|NSFOCUS FPGA 智能网卡 RTL 工程分析]]（覆盖各子系统一段式概览、目录树、顶层数据流、mem_out 槽位、10 条可复用设计模式）。本文为"检查还有哪些地方没有覆盖到"的逐项审计结果，并映射到本技能集各深度分析页。

## 1. 审计对象与规模

| 范围 | 文件数 | 说明 |
|---|---|---|
| rtl/（作者自研 RTL） | 152 | 排除 build/ 与 ip/ 下的 Xilinx 厂商 IP |
| sim/ 源码（.sv/.v/.svh） | 97 | 含 Vendown tb_model；用户仿真源码约 60 |
| constraint/ | 10 | 6 文本约束 + 1 Excel 引脚表 + 3 说明 |
| build_lib/ | 7 | 3 tcl + 位流/烧写 bin |
| 解压工作区 | — | `Q:\AI\fpga_work\ips_test_2025_add_mpls_6que\`（仅分析用，不随库提交） |

## 2. 覆盖分级

- ==已覆盖==：综述给出模块级架构事实（职责、数据流、寄存器、状态机要点）。
- ==浅覆盖==：综述仅点到名字/一句话，无实现细节。
- ==未覆盖==：综述完全未提及。

## 3. rtl/ 逐模块审计

### def / 顶层

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| top.sv | 浅覆盖（数据流图+槽位表，无端口/参数/生成内幕） | [00-overview/top-dataflow](top-dataflow.md) |
| def/ver_define.svh | 浅覆盖（器件宏一句） | [00-overview/defines-params](defines-params.md) |
| def/user_bus_def.sv / user_bus_if.sv | 已覆盖（§4.1 一句）→ 补字段级 | [00-overview/defines-params](defines-params.md) |
| def/pci_bus_def.sv | 浅覆盖（arid 编码一句） | [00-overview/defines-params](defines-params.md) |

### common/（22 文件）

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| bus_c_sch.sv / pkt_with_rdy_sch.sv | 浅覆盖 | [01-common/arbiters](arbiters.md) |
| rd_req_sch.sv | 未覆盖 | [01-common/arbiters](arbiters.md) |
| sc_fifo_ctrl.sv / sc_fifo_idx.sv | 浅覆盖 | [01-common/fifo-primitives](fifo-primitives.md) |
| dc_fifo_across.sv / dc_fifo_c_ctrl.sv | 浅覆盖 | [01-common/fifo-primitives](fifo-primitives.md) |
| dff.sv / reg_axi_b.sv | 未覆盖 | [01-common/fifo-primitives](fifo-primitives.md) |
| clk_rst_ctrl.sv | 未覆盖 | [01-common/reset-util](reset-util.md) |
| timeout_gen.sv / pps_async_cnt.sv / xadc_capture.sv | 未覆盖 | [01-common/reset-util](reset-util.md) |
| position_check.sv / axis_rxq_demux.sv | 未覆盖（仅流水线一句） | [01-common/parse-hash-demux](parse-hash-demux.md) |
| sdip_hash_gen.sv / crc_adjust.sv / eth_pkt_gen.sv | 未覆盖 | [01-common/parse-hash-demux](parse-hash-demux.md) |
| hash_32b_gen.sv / crc16_d64.sv / crc16_pipeline.sv | 已覆盖（§4.1 要点） | [01-common/parse-hash-demux](parse-hash-demux.md)（补实现细节） |

### dma/（20 文件）

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| ndma_core.v / defines.v / bd/design_bd_wrapper.sv | 浅覆盖 | [02-dma/core-descriptor](core-descriptor.md) |
| up_stream_block.v / up_stream_unit.v | 浅覆盖 | [02-dma/up-stream](up-stream.md) |
| rx_info_gen.v / axis_to_native_WrReq.v / native_WrReq_to_axis.v / axi_master_new.v / st_gp_fifo_w360.v | 未覆盖 | [02-dma/up-stream](up-stream.md) |
| down_stream_block.v / down_stream_unit.v / ptr_poll_block.v / ptr_update_block.v | 未覆盖 | [02-dma/down-stream](down-stream.md) |
| axis_to_native_RdReq.v / native_RdReq_to_axis.v / axis_demux.sv / abtr_4to1.v | 未覆盖 | [02-dma/down-stream](down-stream.md) |
| axi_lite_slave.v / axi_master_0_axi_periph.v / single_port_dma.v | 未覆盖 | [02-dma/down-stream](down-stream.md) |

### forward/（18 文件）

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| Forward_top.sv / Route_mux.sv / Replace_*.sv / Tcp_*.sv / crs_crd*.sv / up_numa.sv / mac_rep_tab.sv | 已覆盖（§4.2） | —（不重复） |
| Forward_shunt.sv / Forward_lbs.sv / slp_decode.sv | 未覆盖 | [03-dataplane/forward-gap](forward-gap.md) |
| Dma_Ses_mux.sv / ch_trf.sv / Axis2Avls.sv / Eth_package.sv / Message_package.sv | 未覆盖 | [03-dataplane/forward-gap](forward-gap.md) |
| ch[95:0] 元数据跨模块契约 | 仅提到概念 | [03-dataplane/ch-protocol](ch-protocol.md) |

### i_e_gress/（13 文件）

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| Ingress_chnl.sv / Egress_chnl.sv / Core_rx_side / Core_tx_side / dma_full_bypass.sv / tcp_ckes_filter.sv / ipv4_ckes_filter.sv / eth_sta.sv / eth_rx_pkt_sch.sv | 已覆盖（§4.10） | [03-dataplane/io-egress-gap](io-egress-gap.md)（补 doc 未展开细节） |
| Eth_bypass.sv / add.sv / ckes_calc.sv | 未覆盖 | [03-dataplane/io-egress-gap](io-egress-gap.md) |

### pci/（22 文件）

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| axi2pci.sv / mwr / mrd / mreq / scompd / tag_manger.sv / pci_xil_core_wrapper.sv | 已覆盖（§4.6） | — |
| pci_top.sv / pci_xil_wrapper.sv / pci_xil_wrapper_top.sv | 未覆盖 | [04-pci/bridge-queues](bridge-queues.md) |
| xil_cc.sv / xil_cq.sv / xil_rc.sv / xil_rq.sv | 未覆盖 | [04-pci/bridge-queues](bridge-queues.md) |
| s_axi_r.sv / s_axi_w.sv / m_axi_lite_r.sv / m_axi_lite_w.sv / axi_reg.sv / axi_data_split.sv / d_slide_left.sv / d_slide_right.sv | 未覆盖 | [04-pci/axi-lite-access](axi-lite-access.md) |

### qos/ + 寄存器体系

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| qos_block.v / fc_bucket.v / qos_defines.v | 浅覆盖（一句话） | [05-qos-memmap/qos-engine](qos-engine.md) |
| pkt_info.v / host_intf.v(host_inft) | 浅覆盖 | [05-qos-memmap/qos-engine](qos-engine.md) |
| top_mem_map.sv + 各 *_mem_map | 浅覆盖（槽位表） | [05-qos-memmap/lbs-register-map](lbs-register-map.md) |

### table / tlv / blacklist / port_group / pkt_replay

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| session_t_sch.sv | 浅覆盖（§4.3 键布局） | [06-lookup-config/session-table](session-table.md) |
| st_sch_mem_map.sv | 浅覆盖（寄存器名枚举） | [06-lookup-config/session-table](session-table.md) |
| tl_parsing.sv / cfg_pkt_check.sv / cfg_ip_parsing.sv / t_hash_gen.sv | 已覆盖（§4.4 要点） | [06-lookup-config/tlv-config-path](tlv-config-path.md)（补链路细节） |
| blacklist_filter / proc / tcam | 已覆盖（§4.8） | [06-lookup-config/filters-portgroup-replay](filters-portgroup-replay.md)（补 TCAM 寄存器） |
| tcam_mem_map.sv | 未覆盖 | [06-lookup-config/filters-portgroup-replay](filters-portgroup-replay.md) |
| pg_top / port_group | 浅覆盖 | [06-lookup-config/filters-portgroup-replay](filters-portgroup-replay.md) |
| pg_req.sv / pg_tab.sv | 未覆盖 | [06-lookup-config/filters-portgroup-replay](filters-portgroup-replay.md) |
| pkt_rply.v | 已覆盖（§4.13） | — |
| pkt_rply_defines.v / pkt_rprx_comb.v | 未覆盖 | [06-lookup-config/filters-portgroup-replay](filters-portgroup-replay.md) |

### mtu / payload_hash / pkt_tracing / share_ram

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| mtu.sv / mtu_comb.sv | 已覆盖（§4.11） | — |
| payload_hash_gen / mem_map | 已覆盖（§4.14） | — |
| pkt_tracing_detection / mem_map | 已覆盖（§4.12） | — |
| ram_share / ram_wr / ram_rd / ram_sour | 已覆盖（§4.12） | — |

### updata/（10 文件）

| 文件 | 现状 | 深度分析页 |
|---|---|---|
| update / spi_ctrl / Qspi_* / reload / Reload_program | 已覆盖（§4.9） | [07-firmware-build/fw-update](fw-update.md)（补命令/状态机细节） |
| SAXI_LITE2LBS.sv | 未覆盖 | [07-firmware-build/fw-update](fw-update.md) |

## 4. sim / build / constraint 审计

| 范围 | 现状 | 深度分析页 |
|---|---|---|
| tb_nic_top.sv / tb_def / tb_top 模态 TB | 浅覆盖 | [09-sim-testbench/tb-nic-top](tb-nic-top.md) |
| testcase_inc.svh / tc_drivers.svh / tc_tasks.svh / tc_prelude.svh | 未覆盖（refactor 事实在 zip 内 CLAUDE.md） | [09-sim-testbench/testcase-infra](testcase-infra.md) |
| 29 个 tc*.sv 逐条语义 | 浅覆盖（tc 表一行一个） | [09-sim-testbench/testcase-semantics](testcase-semantics.md) |
| sim_lib 各包 | 已覆盖（§5.1a） | — |
| tb_dma env/driver/testbench/xge_intf + pcap | 未覆盖 | [09-sim-testbench/tb-dma-models](tb-dma-models.md) |
| tb_model（ddr/dma/eth/pcie 行为模型） | 未覆盖（vendor 部分不精读） | [09-sim-testbench/tb-dma-models](tb-dma-models.md) |
| build/Makefile + build_lib tcl + msim_setup + com_*.tcl / run_synth / nic_sim | 浅覆盖 | [07-firmware-build/build-system](build-system.md) |
| constraint/ 6 约束 + xlsx 引脚表 | 已覆盖（§6 要点） | [08-constraint/constraints](constraints.md)（补逐声明表） |

## 5. 审计结论

- 99 个 RTL 文件中，综述**未覆盖**约 46 个、**浅覆盖**约 35 个 → 本次为新全覆盖目标。
- 最大待补深区块：**pci/（15 个文件）、common/（13 个）**、dma/ 内部子块、仿真 testcase 设施。
- 已知不在本次分析范围内的厂商/IP 内容：`build/*.gen`（DDR4 等 IP 网表 RTL）、`ip/`（Xilinx IP 卡）、`tb_model/ddr/` 的 `ddr4_v2_2_*`/microblaze 等 Xilinx 生成代码。
- 综述已覆盖且本次不重复：Forward_top 流水线、Route_mux 模式译码、校验和三段、MTU 重组、共享 RAM 链表、pkt_replay 主引擎、payload_hash 三 CRC、黑名单 DDR 哈希、pkt_tracing 双时钟、red info 三数据库（见综述）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)