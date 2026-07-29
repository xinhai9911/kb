---
title: AMD EPYC 处理器资料蒸馏
tags: [reference, sources, amd, epyc, cpu, numa, hpc, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料\AMD
---

# AMD EPYC 处理器资料蒸馏

> AMD EPYC 霄龙服务器处理器 NUMA 与 HPC 调优资料，位于 `Q:\芯片资料\AMD\`。

## 文件清单（原文路径 `Q:\芯片资料\AMD\`）

| 文件名 | 体量 | 内容 |
|---|---|---|
| AMD EPYC 霄龙  NUMA 配置设置.pdf | ~0.6 MB | NUMA 节点配置与亲和性 |
| AMD EPYCTM 7002 系列处理器的高性能计算 (HPC) 调整指南.pdf | ~4.9 MB | 7002 系列 HPC 调优（BIOS/OS/编译器） |

## 关键要点

- **NUMA**：多 Die/CCD 拓扑，内存就近访问与亲和性绑定。
- **HPC 调优**：BIOS（NUMA/SMT/CMB）、OS 内核参数、编译器选项、MPI 绑定。

## 适用场景

- 在 AMD 服务器上部署 DPDK / 交换控制面时做 NUMA 亲和性规划（结合 [[sources/chips/nic-dpdk]]）。
- 性能基线建立时回查 HPC 调优指南。

## 关联

- 网卡 / DPDK：[[sources/chips/nic-dpdk]]
- 微架构优化：[[sources/books/intel-architecture-perf]]
