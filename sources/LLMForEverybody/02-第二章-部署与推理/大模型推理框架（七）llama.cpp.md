大模型推理框架（七）llama.cpp

`llama.cpp`[1](#refer-anchor-1)是由Georgi Gerganov创建的开源项目，旨在实现**纯CPU**运行Meta的LLaMA模型。它是本地LLM推理的先驱，推动了整个"在笔记本电脑上跑大模型"运动的兴起。llama.cpp的核心理念是**极简、跨平台、零GPU依赖**，任何人都可以在没有昂贵显卡的情况下运行大语言模型，同时通过GGUF量化格式和各种后端优化（CUDA、Metal、Vulkan、SYCL），在有GPU时也能获得优秀的加速效果。

## 1. 为什么需要 llama.cpp

在llama.cpp出现之前，运行大语言模型通常需要：

- 高端NVIDIA GPU（显存16GB+）
- 复杂的Python环境配置
- 大量的依赖库

llama.cpp改变了这一切：

```
传统方式：
  Python + PyTorch + CUDA + 多GB显存 → 门槛高

llama.cpp：
  一个二进制文件 + 量化后的模型 → 即装即用
```

## 2. 核心特性

### 2.1 GGUF 量化格式

GGUF（GPT-Generated Unified Format）是llama.cpp定义的模型格式，取代了早期的GGML格式。GGUF的特点：

- **单文件部署**：模型权重、元数据、分词器全部打包在一个文件中
- **内存映射**：支持mmap，无需将整个模型加载到内存
- **丰富的量化类型**：

| 量化类型 | 位宽 | 大小（7B模型） | 质量 | 速度 |
|---------|------|---------------|------|------|
| F16 | 16-bit | ~14GB | 原始 | 慢 |
| Q8_0 | 8-bit | ~7.5GB | 优 | 中 |
| Q6_K | 6-bit | ~5.5GB | 良 | 快 |
| Q5_K_M | 5-bit | ~5GB | 良 | 快 |
| Q4_K_M | 4-bit | ~4GB | 可用 | 快 |
| Q3_K_M | 3-bit | ~3GB | 一般 | 很快 |
| Q2_K | 2-bit | ~2.5GB | 差 | 最快 |

### 2.2 跨平台后端支持

llama.cpp支持多种计算后端，自动检测并选择最优方案：

```
┌─────────────────────────────────────────┐
│              llama.cpp                  │
├─────────────────────────────────────────┤
│  后端：                                  │
│  ├── CPU (默认, 所有平台)                │
│  ├── CUDA (NVIDIA GPU)                  │
│  ├── Metal (Apple Silicon M1/M2/M3/M4)  │
│  ├── Vulkan (跨平台 GPU)                │
│  ├── SYCL (Intel GPU)                   │
│  ├── MUSA (Moore Threads)               │
│  └── CANN (华为昇腾)                     │
└─────────────────────────────────────────┘
```

### 2.3 内存映射（mmap）

llama.cpp利用操作系统级内存映射技术，将模型文件直接映射到虚拟内存空间：

- 不需要将整个模型加载到RAM/VRAM
- 按需加载模型页（page）
- 支持超大模型在有限内存上运行
- 多个进程可以共享同一模型的内存映射

### 2.4 极简API

llama.cpp提供简洁的C/C++ API，也可通过绑定在其他语言中使用：

```cpp
// C++ 示例
#include "llama.h"

auto ctx = llama_init_from_file("model.bin", params);
llama_eval(ctx, tokens, n_tokens, 0, params);
// ... 获取生成的token
```

Python绑定（`llama-cpp-python`）：

```python
from llama_cpp import Llama

llm = Llama(model_path="./models/7b-q4_0.gguf", n_ctx=2048)
output = llm("Hello, world", max_tokens=100)
print(output["choices"][0]["text"])
```

## 3. 量化工作流

llama.cpp的典型量化流程：

```bash
# 1. 下载原始模型（HuggingFace格式）
git clone https://huggingface.co/meta-llama/Llama-2-7b-hf

# 2. 转换为GGUF格式
python convert_hf_to_gguf.py Llama-2-7b-hf --outfile llama-2-7b-f16.gguf

# 3. 量化（以Q4_K_M为例）
./quantize llama-2-7b-f16.gguf llama-2-7b-q4_k_m.gguf Q4_K_M

# 4. 运行推理
./llama-cli -m llama-2-7b-q4_k_m.gguf -p "What is AI?" -n 200
```

## 4. 服务模式

llama.cpp支持启动为HTTP服务器，提供兼容OpenAI的API接口：

```bash
# 启动服务
./llama-server \
    -m llama-2-7b-q4_k_m.gguf \
    --host 0.0.0.0 \
    --port 8080 \
    -ngl 33  # GPU加速层数

# 调用（兼容OpenAI API格式）
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-2-7b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 5. 与其他框架对比

| 维度         | llama.cpp | vLLM  | Ollama             | SGLang    |
| ---------- | --------- | ----- | ------------------ | --------- |
| **运行环境**   | CPU/GPU   | GPU   | CPU/GPU            | GPU       |
| **量化格式**   | GGUF      | 多种    | GGUF (底层llama.cpp) | 多种        |
| **跨平台**    | ⭐⭐⭐⭐⭐     | ⭐⭐    | ⭐⭐⭐⭐               | ⭐⭐        |
| **易用性**    | ⭐⭐⭐       | ⭐⭐⭐⭐  | ⭐⭐⭐⭐⭐              | ⭐⭐⭐⭐      |
| **GPU吞吐量** | ⭐⭐⭐       | ⭐⭐⭐⭐⭐ | ⭐⭐⭐                | ⭐⭐⭐⭐⭐     |
| **CPU推理**  | ⭐⭐⭐⭐⭐     | ❌     | ⭐⭐⭐⭐               | ❌         |
| **内存效率**   | ⭐⭐⭐⭐⭐     | ⭐⭐⭐⭐  | ⭐⭐⭐⭐               | ⭐⭐⭐⭐      |
| **最佳场景**   | 本地/边缘/离线  | 生产服务  | 个人助手               | Agent/结构化 |

## 6. llama.cpp 的生态

llama.cpp催生了大量下游项目和集成：

- **Ollama**：基于llama.cpp的简化封装，一键部署本地大模型
- **LM Studio**：GUI界面，底层使用llama.cpp
- **text-generation-webui**：Web界面，支持llama.cpp后端
- **Open WebUI**：兼容OpenAI API的Web界面
- **llama-cpp-python**：Python绑定，方便程序化调用
- **Cursor / Continue**：IDE集成，使用llama.cpp进行本地代码补全

## 参考

<div id="refer-anchor-1"></div>

[1] [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)

<div id="refer-anchor-2"></div>

[2] [llama.cpp Wiki](https://github.com/ggerganov/llama.cpp/wiki)

<div id="refer-anchor-3"></div>

[3] [GGUF 格式规范](https://github.com/ggerganov/llama.cpp/blob/master/docs/gguf.md)

## 欢迎关注我的GitHub和微信公众号[真-忒修斯之船]，来不及解释了，快上船！

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

仓库上有原始的Markdown文件，完全开源，欢迎大家Star和Fork！

---

## 📚 相关概念

[[concepts/LLM 推理 优化|LLM 推理 优化]] | [[concepts/推测解码|推测解码]] | [[concepts/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/vllm|vllm]] | [[entities/tensorrt-llm|tensorrt-llm]] | [[entities/sglang|sglang]] | [[entities/llama.cpp|llama.cpp]] | [[entities/Hugging Face|Hugging Face]] | [[concepts/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
