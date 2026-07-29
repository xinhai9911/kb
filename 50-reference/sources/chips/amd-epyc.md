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

---

## 深度提炼

> 来源：`AMD_EPYCTM_7002_系列处理器的高性能计算__HPC__调整指南.txt`（~49 KB，英文正文完整，9 章）、`AMD_EPYC_霄龙__NUMA_配置设置.txt`（~3 KB，NPS 配置说明）。7002 系列即 Rome，基于 Zen 2（7nm）。

### 1) 微架构与封装

- **多芯片模块（MCM）**：单插槽 = 中央 **I/O Die（IOD）** + 最多 **8 个 CCD**（Compute Complex Die）；每个 CCD 含最多 **2 个 CCX**，每个 CCX = **4 核 + 共享 16MB L3**。即每 CCD 最多 8 核 / 32MB L3。
- **Infinity Fabric（DF）**：连接各 CCD 与 IOD，最高 **1467 MHz（FCLK）**；提供跨组件及双路 CPU 间的一致内存访问。
- **内存**：每插槽 **8 通道 DDR4**，每通道 ≤2 DIMM，最高 **DDR4-3200 / 4TB**；统一内存控制器（UMC）频率 ≤1600MHz(MEMCLOCK)。
- **I/O**：每插槽最多 **128 条 PCIe Gen4** 通道；全部挂在单一 IOD 上，可抽象为 **4 个逻辑象限**（每象限 2 内存通道 + 32 I/O 通道），内存可在象限内 2 路交错到 16 路（双路全交错）。
- **核心**：Zen 2 核含 L1 回写缓存 + 私有 512KB L2；支持 **SMT**（每核 2 线程）。
- **关键规格**：Max 64 核 / 3200MHz 内存 / 128 lane PCIe Gen4。

### 2) NUMA 与 NPS 配置（核心调优点）

- Rome 采用 NUMA 内存交错，BIOS 可设 **NPS（Nodes Per Socket）= 0 / 1 / 2 / 4**，另有 **L3CAN（L3 Cache As NUMA）**。
- **NPS1**：整 CPU = 1 NUMA 域，8 通道全交错；所有 PCIe 也归此域。
- **NPS2**：2 个 NUMA 域，各半核半内存，4 通道交错。
- **NPS4**：每象限 1 NUMA 域，2 通道交错；PCIe 设备按根所在象限归属某域（如 Mellanox HCA 靠近特定 NUMA）。
- **NPS0**：跨双路全 16 通道交错——**HPC 不推荐**（增加跨插槽延迟）。
- **约束**：6 个 CCD 的 SKU 不支持 NPS4，仅 NPS1/2。
- **L3CAN**：每 L3 作为独立 NUMA 节点，双路最多暴露 32 个 NUMA 域。
- **查看拓扑**：`hwloc-ls` / `hwloc-info` / `numactl -H`；SMT=ON 时 CPU ID 0–127 为线程 0、128–255 为线程 1（core-0 关联 CPU 0 与 128）。

### 3) 电源状态与 BIOS 调优

- **C-State**：C0 活跃 / C1 空闲 / C2 更深睡眠+电源门控。禁用 C2（`cpupower -c 0-3 idle-set -d 2`）对低延迟网络（如 Infiniband）关键——从 C2→C0 的恢复延迟会增大网络 IO 延迟；**SMT 任一线程在 C0/C1 时核无法进 C2**，故禁用 C2 需同时对配对逻辑 CPU 操作。
- **P-State / Boost**：仅 C0 时可达更高 P 态；7742 基频 2.25GHz(P0)、Boost 至 3.4GHz。命令行开关：`echo 1 > /sys/devices/system/cpu/cpufreq/boost`（需 BIOS Core Performance Boost=ENABLED）。
- **调速器**：HPC 用 `cpupower frequency-set -g performance`；其余 ondemand/conservative/powersave。
- **推荐 BIOS（裸机 HPC）**：x2APIC=Enabled、SMT=Disabled、NPS=4（6×CCD 用 NPS2）、APBDIS=1、Fixed SOC Pstate=P0、Core Performance Boost=ON、Determinism Slider=Power、cTDP=PPL=240W、DF C-States=Disabled、TSME=OFF；低延迟互联（Mellanox）启用 Preferred-IO + Enhanced Preferred-IO Mode，并用 `lspci` 定位设备总线号填入 Preferred-IO Device。
- **耦合 vs 非耦合模式**：内存时钟 ≤2933MT/s 时与 Fabric 同频=**耦合模式（最低延迟）**；DDR4-3200 时 Fabric 异步=**非耦合（带宽略高、延迟增加）**。可在 2933 耦合 / 3200 非耦合间试验。

### 4) OS 层面调优

- **大页**：DPDK/HPL 等建议禁用 THP（`echo never > /sys/kernel/mm/transparent_hugepage/enabled|defrag`），分配显式大页：`echo $N > /proc/sys/vm/nr_hugepages`（例 240GB/2MB：`N=240*1024/2`），用 `hugectl --force-preload --heap` 运行。
- **swap / 回收**：`swapoff -a`；`/proc/sys/vm/zone_reclaim_mode`（1=开区回收 / 2=写脏页 / 4=swap），双路 EPYC 推荐 1 或 3；清理缓存 `echo 1|2|3 > /proc/sys/vm/drop_caches`。
- **NUMA 平衡**：`echo 0 > /proc/sys/kernel/numa_balancing`（HPC 通常关，避免扫描开销与抖动）。
- **Spectre/Meltdown**：EPYC 不受 Variant-3(Meltdown) 影响，受 Variant-1/2(Spectre) 影响；内部计算节点可关补丁：`echo 0 > /sys/kernel/debug/x86/retp_enabled` 与 `ibpb_enabled`。
- **核心绑定示例**：`numactl -C 7 ./mybinary`、`numactl -C 7 --membind=0 ./mybinary`；构建用 `make -j 256`（双路 2×64 SMT=ON = 256 线程）。

### 5) 编译器与库（AOCC / AOCL）

- **AOCC**（AMD 编译器套件，基于 LLVM 9.0）：clang(C/C++) + flang(Fortran)；关键 flag：`–march=znver2` / `–march=native`、`-Ofast`、`-flto`、`-fopenmp`、`-vector-library=LIBMVEC`。
- **GCC**：HPC 推荐 ≥7.3（自带 4.8.5 性能不足）；Intel 编译器 v18–v20 有限测试可用。
- **MKL 在 AMD 上的坑**：MKL ≤v19 不认 AVX2 指令位，需设 `export MKL_DEBUG_CPU_TYPE=5` 与 `export MKL_ENABLE_INSTRUCTIONS=AVX2`，否则 DGEMM 慢数倍。
- **AOCL 数学库**：BLIS（BLAS）、libFLAME（LAPACK）、FFTW（DFT）、AMD LibM、ScaLAPACK（并行 LA，依赖 BLIS+libFLAME）。
- **uProf**：AMD 性能分析器，支持 CPU/能耗/系统级分析、性能计数器监控、Timeline(Timechart)，可定位热点与微架构瓶颈。
- **MPI 绑定**：OpenMPI 用 appfile 固定到 L3（`seq -s, 0 4 127` 每 L3 1 rank），配合 `UCX_NET_DEVICES=mlx5_2:1`、numactl 绑核；混合 MPI+OpenMP 时 OMP_NUM_THREADS=驻留 L3 的核/线程数。

### 6) 实操速查

- 查 SMT：`lscpu`（Threads per core）；查 Boost：`cat /sys/devices/system/cpu/cpufreq/boost`；查 NUMA：先 `numactl -H`。
- 基准：双路 DDR4-3200 单 DIMM/通道、每 L3 1 核，STREAM 约 **350 GB/s**（Intel 或 AOCC 编译器）。
- 验证推荐设为基线后再做二次调优；NPS=4/8×CCD/每 L3 4 核 + Boost=ON + SMT=ON 在 NAMD(STMV) 表征中性能最佳。

### 双链

- 网卡 / DPDK 部署规划：[[sources/chips/nic-dpdk]]
- 微架构 / 性能计数器优化：[[sources/books/intel-architecture-perf]]
- 可观测 / 定时器机制（同属系统性能主题）：[[50-reference/npp-timer-mechanism]]
