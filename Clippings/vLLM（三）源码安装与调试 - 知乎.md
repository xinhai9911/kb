---
title: "vLLM（三）源码安装与调试"
source: ""
author: "知乎·vLLM 源码解读系列"
published:
created: 2026-08-19
description: "本系列将介绍 vLLM 的方方面面："
tags:
  - "clippings"
  - "vLLM"
  - "知乎"
series: "vLLM（知乎）"
part: "三"
---
> [https://github.com/vllm-project/vllm](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm)

本系列将介绍 vLLM 的方方面面：

___

在解读 vLLM 源码前，插入一篇源码安装与调试的文章，目的是希望大家也可以跟着安装一下 vLLM，这样可以在阅读源码解析的文章时跟着一步一步调试，加深对 vLLM 设计与实现的理解，相信会有很大的收获。

## 源码安装

-   创建 conda 环境

```bash
> conda create -n vllm-env python=3.10 -y > conda activate vllm-env
```

-   下载源码

```bash
> git clone https://github.com/vllm-project/vllm.git > cd vllm
```

-   切换到目的版本

```bash
# 后续的源码解读都基于 v0.2.7 这个版本 > git checkout v0.2.7
```

-   查看依赖的 pytorch 版本

```bash
> cat requirements.txt ... torch == 2.1.2 transformers >= 4.36.0 # Required for Mixtral. xformers == 0.0.23.post1 # Required for CUDA 12.1. ...
```

-   安装 pytorch

需保证`nvcc --version`显示的版本也为 12.1。

```bash
> conda install pytorch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 pytorch-cuda=12.1 -c pytorch -c nvidia
```

-   安装 vllm

注意：我使用的 gcc 版本是 7.5.0，如果太低，编译可能会遇到错误。

## 调试

调试基于 [VSCode](https://zhida.zhihu.com/search?content_id=241952750&content_type=Article&match_order=1&q=VSCode&zhida_source=entity)，使用它让调试变得简单。  
先新建一个`vllm_debug.py`文件，内容如下：

```python3
from vllm import LLM, SamplingParams prompts = [ "Hello, my name is", "The future of AI is", "The life is", ] sampling_params = SamplingParams(temperature=0.8, top_p=0.95) # meta-llama/Llama-2-7b-hf 权重已下载到本地的 ckpts 路径 # 如果还没下载，可以直接 llm = LLM(model="meta-llama/Llama-2-7b-hf") llm = LLM(model="./ckpts/llama-2-7b-hf") outputs = llm.generate(prompts, sampling_params) # Print the outputs. for output in outputs: prompt = output.prompt generated_text = output.outputs[0].text print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")
```

然后在第 12 行和 14 行设置断点，如图 1 所示：

![](https://pic2.zhimg.com/v2-6af7d67f1f874d04f7d5d1744fcf0c61_1440w.jpg)

图 1：设置断点

最后按 F5 开始调试。

![](https://pic1.zhimg.com/v2-507332628e50831ac8c1db5c0dcdebb5.jpg?source=25ab7b06)

01:02

代码调试演示

对安装与调试的介绍就到此为止了，接下来的 vLLM 源码解读计划分三篇文章介绍，第一篇介绍 vLLM 组件的初始化，第二篇介绍[调度策略](https://zhida.zhihu.com/search?content_id=241952750&content_type=Article&match_order=1&q=%E8%B0%83%E5%BA%A6%E7%AD%96%E7%95%A5&zhida_source=entity)的实现细节，第三篇介绍模型的推理细节。

---

> **vLLM（知乎）系列导航**：[[vLLM 系列（知乎）索引|系列索引]] ｜ 上一篇：[[vLLM（二）架构概览 - 知乎|二：架构概览]] ｜ 下一篇：[[vLLM（四）核心组件的初始化 - 知乎|四：核心组件的初始化]]

