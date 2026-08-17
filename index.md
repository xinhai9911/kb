---
summary: >-
    *This index is automatically maintained. Last updated: 2026-07-30*
category: index
title: Wiki Index
base_confidence: 0.9
lifecycle: reviewed
created: 2026-07-29
tags: [kb]
updated: 2026-07-30
---

# Wiki Index

*This index is automatically maintained. Last updated: 2026-07-30*

## 索引

- [[00-index/how-to-use|使用说明]]
- [[00-index/tag-glossary|标签字典]]
- [[50-reference/obsidian-usage|Obsidian 使用方法]]
- [[50-reference/obsidian-plugins|Obsidian 已安装插件说明]]
- [[50-reference/callout-conventions|全库 Callout 使用清单与规范]]

## 项目

- [[10-projects/database-decoder|database-decoder]]
- [[10-projects/training|training]]

### 工程示例（可编译/可运行）
- [[projects/README|工程示例总览导航（nginx / 加密 / 限流熔断 / 可观测 / CI-CD / db-decoder）]]

## 协议分析

- [[20-protocols/hbase|HBase 协议分析]]
- [[20-protocols/elasticsearch|Elasticsearch 协议分析]]
- [[20-protocols/influxdb|InfluxDB 协议分析]]

## FPGA / 硬件逻辑

- [[20-protocols/fpga|FPGA 知识（现场可编程门阵列）]]
- [[20-protocols/fpga-design-patterns|FPGA 常用设计模式（FSM/流水线/FIFO/握手/AXI-S/仲裁器）]]
- [[50-reference/fpga-usage|FPGA 使用方法（工具链 / 仿真 / 上板）]]
- [[50-reference/fpga-verification|FPGA 验证方法（Testbench / 断言 / 覆盖率 / CI）]]
- [[entities/fpga-vendors|FPGA 厂商与开源工具链（选型 / Yosys / nextpnr）]]

### 综述

- [[_staging/synthesis/fpga-chip-design-systematic-guide|FPGA 完整芯片代码构建综述（设计流程/工程结构/顶层模块/子系统/约束/验证/学习路径）]]

## 网络数据面（VPP / VLIB）

- [[20-protocols/vpp|VPP 知识（Vector Packet Processing）]]
- [[entities/VPP 开发实战|VPP 开发实战]]
- [[50-reference/vpp-usage|VPP 使用方法（CLI / 配置 / 运维）]]
- [[50-reference/vpp-plugin-dev|VPP 插件开发（自定义 Node / Plugin）]]
- [[50-reference/vpp-plugin-perf|VPP 插件性能调优（节点 / 批处理 / 多核）]]

## NPP（基于 VPP 的流表平台）

- [[50-reference/npp-timer-mechanism|NPP 内部定时触发机制]]
- [[50-reference/npp-flowtable-cleanup-example|NPP 流表清理代码实例]]
- [[50-reference/npp-flowtable-perf-test|NPP 流表性能测试实例]]

## Nginx 反向代理

### 概念
- [[concepts/Nginx 架构与事件模型|Nginx 架构与事件模型]]
- [[concepts/Nginx 框架内部实现|Nginx 框架内部实现（模块三元组 / 配置合并 / 阶段 handler / 内存池 slab / upstream 状态机）]]

### 实体
- [[entities/Nginx 反向代理实战|Nginx 反向代理实战（配置大全）]]
- [[entities/Nginx 性能调优与排障|Nginx 性能调优与排障]]
- [[entities/Nginx 模块开发实战|Nginx 模块开发实战（Handler/Filter/Upstream/负载均衡器 + 调试）]]

## 加密算法（系统/工程/性能视角）

- [[synthesis/加密算法技术全景综述|加密算法技术全景综述（选型 + 学习地图）]]

### 概念
- [[concepts/加密算法总览与分类|加密算法总览与分类（对称/非对称/哈希/TLS 分层）]]
- [[concepts/对称加密 AES与ChaCha20|AES 与 ChaCha20（模式 / AEAD / Nonce / 硬件加速边界）]]
- [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE|RSA / ECC / ECDHE（填充 / PFS / 签名）]]
- [[concepts/哈希函数与消息认证 HMAC|哈希与 HMAC（SHA-2/3 / SM3 / MAC vs 签名）]]
- [[concepts/TLS 协议握手与记录层|TLS 1.2/1.3 握手与记录层（PFS / 0-RTT / 密钥派生）]]
- [[concepts/加密硬件加速 AES-NI与协处理器|AES-NI / 协处理器 / TLS Offload 硬件加速]]
- [[concepts/侧信道攻击与常量时间实现|侧信道攻击与常量时间实现（时序/缓存/Spectre）]]

### 实体（实战）
- [[entities/OpenSSL_BoringSSL 开发集成实战|OpenSSL/BoringSSL 开发集成（EVP/AEAD/证书/TLS）]]
- [[entities/Nginx TLS 配置与证书管理实战|Nginx TLS 配置与证书管理（1.3/PFS/OCSP/HSTS）]]
- [[entities/国密 SM2_SM3_SM4 实战|国密 SM2/SM3/SM4 + TLCP 实战]]
- [[entities/证书与 X.509 公钥基础设施实战|X.509 证书与 PKI（链/CSR/mTLS/吊销）]]

## 软件工程与架构

- [[synthesis/软件工程与架构技术全景综述|软件工程与架构技术全景综述（权衡 + 学习路径）]]

### 概念（原理）
- [[concepts/软件设计原则与代码质量|软件设计原则与代码质量（SOLID/DRY/Clean Code/坏味道）]]
- [[concepts/设计模式精讲|设计模式精讲（创建/结构/行为 + 反模式）]]
- [[concepts/架构风格演进|架构风格演进（单体→微服务→事件驱动→CQRS→Serverless）]]
- [[concepts/分布式系统基础|分布式系统基础（CAP/共识/幂等/时钟）]]
- [[concepts/容器原理与运行时|容器原理与运行时（Namespace/Cgroups/OverlayFS/OCI 镜像/运行时栈，衔接 K8s 分布式编排）]]
- [[concepts/容器安全|容器安全（Capabilities/seccomp/AppArmor/Rootless/镜像供应链/PodSecurity/Falco）]]
- [[concepts/Kafka 消息队列与流处理|Kafka 消息队列与流处理（分区/ISR/Exactly-once/KRaft/与 RabbitMQ·Pulsar 对比，衔接事件驱动）]]
- [[concepts/可观测性工程|可观测性工程（日志/指标/追踪/SLO）]]
- [[concepts/韧性设计|韧性设计（超时/重试/熔断/限流/舱壁/降级）]]
- [[concepts/CI_CD与测试策略|CI/CD 与测试策略（金字塔/契约/金丝雀）]]
- [[concepts/API 设计|API 设计（REST/gRPC/版本化/幂等/错误模型）]]
- [[concepts/领域驱动设计 DDD|领域驱动设计 DDD（限界上下文/聚合/领域事件）]]
- [[concepts/系统设计思维|系统设计思维（trade-off/容量/技术债）]]
- [[concepts/Go 运行时与并发模型|Go 运行时与并发模型（GMP/三色 GC/Channel/内存模型，云原生底座）]]
- [[concepts/Redis 缓存与数据结构|Redis 缓存与数据结构（结构/持久化/Cluster/穿透·击穿·雪崩/Cache-Aside）]]
- [[concepts/关系型数据库内核|关系型数据库内核（InnoDB B+树/缓冲池/MVCC/隔离级别/WAL，对比 NoSQL）]]
- [[concepts/HTTP2 与 HTTP3(QUIC)|HTTP/2 与 HTTP/3(QUIC)（多路复用/HPACK/TCP 队头阻塞/UDP 0-RTT）]]
- [[concepts/认证授权 OAuth2 OIDC JWT|认证授权 OAuth2/OIDC/JWT（认证 vs 授权/授权码+PKCE/JWT 校验/零信任）]]
- [[concepts/基础设施即代码 Terraform|基础设施即代码 Terraform（HCL/state/plan/模块化，衔接 GitOps）]]
- [[concepts/etcd 与 Raft 共识实战|etcd 与 Raft 共识实战（MVCC/Lease/备份恢复/性能调优，K8s 状态存储层）]]
- [[concepts/RabbitMQ 消息代理|RabbitMQ 消息代理（AMQP/Exchange 类型/Quorum 队列/Stream，灵活路由）]]
- [[concepts/NATS 轻量消息系统|NATS 轻量消息系统（Core NATS/JetStream/超集群，超低延迟 Pub/Sub）]]
- [[concepts/Pulsar 云原生消息|Pulsar 云原生消息（计算存储分离/Geo-Replication/Tiered Storage）]]
- [[concepts/Consul 服务发现与网格|Consul 服务发现与网格（DNS/KV/Service Mesh，混合环境）]]
- [[concepts/多集群管理与联邦|多集群管理与联邦（Federation/Cluster API/Submariner/Liqo）]]
- [[concepts/分布式存储 Rook-Ceph Longhorn|分布式存储 Rook/Ceph/Longhorn（K8s 原生分布式存储）]]
- [[concepts/安全容器运行时 gVisor Kata Firecracker|安全容器运行时 gVisor/Kata/Firecracker（沙箱/microVM）]]
- [[concepts/OPA Gatekeeper 策略引擎|OPA Gatekeeper 策略引擎（Rego/ConstraintTemplate/Admission 控制）]]
- [[concepts/HPA VPA KEDA 自动伸缩深度|HPA/VPA/KEDA 自动伸缩深度（三类伸缩器原理与组合）]]
- [[concepts/FinOps 与云资源优化|FinOps 与云资源优化（成本治理/VPA/Spot/Karpenter）]]

### 实体（实战）
- [[entities/重构实战：识别并消除代码坏味道|重构实战（坏味道前后对比）]]
- [[entities/微服务拆分实战|微服务拆分实战（边界/数据/通信/一致性）]]
- [[entities/可观测性接入实战|可观测性接入实战（OTel+Prometheus+Grafana）]]
- [[entities/CI_CD 流水线实战|CI/CD 流水线实战（GitHub Actions/金丝雀）]]
- [[entities/限流熔断实战|限流熔断实战（令牌桶/滑动窗口/熔断/退避）]]
- [[entities/容器实战|容器实战（docker/nerdctl/ctr 命令、镜像构建、排障，衔接 K8s）]]
- [[entities/GitOps 与 ArgoCD 实战|GitOps 与 ArgoCD 实战（Git 唯一事实源/Application/自动同步/回滚，衔接 CI/CD）]]
- [[entities/容器可观测落地|容器可观测落地（cAdvisor/kube-state-metrics/Prometheus、容器日志管道 Loki、OTel 跨 Pod 追踪、RED+USE 排障闭环）]]

### 示例工程
- [[projects/README|工程示例总览导航（一眼看全部示例工程）]]
- [[projects/resilience-examples/README|resilience-examples（限流/熔断/重试 可编译 C 示例）]]
- [[projects/observability-examples/README|observability-examples（OTel+Prometheus+Loki+Tempo+Grafana 栈）]]
- [[projects/cicd-pipeline-examples/README|cicd-pipeline-examples（GitHub Actions + Helm 金丝雀 + 回滚）]]

## 软件项目管理

- [[synthesis/软件项目管理全景综述|软件项目管理全景综述（PMBOK / 敏捷 / 学习路径）]]

### 概念（基础）

- [[concepts/pm-pmbok|PMBOK 知识体系（5 大过程组 × 10 大知识领域）]]
- [[concepts/pm-agile-methodologies|敏捷方法论概述（Scrum / Kanban / Lean / XP 对比）]]
- [[concepts/pm-scrum|Scrum 框架（Sprint / 三角色 / 五事件）]]
- [[concepts/pm-kanban|看板方法（WIP / Cycle Time / 流动）]]
- [[concepts/pm-requirements-management|需求与范围管理（WBS / User Story / 变更控制）]]
- [[concepts/pm-schedule-cost-management|进度与成本管理（CPM / EVM / 估算）]]
- [[concepts/pm-quality-management|质量管理（QA/QC / CMMI / 成本）]]
- [[concepts/pm-risk-management|风险管理（识别 / 概率-影响 / 应对）]]
- [[concepts/pm-team-stakeholder-management|团队与干系人管理（Tuckman / RACI）]]
- [[concepts/pm-estimation-deep|软件估算技术深入（Wideband Delphi / COCOMO / FPA）]]
- [[concepts/pm-metrics-kpi|项目度量与 KPI（Velocity / Cycle Time / CPI）]]
- [[concepts/pm-lean-xp|Lean 与 XP 深入（精益原则 / TDD / 结对编程）]]
- [[concepts/pm-scaling-agile|规模化敏捷（SAFe / LeSS / Nexus）]]
- [[concepts/pm-change-configuration|变更与配置管理（CCB / 配置项 / 审计）]]
- [[concepts/pm-documentation|软件项目文档体系（全生命周期文档清单）]]

### 实体（工具）

- [[entities/pm-jira|Jira 项目跟踪工具]]
- [[entities/pm-zentao|禅道（全生命周期管理）]]
- [[entities/pm-turnitin-kanban|板栗看板（轻量级看板）]]
- [[entities/pm-common-tools|项目管理工具对比]]

### 来源

- [[sources/pm-classic-references|项目管理经典参考来源（规范 / 书籍 / 文章）]]

## Linux 内核与性能

### 概念
- [[concepts/Linux 内核网络栈|Linux 内核网络栈]]
- [[concepts/PCIe 子系统|PCIe 子系统]]
- [[concepts/Linux 内存管理|Linux 内存管理]]
- [[concepts/存储栈与io_uring|存储栈与 io_uring]]

### 实体
- [[entities/Linux 性能诊断工具集|Linux 性能诊断工具集]]

## 参考

- [[50-reference/sources|来源蒸馏索引]]
- [[50-reference/dlopen-internal-memory|dlopen 内部内存]]
- [[50-reference/npp-timer-mechanism|NPP Timer 机制]]
- [[50-reference/claude-prompting-best-practices|Claude 提示词最佳实践]]
- [[50-reference/montage-techniques|Montage 剪辑技术]]
- [[50-reference/shot-sizing-axes-storyboard|镜头、景别、轴线与故事板]]
- [[50-reference/director-intro|导演基础]]

## AI 大模型

- [[synthesis/ai-llm-overview|AI 大模型全景综述]]
- [[concepts/transformer-architecture|Transformer 架构]]
- [[concepts/llm-training-pipeline|LLM 训练管线]]
- [[concepts/llm-inference-optimization|LLM 推理优化]]
- [[entities/openai|OpenAI]]
- [[entities/hugging-face|Hugging Face]]
- [[entities/deepseek|DeepSeek]]

### 来源

- [[sources/vaswani2017-attention|Attention Is All You Need (2017)]]
- [[sources/deepseek-v4-technical|DeepSeek V4 技术报告]]
- [[sources/llm-training-pipeline-guide|LLM 训练管线指南]]
- [[sources/llm-inference-optimization|LLM 推理优化综述]]
- [[sources/chinese-llm-landscape|中国大模型生态分析]]
- [[sources/huggingface-ecosystem|Hugging Face 生态系统]]

## AI Agent

- [[synthesis/ai-agent-research|AI Agent 研究综述]]
- [[concepts/ai-agent-overview|AI Agent 概述]]
- [[concepts/agent-frameworks|Agent 框架]]
- [[concepts/mcp-protocol|Model Context Protocol]]
- [[concepts/agent-memory-planning|Agent 记忆与规划]]
- [[concepts/hybrid-retrieval-bm25-semantic-fusion|混合检索（BM25 + 语义 + 融合排序）]]
- [[entities/anthropic|Anthropic]]
- [[entities/openai|OpenAI]]
- [[entities/langchain|LangChain]]
- [[entities/crewai|CrewAI]]

### 来源

- [[sources/anthropic-agent-build|Anthropic Agent 构建指南]]
- [[sources/langchain-intro|LangChain/LangGraph 框架介绍]]
- [[sources/mcp-specification|MCP 规范]]
- [[sources/agent-frameworks-comparison|AI Agent 框架对比]]

## eBPF 内核可编程

### 综述

- [[synthesis/eBPF 技术全景|eBPF 技术全景综述]]

### 概念

- [[concepts/eBPF 核心架构|eBPF 核心架构]]
- [[concepts/eBPF Maps 存储模型|eBPF Maps 存储模型]]
- [[concepts/eBPF 验证器与安全模型|eBPF 验证器与安全模型]]
- [[concepts/eBPF 程序类型与全挂载点|eBPF 程序类型与挂载点]]
- [[concepts/XDP 高速数据路径|XDP 高速数据路径]]

### 实体

- [[entities/Cilium 容器网络|Cilium 容器网络]]
- [[entities/eBPF 开发实战|eBPF 开发实战]]
- [[entities/DPDK 开发实战|DPDK 开发实战]]
- [[entities/eBPF 安全工具|eBPF 运行时安全工具]]
- [[entities/eBPF 工具链|eBPF 工具链]]
- [[entities/sched_ext 可扩展CPU调度器|sched_ext 可扩展调度器]]
- [[entities/eBPF 生产案例与生态系统|eBPF 生产案例与生态系统]]

### 概念

- [[concepts/DPDK 核心架构|DPDK 核心架构]]

### 综述

- [[synthesis/DPDK 与 eBPF XDP 技术对比|DPDK 与 eBPF/XDP 技术对比]]

### 来源

- [[sources/eBPF 调研来源|eBPF 调研来源]]

## Kubernetes

### 综述

- [[synthesis/Kubernetes 技术全景综述|Kubernetes 技术全景综述（声明式/控制循环/四大支柱/生态/学习路径）]]
- [[synthesis/容器分布式技术全景综述|容器分布式技术全景综述（容器原理→运行时/镜像→实战→安全→K8s 编排→分布式支柱 的分层地图与学习路径）]]

### 概念（原理）

- [[concepts/Kubernetes 核心架构与组件|Kubernetes 核心架构与组件（控制面/数据面/API 对象模型）]]
- [[concepts/Kubernetes 声明式模型与控制器|Kubernetes 声明式模型与控制器（Reconcile/finalizer/级联删除/SSA）]]
- [[concepts/Kubernetes 工作负载与调度|Kubernetes 工作负载与调度（Pod/Deployment/StatefulSet/调度/QoS）]]
- [[concepts/Kubernetes 网络模型|Kubernetes 网络模型（CNI/Service/kube-proxy/Ingress/NetworkPolicy）]]
- [[concepts/Kubernetes 存储体系|Kubernetes 存储体系（PV/PVC/StorageClass/CSI）]]
- [[concepts/Kubernetes 安全模型|Kubernetes 安全模型（RBAC/SA/Secret/PSS/准入/NetworkPolicy）]]
- [[concepts/Kubernetes 高可用与自愈|Kubernetes 高可用与自愈（探针/滚动更新/PDB/控制面 HA/etcd）]]
- [[concepts/Kubernetes Operator 与 CRD|Kubernetes Operator 与 CRD（扩展机制/成熟度模型/开发栈）]]
- [[concepts/Kubernetes Service Mesh|Kubernetes Service Mesh（Sidecar/数据面控制面/Istio-Linkerd/mTLS/选型）]]

### 实体（实战）

- [[entities/Kubernetes 部署与工具链实战|Kubernetes 部署与工具链实战（minikube/kind/kubeadm/containerd）]]
- [[entities/kubectl 与日常运维实战|kubectl 与日常运维实战（命令速查/故障排查）]]
- [[entities/Helm 包管理实战|Helm 包管理实战（Chart/模板/Release/回滚/GitOps）]]
- [[entities/Ingress-Nginx 详解实战|Ingress-Nginx 详解实战（架构/注解/TLS/金丝雀/常见坑）]]
- [[entities/Kubernetes 网络实战|Kubernetes 网络实战（厂商中立：Service 四类型/CoreDNS/Ingress/NetworkPolicy + 排障清单）]]

### 示例工程

- [[projects/k8s-kind-examples/README|k8s-kind-examples（kind 一键集群 + 负载均衡/滚动更新/探针/Ingress 演示）]]

### 来源

- [[sources/Kubernetes 学习来源|Kubernetes 学习来源（官方文档/教程/书籍/社区）]]

## CPU 体系架构

### 概念
- [[concepts/CPU 核心架构|CPU 核心架构]]
- [[concepts/CPU 内存模型与大页|CPU 内存模型与大页]]
- [[concepts/CPU 指令集加速|CPU 指令集加速：网络数据面专用指令]]
- [[concepts/CPU Cache 高级优化|CPU Cache 高级优化：CAT/RDT/预取]]
- [[concepts/CPU 虚拟化与IO穿透|CPU 虚拟化与 I/O 穿透]]
- [[concepts/CPU 功耗与RAPL|CPU 功耗与 RAPL]]
- [[concepts/CPU 微架构内部|CPU 微架构内部（ROB/端口/μOP）]]
- [[concepts/CPU 互联拓扑|CPU 互联拓扑（UPI/CXL/延迟 Map）]]

### 实体
- [[entities/CPU 性能分析实战|CPU 性能分析实战]]
- [[entities/CPU 隔离与实时调优|CPU 隔离与实时调优]]
- [[entities/CPU 中断与MSI-X|CPU 中断模型与 MSI-X 亲和]]

### 综述
- [[synthesis/CPU 架构对比 x86与ARM|CPU 架构对比：x86 vs ARM]]

## 视频后期制作

### 综述

- [[synthesis/video-editing-pipeline|视频后期制作流水线全景]]

### 概念

- [[concepts/offline-online-workflow|离线/在线编辑工作流]]
- [[concepts/proxy-workflow|代理工作流]]
- [[concepts/split-edits-j-cut-l-cut|分切编辑 J-Cut / L-Cut]]
- [[concepts/color-grading-workflow|色彩管理管线与调色工作流]]
- [[concepts/audio-post-production-pipeline|音频后期制作管线]]
- [[concepts/mezzanine-codec|中间编解码器（Mezzanine Codec）]]
- [[concepts/delivery-codec|交付编解码器（Delivery Codec）]]
- [[concepts/narrative-psychology-editing|剪辑的叙事心理学]]
- [[concepts/advanced-motion-graphics|动态图形进阶 — After Effects 实践]]
- [[concepts/audio-repair-practical|音频修复实战]]
- [[concepts/color-theory-looks|色彩理论与调色方案实战]]
- [[concepts/titling-localization|字幕、图形与本地化]]
- [[concepts/video-specs-compatibility|视频规格与兼容性]]
- [[concepts/editor-career-path|剪辑师职业发展]]

### 实体

- [[entities/davinci-resolve|DaVinci Resolve]]
- [[entities/adobe-premiere-pro|Adobe Premiere Pro]]
- [[entities/apple-final-cut-pro|Apple Final Cut Pro]]
- [[entities/avid-media-composer|Avid Media Composer]]
- [[entities/capcut|CapCut（剪映）]]
- [[entities/avid-pro-tools|Avid Pro Tools]]

### 来源

- [[sources/nle-comparison-larry-jordan|Larry Jordan NLE 对比]]
- [[sources/workflow-pipeline-shot-ai|Shotstack 离线/在线工作流]]
- [[sources/codec-guide-mpegflow|MpegFlow 编解码器指南]]
- [[sources/audio-post-forte-ai|Forte AI 音频后期指南]]
- [[sources/color-management-cinapex|Cinapex 色彩管理]]
- [[sources/film-cognition-plos-one|PLOS ONE 库里肖夫效应 fMRI 研究]]

## 电影导演

### 综述

- [[synthesis/film-directing-panorama|电影导演全景综述]]

### 概念

- [[concepts/three-act-structure|三幕剧结构]]
- [[concepts/nonlinear-narrative|非线性叙事]]
- [[concepts/mise-en-scene|场面调度]]
- [[concepts/film-lighting-techniques|布光技法]]
- [[concepts/color-psychology-in-film|色彩心理学]]
- [[concepts/directing-actors|表演指导]]
- [[concepts/film-production-workflow|制作流程]]
- [[concepts/director-approaches|导演方法论]]
- [[concepts/film-analysis-framework|拉片方法论]]
- [[concepts/composition-techniques|构图技术]]
- [[concepts/camera-angle-narrative|镜头角度叙事]]
- [[concepts/genre-directing-strategies|类型片策略]]
- [[concepts/short-film-directing|短片导演]]
- [[concepts/low-budget-filmmaking|低成本制作]]
- [[concepts/director-script-analysis|剧本分析]]
- [[concepts/director-dp-collaboration|导演-DP协作]]
- [[concepts/director-department-collaboration|部门协作]]
- [[concepts/on-set-directing|片场决策]]
- [[concepts/advanced-film-grammar|高级语法]]
- [[concepts/advanced-staging-blocking|群戏走位]]
- [[concepts/directing-with-sound|声音叙事]]
- [[concepts/director-rehearsal-methods|排练方法]]
- [[concepts/music-in-film-directing|音乐叙事]]
- [[concepts/film-movements|电影运动]]
- [[concepts/film-theory-essentials|电影理论]]
- [[concepts/festival-distribution|电影节发行]]
- [[concepts/performance-theory-adaptation|表演理论与改编]]
- [[concepts/masterclass-film-analysis|经典拉片分析]]
- [[concepts/documentary-directing|纪录片导演]]
- [[concepts/director-business-legal|商业法律]]
- [[concepts/camera-lens-decisions|摄影机与镜头]]
- [[concepts/tv-series-directing|电视剧导演方法]]
- [[concepts/animation-directing|动画导演方法]]
- [[concepts/experimental-cinema|实验电影与先锋导演]]
- [[concepts/director-color-signatures|导演色彩签名]]

### 实体

- [[entities/alfred-hitchcock|希区柯克]]
- [[entities/stanley-kubrick|库布里克]]
- [[entities/christopher-nolan|诺兰]]
- [[entities/bong-joon-ho|奉俊昊]]
- [[entities/kore-eda-hirokazu|是枝裕和]]
- [[entities/tarkovsky-andrei|塔可夫斯基]]
- [[entities/wong-kar-wai|王家卫]]
- [[entities/coen-brothers|科恩兄弟]]
- [[entities/spielberg-steven|斯皮尔伯格]]
- [[entities/kurosawa-akira|黑泽明]]
- [[entities/fellini-federico|费里尼]]
- [[entities/david-fincher|芬奇]]
- [[entities/quintin-tarantino|塔伦蒂诺]]
- [[entities/villeneuve-denis|维伦纽瓦]]
- [[entities/miyazaki-hayao|宫崎骏]]
- [[entities/hou-hsiao-hsien|侯孝贤]]
- [[entities/jia-zhangke|贾樟柯]]
- [[entities/ang-lee|李安]]
- [[entities/martin-scorsese|斯科塞斯]]
- [[entities/wes-anderson|韦斯·安德森]]
- [[entities/david-lynch|大卫·林奇]]
- [[entities/paul-thomas-anderson|PTA]]
- [[entities/apichatpong|阿彼察邦]]
- [[entities/godard-jean-luc|戈达尔]]
- [[entities/bergman-ingmar|伯格曼]]
- [[entities/park-chan-wook|朴赞郁]]
- [[entities/hamaguchi-ryusuke|滨口龙介]]
- [[entities/zhang-yimou|张艺谋]]
- [[entities/ozu-yasujiro|小津安二郎]]
- [[entities/edward-yang|杨德昌]]
- [[entities/bresson-robert|布列松]]
- [[entities/claire-denis|克莱尔·德尼]]
- [[entities/michael-haneke|哈内克]]
- [[entities/charlie-chaplin|查理·卓别林]]
- [[entities/francois-truffaut|弗朗索瓦·特吕弗]]
- [[entities/pedro-almodovar|佩德罗·阿莫多瓦]]
- [[entities/werner-herzog|沃纳·赫尔佐格]]
- [[entities/spike-lee|斯派克·李]]

### 来源

- [[sources/studiobinder-three-act-structure|StudioBinder 三幕剧结构]]
- [[sources/studiobinder-mise-en-scene|StudioBinder 场面调度]]
- [[sources/studiobinder-film-lighting|StudioBinder 布光]]
- [[sources/studiobinder-pre-production|StudioBinder 前期制作]]
- [[sources/human-libretexts-film-analysis|Human LibreTexts 电影分析]]
- [[sources/bang2write-nonlinear-narrative|Bang2Write 非线性叙事]]

### 参考

- [[50-reference/director-intro|导演基础]]
- [[50-reference/montage-techniques|蒙太奇技术]]
- [[50-reference/shot-sizing-axes-storyboard|镜头/景别/轴线/故事板]]

## 归档

- [[90-archive/]]

## db-decoder-ironhive

- [[projects/db-decoder-ironhive/db-decoder-ironhive|项目概述]]
- [[projects/db-decoder-ironhive/hive-protocol-analysis|Hive 协议分析]]
- [[projects/db-decoder-ironhive/decoder-track|解码器开发 Track]]
- [[projects/db-decoder-ironhive/hive-decoder-implementation|Hive 解码器实现]]

## nginx-module-examples（模块开发示例工程）

- [[projects/nginx-module-examples/README|示例工程总览 + 编译/运行配置]]
- [最小 nginx.conf（一键 -c 启动）](projects/nginx-module-examples/nginx.conf)
- [[entities/Nginx 模块开发实战|Nginx 模块开发实战（文档）]]
- [[concepts/Nginx 框架内部实现|Nginx 框架内部实现（原理）]]

## openssl-crypto-examples（加密示例工程）

- [[projects/openssl-crypto-examples/README|OpenSSL 示例工程（AES-GCM / HMAC / ECDHE / TLS / 国密 GmSSL）]]
- [[entities/OpenSSL_BoringSSL 开发集成实战|OpenSSL/BoringSSL 开发集成实战（文档）]]
- [[entities/国密 SM2_SM3_SM4 实战|国密 SM2/SM3/SM4 实战（含 GmSSL 示例）]]
- [[concepts/加密算法总览与分类|加密算法总览与分类（原理）]]
