# Фреймворки обучения LLM, часть 2: FSDP

Fully Sharded Data Parallel (FSDP)[1](#refer-anchor-1) - это метод data parallelism, впервые предложенный FairScale-FSDP в 2021 году и позднее интегрированный в PyTorch 1.11.

FSDP можно рассматривать как реализацию `ZERO-3` из трех уровней алгоритма ZERO, предложенных во фреймворке Microsoft DeepSpeed. За счет sharding градиентов модели, optimizer states и параметров каждый GPU хранит только часть информации о параметрах, что оптимизирует использование ресурсов и повышает эффективность обучения. Кроме того, FSDP тесно совместно спроектирован с несколькими ключевыми core-компонентами PyTorch, включая Tensor implementation, scheduler system и CUDA memory caching allocator, чтобы обеспечить неинвазивный пользовательский опыт и высокую эффективность обучения.

## 1. DP & DDP & ZeRO

***DP (Data Parallel)***: data parallelism в узком смысле, DP, - самая простая стратегия параллелизации. Она распределяет копии модели по нескольким GPU на одной машине: на каждом GPU находится своя копия модели, и каждый GPU обрабатывает разные подмножества данных. В конце каждого training step все GPU синхронизируют параметры модели.

***DDP (Distributed Data Parallel)***: когда объем данных растет, эффективность обучения на нескольких GPU в рамках одной машины становится низкой. В этот момент нужен distributed data parallelism, DDP. DDP распределяет копии модели по нескольким машинам: на каждой машине есть несколько GPU, и на каждом GPU находится копия модели. В конце каждого training step все GPU синхронизируют параметры модели.

***ZeRO***, полное название "Zero Redundancy Optimizer", - технология управления памятью для оптимизации распределенного обучения, предложенная Microsoft Research. Она предназначена для решения memory bottleneck, возникающего в крупномасштабном распределенном обучении, особенно при обучении больших deep learning моделей. ZeRO оптимизирует использование памяти за счет сокращения redundant data, благодаря чему становится возможным обучать более крупные модели на ограниченных аппаратных ресурсах.

![alt text](../../../01-第一章-预训练/assest/大模型训练框架（二）FSDP/0.png)

## 2. Объяснение

Рассмотрим простую модель из 3 слоев, где в каждом слое есть 3 параметра:

La | Lb | Lc
---|----|---
a0 | b0 | c0
a1 | b1 | c1
a2 | b2 | c2

Слой La имеет веса a0, a1 и a2.

Если у нас есть 3 GPU, sharded DDP (= Zero-DP) разделит модель между 3 GPU следующим образом:

GPU0:
La | Lb | Lc
---|----|---
a0 | b0 | c0

GPU1:
La | Lb | Lc
---|----|---
a1 | b1 | c1

GPU2:
La | Lb | Lc
---|----|---
a2 | b2 | c2

Теперь каждый GPU получает обычный mini-batch, с которым он работал бы в DP:

```Plain Text
x0 => GPU0
x1 => GPU1
x2 => GPU2
```

Входы не изменяются: они "считают", что будут обрабатываться обычной моделью.

Сначала входы попадают в слой La.

Сосредоточимся только на GPU0: x0 нужны параметры a0, a1 и a2, чтобы выполнить свой forward path, но на GPU0 есть только a0. Поэтому он получает a1 с GPU1 и a2 с GPU2, собирая все части модели вместе.

Одновременно GPU1 получает mini-batch x1. У него есть только a1, но нужны параметры a0 и a2, поэтому он получает их с GPU0 и GPU2.

То же самое происходит с GPU2, который получает вход x2. Он получает a0 и a1 с GPU0 и GPU1 и с помощью своего a2 восстанавливает полный tensor.

Все 3 GPU восстанавливают полный tensor и выполняют forward propagation.

Как только вычисление завершено, данные, которые больше не нужны, отбрасываются: они используются только во время вычисления. Восстановление эффективно выполняется через pre-fetch.

Весь процесс сначала повторяется для слоя Lb, затем вперед для Lc, затем назад для Lc, а потом в обратном направлении Lc -> Lb -> La.

## 3. Более наглядное объяснение

Компания организует трехдневный выезд с кемпингом, и каждый несет часть вещей:

```Plain Text
A несет палатку
B несет перекус
C несет воду
```

Теперь каждый вечер они делятся с другими тем, что у них есть, и получают от других то, чего у них нет. Утром они снова собирают распределенное между ними снаряжение и продолжают путь. Это и есть Sharded DDP/ZeRO DP.

Сравним эту стратегию с простой: в простой стратегии каждому пришлось бы нести собственную палатку, собственный перекус и собственную воду, что намного менее эффективно.

## 4. FSDP

У ZeRO есть три уровня алгоритма: `ZERO-1`, `ZERO-2` и `ZERO-3`. `ZERO-3` - самый высокий уровень алгоритма: он выполняет sharding градиентов модели, optimizer states и параметров, поэтому каждый GPU хранит только часть информации о параметрах. Это оптимизирует использование ресурсов и повышает эффективность обучения. FSDP - реализация ZeRO-3.

## 5. FSDP PyTorch

![alt text](../../../01-第一章-预训练/assest/大模型训练框架（二）FSDP/1.png)

Использование FSDP в PyTorch позволяет эффективно обучать крупные модели, особенно когда GPU memory или memory ограничены. FSDP - технология data parallelism, которая делит параметры модели, градиенты и optimizer states между несколькими устройствами. Ниже основные шаги:

1. **Инициализация распределенного окружения**:
   Сначала нужно инициализировать распределенное окружение для коммуникации между процессами. Обычно это делается через функцию `torch.distributed.init_process_group`.

2. **Настройка local rank**:
   Каждому процессу нужно на основе своего `local_rank` задать GPU, который он должен использовать. Это можно получить через environment variables или command line arguments.

3. **Создание FSDP-модели**:
   Используйте класс `FullyShardedDataParallel`, чтобы обернуть вашу модель. Это позволит выполнять sharding параметров модели по нескольким GPU. Например:
   ```python
   from torch.distributed.fsdp import FullyShardedDataParallel

   model = MyModel()
   model = model.to(device)  # 将模型移动到GPU
   fsdp_model = FullyShardedDataParallel(model, ...其他参数...)
   ```

4. **Настройка параметров FSDP**:
   FSDP предоставляет множество параметров для настройки поведения, например `cpu_offload`, который определяет, выгружать ли параметры на CPU, и `sharding_strategy`, который задает стратегию sharding.

5. **Обучение модели**:
   В training loop FSDP автоматически обрабатывает sharding параметров и aggregation градиентов. Вам нужно только выполнять forward и backward propagation как обычно.

6. **Сохранение и загрузка модели**:
   При использовании FSDP сохранение и загрузка модели могут требовать специальной обработки, чтобы sharded-параметры обрабатывались корректно.

Ниже более подробный пример кода, показывающий, как использовать FSDP для обучения простой модели:

```python
import torch
import torch.nn as nn
from torch.distributed.fsdp import FullyShardedDataParallel, CPUOffload

class MyModel(nn.Module):
    def __init__(self):
        super(MyModel, self).__init__()
        self.layer1 = nn.Linear(8, 4)
        self.layer2 = nn.Linear(4, 16)
        self.layer3 = nn.Linear(16, 4)

    def forward(self, x):
        x = torch.relu(self.layer1(x))
        x = torch.relu(self.layer2(x))
        x = self.layer3(x)
        return x

# 初始化分布式环境
torch.distributed.init_process_group(backend='nccl')

# 设置本地排名和设备
local_rank = torch.distributed.get_rank()
world_size = torch.distributed.get_world_size()
torch.cuda.set_device(local_rank)

# 创建模型并移动到对应的GPU
model = MyModel().to(local_rank)

# 使用FSDP包装模型
fsdp_model = FullyShardedDataParallel(
    model,
    cpu_offload=CPUOffload(offload_params=True),
    # 其他FSDP参数
)

# 定义损失函数和优化器
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(fsdp_model.parameters(), lr=0.001)

# 训练循环
for epoch in range(num_epochs):
    for data, target in dataloader:
        data, target = data.to(local_rank), target.to(local_rank)
        optimizer.zero_grad()
        output = fsdp_model(data)
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()
```

## 6. FSDP Hugging Face/Accelerate

Как продвинутая deep learning библиотека, Hugging Face предоставляет библиотеку Accelerate, которая помогает пользователям проще использовать технологии распределенного обучения, включая FSDP. Accelerate предоставляет простой API, позволяющий за несколько строк кода преобразовать модель в FSDP-модель и автоматически обработать детали распределенного обучения.

```shell
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: FSDP # 使用FSDP的配置
downcast_bf16: 'no'
fsdp_config:
  fsdp_auto_wrap_policy: TRANSFORMER_BASED_WRAP
  fsdp_backward_prefetch_policy: BACKWARD_PRE
  fsdp_forward_prefetch: false
  fsdp_cpu_ram_efficient_loading: true
  fsdp_offload_params: false
  fsdp_sharding_strategy: FULL_SHARD
  fsdp_state_dict_type: SHARDED_STATE_DICT
  fsdp_sync_module_states: true
  fsdp_transformer_layer_cls_to_wrap: BertLayer
  fsdp_use_orig_params: true
machine_rank: 0
main_training_function: main
mixed_precision: bf16
num_machines: 1
num_processes: 2
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
```

`tips`: 13 сентября 2024 года, почти через год после того, как разработка Accelerate стала стабильной, был официально выпущен Accelerate 1.0.0 - первый release candidate Accelerate.

![alt text](../../../01-第一章-预训练/assest/大模型训练框架（二）FSDP/2.png)

Ниже показана поддержка стратегий параллелизации разными фреймворками по состоянию на 2024/10/12:

| Фреймворк | DP | PP | TP | 3D parallelism |
| :--- |:----:| :----: |:---: |:---: |
| PyTorch(FSDP) | да | нет | нет | нет |
| DeepSpeed | да | да | да | да |
| Megatron-LM | да | да | да | да |
| Accelerate | да | нет | нет | нет |

## Ссылки

<div id="refer-anchor-1"></div>

[1] [Getting Started with Fully Sharded Data Parallel(FSDP)](https://pytorch.org/tutorials/intermediate/FSDP_tutorial.html)

<div id="refer-anchor-2"></div>

[2] [Accelerate](https://huggingface.co/docs/accelerate/index)

## GitHub и WeChat автора

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы, он полностью open source. Добро пожаловать, ставьте Star и делайте Fork!


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
