---
title: "MindSpore Transformers 整体架构（官方文档 r1.8.0）"
tags: [mindspore, ascend, llm, inference, training, official-docs, active]
lifecycle: active
category: reference
base_confidence: 0.85
created: 2026-08-17
updated: 2026-08-17
summary: >-
  MindSpore Transformers r1.8.0 官方文档"整体架构"页面：概述、模块组成（训推调度/注册配置层/模型库/数据集/训练组件/工具层/DFX）、
  Mcore 模型架构、训练能力（多维并行/HuggingFace 生态/权重易用性/高可用/迁移）、推理能力（生态融合/南向优化/量化/vLLM 服务化）。
source: https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/introduction/overview.html
---

# MindSpore Transformers 整体架构（官方文档 r1.8.0）

> 📄 本文档抓取自 MindSpore Transformers v1.8.0 官方文档，作为参考归档。

## 概述

MindSpore Transformers 北向既支持昇腾自有技术栈，也积极拥抱开源社区。用户可将其集成在自有训推平台或者开源组件中：

1. **训练平台**：MindCluster、第三方平台
2. **服务化组件**：vLLM
3. **社区**：魔乐社区、Hugging Face

MindSpore Transformers 南向基于昇思+昇腾的大模型技术栈，利用昇思框架结合 CANN 对昇腾硬件进行亲和优化，提供高性能的模型训推体验。

## 模块组成

MindSpore Transformers 主要分为如下模块：

| 模块 | 职责 |
|------|------|
| **训推统一调度** | 提供启动脚本 `msrun_launcher.sh`，统一执行与调度套件内所有模型的分布式训推流程 |
| **注册/配置层** | 按接口类型实现类工厂，使能高阶接口层按配置初始化对应的任务接口、模型接口 |
| **大模型模型库** | 提供高性能大模型库以及基础 Transformer 接口，既可支持用户配置化构建自有模型，也可自定义开发 |
| **数据集** | 封装大模型训练、微调任务的数据加载接口，支持 Hugging Face 数据集、Megatron 数据集以及 MindRecord 数据集 |
| **训练组件** | 提供训练流程的基础接口，包含学习率策略、优化器、训练回调以及训练包装接口等 |
| **工具层** | 提供数据预处理、Hugging Face 权重互转、评测工具脚本 |
| **DFX（Design for X）** | 实现故障诊断、故障监测等高可用特性，降低训练故障恢复成本 |

## 模型架构

MindSpore Transformers 在 1.6.0 版本之后应用了全新的模型架构：

- **Legacy 架构**（旧）：各模型单独实现一份模型代码，较难维护与优化
- **Mcore 架构**（新）：对通用 Transformer 架构大模型进行分层抽象与模块化实现

### Mcore 分层设计

```
┌─────────────────────────────────────────┐
│  模型统一接口  GPTModel (General PreTrained) │
├─────────────────────────────────────────┤
│  MoELayer / TransformerBlock           │
├─────────────────────────────────────────┤
│  基础层  Linear / Embedding / Norm      │
└─────────────────────────────────────────┘
```

所有模块化接口基于 MindSpore 提供的并行能力，进行了深度并行优化，对外提供开箱即用的高性能接口，支持通过 **ModuleSpec 机制**自由组合进行模型搭建。

## 训练能力

MindSpore Transformer 提供高效、稳定、易用的大模型训练能力，覆盖预训练和微调场景。

### 多维混合并行训练

支持多种并行策略的灵活组合：

| 并行策略 | 说明 |
|----------|------|
| 数据并行 | Data Parallel |
| 模型并行 | Model Parallel |
| 优化器并行 | Optimizer Parallel |
| 流水线并行 | Pipeline Parallel |
| 序列并行 | Sequence Parallel |
| 上下文并行 | Context Parallel |
| MoE 专家并行 | Mixture of Experts Parallel |

### 主流开源生态支持

**预训练阶段**：
- 支持直接加载 Megatron-LM 多源混合数据集
- 减少跨平台和框架的数据集迁移成本

**微调阶段**（深度接入 Hugging Face 生态）：
- 使用 Hugging Face SFT 数据集
- 使用 Hugging Face Tokenizer 进行数据预处理
- 读取 Hugging Face 模型配置实例化模型
- 加载原生 Hugging Face Safetensors 权重

配合零代码、配置化使能低参微调的能力，实现高效便捷微调。

### 模型权重易用性

- 支持分布式权重自动切分与加载
- 无需手动转换权重
- 显著降低在分布式策略切换、集群扩缩容等场景下的调试复杂度

### 训练高可用保障

| 特性 | 说明 |
|------|------|
| 训练状态监控 | 实时监控训练状态 |
| 故障快恢 | 快速故障恢复 |
| 异常跳过 | 跳过异常数据/步骤 |
| 断点续训 | 从 checkpoint 恢复训练 |

### 模型低门槛迁移

- 封装了高性能基础接口，接口设计与 Megatron-LM 对齐
- 提供模型迁移指南和精度比对教程
- 支持昇腾工具链 Cell 级 dump 调试能力
- 实现低门槛、高效率的模型迁移与构建

## 推理能力

MindSpore Transformers 构建了"北向生态融合、南向深度优化"的推理体系。

### 北向生态融合

#### Hugging Face 生态复用

- 支持直接加载使用 Hugging Face 开源模型的配置文件、权重和 Tokenizer
- 实现配置即用、一键启动推理
- 降低迁移与部署门槛

#### 对接 vLLM 服务化框架

- 支持对接 vLLM 服务化框架，实现推理服务化部署
- 支持 **Continuous Batch**、**Prefix Cache**、**Chunked Prefill** 等核心特性
- 显著提升吞吐与资源利用率

#### 量化推理

- 依托 MindSpore Golden-Stick 量化套件提供的量化算法
- Legacy 模型已支持：**A16W8**、**A8W8**、**A8W4** 量化推理
- Mcore 模型预计在下一版本中支持 A8W8 与 A8W4 量化推理

#### 开源榜单评测

- 通过 AISbench 评测套件，可对基于 vLLM 部署的模型进行评测
- 覆盖 CEval、GSM8K、AIME 等 20+ 主流榜单

### 南向深度优化

#### 算子多级流水下发

依靠 MindSpore 框架 Runtime 运行时能力，在 Host 侧将算子调度拆分成三个任务进行流水线式下发：

1. **InferShape** — 推断输出张量形状
2. **Resize** — 内存分配
3. **Launch** — 算子执行

充分发挥 Host 多线程并行优势，提升算子下发效率，降低推理延迟。

#### 动静结合的执行模式

- 默认采用 **PyNative 编程模式** + **JIT 即时编译**技术
- 将模型编译成静态计算图进行推理加速
- 同时支持一键切换至 PyNative 动态图模式便于开发调试

#### 昇腾高性能算子加速

支持使用以下算子接口，在昇腾底座上实现高效推理性能：

| 算子接口 | 说明 |
|----------|------|
| **ACLNN** | 昇腾算子调用接口 |
| **ATB** | Attention Transformer Boost，注意力加速 |
| **MindSpore 融合算子** | 框架内置高性能融合算子 |

## 相关链接

- 官方文档：https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/introduction/overview.html
- 模型库：https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/introduction/models.html
- 安装指南：https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/installation.html
- 训练指南：https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/guide/llm_training.html
- 推理指南：https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/guide/inference.html
- 服务化部署：https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/guide/deployment.html

## 知识关联

- → [[entities/mindspore-transformers]] — MindFormers 套件详解（模型库/架构/安装）
- → [[concepts/ascend-software-stack]] — 昇腾全栈架构（CANN/MindSpore/MindIE 分层）
- → [[llm-inference-optimization]] — 推理优化总论

---

**抓取时间**：2026-08-17
**文档版本**：r1.8.0
**维护者**：Claudian