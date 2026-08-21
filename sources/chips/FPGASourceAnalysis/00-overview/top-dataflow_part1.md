# top.sv 深度解剖（part 1：端口 / 参数 / generate 体系 / 时钟复位）

> 源码：`Q:\AI\fpga_work\ips_test_2025_add_mpls_6que\rtl\top.sv`（2385 行，工程 `ec_8x10_nf_v1`，作者 luoanchen）。行号均指源码。数据面/槽位/控制面见 part 2。综述只给一句话的 §4.1 在此补成底层细节。

## 1. 模块参数与本地常量

| 参数 | 值 | 说明 |
|---|---|---|
| `ETH_REF_CLK_NUM` | 2 | 参考时钟域数（= 通道数，用于 reg bus / tlv 映射切片） |
| `ETH_NUM` | 8 | 以太网口总数 |
| `C0_APP_DATA_WIDTH` | 512 | DDR4 MIG c0 用户（UI）数据位宽 |
| `C0_APP_ADDR_WIDTH` | 28 | MIG 地址位宽（MIG 侧拼 `{1'b0,c0_app_addr}` → 29b） |
| `C0_CMD_DEPTH` | 45 | UI 命令深度 |
| `C0_COL/ROW/BANK/BANK_GROUP/RANK_WIDTH` | 10/16/2/1/1 | MIG 列/行/组/组群/rank 位宽 |
| `C0_TCK` | 938 | DDR 时钟周期 ps → 约 1066 MHz（DDR4-2133） |
| `C0_MEM_ADDR_ORDER` | "ROW_COLUMN_BANK" | MIG 寻址次序 |
| `C0_MEMORY_WIDTH` | 16 | 颗粒位宽（x16） |
| `C1_*`（APP_DATA=128、TCK=833…） | — | 第二片 DDR（blk 字典）参数，**已注释禁用** |
| `SIM_MODE` | 0 | 0=真实（含 MIG/update/xadc）；1=仿真（相关输出接 'h0） |
| `CHNL_ETH_NUM` | 4 | 每通道以太口数 |
| `CHNL_NUM` | `ETH_NUM/CHNL_ETH_NUM=2` | 处理通道数（每通道=1×PCIe x8 + 1×DDR4 + 4 口） |

本地常量：`DISPATCH_MODE="port"`（ram_share 分发）、`VLAN_ID=0`。

## 2. 端口总表（按功能分组）

| 信号名 | 位宽 | 方向 | 说明 |
|---|---|---|---|
| `clk_100m` | 1 | in | 板级输入时钟（10ns） |
| `qsfp_intn_f` / `qsfp_prsntn_f` | [1:0] | in | 40G 光模块中断 / 在位 |
| `opt_signal_detect` / `opt_tx_fault` / `sfp_mod_abs` | [3:0] | in | 10G 光模块信号监测 / 故障 / 在位 |
| `fpga_fan_fg` | 1 | in | 风扇测速反馈（pps_async_cnt 统计） |
| `gt_40g_ref_clk_n/p` | [1:0] | in | 4×40G 参考时钟 |
| `gt_40g_rx_port_n/p` | [7:0] | in | 40G GT 收（KU060 下第二组 4 lane 给 l_ethernet_1） |
| `gt_10g_ref_clk_n/p` | [0:0] | in | 4×10G 参考时钟 |
| `gt_10g_rx_port_n/p` | [3:0] | in | 10G GT 收 |
| `pcie_ref_clk_clk_p/n` | [1:0] | in | 每通道 PCIe 参考时钟 |
| `pcie_reset_n` | [1:0] | in | 每通道 PCIe 复位 |
| `pcie_7x_mgt_0_rxn/rxp` | [15:0] | in | `CHNL_NUM*8`=16 lane（每卡 x8） |
| `c0_sys_clk_p/n` | [1:0] | in | 每卡 DDR4 时钟（`ifndef GOLDEN` 段） |
| `qsfp_lpmode_f` / `qsfp_modseln_f` / `qsfp_rst_n_f` | [1:0] | out | 40G 模块低功耗/片选(=2'b11)/复位（=`clk_100m_lock`） |
| `sfp_rs0_f`/`sfp_rs1_f` | [3:0] | out | 10G 速率选择（初始 4'hf） |
| `opt_tx_disable` | [3:0] | out | 10G 发关断（=eth_core_rst[7:4]） |
| `fpga_sfp_iic_scl/sda` | [5:0] | out | IIC（初值 0） |
| `fpga_p_act` | [5:0] | out | 活动灯（={eth_led[1:0],eth_led[7:4]}） |
| `gt_40g_tx_port_n/p` | [7:0] | out | 40G GT 发 |
| `gt_10g_tx_port_n/p` | [3:0] | out | 10G GT 发 |
| `pcie_7x_mgt_0_txn/txp` | [15:0] | out | PCIe GT 发 |
| `spi_ext_csn/i/o` | — | out/in/out | 外部 SPI（固件升级 `update` 用；`GOLDEN` 变体不实现 DDR4 端口，故 SPI 为醒目保留） |
| `c0_ddr4_act_n/adr[17]/ba[2]/bg/cke/odt/cs_n/ck_t/ck_c/reset_n` | 每卡 1 组 | out | DDR4 控制（adr 每卡 17b） |
| `c0_ddr4_dm_dbi_n/dqs_c/dqs_t` | [15:0] | inout | 每卡 8 字节 lane |
| `c0_ddr4_dq` | [127:0] | inout | 每卡 64 位 DQ（x16×4） |

`GOLDEN` 宏下 `c0_sys_clk_p/n`、`c0_ddr4_*` 端口整体移除（只留 SPI）——即 golden 板为小封装裸器件。

## 3. generate 体系内幕

顶层的 generate 块及循环边界（括号内为循环次数）：

| generate 块 | 边界 | 内容 |
|---|---|---|
| 域映射块（匿名） | i<2 | `axi_bcam/axi_tcam` 时钟；`s_rx_axis_t*`←`dma_bypass_axi[i]`；`m_tx_axis_t*`→`dma_dn_axi[i]` |
| ETH_REF_CLK_NUM 块 | i<2 | `mem_in[i]` 生成；`reg_axi_b`（AXI-Lite→LBS 桥）每通道一个；`tlv_din[i]` 字节序反转映射 |
| `ETH_CH_GEN` | i<8 | 三分支：i<2 例化 40G `Ingress_chnl`(DW=256)+`Egress_chnl`+`data_led`（数据源 `axis_eth_40g_rx[i]`）；2≤i<4 全部接 0（该两路 40G 总线在数据面弃用）；i≥4 例化 10G 同套（DW=64，数据源 `axis_eth_10g_rx[i-4]`，bypass 用 `r_bypass_en[1][0]`） |
| `ETH_PARSER_GEN` | i<8 | `eth_ul_pkt_parsing` ×8，两分支仅 bypass 位不同（ETH0..3 用 `{r_bypass_en[1][2:1],r_bypass_en[0][1]}`，ETH4..7 用 `{r_bypass_en[1][4:3],r_bypass_en[0][2]}`），DW=256,CHW=0，mem 挂 `mem_out[i/4][i%4+1]` |
| `PROC_GEN` | i<CHNL_NUM(=2) | 整条数据面每通道一套（详见 part 2 §1）；内含二级 `DDR_GEN`（j<2：两片 DDR 的出入 FIFO/调度/sch 全链） |
| `DMA_GEN` | `PCIE_DUAL`?2:1 | `design_bd_wrapper`（PCIe XDMA BD 拓扑）+ `dma_full_bypass` 每通道各一 |
| `GEN_MEM_WITHOUT_UPDATE` / `GEN_MEM_WITH_UPDATE` | `SIM_MODE` 选 1 | 非仿真：`update`(mst@0x83000/slv@0x83800) SPI 级联 + xadc；仿真：`mem_spi_rdy='h3` 并清 [9][10][12][14] |
| `GEN_XADC` | `SIM_MODE==0` | `xadc_capture`（温度 → `xadc_temp` → top_mem_map.s_axi_rdata） |

**PROC_GEN 内部时序理解要点**（top.sv:880-1659）：
1. `w_card_status[i]` 32-bit 只读卡状态字拼接（self_check / clk_100m_lock / ~sys_rst / ~pcie_axi_rst / ~ui_rst / init_calib / eth linkup）。
2. `top_mem_map#(DEV_ID=i, BASE_ADDR=24'h8_0000)` 每通道一套——LBS 0x80000 是**每卡寄存器文件/主译码**，不是会话表槽（综述表把 [6] 也记为 0x08_0000，对照此处：槽 [0]=0x08_0000，槽 [6] 的会话表基址在 `session_t_sch` 内部，待核实）。
3. `eth_rx_pkt_sch` 输入为 `{eth_rx[i*2+5:i*2+4], eth_rx[i]}`——**3 口 → 4 路**以太流并入（i=0 取 {5,4,0}，i=1 取 {7,6,1}；口 2/3 在 ETH_CH_GEN 被清 0，故不进调度），输出 `eth_rx_sch_in[i*4 +: 4]`。
4. `ddr_sesstion_wr_mux` 只在 i==0 例化（`bus_c_sch` 4→1 合并**全部通道**的 `ddr_wr_sch_in`），是双卡会话写汇聚点。

## 4. 时钟域与复位

| 时钟 | 来源 | 用途 |
|---|---|---|
| `clk_100m` | 板级 | `clk_rst_ctrl` 输入（生成内部 clk_200m_in） |
| `clk_100m_in` | clk_rst_ctrl（MMCM 100MHz） | 配置域：reg bus、TLV、hash、update/SFI、axi_bcam/tcam、xadc、各 MAC `s_axi` 口 |
| `sys_clk`(=clk_200m_in) | clk_rst_ctrl（200MHz，qos 注释行自述「200MHz」） | 数据面主时钟：解析/会话/转发/crs_crd/Forward_top/总线调度 |
| `clk_005m_in` | clk_rst_ctrl（5MHz） | LED（data_led clk_led）、pps_async_cnt 统计 |
| `eth_rx_clk[i]`/`eth_tx_clk[i]` | 各 MAC 核（`(*keep="true"*)`；40G 口 0 的 rx 时钟源=tx：`eth_rx_clk[0]=eth_tx_clk[0]`） | Ingress/Egress 核侧 |
| `pcie_axi_aclk[1:0]`/`pcie_axi_rst[1:0]` | `design_bd_wrapper` 输出 | DMA/PCIe AXI 域（crs_crd_numa、sdip_hash_gen、ram_share、Forward_top dma_clk） |
| `ui_clk[CHNL_NUM*2-1:0]`/`ui_rst` | MIG `ddr4_0_dns` c0 输出（仅 `i*2` 被驱动，`i*2+1` **无驱动**，见 part 2 §5） | DDR 写 FIFO 读侧、ddr_ctrl、pps 计数 clkb |
| `clk_010m_in` | **顶层未声明**（top.sv:1832 `design_bd_wrapper .m_dna_clk` 引用） | DNA 时钟，疑为悬空网线/编译隐患 |

复位层次：`sys_rst`（clk_rst_ctrl 内 4bit shift，最大扇出 999）作数据面异步复位；`clk_100m_unlock` 作配置域复位；每口 `eth_rst`（gtwiz）/`eth_mac_rst`（MAC）/`user_rx_reset`/`eth_tx_rst`；DDR 侧 `ui_rst`（MIG）；PCIe 侧 `pcie_axi_rst`。`qsfp_rst_n_f={2{clk_100m_lock}}`、`qsfp_lpmode_f=eth_core_rst[1:0]`、`opt_tx_disable=eth_core_rst[7:4]`。

> 继续：[top-dataflow_part2.md](top-dataflow_part2.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)。