---
title: MindSpore Transformers 大模型套件
tags: [llm, inference, training, huawei, ascend, mindspore, active]
lifecycle: active
category: entity
base_confidence: 0.78
created: 2026-08-17
updated: 2026-08-17
summary: >-
  华为昇腾大模型全流程开发套件 MindSpore Transformers（MindFormers）：基于 MindSpore 框架 + 昇腾 NPU 的
  预训练/微调/推理/部署一站式方案，涵盖 Mcore 模型架构、HyperParallel 分布式并行、MindIE 推理引擎、vLLM 适配。
---

# MindSpore Transformers 大模型套件

> 华为昇腾生态的**大模型全家桶**——用 MindSpore 框架替代 PyTorch，在昇腾 NPU 上实现大模型从训练到部署的完整链路。

## 定位与生态

MindSpore Transformers（简称 MindFormers）定位为**大模型全流程开发套件**，覆盖：

```
数据预处理 → 预训练 → 微调 → 评测 → 推理 → 部署
```

在昇腾 AI 生态中的位置：

| 层 | 组件 | 类比 PyTorch 生态 |
|---|------|-------------------|
| **硬件** | Atlas 800T A2 / Atlas 900 A3 | NVIDIA GPU |
| **算子/驱动** | CANN（Compute Architecture for Neural Networks） | CUDA/cuDNN |
| **框架** | MindSpore（≥ 2.10） | PyTorch |
| **并行** | HyperParallel | DeepSpeed / Megatron-LM |
| **套件** | **MindSpore Transformers** | HF Transformers |
| **推理引擎** | MindIE（Mind Inference Engine） | vLLM / TensorRT-LLM |
| **服务化** | MindIE Service + vLLM-MindSpore 插件 | vLLM serving |

> 一句话：**MindFormers ≈ HF Transformers + DeepSpeed + vLLM，但只跑在昇腾上。**

## 架构：Mcore

从 v1.6.0 开始采用新架构 **Mcore**，替代旧的 Legacy 架构（各模型独立实现，难以维护）。

### 分层设计

```
┌─────────────────────────────────────────────┐
│  模型统一接口  GPTModel (General PreTrained) │  ← 顶层：统一 forward/generate
├─────────────────────────────────────────────┤
│  TransformerBlock / MoELayer                │  ← 中层：可组合的 Transformer 块
├─────────────────────────────────────────────┤
│  基础层  Linear / Embedding / Norm / Attn   │  ← 底层：模块化基础组件
├─────────────────────────────────────────────┤
│  并行层  HyperParallel (HSDP/PP/TP/DP)      │  ← 分布式并行
├─────────────────────────────────────────────┤
│  MindSpore Runtime + CANN 算子              │  ← 框架 + 算子加速
└─────────────────────────────────────────────┘
```

### 核心特性

| 特性 | 说明 |
|------|------|
| **模块化组合** | 通过 `ModuleSpec` 机制自由组合 Linear、Attention、MLP 等模块搭建自定义模型 |
| **开箱即用并行** | 所有模块内置并行支持（TP/PP/DP/SP），配置即生效 |
| **配置化构建** | YAML 配置文件驱动，无需改代码即可切换模型/规模/并行策略 |
| **混合精度** | FP16/BF16/FP8，自动 Loss Scaling |
| **算子加速** | 基于 ACLNN/ATB 的高性能融合算子 |

## 模型库

### LLM（大语言模型）

| 模型 | 规模 | 说明 |
|------|------|------|
| **LLaMA 系列** | 7B ~ 70B+ | Meta LLaMA / LLaMA 2 / LLaMA 3 |
| **Qwen 系列** | 7B ~ 72B | 阿里通义千问 |
| **DeepSeek** | V2/V3 | 深度求索 MoE |
| **ChatGLM** | 6B ~ 130B | 智谱 GLM |
| **Baichuan** | 7B ~ 13B | 百川智能 |
| **BLOOM** | 560M ~ 176B | BigScience |
| **Mistral/Mixtral** | 7B / 8x7B | Mistral AI |
| **GPT** | 多规模 | OpenAI GPT 系列 |
| **Gemma** | 2B / 7B | Google |

### 多模态

| 模型 | 说明 |
|------|------|
| **LLaVA** | 视觉语言模型 |
| **Qwen-VL** | 通义千问视觉 |
| **InternVL** | 上海 AI Lab |

### 基础 Transformer

| 模型 | 说明 |
|------|------|
| **BERT** | 双向编码器 |
| **T5** | 编码器-解码器 |
| **ViT** | Vision Transformer |

## 分布式并行

MindFormers 基于 **HyperParallel**（昇腾超节点亲和的分布式并行加速库）提供：

| 并行策略 | 说明 | 适用场景 |
|----------|------|----------|
| **DP**（Data Parallel） | 数据并行 | 通用 |
| **TP**（Tensor Parallel） | 张量并行 | 单层参数大 |
| **PP**（Pipeline Parallel） | 流水线并行（1F1B/VPP） | 模型层数多 |
| **SP**（Sequence Parallel） | 序列并行 | 长序列 |
| **ZeRO** | 优化器状态分片 | 显存受限 |
| **MoE** | 专家并行 | MoE 模型（DeepSeek 等） |

## 推理与部署

### MindIE（Mind Inference Engine）

昇腾高性能推理框架，MindFormers 承载在 MindIE LLM 层：

```
应用层：MindIE Service（服务化）
  ↓
推理层：MindIE LLM（加速）
  ↓
模型层：MindSpore Transformers（模型加载）
  ↓
算子层：ACLNN / ATB 融合算子
  ↓
硬件层：昇腾 NPU
```

### vLLM-MindSpore 插件

将 MindFormers 模型接入 vLLM 生态：
- 所有 Mcore 模型自动注册为 `MindFormersForCausalLM`
- 通过 `config.json` 的 `model_type` / `architectures` 自动匹配
- 支持 vLLM 的 PagedAttention、连续批处理等特性

### 部署方式

| 方式 | 说明 |
|------|------|
| **MindIE Service** | 华为官方推荐，一键部署脚本 |
| **vLLM + MindSpore 插件** | 兼容 vLLM API，适合已有 vLLM 基础设施 |
| **Docker 镜像** | 官方预构建镜像，开箱即用 |

## 安装与环境

### 软件配套关系

| 组件 | 版本要求 |
|------|----------|
| Python | 3.11.4+ |
| CANN | 与 MindSpore 版本对应 |
| MindSpore | ≥ 2.10 |
| MindFormers | 1.9.0（stable）/ 2.0.0（在研） |
| HyperParallel | 动态图训练必需 |

### 安装方式

```bash
# pip 安装（稳定版）
pip install mindformers==1.9.0

# 源码安装（master 最新特性）
git clone -b r1.9.0 https://atomgit.com/mindspore/mindformers.git
cd mindformers
bash build.sh

# Docker 镜像（开箱即用）
docker pull swr.cn-north-4.myhuaweicloud.com/ddn-8a41821f-e6ac-4e9a-956e-4e29f58397fc/mindformers:1.9.0
```

### 支持硬件

| 硬件 | 芯片 |
|------|------|
| Atlas 800T A2 | 昇腾 910B |
| Atlas 800I A2 | 昇腾 910B |
| Atlas 900 A3 SuperPoD | 昇腾 910C |

## 与 PyTorch 生态对比

| 维度 | MindFormers | HF Transformers + vLLM |
|------|-------------|------------------------|
| **硬件** | 仅昇腾 NPU | GPU 为主 |
| **框架** | MindSpore | PyTorch |
| **并行** | HyperParallel（HSDP/PP） | DeepSpeed / Megatron-LM |
| **推理** | MindIE + vLLM 插件 | vLLM / TensorRT-LLM |
| **模型更新** | 跟随主流，略有滞后 | 第一时间支持 |
| **社区** | 华为生态，国内为主 | 全球开源社区 |
| **生态丰富度** | 较封闭 | 极其丰富 |

### 选型建议

| 场景 | 推荐 |
|------|------|
| 昇腾 NPU 集群 | MindFormers（唯一选择） |
| NVIDIA GPU | PyTorch + HF Transformers |
| 国产化/信创 | MindFormers（昇腾）或 CANN 适配 |
| 快速原型 | HF Transformers（模型更新最快） |
| 大规模训练 | 昇腾集群 + MindFormers 或 GPU + DeepSpeed |

## 延伸

- → [[llm-inference-optimization]] — 推理优化总论（量化/蒸馏/加速框架）
- → [[inference-engine-selection]] — 推理引擎选型（vLLM/TGI/TensorRT-LLM 对比）
- → [[50-reference/sources/chips/gpu-ai-accelerator|GPU 与 AI 加速芯片架构]] — 昇腾硬件背景
- → [[concepts/transformer-architecture|Transformer 架构]] — MindFormers 的模型基础

---

**参考来源**：
- [MindSpore Transformers 官方文档](https://www.mindspore.cn/mindformers/docs/zh-CN/stable/introduction/overview.html)
- [昇腾社区 MindSpore Transformers 实践](https://www.hiascend.com/)
- [MindSpore Transformers AtomGit 仓库](https://atomgit.com/mindspore/mindformers)

**最后更新**：2026-08-17
**维护者**：Claudian
**状态**：活跃维护中