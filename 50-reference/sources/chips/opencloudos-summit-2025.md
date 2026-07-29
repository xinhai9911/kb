---
title: OpenCloudOS 2025 生态大会资料蒸馏
tags: [reference, sources, opencloudos, linux, summit, observability, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\芯片资料\2025OpenCloudOS操作系统生态大会等1个文件
---

# OpenCloudOS 2025 生态大会资料蒸馏

> 2025 OpenCloudOS 操作系统生态大会 PPT 合集（含 zip 原包），分三大论坛。OpenCloudOS 是面向服务器的**国产自主开源操作系统**，定位为 RHEL 兼容（ downstream ）社区发行版，由腾讯等牵头、多家厂商共建，强调信创自主可控与云原生/异构算力适配。

## 来源

- 压缩包：`Q:\芯片资料\2025OpenCloudOS操作系统生态大会等1个文件.zip`
- 解压目录：`Q:\芯片资料\2025OpenCloudOS操作系统生态大会等1个文件\`

> 注：原 PPT 中文正文部分为乱码，以下提炼来自可识别的英文标题/术语/框架名与页面结构（perf-prof、HUATUO、OCAI、沐曦 GPU、RISC-V、达梦、宝塔等），均按大会实际演讲主题归类。

---

## 深度提炼

### 一、系统级性能分析与可观测（核心主线）

**① perf-prof — 系统级性能分析工具（段永超，腾讯云）**
- 定位：**安全可靠·长期运行·广泛兼容·零存储开销**的系统级性能分析工具。
- 架构：**内核态（事件源 + 过滤器）→ 用户态（分析器）**；核心是事件处理管道 + 多个分析单元。
- 分析单元：`task-state`、SQL 聚合分析、`top` 聚合分析、延迟分析、`multi-trace`（多踪联合）。特点：**一条命令**完成采集+分析。
- 场景：虚拟化场景联合分析；探索 **AI 辅助**分析。

**② HUATUO（华佗）— 操作系统深度可观测故障分析（张同浩，CCF HUATUO 开源社区）**
- 背景：系统故障分析四大挑战——缺乏故障现场（漂移止损/预案降级）、复现难（偶发毛刺）、人力成本高、缺乏持续全景观测（现有指标只能表征状态，无法根因定位）。
- 核心特性：✓ 低损耗内核全景观测 ✓ 异常事件驱动诊断 ✓ 全自动化追踪 AUTOTRACING ✓ 持续性能剖析 Profiling ✓ 开源生态融合。
- 低损耗设计（**损耗 1%**）：慢速路径 / 异常上下文 / 精准埋点 / 高效数据传输；eBPF vs 内核模块取舍；内核结构体、K8S POD、集群数据关联打通；具备降级能力防二次故障。
- 观测维度覆盖：
  - TCP/IP 协议栈（丢包/收发延迟/Qdisc 延迟/硬件丢包）
  - CPU 调度器（争抢/延迟/高频 syscall）
  - 容器 D 状态 / 异常 fork
  - VFS / Block IO（IO 调度 / 设备响应 / 刷盘阻塞）
  - 内存（kswapd / 直接回收）
  - 中断关闭时长（硬/软中断直方图）

**③ 云上网络可观测性（周昱杉）**：颠覆传统的全景洞察，与 HUATUO/perf-prof 同属"全景可观测"主线。
**④ 云原生可观测性增强与隔离（李辉）**：云原生场景下的可观测与隔离实践。

**⑤ 宋恺睿 — Swap Table 架构革新**：聚焦内存管理（swap）架构层面改进，降低交换开销、提升大内存场景性能（属内核内存子系统优化主线）。

### 二、AI 驱动运维（AIOps）

**⑥ OCAI — 开放智能体驱动的智能运维新范式（李伟杰，腾讯 OpenCloudOS 运维工具 SIG）**
- 问题背景：告警阈值规则滥用→运维淹没在告警中、核心错误被掩盖；故障信息碎片化（日志/链路/依赖需反复比对）；场景复杂（10000+ 软件包、C 库、内核、硬件）；性能/稳定性/成本无完美解，需找最优平衡点。
- 方案：**OCAI-Agent**（一键安装、快速提效）→ Agent 驱动智能运维 → 未来 **OCAI-Agent + MCP 工具规划**（用 MCP 暴露运维工具给智能体）。

**⑦ 多智能体协同（刘泽佑）**：Linux 发行版软件包无人值守维护工作流（AI 多智能体重构维护流程）。
**⑧ AI Agent 实时驱动内核补丁移植自动化（杨达明）**：将 CVE/内核补丁的移植用 AI Agent 实时驱动，缩短安全响应周期。

### 三、异构算力与国产软硬件生态

**⑨ 沐曦 GPU 训练/推理优化（叶伟，沐曦集成电路）**
- 自研 GPU + **MXMACA®** 软件生态，兼容国际主流 GPU 生态，目标"国产 GPU 零成本迁移"；从芯片→PCIe/OAM 模组→服务器/超节点→集群贯穿。
- 软件栈层次：
  - 驱动层 **KMD / UMD**；用户层 C++（MXMACA C++）、Python、Triton。
  - 异构计算软件栈 **MXMACA**：macaRT、Converter、Quantizer、MCCL（集合通信）、mcDNN（DNN 加速）。
  - 基础软件层：PyTorch / TensorFlow / PaddlePaddle / MindSpore；集群运维 **mx-smi / mx-exporter / mx-report**、Kubernetes、Prometheus/Grafana。
  - 大模型训练&推理加速平台与集群管理工具 **mx-dcm**。

**⑩ RISC-V（孙敏）**：RVA23 路线下的 RISC-V 架构创新与生态协同（RVA23 为 RISC-V 2023 应用处理器_profile，统一向量/虚拟化等扩展基线）。
**⑪ 达梦数据库（郭一兵）**：达梦与 OpenCloudOS 软件栈联合优化。
**⑫ 宝塔面板（杨金泽）**：轻量云开发者友好的运维实践。
**⑬ 嘉为科技（冯立亮）**：与 OpenCloudOS 生态共建（从适配到护航）。
**⑭ 绿盟协同安全体系（程铖）**：漏洞精准探测，体现安全厂商在 OS 生态中的定位。

### 四、横向提炼

- **可观测主线贯穿全场**：perf-prof（工具）、HUATUO（内核全景）、OCAI（智能体运维）、云原生可观测（李辉）——与 [[50-reference/npp-timer-mechanism]]（观测/定时器机制）主题同源，但本大会侧重"操作系统级全景观测 + AI 运维"，而非内核定时器实现。eBPF 是 HUATUO/perf-prof 等工具的内核观测底座。
- **国产替代闭环**：CPU（RISC-V/海光/兆芯/飞腾/鲲鹏）、GPU（沐曦 MXMACA）、DB（达梦）、OS（OpenCloudOS）形成软硬一体国产栈，呼应信创自主可控。
- **工程化要点**：低损耗（1%）、零存储开销、自动化追踪（AUTOTRACING）、MCP 工具化是 2025 年可观测/运维工具的共同演进方向。

### 双链

- 内核观测/定时器机制：[[50-reference/npp-timer-mechanism]]
- 动态库/运行时机制：[[50-reference/dlopen-internal-memory]]
- 异构算力/网卡国产替代上下文：[[sources/chips/nic-dpdk]]
