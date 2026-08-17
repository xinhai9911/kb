В чем разница между latency (задержкой) и throughput (пропускной способностью) в больших моделях?
## 1. Введение
Чтобы быстро применять большие модели, нам нужно закупать коммерческие большие модели. Перед закупкой, при общении с отделом продаж, мы описали наш сценарий и требования:

Q: Количество prompts token у нас находится в диапазоне 1500-2000, completion token — около 500. Сколько в такой ситуации занимает prefilling? Сколько времени занимает вывод каждого token?

Ответ продавца: стандартный 3500 token Input, первый пакет выходит меньше чем за 1 секунду; throughput 300token/s.

Вы заметили, что ответ не на тот вопрос?

Вопрос был связан с latency, а ответ — про throughput. Так в чем разница между этими двумя словами, если даже продавцы в этой области могут их путать?

![alt text](../../../02-第二章-部署与推理/assest/大模型的latency（延迟）和throughput（吞吐量）有什么区别/11.png)

Прежде чем разобраться с latency и throughput, посмотрим на KV cache и prefilling.

## 2. KV Cache
KV Cache использует идею обмена пространства на время: повторно использует KV cache из предыдущего инференса, что может существенно снизить давление на память, повысить производительность инференса и при этом не влияет на точность вычислений.

В decoder-архитектуре главное — это стек структур self-attention в transformer. Суть KV-cache в том, что ранее вычисленные key-value и текущий query используются для генерации следующего token.

prefill означает, что при генерации первого token у kv еще нет никакого кэша: нужно заранее заполнить и закэшировать KV-матрицу, соответствующую prompt. Поэтому первый token генерируется медленнее всего, а начиная со второго token модель быстро обращается к кэшу и также кэширует kv предыдущего token.

Видно, что это схема обмена пространства на время: кэш постоянно растет. Поэтому при приватном развертывании и расчете видеопамяти, кроме размера модели, нужно учитывать размеры prompt и completion в вашем приложении (и, конечно, batch-size).


## 3. Prefilling & Decoding

Если вы используете коммерческую большую модель или локально развертываете open source большую модель, то кроме качества генерации еще один ключевой показатель — скорость генерации token. Причем это не просто количество token в секунду, а два отдельных этапа:
- prefill: предзаполнение, параллельная обработка входных tokens;
- decoding: декодирование, генерация следующего token по одному.

### Предзаполнение (prefill)
На этапе предзаполнения модель параллельно обрабатывает входной prompt (то есть input token) и создает KV cache. Этот шаг включает один полный forward pass (forward) и выводит первый token. Время этого процесса в основном определяется input token, поскольку для инициализации всего процесса генерации нужно выполнить полный расчет.

### Декодирование (decoding)
Этап декодирования — это процесс генерации следующего token по одному. На этом шаге количество output token определяет, сколько раз нужно выполнить forward pass. Хотя каждый forward pass благодаря KV cache выполняется быстрее, модели все равно приходится многократно считать, постепенно генерируя каждый последующий token.

### Разные компании используют разные термины:
- Задержка первого token, Time To First Token (TTFT), prefill, Prefilling

   Все они означают задержку от ввода до вывода первого token;

- Задержка каждого output token (без первого Token), Time Per Output Token (TPOT)

  Означает скорость выдачи начиная со второго token;

- Latency

  Теоретически это время от ввода до вывода последнего token. Принципиальная формула расчета: Latency = (TTFT) + (TPOT) * (the number of tokens to be generated);

- Tokens Per Second (TPS):

  (the number of tokens to be generated) / Latency;

## 4. Latency VS Throughput
- Latency: задержка, время от ввода до вывода, то есть время от ввода до вывода последнего token;

![alt text](../../../02-第二章-部署与推理/assest/大模型的latency（延迟）和throughput（吞吐量）有什么区别/1.png)

- Throughput: пропускная способность, количество задач, обработанных за единицу времени, то есть количество token, обработанных за секунду.

![alt text](../../../02-第二章-部署与推理/assest/大模型的latency（延迟）和throughput（吞吐量）有什么区别/2.png)

Ниже приведен способ расчета latency и throughput:

```python
# constants
max_tokens = 10

# observations
durations = []
throughputs = []
latencies = []

batch_sizes = [2**p for p in range(8)]
for batch_size in batch_sizes:
    print(f"bs= {batch_size}")

    # generate tokens for batch and record duration
    t0 = time.time()
    batch_prompts = [
        prompts[i % len(prompts)] for i in range(batch_size)
    ]
    inputs = tokenizer(
        batch_prompts, padding=True, return_tensors="pt"
    )
    generated_tokens = generate_batch(inputs, max_tokens=max_tokens)
    duration_s = time.time() - t0

    ntokens = batch_size * max_tokens
    throughput = ntokens / duration_s
    avg_latency = duration_s / max_tokens
    print("duration", duration_s)
    print("throughput", throughput)
    print("avg latency", avg_latency)
    print()

    durations.append(duration_s)
    throughputs.append(throughput)
    latencies.append(avg_latency)
```

## 5. Navie batching

Navie batching означает объединение нескольких входов в один batch и однократную подачу в модель. Это уменьшает число forward pass модели и повышает эффективность.
Некоторые также называют это synchronous batching или static batching, в отличие от continuous batching, который будет описан ниже.

![alt text](../../../02-第二章-部署与推理/assest/大模型的latency（延迟）和throughput（吞吐量）有什么区别/9.png)

Недостаток Navie batching в том, что если в одном batch есть очень большой вход, то время расчета всего batch растягивается, и из-за этого время вычисления всего batch становится больше.

## 6. Continuous batching

В традиционном batching-подходе вся группа запросов должна полностью завершить обработку, прежде чем результаты будут возвращены вместе. Это означает, что короткие запросы вынуждены ждать завершения длинных запросов, что приводит к пустой трате ресурсов GPU и росту задержки инференса. Технология Continuous Batching позволяет после обработки текущей итерации сразу вернуть результат запроса, если он уже завершен, не дожидаясь завершения всего batch. Это заметно повышает использование аппаратных ресурсов и сокращает время простоя.

![alt text](../../../02-第二章-部署与推理/assest/大模型的latency（延迟）和throughput（吞吐量）有什么区别/10.png)

Кроме того, Continuous Batching решает проблему потерь ресурсов из-за разного объема вычислений у разных запросов: за счет планирования на уровне итераций он динамически регулирует размер batch, адаптируется к сложности разных запросов и эффективно снижает время ожидания для запросов высокой сложности.

Важно отметить, что при реализации Continuous Batching нужно учитывать несколько ключевых вопросов: обработку Early-finished Requests и Late-joining Requests, а также batching запросов разной длины. Две идеи дизайна, предложенные OCRA, — Iteration-level Batching и Selective Batching — как раз предназначены для решения этих проблем.

В практическом применении разные фреймворки могут реализовывать Continuous Batching по-разному. Например, фреймворк vLLM использует упрощенную реализацию, разделяя prefill и decoding, а фреймворк FastGen использует метод SplitFuse: разбивает длинный prompt на маленькие блоки и планирует их на нескольких step. Все эти разные реализации направлены на повышение производительности инференса, снижение задержки и оптимизацию использования ресурсов.


Код для генерации continous batching:

```python
# seed the random number generator so our results are deterministic
random.seed(42)

# constants
queue_size = 32
batch_size = 8

# requests waiting to be processed
# this time requests are tuples (prompt, max_tokens)
request_queue = [
    (prompts[0], 100 if i % batch_size == 0 else 10)
    for i in range(queue_size)
]

t0 = time.time()
with tqdm(total=len(request_queue), desc=f"bs={batch_size}") as pbar:
    # first, let's seed the initial cached_batch
    # with the first `batch_size` inputs
    # and run the initial prefill step
    batch = init_batch(request_queue[:batch_size])
    cached_batch = generate_next_token(batch)
    request_queue = request_queue[batch_size:]

    # continue until both the request queue is
    # fully drained and every input
    # within the cached_batch has completed generation
    while (
        len(request_queue) > 0 or
        cached_batch["input_ids"].size(0) > 0
    ):
        batch_capacity = (
            batch_size - cached_batch["input_ids"].size(0)
        )
        if batch_capacity > 0 and len(request_queue) > 0:
            # prefill
            new_batch = init_batch(request_queue[:batch_capacity])
            new_batch = generate_next_token(new_batch)
            request_queue = request_queue[batch_capacity:]

            # merge
            cached_batch = merge_batches(cached_batch, new_batch)

        # decode
        cached_batch = generate_next_token(cached_batch)

        # remove any inputs that have finished generation
        cached_batch, removed_indices = filter_batch(cached_batch)
        pbar.update(len(removed_indices))

duration_s = time.time() - t0
print("duration", duration_s)
```

## Ссылки

[1] [deeplearning.ai](https://learn.deeplearning.ai/courses/efficiently-serving-llms/lesson/3/batching)

[2] [Continuous Batching: инструмент для повышения throughput при развертывании LLM](https://www.high-flyer.cn/en/blog/continuous-batching/)

[3] [Оптимизация инференса LLM: Continuous Batching и его реализация](https://yangwenbo.com/articles/llm-continuous-batching.html)

[4] [How continuous batching enables 23x throughput in LLM inference while reducing p50 latency](https://www.anyscale.com/blog/continuous-batching-llm-inference)

[5] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)
