# vLLM vs SGLang 对比 FAQ

## 两者最核心的架构差异是什么？
- vLLM V1：前端进程 + 独立 `EngineCore` 进程，经 ZMQ/msgpack 通信，模块化强、生产稳定，Scheduler 在 EngineCore 内部。
- SGLang：`TokenizerManager`（主进程，宿主 HTTP）→ `Scheduler` 子进程 + `TpModelWorker`（与 Scheduler 同进程）→ `DetokenizerManager` 子进程，经 ZMQ 通信。
- 见 `00-architecture/architecture-comparison.md`。

## 前缀缓存机制谁更强？
SGLang 的 RadixCache 是前缀树（match_prefix/insert/eviction），支持 HiRadixCache（L1/L2/L3）、ChunkCache 等 8 种缓存实现；vLLM 采用 hash block 前缀缓存（`enable_prefix_caching`）。SGLang 在前缀复用与共享前缀场景更具优势。见 `03-kvcache-prefix/`。

## 调度策略各有什么？
vLLM V1：FCFS + priority；SGLang：fcfs/lpm/dfs-weight 等 6 种策略，且显式区分 prefill/decode batch、支持 overlap 双循环。见 `02-scheduler/scheduler-comparison_part2.md`。

## 注意力后端如何选择？
vLLM 通过平台层 `get_attn_backend_cls` 选择（FLASH_ATTN/FLASHINFER/TRITON 等）；SGLang 用 `ATTENTION_BACKENDS` 注册表 + 默认逻辑，支持 FlashInfer/FA3/FA4/FlashMLA 等 20+ 后端。见 `04-attention/attention-comparison.md`。

## 多模态生成该选谁？
唯一支持**多模态生成**（图像/音频/视频，`multimodal_gen`）的是 SGLang；vLLM 仅支持多模态输入。见 `09-multimodal-tool/multimodal-comparison.md`。

## MoE 大模型专家负载均衡谁更强？
SGLang EPLB 源自 DeepSeek 算法，支持 packing/replicate/分层与 LPLBSolver 在线重均衡；vLLM EPLB 较简单。见 `07-distributed/eplb-comparison.md`。

## 结构化输出/工具调用差异？
两者都支持 xgrammar/outlines 等 grammar 后端与 OpenAI tools；vLLM 用 ToolParserManager（48 注册）+ structured_outputs bitmask，SGLang 用 function_call（33 detector）+ constrained GrammarMask。见 `09-multimodal-tool/tool-structure-comparison.md`。

## 如何从 vLLM 迁移到 SGLang？
主要差异在启动参数与 API：vLLM `EngineArgs` vs SGLang `ServerArgs`；vLLM 用 `LLM` 类 vs SGLang `Engine`。迁移速查见 `11-selection/selection-guide_part2.md`。

## 哪些场景推荐 vLLM？
生产稳定性、生态/社区、多硬件平台、结构化输出规模要求高、需要 Ray 多节点编排的场景。见 `11-selection/selection-guide.md`。

## 哪些场景推荐 SGLang？
高并发前缀复用/多轮对话/共享前缀、MoE 大模型 EPLB、多模态生成（图像/音频/视频）、极致吞吐调优场景。见 `11-selection/selection-guide.md`。
