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

## 项目

- [[10-projects/database-decoder|database-decoder]]
- [[10-projects/training|training]]

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
- [[projects/nginx-module-examples/nginx.conf|最小 nginx.conf（一键 -c 启动）]]
- [[entities/Nginx 模块开发实战|Nginx 模块开发实战（文档）]]
- [[concepts/Nginx 框架内部实现|Nginx 框架内部实现（原理）]]

## openssl-crypto-examples（加密示例工程）

- [[projects/openssl-crypto-examples/README|OpenSSL 示例工程（AES-GCM / HMAC / ECDHE / TLS / 国密 GmSSL）]]
- [[entities/OpenSSL_BoringSSL 开发集成实战|OpenSSL/BoringSSL 开发集成实战（文档）]]
- [[entities/国密 SM2_SM3_SM4 实战|国密 SM2/SM3/SM4 实战（含 GmSSL 示例）]]
- [[concepts/加密算法总览与分类|加密算法总览与分类（原理）]]

## 本地 PDF 资料

- [[sources/pdf-index|PDF 资料索引总表]]
- [[sources/pdf-intel|Intel/AMD CPU 架构与优化]]
- [[sources/pdf-chips|交换芯片与网络硬件]]
- [[sources/pdf-hoststack|Hoststack/DPDK/VPP 网络]]
- [[sources/pdf-books|技术书籍 PDF 索引]]
