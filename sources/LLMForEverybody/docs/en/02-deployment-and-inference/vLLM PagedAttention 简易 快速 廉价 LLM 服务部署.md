---
aliases: ["vllm-and-pagedattention-easy-fast-cheap-llm-serving"]
---

# vLLM: easy, fast, and cheap LLM serving with PagedAttention, English translation

## At the Very Beginning

While studying vLLM and PagedAttention, I found many high-quality materials. The most valuable one is probably the official vLLM blog: https://blog.vllm.ai/2023/06/20/vllm.html

The article is detailed and, in my opinion, very well written. So I tried to translate it into Chinese, hoping it would help more people who need this information.

Because the translator's level is limited, errors in the translation are unavoidable. Please be understanding. If you notice a problem, point it out in the comments and I will try to fix it as soon as possible.

## Main Text

LLMs promise to fundamentally change how we use AI across industries. However, building a real service for a model is quite difficult: it can turn out unexpectedly slow even on expensive hardware. Today, June 20, 2023, translator note, we are happy to introduce vLLM, an open source library for fast LLM inference and serving. vLLM uses PagedAttention, our new attention algorithm that efficiently manages attention keys and values. vLLM with PagedAttention redefines the SOTA level of LLM serving: its throughput is up to 24 times higher than HuggingFace Transformers, with no model architecture changes required.

vLLM was developed at UC Berkeley and has been used internally for the last two months inside [Chatbot Arena and Vicuna Demo](https://lmarena.ai/). It is the key technology that makes LLM services economical and accessible even for small research teams with limited compute resources, such as LMSYS. Now you can try vLLM with just one command from our [GitHub repository](https://github.com/vllm-project/vllm).

## Performance Above SOTA

We compared vLLM throughput with the most popular LLM library, [HuggingFace Transformers (HF)](https://huggingface.co/docs/transformers/main_classes/text_generation), and the previous SOTA system, [HuggingFace text-generation-inference (TGI)](https://github.com/huggingface/text-generation-inference). The evaluation used two configurations: LLaMA-7B on an NVIDIA A10G GPU and LLaMA-13B on an NVIDIA A100 GPU (40 GB). Request input/output lengths came from the ShareGPT dataset. In our experiments, vLLM throughput was 24 times higher than HF and 3.5 times higher than TGI.

![alt text](<../../../02-第二章-部署与推理/assest/vLLM 使用PagedAttention轻松、快速且廉价地提供LLM服务（中文版翻译）/0.png>)

The figure above shows serving throughput with one output per request. vLLM throughput is 14 to 24 times higher than HF and 2.2 to 2.5 times higher than TGI.

![alt text](<../../../02-第二章-部署与推理/assest/vLLM 使用PagedAttention轻松、快速且廉价地提供LLM服务（中文版翻译）/1.png>)

The figure above shows serving throughput with three parallel outputs per request. vLLM throughput is 8.5 to 15 times higher than HF and 3.3 to 3.5 times higher than TGI.

## The Secret: PagedAttention

In vLLM, we found that the performance bottleneck of LLM serving is memory, meaning GPU memory. During autoregressive decoding, all input tokens of the LLM create their attention key and value tensors, which are stored in GPU memory for generating the next tokens. These cached key and value tensors are usually called KV Cache. KV Cache has the following features:

- Large size: in LLaMA-13B, one sequence takes up to 1.7 GB.
- Dynamic shape: size depends on sequence length, and sequence length varies a lot and is hard to predict. So efficient KV Cache management is a serious challenge. We found that existing systems waste 60% to 80% of memory because of fragmentation and excessive reservation.

To solve this problem, we introduced PagedAttention, an attention algorithm inspired by classic virtual memory and paging ideas in operating systems. Unlike traditional attention algorithms, PagedAttention allows contiguous keys and values to be stored in non-contiguous memory regions. More specifically, PagedAttention splits each sequence's KV Cache into blocks, and each block contains keys and values for a fixed number of tokens. During attention computation, the PagedAttention kernel efficiently finds and fetches these blocks.

![alt text](<../../../02-第二章-部署与推理/assest/vLLM 使用PagedAttention轻松、快速且廉价地提供LLM服务（中文版翻译）/2.gif>)

PagedAttention: KV Cache is split into blocks. Blocks do not need to be contiguous in memory.

Since blocks do not need to be contiguous in memory, we can manage keys and values more flexibly, like virtual memory in an operating system: blocks can be viewed as pages, tokens as bytes, and sequences as processes. A sequence's contiguous ***logical blocks*** are mapped through a **block table** to non-contiguous ***physical blocks***. Physical blocks are allocated on demand as new tokens are generated.

> Note: this will come up in interviews.

![alt text](<../../../02-第二章-部署与推理/assest/vLLM 使用PagedAttention轻松、快速且廉价地提供LLM服务（中文版翻译）/3.gif>)

Example request generation process with PagedAttention.

In PagedAttention, memory waste happens only in the last block of a sequence. In practice, this gives almost optimal memory usage: the waste ratio is below 4%. The memory-efficiency improvement is very useful: the system can batch more sequences, improve GPU utilization, and significantly increase throughput, as shown in the performance results above.

PagedAttention has another key advantage: efficient memory sharing. For example, in parallel sampling, the same prompt generates several output sequences. In this case, computation and memory for that prompt can be shared across output sequences.

![alt text](<../../../02-第二章-部署与推理/assest/vLLM 使用PagedAttention轻松、快速且廉价地提供LLM服务（中文版翻译）/4.gif>)

Example of parallel sampling.

PagedAttention naturally implements memory sharing through its block table. Just as processes share physical pages, different sequences in PagedAttention can share blocks by mapping their logical blocks to the same physical block. To make sharing safe, PagedAttention tracks reference counts for physical blocks and implements copy-on-write.

![alt text](<../../../02-第二章-部署与推理/assest/vLLM 使用PagedAttention轻松、快速且廉价地提供LLM服务（中文版翻译）/5.gif>)

Example request generation process when sampling multiple outputs.

PagedAttention's memory sharing greatly reduces memory overhead for complex sampling algorithms such as `parallel sampling` and `beam search`, and can reduce memory usage by up to 55%. This can translate into up to 2.2 times higher throughput. Because of this, these sampling methods become practical in LLM serving.

PagedAttention is the key technology behind vLLM, our LLM inference and serving engine. vLLM supports many models, has high performance, and provides a convenient interface. For more technical details about vLLM and PagedAttention, see our [GitHub repository](https://github.com/vllm-project/vllm) and follow our paper.

## The Hidden Hero of LMSYS Vicuna and Chatbot Arena

In April 2023, translator note, LMSYS developed and open sourced the popular chatbot model Vicuna. Since then, Vicuna has served millions of users in [Chatbot Arena](https://lmarena.ai/). Initially, LMSYS FastChat used an HF Transformers-based [serving backend](https://github.com/lm-sys/FastChat/blob/main/fastchat/serve/model_worker.py) to serve the chat demo. As the demo became more popular, peak traffic grew several times, and the HF backend became a serious bottleneck. The LMSYS and vLLM teams jointly and quickly developed a FastChat-vLLM integration, using vLLM as a [new backend](https://github.com/lm-sys/FastChat/blob/main/fastchat/serve/vllm_worker.py) to support growing demand, up to 5 times the traffic. In early [internal microbenchmarks](https://github.com/lm-sys/FastChat/blob/main/fastchat/serve/test_throughput.py), the LMSYS serving backend on vLLM achieved **30 times higher throughput than the original HF backend**.

Since mid-April 2023, the most popular models, including Vicuna, Koala, and LLaMA, have been served successfully through the FastChat-vLLM integration. Using FastChat as the frontend of a multi-model chat service and vLLM as the inference backend, LMSYS was able to serve millions of Vicuna users with high throughput and low latency using a limited number of university-sponsored GPUs. LMSYS is expanding vLLM usage to a wider set of models, including Databricks Dolly, OpenAsssiant by LAION, and StableLM by Stability AI. Support for more [models](https://docs.vllm.ai/en/latest/models/supported_models.html) is under development and coming soon.

![alt text](<../../../02-第二章-部署与推理/assest/vLLM 使用PagedAttention轻松、快速且廉价地提供LLM服务（中文版翻译）/6.png>)

Requests processed by the FastChat-vLLM integration in Chatbot Arena from April to May. In fact, more than half of Chatbot Arena requests used vLLM as the inference backend.

Using vLLM also greatly reduced operating costs. Thanks to vLLM, LMSYS reduced the number of GPUs needed for the same traffic by 50%. vLLM handles 30K requests per day on average, with peaks reaching 60K, which shows vLLM's stability well.

## Getting Started with vLLM

Install vLLM with the following command. For more information, see the [installation guide](https://docs.vllm.ai/en/latest/getting_started/installation.html):

```shell
$ pip install vllm
```

vLLM can be used for both offline inference and online serving. To use vLLM for offline inference, import vLLM and use the LLM class in a Python script:

```python
from vllm import LLM

prompts = ["Hello, my name is", "The capital of France is"]  # Sample prompts.
llm = LLM(model="lmsys/vicuna-7b-v1.3")  # Create an LLM.
outputs = llm.generate(prompts)  # Generate texts from the prompts.
```

To use vLLM for online serving, you can start an OpenAI API-compatible server like this:

```shell
$ python -m vllm.entrypoints.openai.api_server --model lmsys/vicuna-7b-v1.3
```

You can query the server in the same format as the OpenAI API:

```shell
$ curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "lmsys/vicuna-7b-v1.3",
        "prompt": "San Francisco is a",
        "max_tokens": 7,
        "temperature": 0
    }'
```

For more ways to use vLLM, see the [quickstart guide](https://docs.vllm.ai/en/latest/getting_started/quickstart.html).

## Welcome to my GitHub and WeChat Official Account: no time to explain, hurry aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and it is fully open source. Stars and forks are very welcome.
