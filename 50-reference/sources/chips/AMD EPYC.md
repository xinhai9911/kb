---
aliases: ["amd-epyc"]
title: AMD EPYC 处理器资料蒸馏
tags: [reference, sources, amd, epyc, cpu, numa, hpc, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 体量 | 内容 |
category: reference
source_dir: Q:\芯片资料\AMD
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# AMD EPYC 处理器资料蒸馏

> AMD EPYC 霄龙服务器处理器 NUMA 与 HPC 调优资料，位于 `Q:\芯片资料\AMD\`。

## 文件清单（原文路径 `Q:\芯片资料\AMD\`）

| 文件名 | 体量 | 内容 |
|---|---|---|
| AMD EPYC 霄龙  NUMA 配置设置.pdf | ~0.6 MB | NUMA 节点配置与亲和性（NPS 设置说明） |
| AMD EPYCTM 7002 系列处理器的高性能计算 (HPC) 调整指南.pdf | ~4.9 MB | 7002 系列 HPC 调优（BIOS/OS/编译器） |

## 关键要点

- **NUMA**：多 Die/CCD 拓扑，内存就近访问与亲和性绑定（NPS0/1/2/4）。
- **HPC 调优**：BIOS（NUMA/SMT/C-states/Boost/cTDP）、OS 内核参数、编译器选项、MPI 绑定。

## 适用场景

- 在 AMD 服务器上部署 DPDK / 交换控制面时做 NUMA 亲和性规划（结合 [[50-reference/sources/chips/NIC DPDK]]）。
- 性能基线建立时回查 HPC 调优指南。

## 关联

- 网卡 / DPDK：[[50-reference/sources/chips/NIC DPDK]]
- 微架构优化：[[50-reference/sources/books/Intel 架构 性能]]

---

## 深度提炼

> 来源：`AMD_EPYCTM_7002_系列处理器的高性能计算__HPC__调整指南.txt`（~48 KB，英文正文，9 章）、`AMD_EPYC_霄龙__NUMA_配置设置.txt`（~3 KB）。7002 系列即 Rome，基于 Zen 2（7nm）。

### 1) 微架构与封装（物理拓扑）

- **多芯片模块（MCM）**：单插槽 = 中央 **I/O Die（IOD）** + 最多 **8 个 CCD**（Compute Complex Die）；每个 CCD 含 **2 个 CCX**，每 CCX = **4 核 + 共享 16MB L3**。即每 CCD 最多 8 核 / 32MB L3。
- **Infinity Fabric（DF）**：连接各 CCD 与 IOD，最高 **1467 MHz（FCLK）**；提供跨组件及双路 CPU 间一致内存访问。
- **内存**：每插槽 **8 通道 DDR4**，每通道 ≤2 DIMM，最高 **DDR4-3200 / 4TB**；统一内存控制器（UMC）频率 ≤1600MHz。
- **I/O**：每插槽最多 **128 条 PCIe Gen4** 挂在单一 IOD 上，可抽象为 **4 个逻辑象限**（每象限 2 内存通道 + 32 I/O 通道），内存可在象限内 2 路交错到 16 路（双路全交错）。
- **Zen 2 核**：512KB 私有 L2；支持 **SMT**（每核 2 线程）。
- **关键规格**：Max 64 核 / 3200MHz 内存 / 128 lane PCIe Gen4。7742 基频 2.25GHz(P0)、Boost 3.4GHz。

### 2) NUMA 与 NPS 配置（核心调优点）

Rome 用 NUMA 内存交错，BIOS 设 **NPS（Nodes Per Socket）= 0/1/2/4**，另有 **L3CAN（L3 Cache As NUMA）**：

| NPS 值 | NUMA 域数 | 内存交错通道 | 说明 |
|---|---|---|---|
| NPS0 | 跨双路 1 域 | 全部 16 通道 | **HPC 不推荐**，跨插槽延迟大 |
| NPS1 | 每插槽 1 域 | 8 通道全交错 | 大多数用例默认推荐 |
| NPS2 | 每插槽 2 域 | 每域 4 通道 | 高并行 HPC 可用 |
| NPS4 | 每象限 1 域 | 每域 2 通道 | 高度并行 HPC 最佳；PCIe 按根象限归属域 |

- **约束**：6 个 CCD 的 SKU 不支持 NPS4，仅 NPS1/2。
- **L3CAN**：每 L3 作为独立 NUMA 节点，双路最多暴露 32 个 NUMA 域。
- **查看拓扑**：`hwloc-ls` / `hwloc-info` / `numactl -H`；SMT=ON 时 CPU ID 0–127 为线程 0、128–255 为线程 1（core-0 关联 CPU 0 与 128）。
- **工作负载推荐**：随机访存型 HPC（如 HPL）NPS1/NPS2 与 NPS4 峰值相近；规则流（NAMD STMV）NPS4 + 每 L3 4 核 + Boost=ON + SMT=ON 最佳。

### 3) 电源状态与 BIOS 调优（含具体值）

- **C-State**：C0 活跃 / C1 空闲 / C2 更深睡眠+电源门控。禁用 C2 对低延迟网络（Infiniband）关键——C2→C0 恢复延迟增大网络 IO 延迟；且 SMT 配对线程须同时操作：
  ```bash
  cpupower -c 0-127 idle-set -d 2   # 禁用 C2（全核）；-e 2 重新启用
  ```
- **P-State / Boost**：仅 C0 可达更高 P 态；开关：
  ```bash
  echo 1 > /sys/devices/system/cpu/cpufreq/boost   # BIOS Core Performance Boost=ENABLED 前提
  cat /sys/devices/system/cpu/cpufreq/boost
  ```
- **调速器**：`cpupower frequency-set -g performance`（HPC）；其余 ondemand/conservative/powersave。
- **裸机 HPC 推荐 BIOS**（原文表）：

  | BIOS 项 | 设置 |
  |---|---|
  | x2APIC | Enabled |
  | SMT | Disabled（或 ON，依应用） |
  | NPS | 4（6×CCD 用 2） |
  | APBDIS | 1 |
  | Fixed SOC Pstate | P0 |
  | Core Performance Boost | ON |
  | Determinism Slider | Power |
  | cTDP / PPL | 240（7742 最大，如 240W） |
  | DF C-States | Disabled |
  | TSME | OFF |
  | Core C-states | Enabled（若非纯低延迟场景） |

- **耦合 vs 非耦合模式**：内存 ≤2933MT/s 与 Fabric 同频=**耦合（最低延迟）**；DDR4-3200 时 Fabric 异步=**非耦合（带宽略高、延迟增）**。可在 2933 耦合 / 3200 非耦合间试验。

### 4) OS 层面调优（含命令）

- **大页（HP）**：DPDK/HPL 建议禁用 THP 并分配显式大页：
  ```bash
  echo 'never' > /sys/kernel/mm/transparent_hugepage/enabled
  echo 'never' > /sys/kernel/mm/transparent_hugepage/defrag
  echo 3 > /proc/sys/vm/drop_caches      # 清 page-cache
  echo 1 > /proc/sys/vm/compact_memory   # 整理碎片
  number_huge_2m_pages=$((240*1024/2))   # 240GB / 2MB
  echo $number_huge_2m_pages > /proc/sys/vm/nr_hugepages
  hugectl --force-preload --heap mybinary.bin   # 保留大页运行
  ```
- **swap / 回收**：`swapoff -a`；`/proc/sys/vm/zone_reclaim_mode`（1=开区回收 / 2=写脏页 / 4=swap），双路 EPYC 推荐 1 或 3；`echo 1|2|3 > /proc/sys/vm/drop_caches` 清理缓存（SLURM epilog 常用）。
- **NUMA 平衡**：`echo 0 > /proc/sys/kernel/numa_balancing`（HPC 通常关，避免扫描开销与抖动；STREAM 实测变慢）。
- **Spectre/Meltdown**：EPYC 不受 Variant-3(Meltdown) 影响，受 Variant-1/2(Spectre) 影响；内部计算节点可关补丁：`echo 0 > /sys/kernel/debug/x86/retp_enabled` 与 `ibpb_enabled`。
- **地址随机化**：`echo 0 > /proc/sys/kernel/randomize_va_space`（可选，便于基准复现）。
- **核心绑定示例**：
  ```bash
  numactl -C 7 ./mybinary                  # 绑核
  numactl -C 7 --membind=0 ./mybinary      # 绑核+绑内存域
  make -j 256                              # 双路 2×64 SMT=ON = 256 线程
  ```

### 5) 编译器与库（AOCC / AOCL）

- **AOCC**（AMD 编译器套件，基于 LLVM）：clang(C/C++) + flang(Fortran)；关键 flag：

  | 用途 | flag |
  |---|---|
  | Zen2 指令集 | `-march=znver2` |
  | 本机指令集 | `-march=native` |
  | 激进优化 | `-Ofast` |
  | LTO | `-flto` |
  | OpenMP | `-fopenmp` |
  | 向量库 | `-vector-library=LIBMVEC -L/libm-install/lib -lmvec` |
  | AMD libm | `-L/libm-install/lib -lamdlib` |
  | 展开/快数学 | `-funroll-loops -ffast-math -freciprocal-math` |

  OpenMP 亲和：
  ```bash
  export OMP_NUM_THREADS=N
  export GOMP_CPU_AFFINITY="0-(N-1):1"
  ```
- **GCC**：HPC 推荐 ≥7.3（自带 4.8.5 性能不足）；Intel 编译器 v18–v20 有限测试可用。
- **MKL 在 AMD 上的坑**：MKL ≤v19 不认 AVX2 指令位，需设：
  ```bash
  export MKL_DEBUG_CPU_TYPE=5
  export MKL_ENABLE_INSTRUCTIONS=AVX2
  ```
  否则 DGEMM 慢数倍。
- **AOCL 数学库**：BLIS（BLAS）、libFLAME（LAPACK）、FFTW（DFT）、AMD LibM、ScaLAPACK（并行 LA，依赖 BLIS+libFLAME）。
- **uProf**：AMD 性能分析器，支持 CPU/能耗/系统级分析、性能计数器、Timeline(Timechart)。
- **MPI 绑定（OpenMPI）**：每 L3 1 rank，配合 UCX 设备与 numactl：
  ```bash
  mpirun -np 16 -hostfile hostfile \
    -np 1 numactl --physcpubind=0  mybinary -parallel \
    -np 1 numactl --physcpubind=4  mybinary -parallel \
    ...   # 每个 L3 首核：0,4,8,12,...
  UCX_NET_DEVICES=mlx5_2:1
  ```

### 6) 实操速查

- 查 SMT：`lscpu`（Threads per core）；查 Boost：`cat /sys/devices/system/cpu/cpufreq/boost`；查 NUMA：先 `numactl -H`。
- 基准：双路 DDR4-3200 单 DIMM/通道、每 L3 1 核，STREAM 约 **350 GB/s**。
- NPS4 + Boost=ON + SMT=ON 在 NAMD(STMV) 表征中性能最佳；验证推荐设为基线后再二次调优。

### 双链

- 网卡 / DPDK 部署规划：[[50-reference/sources/chips/NIC DPDK]]
- 微架构 / 性能计数器优化：[[50-reference/sources/books/Intel 架构 性能]]
- 可观测 / 定时器机制（同属系统性能主题）：[[50-reference/NPP 定时器 机制]]
