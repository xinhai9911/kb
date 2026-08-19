---
title: 个人知识库（Personal Knowledge Base）
category: index
summary: >-
    主题化的 Markdown 笔记集合。Git 版本化，远端同步到 GitHub。
created: 2026-07-29
updated: 2026-07-29
sources: []
tags: [kb]
base_confidence: 0.7
lifecycle: reviewed
---

# 个人知识库（Personal Knowledge Base）

> 主题化的 Markdown 笔记集合。Git 版本化，远端同步到 GitHub。

## 地图

| 类别 | 目录 | 用途 |
|---|---|---|
| 索引 | [00-index/](00-index/) | 使用说明、标签字典 |
| 项目 | [10-projects/](10-projects/) | 进行中的项目笔记 |
| 协议 | [20-protocols/](20-protocols/) | 协议分析报告 |
| 片段 | [30-snippets/](30-snippets/) | 可复用的代码、命令、配置 |
| 想法 | [40-ideas/](40-ideas/) | 闪念、TODO、未成形 |
| 参考 | [50-reference/](50-reference/) | 速查、API、架构决策记录 (ADR) |
| 归档 | [90-archive/](90-archive/) | 已完成/不再活跃 |
| 来源蒸馏 | [50-reference/sources/](50-reference/sources/) | `Q:\常规书籍` / `Q:\芯片资料` 资料索引 |

## 双链示例

- 协议笔记：[[20-protocols/InfluxDB 2]]、[[20-protocols/HBase 2]]、[[20-protocols/Elasticsearch 2]]
- 项目笔记：[[10-projects/数据库 解码器]]、[[10-projects/训练]]

## 标签速查

详见 [00-index/tag-glossary.md](00-index/标签 术语表.md)。

## 最近更新
- 2026-08-19: 归拢知乎《vLLM 源码解读》剪藏 → 新增 [[Clippings/vLLM 系列（知乎）索引|vLLM（知乎）系列索引]]（1~7 篇：PagedAttention/架构/安装/组件初始化/调度/推理/LLaVA）：去重并规范文件名、统一补 frontmatter + 前后篇双链；登记入 [[索引|索引]]
- 2026-08-19: 归拢腾讯云《LLM 系列》剪藏 → 新增 [[Clippings/LLM 系列 索引|LLM 系列索引]]（第 2~20 篇共 19 篇）：补齐缺失的「二十：解读 DeepSeek-V4」篇；为 19 篇统一补 frontmatter（source/作者/发表日）+ 前后篇双链与系列导航；回链 Transformer/RAG/分词器/推理引擎等图谱笔记并登记入 [[索引|索引]]
- 2026-08-19: 推理引擎知识整理 —— 将 vLLM / SGLang / llama.cpp 相关推理框架知识统一归拢到 [[sources/推理引擎/|推理引擎]]：vLLM/SGLang/llama.cpp 深度解析与源码导读、推理引擎系列（原则/精通/选择/调优/监控）、大模型-引擎对照、PagedAttention/推测解码/分布式推理、引擎实体页(entities→sources/推理引擎)。全库 wikilink 路径随迁更新
- 2026-08-19: 推理引擎三件套补全（一）新增 [[sources/推理引擎/SGLang-Deep-Dive|SGLang 深度解析]]（RadixAttention/调度/内存/GPU/接口）、[[sources/推理引擎/llama.cpp-Deep-Dive|llama.cpp 深度解析]]（GGUF/量化/mmap/多后端/接口）、[[sources/推理引擎/vLLM 对外接口与运行参考|vLLM 对外接口与运行参考]]（端点/部署/显存/指标）；补全实体页回链并登记 llama.cpp 实体入索引
- 2026-08-19: 推理引擎三件套补全（二）新增 [[sources/推理引擎/SGLang 源码导读|SGLang 源码导读]]（模块地图 / MLA 融合 kernel / Rust 组件 / 分布式 launch）、[[sources/推理引擎/推理引擎 性能对照与基准|推理引擎 性能对照与基准]]（公开量级 + 自测方法论）；vLLM 接口参考补多模态与 LoRA，llama.cpp 深度解析补采样参数表 / 多模态 / RPC 多机
- 2026-08-17: 导入外部知识库 [[sources/LLMForEverybody/索引|LLMForEverybody]]（中文大模型知识体系，12 章 420+ 篇；已扁平并入 sources/ 并作好 Obsidian 双链：导航页汇总 12 章 + 英/俄译本索引 + 草稿，回链库内 Transformer/分词器/推理引擎/微调·LoRA/量化/RAG·Agent·MCP/评估/安全 等 32 篇既有笔记）

<!-- 手动维护：每次重要新增/更新追加一行，格式: - YYYY-MM-DD: [标题](path) -->
- 2026-06-10: 知识库初始化
- 2026-06-10: 迁入 5 个 HBase 笔记到 [[20-protocols/]]（静态分析、dropTable 报文、测试计划/执行、报告模板）
- 2026-06-11: 新增 [[50-reference/dlopen internal 内存]]（dlopen 内部内存动作详解：mmap、重定位、GOT/PLT、RELRO、TLS 全链路拆解）
- 2026-06-15: 新增 [[50-reference/NPP 定时器 机制]]（NPP flowtable 定时触发机制：PROCESS + INTERRUPT 两级架构、空闲判定、慢/快清理策略）
- 2026-07-13: 新增导演系列参考笔记到 [[50-reference/]]：[[50-reference/导演 入门]]（入门+ffmpeg秒点）、[[50-reference/蒙太奇 技巧]]（平行/积累/对比蒙太奇）、[[50-reference/镜头 尺寸 轴线 分镜]]（景别/轴线图+分镜模板）
- 2026-07-29: 蒸馏 `Q:\常规书籍` 与 `Q:\芯片资料` 到 [[50-reference/sources/]]（常规书籍 5 篇 + 芯片资料 9 篇，索引式笔记，保留原文路径便于回查）
- 2026-07-29: 新增 VPP 网络数据面笔记：[[20-protocols/VPP 2|VPP 知识]]（向量化节点图架构、缓冲管理、多线程模型）+ [[50-reference/VPP 用法|VPP 使用方法]]（startup.conf、CLI 命令、抓包调试、运维）+ [[50-reference/VPP 插件 开发|VPP 插件开发]]（自定义 node/plugin、Process Node 协程、CMake 构建、加载调试）+ [[50-reference/VPP 插件 性能|VPP 插件性能调优]]（批处理范式、无锁多核、巨页缓冲、瓶颈定位、NPP 实战）
- 2026-07-29: 新增 [[50-reference/NPP 流表 清理 示例|NPP 流表清理代码实例]]（三级协作完整可编译骨架：clear-process 定时调度 + cleaner 中断执行 + try_cleanup slow/fast 双策略，per-thread 无锁、exapi del_handler 解耦）
- 2026-07-29: 新增 [[50-reference/NPP 流表 性能 测试|NPP 流表性能测试实例]]（四类用例：基线转发/空闲清理开销/满表 fast_cleanup 回收/多核无锁扩展，观测 show cpu·runtime·errors，含结果表与判定标准）
- 2026-07-29: 增加 CI 链接校验：`.github/workflows/check-links.yml`（push/PR 时跑 `scripts/check-links.js`，校验 wikilink 与目录链接，可选 `--check-external` 验外链可达性）
- 2026-07-29: 新增 FPGA 知识库：[[20-protocols/FPGA 2|FPGA 知识]]（LUT/FF/BRAM/DSP 架构、RTL→仿真→综合→实现→比特流全流程、VHDL/Verilog 对比、时序/CDC、与 ASIC/CPU/GPU 取舍）+ [[50-reference/FPGA 用法|FPGA 使用方法]]（iverilog/Verilator/GHDL 仿真、Vivado/Quartus 综合上板、CDC 同步器、Makefile 流程，引用本地 Q:/AI/vhdl_examples）
- 2026-07-29: 扩充 FPGA 知识库（丰富化）：+ [[20-protocols/FPGA 设计 模式|RTL 设计模式]]（FSM/流水线/同步·异步FIFO/握手/AXI-S/仲裁器，含可综合代码）+ [[50-reference/FPGA 验证|FPGA 验证方法]]（自检查 testbench/SVA 断言/功能覆盖率/约束随机/Verilator CI）+ [[entities/FPGA 厂商|FPGA 厂商与开源工具链]]（AMD/Intel/Lattice/Microchip 选型 + Yosys/nextpnr/SymbiFlow）；主篇 fpga.md 增「深入主题」（时序收敛/SoC 软核/部分重配置/功耗面积权衡）并全量双链
- 2026-08-12: 新增 [[concepts/容器原理与运行时|容器原理与运行时]]（容器不是虚拟化：三大内核基石 Namespace/Cgroups/OverlayFS、OCI 镜像分层、运行时栈 docker→containerd→runc、单容器到分布式编排的衔接，并全量双链到 K8s/分布式系统基础/Cilium 等既有笔记）
- 2026-08-12: 新增 [[entities/容器实战|容器实战]]（docker/podman/nerdctl/ctr 工具选型、多阶段镜像构建与 Dockerfile 优化、日常命令速查、namespace/cgroup/网络/OOM 排障、docker→K8s 心智切换 crictl/kubectl，回扣容器原理）
- 2026-08-12: 新增 [[concepts/容器安全|容器安全]]（4C 威胁模型、内核隔离非安全边界、Capabilities/seccomp/AppArmor+SELinux/Rootless+userns 降权、镜像供应链 SBOM+cosign 签名、PodSecurity/Falco 运行时检测、securityContext 速查模板，全量双链）
- 2026-08-12: 新增 [[synthesis/容器分布式技术全景综述|容器分布式技术全景综述]]（入口地图：内核基石→镜像/运行时→实战→安全→K8s 编排→分布式支柱的分层架构图、由底向上学习路径、常见误区、入门/进阶/深入速通路线，全量双链汇总全库容器与分布式笔记）
- 2026-08-12: 新增 [[entities/容器可观测落地|容器可观测落地]]（容器日志管道 stdout→DaemonSet→Loki、cAdvisor 容器资源 + kube-state-metrics 对象状态 + Prometheus kubernetes_sd、OTel 跨 Pod 追踪与 context 传播、RED+USE 排障闭环与 kubectl 速查，回扣 cgroups/OOM）
- 2026-08-12: 新增 [[entities/Kubernetes 网络实战|Kubernetes 网络实战]]（厂商中立：网络模型三约定、Service 四类型 + Headless、CoreDNS 服务发现、Ingress 七层入口、NetworkPolicy 零信任、Pod/Service/DNS 不通排障清单 + netshoot 抓包，补充到既有 K8s 实体笔记）
- 2026-08-12: 缺口补全①：新增 [[concepts/Kafka 消息队列与流处理]]（事件驱动支柱：分区/offset/Consumer Group、追加写日志为何快、ISR/acks/Exactly-once/KRaft、位移与再均衡、RabbitMQ·Pulsar 对比、Kafka Streams、Strimzi 上 K8s；回链 架构风格演进/微服务拆分/分布式系统基础），并补回链到 架构风格演进/微服务拆分实战
