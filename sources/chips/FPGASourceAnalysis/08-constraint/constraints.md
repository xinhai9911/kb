# FPGA 约束体系

> 源路径：`constraint/`。工程含两套约束：Vivado（`.xdc`）用于 Xilinx KU060 综合实现；Pango/紫光同创（`.fdc`/`.ucf`/`.txt`）为同板另一工具链版本。二者指向**同一块物理板**但高速 IO 端口命名体系不同（见下文 §4 差异说明）。

## 1. timing.xdc — Vivado 时序约束

### 1.1 主时钟

| 时钟名 | 周期 / 频率 | 来源 | 说明 |
|---|---|---|---|
| `clk_100m` | 10 ns / 100 MHz | `get_ports clk_100m` | 板级参考时钟，AG12 |
| `clk_100m_out` | 衍生 | MMCM3 CLKOUT0 | 配置域 100 MHz |
| `clk_200m_out` | 衍生 | MMCM3 CLKOUT1 | 数据面主时钟 200 MHz（sys_clk） |
| `clk_005m_out` | 衍生 | MMCM3 CLKOUT2 | 5 MHz 以太网健康检测时钟 |
| `gt_40g_ref_clk_p[0/1]` | 6.4 ns / 156.25 MHz | `get_ports` | 2×40G QSFP GT 参考时钟 |
| `gt_10g_ref_clk_p[0]` | 6.4 ns / 156.25 MHz | `get_ports` | 4×10G SFP+ GT 参考时钟 |
| `pcie_ref_clk_clk_p[0/1]` | 10 ns / 100 MHz | `get_ports` | 双 PCIe Gen3 参考时钟 |

注：DDR4 `ui_clk`（MMCM `mmcm_clkout0*`）由 MIG 内部自动生成，timing.xdc 仅约束其与系统时钟的 false path。

### 1.2 跨时钟 false path 矩阵（精简）

```
clk_100m_out  ↔  clk_200m_out    (双向 false path)
clk_100m_out  →  eth_?x_clk*    (单向 false path)
clk_100m_out  →  pcie_axi_aclk_* (单向 false path)
clk_200m_out  →  eth_?x_clk*
eth_rx_clk*   ↔  eth_tx_clk*    (双向)
rxoutclk_out* ↔  txoutclk_out*  (双向，GT SERDES 内部)
clk_005m_out  ↔  (多个)
```

### 1.3 其他

| 约束 | 值 | 说明 |
|---|---|---|
| multicycle sys_rst_pre_reg[3] | setup×2, hold×1 | 复位链打拍多周期松弛 |
| BITSTREAM.GENERAL.COMPRESS | TRUE | 位流压缩使能 |

---

## 2. pin.xdc — Pro 版引脚与多引导配置

### 2.1 多引导（Multiboot）Pro 配置

| 属性 | 值 | 说明 |
|---|---|---|
| `NEXT_CONFIG_ADDR` | `32'h00000000` | 回退地址（Pro 起始地址） |
| `CONFIGFALLBACK` | ENABLE | 配置失败自动回退 |
| `TIMER_CFG` | `32'h1DCD650`（=31,250,000） | 看门狗计时值；`cclk`=3 MHz 时≈10.4 s |
| `CONFIG_VOLTAGE` | 1.8 V | IO 配置电压 |
| `CFGBVS` | GND | 配置 bank 电压感应 |
| `CONFIG_MODE` | SPIx8 | 8-bit SPI flash 配置 |
| `SPI_32BIT_ADDR` | YES | 32-bit SPI 寻址 |
| `SPI_BUSWIDTH` | 8 | SPI 总线宽度 |
| `CONFIGRATE` | 40 | SPI 时钟速率（MHz） |

### 2.2 关键引脚（pin.xdc，Vivado 端口名）

| 端口名 | PACKAGE_PIN | 功能 |
|---|---|---|
| `clk_100m` | AG12 | 板级 100 MHz 参考时钟 |
| `pcie_7x_mgt_0_txp[0..7]` | AC4 AE4 AG4 AH6 AK6 AL4 AM6 AN4 | PCIe 通道 0 TX（第 1 个 PCIe 控制器） |
| `pcie_7x_mgt_0_txp[8..15]` | G4 J4 L4 N4 R4 U4 W4 AA4 | PCIe 通道 1 TX（第 2 个 PCIe 控制器） |
| `pcie_ref_clk_clk_p[0]` | AB6 | PCIe 0 参考时钟 |
| `pcie_ref_clk_clk_p[1]` | P6 | PCIe 1 参考时钟 |
| `pcie_reset_n[0/1]` | K22 / N23 | PCIe 复位（LVCMOS18，PULLUP） |
| `gt_10g_ref_clk_p[0]` | K6 | 10G 参考时钟 |
| `gt_10g_tx_port_p[0..3]` | F6 D6 C4 B6 | 4×10G SFP+ TX |
| `gt_40g_ref_clk_p[0]` | R29 | 40G-0 参考时钟 |
| `gt_40g_tx_port_p[0..3]` | T31 P31 M31 K31 | 40G QSFP-0 TX |
| `gt_40g_ref_clk_p[1]` | L29 | 40G-1 参考时钟 |
| `gt_40g_tx_port_p[4..7]` | H31 G29 D31 B31 | 40G QSFP-1 TX |
| `spi_ext_csn/i/o` | G26 / L20 / M20 | SPI Flash 片选/MISO/MOSI |
| `c0_sys_clk_p[0]` | AJ23 | DDR4 SODIMM-0 时钟 |

---

## 3. pin_golden.xdc — Golden 版多引导配置

与 pin.xdc **引脚完全相同**，只有多引导属性不同：

| 属性 | pin.xdc（Pro） | pin_golden.xdc（Golden） |
|---|---|---|
| `NEXT_CONFIG_ADDR` | `0x00000000` | `0x00F7FE00`（≈ timer1.bin 地址 / 2） |
| `CONFIGFALLBACK` | ENABLE | ENABLE |
| `NEXT_CONFIG_REBOOT` | 不设 | ENABLE（重启后加载下一镜像） |
| `TIMER_CFG` | `0x1DCD650` | 不设（注释掉） |

Golden 镜像的职责：监视 Pro 镜像是否正常配置；若失败，由看门狗引发 fallback 重新从 `0x00F7FE00` 加载 timer1.bin，再启动 Pro。

---

## 4. 两套约束体系的差异

pin.fdc（Pango）与 timing.fdc（Pango）使用**原理图网络名**（flat net），与 Vivado 的**IP 核端口名**系统不同：

| 约束 | 工具 | 命名体系 | PCIe TXP[0] |
|---|---|---|---|
| `pin.xdc` | Vivado | IP 端口名（`pcie_7x_mgt_0_txp[0]`） | AC4 |
| `pin.fdc` / `80G_PG3T500.txt` | Pango / 原理图 | 网络名（`PCIE_L0_TXP`） | R5 |

**关键差异**：Vivado `pin.xdc` 的 `pcie_7x_mgt_0_txp[0]`（=AC4）对应 Pango/UCF 的 `PCIE_L4_TXP`（=AC5 为 TX_P，AC4 为 TX_N 临引脚）。这表明 Vivado 项目中 PCIe Lane 0 起点从原理图第 4 条 Lane（PCIE_L4）开始编号。同理，`txp[0..7]`（AC4~AN4 系列）对应 PCIe 第一控制器（PCIE_L4~L7 + 另 4 条），`txp[8..15]`（G4~AA4 系列）对应第二控制器（PCIE_L0~L3+）。（**待核实**：需对照 Vivado project .xpr 或 IP 配置确认 Lane 映射关系。）

---

## 5. 80G_PG3T500.ucf / .txt — 原理图引脚映射（旧 UCF 格式）

两个文件内容等价，`.txt` 格式同 UCF，仅扩展名不同。以网络名列出板级 LOC，主要信号组：

| 信号组 | 示例网络名 | 备注 |
|---|---|---|
| PCIe TX | `PCIE_L0_TXP`=R5 … `PCIE_L7_TXP`=AF7 | 8 Lane × TXP/TXN |
| PCIe RX | `PCIE_L0_RXP`=P2 … | 8 Lane × RXP/RXN |
| PCIe 参考时钟 | `PCIE_REFCLK_P`=V7 | 单 100 MHz 参考时钟（待核实：双控制器？） |
| 10G SFP | `SFP0_TXP`=F5 … `SFP3_TXP`=D7 | SFP0~3 数据信号 |
| 40G QSFP | 未在 .txt 首50行中出现，`.ucf` 文件中查看 | |
| DDR4 | `DDR4A_A0`=AF22 … | DDR4 地址/数据线 |
| 以太网控制 | `SFP0_MOD_ABS`=J14，`SFP0_RX_LOS`=AA14 | 光模块存在/告警检测 |
| SPI Flash | FPGA_* | SPI 控制信号 |

`PG3T500-FFBG676_V1.1.xlsx`：二进制 Excel 格式，内含 FFBG676 封装全引脚分配表，未在此展开；文件名意为紫光同创 PG3T500 芯片（FFBG676-V1.1 版本）引脚映射。

---

## 6. timing.fdc — Pango 端口 LOC 约束

```tcl
# 格式示例（Pango define_attribute）
define_attribute {p:PCIE_L0_TXP} {PAP_IO_LOC} {R5}
define_attribute {p:SFP0_TXP}    {PAP_IO_LOC} {F5}
```

**注意**：`timing.fdc` 名为 timing 但内容全为引脚 LOC（`PAP_IO_LOC`），**不含任何时序周期/false path 约束**——这是 Pango 工具约束文件命名惯例，与 Vivado 的 timing.xdc 功能不对称。Pango 时序约束在 `.sdc` 文件中（本工程未随附）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
