---
aliases: ["llm-inference-frameworks-part-5-ollama"]
---

## Introduction

Today, private deployment of a large model is no longer a high-barrier or especially technically difficult task. Most of the time, it is simply a matter of access to the right information. Ollama offers the simplest deployment method.

Technical requirements: be able to click the mouse a little and type. We only need two applications:

Ollama: https://ollama.com/

ChatBox: https://chatboxai.app/zh

## Ollama

Ollama is an open source tool for serving large language models (`LLM`). It is designed to simplify local LLM operation and lower the barrier to using them. It lets developers, researchers, and enthusiasts quickly experiment with, manage, and deploy modern large language models locally, including but not limited to open source LLMs such as Qwen2, Llama3, Phi3, Gemma2, and others. With a simple and efficient interface, Ollama makes it easy to create, run, and manage these models, and also provides a rich library of ready-made models for convenient integration into different applications.

### 1. Download Ollama

Download Ollama from the official website: https://ollama.com/

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/1.png>)

### 2. Install Ollama

Go through the installer: a few clicks, and installation is done.

### 3. Download a Model

In the Ollama model library at https://ollama.com/library, find a model you like. For a convenient test, you can choose a small `tiny` model.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/2.png>)

You can use the qwen2 0.5b model. It uses 4-bit quantization, and the model size is only 352 MB.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/3.png>)

In the `cmd` terminal, enter the command to download the model:

> ollama pull qwen2:0.5b

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/4.png>)

### 4. Run Ollama

Enter the command to run qwen2:0.5b:

> ollama run qwen2:0.5b

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/5.png>)

At this point, you already have a local large model on your computer. You can also download other, larger models to improve answer quality.

## ChatBox

Chatbox AI is an AI client and intelligent assistant that supports many modern AI models and APIs. It is available on Windows, MacOS, Android, iOS, Linux, and the web.

### 1. Download ChatBox

Download ChatBox from the official website: https://chatboxai.app/zh#download

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/6.png>)

### 2. Install ChatBox

Go through the installer: a few clicks, and installation is done.

### 3. Configure ChatBox

Find settings in the lower-left corner of ChatBox.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/7.png>)

Choose ollama as the model provider.

![alt text](<../../../02-第二章-部署与推理/assest/大模型推理框架（五）Ollama/8.png>)

Set API: http://localhost:11434

Set model: qwen2:0.5b

Click save.

Test.

9

You can see that the answer has already been generated through qwen2:0.5b. If you have a very powerful GPU, you can download a larger model for deployment, and the result will be better.

The whole process does not require deep computer knowledge. Being able to install ordinary applications is enough.

## Welcome to my GitHub and WeChat account [The Real Ship of Theseus]: no time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and the project is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]] | [[sources/推理引擎/推测解码|推测解码]] | [[sources/推理引擎/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[sources/推理引擎/vllm|vllm]] | [[sources/推理引擎/tensorrt-llm|tensorrt-llm]] | [[sources/推理引擎/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
