---
summary: >-
    *This index is automatically maintained. Last updated: 2026-07-29*
category: index
title: Wiki Index
base_confidence: 0.9
lifecycle: reviewed
created: 2026-07-29
tags: [kb]
updated: 2026-07-29
---

# Wiki Index

*This index is automatically maintained. Last updated: 2026-07-29*

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

## 归档

- [[90-archive/]]

## db-decoder-ironhive

- [[projects/db-decoder-ironhive/db-decoder-ironhive|项目概述]]
- [[projects/db-decoder-ironhive/hive-protocol-analysis|Hive 协议分析]]
- [[projects/db-decoder-ironhive/decoder-track|解码器开发 Track]]
- [[projects/db-decoder-ironhive/hive-decoder-implementation|Hive 解码器实现]]
