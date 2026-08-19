---
aliases: ["llm-inference-frameworks-part-4-tensorrt-llm"]
---

Large-model inference frameworks, part 4: TensorRT-LLM

`TensorRT-LLM` [1](#refer-anchor-1) is an open source NVIDIA library for optimizing inference performance of large language models (`LLMs`) on NVIDIA GPUs. With advanced optimizations such as quantization, kernel fusion, dynamic batching, and multi-GPU support, it greatly improves LLM inference speed. Compared with traditional CPU-based approaches, inference speed can increase up to 8 times.

## 1. Fast Transformer or TensorRT-LLM?

Fast Transformer is no longer updated.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/0.png>)

TensorRT-LLM can be viewed as a combination of TensorRT and FastTransformer, built to accelerate large-model inference. It not only includes Transformer optimizations from FastTransformer, such as attention optimization, softmax optimization, operator fusion, and other methods, but also adds many features aimed at optimizing large-model inference.

`TensorRT` is an SDK (software development kit) developed by NVIDIA for high-performance deep learning inference on GPUs. It can optimize neural network models, accelerate inference, and greatly improve inference performance and efficiency on GPUs. Main TensorRT features:

1. **Model optimization**: TensorRT can import models trained in mainstream deep learning frameworks and generate optimized runtime engines that can be deployed in data centers, automotive, and embedded environments.

2. **High-performance inference optimization**: TensorRT greatly accelerates inference through layer fusion, precision calibration, kernel auto-tuning, and other techniques.

3. **Low latency**: TensorRT optimizes the computation graph and memory usage, greatly reducing inference latency and making it suitable for real-time AI applications.

4. **Support for multiple precision modes**: TensorRT supports FP32, FP16, INT8, and other precision modes, allowing a balance between accuracy and performance.

## 2. Inference Acceleration Techniques

1. Quantization

Quantization is a model optimization method in the LLM field, especially for deploying models in resource-constrained environments such as mobile devices, embedded systems, or servers where low latency is required. The basic idea of quantization is to convert model weights and activation values from floating point numbers, such as 32-bit floating point FP32, into lower-precision representations such as 8-bit integers (`INT8`) or even lower-bit formats.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/1.png>)

2. In-flight Batching

This is also called Continuous Batching. It is a technique for improving LLM inference efficiency. It continuously processes multiple input samples, reduces idle time during inference, improves compute efficiency, and raises throughput. In LLM inference, batching several input samples lets the system use GPU compute resources more efficiently, reduce waiting during inference, and improve overall inference speed.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/2.png>)

3. Attention

`KV Cache` uses the idea of trading memory for time: it reuses KV cache from the previous inference step, which can greatly reduce memory pressure and improve inference performance without affecting compute accuracy.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/3.png>)

In a decoder architecture, the core is a stack of transformer self-attention structures. The essence of KV cache is that the next token is generated using previously computed key-value pairs and the current query.

`prefill` means that when generating the first token, there is not yet any cache in `kv`: the KV matrix corresponding to the prompt must be filled first and cached. So the first token is the slowest to generate. Starting from the second token, the cache is fetched quickly, and the `kv` of the previous token is also added to the cache.

As you can see, this is a memory-for-time scheme: the cache keeps growing. So when calculating GPU memory for private deployment, you need to consider not only model size, but also the prompt and completion sizes in your application, and of course batch size.

But after memory usage increases, GPU memory becomes the problem again. So people began trying to share keys and values inside the attention mechanism to reduce KV cache content.

That is how `Multi-Query Attention(MQA)` appeared: there are still multiple queries, but only one set of keys and values, and all queries share one group. This makes KV Cache smaller.

But MQA has a drawback: accuracy loss. So researchers proposed a compromise: not all queries share one KV group, but queries inside one group share one KV group. This reduces KV cache while preserving accuracy. That is how `Group-Query Attention(GQA)` appeared.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（四）TensorRT-LLM/4.PNG>)

4. Graph Rewriting

Graph Rewriting is a neural network model optimization technique in TensorRT-LLM. Before deploying a deep learning model on hardware, a graph optimization process is usually performed, called graph rewriting. TensorRT-LLM uses a declarative approach to define neural networks: the model is built by describing its structure and operations, rather than through step-by-step programming.

With graph rewriting, TensorRT-LLM can generate an optimized execution graph for a specific hardware platform, providing efficient inference performance on NVIDIA GPUs. This optimization can greatly increase model runtime speed, reduce latency, and raise overall throughput, which is especially important when processing large language models.

## References

<div id="refer-anchor-1"></div>

[1] [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM/tree/release/0.5.0)

## Welcome to my GitHub and WeChat account [The Real Ship of Theseus]: no time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and the project is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]] | [[sources/推理引擎/推测解码|推测解码]] | [[sources/推理引擎/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[sources/推理引擎/vllm|vllm]] | [[sources/推理引擎/tensorrt-llm|tensorrt-llm]] | [[sources/推理引擎/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
