Фреймворки инференса больших моделей (часть 4): TensorRT-LLM

`TensorRT-LLM` [1](#refer-anchor-1) - это open-source библиотека от NVIDIA для оптимизации производительности инференса больших языковых моделей (`LLMs`) на NVIDIA GPU. Благодаря набору продвинутых оптимизаций, таких как quantization, kernel fusion, dynamic batching и multi-GPU support, она существенно повышает скорость инференса LLMs. По сравнению с традиционными CPU-based подходами скорость инференса может вырасти до 8 раз.

## 1. Fast Transformer или TensorRT-LLM?

Fast Transformer больше не обновляется!!

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/0.png>)

TensorRT-LLM можно рассматривать как сочетание TensorRT и FastTransformer, созданное для ускорения инференса больших моделей. Он не только включает оптимизации Transformer из FastTransformer - attention optimization, softmax optimization, operator fusion и другие подходы, - но и добавляет множество возможностей, ориентированных на оптимизацию инференса больших моделей.

`TensorRT` - это SDK (software development kit), разработанный NVIDIA для высокопроизводительного deep learning inference на GPU. Он может оптимизировать neural network models, ускорять процесс инференса и существенно повышать производительность и эффективность инференса на GPU. Основные возможности TensorRT:

1. **Оптимизация моделей**: TensorRT может импортировать модели, обученные в основных deep learning frameworks, и генерировать оптимизированные runtime engines, которые можно развертывать в data centers, automotive и embedded environments.

2. **Высокопроизводительная оптимизация инференса**: TensorRT значительно ускоряет инференс за счет layer fusion, precision calibration, kernel auto-tuning и других технологий.

3. **Низкая latency**: TensorRT оптимизирует computation graph и использование памяти, тем самым заметно снижая latency инференса и подходя для real-time AI applications.

4. **Поддержка нескольких precision modes**: TensorRT поддерживает FP32, FP16, INT8 и другие precision modes, позволяя балансировать между точностью и производительностью.


## 2. Технологии ускорения инференса

1. Quantization

Quantization - это метод оптимизации моделей в области LLM, особенно при развертывании моделей в средах с ограниченными ресурсами, таких как mobile devices, embedded systems или серверы, где требуется низкая latency. Базовая идея quantization - преобразовать веса и activation values модели из floating point numbers (например, 32-bit floating point, FP32) в представление более низкой точности, например 8-bit integers (`INT8`) или форматы с еще меньшей разрядностью.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/1.png>)

2. In-flight Batching

Также называется Continuous Batching. Это технология повышения эффективности LLM inference. Она непрерывно обрабатывает несколько входных samples, сокращает простои во время инференса, повышает compute efficiency и throughput. В LLM inference batching нескольких входных samples позволяет эффективнее использовать вычислительные ресурсы GPU, уменьшать ожидание в процессе инференса и повышать общую скорость инференса.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/2.png>)

3. Attention

`KV Cache` использует идею обмена памяти на время: повторно использует KV cache из предыдущего шага инференса, что может сильно снизить давление на память и повысить производительность инференса, не влияя на вычислительную точность.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/3.png>)

В decoder-архитектуре основой является стек self-attention структур из transformer. Суть KV-cache в том, что для генерации следующего token используются ранее вычисленные key-value и текущий query.

`prefill` означает, что при генерации первого token в `kv` еще нет никакого cache: нужно предварительно заполнить KV-матрицу, соответствующую prompt, и закэшировать ее. Поэтому первый token генерируется медленнее всего, а начиная со второго token cache быстро извлекается, и `kv` предыдущего token также добавляется в cache.

Как видно, это схема обмена памяти на время: cache постоянно растет. Поэтому при расчете видеопамяти для приватного развертывания нужно учитывать не только размер модели, но и размеры prompt и completion в вашем приложении (и, конечно, batch-size).

Но после увеличения использования памяти видеопамять снова становится проблемой. Поэтому люди начали пробовать совместно использовать keys и values внутри attention mechanism, чтобы уменьшить содержимое KV cache.

Так появился `Multi-Query Attention(MQA)`: query по-прежнему несколько, а keys и values только одни, и все query совместно используют одну группу. За счет этого KV Cache становится меньше.

Но недостаток MQA - потеря точности. Поэтому исследователи предложили компромисс: не все query совместно используют одну группу KV, а query внутри одного group совместно используют одну группу KV. Так можно уменьшить KV cache и одновременно сохранить точность. Так появился `Group-Query Attention(GQA)`.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/4.PNG>)

4. Graph Rewriting

Graph Rewriting - это технология оптимизации neural network models в TensorRT-LLM. Перед развертыванием deep learning model на hardware обычно выполняется процесс graph optimization, который называется graph rewriting. TensorRT-LLM использует declarative approach для определения neural networks: это означает, что модель строится через описание ее структуры и операций, а не через пошаговое программирование.

С помощью graph rewriting TensorRT-LLM может генерировать оптимизированный execution graph для конкретной hardware platform, обеспечивая эффективную производительность инференса на NVIDIA GPU. Такая оптимизация может значительно повысить скорость работы модели, снизить latency и увеличить общий throughput, что особенно важно при обработке больших языковых моделей.

## Ссылки

<div id="refer-anchor-1"></div>

[1] [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM/tree/release/0.5.0)

## Добро пожаловать на мой GitHub и в WeChat-аккаунт [真-忒修斯之船]: объяснять некогда, поднимайтесь на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы, проект полностью open-source. Буду рад вашим Star и Fork!


---

## 📚 相关概念

[[concepts/LLM 推理 优化|LLM 推理 优化]] | [[concepts/推测解码|推测解码]] | [[concepts/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/vllm|vllm]] | [[entities/tensorrt-llm|tensorrt-llm]] | [[entities/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[concepts/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
