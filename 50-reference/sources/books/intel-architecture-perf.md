---
title: CPU 性能 / Intel 架构手册蒸馏
tags: [reference, sources, intel, x86, performance, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 体量 | 侧重点 |
category: reference
source_dir: Q:\常规书籍\性能
sources: []
base_confidence: 0.6
lifecycle: reviewed
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

- 网卡/交换芯片数据面性能调优（结合 [[50-reference/sources/chips/nic-dpdk]] DPDK 资料）。
- 编写高性能 C/C++ 时回查优化手册。

## 关联

- DPDK / 网卡：[[50-reference/sources/chips/nic-dpdk]]
- 底层机制笔记：[[50-reference/npp-timer-mechanism]]、[[50-reference/dlopen-internal-memory]]

---

## 深度提炼

> 三本 Intel 手册提取文本均落盘于 `Q:\AI\extract_tmp\out\`（英文原版，非扫描）。大手册用 grep 抽样关键主题，未全读百万字符。

### A. Intel® 64 和 IA-32 架构优化参考手册（~2.4M 字符）

**章节地图（20 章，已逐章确认标题）**：
1. Introduction
2. Intel 64 and IA-32 Processor Architectures
3. General Optimization Guidelines
4. Intel Atom® Processor Architectures
5. Coding for SIMD Architectures
6. Optimizing for SIMD Integer Applications
7. Optimizing for SIMD Floating-Point Applications
8. INT8 Deep Learning Inference
9. Optimizing Cache Usage
10. Sub-NUMA Clustering
11. Multicore and Hyper-Threading Technology
12. Intel® Optane™ DC Persistent Memory
13. 64-bit Mode Coding Guidelines
14. SSE4.2 and SIMD Programming for Text Processing/Lexing/Parsing
15. Optimizations for Intel® AVX, FMA and AVX2
16. Intel® TSX Recommendations
17. Power Optimization for Mobile Usages
18. Software Optimization for Intel® AVX-512 Instructions
19. Cryptography & Finite Field Arithmetic Enhancements
20. Knights Landing Microarchitecture and Software Optimization

**关键主题提炼（grep 实证）**：
- **缓存层级与预取**：cache 提及 1640 次、prefetch 649 次。L1/L2/L3（MLC/LLC）层级；支持数据预取到 L1；增强型 data prefetcher 提升访存并行度（Coding for SIMD / Optimizing Cache Usage 章）。
- **流水线 / 执行端口**：pipeline 300 次。执行单元按端口映射（Port 0/1/2...），INT 表示 GPR 标量指令，VEC 表示浮点/整数向量指令；Shuffle 在 Port 1 仅支持同 128-bit 子向量内；iDIV 在 Port 1 降低延迟。
- **SIMD / AVX**：SIMD 808 次、AVX 895 次。覆盖 SSE→AVX/AVX2→AVX-512 的向量化优化；512-bit 向量在 Client 部分不可用（脚注标注）。AVX-512 章含 ZMM、VBMI、超越函数支持。
- **TLB**：TLB 389 次。一级 ITLB 缓存小页/大页翻译（大页按 256KB 粒度缓存）；一级 DTLB（uTLB）大页被拆成 4KB 项；4K 页可用全部 2048 项，2/4MB 页用 1024 项（8 ways）。TLB Miss 在性能分析附录（B/C 附录）单列。
- **分支预测 / 融合**：branch 469 次。Macro-fusion（如 `CMP MEM-IMM, JGE` 抑制，无符号迭代计数兼容）/ Micro-fusion（LEA 两源单操作、三源拆两周期）；分支误预测代价在延迟分析中体现。

### B. Intel® 64 和 IA-32 软件架构程序员手册 卷1 - 基本架构（~1.5M 字符）

**章节地图（15 章，已逐章确认标题）**：
1. About This Manual
2. Intel 64 and IA-32 Architectures
3. Basic Execution Environment
4. Data Types
5. Instruction Set Summary
6. Procedure Calls, Interrupts, and Exceptions
7. Programming with General-Purpose Instructions
8. Programming with the x87 FPU
9. Programming with Intel® MMX™ Technology
10. Programming with Intel® SSE
11. Programming with Intel® SSE2
12. Programming with SSE3, SSSE3, SSE4 and AESNI
13. Managing State Using the XSAVE Feature Set
14. Programming with AVX, FMA and AVX2
15. Programming with Intel® AVX-512

**关键主题提炼（grep 实证）**：
- **基础执行环境**：通用寄存器（general-purpose register 120 次）、段机制（segment 353 次）、控制寄存器（control register 36 次）、内存模型（memory model 44 次）、64-bit mode（300 次）。
- **数据类型与指令集**：x87 FPU（783 次）、MMX（434 次）、SIMD（615 次）覆盖从标量到向量全谱系；XSAVE 特性集管理扩展状态。
- **定位**：与优化手册互补——本卷是"是什么/怎么用"（架构与指令语义），优化手册是"怎么写好"（微架构调优）。

### C. Intel 架构指令集扩展及新特性展望（~549K 字符）

**关键主题提炼（grep 实证）**：
- **Intel® AMX（Advanced Matrix Extensions）**：AMX 120 次，含 "Intel® AMX Instruction Set Reference, A-Z" 与 "AMX Exception Classes"——面向矩阵/深度学习推理的新指令集。
- **向量与深度学习扩展**：SSE 250 次、AVX 51 次、AVX-512 6 次；VNNI（Vector Neural Network Instructions）17 次、BF16（bfloat16）29 次——用于低精度推理。
- **扩展机制**：extension 147 次、instruction set 91 次、ISA 62 次——系统梳理指令集演进路线图与新特性。
- **定位**：指令集路线图/新特性总览，是前两者的"未来方向"补充。

### 与知识库的关联

- 数据面性能调优（DPDK / 网卡）应回查 A 卷缓存/预取/SIMD、B 卷指令语义 → [[50-reference/sources/chips/nic-dpdk]]。
- 底层机制（定时器、动态链接）与 B 卷执行环境、控制寄存器呼应 → [[50-reference/npp-timer-mechanism]]、[[50-reference/dlopen-internal-memory]]。
