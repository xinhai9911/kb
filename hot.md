---
title: Hot Cache
summary: >-
    *A ~500-word semantic snapshot of recent activity.*
category: index
updated: 2026-07-29T19:00:00+00:00T18:00:00
base_confidence: 0.7
lifecycle: draft
created: 2026-07-29
tags: [kb]
---

# Hot Cache

*A ~500-word semantic snapshot of recent activity.*

## Recent Activity

- [2026-07-29] WIKI_RESEARCH topic="Film Directing" — 电影导演全景调研，21 篇页面（sources=6, concepts=8, entities=6, synthesis=1）。覆盖：叙事结构（三幕剧/非线性）、场面调度、布光技法、色彩心理学、表演指导、制作流程、导演方法论光谱、作者论、5 位代表导演方法（Hitchcock/Kubrick/Nolan/Bong/Kore-eda）

- CROSS_LINK 5 links added: MCP↔protocols, Anthropic↔Claude prompt guide, OpenAI↔Transformer, Agent-memory↔decoder-track; how-to-use.md rewritten to cover all 86 pages

- [2026-07-29] WIKI_RESEARCH topic="eBPF" — 第一阶段 7 篇页面：核心架构、Maps、Cilium、安全工具、工具链、来源、全景
- [2026-07-29] WIKI_RESEARCH topic="eBPF" DEEP_DIVE — 第二阶段深挖 5 篇：验证器与安全模型、程序类型全目录、XDP 详解、sched_ext、生产案例；扩展 synthesis（时间线/helpers/syscall/案例）、工具链（ELF section 映射）、核心架构（关联页）
- [2026-07-29] WIKI_UPDATE topic=ai-llm — AI 大模型全景调研，13 篇页面（sources=6, concepts=3, entities=3, synthesis=1）
- [2026-07-29] WIKI_RESEARCH topic="AI Agent" — Agent 框架、MCP 协议、记忆规划，13 篇页面（sources=4, concepts=4, entities=4, synthesis=1）
- [2026-07-29] WIKI_UPDATE db-decoder-ironhive — 新项目同步，4 篇页面（项目概述、协议分析、Track 设计、实现）

## Active Threads

- **film-directing** — 2026-07-29 完成全景调研：21 篇（sources=6, concepts=8, entities=6, synthesis=1）。覆盖叙事结构（三幕剧/非线性）、场面调度、布光、色彩、表演指导、制作流程、导演方法论光谱、作者论、5 位代表导演（Hitchcock/Kubrick/Nolan/Bong/是枝）。现有 3 篇实操参考页（ffmpeg 剪辑/蒙太奇/分镜模板）。后续可深挖：拉片方法论、具体电影案例拆解、短片导演实战流程
- **ebpf** — 已完成两轮调研：第一轮 7 篇（核心架构/Maps/Cilium/安全/工具链/来源/全景），第二轮深挖 5 篇（验证器与安全模型、程序类型全目录、XDP、sched_ext、生产案例）并扩展 synthesis 和工具链。合计 12 篇概念/实体/综述 + 1 篇来源。剩余可探索：验证器实战调试、eBPF + AI 工作负载调度、Windows eBPF 演进跟踪、BPF arena/exceptions 编程实践
- **ai-llm** — Transformer 架构 → 三阶段管线 → 推理优化 → 开源/中国生态，已写 13 篇，后续可深挖多模态、Agent、评测
- **ai-agent** — Agent 框架对比（LangGraph/CrewAI/AutoGen）、MCP 协议、记忆规划机制，已写 13 篇，可深挖 Agent 安全评估和调优
- **db-decoder-ironhive** — Hive 解码器开发一期，解码器代码已完成（libhive.so），falcon 部署因框架限制受阻，待平台团队介入

## Key Takeaways

- Transformer Decoder-only 仍是 LLM 最基础架构
- "预训练 → SFT → 对齐"三阶段范式确立；RLHF vs DPO vs GRPO 因模型而异
- 推理优化产品价值超过训练优化
- DeepSeek V4 以 GPT-4 1/70 定价推动降价
- Hugging Face 是开源生态不可替代的基础设施
- AI Agent 核心：工具使用 + 记忆 + 规划
- MCP 协议正在标准化 Agent 工具集成接口
- **eBPF 生产成本节约**：多数企业报告约 30% 基础设施成本下降（Cloudflare 30%、DoorDash 40% 内存、LinkedIn 70% 日志量）
- **Cilium 2026 年 K8s CNI 事实标准**：O(1) 服务查找、sidecarless L7、Hubble 连接级可观测
- **eBPF 安全三工具**：Falco 检测告警（CNCF 毕业）、Tetragon 内核阻断（Cilium 生态）、Tracee 取证（Aqua）
- **sched_ext (6.12+)**：BPF 自定义 CPU 调度器，静默回退 CFS，CachyOS 默认启用，大模型推理场景受益
- **XDP 纳秒级包处理**：Netflix 数万实例、Cloudflare 7 Tbps+ DDoS、Meta Katran L4 LB
- **验证器安全基座**：CFG + SSA 符号执行 + 状态剪枝；PREVAIL/BeePL 验证器突破；CAP_BPF + BPF token + BPF LSM 三层授权
- **eBPF 现代特性**：kfuncs (5.13+)、异常/bpf_throw (6.19+)、arena map、IETF ISA 标准化、Windows 兼容推进

## CPU 内存模型与大页

- [2026-07-29] NEW [[concepts/CPU 内存模型与大页]] — 内存类型（UC/WC/WB）、Write Combining 与 NIC 发送描述符合并写入、Store Buffer + Invalidate Queue 结构、x86 TSO vs ARM64 Relaxed 对比与 barrier 开销表、Non-temporal store 与 memcpy 绕过 cache、TLB 层级（4K/2M/1G 页覆盖 vs Miss 率对比）、THP vs hugetlbfs 配置、DPDK 无锁 ring 的 barrier 布局、false sharing 围栏
- **WC 内存数据面收益**：合并多次 8B PCIe 写为一次 16B TLP，TX 环效率显著提升
- **x86 TSO vs ARM64**：x86 smp_wmb 退化为 0-cycle compiler barrier；ARM64 需 dmb ishst (~20 cy)，无锁 ring 性能差 8-15%
- **1G 大页 vs 4K 页**：TLB miss 率 <0.5% vs ~15%，page walk 级数 2 vs 4，64GB 内存页表差 512x
- **THP 必须关**：khugepaged 碎片整理导致延迟抖动，DPDK/VPP 应用只认 hugetlbfs

## CPU 隔离与实时调优

- [2026-07-29] NEW [[entities/CPU 隔离与实时调优]] — 8 类干扰源与隔离手段一览、内核启动参数完整示例（isolcpus / nohz_full / rcu_nocbs / intel_pstate=disable / processor.max_cstate=1 / skew_tick=1 / clocksource=tsc）、cpuset 二次加固、IRQ 亲和绑定脚本、performance governor、大页配置（1G/2M + 多 NUMA）、tuned-adm realtime profile、DPDK 隔离检查脚本、turbostat 验证、12 项常见问题排查表
- **isolcpus 不够**：root 进程仍可跑在隔离核，必须 cpuset 二次加固剔除
- **tick 是漂移头号杀手**：nohz_full 隔离核上约 1μs/次，skew_tick=1 错开共振
- **三件套验证**：turbostat Busy%≈100% + 中断计数=0 + CPU%c1≈0

## CPU 架构对比 x86 vs ARM

- [2026-07-29] NEW [[synthesis/CPU 架构对比 x86与ARM]] — CISC vs RISC（流水线/解码/发射/L0 Cache）、内存模型（x86 TSO vs ARM Relaxed + barrier 开销表）、SIMD（AVX-512 vs SVE2 寄存器/谓词/场景适用性）、大页与 TLB（2M/1G/contiguous bit）、原子操作（lock cmpxchg vs ldxr/stxr/cas + DPDK ring 性能差异 8-15%）、性能观测（PEBS vs SPE）、选型指引（NFV→x86，边缘/信创→ARM64）
- **ARM64 DPDK 代价**：smp_wmb 不是免费指令（x86 0cy vs ARM64 ~20cy），无锁 ring 慢 8-15%
- **ARM64 调优短板**：无 perf c2c（无 HITM 事件）、SPE 精度不如 PEBS、TLB PMC 不足

## CPU 指令集加速

- [2026-07-29] NEW [[concepts/CPU 指令集加速]] — 数据面关键指令速查：CRC32（SSE4.2 单指令 8B CRC → ~12 GB/s，VPCLMULQDQ → ~80 GB/s）、BMI/BMI2（BEXTR/ANDN/PEXT/PDEP 代替多位移位+掩码）、MOVDIR64B 一次 64B 原子 WC 写入（DPDK ice PMD TX commit）、AES-NI 做 IPSec GCM 卸载（VPP encrypt node）、PREFETCHW/NTA/CLWB/CLFLUSHOPT 缓存控制指令集
- **MOVDIR64B 网卡提交**：一次 PCIe 64B 写代替 8 次 movnti，DSA/IA 也受益
- **BMI2 pext/pdep**：VPP 隧道头解析用 1 条指令代替 5-8 条 shift+mask
- **CRC 硬件加速**：VPCLMULQDQ 批量 CRC 比 SSE4.2 查表快 6x
- 检测：`grep "vpclmulqdq\|movdir64b\|bmi2\|aes" /proc/cpuinfo`

## CPU 中断与 MSI-X 模型

- [2026-07-29] NEW [[entities/CPU 中断与MSI-X]] — x86 APIC vs ARM GIC 中断拓扑、MSI-X 表结构与 per-vector 亲和性配置脚本、多队列 RSS ↔ IRQ 映射、轮询 vs 中断 vs NAPI 模式选择、中断延迟解剖（~2-5μs vs 0μs 轮询）、空轮询自适应切换（DPDK Power Lib）、ethtool 合并调优、IRQ 风暴排查、ARM64 GIC ITS 限制、实际中断亲和绑定脚本
- **MSI-X 每队列独立绑核**：2048 向量 vs MSI 32 向量，数据面必须 MSI-X
- **DPDK PMD 中断只留控制面**：link state/error 事件绑到 non-isolated 核，worker 纯轮询
- **ARM GIC 注意**：GICv2 不支持 MSI-X（需 ITS），部分 SoC 最多 32 vec

## CPU Cache 高级优化

- [2026-07-29] NEW [[concepts/CPU Cache 高级优化]] — Intel RDT 三件套（CAT cache 分区隔离降 miss 率 23%→5%、CMT 实时监控 LLC 占用、MBM 带宽监控），硬件预取器 6 种（DCU/IP/L2 Adj/HW/LLC/MLP）及 MSR 0x1A4 控制，预取距离调优表（L2 转发 8-12 / 隧道 4-6 / IPSec 2-3），DDIO 分片配置（BIOS 10%-20% 可调），代码布局（hot/cold 属性分离、16B 对齐、NOP padding），Cache blocking 分块，兜底策略速查
- **CAT 是数据面杀手锏**：防止 control plane 进程踢掉 DPDK 热 cache line，miss 率 23%→5%
- **预取器非万能**：随机查表关掉，流式处理打开
- **DDIO 双刃剑**：小包开 DDIO（热数据在 LLC），大包关（避免踢热数据），BIOS 控制
- **perf 验证**：LLC miss <5% 优秀，>15% 需出优化手段

## CPU 虚拟化与 I/O 穿透

- [2026-07-29] NEW [[concepts/CPU 虚拟化与IO穿透]] — VT-x/SVM VM-Exit 开销（2000 cy/simple）、EPT 二级地址翻译、VT-d DMA Remapping + Interrupt Remapping + Posted Interrupts、SR-IOV PF/VF 结构与配置（最多 252 VF）、VFIO 架构与 IOCTL 流程、IOPT 页表与 IOTLB miss、vCPU pinning + NUMA 绑核（关键！）、Posted Interrupts 绕过 VMM 注入（~500 cy vs 传统 2000 cy）、虚拟化吞吐损失对比（SR-IOV 3-7% vs virtio 20-40%）
- **SR-IOV 数据面核心**：VF + vCPU + 内存必须同 NUMA node，否则吞吐减半
- **Posted Interrupts**：IOMMU 直接写 VM 的 PIR，零 VM-Exit 投递中断
- **VFIO 隔离**：IOMMU 分组决定直通粒度，分组内所有设备必须全直通

## CPU 功耗与 RAPL

- [2026-07-29] NEW [[concepts/CPU 功耗与RAPL]] — P-state 模型（P0-Pn/CPPC）、intel_pstate vs acpi_cpufreq（数据面必须 intel_pstate=disable + performance）、C-state 深度（C1/C1E/C6/C7/C8 唤醒延迟 1μs→300μs）、RAPL 五个域（PKG/DRAM/PP0/PP1/PSys）、能量计数器读取（energy_uj）、power capping 命令与实测降频效果（200W→100W 吞吐降 30-40%）、PL1/PL2/Tau 解读、turbostat 稳态验证
- **数据面推荐**：intel_pstate=disable + max_cstate=0 + performance governor + no RAPL cap
- **C6 代价**：~100μs 退出延迟 = 数百 64B 包，数据面核必须禁止 C6+
- **turbostat 三要素**：Busy%=100 + CPU%c6=0 + 频率恒定

## CPU 微架构内部

- [2026-07-29] NEW [[concepts/CPU 微架构内部]] — OoO 流水线全流程（Decode→IDQ→RAT→RS→Port→ROB）、关键结构深度（Golden Cove: ROB 512 / RS 97 / Load Buf 72 / Store Buf 56 / IDQ 108 / μOP Cache 2.25K）、MacroFusion（cmp+jne 合并减少 10-15% μOP）、12 执行端口竞争分析（Port0-11 function map）、perf 端口压力诊断命令、ROB/RS 满 stall 溯源事件、Load/Store Buffer 满检测、Store-Forwarding 冲突、Branch Predictor 内部（BTB/BHB/TAGE/Loop Detector/SC）、Pipeline bubble 五类根因全表
- **端口瓶颈看 `uops_dispatched_port.port_*`**：任一超过 40% 应怀疑微架构瓶颈
- **ROB = 乱序执行窗口**：L3 miss（300cy）占 ROB entry 不放，窗口满 → 流水线停
- **MacroFusion**：cmp + jne 合为一条 μOP，VPP 的 if-else 分发路径天然受益

## CPU 互联拓扑

- [2026-07-29] NEW [[concepts/CPU 互联拓扑]] — Xeon 互联演进（Ring→Mesh→UPI）、Mesh 延迟公式（|Δrow|+|Δcol| hops × 10ns）、UPI 参数对比（Skylake 10.4GT/s → Granite Rapids 20GT/s）、Snoop 协议模式（Early/Home/COD/SNC→SNC 降延迟 20%）、AMD CCD/IOD/xGMI 架构（跨 CCD ~80ns vs 同 CCD ~20ns）、CXL 三协议栈（io/mem/cache）与 Type1-3、CXL 数据面场景（流表扩展/SmartNIC 缓存/FPGA 共享）、延迟 Map 全表（L1 4cy → CXL Type3 540cy）、实战延迟矩阵生成脚本（mlc）、部署策略（高吞吐→同 Socket+SNC）
- **SNC (Sub-NUMA Clustering)**：LLC 切片虚拟 NUMA，降延迟 20%，DPDK 需确认支持等分
- **CXL Type 2/3 对数据面意义**：SmartNIC cache 一致性（300ns cache）和内存池扩展（200ns）正在改变数据面架构
- **无论 Intel/AMD**：跨 die/socket 延迟是本地 2x，vCPU + VF + 内存绑同 NUMA 是强制要求

## Linux 内核网络栈

- [2026-07-29] NEW [[concepts/Linux 内核网络栈]] — 收包主线（NIC DMA → NAPI poll → GRO → netif_receive_skb → TC ingress → IP → Netfilter → socket）、sk_buff 关键字段布局、NAPI budget 调优（默认 64，调大提吞吐但增延迟）、GRO/GSO/TSO 硬件卸载作用、TC ingress/egress 与 BPF 挂接、Netfilter 5 hook 点与 conntrack 开销（新建 200-500cy）、RPS/RFS/XPS 软件分发、Flow Offload 直接推流转发到网卡硬件、数据面路径延迟全表（DPDK 500ns / XDP 1μs / NAPI 5μs / Netfilter 20μs）
- **GRO 核心**：同流小包合并为大包，一次协议栈处理代替 N 次
- **Flow Offload**：conntrack 流推到 NIC 硬件转发，零 CPU 开销（但受硬件流表容量限制）

## PCIe 子系统

- [2026-07-29] NEW [[concepts/PCIe 子系统]] — PCIe 拓扑（RC/Switch/EP）、BDF 枚举地址格式、配置空间（VendorID/BAR/MSI-X Cap 链）、BAR 类型（Memory 64-bit Prefetchable vs Non-prefetchable/WC）、TLP 事务包结构（MRd/MWr/CplD/MSG）、DMA 流程（mbuf 写入→描述符更新→MSI-X）、PCIe Gen1-6 每 Lane 速率（2.5-64 GT/s）、高级特性（ACS/ATS/AER/DPC/SR-IOV/PASID）、DPDK EAL PCI 枚举流程、常见绑定/资源/链路问题排查
- **PCIe Gen5 x16 = 63 GB/s**：百 G 网卡（~25GB/s 双工）刚好够用，Gen4 x16（31.5GB/s）开始紧
- **BAR WC 映射**：DPDK 用 resource0_wc 做 TX 门铃合并写，不需要额外 sfence
- **ATS 减少 IOTLB miss**：设备预翻译 IOMMU 地址，对高 IOPS NVMe 场景有益

## Linux 内存管理

- [2026-07-29] NEW [[concepts/Linux 内存管理]] — Buddy 分配器（order 0-10 层级、分裂合并代价 20-50 cy）、Migration Types（Unmovable/Movable/Reclaimable 碎片控制）、Watermark 三水位与 kswapd 直接回收 Direct Reclaim（100μs-10ms 阻塞！DPDK 场景必须避免）、Slab/Slub per-CPU allocator（~10-20 cy，sk_buff 分配 ~200 cy vs DPDK mbuf ~10 cy）、碎片整理 kcompactd 与直接压缩 stall、CMA 连续内存预留、NUMA 均衡与 AutoNUMA（数据面关掉 `numa_balancing=0`）、OOM 原理与 DPDK 预分配免干扰策略
- **Direct Reclaim 是数据面杀手**：`< low watermark` → 分配阻塞 100μs-10ms → 大量丢包
- **kswapd 即使 isolcpus 也会跑**：必须 cpuset 限制到 non-isolated 核
- **DPDK 预分配即防御**：启动时吃掉所有需要的内存，运行中不再触发内核分配

## Linux 性能诊断工具集

- [2026-07-29] NEW [[entities/Linux 性能诊断工具集]] — 30 秒快速诊断（CPU/内存/磁盘/网络/中断/进程/dmesg 八步检查）、ftrace（function_graph 跟踪任意内核函数、event tracing 调度/内存/IRQ/NET 事件）、bpftrace one-liners（execve/kmalloc/IO 延迟/softirq/sk_buff 分配/DPDK VFIO ioctl）、perf 补充（tracepoint 频率、per-core PMC、ns 精度时间线、对比 diff）、trace-cmd + kernelshark 图形化时间线、/proc 快速诊断文件大全、四类场景排查组合（worker 抖动/网络降速/用户态慢/Direct Reclaim）、工具选择决策树
- **DPDK 抖动排查三部曲**：`cat /proc/interrupts` → `trace-cmd sched_switch` → `kernelshark` 时间线
- **bpftrace 无侵入**：生产环境安全，DPDK 用户态不触发，但可跟踪控制面 VFIO ioctl
- **ftrace event 开销最小**：只有事件点时插桩，数纳秒级

## 存储栈与 io_uring

- [2026-07-29] NEW [[concepts/存储栈与io_uring]] — Block 层结构（VFS→FS→Block Layer→NVMe 驱动→PCIe）、bio/request 合并流程、I/O Scheduler（NVMe→none / SATA→mq-deadline / HDD→bfq）、NVMe 多队列模型（每核一对 SQ/CQ）、io_uring 架构（SQ/CQ 共享环）、四种加速模式对比（中断/SQPOLL/IOPOLL/FixedBuf）、延迟对比（read ~8.5μs → io_uring IOPOLL ~6.2μs，省 30%）、SPDK 用户态 NVMe 驱动（与 DPDK 对称架构：轮询/大页/VFIO）、NVMe-oF 跨网络存储、数据面场景对比（DPDK 500ns vs SPDK 5-15μs vs io_uring 6μs）
- **io_uring 最大收益不在于单次延迟，在于消除 syscall + 中断路径**
- **SPDK vs DPDK 完全对称**：用户态驱动 + 轮询 + 大页 + VFIO，一个控网络一个控存储
- **NVMe-oF RDMA + SPDK**：跨网络存储延迟仅增加 ~5μs（RDMA 一跳），接近本地性能

## New: CPU 框架知识

- [2026-07-29] WIKI_UPDATE topic="CPU" — CPU 知识入库 2 篇：[[concepts/CPU 核心架构]]（超标量流水线 / Cache 层级 MESI / NUMA 拓扑 / DDIO / SIMD 演进 / 分支预测 / P/E-core 混合 / IPC 健康指标 / 微架构速查表）和 [[entities/CPU 性能分析实战]]（perf 全方位用法 + PMC 指标解读 + 火焰图 + Cache Miss 定位 + False Sharing + VPP/DPDK 专用分析 + 典型优化案例 + 监控脚本）
- **CPU 性能核心等式**：IPC = instructions / cycles；IPC > 2 优、< 1 表示 Cache Miss / 分支预测失败 / 数据依赖瓶颈
- **数据面最大杀手是内存停顿**：一次 L3 Miss ≈ 300 周期 ≈ 80-100 条指令空等；DDIO 可把网卡数据直写 LLC 跳过 DRAM
- **NUMA 跨域代价**：跨 Socket 访存比本地慢约 2x，DPDK/VPP 必须绑同 NUMA
- **perf 排查链**：`perf top` 看热点 → `perf stat` 看 IPC/Cache Miss → `perf record -g` 取调用链 → 火焰图可视化 → `perf c2c` 定位 false sharing
- **VPP 分支优化模式**：多 if-else 拆成多个独立 node，前级 node 根据类型分发 → 分支预测失败归零

## New: DPDK + eBPF + VPP 开发实战

- [2026-07-29] WIKI_UPDATE topic="DPDK" — DPDK 知识入库 2 篇：[[concepts/DPDK 核心架构]]（EAL/PMD/内存模型/run-to-completion vs pipeline/生态系统）、[[synthesis/DPDK 与 eBPF XDP 技术对比]]（设计哲学/性能/开发运维/选型指引/融合趋势 AF_XDP）；eBPF 全景和来源页增加 DPDK 交叉引用
- [2026-07-29] WIKI_UPDATE topic="develop" — 开发实战双页入库：[[entities/eBPF 开发实战]]（BCC 3 例 + libbpf XDP/TC/fentry + maps 4 种 + bpftool/bpftrace 调试 + 11 条陷阱清单）和 [[entities/DPDK 开发实战]]（环境搭建脚本 + l2fwd 代码 + pipeline 3-stage 源码 + API 详解 + 10 项调优清单）
- [2026-07-29] WIKI_UPDATE topic="VPP" — [[entities/VPP 开发实战]] （环境搭建 + 完整插件项目模板（hello_vpp） + node function 编写范式 + VNET feature 挂接 + 包修改 + process node 定时任务 + 外部项目构建 + 追踪/调试/性能观测 + 常见陷阱速查）
- **DPDK vs eBPF 核心差异**：DPDK 是内核旁路（用户空间轮询 PMD，独占网卡，100GbE 线速），eBPF/XDP 是内核内加速（驱动层 hook，安全验证器，云原生）。两条路以 AF_XDP 为桥梁融合。
- **DPDK 生态系统**：FD.io/VPP（NFV）、OVS-DPDK、SPDK（存储）、F-Stack（TCP/IP），K8s 场景需 SR-IOV 直通
- **VPP 插件开发模式**：VLIB_PLUGIN_REGISTER 入口 → VLIB_REGISTER_NODE 注册数据面节点 → vnet_feature_enable_disable 挂接 → VLIB_CLI_COMMAND 控制面。PROCESS node 做定时，INTERNAL node 做向量化处理。[50-reference/vpp-plugin-dev|vpp-plugin-dev]、[50-reference/vpp-plugin-perf|vpp-plugin-perf] 分别深究 API 和调优
