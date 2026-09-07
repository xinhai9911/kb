---
title: LLM 缓存 KV Prefix Prompt Semantic
category: concepts
tags: [llm, kv-cache, prefix-caching, prompt-caching, semantic-cache, inference, serving, ttft, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    LLM 服务化的四层缓存：KV Cache（单序列内复用注意力 K/V）、Prefix Cache（跨请求复用相同前缀的
    KV blocks）、Prompt Cache（产品化的显式前缀缓存 + 计费折扣）、Semantic Cache（按语义相似度复用
    最终回答）。四者粒度由「token 级张量」递进到「请求级答案」，分别优化 TPOT/TTFT/成本/延迟。
base_confidence: 0.85
lifecycle: draft
---

# LLM 缓存 KV Prefix Prompt Semantic

> 前置 [[concepts/Transformer 架构]]、[[concepts/FlashAttention 注意力内核]]；
> 相关 [[concepts/RAG 检索 增强 生成]]、[[concepts/向量 DB 嵌入]]、[[concepts/分词器 LLM]]。

---

## 0. 一句话区分：缓存的是什么

| 层 | 缓存对象 | 命中条件 | 所在位置 | 主要收益 |
|---|---|---|---|---|
| **KV Cache** | 已算好的 `K/V` 张量（单条序列内部） | 同一次生成的后续解码步 | 引擎内 / GPU 显存 | 把解码从 `O(n²)` 降到 `O(n)`，降 TPOT |
| **Prefix Cache** | 已算好的 KV blocks（跨请求共享） | token 序列**逐字相同的前缀** | 引擎内 / GPU→CPU→SSD 分层 | 免重算 prefill，降 TTFT |
| **Prompt Cache** | 同上，但**显式声明断点 + 有 TTL + 计费折扣** | 前缀逐字相同且未过期 | API 网关 / 引擎 | 降 TTFT + 降成本 |
| **Semantic Cache** | **最终回答文本**（可带元信息） | 语义相似 > 阈值（不是逐字相同） | LLM 网关 / 应用层 | 直接跳过推理，延迟→毫秒级 |

关键心智模型：

```text
KV Cache      —— 纵向（同一个请求，时间维度上不重算历史）
Prefix Cache  —— 横向（不同请求，相同前缀的 KV 复用）
Prompt Cache  —— Prefix Cache 的产品化封装（显式断点 / TTL / 计费）
Semantic Cache—— 跨出引擎，在答案层面复用（近似匹配）
```

命中率来源完全不同：**Prefix/Prompt 靠「字面重复」**（系统提示、工具定义、few-shot、多轮对话、RAG 同一文档），
**Semantic 靠「意图重复」**（不同用户问同一个意思）。前者 100% 等价、零风险；后者是概率匹配、有假阳性。

---

## 1. KV Cache：解码不重算历史

### 1.1 为什么需要

自回归解码第 `t` 步时，Attention 需要 **所有 `1..t` 位置** 的 K/V：

```text
q_t · [k_1, k_2, ..., k_t]ᵀ → softmax → × [v_1, ..., v_t]ᵀ
```

若不缓存，每生成一个 token 都要把整个前文重新前向一遍 → 总复杂度 `O(n²)`。
缓存后，每步只计算**新 token** 的 `q_t/k_t/v_t`，把 `k_t, v_t` 追加进缓存 → 总复杂度 `O(n)`。

这就是 **prefill（并行算整个 prompt，算力密集）** 与 **decode（逐 token 算，带宽密集）**
两阶段分离的根本原因，也是 **输出 token 比输入 token 贵** 的底层原因之一。

### 1.2 显存怎么算

单 token 的 KV 占用：

```text
per_token_bytes = 2 (K 和 V) × n_layers × n_kv_heads × head_dim × dtype_bytes
```

| 模型 | layers | kv_heads | head_dim | FP16 每 token | 8K 上下文 |
|---|---|---|---|---|---|
| Llama-3-8B (GQA) | 32 | 8 | 128 | 131,072 B ≈ **0.125 MB** | ≈ 1.0 GB |
| Llama-3-70B (GQA) | 80 | 8 | 128 | 327,680 B ≈ **0.32 MB** | ≈ 2.6 GB |
| 同规模 MHA (kv_heads=32) | 32 | 32 | 128 | ≈ 0.5 MB | ≈ 4.0 GB |

> 注意是 `n_kv_heads` 而非 `n_heads`：**MQA / GQA / MLA** 的本质收益就是压缩 KV Cache。
> GQA 把 32 个 KV head 压到 8 个（4× 省），MQA 压到 1 个，DeepSeek 的 **MLA** 用低秩潜向量压缩更激进。

总显存预算：

```text
KV 显存 = per_token_bytes × (并发请求数 × 平均上下文长度)
可用 KV 显存 = 总显存 − 模型权重 − 激活 − CUDA Graph / 框架预留
```

这条公式直接决定 **最大并发数** —— 显存墙比算力墙更容易先到。

### 1.3 显存管理的三次演进

1. **朴素预分配**：按 `max_seq_len` 给每个请求预留连续显存 → 内部碎片 + 外部碎片，利用率常 < 50%。
2. **PagedAttention（vLLM）**：把 KV 切成固定大小 **block**（如 16 token），按需分配、逻辑连续物理离散。
   - 碎片几乎归零；
   - **copy-on-write**：beam search / n>1 采样时多个分支共享同一前缀 block，只在写时复制；
   - block 是 Prefix Cache 的天然粒度单位。
3. **分层 + Offload**：GPU HBM → CPU DRAM → 本地 SSD → 远端 KV Store（如 LMCache / Mooncake），
   把冷 KV 换出，热 KV 换入，等价于给 KV Cache 做了一个「存储层次」。

### 1.4 压缩与淘汰

| 手段 | 做法 | 代价 |
|---|---|---|
| **KV 量化** | FP16 → FP8 / INT8（`--kv-cache-dtype fp8`） | 容量 ~2×，长上下文有轻微精度损失 |
| **GQA / MQA / MLA** | 减少或压缩 KV head | 需训练期决定 |
| **滑动窗口 / StreamingLLM** | 只保留 attention sink + 局部窗口 | 丢弃中段，长程召回下降 |
| **H2O / Heavy-Hitter** | 按 attention 分数淘汰「不重要」token | 需在线统计，有近似误差 |
| **KV Offload** | 冷 KV 换到 CPU/SSD | 换回时有 PCIe / IO 延迟 |

### 1.5 一个易踩的坑：位置编码

RoPE 是**相对**位置编码，缓存里存的是**已应用位置信息**的 K。因此：

- 同一前缀只要**起始 position id 一致**，KV 就能原样复用；
- 若复用时起始 position 变了（例如把缓存块接到不同位置），必须重新施加旋转，否则结果错误。
这是所有 prefix 复用实现绕不开的正确性前提。

---

## 2. Prefix Cache：跨请求共享相同前缀

### 2.1 动机

真实流量里 prefill 存在大量重复：

- **系统提示 / 工具定义 / schema**：同一应用下所有请求都一样，动辄 2K–10K token；
- **多轮对话**：第 N 轮请求的 prompt = 第 N−1 轮的 prompt + 回答（前缀完全重复）；
- **RAG**：同一篇文档被多个问题命中；
- **few-shot 示例**、**self-consistency / best-of-n 采样**、**beam search**：同一 prompt 多路；
- **Agent 循环**：每步都把完整历史重发一遍。

这些场景下重复 prefill 是纯浪费。Prefix Cache 让第二次及以后的请求**跳过已缓存前缀的 prefill**。

### 2.2 实现：内容寻址 + Radix Tree

核心思路是 **用 token 序列给 KV block 做哈希**，实现内容寻址：

```text
block_hash = hash(前缀 token ids + block 内 token ids + 可选 lora_id / 量化类型等)
```

- **vLLM（Automatic Prefix Caching）**：为每个 KV block 算 hash，维护 hash → block 的映射；
  新请求 prefill 时先查表，命中的 block 直接复用并增加引用计数，未命中的才计算；
  按 LRU 淘汰**引用计数为 0** 的 block。V1 起默认开启。
- **SGLang（RadixAttention）**：把所有序列组织成一棵 **Radix Tree（基数树）**，
  边是 token 序列，节点存对应 KV block。调度时在树上做最长前缀匹配；
  淘汰只在**叶子**上做 LRU，保证共享的祖先节点不会被误删；
  配合 **cache-aware 调度**（最长共享前缀优先），可显著提高命中率与吞吐。

```text
Radix Tree 示意（系统提示 S 被三个请求共享）：

              [root]
                │  S (system prompt)
                ▼
             [S 节点]  ← KV block 共享，refcnt=3
            ╱    │    ╲
       用户A    用户B   用户C(多轮)
```

### 2.3 收益与不收益的部分

- ✅ **TTFT 显著下降**：prefill 是 TTFT 的主要构成，前缀命中即省掉这部分算力；
- ✅ **prefill 算力节省** → 同样 GPU 能支撑更高并发 / 更长 prompt；
- ✅ **与 PagedAttention 天然协同**：共享是 block 粒度，copy-on-write 保证安全；
- ❌ **不影响 TPOT**（每输出 token 的时间）—— decode 阶段仍要逐步算；
- ❌ 若前缀不共享（每个请求都独一无二的短 prompt），几乎无收益，还多出哈希与查表开销。

### 2.4 「跨请求」到底跨什么

「跨请求共享」的**唯一条件是前缀 token 逐字相同**，与「是否同一会话/同一用户」**无关**。
因此实际包含三种情形：

| 情形 | 是否跨会话 | 共享的是什么 |
|---|---|---|
| 单请求内 n>1 采样 / beam search | 否（同一请求内） | 整个 prompt 的 KV |
| 同一会话的多轮对话 | 否（跨请求，同会话） | 上一轮 prompt + 回答组成的新前缀 |
| **不同会话 / 不同用户** | **是** | 共同的系统提示、工具定义、few-shot、同一篇 RAG 文档 |

换句话说：**跨会话只是跨请求的一个子集**，而且往往是最有价值的那个
（应用级系统提示被所有用户的请求共享，命中率最高）。

**作用域（生命周期）取决于缓存在哪一层**：

```text
引擎进程内存（radix tree / block hash）
  └─ 命中范围：打到「同一实例、同一进程」的请求
     └─ 进程重启 / 显存淘汰 → 失效
        └─ 加分层 KV Store（LMCache / Mooncake：GPU→CPU→SSD→远端）
           └─ 命中范围扩展到：跨实例、跨重启、跨会话、跨时间
```

所以严格说：**前缀缓存天然是「跨会话」的，但默认只在单实例内存内跨**；
要做成跨实例/跨重启的全局缓存，需要额外的分层存储组件。

### 2.5 多租户：会不会泄漏

**不能**。前缀缓存是**精确 token 匹配** —— 两个请求的前缀只要有一个 token 不同就不会命中，
而 KV 只是这些 token 的确定性函数，命中本身意味着「内容本来就是一样的」，
因此**不存在 A 用户读到 B 用户内容的路径**。

真正需要关注的多租户问题是另外三个：

1. **缓存 key 维度不全**：若 `model / LoRA adapter / KV dtype / 量化方式` 没进 key，
   会把错误的 KV 拿去复用 → 这是**正确性 bug**，不是泄漏。
2. **命中探测侧信道**：攻击者可用响应延迟反推「某段文本是否已被缓存」，
   从而推断他人是否发送过相同内容（属旁路信息，非内容泄漏）。
3. **缓存公平性与污染**：某租户的长前缀占满缓存，把其他租户的热前缀挤出去 → 需按租户做配额/公平淘汰。

### 2.6 工程注意点

| 事项 | 说明 |
|---|---|
| **路由亲和** | 多副本下，若请求随机打到不同实例，命中率暴跌。需按 `session_id / 租户 / prompt 前缀哈希` 做一致性路由 |
| **调度策略** | 优先调度与缓存前缀匹配最长的请求（SGLang cache-aware scheduling） |
| **缓存 key 维度** | 需把 `model / LoRA adapter id / KV dtype / 量化方式 / tokenizer` 纳入，否则会错配 |
| **block 边界** | 只有落在 block 边界上的前缀才能复用，尾部零头无法共享 |
| **淘汰策略** | 引用计数 + LRU，避免把「被很多人共享的热前缀」淘汰掉 |
| **多租户** | 精确匹配保证不泄漏；需处理 key 维度完整性、命中探测侧信道、缓存配额公平性 |

---

## 3. Prompt Cache：产品化的前缀缓存

### 3.1 与 Prefix Cache 的关系

**Prompt Cache = 前缀缓存的产品化形态**：引擎侧机制（Prefix Cache）+ 用户可见的接口
（显式缓存断点）+ 生命周期（TTL）+ 计费模型（读写不同价）。

Prefix Cache 是**隐式的、引擎自动的、尽力而为**的；Prompt Cache 是**显式的、用户可控的、有 SLA 语义**的。

### 3.2 两种形态

**A. 云端 API 的 Prompt Caching（以 Anthropic / OpenAI 为代表）**

- 在 prompt 中标记**缓存断点**（如 Anthropic 的 `cache_control: {type: "ephemeral"}`），
  断点及其之前的内容被缓存；
- 通常有 **最小可缓存长度**（约 1024 / 2048 token，随模型而异）和 **断点数量上限**（如 4 个）；
- 有 **TTL**，默认 5 分钟，可按需刷新（部分提供 1 小时选项）；
- **计费**：写入缓存略贵于普通输入（约 1.25×），读取缓存显著便宜（约 0.1×），
  未命中则按普通输入计价；
- OpenAI 侧为**自动**前缀缓存（无需显式标记，通常 1024 token 以上自动生效，
  缓存寿命一般 5–10 分钟，低峰可至约 1 小时，命中部分有折扣）。
  > 具体倍率、阈值与有效期随厂商和模型频繁调整，**以官方最新定价文档为准**。

**B. 自建侧的「Prompt as Artifact」**

把模板化 prompt 段（system / tools / few-shot / 长文档）**预计算成 KV 并持久化**，
请求到来时直接加载而非重算，可跨进程、跨机器、跨重启复用。适合：

- 系统提示极长且固定的 SaaS（如代码助手的仓库上下文）；
- 同一批文档反复被问的 RAG 服务；
- 需要把 KV 存到 CPU/SSD/对象存储做**分层缓存**的场景（LMCache / Mooncake 等）。

### 3.3 使用要点

1. **把稳定内容放前面，动态内容放后面**。前缀必须**逐 token 一致**才命中 ——
   把时间戳、request id、用户名插到 system prompt 开头，会让所有缓存失效。
2. **分层放断点**：`[system + tools] → 断点 → [长文档] → 断点 → [对话历史] → [当前问题]`，
   这样文档变更只失效后半段。
3. **算清楚账**：只有**复用次数足够多**才划算。若某前缀 5 分钟内只被调用一次，
   写入的溢价反而更贵。
4. **命中率必须监控**：`cache_read_tokens / (cache_read + cache_write + 常规 input tokens)`。
   低命中率通常意味着「前缀不稳定」或「TTL 与流量节奏不匹配」。

---

## 4. Semantic Cache：按语义复用答案

### 4.1 位置与流程

Semantic Cache 通常**不在推理引擎内**，而在 **LLM 网关 / 应用服务层**
（如 GPTCache、各类 AI Gateway、Redis 向量检索），可与 Prefix/Prompt Cache 叠加：

```text
用户 query
   │
   ├─① embedding → 向量库 ANN 检索（HNSW / IVF-PQ）
   │        │
   │        ├─ sim ≥ 阈值 且 namespace 匹配 → 直接返回缓存的 response  ✅ 毫秒级
   │        └─ 未命中 → ② 正常走 LLM（此时仍可享受 Prefix/Prompt Cache）
   │                        └─ ③ 写回 (query_embedding, response, 元信息)
```

### 4.2 关键参数

| 参数 | 典型值 | 说明 |
|---|---|---|
| **相似度阈值** | cosine 0.80 ~ 0.95 | 最核心的旋钮。阈值低→命中率高但假阳性多；高→安全但收益低 |
| **Embedding 模型** | 与业务语言/领域匹配 | 换模型必须**整体失效**缓存，向量空间不兼容 |
| **TTL** | 分钟 ~ 天 | 对时效敏感场景设短 TTL |
| **namespace / 分区键** | `tenant_id + model + prompt_version + 工具集` | **安全隔离的强制项** |
| **缓存内容** | 响应正文 + 模型/参数/来源引用/时间戳 | 便于审计与失效判断 |

### 4.3 风险（比前三种高一个量级）

| 风险 | 说明 | 缓解 |
|---|---|---|
| **假阳性** | 「怎么退款」vs「退款政策是什么」语义近但答案不同；**数字/日期/金额/专有名词** 尤其危险 | 提高阈值；对含数字/实体的 query 降权或强制回源；用小模型做二次校验（等价性判断） |
| **跨用户泄漏** | 命中了别人的个性化答案（订单号、余额、病历） → **严重安全事故** | 强制 namespace 隔离；PII 检测后不缓存；默认只缓存无个性化的通用回答 |
| **固化随机性** | `temperature > 0` 时缓存相当于把一次采样结果固化为标准答案，多样性丧失 | 只在 `temperature ≈ 0` 或确定性场景启用 |
| **陈旧答案** | 知识更新后仍返回旧答案 | TTL + 版本化 prompt/语料 + 主动失效 |
| **缓存污染** | 恶意/低质回答被缓存后扩散 | 写入前做质量/安全过滤；限制单点写入权限 |

### 4.4 适合 / 不适合

- ✅ **适合**：FAQ、客服、产品文档问答、代码解释、翻译、分类/抽取等**确定性**任务；
  查询分布长尾集中（Top-N 问题占大头的场景收益最大）。
- ❌ **不适合**：需要实时数据（股价、库存）、强个性化、强依赖当轮上下文的多轮对话、
  要求引用随召回变化的 RAG、需要审计每一次生成结果的合规场景。

> 与 RAG 的关系：语义缓存**不能替代** RAG。更稳妥的组合是「先查语义缓存 → 未命中走 RAG」，
> 或对**检索结果**做缓存而不是对最终答案做缓存（可控性更高）。

---

## 5. 横向对比与选型

| 维度 | KV Cache | Prefix Cache | Prompt Cache | Semantic Cache |
|---|---|---|---|---|
| 缓存粒度 | token 级 K/V 张量 | block 级 K/V（16 token 级） | 前缀段（≥ 千 token） | 请求级答案 |
| 匹配方式 | 同序列 | **字面前缀**精确 | **字面前缀**精确 + TTL | **语义**近似 |
| 等价性 | 精确 | 精确（bit-level 复用 KV） | 精确 | **近似，有假阳性** |
| 生效位置 | 引擎内核 | 引擎调度/内存管理 | API 网关 + 引擎 | 应用/网关层 |
| 优化指标 | TPOT、吞吐 | TTFT、prefill 算力 | TTFT + 成本 | **端到端延迟、成本** |
| 主要成本 | 显存 | 显存 + 哈希/树维护 | 写入溢价 | 向量库 + 假阳性风险 |
| 失效触发 | 请求结束释放 | LRU / 显存压力 | TTL 到期 | TTL / 版本变更 |
| 是否默认可用 | 总是开启 | vLLM V1、SGLang 默认开启 | 需显式标记或满足长度门槛 | 需自行搭建 |
| 主要风险 | 显存 OOM | 命中率低、路由打散 | 前缀不稳定→白付溢价 | **答案错误 / 数据泄漏** |

**选型决策链**：

```text
1. 显存是否够？              → KV 量化 / GQA / Offload / 分层缓存
2. 是否有大量共享前缀？       → 开 Prefix Cache + 一致性路由 + cache-aware 调度
3. 用云 API 且系统提示很长？   → 用 Prompt Caching，拆分断点，监控命中率
4. 查询是否高度重复且低风险？  → 加 Semantic Cache，严控阈值与 namespace
5. 都不满足？                → 别上缓存，先做 prompt 瘦身 / 模型选型 / 流式输出
```

---

## 6. 落地检查清单

**引擎侧（自建）**

- [ ] `--enable-prefix-caching`（vLLM V1 默认）或 SGLang RadixAttention 已开启
- [ ] 监控 **prefix cache hit rate**、GPU KV cache utilization、eviction 次数
- [ ] 按 `session_id / 前缀哈希` 做一致性路由，避免多副本打散
- [ ] 对长上下文开启 KV 量化（`fp8`）并做精度回归
- [ ] 多租户场景确认缓存 key 含 model/adapter/dtype，并设置租户级缓存配额
- [ ] 多 LoRA / 多模型确认缓存 key 含 adapter/model 标识

**API 侧（云厂商）**

- [ ] system prompt 与工具定义置顶且**完全静态**（禁时间戳/random id）
- [ ] 合理设置 1–4 个缓存断点，稳定段在前、动态段在后
- [ ] 估算复用次数，确认「写入溢价 < 读取折扣 × 命中次数」
- [ ] 让 TTL 与业务会话节奏对齐（长会话考虑周期性刷新）

**Semantic Cache 侧**

- [ ] 阈值先设高（0.92+）再按 badcase 逐步下调
- [ ] namespace 必须含 `tenant_id`，敏感/PII 内容**不缓存**
- [ ] 只在 `temperature ≈ 0` 场景启用
- [ ] 记录每次命中，保留「强制回源」开关与人工审计样本
- [ ] embedding 模型升级 → 整体失效

---

## 7. 关联

- [[concepts/Transformer 架构]] — Attention / KV 的来源
- [[concepts/FlashAttention 注意力内核]] — KV 读写的内核层优化
- [[concepts/RAG 检索 增强 生成]] — 共享长文档前缀是 Prefix Cache 的典型场景
- [[concepts/向量 DB 嵌入]] — Semantic Cache 的检索底座
- [[concepts/分词器 LLM]] — 前缀逐 token 一致的前提
- [[concepts/模型 压缩 蒸馏]]、[[concepts/LoRA PEFT 微调]] — 影响缓存 key 与显存预算

## 8. 参考

- vLLM: PagedAttention / Automatic Prefix Caching 文档
- SGLang: RadixAttention（*Efficiently Serving LLM Programs with SGLang*）
- Anthropic: Prompt Caching 文档（cache_control / TTL / 计费倍率）
- OpenAI: Prompt Caching 文档（自动前缀缓存 / 门槛 / 折扣）
- LMCache、Mooncake：分层 KV Cache 与 Offload
- GPTCache：Semantic Cache 开源实现
