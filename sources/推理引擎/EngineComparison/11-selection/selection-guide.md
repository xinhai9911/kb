## 11-selection 选型指南（一）：设计哲学、优劣势矩阵与适用场景

综合本对比库 00-architecture ~ 10-serving 全部结论，回答「何时选 vLLM、何时选 SGLang」。事实基准与各模块一致：vLLM V1（`v0.27.2rc0-203-g41f179b57a`）、SGLang SRT（commit `21c88f86`）。本文不给 benchmark 数字，优劣均指机制/能力层面。

### 一、设计哲学总结

| 引擎 | 一句话定位 | 核心哲学 | 代表性机制（KB 出处） |
|---|---|---|---|
| vLLM | 模块化、强解耦、稳定生产 | 三层进程隔离（前端/EngineCore/GPU Worker）、msgspec 强类型契约、多执行器抽象（单进程/Multiprocess/Ray）；V1 调度取消 prefill/decode 阶段分裂 | EngineCore 独立进程、`EngineCoreRequest` 契约、Plugin 插件机制、OpenAI 协议为主（00-architecture、10-serving） |
| SGLang | 运行时一体化、性能极致 | 四大 Manager 同构流水线、Scheduler 内嵌 TpModelWorker 减少拷贝；RadixAttention 前缀树极致复用；多模态生成一体 | RadixCache 树 + lock_ref + 叶子驱逐、overlap 双 stream、EAGLE topk 树投机、sglang.lang DSL、SGLang Diffusion（00/03/06/09 模块） |

**哲学结论**：工程稳定与生态 → vLLM；单场景极致性能、前缀复用、多模态生成 → SGLang。

### 二、各维度优劣势矩阵

| 维度 | vLLM | SGLang | 倾向 |
|---|---|---|---|
| 架构 | 三层进程隔离，调度崩溃不拖累 Worker、契约显式可查；代价：进程多、多一跳 IPC | Scheduler 与 TpModelWorker 同进程、Detokenizer 独立子进程，路径短拷贝少；代价：隔离弱 | 稳定 vLLM / 性能 SGLang |
| 调度 | 隐式连续 token 分配（num_computed_tokens 追赶），无阶段分裂，batch_queue 多批异步重叠；策略仅 fcfs/priority | 显式 EXTEND/DECODE 两相，6+1 策略含 cache-aware（lpm/dfs-weight），overlap 双 stream，三路抢占（优先级/内存守卫/radix 回收） | SGLang 功能面更全 |
| 前缀缓存 | hash-block 扁平字典，整块命中 + partial CoW；简单可靠，无分层 | RadixCache 前缀树，token 段级命中可部分复用，7 种淘汰，HiRadixCache L1 GPU/L2 host/L3 storage 分层 | **SGLang 显著领先** |
| 注意力 | 平台层按架构选型 + `validate_configuration()` 类静态校验，35+ 后端覆盖 CUDA/ROCm/CPU/XPU；全局单后端 | 配置启发式 + prefill/decode 可拆双后端（HybridAttnBackend），覆盖 ascend/NPU/intel_xpu；灵活但无统一选型校验层 | 稳定 vLLM / 灵活 SGLang |
| 采样 | logits 级处理、每 token 行粒度，torch.Generator 确定性**后端无关** | probs 级就地 softmax 省显存，flashinfer 融合算子，custom logit processor dill 随请求传输；确定性锁 flashinfer 不可用 | 确定性 vLLM / 效率 SGLang |
| 投机 | proposer 内建 ModelRunner、线性草稿，后端面宽（eagle/medusa/draft_model/ngram/dflash/dspark/mtp/custom_class） | spec worker 替换 model_worker，EAGLE topk **树**草稿 + draft_extend 阶段 + 独立 draft CUDA graph + 多层 EAGLE + FROZEN_KV_MTP + 自适应步数 | **SGLang EAGLE 深度领先** |
| 分布式 | 9 并行组含独立 PCP/EPLB 组，CudaCommunicator + All2AllManager 抽象（DeepEP/NIXL/FlashInfer/Mori 可插拔） | 11 组，ATTN/MoE 通信组从 TP 解耦（DP-attention），弹性 EP + mooncake backend，SGLang 无 PCP 维度 | 维度全 vLLM / 弹性 SGLang |
| 量化 | 方法级组织，23 checkpoint + 7 在线简写，独有 torchao/inc/fbgemm_fp8 | scheme/内核解耦三级分派，独有 bitsandbytes/gguf/auto-round/modelslim/mlx_q4-q8、NPU 深度适配、FP4→FP8 重量化转写 | 生态 vLLM / 平台 SGLang |
| 多模态 | 输入管线强（装饰器注册/三级缓存/Tensor IPC），**引擎内无生成能力** | 输入 + 分块 mm 调度 + per-image 批量编码 + 前向融合；**SGLang Diffusion 独立运行时做图像/视频生成，vLLM 无对应** | **多模态生成 SGLang 唯一** |
| 工具 | 48 工具 parser + ~30 reasoning parser + 统一 ParserManager，guidance/lm-format-enforcer 后端，MCP 外部工具；必须显式指定 parser | 33 parser + `auto` 自动探测，llguidance + jump-forward + structural tag 双格式；约束决策集中一棵树 | 生态面 vLLM / 易用 SGLang |
| 服务 | OpenAI 协议为主 + Anthropic/Cohere/SageMaker/gRPC/Ray，管理端点收敛到 dev 模式 | 原生 /generate + OpenAI 兼容，另含 Ollama/Vertex/WS realtime、`--api-key` 鉴权、/v1/loads 分节负载、OTLP trace 独立子系统 | 协议核心对齐，SGLang 端点面更丰富 |

### 三、适用场景建议

| 场景 | 推荐 | 依据（KB 事实） |
|---|---|---|
| 高并发前缀复用 / 多轮对话 / 共享前缀 | **SGLang** | RadixCache token 段级命中、可部分复用，cache-aware 策略（lpm/dfs-weight）先匹配再排序、批内共享前缀临时降权；vLLM hash-block 块级命中，prompt 轻微变化即破坏整块哈希（partial 仅缓解） |
| 长文本 / 大 batch | 两者均可；超长共享前缀场景 SGLang | vLLM 预算制（max_num_scheduled_tokens）自然切分长 prefill、`max_model_len=-1` 自动 fit；SGLang `chunked_prefill_size` 按显存分级（2048~16384）、`max_prefill_tokens` 默认 16384，且 HiRadixCache L2/L3 对超长缓存复用更优 |
| 多模态生成（图像/音频/视频） | **SGLang（唯一）** | vLLM 推理引擎内无生成；SGLang Diffusion（`sglang/multimodal_gen/`）独立运行时 + xDiT 风格并行（tp/cfg/ulysses/ring）+ TeaCache/Spectrum 跳步 + OpenAI 兼容 API |
| 生产稳定 / 生态 / 社区 | **vLLM** | 三层进程隔离、强类型契约、Plugin 机制、Ray 多节点、OpenAI 协议主导、K8s 探针/gRPC/DP supervisor/`run-batch` 等生产面完整 |
| MoE 大模型 / EPLB | **SGLang** | 完整 DeepSeek 生产级 EPLB 全链路（算法+统计+搬运+弹性+LPLB 线性规划分派）；vLLM 有 DefaultEplbPolicy + EPLB 独立通信组，但无 LPLB、无 DeepEP 分派统计、无弹性 EP 在线重均衡与 DRAM 备份 |
| 多硬件平台（NPU/MLX 等） | **SGLang** | `hardware_backend/` 6 平台（gpu/cpu/npu/mlx/musa/xpu）各带量化分派壳，mlx_q4/q8 量化、ascend 注意力、NPU 专属量化方案；vLLM 无 MLX 路径、无独立 NPU 量化 |
| 深度绑定 DeepSeek 系模型 | **SGLang** | MLA 后端最多（flashmla/trtllm_mla/cutlass_mla/tokenspeed_mla）、DSV4 sparse 注意力（dsa/dsv4）、DeepSeek EPLB 全链路、FP4→FP8 重量化转写 |
| 需要确定性采样复现 | **vLLM** | `seed` 走每请求 torch.Generator、后端无关；SGLang `sampling_seed` 仅 `--enable-deterministic-inference` 且 flashinfer 后端断言不支持 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
