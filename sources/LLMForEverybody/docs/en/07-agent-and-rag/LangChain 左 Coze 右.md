---
aliases: ["langchain-nalevo-coze-napravo"]
---

# LangChain to the Left, Coze to the Right

## 1. Background

For many people, LangChain and Coze feel like tools for two different audiences. LangChain, currently the most popular framework for Agent development, is aimed at developers building large-model applications. Coze is seen more as an entertainment tool: with a very low no-code threshold, mainly through prompt engineering, users can build their own bots and share them in communities. But now, as platforms like Coze deepen their API development, LangChain's position is being challenged.

At the 2023 World Artificial Intelligence Conference (`WAIC`), the theme was the "battle of a hundred models." This year's WAIC keyword is "applications first." If you look at the hot forum topics this year, whether embodied intelligence or AI Agent, all of them point toward vertical application of AI technology based on large models in different scenarios.

![alt text](../../../07-第七章-Agent/assest/langchain向左coze向右/1.webp)

**Agent**

An Agent is a system that can perceive its environment and make decisions based on the perceived information to achieve a specific goal. With support from large models, Agent has become more visible than ever before.

## 2. LangChain

Agent frameworks led by LangChain are currently the most widely used open source frameworks in China. The original design idea of LangChain was to represent a workflow as a DAG (`directed acyclic graph`), which is where Chain came from.

As the Multi-Agent idea spreads and the Agent paradigm gradually settles, Agent workflows become more complex: loops and other conditions appear. That requires a Graph approach, and LangGraph appeared for this reason.

![alt text](../../../07-第七章-Agent/assest/langchain向左coze向右/2.webp)

**Criticism of LangChain**

The fame is large, and so is the criticism. LangChain is often criticized, and the main complaint is about code volume and abstraction level: the amount of code when using LangChain is roughly comparable to using only the official OpenAI library, while LangChain combines more object classes but does not provide an obvious code advantage. Also, LangChain's abstractions increase code complexity without clear benefit, making development and maintenance harder.

## 3. Coze

**What is Coze**

Coze is a next-generation AI platform for developing large-model applications. Whether or not you have programming skills, you can quickly build different bots, publish them to major social platforms with one click, or easily deploy them on your own website.

![alt text](../../../07-第七章-Agent/assest/langchain向左coze向右/3.webp)

**Publishing platforms**

Besides publishing to social networks, a completed bot can be published as an API. This means an Agent can be created through drag-and-drop (`low-code`) and then embedded through an API into any workflow. Coze suddenly turns from an entertainment tool into a real productivity tool.

![alt text](../../../07-第七章-Agent/assest/langchain向左coze向右/4.webp)

## 4. Development paradigm shift

**Paradigm shift**

For large companies, platform competition means ecosystem competition, and Coze already has first-mover advantage. Previously, everyone built small bots, published them in Doubao, or placed them in a WeChat Official Account. After APIs opened, we can put Agents into any workflow, which means we can create many productivity tools and embed them into existing workflows across different industries.

**My view**

At least in China, ordinary developers should focus more on the business problems solved by Agents, instead of spending too much time on the lower-level details of LangChain. If all players follow APIs, creating Agents will become work with almost no development cost, and then ideas will become incredibly important.

## References

<div id="refer-anchor-1"></div>

[1] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)


---

## 📚 相关概念

[[concepts/RAG 检索 增强 生成|RAG 检索 增强 生成]] | [[concepts/向量 DB 嵌入|向量 DB 嵌入]] | [[concepts/混合 检索 bm 25 语义 融合|混合 检索 bm 25 语义 融合]] | [[concepts/智能体 编排 模式|智能体 编排 模式]] | [[concepts/智能体 编程|智能体 编程]] | [[concepts/智能体 工具 使用 MCP|智能体 工具 使用 MCP]] | [[concepts/智能体 长 期 内存|智能体 长 期 内存]] | [[concepts/多 智能体 协作|多 智能体 协作]] | [[concepts/LLM 智能体 测试框架|LLM 智能体 测试框架]] | [[concepts/浏览器 智能体|浏览器 智能体]] | [[concepts/轻量 智能体 框架|轻量 智能体 框架]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/LangChain|LangChain]] | [[entities/CrewAI|CrewAI]] | [[entities/Anthropic|Anthropic]] | [[entities/OpenAI|OpenAI]] | [[entities/Google ADK|Google ADK]] | [[sources/Anthropic 智能体 构建|Anthropic 智能体 构建]] | [[sources/LangChain 入门|LangChain 入门]] | [[sources/MCP 规范|MCP 规范]] | [[sources/智能体 框架 对比|智能体 框架 对比]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：Agent
