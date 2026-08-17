`Text Generation Inference (TGI)`[1](#refer-anchor-1) is a framework developed by Hugging Face for deploying and serving large language models (`LLMs`). It is a production-ready toolkit designed specifically to run large language models as a service on local machines. TGI is written in Rust and Python and provides an endpoint for calling the model, making text generation more efficient and flexible.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/0.png>)

## 1. Inference Acceleration Techniques

1. Tensor Parallelism

Tensor parallelism uses the fact that matrix multiplication can be computed in parallel: model parameters are split into several parts, each part is computed on a separate device, and the results are then merged. Below, we look at tensor parallelism for FFN and Self-Attention separately.

The main building blocks of `MLP` are fully connected `nn.Linear` layers followed by the nonlinear activation GeLU.

Following notation from the Megatron paper, the dot-product part can be written as `Y = GeLU(XA)`, where `X` and `Y` are the input and output vectors, and `A` is the weight matrix.

Looking at the computation in matrix form, it is easy to see how matrix multiplication can be split across multiple GPUs:

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/1.png>)

If the weight matrix `A` is split by columns across `N` GPUs, and matrix multiplications from `XA_1` to `XA_n` are computed in parallel, we get `N` output vectors `Y_1`, `Y_2`, ..., `Y_n`, which can be independently passed into GeLU:

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/2.png>)

Using this principle, an MLP of any depth can be updated without synchronization between GPUs until the very end, when the output vector needs to be restored.

The Megatron-LM authors give a useful example for this:

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/3.png>)

Tensor parallelism for `Self-Attention` is even simpler, because self-attention is naturally a multi-head attention mechanism: computation for each head can be distributed across different GPUs.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/4.png>)

In the figure above, self-attention can be computed in parallel on 2 GPUs, with each GPU computing attention for one head. In principle, if there are many heads, that many GPUs can be used for parallel computation.

2. Continuous batching

In traditional batch processing, the entire batch of requests must finish before results are returned together. This means shorter requests have to wait for longer ones, wasting GPU resources and increasing inference latency. Continuous Batching lets the model return a request result immediately after the current iteration if that request has finished, without waiting for every request in the batch. This noticeably improves hardware utilization and reduces idle time.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/5.png>)

Continuous Batching also helps solve resource waste caused by different compute amounts across requests. Through iteration-level scheduling, batch size dynamically adapts to request complexity, effectively reducing wait time for high-complexity requests.

It is worth noting that implementing Continuous Batching requires handling several key issues: early-finished requests, late-joining requests, and batching requests of different lengths. Two design ideas proposed by OCRA, Iteration-level Batching and Selective Batching, are aimed exactly at these problems.

3. Flash Attention

Flash Attention is a new attention algorithm jointly developed by research teams from Stanford University and the University at Buffalo. It is designed to solve the high time and memory complexity traditional Transformer models face when processing long sequences. The key idea is to reduce read and write operations between GPU high-bandwidth memory (`HBM`) and GPU on-chip SRAM. With tiling and recomputation, the algorithm greatly reduces how often it accesses HBM, improving runtime speed and reducing memory usage.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/6.png>)

Through an IO-aware approach, Flash Attention optimizes memory access patterns, makes Transformer models more efficient on long sequences, and opens the door to high-quality models with longer context.

4. PagedAttention

vLLM introduced PagedAttention, an attention algorithm inspired by classic virtual memory and paging ideas in operating systems. Unlike traditional attention algorithms, PagedAttention allows contiguous keys and values to be stored in non-contiguous memory regions. More specifically, PagedAttention splits the KV cache of each sequence into blocks, and each block contains keys and values for a fixed number of tokens. During attention computation, the PagedAttention kernel efficiently finds and fetches these blocks.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（三）Text generation inference (TGI)/7.gif>)

## 2. TGI Features

1. **Simple launcher**: TGI provides a simple launcher that can easily serve the most popular LLMs.

2. **Production readiness**: TGI integrates distributed tracing (using Open Telemetry) and Prometheus metrics, matching production-environment requirements.

3. **Tensor parallelism**: through tensor-parallel computation on multiple GPUs, TGI can noticeably speed up inference.

4. **Token streaming**: token streaming is implemented with server-sent events (`SSE`).

5. **Continuous batching**: incoming requests are processed through continuous batching, improving overall throughput.

6. **Optimized inference code**: for the most popular architectures, TGI optimizes Transformers code with Flash Attention, Paged Attention, and other technologies.

7. **Support for different quantization types**: several quantization methods are supported, including bitsandbytes, GPT-Q, EETQ, AWQ, Marlin, and fp8.

8. **Safe weight loading**: Safetensors is used for loading weights, improving safety.

9. **Watermarking**: watermarking technology from "A Watermark for Large Language Models" is integrated.

10. **Flexible generation control**: logits warpers (temperature scaling, top-p, top-k, repetition penalty, and others), stop sequences, and log-probability output are supported.

11. **Speculative generation**: latency optimization of about 2 times is implemented.

12. **Guidance/JSON output**: output format constraints are supported, which speeds up inference and ensures output follows the requested specification.

13. **Custom prompt generation**: model output can be guided with a custom prompt, making it easy to generate the desired text.

14. **Fine-tuning support**: fine-tuned models can be used for specific tasks, achieving higher accuracy and performance.

15. **Hardware support**: besides NVIDIA GPUs, TGI supports AMD GPUs, Intel GPUs, Inferentia, Gaudi, Google TPU, and other hardware platforms.

## References

<div id="refer-anchor-1"></div>

[1] [text-generation-inference](https://huggingface.co/docs/text-generation-inference/index)

[2] [Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM](https://arxiv.org/abs/2104.04473)

## Welcome to my GitHub and WeChat account [The Real Ship of Theseus]: no time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and the project is fully open source. Stars and forks are very welcome.
