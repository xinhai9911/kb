# 寄存器适配与整卡映射（common/fifo-primitives）– part2

> 承接 [part1](fifo-primitives_part1.md)（FIFO/dff/DDR 请求-响应编址）。本页覆盖 rtl/common/ 的 `reg_axi_b`（AXI 寄存器适配）与 `top_mem_map`（整卡 LBS 寄存器映射），是「寄存器面」两个核心件。

## 1. reg_axi_b —— AXI-Lite 写分发 / 读直通适配

功能：把**单个** CPU AXI-Lite 主（`reg_axi_*`）按地址档分发成 CHNL_ETH_NUM 路 `axi_eth_*` 以太网核寄存器写口；读通道直接映射到 `mem_out`（LBS 读回）。`clk=clk_100m_in`、`rst=clk_100m_unlock`（top.sv `inst_reg_axi_b`，CHNL_ETH_NUM 参数）。

| 通道 | 握手规则 |
|---|---|
| AW/W | `awready/wready` 仅当 `~bvalid & awvalid & wvalid & mem_spi_rdy` 时置 1（**单笔突出的 write 事务**，且要 SPI 总线空闲）；握手后退 0 |
| B | `reg_axi_bvalid` 在 `wvalid&wready` 置 1、`bready&bvalid` 清 0 |
| R | `reg_axi_rvalid` 在 `arvalid` 置 1、`rready&rvalid` 清 0；`rdata` 来自 `mem_out.rd_data`（top_mem_map 译码） |

**地址改写表**（`generate ETH_AXI_GEN`，供 4 个以太网口）：
| 主机地址 reg_axi_awaddr[23:0] | axi_eth_awaddr | 寄存器含义 | 数据变换 |
|---|---|---|---|
| 0x8001c | 0x8 | loopback | `{reg_axi_wdata[i],1'b1,30'h3}` |
| 0x80020 | 0x4 | serdes reset | `{2'h0,~reg_axi_wdata[i],27'h0,~{2{wdata[i]}}}`（支持 10G&40G） |
| 0x80030 | 0xc | ipg | `32'h3` |
| 其余 | 0xc（默认） | — | `32'h3` |

- `axi_eth_wvalid = axi_eth_awvalid`（aw 握手即写）；每次主机 AW 触发更新 addr/wdata 译码。
- 陷阱：`reg_axi_bvalid` 无复位寄存（首拍为 x→0），若仿真不吃 `+initreg` 需留意。

## 2. top_mem_map —— 整卡 LBS 寄存器映射（BASE 0x08_0000，每 DEV_ID 一份）

地址窗口：`{mem_in.address[23:2],2'd0}` 译码（BASE_ADDR=24'h08_0000）。读写均点地址；读**两级打拍**（`rd_vld_pre→mem_out.rd_vld`、`rd_data_pre→mem_out.rd_data`）。属"请求-响应编址"寄存器侧：`mem_in.wr_vld` 写、`mem_in.rd_req` 读。

| 区段 | 寄存器 | 简要 |
|---|---|---|
| 0x00~0x0c | NIC_DATE/TIME/REV/VER | 编译日期时间/版本，`DEF_NIC_*` 宏 + DEV_ID 加剂 |
| 0x10~0x30 | TABLE_CLEAR / BYPASS_EN / ETH_PORT_MAP / ETH_LOOPBACK / CORE_RST / CORE_RX_EN | 表清、旁路位、端口映射、核复位（`~wr_data[3:0]`）等 |
| 0x28/0x2c | CARD_STATUS / ST_TIMEOUT | 卡状态回读（含 eth link/自检位）、老化超时 |
| 0x34~0x3c | DDR_RD_DB2/1/0 | 三个 pps 计数回读（DDR 请求/响应/风扇） |
| 0x40~0x9c | DDR_DB_WR_A0~A3 + D0~D15 + DDR_DB_RD_A0 + RD_D0~D15 | **DDR 调试读写窗口**：写 512b×4 地址接 `ddr_db_wr`（`{addr[28:3],3'h0}` 打包）、`ddr_db_wr.vld` 时数据锁 `ddr_db_wdata_512b`；读经 `ddr_db_rd_req`（addr bit[28]=DDR 类型、bit0 供 rd_res_demux 分发）→ db_rd_req_fifo |
| 0xe0~0xec | WATCH_DOG_NUM/CNT/CLR/EN | 软件看门狗：`sp` 每 1e8 拍秒脉冲，cnt 到 NUM 时 `r_bypass_en` 兜底置 1（旁路自启） |
| 0xf0~0xfc, 0x124~0x12c | DDR_CFG_CNT0~6 | DDR 配置计数 |
| 0x100~0x11c | LOCAL_ID_NUM / LINK_STATUS_L/H / HASH_SIP/DIP/RES/PORT/D | 卡号、链路开关表、sdip_hash_gen 调试读数 |
| 0x120 / 0x130 / 0x154 | XADC_TEMP / DMA_FULL_BYPASS / DMA_FULL_DROP_CNT | 温度（xadc_capture）、DMA 满旁路开关/丢包计数 |
| 0x180 / 0x1b0~0x1b4 | POSITION_MATCH / BUS_CHECK / PCIE_CHANNEL(0x1f0) / PORT_CFG_RAM_WR/RD | 协议匹配计数、总线检查（即 `eth_pkt_ctrl` 源）、PCIe 通道 ID、RSS 端口配置 RAM |
| 0x1b0/0x1b4 | PORT_CFG_RAM_WR/RD | RSS 端口配置 RAM（ram_tdp 双口，写 clk、读 clk_sys），`port_cfg` 出 |

- 旁路默认值：`r_bypass_en` 上电 0x61；看门狗溢出强制置 bit0=1（整链旁路兜底）。
- 读缺省 `rd_data_pre='h0`；未列出地址读 0。
- 与 reg_axi_b 的分工：reg_axi_b 管 ETH 核直接写口（0x8001c..），top_mem_map 管 LBS 主窗口；二者经 `mem_in/mem_out`（`MEM#(32)` 虚类）与 `&mem_spi_rdy` 串行化。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)