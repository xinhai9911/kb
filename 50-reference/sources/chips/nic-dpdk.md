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
