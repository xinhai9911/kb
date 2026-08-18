大模型推理框架（六）SGLang

`SGLang`[1](#refer-anchor-1)是由UC Berkeley和Stanford的研究者开发的高性能大语言模型推理引擎。它以**RadixAttention（基数树注意力）**为核心创新，通过将所有请求的KV Cache组织为基数树结构，自动共享公共前缀，实现了极高的前缀复用效率。SGLang同时内置了强大的结构化生成支持（JSON/正则约束解码），并采用分裂式Prefill-Decode架构，在Agent、多轮对话和结构化输出等场景下表现优异。

## 1. 核心架构

SGLang的架构分为**前端（Frontend）**和**后端（Backend）**两部分：

```
┌──────────────────────────────────────────┐
│           SGLang Runtime                  │
├──────────────────────────────────────────┤
│  Frontend: SGLang 前端语言                │
│  ┌──────────────────────────────────┐    │
│  │  Python DSL + 程序结构化生成       │    │
│  │  JSON Schema / Regex 约束         │    │
│  └──────────────────────────────────┘    │
├──────────────────────────────────────────┤
│  Backend: 推理引擎                       │
│  ┌──────────────┐  ┌──────────────────┐  │
│  │ RadixAttention│  │ Continuous Batching│ │
│  │ (基数树 KV)   │  │ (连续批处理)       │  │
│  └──────────────┘  └──────────────────┘  │
├──────────────────────────────────────────┤
│  分裂式架构 (Disaggregated)               │
│  ┌──────────┐      ┌──────────────┐      │
│  │ Prefill  │ ───→ │    Decode     │      │
│  │ Instance │      │   Instance    │      │
│  └──────────┘      └──────────────┘      │
├──────────────────────────────────────────┤
│  CUDA / NCCL / NVLink                    │
└──────────────────────────────────────────┘
```

- **前端**：提供Python DSL（领域特定语言），支持编排复杂的推理流程，如多轮对话、Agent调用等；
- **后端**：基于RadixAttention的高效推理引擎，支持连续批处理和分裂式架构。

## 2. RadixAttention（基数树注意力）

RadixAttention是SGLang最核心的创新。传统推理引擎（如vLLM的Prefix Caching）采用线性缓存来复用前缀，而SGLang将所有请求的KV Cache组织为一棵**基数树（Radix Tree）**，实现自动的前缀共享：

```
Radix Tree 结构：

Root
├── [System Prompt] (1000 tokens)
│   ├── [User: What is AI?] → KV Cache A
│   ├── [User: What is ML?] → KV Cache B
│   └── [User: What is NLP?] → KV Cache C
├── [Other Prompt] (500 tokens)
│   └── [User: Hello] → KV Cache D
```

### RadixAttention vs vLLM Prefix Caching

| 维度 | vLLM Prefix Caching | SGLang RadixAttention |
|------|---------------------|----------------------|
| 数据结构 | 线性缓存 | 基数树 |
| 前缀匹配 | 精确匹配 | LRU 淘汰 + 树匹配 |
| 共享粒度 | 块级别 | Token 级别 |
| 适用场景 | 简单前缀复用 | 复杂多轮对话、Agent |

在多轮对话和Agent场景中，RadixAttention能够自动识别并复用大量公共前缀（如System Prompt），显著减少重复计算，降低首Token延迟（TTFT）。

## 3. 结构化生成（Guided Decoding）

SGLang内置了强大的结构化生成支持，可以直接在推理时约束输出格式：

```python
import sglang as sgl

@sgl.function
def chat_with_schema(s, question):
    s += sgl.system("You are a helpful assistant")
    s += sgl.user(question)
    s += sgl.assistant(
        sgl.gen(
            "answer",
            max_tokens=256,
            # 正则表达式约束
            regex=r'\{"name": "[^"]+", "age": \d+, "skills": \["[^"]+", ...\]\}'
        )
    )

# 或使用 Pydantic 模型
from pydantic import BaseModel

class PersonInfo(BaseModel):
    name: str
    age: int
    skills: list[str]

@sgl.function
def extract_info(s, text):
    s += sgl.user(f"Extract person info from: {text}")
    s += sgl.assistant(
        sgl.gen(
            "info",
            max_tokens=256,
            json_schema=PersonInfo  # JSON Schema 约束
        )
    )
```

支持**JSON Schema**和**正则表达式**两种约束方式，确保模型输出严格符合指定格式。

## 4. SGLang 前端语言

SGLang提供了一套Python DSL，用于编排复杂的推理流程：

```python
import sglang as sgl

@sgl.function
def multi_turn_qa(s, question, context):
    # 多轮对话
    s += sgl.system("You are a helpful assistant")
    s += sgl.system(f"Context: {context}")
    
    # 第一轮
    s += sgl.user(question)
    s += sgl.assistant(sgl.gen("answer1", max_tokens=256))
    
    # 基于第一轮结果的追问
    s += sgl.user(f"Tell me more about: {s['answer1']}")
    s += sgl.assistant(sgl.gen("answer2", max_tokens=256))

# 并行执行多个请求
states = multi_turn_qa.run_batch([
    {"question": "What is AI?", "context": "..."},
    {"question": "What is ML?", "context": "..."},
])
```

这种DSL风格使得复杂推理流程的编排变得非常直观，特别适合Agent和工作流场景。

## 5. 分裂式架构（Disaggregated Prefill-Decode）

SGLang原生支持将**Prefill（预填充）**和**Decode（解码）**分离到不同GPU上执行：

```
传统架构：
  GPU 0: [Prefill + Decode 混合] → 互相干扰

分裂式架构：
  GPU 0 (Prefill):  [快速处理输入 tokens] → KV Cache 传输
  GPU 1 (Decode):   [专注生成输出 tokens] → 高吞吐
```

| 维度 | 混合架构 | 分裂式架构 |
|------|----------|------------|
| GPU 利用率 | Prefill 和 Decode 争抢资源 | 各自专注，利用率高 |
| TTFT | 受 Decode 干扰 | 更低（Prefill 专用 GPU） |
| 吞吐量 | 一般 | 更高 |
| 复杂度 | 低 | 高（需 KV 传输） |

分裂式架构特别适合对首Token延迟（TTFT）有严格要求的场景。

## 6. 多GPU并行与部署

SGLang支持张量并行和分裂式部署：

```bash
# 张量并行（2 GPU）
python -m sglang.launch_server \
    --model-path meta-llama/Llama-3-8B-Instruct \
    --tp-size 2 \
    --port 30000

# 分裂式部署
python -m sglang.launch_server \
    --model-path meta-llama/Llama-3-8B-Instruct \
    --disaggregation-mla-chunk-prefill-size 32 \
    --port 30000
```

## 7. 与 vLLM 对比

| 维度 | SGLang | vLLM |
|------|--------|------|
| **前缀复用** | ⭐⭐⭐⭐⭐ (RadixAttention) | ⭐⭐⭐⭐ (Prefix Caching) |
| **结构化生成** | ⭐⭐⭐⭐⭐ (原生支持) | ⭐⭐⭐⭐ (Guided Decoding) |
| **易用性** | ⭐⭐⭐⭐ (SGLang DSL) | ⭐⭐⭐⭐⭐ (OpenAI API) |
| **模型支持** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **分裂式架构** | ⭐⭐⭐⭐⭐ (原生) | ⭐⭐ (开发中) |
| **社区活跃度** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **最佳场景** | Agent/多轮对话/结构化 | 通用服务化部署 |

## 参考

<div id="refer-anchor-1"></div>

[1] [SGLang Official Documentation](https://sgl-project.github.io/)

<div id="refer-anchor-2"></div>

[2] [SGLang GitHub](https://github.com/sgl-project/sglang)

<div id="refer-anchor-3"></div>

[3] [RadixAttention: Efficient Recognition for Large Vision Language Models](https://arxiv.org/abs/2312.07104)

## 欢迎关注我的GitHub和微信公众号[真-忒修斯之船]，来不及解释了，快上船！

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

仓库上有原始的Markdown文件，完全开源，欢迎大家Star和Fork！

---

## 📚 相关概念

[[concepts/LLM 推理 优化|LLM 推理 优化]] | [[concepts/推测解码|推测解码]] | [[concepts/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/vllm|vllm]] | [[entities/tensorrt-llm|tensorrt-llm]] | [[entities/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[concepts/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
