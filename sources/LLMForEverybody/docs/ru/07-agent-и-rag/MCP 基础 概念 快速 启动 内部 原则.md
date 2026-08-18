---
aliases: ["mcp-bazovye-ponyatiya-bystryy-start-i-vnutrennie-principy"]
---

Когда Claude Desktop автоматически оформляет протокол встречи, а плагин Midjourney в реальном времени читает локальный дизайн-макет, вам не любопытно, как эти AI-инструменты выходят из "цифровой клетки" и начинают сотрудничать с человеком?

За этим стоит революционный протокол - Model Context Protocol (MCP). Как "универсальный адаптер" в области AI, MCP перестраивает способ соединения больших моделей с реальным миром.

Статья состоит из трех частей:

Первая часть кратко объясняет базовые понятия MCP.

Вторая часть пошагово показывает путь от "использования готовых инструментов" до "разработки собственного MCP server".

Третья часть через динамические sequence diagrams раскрывает философию протокольного дизайна Anthropic и других ведущих лабораторий, помогая понять стандарт AI-взаимодействия следующего поколения.


## I. Базовые понятия

MCP - это открытый протокол, выпущенный Anthropic в 2024 году. Он предназначен для стандартизации коммуникации между большими языковыми моделями (LLM) и внешними источниками данных/инструментами, чтобы решить проблему традиционного AI, который из-за изолированных данных не может полноценно взаимодействовать с окружением. Он похож на "универсальную вилку" в AI: модель через единый интерфейс безопасно получает доступ к локальным или удаленным ресурсам, например базам данных, API и файловой системе, динамически получает контекст и выполняет операции.

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/1.png)

MCP использует client-server архитектуру и включает следующие ключевые компоненты:

1. MCP Host: например Claude Desktop или Cursor IDE, предоставляет интерфейс взаимодействия с пользователем.
2. MCP Client: встроен в Host и отвечает за разбор протокола и коммуникацию.
3. MCP Server: легковесный сервисный узел, предоставляющий три типа возможностей:
- Resources: статические данные, например файлы и записи БД.
- Tools: исполняемые функции, например API-вызовы и анализ данных.
- Prompts: предопределенные шаблоны взаимодействия.

Примечание: базовые понятия MCP не являются главным фокусом этой статьи. Но для полноты я все же добавил этот раздел. Если хотите подробнее разобраться в основах MCP, рекомендую прочитать две статьи ниже:

https://mp.weixin.qq.com/s/5XbO76qCCYrRVaYjTd3BIA

https://mp.weixin.qq.com/s/G2V5VmsjMWs08rUAE8zCuQ


## II. Как использовать MCP

### 2.0. MCP Server

***Опубликованные MCP server***

Сейчас публично опубликовано очень много MCP server, вокруг них постепенно сформировалось несколько сообществ:

https://mcpmarket.com/

https://smithery.ai/

https://mcp.so/

https://modelscope.cn/mcp

https://actions.zapier.com/mcp

Разработчикам удобно искать полезные MCP services на этих сайтах.

Ниже на примере mcp.so покажем, как подготовить собственный MCP service.

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/2.png)

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/3.png)

Можно увидеть, что конфигурация github server выглядит так:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<YOUR_TOKEN>"
      }
    }
  }
}
```

Здесь фактически задается способ запуска этого github MCP service. Если он нам нужен, достаточно скопировать эту конфигурацию и поместить ее в выбранный Host. Если сейчас непонятно, как это настроить, ничего страшного: в следующих разделах я покажу это пошагово.

***Собственный server***

Мы также можем создать собственный MCP server. Для этой части можно напрямую опираться на официальный пример Anthropic: https://modelcontextprotocol.io/quickstart/server

В этот момент у вас появляется собственный server с такой конфигурацией:

```json
{
    "mcpServers": {
        "weather": {
            "command": "uv",
            "args": [
                "--directory",
                "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather",
                "run",
                "weather.py"
            ]
        }
    }
}
```

Дальше нужно настроить эти server в нашем Host. В этой статье я выбрал Cherry Studio client, фреймворк разработки LangGraph и LLMOps-платформу Dify, чтобы показать, как подключать MCP Server.

### 2.1. Использование MCP Server в Cherry Studio

Как установить Cherry Studio, здесь не обсуждается. После установки можно открыть MCP Servers в настройках и вставить туда конфигурацию из предыдущего раздела.

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/4.png)

### 2.2. Использование MCP Server в LangGraph

Использовать MCP service в LangGraph тоже просто. Согласно официальному примеру https://langchain-ai.github.io/langgraph/agents/mcp/#use-mcp-tools, достаточно скопировать конфигурацию из предыдущего раздела в код.

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

client = MultiServerMCPClient(
    {
        "math": {
            "command": "python",
            # Replace with absolute path to your math_server.py file
            "args": ["/path/to/math_server.py"],
            "transport": "stdio",
        },
        "weather": {
            # Ensure your start your weather server on port 8000
            "url": "http://localhost:8000/mcp",
            "transport": "streamable_http",
        }
    }
)
## 在上面的方法里拷贝上文中的配置

tools = await client.get_tools()
agent = create_react_agent(
    "anthropic:claude-3-7-sonnet-latest",
    tools
)
math_response = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "what's (3 + 5) x 12?"}]}
)
weather_response = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "what is the weather in nyc?"}]}
)
```

### 2.3. Использование MCP Server в Dify

В Dify пока поддерживаются только SSE MCP services. Сначала убедитесь, что версия Dify выше 1.2.0. В plugin marketplace найдите `mcp`, выберите Agent strategy (Support MCP Tool) и установите. Примечание: другие плагины тоже можно попробовать самостоятельно.

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/5.png)

В Agent выберите ReAct (Support MCP Tool), а в конфигурации MCP service вставьте конфигурацию из предыдущего раздела.

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/6.png)

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/7.png)

## III. Как работает MCP

Чтобы понять, что именно делает MCP, можно посмотреть на sequence diagrams: отдельно для регистрации server и для пользовательского вызова.

### 3.1. Sequence diagram регистрации server

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/8.png)

Номера шагов ниже соответствуют sequence diagram.

На примере Cherry Studio: когда мы регистрируем написанный нами `calculator` MCP service, до успешной регистрации server и client уже успевают обменяться несколькими сообщениями.

1. Сначала Client запускает MCP server. Наш MCP service использует stdio, поэтому на этом шаге Cherry Studio фактически выполняет такую команду:

```bash
uv run calculator.py
```

2. Client передает server информацию: я такой-то client.

```bash
{"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"Cline","version":"3.12.3"}},"jsonrpc":"2.0","id":0}
```

3. Server отвечает: я calculator service.

```bash
{"jsonrpc":"2.0","id":0,"result":{"protocolVersion":"2024-11-05","capabilities":{"experimental":{},"prompts":{"listChanged":false},"resources":{"subscribe":false,"listChanged":false},"tools":{"listChanged":false}},"serverInfo":{"name":"CalculatorService","version":"1.8.1"}}}
```

4. Client инициализирует service, а затем спрашивает server, какие tools доступны.

```bash
{"method":"notifications/initialized","jsonrpc":"2.0"}
{"method":"tools/list","jsonrpc":"2.0","id":1}
```

5. Service отвечает информацией о tools: включая описание tools, входные и выходные параметры.

```bash
{
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
                "tools": [{
                        "name": "add",
                        "description": "执行浮点数加法运算",
                        "inputSchema": {
                                "properties": {
                                        "a": {
                                                "title": "A",
                                                "type": "number"
                                        },
                                        "b": {
                                                "title": "B",
                                                "type": "number"
                                        }
                                },
                                "required": ["a", "b"],
                                "title": "addArguments",
                                "type": "object"
                        }
                },
                {
                        "name": "subtract",
                        "description": "执行浮点数减法运算",
                        "inputSchema": {
                                "properties": {
                                        "a": {
                                                "title": "A",
                                                "type": "number"
                                        },
                                        "b": {
                                                "title": "B",
                                                "type": "number"
                                        }
                                },
                                "required": ["a", "b"],
                                "title": "subtractArguments",
                                "type": "object"
                        }
                },
                {
                        "name": "multiply",
                        "description": "执行浮点数乘法运算",
                        "inputSchema": {
                                "properties": {
                                        "a": {
                                                "title": "A",
                                                "type": "number"
                                        },
                                        "b": {
                                                "title": "B",
                                                "type": "number"
                                        }
                                },
                                "required": ["a", "b"],
                                "title": "multiplyArguments",
                                "type": "object"
                        }
                },
                {
                        "name": "divide",
                        "description": "执行浮点数除法运算\n    Args:\n        b: 除数（必须非零）\n    ",
                        "inputSchema": {
                                "properties": {
                                        "a": {
                                                "title": "A",
                                                "type": "number"
                                        },
                                        "b": {
                                                "title": "B",
                                                "type": "number"
                                        }
                                },
                                "required": ["a", "b"],
                                "title": "divideArguments",
                                "type": "object"
                        }
                },
                {
                        "name": "power",
                        "description": "计算幂运算",
                        "inputSchema": {
                                "properties": {
                                        "base": {
                                                "title": "Base",
                                                "type": "number"
                                        },
                                        "exponent": {
                                                "title": "Exponent",
                                                "type": "number"
                                        }
                                },
                                "required": ["base", "exponent"],
                                "title": "powerArguments",
                                "type": "object"
                        }
                },
                {
                        "name": "sqrt",
                        "description": "计算平方根",
                        "inputSchema": {
                                "properties": {
                                        "number": {
                                                "title": "Number",
                                                "type": "number"
                                        }
                                },
                                "required": ["number"],
                                "title": "sqrtArguments",
                                "type": "object"
                        }
                },
                {
                        "name": "factorial",
                        "description": "计算整数阶乘",
                        "inputSchema": {
                                "properties": {
                                        "n": {
                                                "title": "N",
                                                "type": "integer"
                                        }
                                },
                                "required": ["n"],
                                "title": "factorialArguments",
                                "type": "object"
                        }
                }]
        }
}
```

На этом регистрация server завершена.


### 3.2. Sequence diagram пользовательского вызова

![alt text](../../../07-第七章-Agent/assest/MCP：基础概念、快速应用和背后原理/9.png)

Номера шагов ниже соответствуют sequence diagram.

1. Пользователь отправляет запрос в Host, например вычислить `1+1`: в Cherry Studio вводит `1+1` и нажимает Enter.

2. Cherry Studio передает этот запрос вместе с информацией о настроенном MCP server в LLM в форме prompt/function call. В этом prompt заранее оговорен формат, который нужно использовать, если потребуется вызвать MCP server.

3. После рассуждения большая модель понимает, что нужно вызвать tool `add` у calculator MCP server, и согласно договоренности возвращает метод вызова в MCP-формате. Здесь ответ выглядит так:

```bash
{"method":"tools/call","params":{"name":"add","arguments":{"a":1.0,"b":1.0}},"jsonrpc":"2.0","id":4}
```

4. Client пересылает запрос и вызывает server.

5. Server возвращает результат.

```bash
{"jsonrpc":"2.0","id":4,"result":{"content":[{"type":"text","text":"2.0"}],"isError":false}}
```

6. Client пересылает результат LLM, вместе с историческим контекстом.

7. Большая модель получает результат и делает итоговое резюме, возвращая final answer client.

8. Client получает результат и отправляет его пользователю.

### 3.3. Model Context Protocol

Для термина Model Context Protocol важно помнить: этот протокол регламентирует только протокол взаимодействия между Client и Server, но не регламентирует, как Client взаимодействует с LLM. Разные clients реализуют это по-своему.

Для большой модели контекст - это среда. Контекст модели означает, в какой среде находится модель, то есть какие tools она может получить.

По сути MCP - это протокол, который позволяет модели воспринимать внешнюю среду.


## Ссылки

<div id="refer-anchor-1"></div>

[1]https://mp.weixin.qq.com/s/5XbO76qCCYrRVaYjTd3BIA

https://mp.weixin.qq.com/s/G2V5VmsjMWs08rUAE8zCuQ

https://mcpmarket.com/

https://smithery.ai/

https://mcp.so/

https://modelscope.cn/mcp

https://actions.zapier.com/mcp

https://modelcontextprotocol.io/quickstart/server

https://langchain-ai.github.io/langgraph/agents/mcp/#use-mcp-tools

https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/?utm_campaign=anthropicC2-launch&utm_medium=headband&utm_source=deeplearning-ai


---

## 📚 相关概念

[[concepts/RAG 检索 增强 生成|RAG 检索 增强 生成]] | [[concepts/向量 DB 嵌入|向量 DB 嵌入]] | [[concepts/混合 检索 bm 25 语义 融合|混合 检索 bm 25 语义 融合]] | [[concepts/智能体 编排 模式|智能体 编排 模式]] | [[concepts/智能体 编程|智能体 编程]] | [[concepts/智能体 工具 使用 MCP|智能体 工具 使用 MCP]] | [[concepts/智能体 长 期 内存|智能体 长 期 内存]] | [[concepts/多 智能体 协作|多 智能体 协作]] | [[concepts/LLM 智能体 测试框架|LLM 智能体 测试框架]] | [[concepts/浏览器 智能体|浏览器 智能体]] | [[concepts/轻量 智能体 框架|轻量 智能体 框架]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/LangChain|LangChain]] | [[entities/CrewAI|CrewAI]] | [[entities/Anthropic|Anthropic]] | [[entities/OpenAI|OpenAI]] | [[entities/Google ADK|Google ADK]] | [[sources/Anthropic 智能体 构建|Anthropic 智能体 构建]] | [[sources/LangChain 入门|LangChain 入门]] | [[sources/MCP 规范|MCP 规范]] | [[sources/智能体 框架 对比|智能体 框架 对比]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：Agent
