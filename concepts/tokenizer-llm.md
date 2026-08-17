---
lifecycle: draft
base_confidence: 0.84
category: reference
tags:
  - llm
  - tokenizer
  - bpe
  - tokenization
  - active
aliases:
  - Tokenizer
  - 分词器
  - BPE
  - Token
---

# Tokenizer 分词器

## 概述

Tokenizer 是将自然语言文本转换为模型可处理的离散 token 序列的关键组件。分词质量直接影响模型的词汇覆盖能力、训练效率和推理成本。

---

## 分词算法对比

| 算法 | 核心思想 | 词表策略 | 代表模型 |
|------|---------|---------|---------|
| **BPE** (Byte Pair Encoding) | 迭代合并频率最高的相邻字节对 | 贪心合并，固定词表大小 | GPT-2/3/4, LLaMA |
| **WordPiece** | 基于似然最大化合并，选择使语言模型似然增加最大的子词 | 类似 BPE，但用概率选择 | BERT, DistilBERT |
| **Unigram** | 从大词表开始迭代删减，删除对整体似然损失最小的子词 | 自顶向下删减 | T5, ALBERT |
| **SentencePiece** | 将文本视为原始字节流，直接在未分词文本上训练 BPE/Unigram | 语言无关，支持 UNK=0 | LLaMA, Gemma, Qwen |

### 关键区别

- BPE 和 WordPiece 是**自底向上**合并策略（从字符到词）
- Unigram 是**自顶向下**删减策略（从候选集中筛选）
- SentencePiece 不依赖预分词，直接处理原始字节

---

## 词表大小与模型性能

| 模型 | 词表大小 | 分词算法 | 特点 |
|------|---------|---------|------|
| GPT-2 | 50,257 | BPE | 英文为主，中文效率低 |
| GPT-4 | ~100,000 | Tiktoken (BPE) | 多语言优化 |
| LLaMA-2 | 32,000 | SentencePiece (BPE) | 英文为主 |
| LLaMA-3 | 128,256 | Tiktoken (BPE) | 多语言增强，128K 词表 |
| Qwen-2.5 | 151,643 | Tiktoken (BPE) | 中文优化，超大词表 |
| BERT | 30,522 | WordPiece | 中文按字切分 |

### 词表大小权衡

- **词表过小** -> 序列更长（OOV 多），增加计算成本
- **词表过大** -> Embedding 层参数增加，稀有 token 训练不足
- 最佳实践：根据目标语言和模型规模选择 32K-150K 词表

---

## Token 计数与成本估算

### 经验法则

| 语言 | 平均 token 数 | 说明 |
|------|-------------|------|
| 英文 | ~1.3 token/词 | 常见词为单 token |
| 中文 | ~0.6-1.5 token/字 | 取决于词表覆盖度 |
| 代码 | ~1.5 token/符号 | 关键字、变量名通常为单 token |

### 成本计算公式

```
API 费用 = (input_tokens + output_tokens) x 单价

示例 (GPT-4o):
- 输入 $2.50 / 1M tokens
- 输出 $10.00 / 1M tokens
- 1 万字中文 ~ 10,000 tokens -> 输入约 $0.025
```

### 实用工具

- OpenAI Tokenizer: https://platform.openai.com/tokenizer
- tiktoken 库: Python 直接计算 token 数

---

## 特殊 Token

| Token | 含义 | 使用场景 |
|-------|------|---------|
| bos (Beginning of Sequence) | 序列起始 | 生成任务起始标记 |
| eos (End of Sequence) | 序列结束 | 控制生成终止 |
| pad (Padding) | 填充 | 批处理对齐 |
| im_start | ChatML 消息起始 | Qwen 对话格式 |
| im_end | ChatML 消息结束 | Qwen 对话格式 |
| system/user/assistant | 角色标记 | 对话系统角色区分 |
| unk (Unknown) | 未知 token | 未在词表中出现的字符 |
| mask | 掩码标记 | BERT MLM 预训练 |

---

## 常见坑

### 1. 中文分词效率低

- GPT-2 词表中中文字符极少，一个汉字可能被拆成 2-4 个 byte token
- 解决：使用针对中文优化的词表（Qwen 151K、ChatGLM 65K）

### 2. Emoji 和特殊字符处理

- Emoji 可能被拆成多个 token，占用大量上下文窗口
- 代码中的缩进、特殊符号可能被合并成意外的 token

### 3. Token 限制截断

- context window 限制是 token 数而非字符数
- 长文本需按 token 边界截断，避免破坏语义

### 4. Tokenizer 版本不一致

- 同一模型不同版本可能使用不同 tokenizer
- 微调时必须使用与预训练一致的 tokenizer

---

## 延伸阅读

- [[transformer-architecture]] - Transformer 架构中 Embedding 层的 token 处理
- [[llm-inference-optimization]] - 推理阶段 KV Cache 与 token 的关系
- SentencePiece 官方文档: https://github.com/google/sentencepiece
- HuggingFace Tokenizers: https://github.com/huggingface/tokenizers
