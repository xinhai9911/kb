Разбираемся с оптимизаторами нейронных сетей за 3 минуты в день (часть 10): Nadam

## 1. Появление алгоритма Nadam
Алгоритм Nadam (Nesterov-accelerated Adaptive Moment Estimation) был предложен Tim Salimans et al. в 2016 году. Он объединяет преимущества Adam и Nesterov Accelerated Gradient (NAG), чтобы повысить качество оптимизации. Подробное описание и принципы алгоритма Nadam можно найти в статье «Incorporating Nesterov Momentum into Adam» [1](#refer-anchor-10), впервые отправленной на arXiv в 2016 году и позже опубликованной на конференции ICLR 2017.

## 2. Принцип работы алгоритма Nadam

Nadam (Nesterov-accelerated Adaptive Moment Estimation) - это оптимизатор, который объединяет Nesterov momentum (NAG) и алгоритм оптимизации Adam. Он предназначен для повышения качества процесса оптимизации, особенно в глубоком обучении.

Правила обновления Nadam выглядят так:

1. Инициализировать оценку первого момента (momentum) $m_0$ и оценку второго момента (скользящее среднее квадратов градиентов) $v_0$ нулями, а также задать временной шаг $t=1$;
2. На каждой итерации вычислить градиент $g_t$;
3. Обновить оценку первого момента $m_t$ и оценку второго момента $v_t$:

   $m_t = \beta_1 \cdot m_{t-1} + (1 - \beta_1) \cdot g_t$

   $v_t = \beta_2 \cdot v_{t-1} + (1 - \beta_2) \cdot g_t^2$

4. Вычислить скорректированную на смещение оценку первого момента $\hat{m}_t$ и оценку второго момента $\hat{v}_t$:

   $\hat{m}_t = \frac{m_t}{1 - \beta_1^t}$

   $\hat{v}_t = \frac{v_t}{1 - \beta_2^t}$

5. Вычислить специфичный для Nadam скорректированный momentum $\hat{m}_t^{'}$:

   $\hat{m}_t^{'} = \beta_1 \cdot m_{t-1} +\frac{(1 - \beta_1) \cdot g_t}{1 - \beta_1^t}$

6. Обновить параметры $\theta$:

   $\theta_t = \theta_{t-1} - \eta \cdot \frac{\hat{m}_t^{'}}{\sqrt{\hat{v}_t} + \epsilon}$

В формуле обновления Nadam $\hat{m}_t^{'}$ - это скорректированный momentum, объединенный с Nesterov momentum; при вычислении обновления он учитывает скорость предыдущего шага. Эта особенность, связанная с Nesterov momentum, является главным отличием Nadam от Adam.

## 3. Основные особенности алгоритма Nadam

Преимущества алгоритма Nadam включают:
- Он объединяет преимущества Nesterov momentum и Adam: обладает и адаптивным learning rate, и Nesterov momentum, поэтому может сходиться быстрее.
- Хорошо работает при оптимизации моделей глубокого обучения.

Возможные недостатки алгоритма Nadam:
- Нужно вручную задавать начальный learning rate и два коэффициента затухания, поэтому настройка гиперпараметров достаточно сложна.
- Может приводить к колебаниям в процессе обучения, особенно при высоком learning rate.
- Поскольку он объединяет Adam и Nesterov momentum, процесс оптимизации может стать слишком сложным, что увеличивает вычислительную нагрузку.

На практике Nadam обычно используют для обучения моделей глубокого обучения, особенно когда нужна быстрая сходимость и оптимизация на разреженных наборах данных. Во многих случаях он дает хорошую производительность, но при использовании важно настраивать гиперпараметры, чтобы добиться лучшего результата.

![alt text](../../../01-第一章-预训练/assest/神经网络的优化器（十）Nadam/0.png)

## Ссылки

<div id="refer-anchor-10"></div>

[1] [Incorporating Nesterov Momentum into Adam](https://openreview.net/forum?id=OM0jvwB8jIp57ZJjtNEZ)

## GitHub и WeChat автора

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы, он полностью open source. Буду рад вашим Star и Fork!


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
