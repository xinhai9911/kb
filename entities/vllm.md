---
title: vLLM 推理引擎
tags: [llm, inference-engine, vllm, pagedattention, serving, active]
lifecycle: active
category: entity
base_confidence: 0.85
created: 2026-08-17
updated: 2026-08-17
summary: >-
  vLLM：高性能 LLM 推理和服务引擎，核心创新 PagedAttention 实现高效 KV Cache 管理，
  支持 Continuous Batching、Prefix Caching、FP8 量化、张量并行，是当前最流行的开源推理引擎。
---

# vLLM 推理引擎

> **一句话**：vLLM = PagedAttention + Continuous Batching + 开箱即用的 LLM 服务化，当前最流行的开源 LLM 推理引擎。

## 定位

| 维度 | 说明 |
|------|------|
| **定位** | 高吞吐、低延迟的 LLM 推理和服务引擎 |
| **核心创新** | PagedAttention（分页注意力） |
| **语言** | Python + C++/CUDA |
| **许可证** | Apache 2.0 |
| **GitHub** | github.com/vllm-project/vllm |
| **官网** | vllm.ai |

## 核心架构

```
┌──────────────────────────────────────────┐
│              API Server (OpenAI 兼容)     │
├──────────────────────────────────────────┤
│          Scheduler（调度器）              │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  │
│  │ Waiting  │→│ Running  │→│Swapped │  │
│  │  Queue   │  │  Queue   │  │ Queue  │  │
│  └─────────┘  └──────────┘  └────────┘  │
├──────────────────────────────────────────┤
│       Block Manager（块管理器）           │
│  ┌──────────────────────────────────┐    │
│  │  PagedAttention KV Cache Store   │    │
│  │  Block Table: Logical→Physical   │    │
│  └──────────────────────────────────┘    │
├──────────────────────────────────────────┤
│       Model Runner（模型执行器）          │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  │
│  │ Attention│  │  MLP     │  │  All   │  │
│  │ (FA/PA)  │  │ (Fused)  │  │ Layers │  │
│  └─────────┘  └──────────┘  └────────┘  │
├──────────────────────────────────────────┤
│       Worker（多 GPU 并行）               │
│  Worker 0 │ Worker 1 │ ... │ Worker N    │
└──────────────────────────────────────────┘
```

## 核心特性

### 1. PagedAttention（分页注意力）

传统 KV Cache 为每个序列预分配最大长度的连续内存，导致严重的内存碎片和浪费。PagedAttention 借鉴 OS 虚拟内存，将 KV Cache 分成固定大小的**块（block）**，按需分配：

| 维度 | 传统方式 | PagedAttention |
|------|----------|----------------|
| 内存分配 | 预分配连续最大长度 | 按需分配固定块 |
| 内存浪费 | 40-80%（碎片+预留） | <4%（仅末尾块浪费） |
| 共享 KV | 不支持 | Copy-on-Write 共享 |
| 序列合并 | 不支持 | Prefix Caching |

```python
# vLLM 使用示例
from vllm import LLM, SamplingParams

# 初始化引擎（自动启用 PagedAttention）
llm = LLM(
    model="meta-llama/Llama-3-8B-Instruct",
    tensor_parallel_size=1,        # GPU 数量
    max_model_len=8192,            # 最大上下文长度
    gpu_memory_utilization=0.9,    # GPU 内存利用率
    block_size=16,                 # KV Cache 块大小
)

# 推理
prompts = ["Hello, how are you?", "Explain quantum computing"]
sampling_params = SamplingParams(temperature=0.7, max_tokens=512)
outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    print(output.outputs[0].text)
```

### 2. Continuous Batching（连续批处理）

传统静态批处理等待整个批次完成后才处理新请求。vLLM 的连续批处理在每个**解码步骤**后都可以插入新请求或移除已完成的请求：

| 维度 | 静态批处理 | 连续批处理 |
|------|------------|------------|
| 请求调度 | 整批进整批出 | 逐请求调度 |
| GPU 利用率 | 低（短请求等长请求） | 高（随时填充） |
| 吞吐量 | 1-3x | 3-10x |
| 延迟 | 高（等待最长序列） | 低（完成即返回） |

### 3. Prefix Caching（前缀缓存）

自动检测多个请求的公共前缀，共享 KV Cache，避免重复计算：

```python
# 场景：多个请求共享相同的 system prompt
system_prompt = "You are a helpful assistant. ...（1000 tokens）"

# 请求1: system_prompt + "What is AI?"
# 请求2: system_prompt + "What is ML?"
# 请求3: system_prompt + "What is NLP?"

# vLLM 自动缓存 system_prompt 的 KV Cache
# 请求2、3 直接复用，无需重新计算 1000 tokens
```

### 4. 结构化输出（Guided Decoding）

支持 JSON Schema、正则表达式等约束解码：

```python
from vllm import SamplingParams

# JSON Schema 约束
sampling_params = SamplingParams(
    guided_json={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "skills": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["name", "age"]
    }
)

# 正则表达式约束
sampling_params = SamplingParams(
    guided_regex=r"\d{3}-\d{4}-\d{4}"  # 电话号码格式
)

# 选择列表约束
sampling_params = SamplingParams(
    guided_choice=["positive", "negative", "neutral"]
)
```

### 5. 多 GPU 并行

| 并行策略 | 说明 | 适用场景 |
|----------|------|----------|
| **张量并行 (TP)** | 将模型层切分到多 GPU | 单模型跨多 GPU |
| **流水线并行 (PP)** | 将模型层分配到不同 GPU | 超大模型 |
| **专家并行 (EP)** | MoE 专家分布在不同 GPU | MoE 模型（DeepSeek 等） |

```bash
# 张量并行：4 GPU 运行 70B 模型
vllm serve meta-llama/Llama-3-70B-Instruct \
    --tensor-parallel-size 4 \
    --max-model-len 4096

# 流水线并行：2 节点各 4 GPU
vllm serve deepseek-ai/DeepSeek-V3 \
    --pipeline-parallel-size 8 \
    --tensor-parallel-size 1
```

### 6. 量化支持

| 量化方法 | 精度 | 速度提升 | 内存节省 | 说明 |
|----------|------|----------|----------|------|
| **FP8** | W8A8 | 1.5-2x | 50% | Hopper+ 原生支持 |
| **AWQ** | W4A16 | 2-3x | 75% | 激活感知权重量化 |
| **GPTQ** | W4A16 | 2-3x | 75% | 基于 Hessian 的量化 |
| **SqueezeLLM** | W4A16 | 2-3x | 75% | 非均匀量化 |
| **BitsAndBytes** | W4/W8 | 1.5-2x | 50-75% | 动态量化 |

```bash
# AWQ 量化模型
vllm serve TheBloke/Llama-2-7B-Chat-AWQ \
    --quantization awq \
    --max-model-len 4096

# FP8 量化（H100/H200）
vllm serve meta-llama/Llama-3-8B-Instruct \
    --quantization fp8 \
    --dtype float16
```

## 部署方式

### 方式一：OpenAI 兼容 API 服务

```bash
# 启动服务（兼容 OpenAI API）
vllm serve meta-llama/Llama-3-8B-Instruct \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 4096

# 客户端调用（与 OpenAI SDK 兼容）
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3-8B-Instruct",
    "prompt": "Hello, how are you?",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

### 方式二：Python 库直接调用

```python
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-3-8B-Instruct")
outputs = llm.generate(["Hello"], SamplingParams(max_tokens=100))
```

### 方式三：Docker 部署

```bash
docker run --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3-8B-Instruct \
  --max-model-len 4096
```

## 性能基准

### 吞吐量对比（Llama-2-7B, A100 80GB）

| 引擎 | Throughput (tokens/s) | 相对性能 |
|------|:---------------------:|:--------:|
| **vLLM** | ~2500 | 1.0x (baseline) |
| HuggingFace TGI | ~1800 | 0.72x |
| TensorRT-LLM | ~3000 | 1.2x |
| SGLang | ~2600 | 1.04x |

> 注：性能随配置、硬件、工作负载变化，以上为典型参考值。

## 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--tensor-parallel-size` | 1 | 张量并行 GPU 数 |
| `--max-model-len` | 模型默认 | 最大上下文长度 |
| `--gpu-memory-utilization` | 0.9 | GPU 内存利用率 |
| `--block-size` | 16 | KV Cache 块大小 |
| `--max-num-seqs` | 256 | 最大并发序列数 |
| `--max-num-batched-tokens` | 8192 | 最大批处理 token 数 |
| `--enable-prefix-caching` | False | 启用前缀缓存 |
| `--quantization` | None | 量化方法 |
| `--dtype` | auto | 数据类型 |
| `--enforce-eager` | False | 强制 eager 模式（禁用 CUDA Graph） |

## 已知限制

- 不支持 speculative decoding（vLLM v0.6+ 已支持，见 [PR](https://github.com/vllm-project/vllm/pull/6994)）
- MoE 模型的专家并行仍在完善中
- 部分新模型支持可能滞后于 HuggingFace Transformers

## 延伸

- → [[推理 引擎 选择]] — 推理引擎选型对比
- → [[LLM 推理 优化]] — 推理优化技术总论
- → [[entities/tensorrt-llm|TensorRT-LLM]] — NVIDIA 官方推理引擎
- → [[entities/sglang|SGLang]] — 高性能推理引擎（RadixAttention）
- → [[concepts/speculative-decoding|推测解码]] — 推测解码加速技术

---

**参考来源**：
- [vLLM 官方文档](https://docs.vllm.ai/)
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [PagedAttention 论文](https://arxiv.org/abs/2309.06180)

**最后更新**：2026-08-17
**维护者**：Claudian
**状态**：活跃维护中