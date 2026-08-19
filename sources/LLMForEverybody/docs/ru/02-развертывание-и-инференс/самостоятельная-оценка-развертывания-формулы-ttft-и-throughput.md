Оценка производительности приватного развертывания большой модели

## Приватное развертывание?

Если вы тоже оказались в волне приватного развертывания DeepSeek R1, ваш руководитель может попросить вас оценить, какие аппаратные ресурсы нужны для развертывания модели версии XX и каким будет TPS. Для этого вы, возможно, начнете искать в интернете разные тесты и увидите примерно такую картинку:

![alt text](../../../02-第二章-部署与推理/assest/私有化部署大模型性能估计/0.PNG)

Такие бенчмарки в основном измерены организациями или пользователями на собственных машинах. Есть ли способ быстро получить оценочное значение для общего понимания, даже если оно будет не очень точным?

Сегодня мы вместе разберем:

1. Какие метрики производительности есть у инференса больших моделей
2. От чего зависит производительность инференса больших моделей
3. Как быстро оценить теоретический предел производительности инференса по уже имеющейся информации

## 1. Метрики производительности инференса больших моделей

Вы могли слышать термины TTFT, TPOT, Throughput, Latency, TPS и другие. Посмотрим, что каждый из них означает:

- TTFT(Time To First Token)
  То есть задержка первого token: задержка от ввода до вывода первого token.
  На этапе инференса большой модели используется KV Cache, поэтому есть два этапа: Prefilling и Decoding. TTFT — это время, за которое большая модель завершает создание KV cache для prompt и генерирует первый Token.

- TPOT(Time Per Output Token),
  В Decoding это средняя задержка каждого output token (без первого Token).

- Latency(задержка)
  - Теоретически это время от ввода до вывода последнего token. Принципиальная формула расчета: Latency = (TTFT) + (TPOT) * (number of tokens);

- TPS(Tokens Per Second)
  - Обычно означает количество token в секунду для одного запроса, иногда — общий throughput параллельных запросов; достаточно смотреть на контекст. Способ расчета: number of tokens / Latency;

- Throughput пропускная способность
  - При наличии параллельности это общее количество token в секунду по нескольким запросам.

## 2. Факторы, влияющие на производительность больших моделей

Какие факторы влияют на производительность больших моделей?

Она связана с самой большой моделью, GPU, используемым для инференса, фреймворком, длиной prompt, уровнем параллельности и другими факторами. Ниже рассмотрим подробнее.

### 2.1. Сама большая модель

  Сначала нужно посмотреть, какая у модели архитектура: Dense или MoE. В Dense-архитектуре во время инференса активируются все параметры; в MoE-архитектуре, например DeepSeek R1, у модели 671B параметров, но активируются только 37B. Скорость инференса связана с размером активируемых параметров.

  Кроме того, каждый параметр может использовать разную точность, например BF16, Int8 и т. д. Чем ниже точность, тем быстрее инференс.

![alt text](../../../02-第二章-部署与推理/assest/私有化部署大模型性能估计/1.png)

### 2.2 GPU

У GPU много параметров. Для инференса больших моделей главные три: размер видеопамяти, вычислительная мощность и скорость коммуникации. Рассмотрим их по очереди:

![alt text](../../../02-第二章-部署与推理/assest/私有化部署大模型性能估计/2.png)

Когда мы говорим о видеопамяти видеокарты, обычно имеется в виду что-то вроде HBM (High Bandwidth Memory). Во время инференса мы помещаем всю большую модель в видеопамять, а также сохраняем постоянно растущий KV Cache и промежуточные вычислительные значения.

Коммуникационная способность в основном делится на три части: коммуникация внутри карты, коммуникация между картами внутри узла и коммуникация между узлами. Коммуникация внутри карты: типичный пример — во время вычислений GPU загружает данные из HBM в SRAM, выполняет операции в SRAM, а затем передает результат обратно в HBM для хранения.

Коммуникация между картами внутри узла и между узлами обычно нужна, когда одна видеокарта не может загрузить всю модель, поэтому во время вычислений данные приходится передавать между картами.

![alt text](../../../02-第二章-部署与推理/assest/私有化部署大模型性能估计/5.png)

Вычислительная мощность и утилизация GPU: у одной и той же видеокарты чем выше точность, тем ниже вычислительная мощность. При этом из-за планирования и коммуникации обычно невозможно полностью загрузить всю вычислительную мощность GPU.

Утилизация GPU: когда мы говорим об утилизации GPU, обычно имеется в виду использование вычислительной мощности GPU. Поскольку сейчас коммуникационные возможности улучшаются гораздо медленнее, чем вычислительная мощность, коммуникация становится бутылочным горлышком. Из-за слабой коммуникации вычислительные блоки GPU часто ждут данные и простаивают.

![alt text](../../../02-第二章-部署与推理/assest/私有化部署大模型性能估计/3.png)

### 2.3. Фреймворк инференса

Используются ли Flash Attention, Page Attention и т. д.

Может ли фреймворк полноценно планировать работу GPU.

### 2.4. Способ инференса

Длина prompt и Batch-size.


## 3. Как быстро оценить объем вычислений инференса

Если вычислительная мощность зафиксирована, то для получения TTFT, Throughput и других данных нужно знать, каков объем вычислений на этапах Prefilling и Decoding.

Простая оценка:

Prefilling_FLOPs = 2 * Batch_size * Prompt_size * Parameters

Decoding_FLOPs_Per_Step = 2 * Batch_size * Parameters

Decoding_FLOPs = 2 * Batch_size * Completion_size * Parameters

Однако если вы хотите внимательно проверить объем вычислений на каждом шаге, можно взять Qwen2.5-32B и отдельно посчитать FLOPs для двух этапов.

Сначала посмотрим структуру модели. Структура модели Qwen2.5-32B выглядит так:

```python
config = {
  "attention_dropout": 0.0,
  "bos_token_id": 151643,
  "eos_token_id": 151643,
  "hidden_act": "silu",
  "hidden_size": 5120,
  "initializer_range": 0.02,
  "intermediate_size": 27648,
  "max_position_embeddings": 131072,
  "max_window_layers": 64,
  "model_type": "qwen2",
  "num_attention_heads": 40,
  "num_hidden_layers": 64,
  "num_key_value_heads": 8,
  "rms_norm_eps": 1e-05,
  "rope_theta": 1000000.0,
  "sliding_window": 131072,
  "torch_dtype": "bfloat16",
  "transformers_version": "4.43.1",
  "vocab_size": 152064
}
```

Мы видим, что у модели 64 слоя, в каждом слое 40 attention heads, у каждого attention head 8 key-value heads, hidden size каждого head равен 5120, intermediate size равен 27648, vocab size равен 152064.

Можно вычислить количество параметров этой модели:

```python
def calculate_total_parameters(config):
    # 计算嵌入层参数量
    embedding_params = config['vocab_size'] * config['hidden_size']
    # 计算每层的参数量
    # 前馈网络（FFN）部分
    ffn_params = 3 * (config['hidden_size'] * config['intermediate_size'])  # 三个线性层
    # 多头注意力机制部分 Q, K, V
    attention_params = 2 * config['hidden_size'] * config['hidden_size']*config['num_key_value_heads']/config['num_attention_heads'] + config['hidden_size'] * config['hidden_size']
    # 输出投影部分O
    output_projection_params = config['hidden_size'] * config['hidden_size']  # 输出投影
    # 每层的总参数量
    layer_params = ffn_params + attention_params + output_projection_params
    # 总参数量
    total_params = embedding_params + layer_params * config['num_hidden_layers']
    return total_params/ 1e9


 # 总参数量
total_params = calculate_total_parameters(config)
print(f"总参数量: {total_params:.2f} B")

```

Получаем общее количество параметров этой модели: 31.98 B.

Далее можно вычислить Prefilling_FLOPs и Decoding_FLOPs этой модели.

```python
config = {
  "attention_dropout": 0.0,
  "bos_token_id": 151643,
  "eos_token_id": 151643,
  "hidden_act": "silu",
  "hidden_size": 5120,
  "initializer_range": 0.02,
  "intermediate_size": 27648,
  "max_position_embeddings": 131072,
  "max_window_layers": 64,
  "model_type": "qwen2",
  "num_attention_heads": 40,
  "num_hidden_layers": 64,
  "num_key_value_heads": 8,
  "rms_norm_eps": 1e-05,
  "rope_theta": 1000000.0,
  "sliding_window": 131072,
  "torch_dtype": "bfloat16",
  "transformers_version": "4.43.1",
  "vocab_size": 152064,
  "prompt_token_length": 1024,
  "output_token_length": 1024,
  "batch_size": 1,
}

def calculate_prefilling_FLOPs(config):
    ## Q投影计算量
    query_projection_flops = 2*config['prompt_token_length'] * config['hidden_size']**2
    ## K,v投影计算量
    key_projection_flops = 2* config['prompt_token_length'] * config['hidden_size']**2 * config['num_key_value_heads']/config['num_attention_heads']
    value_projection_flops = 2* config['prompt_token_length'] * config['hidden_size']**2 * config['num_key_value_heads']/config['num_attention_heads']
    ## attention计算量
    # kv 在GQA的状态下，kv的存储量变小，但是计算量不变，因为K和V会有广播
    Q_K_flops = 2* config['prompt_token_length']**2 * config['hidden_size']
    A_V_flops = 2* config['prompt_token_length']**2 * config['hidden_size']
    ## 输出投影计算量
    output_projection_flops = 2*config['prompt_token_length'] * config['hidden_size']**2

    ## 前馈网络计算量
    ## swiGLu 有三次线性变换
    ffn_flops = 3* 2* config['prompt_token_length'] * config['hidden_size'] * config['intermediate_size']

    layer_flops = query_projection_flops + key_projection_flops + value_projection_flops + Q_K_flops + A_V_flops + output_projection_flops + ffn_flops

    total_flops = layer_flops * config['num_hidden_layers']*config['batch_size']
    return total_flops/ 1e12


calculate_prefilling_FLOPs(config)


def calculate_prefilling_FLOPs_quick(config):
    total_flops = (4*(1+config['num_key_value_heads']/config['num_attention_heads'])*config['prompt_token_length']*config['hidden_size']**2
                   + 4*config['prompt_token_length']**2*config['hidden_size']
                   + 6*config['prompt_token_length'] *
                   config['hidden_size']*config['intermediate_size'])*config['num_hidden_layers']*config['batch_size']
    return total_flops/ 1e12


calculate_prefilling_FLOPs_quick(config)


total_prefilling_flops = calculate_prefilling_FLOPs(config)
print(f"Prefilling阶段总计算量: {total_prefilling_flops:.2f} TFLOPs")

```

Общий объем вычислений на этапе Prefilling: 65.28 TFLOPs.

Объем вычислений на этапе Decoding:

```python
def calculate_decoding_FLOPs_per_token(config):
        ## Q投影计算量
    query_projection_flops = 2* config['hidden_size']**2
    ## K,v投影计算量，每次计算一个token的kv
    key_projection_flops = 2* config['hidden_size']**2 * config['num_key_value_heads']/config['num_attention_heads']
    value_projection_flops = 2* config['hidden_size']**2 * config['num_key_value_heads']/config['num_attention_heads']
    ## attention计算量
    # kv cache的状态下，KV的大小的随着step的增加而增加，从初始的prompt_token_length 到最终的prompt_token_length+output_token_length
    Q_K_flops = 2* (config['prompt_token_length']+(1+config['output_token_length'])/2) * config['hidden_size']
    A_V_flops = 2* (config['prompt_token_length']+(1+config['output_token_length'])/2) * config['hidden_size']
    ## 输出投影计算量
    output_projection_flops = 2* config['hidden_size']**2

    ## 前馈网络计算量
    ## swiGLu 有三次线性变换
    ffn_flops = 3* 2* config['hidden_size'] * config['intermediate_size']

    layer_flops = query_projection_flops + key_projection_flops + value_projection_flops + Q_K_flops + A_V_flops + output_projection_flops + ffn_flops

    total_flops = layer_flops * config['num_hidden_layers']*config['batch_size']
    return total_flops/ 1e12

decoding_FLOPs_per_token = calculate_decoding_FLOPs_per_token(config)
print(f"平均每个token的计算量: {decoding_FLOPs_per_token:.2f} TFLOPs")
```

Средний объем вычислений на каждый token: 0.06 TFLOPs.

## 4. Теоретическая производительность и утилизация GPU

### Prefilling

TTFT = Prefilling_FLOPs / GPU_FLOPS

Расчетный общий объем вычислений на этапе Prefilling: 65.28 TFLOPs.

Теоретический TTFT = 65.28TFLOPs/148TFLOPS = 441ms.

Но утилизацию GPU обычно не удается довести примерно до 60%, поэтому задержка будет выше.

### Decoding

Расчетный объем вычислений для генерации каждого batch равен 0.06TFLOPs.

Теоретический throughput = 148TFLOPS/0.06TFLOPs = 2466token/s.

Но из-за утилизации GPU реальный TPS, который мы можем оценить, будет ниже.

### Быстрый способ оценки

Prefilling_FLOPs = 2 * Batch_size * Prompt_size * Parameters= 2 * 1 * 1024 * 32B = 64TFLOPs
Оценка TTFT = 64TFLOPs/148TFLOPs=432ms

Decoding_FLOPs_Per_Step = 2 * Batch_size * Parameters = 2 * 1 * 32B = 0.064TFLOPs

Быстрая оценка теоретического Throughput =  148TFLOPS/0.064TFLOPs = 2312token/s

## Ссылки

[1] [Qwen/Qwen2.5-32B](https://huggingface.co/Qwen/Qwen2.5-32B/blob/main/config.json)

[2] [inference_speed_ipynb](../../../02-第二章-部署与推理/inference_speed.ipynb)


---

## 📚 相关概念

[[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]] | [[sources/推理引擎/推测解码|推测解码]] | [[sources/推理引擎/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[sources/推理引擎/vllm|vllm]] | [[sources/推理引擎/tensorrt-llm|tensorrt-llm]] | [[sources/推理引擎/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
