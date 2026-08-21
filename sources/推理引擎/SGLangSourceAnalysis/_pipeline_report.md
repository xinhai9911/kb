# 转换报告：SGLang 源码分析（Round 1-2）

## 输入

- **输入类型**：文件夹（`Q:\AI\sglang-main`，解压自 `sglang-main.zip`）
- **来源文件**：`python/sglang/` 包共 3365 个 `.py`（核心 `srt/` 1614、`multimodal_gen/` 925、`kernels/` 592）；两轮深入分析约 140+ 个核心源码文件
- **空文件**：0
- **排除文件**：`test/`、`benchmark/`、`docs/`、`examples/`、`experimental/`、`scripts/`、`3rdparty/`、`docker/` 等非包源码目录；二进制与生成物

## 版本

- commit `21c88f8625f2e699543a1c34f41d6894ef342903`

## Round 1 模块（核心链路）

| 模块 | 目录 | 文件数 | 覆盖源码重点 |
|---|---|---|---|
| 00 整体架构 | 00-overview | 2 | 进程模型（四大 manager）、ZMQ IPC、RadixAttention 理念、请求路径、vLLM 对照 |
| 01 配置体系 | 01-config | 3 | ServerArgs（10073 行）、40+ 参数分组、SGLANG_* 环境变量、configs |
| 02 Manager 进程 | 02-managers | 3 | TokenizerManager 请求流、Req/ScheduleBatch、communicator（89 种消息） |
| 03 调度器 | 03-scheduler | 4 | 调度主循环、get_new_batch_prefill、6 种调度策略、PP 调度 |
| 04 Radix 缓存 | 04-radix-cache | 3 | RadixCache/HiRadixCache/ChunkCache 族、7 淘汰策略、chunking |
| 05 内存池 | 05-mem-cache | 3 | 请求/KV/token 池、显存分配估算、特殊池 |
| 06 模型执行 | 06-model-executor | 3 | ModelRunner、ForwardBatch、权重加载链路 |
| 07 注意力 | 07-attention | 3 | RadixAttention 层、20+ 后端注册与选择、KV 布局差异 |
| 08 采样 | 08-sampling | 3 | SamplingParams、批量张量化、采样后端（flashinfer/pytorch/ascend） |
| 09 服务入口 | 09-entrypoints | 4 | HTTP 端点（80+）、OpenAI/Ollama/Anthropic 协议族、Engine 离线接口、gRPC |
| **根文件** | 根目录 | 3 | `skill.md`、`faq.md`、本报告 |

### Round 2（深化：层/模型/多模态/投机/工具/分布式/内核/LoRA/PD/语言）

| 模块 | 目录 | 文件数 | 覆盖源码重点 |
|---|---|---|---|
| 10 模型层 | 10-layers | 2 | 并行线性层、Norm、MoE、RoPE、Embedding |
| 11 模型定义 | 11-models | 4 | 注册机制、代表架构、全量索引（195 文件/246 架构类） |
| 12 多模态 | 12-multimodal | 3 | 输入处理、调度缓存、multimodal_gen 生成管线 |
| 13 投机解码 | 13-speculative | 3 | spec worker 架构、EAGLE-1/2/3、7 种草稿后端 |
| 14 工具/约束 | 14-function-constrained | 3 | tools schema、33 detector、xgrammar/outlines 约束 |
| 15 分布式 | 15-distributed | 4 | 并行状态、通信算子、EPLB 在线重均衡 |
| 16 硬件/内核 | 16-hardware-kernels | 3 | 6 平台后端抽象、20 内核族 |
| 17 LoRA | 17-lora | 2 | 请求登记、权重池、层注入 |
| 18 PD 分离 | 18-disaggregation | 2 | prefill/decode 分离、KV 传输后端 |
| 19 语言/可观测 | 19-lang-observability | 4 | sglang.lang DSL、metrics/trace、编译/CUDA graph |

## 阶段状态

| 阶段 | 状态 | 摘要 |
|---|---|---|
| 一 分析 | 完成 | 盘点 `python/sglang/` 顶层模块，规划 Round 1（00-09）与 Round 2（10-19） |
| 二 规划 | 完成 | 模块目录 `NN-english-slug` 连续编号 00-19 |
| 三 逻辑分片 | 完成 | 按模块分派并行分析代理，每代理只读自身模块源码 |
| 四 生成 | 完成 | 20 代理产出 62 个模块文件 + 3 个根文件，遵循统一模板与页脚 |
| 五 审查 | 完成 | 六维检查：页脚齐全、大小合规；修复 eplb 引用断链、拆分 sampling.md（8.2KB） |
| 六 优化 | 完成 | 拆分超限文件（sampling.md→2 段）；无跨文件重复段落 |
| 七 硬化 | 完成 | 索引与文件清单一致（62/62）；链接不越出输出目录；全局约定仅存于 skill.md |

## 覆盖率

- **模块级覆盖率**：20/20（Round 1+2 计划模块，100%）
- **已覆盖**：srt 全部核心子系统（配置/manager/调度/radix/内存/执行/注意力/采样/入口/层/模型/多模态/投机/工具/分布式/内核/LoRA/PD/语言/可观测）
- **未深入（可选）**：

| 目录 | 说明 |
|---|---|
| `kernels/`（592） | 已覆盖组织与内核族概览，未逐内核展开 |
| `multimodal_gen/`（925） | 已覆盖生成运行时架构，未逐应用展开 |
| `srt/debug_utils/`（91）、`srt/kv_canary/`（50）、`srt/session/`、`srt/multiplex/`、`srt/dllm/` 等 | 调试/工具/实验性模块，按需补完 |
| `benchmark/`、`test/` | 基准与测试脚本，不展开 |

## 最终统计（Round 1-2）

- 目录数：21（20 模块 + 根）
- Markdown 文件数：62（模块）+ 3（根）= **65**
- 全部模块文件 ≤8KB；最大文件约 8.2KB（已拆分）

## 遗留问题

- 源码快照个别路径不存在（如部分 attention 后端、`sampling_info_done` 字段），文档已按实际源码记录并注明。
- 中间出现过 `sglang-main` 目录消失（需重新解压 zip 恢复），不影响已落盘文档。
- 剩余可选模块（debug_utils/kv_canary/session 等）与 kernels/multimodal_gen 深度展开可按需补完。
