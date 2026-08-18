# Параллелизм распределенного обучения LLM, часть 4: tensor parallelism

## Введение

В архитектуре Transformer есть две основные вычислительно тяжелые части: Self-Attention и MLP. В предыдущих статьях мы уже разобрали model parallelism и data parallelism. В этой статье рассмотрим tensor parallelism - более мелкозернистый способ параллелизма, который позволяет еще сильнее повысить эффективность обучения модели.

Tensor parallelism использует свойство матричного умножения: его можно вычислять параллельно. Параметры модели делятся на несколько частей, каждая часть вычисляется на отдельном устройстве, а затем результаты собираются вместе. Ниже отдельно посмотрим, как tensor parallelism реализуется для FFN и Self-Attention.

## MLP

Основные строительные блоки MLP - полностью связанные `nn.Linear`, за которыми идет нелинейная активация GeLU.

Следуя обозначениям из статьи Megatron [2], точечное произведение можно записать как `Y = GeLU(XA)`, где `X` и `Y` - входной и выходной векторы, а `A` - матрица весов.

Если посмотреть на вычисления в матричной форме, легко увидеть, как матричное умножение можно разделить между несколькими GPU:

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（四）张量并行/4.png)

Если разделить матрицу весов `A` по столбцам на `N` GPU и параллельно выполнить матричные умножения от `XA_1` до `XA_n`, мы получим `N` выходных векторов `Y_1`, `Y_2`, ..., `Y_n`. Эти векторы можно независимо подать в GeLU:

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（四）张量并行/5.png)

Используя этот принцип, можно обновлять MLP любой глубины без синхронизации между GPU до самого конца, когда понадобится заново собрать выходной вектор.

Авторы статьи Megatron-LM приводят для этого полезный пример:

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（四）张量并行/6.png)

## Self-Attention

Tensor parallelism для Self-Attention еще проще, потому что self-attention естественным образом является multi-head attention: вычисление каждого head можно назначить на отдельный GPU.

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（四）张量并行/7.png)

На рисунке выше self-attention можно параллельно вычислять на 2 GPU: каждый GPU считает attention-механизм для одного head. В принципе, сколько есть heads, столько GPU можно использовать для параллельного вычисления.

> Важное замечание: `TP` требует очень быстрой сети, поэтому не рекомендуется использовать `TP` между несколькими узлами. На практике, если в одном узле 4 GPU, максимальная степень `TP` равна 4. Если нужна степень `TP` 8, нужен узел как минимум с 8 GPU.

В следующей статье посмотрим на hybrid parallelism.

## Ссылки

<div id="refer-anchor-1"></div>

[1] [Model Parallelism](https://huggingface.co/docs/transformers/v4.15.0/en/parallelism)

[2] [Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM](https://arxiv.org/abs/2104.04473)

## GitHub и WeChat автора

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы. Проект полностью open source, приветствуются Star и Fork!


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
