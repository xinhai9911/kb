---
title: CPU 性能 / Intel 架构手册蒸馏
tags: [reference, sources, intel, x86, performance, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\常规书籍\性能
---

# CPU 性能 / Intel 架构手册蒸馏

> Intel 64/IA-32 架构优化与指令集参考资料，位于 `Q:\常规书籍\性能\`。

## 书目清单（原文路径 `Q:\常规书籍\性能\`）

| 文件名 | 体量 | 侧重点 |
|---|---|---|
| Intel64及IA32架构优化参考手册.pdf | ~11 MB | 微架构优化、流水线、cache、SIMD |
| Intel64及IA32软件架构程序员手册卷1 - 基本架构.pdf | ~3 MB | 寄存器、内存模型、基础指令 |
| Intel架构指令集扩展及新特性展望.pdf | ~8 MB | AVX/SSE、新特性路线图 |

## 关键要点

- **微架构**：超标量、乱序执行、分支预测、cache 层级。
- **向量化**：SSE/AVX 指令集与优化。
- **性能调优**：与 [[50-reference/npp-timer-mechanism]]、[[50-reference/dlopen-internal-memory]] 中的底层机制互补。

## 适用场景

- 网卡/交换芯片数据面性能调优（结合 [[sources/chips/nic-dpdk]] DPDK 资料）。
- 编写高性能 C/C++ 时回查优化手册。

## 关联

- DPDK / 网卡：[[sources/chips/nic-dpdk]]
- 底层机制笔记：[[50-reference/npp-timer-mechanism]]、[[50-reference/dlopen-internal-memory]]
