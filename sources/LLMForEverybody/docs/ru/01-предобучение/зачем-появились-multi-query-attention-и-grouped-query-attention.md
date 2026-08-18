## Введение

Если посмотреть статьи серии GPT, то self-attention, который вы изучаете, — это **Multi-Head Attention** (MHA), то есть механизм многоголового внимания.
MHA содержит $h$ матриц Query, Key и Value, а веса матриц Key и Value у всех attention head (head) не являются общими.

Этот механизм уже хорошо улавливает информацию. Почему же затем появились MQA и GQA?

Во многих статьях сразу приводят математические различия между этими тремя механизмами attention, но не объясняют, зачем при наличии MHA понадобились MQA и даже GQA. В этой статье кратко разберем причину и дадим интуитивное понимание.

![alt text](<../../../01-第一章-预训练/assest/为什么会发展出Multi Query Attention和Group Query Attention/1.PNG>)

## KV Cache

По мере роста числа параметров больших моделей скорость inference тоже столкнулась с серьезными вызовами. Поэтому стали использовать KV Cache, пытаясь обменять пространство на время.

> статья про kv cache

## MQA

Но после увеличения потребления памяти проблемой стала уже VRAM, поэтому исследователи попробовали разделять keys и values внутри механизма attention, чтобы уменьшить содержимое KV cache.
Так появился Multi-Query Attention (MQA): query по-прежнему несколько, а keys и values только одни, и все query используют общий набор. Благодаря этому KV Cache становится меньше.

## GQA

Недостаток MQA в том, что он приводит к потере точности, поэтому исследователи предложили компромиссный вариант: не все query используют один общий набор KV, а query внутри одной group используют один общий набор KV. Это одновременно снижает объем KV cache и помогает сохранить точность. Так появился Grouped-Query Attention.


## Ссылки

<div id="refer-anchor-1"></div>

[1] [GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints]( https://arxiv.org/pdf/2305.13245)

[2] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
