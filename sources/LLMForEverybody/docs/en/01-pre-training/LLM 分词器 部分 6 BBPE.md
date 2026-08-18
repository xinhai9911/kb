---
aliases: ["llm-tokenizers-part-6-bbpe"]
---

# Understanding LLM Tokenizers, Part 6: BBPE

BBPE is a BPE-based tokenizer, a BPE variant proposed by the Google Brain team. Its full name is Byte-level BPE, meaning a BPE tokenizer at the byte level.

## 1. Intuitive Understanding

For BPE, see the previous article: [Understanding LLM Tokenizers, Part 2: BPE (Byte-Pair Encoding)](LLM 分词器 部分 2 BPE.md)

The key idea of BBPE is to merge pairs of symbols in text, which are byte pairs in UTF-8, to form frequent lexical or character patterns. The process continues until the target vocabulary size is reached or no more merges can be performed.

The difference between BPE and BBPE is that BPE works at the character level, while BBPE works at the byte level.

BBPE has these advantages:

- cross-language universality: because it is based on byte-level representation, it is easier to transfer across different languages and writing systems;
- smaller vocabulary size: by merging byte pairs, BBPE can produce more universal subword units and reduce vocabulary size;
- handling rare characters and OOV: BBPE handles rare characters more effectively because it does not allocate a separate vocabulary entry for every rare character, but processes them as byte sequences.

![alt text](../../../01-第一章-预训练/assest/搞懂大模型的分词器（六）/1.png)

## Series Summary

In this tokenizer series, we started with the simplest word-level and character-level methods and discussed the pros and cons of tokenizing by words and by characters.

Then we introduced subword-level tokenizers, including BPE, WordPiece, Unigram, and others.

Finally, we looked at two variants. The first is the SentencePiece tool: it treats multilingual text as a sequence of Unicode characters and does not depend on language-specific logic. SentencePiece can be based on BPE or Unigram, and it can also use BBPE.

The second is the BBPE algorithm, a byte-level BPE tokenizer where the minimum unit is the byte.

![alt text](../../../01-第一章-预训练/assest/搞懂大模型的分词器（六）/0.png)

You now know the basic principles and implementation ideas behind tokenizers. Next, we will cover even more LLM knowledge, so stay tuned.

## References

[1] [Unigram tokenization](https://huggingface.co/learn/nlp-course/en/chapter6/7?fw=pt)

## Follow My GitHub and WeChat. No Time to Explain, Hop In.

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository contains the original Markdown files, all fully open source. Stars and forks are welcome.


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
