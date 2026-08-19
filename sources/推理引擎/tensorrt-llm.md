---
title: TensorRT-LLM 推理引擎
tags: [llm, inference-engine, nvidia, tensorrt, tensorrt-llm, active]
lifecycle: active
category: entity
base_confidence: 0.82
created: 2026-08-17
updated: 2026-08-17
summary: >-
  NVIDIA TensorRT-LLM：基于 TensorRT 的高性能 LLM 推理引擎，深度优化 NVIDIA GPU（Hopper/Blackwell），
  支持 FP8/INT4 量化、In-flight Batching、Paged KV Cache、多 GPU 张量/流水线并行。
---

# TensorRT-LLM 推理引擎

> **一句话**：TensorRT-LLM = NVIDIA GPU 上的极致推理优化，图优化 + 融合算子 + FP8，追求单卡最高性能。

## 定位

| 维度 | 说明 |
|------|------|
| **定位** | NVIDIA GPU 上的极致 LLM 推理优化 |
| **核心优势** | 深度 GPU 亲和、图优化、融合算子 |
| **语言** | C++/Python |
| **许可证** | Apache 2.0 |
| **GitHub** | github.com/NVIDIA/TensorRT-LLM |
| **前置依赖** | TensorRT、CUDA、cuDNN、NCCL |

## 核心架构

```
┌──────────────────────────────────────────┐
│            Triton Inference Server        │
│        （可选，用于生产服务化）              │
├──────────────────────────────────────────┤
│           TensorRT-LLM Runtime            │
│  ┌──────────────┐  ┌──────────────────┐  │
│  │  Engine Build │  │  Engine Execute  │  │
│  │  (离线编译)   │  │  (在线推理)      │  │
│  └──────────────┘  └──────────────────┘  │
├──────────────────────────────────────────┤
│           TensorRT Core                   │
│  ┌─────────┐ ┌────────┐ ┌────────────┐  │
│  │图优化    │ │算子融合 │ │CUDA Kernel │  │
│  │层融合    │ │Attention│ │Triton      │  │
│  │常量折叠  │ │MLP融合  │ │Custom      │  │
│  └─────────┘ └────────┘ └────────────┘  │
├──────────────────────────────────────────┤
│           CUDA / NCCL / NVLink           │
├──────────────────────────────────────────┤
│           NVIDIA GPU (Hopper/Blackwell)  │
└──────────────────────────────────────────┘
```

## 核心特性

### 1. 模型编译优化

TensorRT-LLM 的核心是**离线编译**：将模型转换为高度优化的推理引擎。

```bash
# 步骤1：转换 HF 权重为 TRT-LLM 格式
python convert_checkpoint.py \
    --model_dir ./Llama-3-8B-Instruct \
    --output_dir ./trt_ckpt \
    --dtype float16

# 步骤2：构建 TensorRT 引擎
trtllm-build \
    --checkpoint_dir ./trt_ckpt \
    --output_dir ./trt_engine \
    --gemm_plugin float16 \
    --max_batch_size 64 \
    --max_input_len 4096 \
    --max_seq_len 8192

# 步骤3：运行推理
python run.py \
    --engine_dir ./trt_engine \
    --max_output_len 256 \
    --tokenizer_dir ./Llama-3-8B-Instruct \
    --input_text "Hello, how are you?"
```

### 2. 图优化技术

| 优化技术 | 说明 | 性能提升 |
|----------|------|----------|
| **层融合** | 将多个小算子合并为大算子 | 10-30% |
| **常量折叠** | 编译时计算常量表达式 | 5-10% |
| **内核自动调优** | 自动选择最优 CUDA kernel | 10-20% |
| **精度校准** | FP8/INT8 量化校准 | 1.5-2x |
| **KV Cache 量化** | 降低 KV Cache 精度 | 30-50% 内存 |

### 3. In-flight Batching

TensorRT-LLM 的连续批处理实现，类似 vLLM 的 Continuous Batching：

```
时间步 T0:  [Request_A(100t)] [Request_B(50t)]
时间步 T1:  [Request_A(101t)] [Request_B(51t)] [Request_C(new)]
时间步 T2:  [Request_A(102t)] [Request_C(1t)]  ← Request_B 完成
时间步 T3:  [Request_C(2t)]  [Request_D(new)]  ← Request_A 完成
```

### 4. Paged KV Cache

与 vLLM 的 PagedAttention 类似，TensorRT-LLM 也实现了分页 KV Cache：

- 固定大小的 KV Cache 块
- 按需分配，减少内存浪费
- 支持 Copy-on-Write 共享

### 5. FP8 推理（Hopper/Blackwell）

H100+ GPU 的原生 FP8 支持，性能翻倍：

```bash
# FP8 量化构建
trtllm-build \
    --checkpoint_dir ./trt_ckpt \
    --output_dir ./trt_engine_fp8 \
    --use_weight_only \
    --weight_only_precision fp8 \
    --gemm_plugin fp8
```

| 精度 | 性能 (tokens/s) | 内存 | 质量损失 |
|------|:---------------:|:----:|:--------:|
| FP16 | 1.0x | 100% | 0 |
| FP8 | 1.8-2.0x | 50% | <0.5% |
| INT8 | 1.5-1.8x | 50% | <1% |
| INT4 | 2.5-3x | 25% | 1-3% |

### 6. 多 GPU 并行

```bash
# 8 GPU 张量并行
mpirun -n 8 python run.py \
    --engine_dir ./trt_engine \
    --max_output_len 256 \
    --tokenizer_dir ./Llama-3-70B-Instruct

# 流水线并行（跨节点）
mpirun -n 16 python run.py \
    --engine_dir ./trt_engine \
    --tensor_parallel_size 8 \
    --pipeline_parallel_size 2
```

## 与 vLLM 对比

| 维度 | TensorRT-LLM | vLLM |
|------|---------------|------|
| **单卡性能** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **易用性** | ⭐⭐（需编译） | ⭐⭐⭐⭐⭐ |
| **模型支持** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **生态丰富度** | ⭐⭐⭐（Triton 集成） | ⭐⭐⭐⭐⭐ |
| **量化支持** | FP8/INT4/INT8 | FP8/AWQ/GPTQ |
| **开发迭代** | 较慢 | 快 |
| **最佳场景** | 追求极致性能 | 快速部署、通用场景 |

## Triton 集成

TensorRT-LLM 通常与 NVIDIA Triton Inference Server 配合使用：

```bash
# 使用 Triton 部署
docker run --gpus all \
  -v /path/to/trt_engine:/models/llm \
  nvcr.io/nvidia/tritonserver:24.01-trtllm-python-py3 \
  tritonserver --model-repository=/models
```

## 延伸

- → [[sources/推理引擎/vllm|vLLM]] — 对比：通用推理引擎
- → [[推理 引擎 选择]] — 推理引擎选型对比
- → [[LLM 推理 优化]] — 推理优化技术总论
- → [[50-reference/sources/chips/gpu-ai-accelerator|GPU 与 AI 加速芯片架构]] — NVIDIA GPU 硬件背景

---

**参考来源**：
- [TensorRT-LLM 官方文档](https://nvidia.github.io/TensorRT-LLM/)
- [TensorRT-LLM GitHub](https://github.com/NVIDIA/TensorRT-LLM)

**最后更新**：2026-08-17
**维护者**：Claudian
**状态**：活跃维护中

---

## 📖 来源参考

- **LLMForEverybody**：[[sources/LLMForEverybody/索引#部署与推理|部署与推理（第02章）]]
> 来自 [luhengshiwo/LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody) 外部知识库导入
