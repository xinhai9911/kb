---
aliases: ["llm-application-adoption-classification-part-1"]
---

# LLM Application Adoption Guide: Classification, Part 1

## 1. Application classification

### 1.1 LLM application scenarios

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/1.png>)

### 1.2 Classification of LLM applications

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/2.png>)

## 2. Complexity evaluation

### 2.1 Complexity levels

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/3.png>)

- L1 applications: rely on the LLM's own capabilities, make one LLM call, and let the LLM directly produce the result.
- L2 applications: take the limits of the LLM's own capabilities into account and start decomposing the task. The earliest RAG applications are a typical scenario at this level: they fill knowledge gaps in the LLM through retrieval.
- L3 applications: introduce an Agent capability such as reflection. Reflection is a very important Agent capability: it lets the system react to information from the environment, check whether the goal has been reached, and execute the task again. Important: at this stage, Agent capabilities are introduced through code.
- L4 applications: full Agent. It needs tools so it can plan by itself and use tools to autonomously complete any related tasks or answer questions.

### 2.2 Complexity evaluation: knowledge Q&A as an example

Let's take knowledge Q&A and look at L1-L4 applications.

**L1: simple knowledge Q&A**

- No extra knowledge is provided. Answers are based only on the model's own capabilities.
- The model may have been fine-tuned for a vertical domain.

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/4.png>)

**L2: RAG-based knowledge Q&A**

- RAG is introduced: the knowledge base fills the model's knowledge gaps and helps avoid hallucinations.

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/5.png>)

**L3: knowledge Q&A with a simple Agent**

- Reflection against the goal is introduced. In a RAG Agent, the system must determine whether the user's question is clear enough. If not, it should ask for clarification.
- It also needs to determine whether RAG retrieval found knowledge that can answer the question. If not, retrieval is performed again.

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/6.png>)

**L4: knowledge Q&A with a full Agent**

- Long-term memory is introduced: based on the user's habits, the Agent can understand what the user wanted to express and proactively remove ambiguity from the question.
- Planning is introduced: the Agent can plan which of several knowledge bases to query first, then based on the found data, decide which knowledge bases to use for detailed information, repeating this cycle iteratively.

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/7.png>)

## 3. UX risk

### 3.1 UX risk formula for large models

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/8.png>)

### 3.2 Prioritizing work based on error impact

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/9.png>)

## 4. Common ways to build L3 LLM applications

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/10.png>)

Note: aside from several redrawn diagrams, the content of this article is mostly copied from the Thoughtworks WeChat article listed as source 1.

## References

[1] [LLM应用落地实施手册](https://mp.weixin.qq.com/s/t-uYwd9NOxJIAIMAYWEqhg)


---

## 📚 相关概念

[[concepts/RAG 检索 增强 生成|RAG 检索 增强 生成]] | [[concepts/向量 DB 嵌入|向量 DB 嵌入]] | [[concepts/混合 检索 bm 25 语义 融合|混合 检索 bm 25 语义 融合]] | [[concepts/智能体 编排 模式|智能体 编排 模式]] | [[concepts/智能体 编程|智能体 编程]] | [[concepts/智能体 工具 使用 MCP|智能体 工具 使用 MCP]] | [[concepts/智能体 长 期 内存|智能体 长 期 内存]] | [[concepts/多 智能体 协作|多 智能体 协作]] | [[concepts/LLM 智能体 测试框架|LLM 智能体 测试框架]] | [[concepts/浏览器 智能体|浏览器 智能体]] | [[concepts/轻量 智能体 框架|轻量 智能体 框架]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/LangChain|LangChain]] | [[entities/CrewAI|CrewAI]] | [[entities/Anthropic|Anthropic]] | [[entities/OpenAI|OpenAI]] | [[entities/Google ADK|Google ADK]] | [[sources/Anthropic 智能体 构建|Anthropic 智能体 构建]] | [[sources/LangChain 入门|LangChain 入门]] | [[sources/MCP 规范|MCP 规范]] | [[sources/智能体 框架 对比|智能体 框架 对比]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：Agent
