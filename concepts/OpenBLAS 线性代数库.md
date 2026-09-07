---
title: OpenBLAS 线性代数库
category: concepts
tags: [openblas, blas, lapack, gemm, performance, opensource, arm, x86, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    OpenBLAS 是开源的高性能 BLAS（含部分 LAPACK）实现，fork 自 GotoBLAS2，
    针对 x86/ARM/Power/RISC-V 等架构手调 GEMM 内核，是 NumPy/SciPy 与无 MKL 时
    PyTorch 等框架的默认 CPU 线性代数后端。
base_confidence: 0.85
lifecycle: draft
---

# OpenBLAS 线性代数库

> 前置 [[concepts/oneMKL 数学核心库]]（商用对照）、[[concepts/CPU 指令集加速]]（SIMD 内核）、
> [[concepts/oneDNN 深度学习性能库]]（ML 框架底层 GEMM）。

## 1. 是什么

- **定位**：开源 BLAS（Basic Linear Algebra Subprograms）实现，提供 Level 1/2/3 与常用 LAPACK 例程。
- **起源**：Zhang Xianyi 于 2011 从 **GotoBLAS2**（K. Goto 的手调 GEMM）fork 后持续维护，BSD 许可。
- **角色**：在缺少 Intel MKL 的环境里，是事实上的默认 CPU BLAS 后端。

## 2. 架构支持与内核

| 架构 | SIMD | 备注 |
|------|------|------|
| x86-64 | SSE / AVX / AVX2 / AVX-512 | 多代微架构分内核 |
| ARM / ARM64 | NEON / SVE | 树莓派、麒麟、鲲鹏等 |
| POWER | VSX | IBM |
| RISC-V | RVV（部分） | 新兴 |
| LoongArch / SW64 | 厂商向量扩展 | 国产 |

- **GEMM 为核心**：手调 packing + 微内核（register block），按 `DGEMM/ZGEMM` 等分架构实现；其余 Level 3 多基于 GEMM 构建。
- **运行时 CPU 探测**：启动检测 `cpuid` 选择最优内核，无需重新编译即可适配。

## 3. 线程与集成

- 并行：OpenMP 或 pthreads（构建时选）；用 `OMP_NUM_THREADS` / `OPENBLAS_NUM_THREADS` 控制线程数。
- 上层集成：
  - **NumPy / SciPy**：`numpy.show_config()` 常显示 OpenBLAS。
  - **PyTorch CPU**：无 MKL 时以 OpenBLAS 作 BLAS 后端。
  - **R / Julia / 多数科学栈**：默认或可选后端。

```bash
# 查看/限制 OpenBLAS 线程
export OPENBLAS_NUM_THREADS=8
# NumPy 后端自检
python -c "import numpy; numpy.show_config()"
```

## 4. 与 oneMKL / oneDNN 对照

| 维度 | OpenBLAS | oneMKL | oneDNN |
|------|----------|--------|--------|
| 范围 | BLAS + 部分 LAPACK | BLAS/LAPACK/FFT/统计 | DL 算子原语 |
| 许可 | BSD | Apache 2.0 | Apache 2.0 |
| 新指令 | 跟进较慢 | 紧跟 Intel（AMX 等） | 紧跟 Intel |
| 国产/ARM | 支持好 | 限 Intel | 有 Arm 后端(ACL) |

## 参考来源

- [[concepts/oneMKL 数学核心库]]
- [[concepts/oneDNN 深度学习性能库]]
- [[concepts/CPU 指令集加速]]
- OpenBLAS GitHub（https://github.com/OpenMathLib/OpenBLAS）
- GotoBLAS / Goto 论文（Anatomy of High-Performance Matrix Multiplication）
