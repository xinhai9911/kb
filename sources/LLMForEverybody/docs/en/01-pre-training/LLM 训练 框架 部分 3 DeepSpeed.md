---
aliases: ["llm-training-frameworks-part-3-deepspeed"]
---

# LLM Training Frameworks, Part 3: DeepSpeed

DeepSpeed[1](#refer-anchor-1) is a deep learning optimization library developed by Microsoft Research. It is designed for efficient and scalable training of large models. DeepSpeed significantly improves training efficiency and reduces resource requirements through advanced parallelism strategies, memory optimization methods such as the ZeRO memory optimizer, and mixed precision training.

## 1. ZeRO

ZeRO (Zero Redundancy Optimizer) is one of DeepSpeed's key technologies. It is an optimizer designed to solve the memory bottleneck in large-scale distributed training. ZeRO greatly reduces required memory by optimizing storage and communication of model states, allowing larger models to be trained with limited resources. DeepSpeed is Microsoft's open-source deep learning optimization library, aimed at improving the efficiency and scalability of large model training, and ZeRO is one of its core components: it optimizes memory use and enables larger model training.

![alt text](../../../01-第一章-预训练/assest/大模型训练框架（三）DeepSpeed/0.png)

ZeRO has three optimization levels: ZeRO-1, ZeRO-2, and ZeRO-3. Each next level further reduces memory consumption compared with the previous one.

1. **ZeRO-1**: optimizer states, such as Adam optimizer weights and gradients, are distributed across several GPUs instead of being fully stored on every GPU. This saves part of GPU memory, but model parameters and activations still need to be fully stored on each GPU.

2. **ZeRO-2**: gradient sharding is added on top of ZeRO-1. Besides optimizer states, gradients are also distributed across several GPUs. This further reduces memory use on each GPU and improves compute efficiency.

3. **ZeRO-3**: all model states are fully sharded, including model parameters. This means model parameters, optimizer states, and gradients are distributed across several GPUs. This approach allows larger models to be trained with the same amount of GPU memory, but it may increase communication overhead.

There is also ZeRO-Infinity, an extension of ZeRO-3 that can use CPU and NVMe memory to further extend GPU memory and support even larger model training.

FSDP can be understood as an implementation of ZeRO-3: it shards model gradients, optimizer states, and parameters, so each GPU stores only part of the parameter information. This optimizes resource use and improves training efficiency.

## 2. DeepSpeed Parallelism Strategies

DeepSpeed supports several parallelism strategies, including data parallelism and model parallelism, including pipeline and tensor parallelism. These methods can be flexibly combined to fit deep learning models of different scales and complexity.

**Data Parallelism** distributes model copies across several GPUs: each GPU processes its own subset of data, and model parameters are synchronized at the end of each training step. This method is suitable when the model is large enough that it cannot fully fit in one GPU's memory. Data parallelism mainly uses the ZeRO strategy described above.

**Pipeline Parallelism** splits model layers into several stages that can be processed in parallel on different processors. This method improves memory and compute efficiency and is especially useful for training deep neural networks.

![alt text](../../../01-第一章-预训练/assest/大模型训练框架（三）DeepSpeed/2.png)

Training data in each batch is split into smaller micro-batches, which can be processed in parallel on different pipeline stages. Once one stage finishes the forward pass for a micro-batch, activation memory is passed to the next pipeline stage. Similarly, when the next stage finishes the backward pass for a micro-batch, gradients with respect to activations are passed backward through the pipeline. Each backward pass accumulates gradients locally, after which all data parallel groups reduce gradients in parallel. At the end, the optimizer updates model weights.

**Tensor Parallelism** splits model parameter tensors across several GPUs. This preserves the overall model structure and speeds up training through distributed computation. Tensor parallelism is usually used when the number of model parameters is so large that one GPU cannot fit the whole model.

![alt text](../../../01-第一章-预训练/assest/大模型训练框架（三）DeepSpeed/4.png)

The main difference between pipeline and tensor parallelism in DeepSpeed is how they split the model. Pipeline parallelism splits by layers, while tensor parallelism splits parameter tensors. These two types of parallelism can be used together to form a hybrid parallelism strategy and further improve training efficiency and scalability. For example, tensor parallelism can be used inside each pipeline stage to split parameters within a layer and achieve finer-grained parallelism.

## 3. DeepSpeed Implementation in PyTorch

Using DeepSpeed to train deep learning models in PyTorch mainly involves these steps:

1. **Install DeepSpeed**:
   - Install DeepSpeed with `pip`: `pip install deepspeed`.

2. **Prepare a configuration file**:
   - Create `deepspeed_config.json`, defining training parameters and model settings. For example:
     ```json
     {
       "train_batch_size": 4,
       "optimizer": {
         "type": "SGD",
         "params": {
           "lr": 0.001,
           "momentum": 0.9
         }
       },
       "fp16": {
         "enabled": true
       },
       "zero_optimization": {
         "stage": 2
       }
     }
     ```

3. **Write the training script**:
   - Import DeepSpeed: `import deepspeed`.
   - Define the model, dataloader, and optimizer.
   - Use `deepspeed.initialize()` to initialize the DeepSpeed engine, wrapping the model and optimizer:
     ```python
     model_engine, optimizer, _, _ = deepspeed.initialize(args=cmd_args,
                                                           model=model,
                                                           model_parameters=params)
     ```

4. **Train the model**:
   - Replace the original training loop with calls to `model_engine.backward(loss)` and `model_engine.step()` for backpropagation and parameter updates.
   - DeepSpeed automatically handles gradient accumulation, gradient compression, and other techniques for improving training efficiency.

5. **Save and load checkpoints**:
   - Use `model_engine.save_checkpoint()` and `model_engine.load_checkpoint()` to save and load model checkpoints.

6. **Start training**:
   - Use the DeepSpeed CLI tool to launch distributed training. For example:
     ```plaintext
     deepspeed --hostfile=myhostfile --no_ssh --node_rank=<n> \
     --master_addr=<addr> --master_port=<port> \
     <client_entry.py> <client args> \
     --deepspeed --deepspeed_config ds_config.json
     ```
   - In a single-node multi-process environment with several GPUs, use `--include` and `--exclude` to select GPUs.

7. **Monitor and tune**:
   - During training, use DeepSpeed tools for performance monitoring and tuning.

8. **Mixed precision training**:
   - Enable mixed precision in the configuration file, for example by setting `"fp16": {"enabled": true}`.

9. **ZeRO optimization**:
   - Set the ZeRO optimization strategy in the configuration file, for example `"zero_optimization": {"stage": 2}`.

10. **Offload optimization**:
    - If needed, enable ZeRO-Offload in the configuration file to offload part of computation and memory to CPU, for example `"zero_optimization": {"offload_optimizer": {"device": "cpu", "pin_memory": true}}`.

As of the completion of this article (2024/10/14), DeepSpeed support in PyTorch mainly focuses on ZeRO; PP and TP support is limited.

## 4. DeepSpeed Implementation in Accelerate

The Accelerate library provides a simple interface for integrating DeepSpeed, simplifying distributed training in PyTorch. Below are the basic steps for distributed training with DeepSpeed and Accelerate:

1. **Install DeepSpeed and Accelerate**:
   ```bash
   pip install deepspeed accelerate
   ```

2. **Create a DeepSpeed configuration file**:
   Create `deepspeed_config.json`, defining training parameters and model settings. For example:
   ```json
   {
     "train_batch_size": 4,
     "optimizer": {
       "type": "SGD",
       "params": {
         "lr": 0.001,
         "momentum": 0.9
       }
     },
     "fp16": {
       "enabled": true
     },
     "zero_optimization": {
       "stage": 2
     }
   }
   ```

3. **Write the training script**:
   Import the required libraries and define the model, dataloader, and optimizer. Use `Accelerator` and `DeepSpeedPlugin` from Accelerate to prepare the model, optimizer, and dataloader. For example:
   ```python
   import torch
   import torch.nn as nn
   from torch.utils.data import TensorDataset, DataLoader
   from accelerate import Accelerator, DeepSpeedPlugin

   class TestNet(nn.Module):
       def __init__(self, input_dim: int, output_dim: int):
           super(TestNet, self).__init__()
           self.fc1 = nn.Linear(in_features=input_dim, out_features=output_dim)
           self.fc2 = nn.Linear(in_features=output_dim, out_features=output_dim)

       def forward(self, x: torch.Tensor):
           x = torch.relu(self.fc1(x))
           x = self.fc2(x)
           return x
   ```

4. **Start training**:
   Use Accelerate's `launch` command to start distributed training. For example:
   ```bash
   accelerate launch --config_file default_config.yaml my_training_script.py
   ```
   Here `default_config.yaml` is the Accelerate configuration file, which can be generated with `accelerate config`.

5. **Monitor and tune**:
   During training, use DeepSpeed tools for performance monitoring and tuning.

6. **Save and load checkpoints**:
   Use Accelerate's `save` and `load` methods to save and load model checkpoints.

As of the completion of this article (2024/10/14), DeepSpeed support in Accelerate mainly focuses on ZeRO; Accelerate does not yet have PP and TP.

Below is the parallelization strategy support of different frameworks as of 2024/10/14:

| Framework | DP | PP | TP | 3D parallelism |
| :--- |:----:| :----: |:---: |:---: |
| PyTorch(FSDP) | yes | no | no | no |
| DeepSpeed | yes | yes | yes | yes |
| Megatron-LM | yes | yes | yes | yes |
| Accelerate | yes | no | no | no |

## References

<div id="refer-anchor-1"></div>

[1] [DeepSpeed](https://github.com/microsoft/DeepSpeed)

[2] [parallelism](https://huggingface.co/docs/transformers/v4.15.0/en/parallelism)

## Follow My GitHub and WeChat Account, No Time to Explain, Hop In.

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository contains the original Markdown files. It is fully open source, and Stars and Forks are welcome.


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
