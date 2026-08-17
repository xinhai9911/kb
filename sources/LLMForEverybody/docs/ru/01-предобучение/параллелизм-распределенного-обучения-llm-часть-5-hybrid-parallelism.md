# Параллелизм распределенного обучения LLM, часть 5: hybrid parallelism

## Введение

Возможно, вы уже много раз слышали о 3D parallelism. Ранее мы обсуждали data parallelism, pipeline parallelism и tensor parallelism; все они относятся к 1D parallelism.

В некоторых классификациях pipeline parallelism и tensor parallelism относят к техникам model parallelism.

Hybrid parallelism означает одновременное использование нескольких техник parallelism: например, data parallelism и model parallelism, data parallelism и pipeline parallelism или data parallelism и tensor parallelism.

## DP+PP

Сочетание data parallelism и pipeline parallelism - очень распространенная техника 2D hybrid parallelism.

На рисунке ниже, взятом из [руководства DeepSpeed по pipeline parallelism](https://www.deepspeed.ai/tutorials/pipeline/), показано, как объединить `DP` и `PP`.

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（五）混合并行/8.png)

Здесь важно увидеть, что `DP Rank 0` не видит GPU2, а `DP Rank 1` не видит GPU3. С точки зрения `DP`, есть только GPU0 и GPU1, и он подает им данные так, будто GPU всего два. GPU0 с помощью `PP` "тайно" делает `offload` части нагрузки на GPU2. GPU1 делает то же самое через GPU3.

Поскольку для каждого измерения нужно как минимум 2 GPU, в этом примере требуется минимум 4 GPU.

## DP+PP+TP

Для более эффективного обучения появился 3D parallelism: `PP` объединяют с `TP` и `DP`, как показано на рисунке ниже.

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（五）混合并行/9.png)

Рисунок взят из блога [3D parallelism: Scaling to trillion-parameter models](https://www.microsoft.com/en-us/research/blog/deepspeed-extreme-scale-model-training-for-everyone/).

Поскольку для каждого измерения нужно как минимум 2 GPU, здесь требуется минимум 8 GPU.

## DP+PP+TP+ZeRO

Это то, что часто называют 4D parallelism. ZeRO - техника, предложенная DeepSpeed: она делит параметры модели на несколько частей, каждая часть вычисляется на отдельном устройстве, а затем результаты собираются вместе. По сути, это сочетание ZeRO-DP с `PP` и, опционально, `TP`.

О ZeRO-DP см. статью [Параллелизм распределенного обучения LLM, часть 2: data parallelism](параллелизм-распределенного-обучения-llm-часть-2-data-parallelism.md).

Важно: когда ZeRO-DP объединяют с `PP` и, опционально, `TP`, обычно включают только Stage 1 ZeRO, то есть optimizer sharding.

Теоретически Stage 2 ZeRO, то есть gradient sharding, можно использовать вместе с `PP`, но это отрицательно влияет на производительность.

Каждый micro-batch требует дополнительной collective-операции Reduce-Scatter, чтобы агрегировать gradients перед sharding. Это может значительно увеличить коммуникационные накладные расходы. Из-за природы `PP` используются micro-batches меньшего размера внутри Macro-Batch, а основная задача - сбалансировать arithmetic intensity, то есть размер micro-batch, и минимизацию pipeline bubbles, то есть число micro-batches. Поэтому такие коммуникационные расходы становятся заметными.

Кроме того, из-за `PP` число слоев уже меньше, чем в обычном случае, поэтому экономия памяти будет не очень большой. `PP` уже уменьшает размер gradients до `1/PP`, и на этой основе дополнительная экономия от gradient sharding не так заметна, как в чистом `DP`.

По той же причине Stage 3 ZeRO тоже не лучший выбор: он требует еще больше межузловой коммуникации.

Так как у нас есть ZeRO, появляется еще одно преимущество - ZeRO-Offload. Поскольку используется Stage 1, optimizer states можно выгрузить на CPU.

## Ссылки

<div id="refer-anchor-1"></div>

[1] [Model Parallelism](https://huggingface.co/docs/transformers/v4.15.0/en/parallelism)

[2] [Pipeline Parallelism tutorial](https://www.deepspeed.ai/tutorials/pipeline/)

[3] [3D parallelism: Scaling to trillion-parameter models](https://www.microsoft.com/en-us/research/blog/deepspeed-extreme-scale-model-training-for-everyone/)

## GitHub и WeChat автора

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы. Проект полностью open source, приветствуются Star и Fork!
