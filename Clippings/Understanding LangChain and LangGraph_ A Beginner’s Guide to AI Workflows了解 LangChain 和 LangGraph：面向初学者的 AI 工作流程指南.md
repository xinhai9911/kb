---
title: "Understanding LangChain and LangGraph: A Beginner’s Guide to AI Workflows了解 LangChain 和 LangGraph：面向初学者的 AI 工作流程指南"
source: "https://medium.com/data-science-collective/understanding-langchain-and-langgraph-a-beginners-guide-to-ai-workflows-ad21cd79aba3"
author:
  - "[[Manish Shivanandhan]]"
published: 2025-11-03
created: 2026-08-10
description: "Learn how LangChain and LangGraph help you design intelligent, adaptive AI workflows that move from simple prompts to full applications.了解 LangChain 和 LangGraph 如何帮助您设计智能且可适应的 AI 工作流程，让这些工作流程能够从简单的提示逐步发展为完整的应用程序。"
tags:
  - "clippings"
---
## Learn how LangChain and LangGraph help you design intelligent, adaptive AI workflows that move from simple prompts to full applications.了解 LangChain 和 LangGraph 如何帮助您设计智能且可适应的 AI 工作流程，让这些工作流程能够从简单的提示逐步发展为完整的应用程序。

![](https://miro.medium.com/v2/resize:fit:1400/format:webp/0*knDEi0_mIuhwpjnD.png)

Artificial intelligence is moving fast.  
人工智能的发展速度非常快。

Every week, new tools appear that make it easier to build apps powered by large language models.  
每周都有新的工具出现，这些工具使得使用大型语言模型来构建应用程序变得更加容易。

But many beginners still get stuck on one question. How do you structure the logic of an AI application? How do you connect prompts, memory, tools, and APIs in a clean way?  
不过，许多初学者仍然在面临一个难题：如何构建人工智能应用程序的逻辑结构？如何以一种清晰的方式将提示、记忆、工具和 API 连接起来？

That is where popular open-source frameworks like [LangChain](https://www.langchain.com/) and [LangGraph](https://www.langchain.com/langgraph) come in.  
这就是像 LangChain 和 LangGraph 这样的流行开源框架发挥作用的地方。

Both are part of the same ecosystem. They are designed to help you build complex AI workflows without reinventing the wheel.  
两者都是同一个生态系统的一部分。它们的设计目的是帮助您构建复杂的 AI 工作流程，而无需重新发明轮子。

LangChain focuses on building sequences of steps called chains, while LangGraph takes things a step further by adding memory, branching, and feedback loops to make your AI more intelligent and flexible.  
LangChain 专注于构建一系列步骤，这些步骤被称为“链”；而 LangGraph 则更进一步，通过引入记忆功能、分支机制以及反馈循环，使人工智能更加智能且灵活。

This guide will help you understand what these tools do, how they differ, and how you can start using them to build your own AI projects.  
本指南将帮助您了解这些工具的功能、它们之间的差异，以及如何开始使用它们来构建自己的 AI 项目。

### What is LangChain? 什么是 LangChain？

[LangChain](https://www.turingtalks.ai/p/how-to-build-better-ai-workflows-with-langchain) is a Python and JavaScript framework that helps you build language model powered applications. It provides a structure for connecting models like GPT, data sources, and tools into a single flow.  
LangChain 是一个基于 Python 和 JavaScript 的框架，可以帮助你构建基于语言模型的应用程序。它提供了一种结构，可以将如 GPT 这样的模型、数据来源以及各种工具整合到一个统一的系统中。

Instead of writing long prompt templates or hard coding logic, you use components like chains, tools, and agents.  
与其编写冗长的提示模板或硬编码逻辑，不如使用诸如链条、工具和代理之类的组件。

A simple example is chaining prompts together.  
一个简单的例子就是将提示串联起来使用。

For instance, you might first ask the model to summarize text, and then use the summary to generate a title. LangChain lets you define both steps and connect them in code.  
例如，你可以先让模型对文本进行总结，然后利用这个总结来生成标题。LangChain 允许你定义这两个步骤，并在代码中将它们连接起来。

Here is a basic example in Python:  
以下是用 Python 编写的一个基本示例：

```hs
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = PromptTemplate.from_template("Summarize the following text:\n{text}")
chain = LLMChain(prompt=prompt, llm=llm)
result = chain.run({"text": "LangChain helps developers build AI apps faster."})
print(result)
```

This simple chain takes text and runs it through an OpenAI model to get a summary. You can add more steps, like a second chain to turn that summary into a title or a question.  
这个简单的流程首先接收文本，然后将其通过 OpenAI 模型进行处理以生成摘要。你可以添加更多的步骤，比如再连接一个链条，将摘要转化为标题或问题形式。

LangChain provides modules for prompt templates, models, retrievers, and tools so you can build workflows without managing the raw API logic.  
LangChain 提供了各种模块，包括提示模板、模型、检索器以及工具等，帮助你构建工作流程，而无需管理原始的 API 逻辑。

Here is the full [LangChain documentation](https://docs.langchain.com/oss/python/langchain/overview).  
以下是完整的 LangChain 文档内容。

### Why LangChain Was Not Enough为什么 LangChain 并不足够好

LangChain made it easy to build straight-line workflows.  
LangChain 使得构建直线型工作流程变得非常简单。

But most real-world applications are not linear. When [building a chatbot](https://www.freecodecamp.org/news/build-a-custom-ai-chat-application-with-nextjs/), summarizer, or an autonomous agent, you often need loops, memory, and conditions.  
但是，大多数现实世界中的应用程序并不遵循线性逻辑。在构建聊天机器人、摘要工具或自主代理时，通常需要处理循环、记忆机制以及各种条件判断。

For example, if the AI makes a wrong assumption, you might want it to try again. If it needs more data, it should call a search tool. Or if a user changes context, the AI should remember what was discussed earlier.  
例如，如果人工智能做出了错误的假设，你可能希望它重新尝试。如果它需要更多数据，那么它应该调用搜索工具来获取信息。或者，当用户改变上下文时，人工智能应该记住之前讨论过的内容。

LangChain’s chains and agents could do some of this, but the flow was hard to visualize and manage. You had to write nested chains or use callbacks to handle decisions.  
LangChain 的链和代理可以执行其中的一些任务，但整个流程很难可视化和管理。通常需要编写嵌套的链结构，或者使用回调来处理各种决策。

Developers wanted a better way to represent how AI systems actually think. Not in straight lines, but as graphs where outputs can lead to different paths.  
开发者们希望找到一种更好的方式来表示人工智能系统实际的思维方式。不是用直线来表示，而是用图表来展示，这样就能显示出不同的输出路径。

That is what led to LangGraph.  
正是这一点促成了 LangGraph 的诞生。

### What is LangGraph? 什么是 LangGraph？

LangGraph is an extension of LangChain that introduces a graph-based approach to AI workflows.  
LangGraph 是 LangChain 的一个扩展版本，它引入了基于图的结构来设计人工智能工作流程的方法。

Instead of chaining steps in one direction, LangGraph lets you define nodes and edges like a flowchart. Each node can represent a task, an action, or a model call.  
与单向地连接步骤不同，LangGraph 允许你像绘制流程图一样来定义节点和边。每个节点可以代表一个任务、一个操作或某个模型调用。

This structure allows loops, branching, and parallel paths. It is perfect for building agent-like systems where the model reasons, decides, and acts.  
这种结构支持循环、分支以及并行路径的处理。它非常适合构建类似代理的系统，在这些系统中，模型能够进行推理、决策并采取行动。

Here is an example of a simple LangGraph setup:  
以下是简单的 LangGraph 配置示例：

```hs
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain.agents import Tool

def multiply(a: int, b: int):
    return a * b
tools = [Tool(name="multiply", func=multiply, description="Multiply two numbers")]
llm = ChatOpenAI(model="gpt-4o-mini")
agent_executor = create_react_agent(llm, tools)
graph = StateGraph()
graph.add_node("agent", agent_executor)
graph.set_entry_point("agent")
graph.add_edge("agent", END)
app = graph.compile()
response = app.invoke({"input": "Use the multiply tool to get 8 times 7"})
print(response)
```

This example shows a basic agent graph.  
这个例子展示了一个基本的代理图结构。

The AI receives a request, reasons about it, decides to use the tool, and completes the task. You can imagine extending this to more complex graphs where the AI can retry, call APIs, or fetch new information.  
人工智能系统接收到请求后，会进行分析，决定是否使用相关工具来完成任务。你可以想象，这种机制可以扩展到更复杂的图表结构，让人工智能在需要时能够重新尝试、调用 API 或获取新信息。

LangGraph gives you full control over how the AI moves between states. Each node can have conditions. For example, if an answer is incomplete, you can send it back to another node to refine it.  
LangGraph 让你能够完全控制人工智能在不同状态之间的切换。每个节点都可以有相应的条件判断。例如，如果某个答案还不够完善，你可以将其发送回另一个节点进行完善。

This makes LangGraph ideal for building systems that need multiple reasoning steps, like document analysis bots, code reviewers, or research assistants.  
这使得 LangGraph 非常适合构建需要多个推理步骤的系统，比如文档分析机器人、代码审核员或研究助手等。

Here is the full [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview).  
以下是完整的 LangGraph 文档内容。

### LangChain vs LangGraph LangChain 与 LangGraph 的区别

LangChain and LangGraph share the same foundation, but they approach workflows differently.  
LangChain 和 LangGraph 有着相同的基础，但它们在处理工作流程方面的方式有所不同。

LangChain is linear. Each chain or agent moves from one step to the next in a sequence. It is simpler to start with, especially for prompt engineering, retrieval-augmented generation, and structured pipelines.  
LangChain 是一种线性结构。每个链条或代理都按序列依次进行下一步操作。这种结构比较简单，尤其适用于提示生成、检索增强生成以及结构化流程等场景。

LangGraph is dynamic. It represents workflows as graphs that can loop, branch, and self-correct. It is more powerful when building agents that need reasoning, planning, or memory.  
LangGraph 是动态化的系统。它将工作流程表示为可以循环、分支以及自我修正的图表。在构建需要推理、规划或记忆功能的代理时，它表现得更加出色。

A good analogy is this. LangChain is like writing a list of tasks in order. LangGraph is like drawing a flowchart where decisions can lead to different actions or back to previous steps.  
一个很好的类比就是：LangChain 就像是一系列任务的列表；而 LangGraph 则更像是一个流程图，其中决策可以引导到不同的行动，或者回到之前的步骤。

Most developers start with LangChain to learn the basics, then move to LangGraph when they want to build more interactive or autonomous AI systems.  
大多数开发者最初都会使用 LangChain 来学习基础知识，当他们需要构建更互动或自主的人工智能系统时，才会转向 LangGraph。

### When to Use Each 何时使用每种方法

If you are building simple tools like text summarizers, chatbots, or document retrievers, LangChain is enough. It is easy to get started and integrates well with popular models like GPT, Anthropic Claude, and Gemini.  
如果你正在构建一些简单的工具，比如文本摘要工具、聊天机器人或文档检索系统，那么 LangChain 就足够了。开始使用起来非常容易，而且它与 GPT、Anthropic Claude 以及 Gemini 等流行的模型可以很好地集成在一起。

==If you want to build multi-step agents, or apps that think and adapt, go with LangGraph. You can define how the AI reacts to different outcomes, and you get more control over retry logic, context switching, and feedback loops.  
如果你想要构建多步骤的代理程序，或者开发能够自主思考和适应的应用程序，那么可以选择 LangGraph。你可以定义人工智能对不同结果的反应方式，同时还能更好地控制重试逻辑、上下文切换以及反馈机制。==

In practice, many developers combine both. LangChain provides the building blocks, while LangGraph organizes how those blocks interact.  
在实践中，许多开发者会结合使用这两种方法。LangChain 提供了构建模块的基础框架，而 LangGraph 则负责协调这些模块之间的交互方式。

### Adding Memory and Persistence增加内存和持久性功能

Both LangChain and LangGraph support memory, which lets your AI remember context between interactions. For example, a chatbot that remembers what the user said earlier can respond more naturally.  
LangChain 和 LangGraph 都支持内存功能，这使得人工智能能够在不同的交互中记住上下文信息。例如，一个能够记住用户之前所说内容的聊天机器人，就能更自然地进行回应。

In LangChain, you can use `ConversationBufferMemory` or `ConversationSummaryMemory`. In LangGraph, you can include memory as part of the graph’s state so that it persists between nodes.  
在 LangChain 中，可以使用 `ConversationBufferMemory` 或 `ConversationSummaryMemory` 。而在 LangGraph 中，可以将内存作为图状态的一部分，从而使其在节点之间保持持久性。

Here is a simple example with memory in LangChain:  
以下是一个关于 LangChain 中内存处理的简单示例：

```hs
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_openai import ChatOpenAI

memory = ConversationBufferMemory()
llm = ChatOpenAI(model="gpt-4o-mini")
conversation = ConversationChain(llm=llm, memory=memory)
conversation.predict(input="Hello, I am Manish.")
conversation.predict(input="What did I just tell you?")
```

The model will respond knowing that you introduced yourself in the first message. This same concept works inside LangGraph, but on a larger scale, enabling stateful workflows where memory is part of the graph.  
该模型会根据你在第一条消息中做过的自我介绍来做出响应。这个概念在 LangGraph 中也适用，只不过应用范围更广，能够实现包含记忆功能的有状态工作流程。

### Monitoring and Debugging with LangSmith使用 LangSmith 进行监控和调试

[LangSmith](https://www.langchain.com/langsmith/observability) is another important tool from the LangChain ecosystem. It helps you visualize, monitor, and debug your AI applications.  
LangSmith 是 LangChain 生态系统中的另一个重要工具。它可以帮助你可视化、监控和调试你的 AI 应用程序。

When building workflows, you often want to see how the model behaves, how much it costs, and where things go wrong.  
在构建工作流程时，你通常需要了解模型的行为表现、其成本是多少，以及可能出现的问题所在。

LangSmith records every call made by your chains and agents. You can view input and output data, timing, token usage, and errors. It provides a dashboard that shows how your system performed across multiple runs.  
LangSmith 记录了您的所有呼叫情况，包括通过渠道和代理发出的呼叫。您可以查看输入数据、输出数据、调用时间、令牌使用情况以及错误信息。该工具还提供了一个仪表板，可以显示系统在多次运行中的表现情况。

You can integrate LangSmith easily by setting your environment variable:  
您可以通过设置环境变量来轻松集成 LangSmith 工具：

```hs
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="your_api_key_here"
```

Then, every LangChain or LangGraph process you run will automatically log to LangSmith. This helps developers find bugs, optimize prompts, and understand how the workflow behaves at each step.  
因此，你运行的每个 LangChain 或 LangGraph 过程都会自动记录到 LangSmith 中。这有助于开发者发现漏洞、优化提示语，并了解工作流程在每一步中的表现情况。

Please note that while Langchain and LangGraph are open source, Langsmith is a paid platform. Langsmith is a good-to-have tool and not a requirement to build AI workflows.  
请注意，虽然 Langchain 和 LangGraph 是开源的，但 Langsmith 则是一个付费平台。Langsmith 虽然是一个不错的工具，但它并不是构建 AI 工作流程所必需的工具。

### The LangChain Ecosystem LangChain 生态系统

LangChain is not just one library. It has grown into an ecosystem of tools that work together.  
LangChain 不仅仅是一个库而已。它已经发展成为一个由多种工具组成的生态系统，这些工具能够协同工作。

- **LangChain Core**: The main framework for chains, prompts, and memory.  
	LangChain Core：这是用于构建链条、生成提示以及管理记忆的核心框架。
- **LangGraph**: A graph-based extension for building adaptive workflows.  
	LangGraph：一种基于图的扩展方案，用于构建自适应工作流程。
- **LangSmith**: A debugging and monitoring platform for AI apps.  
	LangSmith：一款用于人工智能应用程序的调试和监控平台。
- **LangServe**: A deployment layer that lets you turn your chains and graphs into APIs with one command.  
	LangServe：一个部署层，它让你可以通过一个命令将你的链和图表转换为 API。

Together, these tools form a complete stack for building, managing, and deploying language model applications. You can start with a simple chain, evolve it into a graph-based system, test it with LangSmith, and deploy it using LangServe.  
这些工具共同构成了一个完整的解决方案，可用于构建、管理和部署语言模型应用程序。你可以从一个简单的链条式结构开始，逐步发展成基于图的系统，然后使用 LangSmith 进行测试，最后通过 LangServe 进行部署。

### Conclusion 结论

LangChain and LangGraph make it easier to move from prompts to production-ready AI systems. LangChain helps you build linear flows that connect models, data, and tools. LangGraph lets you go further by building adaptive and intelligent workflows that reason and learn.  
LangChain 和 LangGraph 使得从提示生成可实用的 AI 系统变得更加容易。LangChain 帮助你构建连接模型、数据和工具的线性流程。而 LangGraph 则能让你进一步开发出具有自适应能力的工作流程，这些工作流程能够进行推理和学习。

For beginners, starting with LangChain is the best way to understand how language models can interact with other components. As your projects grow, LangGraph will give you the flexibility to handle complex logic and long-term state.  
对于初学者来说，从 LangChain 入手是理解语言模型如何与其他组件交互的最佳方式。随着你的项目规模越来越大，LangGraph 会为你提供处理复杂逻辑和长期状态的能力。

Whether you are building a chatbot, an agent, or a knowledge assistant, these tools will help you go from idea to implementation faster and more reliably.  
无论你是构建聊天机器人、智能代理还是知识助手，这些工具都能帮助你更快速、更可靠地将想法转化为现实。

*Hope you enjoyed this article. Signup for my free newsletter* [***TuringTalks.ai***](https://www.turingtalks.ai/) *for more hands-on tutorials on AI. You can also* [***visit my website***](https://manishshivanandhan.com/)*.*  
希望您喜欢这篇文章。如果您想获取更多关于人工智能的实际操作教程，可以注册我的免费通讯 TuringTalks.aif，也可以访问我的网站。