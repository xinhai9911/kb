---
aliases: ["fine-tuning-frameworks-2-huggingface-peft"]
---

## 1. Parameter-Efficient Fine-Tuning

Parameter-Efficient Fine-Tuning (PEFT) — это техника тонкой настройки больших предобученных моделей, например языковых моделей. Ее ключевая цель — адаптировать модель к конкретным downstream-задачам без заметного увеличения числа параметров модели. Такой подход особенно полезен в ресурсно ограниченных средах или в случаях, когда full fine-tuning всей модели невозможен из-за слишком высокой вычислительной стоимости.

Основные методы PEFT см. по ссылкам на Adapters и Soft prompts.

![alt text](../../../03-第三章-微调/assest/大模型微调框架（二）Huggingface-PEFT/0.png)

## 2. Библиотека PEFT

PEFT (параметрически эффективная тонкая настройка) — это библиотека для эффективной адаптации больших предобученных моделей к разным downstream-приложениям без тонкой настройки всех параметров модели, поскольку это слишком дорого. Методы PEFT тонко настраивают лишь небольшое число (дополнительных) параметров модели, при этом достигая качества, сопоставимого с полной тонкой настройкой. Благодаря этому обучать и хранить большие языковые модели (LLM) на потребительском оборудовании становится проще.

![alt text](../../../03-第三章-微调/assest/大模型微调框架（二）Huggingface-PEFT/1.png)

PEFT интегрируется с библиотеками Transformers, Diffusers и Accelerate, предоставляя более быстрый и простой способ загружать, обучать и использовать большие модели для инференса.

Использование библиотеки PEFT можно свести к следующим шагам:

### 1. Установка библиотеки PEFT

Библиотеку PEFT можно установить через PyPI следующей командой:
```bash
pip install peft
```
Либо, если нужно установить из исходного кода, чтобы получить самые свежие функции, можно использовать команду:
```bash
pip install git+https://github.com/huggingface/peft
```
Пользователи, которые хотят вносить вклад в код или смотреть актуальные результаты, могут клонировать репозиторий с GitHub и установить editable-версию:
```bash
git clone https://github.com/huggingface/peft
cd peft
pip install -e .
```


### 2. Настройка метода PEFT
Каждый метод PEFT определяется классом `PeftConfig`, который хранит все важные параметры для создания `PeftModel`. На примере LoRA нужно указать тип задачи, режим инференса, размерность низкоранговых матриц и другие параметры:
```python
from peft import LoraConfig, TaskType
peft_config = LoraConfig(task_type=TaskType.SEQ_2_SEQ_LM, inference_mode=False, r=8, lora_alpha=32, lora_dropout=0.1)
```


### 3. Загрузка предобученной модели и применение PEFT
Загрузите базовую модель для тонкой настройки и используйте функцию `get_peft_model()`, чтобы обернуть базовую модель вместе с `peft_config` и создать `PeftModel`:
```python
from transformers import AutoModelForSeq2SeqLM
from peft import get_peft_model
model = AutoModelForSeq2SeqLM.from_pretrained("bigscience/mt0-large")
model = get_peft_model(model, peft_config)
```


### 4. Обучение модели
Теперь модель можно обучать с помощью `Trainer` из Transformers, Accelerate или любого пользовательского training loop на PyTorch. Например, обучение через класс `Trainer`:
```python
from transformers import TrainingArguments, Trainer
training_args = TrainingArguments(
    output_dir="your-name/bigscience/mt0-large-lora",
    learning_rate=1e-3,
    per_device_train_batch_size=32,
    num_train_epochs=2,
    weight_decay=0.01,
)
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["test"],
    tokenizer=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
)
trainer.train()
```


### 5. Сохранение и загрузка модели
После завершения обучения модель можно сохранить в каталог с помощью функции `save_pretrained` или отправить на Hugging Face Hub с помощью функции `push_to_hub`:
```python
model.save_pretrained("output_dir")
from huggingface_hub import notebook_login
notebook_login()
model.push_to_hub("your-name/bigscience/mt0-large-lora")
```


### 6. Инференс
Используйте класс `AutoPeftModel` и метод `from_pretrained`, чтобы легко загрузить любую inference-модель, обученную с помощью PEFT:
```python
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer
model = AutoPeftModelForCausalLM.from_pretrained("ybelkada/opt-350m-lora")
tokenizer = AutoTokenizer.from_pretrained("facebook/opt-350m")
inputs = tokenizer("Preheat the oven to 350 degrees and place the cookie dough", return_tensors="pt")
outputs = model.generate(input_ids=inputs["input_ids"], max_new_tokens=50)
print(tokenizer.batch_decode(outputs.detach().cpu().numpy(), skip_special_tokens=True)[0])
```

## Ссылки

<div id="refer-anchor-1"></div>

[1] [peft](https://huggingface.co/docs/peft/index)

## Подписывайтесь на мой GitHub и WeChat-канал [真-忒修斯之船]: объяснять некогда, быстро на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы, все полностью open source. Буду рад Star и Fork!


---

## 📚 相关概念

[[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：微调
