---
title: 网卡与 DPDK 资料蒸馏
tags: [reference, sources, nic, dpdk, intel, networking, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 体量 | 内容 |
category: reference
source_dir: Q:\芯片资料
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# 网卡与 DPDK 资料蒸馏

> Intel 82599 10GbE 控制器 datasheet、沐创自研网卡、DPDK 性能报告、对称 RSS 论文的逐字段技术提炼。

## 文件清单（原文路径 `Q:\芯片资料\`）

| 文件名 | 体量 | 内容 |
|---|---|---|
| 82599-datasheet-v3-4.pdf | ~76 MB | Intel 82599 10GbE 控制器 datasheet |
| 沐创网卡用户指南V1.6.pdf | ~3.6 MB | 沐创（MuChuang）网卡用户指南 |
| DPDK_16_11 / 17_02_Intel_NIC_performance_report | PDF | Intel NIC 性能报告 |
| TR-symRSS (1).pdf | ~0.2 MB | 对称 RSS 技术报告（KAIST，见 §5） |
| atc12-final39.pdf / sec22summer_xing.pdf | — | 学术论文，已并入 [[chips-papers-misc]] |

---

## 深度提炼

### 1) Intel 82599 10GbE 控制器架构

**定位**：PCIe 2.0 ×8 的 10 千兆以太网控制器，单/双口。相对前代 82598 新增能力（§1.4）：安全、发送速率限制、FCoE、Rx/Tx 队列与 Rx 过滤增强、中断、虚拟化、VPD、Double VLAN、IEEE 1588 PTP 时间同步。

**整体架构层次**：
- 主机接口：PCIe（含 SR-IOV/ARI 能力），通过 DMA 引擎在主机内存描述符环与 MAC 之间搬运。
- 网络接口：SerDes + PHY，支持 MDIO/I2C 管理；外设侧含 EEPROM、Serial Flash、SMBus、NC-SI、SDP(GPIO)、LED。
- MAC 核心：Descriptor ring 管理、校验和卸载、包分割接收（Packet Split / 头复制）、收/发 pause 流控。

**队列与多队列能力**（关键规格）：
- **接收多队列 + Flow Director**：`16 × 8` 与 `32 × 4` 两种 Rx 队列组合；**128 个发送队列**。
- **RSS（Receive Side Scaling）**：多接收队列按哈希分流，§7.1.2.8 含 4-bit RSS Type 字段；配置寄存器
  - `PSRTYPE[n]`（0x0EA00 + 4*n）：Packet Split Receive Type，配置包分类。
  - `MRQC`（Multiple Receive Queues Command）：选择 RSS / DCB / 二者组合。
  - `RSSRK`（RSS Random Key，40 字节 = 10×32bit）：Toeplitz 哈希密钥（40 字节 = 10 个 32-bit 字）。
  - `RETA`（RSS Redirection Table，128 项 × 4 bit）：哈希值 → 队列号的重定向表。
- **Flow Director（FDIR）**：filter 表规模 **up to 32K−2 flows**（hash 模式）或 **8K perfect filters**；支持镜像/复制；相关寄存器 §8.2.3.21：
  - `FDIRCTRL`（Flow Director Filters Control，0x0EE00）：全局使能。
  - `FDIRCMD`（0x0EE2C）：增删 filter 命令触发。
  - `FDIRVLAN`（0x0EE28）、`FDIRH`（hash 表）、`FDIRS`（sig 表）、`FDIRFREE`/`FDIRLEN`。
- **SR-IOV**：每端口支持 **64 虚拟机 × 2 队列（64 VMs × 2 queues）**，配合 ARI（Alternate RID Interpretation）突破 8 个 function 限制。PF 暴露 VF 给 VM 直通。
- **Descriptor 环**：Tx/Rx 描述符环由硬件管理；Legacy / Advanced 描述符格式。
  - 接收：Legacy Receive Descriptor（§7.1.5），当 `RXDCTL[n].VME` 置位且描述符 VP 位有效时 VLAN 已被剥离入描述符。
  - 发送：DCB 用 Advanced Tx 描述符（T2 格式）。
  - `RXDCTL[n]` / `TXDCTL[n]`：描述符环控制（使能、描述符阈值）；`RDLEN`/`TDLEN` 设置环长度。
- 每端口可编程内存 Tx 缓冲 **160 KB**（`RXPBSIZE`/`TXPBSIZE`）；支持包分割接收（头复制）。

**MAC 卸载**：IPv4/IPv6 TCP·UDP 接收校验和卸载；Alternate MAC Address（§6.2.10/6.2.11）；延迟/减少 Tx 中断机制。

**驱动开发要点**：8.2.3 节按功能给出寄存器基址+偏移（MAC Core Control 0 默认 `MDCSPD`、Flow Director Filters Control 等），可按功能定位。

### 2) DPDK PMD（Poll Mode Driver）模型

DPDK 在用户态轮询网卡，绕过内核协议栈，依赖大页（hugepage）+ 无锁环（ring）+ 多核亲和实现高吞吐。

- **mbuf**：报文缓存结构 `struct rte_mbuf`，承载报文元数据与数据指针；通常从 mempool 中批量分配。
- **ring**：无锁无等待环形队列 `rte_ring`，连接收/发路径与各核，单生产者/单消费者场景零锁。
- **rx/tx burst**：PMD 的核心 API，一次批量收/发，摊薄每次操作开销：

```c
uint16_t rte_eth_rx_burst(uint16_t port_id, uint16_t queue_id,
                          struct rte_mbuf **rx_pkts, const uint16_t nb_pkts);
uint16_t rte_eth_tx_burst(uint16_t port_id, uint16_t queue_id,
                          struct rte_mbuf **tx_pkts, uint16_t nb_pkts);
```

典型主循环：

```c
while (!stop) {
    n = rte_eth_rx_burst(port, qid, pkts, BURST);
    if (n == 0) continue;
    process(pkts, n);
    rte_eth_tx_burst(port, qid, pkts, n);
}
```

### 3) DPDK Intel NIC 性能报告（16.11 / 17.02）

- **测试平台**：Intel® Xeon® E5-2699 v4（55M Cache, 2.20 GHz）/ E5-2699 v3（45M Cache, 2.30 GHz）；流量仪 **IXIA** 跑 **RFC2544 零丢包**测试。
- **网卡型号**：**X710-DA4（4×10G）**、**XL710-QDA2（2×40G）**（Fortville 系列）；亦覆盖 82599。
- **测试 App**：
  - **l3fwd**：用 DPDK `hash`/`LPM` 库做 IPv4 转发（默认 LPM，查找键=目的 IP；hash 模式支持 IPv4/IPv6）。
  - **testpmd**：转发模式 + 访问 NIC 硬件特性；`-i` 时首核用于 CLI。
- **可复现基线命令**：

```bash
# BIOS 内核参数：1G 大页 + CPU 隔离
default_hugepagesz=1G hugepagesz=1G hugepages=16 hugepagesz=2M \
hugepages=2048 isolcpus=1-11,22-33 nohz_full=1-11,22-33 rcu_nocbs=1-11,22-33

# l3fwd：4 端口×各自核，--config (port,queue,core)
./l3fwd -c 0x7800000 -n 4 -w 81:00.0 -w 81:00.1 -w 81:00.2 -w 81:00.3 \
  -- -p 0xf --config '(0,0,23),(1,0,24),(2,0,25),(3,0,26)'

# testpmd：txqflags / txd 等性能旋钮
./testpmd -c 0x180000 -n 4 -- -i --txqflags=0xf01 --txrst=32 --txfreet=32 --txd=128
Testpmd>start
```

- 结果以 **Throughput(Mpps)** 与 **CPU_freq/Throughput** 报告（X710-DA4 / XL710-QDA2 分表）。

### 4) 性能调优旋钮（含取值）

| 旋钮 | 含义 / 取值 | 影响 |
|---|---|---|
| 描述符环大小 `--txd` / `--rxd` | 报告用 `txd=128`；生产常 512/1024/4096 | 环越大容忍突发与时延抖动，但占内存 |
| Burst 大小 | `rte_eth_rx_burst` 的 nb_pkts，典型 32/64 | 批量摊薄单次调用开销 |
| `--txqflags=0xf01` | 关闭部分 offload 以省 CPU | 提升纯转发 Mpps |
| `--txfreet` / `--txrst` | 报告取 `32` | 提前回收/重置描述符阈值 |
| Hugepage | `1G ×16` 或 `2M ×2048` | 减少 TLB miss，避免换页 |
| NUMA / 亲和 | `isolcpus`、`-c` core mask、`--config` 队列→核映射 | 收发包队列与核同 NUMA，避免跨 Node 访问 |
| BIOS | 关闭节能、开启 VT-d/SR-IOV | 直通虚拟化与稳定时延 |

### 5) 对称 RSS（symRSS，KAIST TR-symRSS）

- **问题**：标准 RSS 按五元组（src/dst IP、src/dst port、protocol）哈希，但**同一 TCP 连接的正反向哈希值不同**，导致双向包落到不同队列，有状态设备（防火墙、IDS、WAN 加速）需跨核锁共享状态，抵消 RSS 收益。
- **方案**：仅修改 RSS **密钥（RSSRK / Toeplitz seed）**，使得反向包的哈希与正向相同；**不改哈希算法本身**，硬件照常算哈希，零额外 CPU。
- **代价**：会轻微损害多核间的负载均衡；论文给出理论分析与实验验证。对需要同一连接双向同核处理的系统极有价值。

### 6) 沐创（MuChuang / mucse）国产网卡

- **产品系列**：**N10 系列**（N10G-X2-DC / X4-QC / X2-DCP / X4-QCP / 八口）、**N400L 系列**（N400L-X4-QD / X4F-SC）、**N500L 系列**（N500L-AM2C-DD / AM4C-QD / AM4C-QDP），覆盖 10G/25G/100G。
- **适配广度**（§3）：
  - CPU：x86（Intel/AMD/海光 3·5·7 系/兆芯）、ARM（鲲鹏/飞腾）、龙芯、申威、PowerPC。
  - OS：CentOS/RHEL 6.6–8.6、Ubuntu、Anolis、Kylin V4/V10、UOS V20、OpenCloudOS 8、OpenEuler、凝思、翼辉、Windows、VxWorks 等（多系统已合入驱动免安装）。
  - BIOS/BMC：昆仑、百敖、飞腾、长城、龙芯 PMON、申威 BIOS、AMI。
  - DPDK：2.1.0 → 23.07 全版本适配。光模块：10G SFP+ SR/LR、10G/1G 自适应、光转电。
- **驱动**：Linux 内核 `rnp`/`rnpvf`（N10 两口 & N400 单口）、`rnpm`（N10 四/八口 & N400 四口）、`rnpgbe`/`rnpgbevf`（N500）；DPDK 驱动 `tsrn10`/`rnpgbe`（N10/N400/N500）。支持 rpm/dkms、kconfig 内核安装；Windows 下 N500 驱动 + 配置 IP。
- **DPDK 适配（§7.2）**：解压源码 → **打入沐创网卡驱动补丁包** → 编译 DPDK 目标环境 → 运行 `testpmd` 验证。
- **FAQ**：lspci 只见 2 个 PCIe bus ID、多口命名、多卡 MAC 相同、msi-x 中断资源不足（裁剪 OS）、N10/N400/N500 固件部署。

### 7) 调优/开发要点串联

- 82599 的 RSS/FDIR/多队列/SR-IOV 是 `testpmd`/`l3fwd` 多核转发的基础；NFV 用 SR-IOV 64VM×2Q 直通。
- 单核 Mpps 受收发包队列与 PCIe 带宽限制，需在 BIOS（NUMA/亲和）与 DPDK 参数（`--txd`、`-c`、`--config`）协同。
- 国产替代路径：沐创 N 系列 + `rnp`/`rnpgbe` 驱动 + DPDK 补丁，可作为 Intel 82599/X710 的国产替代选型；symRSS 思路可直接用于其 RSS 配置以满足有状态设备需求。

### 双链

- NUMA/CPU 亲和：[[50-reference/sources/chips/amd-epyc]]
- 微架构/性能计数器优化：[[50-reference/sources/books/intel-architecture-perf]]
- 同一 N10 平台产品化：[[50-reference/sources/chips/hardware-design-nsf]]
