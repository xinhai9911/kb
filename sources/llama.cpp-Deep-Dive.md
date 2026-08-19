---
title: llama.cpp 深度解析
tags: [llm, inference-engine, llama-cpp, gguf, ggml, quantization, cpu, gpu, api, deep-dive]
created: 2026-08-19
updated: 2026-08-19
lifecycle: active
category: sources
base_confidence: 0.85
summary: >-
  从架构到实现深度解析 llama.cpp：ggml 计算图抽象、GGUF 模型格式与全套量化体系（Q/I-K-quants）、
  mmap 与 KV cache 内存管理、多 GPU 后端（CUDA/Vulkan/Metal/SYCL/CANN）、槽位/连续批处理调度、
  llama-server OpenAI 兼容接口与 GBNF 语法约束。
---

# llama.cpp 深度解析

> **一句话**：llama.cpp = C/C++ 写的"单进程多后端" LLM 推理框架，以 **GGML 计算图 + GGUF 量化**把大模型塞进 CPU/低端 GPU/边缘设备；vLLM 面向生产吞吐，它面向"什么机器都能跑"。
> 本文基于 llama.cpp 公开架构与源码模块整理，是 [[entities/llama.cpp|llama.cpp 实体页]] 的深度展开。

## 1. 定位与技术栈

| 维度 | 说明 |
|------|------|
| **项目** | `ggerganov/llama.cpp`（MIT） |
| **核心抽象** | ggml 张量库（即时构建计算图）+ ggml-backend（跨设备后端） |
| **模型格式** | GGUF（含全套量化类型） |
| **语言** | C/C++（无 Python 运行时依赖） |
| **支持硬件** | x86/AArch64 CPU、NVIDIA(CUDA)、AMD(ROCm/HIP)、Apple(Metal)、Intel(SYCL)、Qualcomm 等、Vulkan(跨厂商)、Ascend(CANN)、多机 RPC |
| **最佳场景** | 本地应用/边缘/离线、CPU 推理、Apple Silicon、低显存设备、个人助手（Ollama/LM Studio 底层） |

## 2. 总体架构：三层结构

```
┌────────────────────────────────────────────────────────────┐
│  应用层  llama-cli / llama-server / llama-bench / llama-    │
│          speculative / 第三方绑定(llama-cpp-python…)        │
├────────────────────────────────────────────────────────────┤
│  推理层  llama.cpp（llama_model / llama_context /           │
│          llama_sampler / llama_kv_cache / 采样/GBNF 语法)   │
├────────────────────────────────────────────────────────────┤
│  张量层  ggml（张量、类型/量化、计算图节点/调度）            │
│          └ ggml-backend（CPU/CUDA/Vulkan/Metal/SYCL/CANN…） │
└────────────────────────────────────────────────────────────┘
```

- **ggml**：不是"模型格式"，是**张量 + 运算 + 图执行**的 C 库。每次推理都把模型的一次前向**即时编译成一个计算图**（`ggml_cgraph`），节点是算子（`GGML_OP_MUL_MAT`、`GGML_OP_RMS_NORM`、`GGML_OP_ROPE`、`GGML_OP_GET_ROWS` 等），再由后端调度执行。
- **llama (llama.cpp)**：在其上封装「模型加载 → 上下文（KV cache）→ 逐 batch decode → 采样 → 输出文本」的完整推理循环。
- **应用（examples/）**：命令行/服务端/工具，直接消费上述两层。

### 2.1 计算图模型（为什么它"什么都能跑"）

```
input_ids ──> GET_ROWS(table=token_embd)
         ──> RMS_NORM ──> MUL_MAT(W1) ──> SILU ─┐
         ──> MUL_MAT(W2)                        ├─> ADD ──> RMS_NORM
         ──> ROPE ──> K_PROJ/V_PROJ/Q_PROJ      │           │
         ──> FlashAttn/Attention(读取 KV cache) ←──────────┤
         ──> OUT_PROJ → 每层叠加 → LM_HEAD ──> 采样
```

- 图是**每前向一次构建**的（不是编译后固化），因此对不同 batch/ctx 高度灵活；代价是启动调度有少量开销（这正是与 vLLM "CUDA Graph 固化"路线不同的哲学）。
- 算子实现有 CPU（SIMD：SSE/AVX/AVX2/AVX512、ARM NEON/SVE、RISC-V V）+ 各 GPU 后端两套，`ggml_backend` 决定每个算子落到哪个设备。

## 3. GGUF 模型格式（深度）

### 3.1 为什么是 GGUF

GGML 时代（2023 上半年）的 GGML 格式不记录维度/量化类型之外的信息，只测一台机器、不可迁移；llama.cpp b1510 起用 **GGUF**（GGML Unified File）取代：

- 自描述：头 + 元数据 KV（模型超参、分词器、RoPE 参数…）+ tensor 信息 + 原始数据。
- 自带"元数据即协议"：工具可无损读改写（转换类脚本与 `gguf` 库并存）。
- 支持 mmap 直接加载、可推理时只读头部。

### 3.2 文件布局

```
GGUF 文件（v3 及以后）：
┌──────────────┐
│ magic "GGUF" │  0x46554747
│ uint32 uversion │  版本（3）
│ uint64 n_tensors │
│ uint64 n_kv        │  元数据 KV 对数
├──────────────┤
│ metadata KV 列表   │  每项: key(str), value_type(enum), value
│   general.architecture = "llama"      │
│   llama.context_length = 8192         │
│   tokenizer.ggml.model = "gpt2"       │
│   ... (分词器、量块信息…)             │
├──────────────┤
│ tensor 信息列表    │ 每项: name(str), n_dims, dims[], ggml_type, offset
├──────────────┤────── 数据区起点（对齐，默认 32 字节）
│ tensor 数据        │ 按 offset 依次存放（若开启 mmap 直接映射到虚拟内存）
└──────────────┘
```

- **对齐**：默认 `alignment=32`；mmap 后端要求 tensor 起始地址按对齐边界，保证 SIMD/GPU 直接访问。
- **分布**：权重数据区**只读**、不随请求变化 → 可以安全 `mmap(PROT_READ)`，多个进程共享一份物理页（多客户端同时加载同一模型文件不重复占内存）。

### 3.3 分词器元数据

GGUF 自带分词器表（BPE/Unigram/WordPiece 的 vocab + merges + added tokens），llama.cpp 启动时把它们填入一个自带的 tokenizer 实现（与 HF tokenizers 结果对齐）。因此同一 .gguf 文件无需另外加载 json tokenizer 文件，开箱即用。

## 4. 量化体系（重点）

### 4.1 为什么量化是 llama.cpp 的看家本领

- 目标：尽量把权重点位降到 **4-bit 上下**，让模型塞进内存/显存；配合"按块缩放"把精度损失压低。
- 类型是**每个张量选择**的（`ggml_type` 存于 GGUF），一个模型里不同层可以不同精度。

### 4.2 量化类型家族（常用）

| 类型 | 位宽/块 | 块结构（block） | 典型用途/质量 |
|------|---------|------------------|----------------|
| `FP32/F16/BF16/F8_E4M3` | 32/16/16/8 | — | 未量化基准 |
| `Q4_0` | ~4.5 bit | 32 token/块，1 个 fp16 scale | 老 4-bit，通用最省 |
| `Q4_1` | ~5 bit | 32 token/块，fp16 scale+min | 比 Q4_0 稍好 |
| `Q5_0` / `Q5_1` | ~5.5/6 bit | 类似 | 中档 |
| `Q8_0` | ~8.5 bit | 32 token/块，fp16 scale | 接近无损、运算专用 |
| `Q2_K`/`Q3_K`/`Q4_K`/`Q5_K`/`Q6_K` | 2~6.5 bit | **super-block=256**，内含 16 个小块×16 token + 分层 scale | K 家族，质量/体积权衡最佳（K_M/K_L 变体调小/大 scale 位） |
| `Q8_K` | ~8.5 bit | super-block | 高质量 |
| `IQ1_S`…`IQ3_XXS`/`IQ4_XS`… | 1~5 bit | 重要度感知（imatrix）+ 无 scale 的分块 | 极限低体积（适合 CPU/手机） |
| `TQ1_0`/`TQ2_0` | ~1.6/2.12 bit | 三元/三值量化 | 2025+ 新增极低体积 |

**K-quants 关键点**：`super-block=256`，先存 16 个(fp16)子块 scale，再对每个 16-token 子块用低位量化；`Q4_K_M` 是"混合 K_M 变体"——某些块用更高精度，平均下来质量接近 Q5。这也是"同样 4-bit，Q4_K_M 比 Q4_0 明显好"的原因。

### 4.3 量化的"校准"：importance matrix（imatrix）

- `llama-imatrix` 可以在代表数据集上算出**每个张量的重要度矩阵**，量化器据此给敏感权重分配更多比特/更小的量化误差 → `IQ` 系列质量显著提升。
- 流程：`convert_hf_to_gguf.py` 出 FP16 GGUF → `llama-imatrix -m model.gguf -f data.txt --imatrix imatrix.dat` → `llama-quantize --imatrix imatrix.dat -t q4_k_m`。
- 不加 imatrix 的普通 `llama-quantize` 也行（按启发式），但 IQ/低 bit 强烈建议配合。

### 4.4 转换工具链

| 工具 | 作用 |
|------|------|
| `convert_hf_to_gguf.py` | HuggingFace 模型 → FP16 GGUF |
| `llama-quantize` | FP16 GGUF → 各种量化类型（细粒度 per-tensor 或 imatrix 校准） |
| `llama-imatrix` | 计算 importance matrix（校准数据） |
| `llama-split` / `gguf-split` | 大文件拆分/合并 |

## 5. 内存管理（重点）

### 5.1 权重加载：mmap vs no-mmap

- **mmap（默认，Linux/macOS/Windows 均可）**：把只读的 weight 数据区映射进进程地址空间，**无需整体复制**；首次访问按需换页，OS 负责换页/缓存。内存吃紧时优先逐页淘汰未用权重。多进程共享同一映射。
- **`--no-mmap` / `--mlock`**：把它整体拷到堆内存（更快的预取、避免页错误抖动，但占用更多 RAM；`--mlock` 防换出、延迟更稳）。
- 卸载到 GPU 的层：张量从映射页**拷贝**到设备 buffer，CPU 侧的映射页随后可释放。

### 5.2 KV cache：slot / page + defrag + 复用

- `llama_context` 内为**每一层**分配 KV 缓存，容量由 `--ctx-size`（默认 4096 或按模型）决定——它是所有并发请求共享的"token 会议室"。
- 现代版本用**页式 KV cache（`llama_kv_cache` 分页 + defrag）**：同模型一次性分配大池，按"slot"（会话/请求）切分；上下文用完可 `llama_kv_cache_clear`、`llama_kv_cache_seq_rm`（删段）释放；碎片整理（defrag）在长时间流水后重排页，最大化可复用连续区域。
- 服务端多请求：每个请求占一个/多个 slot；slot 内 token 位置可"复用/续写"（`llama_kv_cache_seq_add` 调整位置做 KV 复用）。

### 5.3 计算缓冲（compute buffer）

- 每次 `llama_decode` 需要一块临时张量内存存放中间激活。llama.cpp 用 `ggml_backend_buffer` 把这些一次性分配好（图执行时复用），避免每 token 分配/释放。
- 激活随 batch/ctx 增长：`--batch-size`（默认 2048）与 `--ubatch-size`（micro-batch，默认 512，防 OOM）联动，长 prefill 会被自动切分为 micro-batch 顺序计算。

### 5.4 总体内存估算（一条实用公式）

```
需要内存 ≈ 权重(量化后) + KV cache + 计算缓冲
权重：7B @ Q4_K_M ≈ 4 GB；33B @ Q4_K_M ≈ 19 GB；70B @ Q4_K_M ≈ 39 GB
KV cache：2 × n_layers × n_ctx × n_kv_heads × head_dim × (bit/8) × 序列数
```
- 简化：启动日志会打印 KV buffer 大小；`-c` 超过模型最大上下文时会被自动钳制到模型上限（或显存/内存不足时报错）。

## 6. GPU 层详解（重点）

### 6.1 多后端抽象

`ggml_backend` 是所有设备的统一接口（alloc / free / compute / buffer），推理时 `llama` 为每个张量选择后端：

| 后端 | 设备 | 说明 |
|------|------|------|
| `CPU` | x86/AArch64/RISC-V | SIMD 算子、`--threads` 多线程 |
| `CUDA` | NVIDIA | cuBLAS 大矩阵乘 + 自研 kernel（含 FlashAttention、持久化 kernel、多流） |
| `Vulkan` | 跨厂商 GPU | ROCm 之外 AMD/Intel 也能跑（shader 后端） |
| `Metal` | Apple Silicon | 新一代 Metal 后端（苹果自研芯效率高） |
| `SYCL` | Intel GPU | `--sycl` 构建 |
| `CANN` | 华为昇腾 | `--cann` 构建 |
| `RPC` | 任意主机 | 多机张量分配（`llama-server --rpc`） |

### 6.2 多 GPU 策略

- **`--n-gpu-layers` / `-ngl N`**：把 N 个层卸载到 GPU（其余在 CPU），是"低显存跑大模型"核心开关；半卸载时矩阵乘走设备、小型中间算子走 CPU。
- **`--split-mode`**：
  - `layer`(默认)：把层**均分到各卡**（每卡各拿部分层，层间串行）；
  - `row`: 张量按行切分跨卡（一次 matmul 跨卡并行，吞吐更高、需显存足够一层的权重）；`none`(不切分)。
- **`--tensor-split`**：填比例列表（如 `0.5,0.5`）让各卡不均匀分摊（配合异构卡）。
- **`--main-gpu`**：指定"主卡"做采样/KV 驻留。
- CUDA 后端支持 **FlashAttention / persistent kernels / multi-stream**，decode 阶段小 batch 也有不错延迟；但**它在 GPU 上的绝对吞吐仍低于 vLLM**（无 continuous batching 的大批量重组 + 无块级页式 KV 复用），定位是"本地可用"而非"数据中心吞吐"。

> 注：关于 `-ngl` 具体"从模型哪一端开始卸载层"由模型加载器的 offload 计划决定（不同版本有差异），按"调到显存刚好放得下、别 OOM"的实践准则来调它即可，不必逐层推敲。

### 6.3 MoE 与 offload

- MoE 模型（如 Mixtral、Qwen-MoE、DeepSeek-MoE）支持 **expert offload**（`--no-experts-offload` 关闭）：将 expert 权重放到 CPU、把 attention/shared 等放 GPU；计算时按需把 expert 张量搬到设备，让大 MoE 也能在低显存跑，代价是吞吐下降。
- 结合 `--batch-size`、`--ubatch-size` 控制设备上输入批的显存峰值。

## 7. 内部调度与生成流程（重点）

### 7.1 单次前向：prefill（prompt）与 decode(逐token)

```
llama_decode(batch)：
  1) 构图：batch 的 token → embedding → N 层 transformer → logits
  2) 执行：ggml_backend_graph_compute（可多线程/多设备并行算子）
  3) 其中注意力读取当前 slot 的 KV cache；新 token 的 K/V 写回
采样循环（llama-cli / server）：
  while 未产出 EOS 或达到 max_new_tokens:
     batch = 上一段输出 token（decode 阶段每步 1 token / 或 spec 多条）
     llama_decode(batch)
     sampling = llama_sampler_sample(logits 最后一行)
     输出 token，写回 KV
```

- **两阶段可独立观察**：prefill 是"计算密集、占用一整个 batch"；decode 是"每 token 一个小 forward、内存带宽密集"。
- 长 prompt 由 `--batch-size` / `--ubatch-size` 自动切成 micro-batch 顺序喂，防止一次 prefill 吃光显存/内存。

### 7.2 服务端槽位与并发

- `llama-server` 用 `--parallel N` 开 N 个并发槽位（slot）。每个 slot 有独立的系统提示/会话，共享同一个 `llama_decoder`；每轮把所有**活跃 slot** 的下一步 token 拼进一个 batch 一起 `llama_decode` → 一次前向服务多个请求（batch 吞吐）。
- 等待队列：活跃 slot 满了新请求排队；有 slot 空闲或请求完成时无碍调度。
- **连续批处理（`--cont-batching`，默认开）**：新到达请求可在**当轮**补进下一个 batch，无需等 slot 全空，近似 vLLM 的效果（但粒度是"轮"不是"token step 重组"）。
- 上下文放不下：较长会话的早段会被截断（重新 tokenize 并让 KV 重算，遵循 `--keep` 保头）；无抢占式换出（与 vLLM 的 swap/recompute 不同，llama.cpp 服务端是"排队 + 截断/复用"）。

### 7.3 采样与精度控制

- `llama_sampler` 是可链式组合的采样管线：`greedy / top-k / top-p / min-p / typical / temperature / frequency_& presence_penalty / repetition_penalty / mirostat / grammar(GBNF)`。
- 服务端请求体透传：`temperature, top_p, top_k, min_p, stop, max_tokens(=n_predict), seed, n_keep, logprobs, ignore_eos, penalty 系列`。
- 可多轮共用 tokenizer/sampler（无状态解耦）。

### 7.4 Speculative Decoding（推测解码）

内置几种推测解码，适合代理模型场景：
- **草稿模型（draft model）**：`llama-server -md draft.gguf -mtd 目标`；小模型每步出 k 个候选，大模型一次验证（`-nd / --n-draft` 控制长度）。
- **Prompt-lookup / n-gram 自推测**：`--prompt-lookup n_gram`——从输入里找重复 n-gram 做候选，无需第二模型。
- 现代版本还支持 **autospec**（自模型草稿头）等更新方案（`--autospec`）。

### 7.5 GBNF 语法约束（结构化输出）

- GBNF（GGML Backus-Naur Form）：`llama.cpp` 自带的上下文无关语法文件，定义输出合法性：`root ::= verse | outro`、`string ::= '"' ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4}))* '"'`；内置 `grammars/json.gbnf`（标准 JSON 最小语法）。
- 运行时 `llama_sampler_grammar` 把语法编译成有限状态机，每步给出"当前已输出前缀 → 下一 token 掩码"，采样时只从合法 token 里选（可自定义/扩充 `grammars/` 目录）。
- 服务端：请求体 `grammar` 字段传 `.gbnf` 字符串，或 OpenAI 风格 `response_format`。

## 8. 对外接口（重点）

### 8.1 llama-server（一个二进制，含 OpenAI 兼容层）

启动：
```bash
llama-server -m Meta-Llama-3-8B-Q4_K_M.gguf \
  --port 8080 -c 8192 --parallel 4 --cont-batching \
  -ngl 24        # GPU 卸载 24 层（用户按显存调）
```

| 端点 | 说明 |
|------|------|
| `POST /v1/chat/completions` | OpenAI 对话补全（messages→role 映射，支持流式 SSE） |
| `POST /v1/completions` | OpenAI 文本补全 |
| `POST /v1/embeddings` | 向量嵌入 |
| `GET /v1/models` | 模型信息 |
| `POST /completion` | 原生补全（`prompt`、`n_predict`、`n_ctx`、`samplers` 等完整字段） |
| `POST /infill` | 代码补全（FIM） |
| `POST /embedding` | 原生嵌入 |
| `POST /tokenize` / `POST /detokenize` | 分词往返 |
| `GET /health` | 存活（可配 `--health-endpoint`） |
| `GET /props` | 服务端能力（上下文大小、模型信息） |
| `GET /slots` | 并发槽位实时状态（每 slot 的活动状态/句量） |
| `GET /metrics` | Prometheus 指标 |

- 鉴权：`--api-key` 设 key；`--alias` 设模型别名；`--chat-template` 用 Jinja 模板替换默认聊天模板。
- 流式：`"stream": true`；`"stream_options": {"include_usage": true}` 尾帧带 usage。
- 多模态：`llama-mtmd`/mmproj 模型支持图片输入（`/v1/chat/completions` 的 `image_url` 与本地路径）。

### 8.2 命令行工具全家

| 命令 | 用途 |
|------|------|
| `llama-cli` | 交互式对话 / 单次补全（`-p`） |
| `llama-server` | HTTP 服务（见上） |
| `llama-perplexity` | 困惑度（模型质量/校准评估） |
| `llama-bench` | 吞吐/延迟基准（`--test speed / pp / tg`） |
| `llama-embd` | 嵌入批量推理 |
| `llama-imatrix` / `llama-quantize` | imatrix 校准 / 量化 |
| `llama-speculative` | 推测解码演示 |
| `llama-passkey` | 长上下文 recall 测 |

### 8.3 采样参数表（服务端请求体 / cli 透传）

| 字段 | 默认 | 含义 |
|------|------|------|
| `temperature` | 0.8 | 采样温度；0=贪心 |
| `top_k` / `top_p` | 40 / 0.95 | 常用约束（核采样） |
| `min_p` | 0.05 | 低概率 token 剪枝 |
| `typical_p` | 1.0 | 典型采样 |
| `repeat_penalty` / `presence_penalty` / `frequency_penalty` | 1.0 / 0 / 0 | 惩罚重复 |
| `stop` / `stop_token_ids` | [] | 停止词串（可多条） |
| `max_tokens`（=`n_predict`） | 128 | 最长生成长度 |
| `min_tokens` | 0 | 至少生成长度（`EOS` 后仍续） |
| `n_keep` / `n_discard` | 0 | 保头丢弃（长会话截断策略） |
| `seed` | 随机 | 复现用；`-1`=随机 |
| `n` | 1 | 并行采样数（`--parallel` 槽位内） |
| `ignore_eos` | false | 忽略 EOS 一直生成 |
| `logprobs` / `top_logprobs` | 0 | 返回 logits/前 k 个 token 概率 |
| `echo` | false | 响应回显 prompt |
| `mirostat`(0/1/2) + `mirostat_tau/eta` | 0 | 自适应熵控制 |
| `sampler_prios` / `grammar` | 默认链 | 采样管线优先级 / GBNF 语法 |
| `model` / `draft` / `n_draft` / `prompt_lookup_num_tokens` | — | 主模型/草稿模型/推测长度/自推测 n-gram |

> 服务端 `POST /completion` 是"全字段"原生入口；OpenAI 兼容端点映射其子集。`--samplers` 自定义采样器链（cli）。

### 8.4 多模态

- **文件**：`-mmproj <file>.mmproj` 加载视觉投影器；Apache/LLaVA 系、MiniCPM-V、InternVL、Qwen2.5-VL 等跨模态架构随版本支持。
- **入口**：`/v1/chat/completions` 的 `messages[].content` 支持 `image`（`image_url` 本地路径/base64）；`llama-mtmd` 工具可调试多模态 tokenizer/投影。
- **代价**：图像会切块并产生额外 prompt token（进入同一 KV cache），`--mmproj` 需与主模型匹配；吞吐随图块数下降。
- **分离性**：多模态支持在 llama.cpp 内基本是"独立 ps 投影层 + 提示 token 拼接"，与主推理路径解耦，故 old GGUF 也可扩展（跨模态权重需 mmproj 配合）。

### 8.5 RPC 多机部署

- 语法：`llama-server --rpc host1:8010,host2:8010`（多个远端 ggml RPC 后端）。
- 行为：把模型张量**按行切分跨机**（配合 `--split-mode row`），利用远端 GPU 的显存与算力；网络延迟敏感，适合"大块矩阵乘并行"而非小算子。
- 注意：RPC 每机需跑 `ggml-rpc` 服务端；交叉带宽（以太/PCE）决定上限；不适合低延迟交互场景的大批小请求。

### 8.6 生态绑定

- **llama-cpp-python**：官方维护的 Python 绑定，可 `model.create_chat_completion()`，是 RAG/Agent 框架（LangChain/LlamaIndex 等）接入本地模型的标准方式。
- **llamafile**：单文件可执行分发（内含形参/模型），一条命令跑起服务。
- **Ollama / LM Studio / GPT4All / Open WebUI**：GUI/CLI 封装，底层都是 llama.cpp（或兼容 GGUF），对外一般也暴露 OpenAI 兼容接口。

### 8.7 GGUF 高可用形态

- `.gguf` 大模型可以**拆片**（`-s split_size` / `gguf-split`）便于分卷。
- GGUF 结构支持「只更新头部元数据、不改动数据区」的原地编辑，便于调整聊天模板/采样默认值等而无需重写权重。

## 9. 性能模型与调优速查

| 目标 | 手段 |
|------|------|
| 更小内存 | 量化降位（Q8→Q5→Q4→IQ）+ `-c` 降上下文 |
| 更快 CPU | `-t` 线程数（≈ 核数）、SIMD 指令集构建（`-march`） |
| GPU 加速 | `-ngl` 全量/部分卸载、`--split-mode row` 多卡并行 |
| 低延迟 | `--flash-attn`、`--mlock`（避免换出）、小 `--batch-size` |
| 吞吐 | 服务端 `--parallel` + `--cont-batching` 多请求合并 |
| 长上下文 | `-c` 加大 + `--flash-attn` + 量化 offload |
| 防 OOM | `--ubatch-size` 调小、`--no-mmap` 或用 imatrix 降权重大小 |

## 10. 与 vLLM / Ollama 关键对比

| 维度 | llama.cpp | vLLM | Ollama |
|------|-----------|------|--------|
| 内核 | ggml 图 + GGUF | 自研 PagedAttention + CUDA | 底层 llama.cpp |
| GPU 绝对吞吐 | 中（本地够用） | 极高（生产） | 中 |
| CPU / 边缘支持 | 原生一等 | 有限 | 中 |
| 模型格式 | GGUF（管全家族） | 原生 HF/multiple | GGUF |
| 连续批处理 | 服务端 + cont-batching | V1 每步动态 | 有 |
| KV 复用/前缀 | 页式+defrag（无 Radix 树） | 块哈希前缀缓存 | 用 llama.cpp |
| 部署 | 单二进制/绑定库 | 服务进程/库（GPU） | 守护进程 + CLI |
| 最佳场景 | 个人、边缘、CPU、果芯 | 数据中心生产吞吐 | 个人助手 |

## 11. 工程注意点

- **构建**：`cmake -B build -DGGML_CUDA=ON`（加 Vulkan/Metal/CANN 等对应 `-DGGML_*`）；产物单二进制，无 Python 依赖。
- **换模型**：llama-server 无运行时热换权重，换模型即重启进程（`-m <新文件>`）；本地/边缘场景通常保持单模型单进程。
- **版本演进**：GGUF 版本、量化类型、端点细节随版本演进（尤其 2025 年新增 TQ/MTMD、`--cont-batching` 默认化、KV 页式化），具体以 `llama-server --help` 与 `docs/` 为准；本环境无法访问外网，以上架构性说明基于稳定公开设计。

## 参考

- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)
- [llama.cpp Wiki](https://github.com/ggerganov/llama.cpp/wiki)
- [GGUF 格式说明](https://github.com/ggerganov/llama.cpp/blob/master/docs/gguf.md)

---

## 📚 相关笔记

- [[entities/llama.cpp|llama.cpp 实体页]] — 概览与快速参考
- [[sources/vLLM-Deep-Dive|vLLM 深度解析]]、[[entities/vllm|vLLM]] — 对比：GPU 生产吞吐
- [[sources/SGLang-Deep-Dive|SGLang 深度解析]]、[[entities/sglang|SGLang]] — 对比：Radix 前缀复用
- [[sources/LLMForEverybody/02-第二章-部署与推理/大模型推理框架（七）llama.cpp|大模型推理框架（七）llama.cpp]] — 外文转载
- [[concepts/模型 压缩 蒸馏]] — 量化/压缩总论
- [[concepts/LLM 推理 优化]] — 推理优化总论