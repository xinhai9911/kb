---
title: 网卡与 DPDK 资料蒸馏
tags: [reference, sources, nic, dpdk, intel, networking, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料
---

# 网卡与 DPDK 资料蒸馏

> Intel 82599 网卡 datasheet、沐创自研网卡、DPDK 性能报告索引。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 体量 | 内容 |
|---|---|---|
| 82599-datasheet-v3-4.pdf | ~76 MB | Intel 82599 10GbE 控制器 datasheet |
| 沐创网卡用户指南V1.6.pdf | ~3.6 MB | 沐创（MuChuang）网卡用户指南 |
| 沐创自研网卡培训-邱瑶.pptx | ~1.5 MB | 沐创自研网卡内部培训 |
| DPDK 性能报告.txt | 30 B | 性能报告入口（简短） |
| DPDK_16_11_Intel_NIC_performance_report.pdf | ~0.8 MB | DPDK 16.11 Intel 网卡性能 |
| DPDK_17_02_Intel_NIC_performance_report.pdf | ~1.1 MB | DPDK 17.02 Intel 网卡性能 |
| TR-symRSS (1).pdf | ~0.2 MB | 对称 RSS 技术报告 |
| sec22summer_xing.pdf | ~0.7 MB | 安全/Summer 相关论文 |
| atc12-final39.pdf | ~0.2 MB | USENIX ATC 2012 论文 |

## 关键要点

- **82599**：10GbE 控制器，寄存器/描述符环/DMA。
- **DPDK**：用户态轮询、大页、无锁队列，性能基准见年度报告。
- **RSS / symRSS**：接收端缩放与对称哈希（用于双向流一致性）。
- **沐创网卡**：国产自研网卡，替代方案。

## 适用场景

- 数据面性能调优（结合 [[sources/books/intel-architecture-perf]] 微架构优化）。
- 网卡驱动 / DPDK 应用开发时回查 datasheet 与性能报告。

## 关联

- CPU 优化：[[sources/books/intel-architecture-perf]]
- 底层机制：[[50-reference/dlopen-internal-memory]]、[[50-reference/npp-timer-mechanism]]

---

## 深度提炼

> 来源：`82599-datasheet-v3-4.txt`（~2 MB，Intel 82599 10GbE 控制器 datasheet，章节/寄存器完整）、`DPDK_16_11_Intel_NIC_performance_report.txt` 与 `DPDK_17_02_Intel_NIC_performance_report.txt`（Intel NIC 性能报告）、`沐创网卡用户指南V1_6.txt`（国产沐创网卡，35 页）。

### 1) Intel 82599 10GbE 控制器（datasheet 提炼）

- **定位**：PCIe 10 千兆以太网控制器，单/双口；相对前代 82598 的新能力（§1.4）：安全、发送速率限制、FCoE、性能、Rx/Tx 队列与 Rx 过滤、中断、虚拟化、VPD、Double VLAN、IEEE 1588 PTP 时间同步。
- **接口**：PCIe、网络接口、EEPROM、Serial Flash、SMBus、NC-SI、MDIO、I2C、SDP(GPIO)、LED。
- **队列能力**（关键规格）：
  - **接收多队列 + Flow Director**：`16 × 8` 与 `32 × 4` 两种 Rx 队列组合；**128 个发送队列**。
  - **RSS（Receive Side Scaling）**：多接收队列，§7.1.2.8 含 4-bit RSS Type 字段；PSRTYPE[n] 寄存器（0x0EA00+4*n）配置包分类。
  - **Flow Director（FDIR）**：16×8/32×4 过滤表，支持镜像/复制；控制寄存器 §8.2.3.21.1。
  - **SR-IOV**：每端口支持 **64 虚拟机 × 2 队列（64 VMs × 2 queues）**，直通虚拟化。
  - **Descriptor 环**：Tx/Rx 描述符环管理硬件；Legacy / Advanced 描述符格式（§7.1.5 Legacy Receive Descriptor Format，VP 位标记 VLAN 且 RXDCTL.VME 置位时 VLAN 已被剥离入描述符）；RXDCTL[n] 描述符控制、DCB 用 Advanced Tx 描述符（T2）。
  - 每端口可编程内存 Tx 缓冲 **160 KB**；支持包分割接收（Packet Split / 头复制）、收/发 pause 帧流控。
- **MAC 功能**：Descriptor ring 管理、延迟/减少 Tx 中断机制、IPv4/IPv6 TCP·UDP 接收校验和卸载、Alternate MAC Address（§6.2.10/6.2.11）。
- **寄存器/开发**：8.2.3 节为各功能寄存器详述（MAC Core Control 0 默认 MDCSPD、Flow Director Filters Control 等）；适合驱动开发时按功能定位寄存器基址+偏移。

### 2) DPDK Intel NIC 性能报告（16.11 / 17.02）

- **测试平台**：Intel® Xeon® E5-2699 v4（55M Cache, 2.20 GHz）/ E5-2699 v3（45M Cache, 2.30 GHz）；流量仪 **IXIA** 跑 **RFC2544 零丢包**测试。
- **网卡型号**：Intel Ethernet Converged Network Adapter **X710-DA4（4×10G）**、**XL710-QDA2（2×40G）**（Fortville 系列）；测试覆盖 82599/X710/XL710 等。
- **测试 App**：
  - **l3fwd**：用 DPDK hash/LPM 库做 IPv4 转发（LPM 默认，查找键=目的 IP；hash 模式支持 IPv4/IPv6），静态 LPM 规则表模拟路由下一跳。编译示例：`Build L3fwd: (in l3fwd/main.c)`；运行 `./l3fwd -c 0x7800000 -n 4 -w 81:00.0 ... -- -p 0x3 --config ...`。
  - **testpmd**：转发模式 + 访问 NIC 硬件特性；`-i` 时首核用于 CLI；示例 `./testpmd -c 0x180000 -n 4 -- -i --txqflags=0xf01 --txd=128`。
- **用例**：Test Case 1–3（16.11）/ 4–5（17.02）为 RFC2544 零丢包、单核性能（Single core max IO throughput）；结果以 **Throughput(Mpps)** 与 **CPU_freq/Throughput** 报告（X710-DA4 / XL710-QDA2 分表给出）。
- **价值**：提供可复现基线配置（BIOS/DPDK build/命令），供在 Intel 架构上评估与优化 DPDK 方案参考。

### 3) 沐创（MuChuang / mucse）国产网卡

- **产品系列**（§4 规格）：**N10 系列**（N10G-X2-DC / X4-QC / X2-DCP / X4-QCP / 八口）、**N400L 系列**（N400L-X4-QD / X4F-SC）、**N500L 系列**（N500L-AM2C-DD / AM4C-QD / AM4C-QDP）。覆盖 10G/25G/100G 等多速率。
- **适配**：CPU 适配列表、OS 适配列表、BIOS/BMC 适配、DPDK 软件适配、兼容光模块、驱动固件版本兼容矩阵（§3）。
- **驱动**：Linux 内核驱动 `rnp` / `rnpvf` / `rnpm` / `rnpgbe` / `rnpgbevf`（PF/VF 与不同 MAC）；支持 rpm/dkms 动态编译、kconfig 内核安装；Windows 下 N500 驱动 + 配置 IP。
- **DPDK 适配（§7.2）**：解压源码 → **打入沐创网卡驱动补丁包** → 编译 DPDK 目标环境 → 运行 `testpmd` 验证。
- **固件**：在线升级网卡固件 / PXE 固件、离线烧录 flash 镜像；FAQ 涉及 lspci 只见 2 个 PCIe bus ID、多口命名、多卡 MAC 相同、msi-x 中断资源不足（裁剪 OS）、N10/N400/N500 固件部署方式等。
- **自研实践（绿盟《沐创自研网卡培训-邱瑶.pptx》）**：
  - 背景：**降成本保供应**，应对 Intel 芯片断货/随时断供风险，适配国产与自研芯片（芯片设计由绿盟硬件工程师李华峰完成）。
  - 适配型号：**N10L-X8**；设计涵盖项目背景 / 网卡设计 / 网卡适配三阶段。
  - **一拖四虚拟化**：基于 **SR-IOV**——PF 为一套独立硬件资源，由 4 个端口共享。
  - 与 [[sources/chips/hardware-design-nsf]] 的 NSF1N10TG 硬件设计报告互为印证（同一 N10 平台的产品化落地）。

### 4) 调优/开发要点串联

- 82599 的 RSS/FDIR/多队列/SR-IOV 是 DPDK `testpmd`/`l3fwd` 发挥多核转发的基础；NFV 场景用 SR-IOV 64VM×2Q 做 VM 直通。
- 性能报告表明：单核 Mpps 受限于收发包队列与 PCIe 带宽，需在 BIOS（NUMA/CPU 亲和，见 [[sources/chips/amd-epyc]]）与 DPDK 参数（`--txd`、`-c` core mask、`--config` 队列映射）协同。
- 国产替代路径：沐创 N 系列 + `rnp`/`rnpgbe` 驱动 + DPDK 补丁，可作为 Intel 82599/X710 的国产替代选型。

### 双链

- NUMA/CPU 亲和（DPDK 部署）：[[sources/chips/amd-epyc]]
- 微架构/性能计数器优化：[[sources/books/intel-architecture-perf]]
