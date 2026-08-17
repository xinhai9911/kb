---
title: CPU 核心架构
category: concepts
tags: [cpu, architecture, cache, numa, simd, performance, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    CPU 微架构核心知识：超标量流水线、Cache 层级与一致性（MESI）、NUMA 拓扑与内存访问、SIMD 向量化、分支预测、DDIO、Prefetch、P/E-core 混合架构。
    面向数据面开发人员（DPDK/VPP/eBPF）的体系架构速查。
base_confidence: 0.85
lifecycle: draft
---

# CPU 核心架构

> 面向高性能网络数据平面开发的知识图谱。理解 CPU 微架构是写出纳秒级包处理代码的前提。
>
> 实战性能工具见 [[entities/CPU 性能分析实战]]，DPDK NUMA 调优见 [[concepts/DPDK 核心架构]]。

## 1. 处理器拓扑

```
Socket 0                              Socket 1
├─ L3 Cache (LLC)                     ├─ L3 Cache (LLC)
│  ├─ Core 0                          │  ├─ Core 4
│  │  ├─ L1i 32KB / L1d 48KB         │  │  ├─ L1i 32KB / L1d 48KB
│  │  ├─ L2 1.25MB (per-core)        │  │  ├─ L2 1.25MB
│  │  └─ HT 0 / HT 1                 │  │  └─ HT 4 / HT 5
│  ├─ Core 1 ...                      │  ├─ Core 5 ...
│  └─ ...                             │  └─ ...
└─ Memory Controller                  └─ Memory Controller
   DDR5-4800 (本地访问 ~100ns)           DDR5-4800 (远程访问 ~180ns)
```

关键概念（以 Intel Xeon / AMD EPYC 为例）：

| 术语 | 含义 | 对数据面的影响 |
|------|------|---------------|
| **Socket** | 物理 CPU 封装 | 多 Socket 跨 NUMA 访存延迟翻倍 |
| **Core** | 物理核心（独立流水线 + L1/L2） | 每核跑一个 DPDK worker / VPP worker |
| **HT / SMT** | 超线程（同核共享 L1/L2/执行单元） | 数据面通常关 HT：避免资源争抢 |
| **NUMA Node** | 共享本地内存的 Core 集合 | 网卡 + worker 必须在同 NUMA，否则性能腰斩 |
| **LLC** | Last Level Cache（L3） | DDIO 写入 LLC，命中即零拷贝 |
| **CCD / Die** | AMD 芯片内计算复合体 | EPYC 多 Die，跨 Die 访存延迟高于 Die 内 |

## 2. 超标量流水线

### 2.1 流水线阶段（现代 x86 约 14-19 级）

```
取指 → 预解码 → 解码 → 重命名 → 分发 → 发射 → 执行 → 提交
       ↓                      ↓          ↓
   分支预测                μOP 缓存   乱序执行
```

- **超标量（Superscalar）**：每周期发射多条指令（Intel 可达 6 μOP/cycle）
- **乱序执行（OoO）**：指令不按程序顺序执行，仅保证数据依赖
- **分支预测**：错误预测代价 12-20 周期，数据面应减少循环内分支
- **μOP Cache**：已解码微操作缓存，减少解码功耗

### 2.2 对开发者的启示

| 做 | 不做 |
|----|------|
| 顺序访问内存（硬件预取生效） | 随机跳跃访问（cache miss） |
| 批处理减少分支（VPP 向量化） | 每个包单独处理（流水线气泡） |
| 函数内联（减少 call/ret） | 深调用链（I-cache miss） |
| 紧凑数据结构（热字段放同一 cache line） | 跨越 cache line 的频繁字段访问 |
| likely/unlikely 标注分支 | 分支内做复杂计算 |

## 3. Cache 层级

### 3.1 典型 Intel Xeon Cache 参数

```
L1d (Data):   48KB,   64B line,  12 周期,   per-core
L1i (Instr):  32KB,   64B line,    per-core
L2:           1.25MB, 64B line,   ~40 周期, per-core
L3 (LLC):     30-60MB,64B line,   ~80 周期, per-socket (共享)
DDR5 DRAM:    —                   ~100ns     ~300 周期
```

- **64 字节 cache line** 是原子单元：相邻数据一次载入
- **Cache 未命中代价**：L1 miss ~12cy → L2 miss ~40cy → L3 miss ~80cy → DRAM ~300cy

### 3.2 MESI 缓存一致性协议

```
Modified   →   Exclusive   →   Shared   →   Invalid
  ↓               ↓               ↓
脏（写回内存）  未修改，独占   未修改，共享   无效
```

- 核间共享数据产生 **MESI 总线流量**
- 写缓存行时若其他核持有该行 → 发送 Invalidate 消息
- **False Sharing（伪共享）**：多核写同 cache line 的不同字段，导致缓存行在核间乒乓传递

```c
// ❌ 伪共享：a 和 b 在同一 cache line，多核交替写触发 MESI 失效
struct { int a; int b; } stats;

// ✅ 各占独立 cache line（__cacheline_aligned 或 padding）
struct { int a __cacheline_aligned; int b __cacheline_aligned; } stats;
```

DPDK/VPP 中 per-worker 的计数器、统计变量均需注意 false sharing。

### 3.3 预取

- **硬件预取器**：检测到顺序/步进访问模式后自动拉取后续 cache line
- **软件预取**：

```c
// 在 DPDK/VPP node function 中手工预取下一批 buffer
rte_prefetch0(vlib_get_buffer(vm, from[4]));  // 拉到 L1
rte_prefetch2(vlib_get_buffer(vm, from[6]));  // 拉到 L2（更远的批次）
```

预取距离需调优：太近（来不及）、太远（被踢出 cache）。

## 4. NUMA

### 4.1 NUMA 拓扑发现

```bash
# 查看 NUMA 拓扑
lscpu
numactl --hardware
lstopo                       # 图形化拓扑

# 关键参数
numactl --show               # 当前策略
numactl --cpunodebind=0 --membind=0 your_app   # 绑定核 + 内存
```

### 4.2 NUMA 访问延迟

| 访问场景 | 相对延迟 |
|----------|----------|
| 同核 L1 命中 | 1x |
| 同 Socket 远端 L3 | ~3x |
| 同 Socket 本地内存 | ~20x |
| 跨 Socket 远端内存 | ~40x |

### 4.3 DPDK/VPP 场景的 NUMA 绑定

```bash
# DPDK EAL 参数
./dpdk-app -l 0-3 -n 4 --socket-mem 1024,0 -- \
  --portmap="(0,0)"  # port 0 绑定到 socket 0

# VPP startup.conf
cpu {
  main-core 0
  corelist-workers 1-3       # 只绑 socket 0 的核
}
```

- 网卡 PCIe 所属 NUMA 节点要与 worker 核一致（`lspci -vv` 看 `NUMA node`）
- 跨 NUMA 分配 buffer 导致 PCIe DMA 到远端内存，延迟翻倍

## 5. DDIO（Data Direct I/O）

Intel Xeon E5 v2+ (Ivy Bridge) 起支持。

```
传统路径:  网卡 → PCIe → 内存 → CPU L3 → Core
DDIO 路径: 网卡 → PCIe → L3 (LLC)   → Core    (跳过内存)
```

- 流量小足 LLC 时：DDIO 把网卡数据直接写入 LLC，Core 零额外延迟读取
- 流量超大（>LLC）时：DDIO 退化为"写到内存 + 预取"模式，需调 `number_of_queues` 拆分
- VPP/DPDK 场景：典型线速流量（10-100GbE）通常 < LLC，DDIO 是本质性能收益之一

## 6. SIMD / 向量化

### 6.1 x86 SIMD 演进

| 指令集 | 寄存器宽度 | 寄存器数 | 每周期 FMA | 支持 CPU |
|--------|-----------|---------|-----------|---------|
| MMX | 64-bit (mm0-mm7) | 8 | — | 已淘汰 |
| SSE/SSE2 | 128-bit (xmm0-xmm15) | 16 | — | 所有 x64 |
| AVX/AVX2 | 256-bit (ymm0-ymm15) | 16 | 2 (FMA) | Haswell+ |
| AVX-512 | 512-bit (zmm0-zmm31) | 32 | 2 | Skylake-SP+ |
| AVX10 | 256/512-bit | 32 | — | Granite Rapids+ (统一 P/E-core) |

### 6.2 数据面的 SIMD 应用

```c
// 例：用 AVX2 同时解析 8 个 IPv4 头（每个 packet 的 TTL + protocol + checksum）
// 注意：实际 DPDK/VPP 节点通常逐包处理已有足够 IPC，SIMD 用于更重的计算

// 例：SIMD 快速 CRC / 校验和
// DPDK 提供 rte_net_get_ptype() + rte_raw_cksum_mbuf() 利用 SIMD
```

- 协议包头解析：`memcpy` 和字段提取通常不会是瓶颈，SIMD 用于：
  - 大块数据校验和（IP/TCP checksum offload 通常已卸载到网卡）
  - 加密/压缩/哈希计算
  - 正则表达式/DPI 模式匹配
- VPP 的 **向量化本就是 SIMD 友好的**：一批包连续处理，指令缓存命中好

### 6.3 自动向量化约束

编译器自动向量化需要：
- 循环次数编译期可知或可推断
- 无指针别名（`__restrict` 关键词）
- 无循环间数据依赖
- 无函数调用（内联）

```c
// 编译器友好写法
void add_arrays (float * __restrict a, const float * __restrict b, int n) {
    for (int i = 0; i < n; i++)
        a[i] += b[i];   // 编译器可自动生成 SIMD
}
```

## 7. 分支预测

### 7.1 预测失败代价

| 架构 | 错误预测惩罚 |
|------|-------------|
| Intel Skylake | 15-20 周期 |
| Intel Ice Lake | ~12 周期 |
| AMD Zen 3/4 | 10-15 周期 |

### 7.2 数据面分支优化

```c
// ❌ 每个包都分支（分支预测器困惑）
if (likely(protocol == TCP))   handle_tcp(b);
else if (protocol == UDP)      handle_udp(b);
else                           handle_other(b);

// ✅ 批量前判 + 分拆到不同的 node（VPP 的 next-node 设计正为此）
// 在 VPP 中注册 3 个 next node，在 node function 里用 nexts[] 分流
// 每个分支作为独立 node function，不存在分支预测失败

// 另一种：用查找表取代分支
typedef void (*handler_t)(vlib_buffer_t *);
handler_t handlers[256] = { /* 查表 */ };
```

- VPP 的节点图设计天然解决分支预测问题：不同包类型走不同 node
- eBPF 验证器限制分支复杂度（CFG + 有界循环），所以 eBPF 程序不会有长分支链

## 8. P-core / E-core 混合架构

Intel 12代+ (Alder Lake) / Granite Rapids：

| 核类型 | 用途 | 适合 |
|--------|------|------|
| P-core (Performance) | 大核，高单线程性能 | DPDK worker / VPP worker / 控制面 |
| E-core (Efficiency) | 小核，高吞吐/低功耗 | 管理面 / 统计 / 非实时任务 |

**对数据面开发者的影响**：
- 必须把 DPDK/VPP worker 绑到 P-core，不可放 E-core（E-core 无 AVX-512，频率低）
- `lscpu` 可看 `Model name` 区分；`lstopo` 可看核心类型
- Linux 6.0+ 的 `taskset` / `numactl` 可感知 P/E 标签

## 9. 流水线气泡与性能指标

```
理想 CPI = 1 (每周期 1 指令)
实际 CPI = 指令数 / 周期数 = 1 + 停顿周期占比

主要停顿来源：
  - Cache miss (L1 ~12cy, L2 ~40cy, L3 ~80cy, DRAM ~300cy)
  - 分支预测失败 (12-20cy)
  - 数据依赖 (3-5cy 每级)
  - I-cache miss (取指令未命中)
  - μOP 队列满 (复杂指令解码)
```

DPDK/VPP node function 中分析 IPC（Instructions Per Cycle）：

```bash
perf stat -e cycles,instructions,cache-misses,branch-misses \
  -p $(pgrep vpp) sleep 10
```

**健康指标**：
- IPC > 2：好（向量化、cache 友好）
- IPC 1-2：可接受
- IPC < 1：有瓶颈（cache miss / 分支预测差 / 数据依赖）

## 10. CPU 微架构快速参考表

| 架构 | 年代 | 工艺 | 流水线级 | L1 / L2 | 解码宽度 | μOP Cache | AVX |
|------|------|------|---------|---------|---------|----------|-----|
| Intel Skylake | 2015 | 14nm | 14-19 | 32KB / 256KB | 5 | 1.5K | AVX2 |
| Intel Sunny Cove (Ice Lake) | 2019 | 10nm | ~14 | 48KB / 512KB | 5 | 2.25K | AVX-512 |
| Intel Golden Cove (Alder Lake P) | 2021 | 7nm | ~14 | 32KB / 1.25MB | 6 | 2.25K | AVX2 |
| Intel Redwood Cove (Meteor Lake) | 2023 | 7nm | — | 48KB / 2MB | 6 | — | AVX2 |
| Intel Lion Cove (Arrow Lake P) | 2024 | — | — | 48KB / 2.5MB | 8 | — | AVX2 |
| AMD Zen 2 (Rome) | 2019 | 7nm | ~13 | 32KB / 512KB | 6 | — | AVX2 |
| AMD Zen 3 (Milan) | 2021 | 7nm | ~13 | 32KB / 512KB | 6 | — | AVX2 |
| AMD Zen 4 (Genoa) | 2022 | 5nm | ~13 | 32KB / 1MB | 6 | — | AVX-512 |
| AMD Zen 5 (Turin) | 2024 | 4nm | ~14 | 48KB / 1MB | 8 | — | AVX-512 |

## 参考来源

- [[50-reference/sources/books/Intel 架构 性能|Intel 架构优化手册蒸馏]]
- [[50-reference/sources/chips/AMD EPYC|AMD EPYC NUMA 配置]]
- [[entities/CPU 性能分析实战|CPU 性能分析实战]]
- Intel® 64 and IA-32 Architectures Optimization Reference Manual
- AMD Processor Programming Reference (PPR)
