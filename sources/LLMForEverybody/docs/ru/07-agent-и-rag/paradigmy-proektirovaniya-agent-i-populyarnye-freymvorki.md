Парадигмы проектирования Agent и популярные фреймворки

## 1. Что такое Agent
Agent — это система, способная воспринимать свое окружение и на основе воспринятой информации принимать решения для достижения конкретной цели. Благодаря поддержке больших моделей Agent стал заметнее, чем когда-либо раньше.

**Суть Agent по-прежнему остается prompt engineering**

## 2. Парадигмы проектирования Agent
"Парадигма Agent" — это разные методы и техники, применяемые в области искусственного интеллекта, особенно при проектировании и разработке интеллектуальных агентов (Autonomous agents, или просто Agents). Интеллектуальный агент — это система, способная воспринимать среду, рассуждать и действовать для выполнения конкретной задачи. В контексте больших языковых моделей (LLMs) парадигма Agent обычно описывает, как использовать эти модели, чтобы усилить способности агента к планированию, принятию решений и выполнению действий.

Единой парадигмы проектирования Agent сейчас нет, но есть несколько распространенных паттернов. Здесь мы рассмотрим несколько парадигм проектирования, упомянутых в статье Эндрю Ына:

- Reflection
- Tool use
- Planning
- Multi-agent collaboration

## 3. Парадигма Agent 1: Reflection

Reflection — это способность Agent рассуждать о собственных действиях и решениях и анализировать их. Такая способность помогает Agent лучше понимать свои действия и решения, а затем эффективнее использовать эту информацию при будущих решениях.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/1.PNG)

Как встроить self-reflection в workflow? Рассмотрим пример NL2SQL:

### Первая интеракция
```python
question = ''
prompt = f'{question}'
plain_query = llm.invoke(prompt)
try:
    df = pd.read_sql(plain_query)
    print(df)
except Exception as e:
    print(e)
```
### reflection

```python
reflection = f"Question: {question}. Query: {plain_query}. Error:{e}, so it cannot answer the question. Write a corrected sqlite query."
```

### Вторая интеракция

```python
reflection_prompt = f'{reflection}'
reflection_query = llm.invoke(reflection_prompt)
try:
    df = pd.read_sql(reflection_query )
    print(df)
except Exception as e:
    print(e)
```

Через reflection мы можем постоянно улучшать наш вопрос, пока не получим нужный ответ.

## 4. Парадигма Agent 2: Tool use

Подобно тому как люди используют инструменты для выполнения задач, Agent тоже может использовать инструменты, чтобы справляться с задачами. Эта парадигма Agent описывает, как Agent использует внешние инструменты и ресурсы, чтобы усилить свои способности к принятию решений и выполнению действий.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/2.PNG)

Например, можно использовать внешний калькулятор или Wikipedia, чтобы решить задачу.

```python
from langchain.agents import load_tools, initialize_agent
from langchain.agents import AgentType
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(temperature=0, model=llm_model)
tools = load_tools(["llm-math","wikipedia"], llm=llm)
agent= initialize_agent(
    tools,
    llm,
    agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    handle_parsing_errors=True,
    verbose = True)

```

## 5. Парадигма Agent 3: Planning

Планирование — ключевой паттерн проектирования Agent AI. Мы используем большие языковые модели, чтобы автономно определять, какие шаги нужно выполнить для решения более крупной задачи. Например, если мы просим Agent провести онлайн-исследование по заданной теме, мы можем использовать LLM, чтобы разбить цель на более мелкие подзадачи: изучить конкретные подтемы, обобщить результаты исследования и написать отчет.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/3.PNG)

## 6. Парадигма Agent 4: Multi-agent collaboration

Multi-agent collaboration — последняя из четырех ключевых парадигм проектирования AI Agent. Для сложных задач вроде написания программного обеспечения Multi-Agent-подход разбивает задачу на подзадачи для разных ролей (например, software engineer, product manager, designer, QA engineer и т. д.) и поручает разным агентам выполнять разные подзадачи.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/4.PNG)

## 7. Другие парадигмы проектирования
Главное различие в других парадигмах проектирования — выделяют ли Memory как отдельный элемент. Вы могли в разных местах встречать схему такого вида:

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/5.png)

Отличие от подхода Эндрю Ына в том, упоминается ли Memory явно. Но это не мешает пониманию, потому что Memory — важная часть Agent.

Memory, в свою очередь, можно разделить на Short-term memory и Long-term memory. Это немного похоже на человеческую систему памяти.
- Short-term memory: использование контекста Context
- Long-term memory: использование внешней базы знаний; типичный пример — технология RAG


## 8. Продвинутые парадигмы проектирования Agent

### 8.1. ReAct
Reasoning and Action — парадигма проектирования, при которой Agent реагирует на изменения в среде. Она описывает, как Agent корректирует свои решения и поведение в зависимости от изменений среды.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/6.png)

### 8.2. Planning & Execute

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/7.png)

### Разница между ними
- ReAct: двигаться шаг за шагом и смотреть, что будет дальше
- Planning & Execute: заранее составить план (конечно, затем его можно итерировать по обратной связи)


***Planning vs. ReAct***

- Planning: Agent автономно решает, какие шаги выполнить для завершения более крупной задачи
- ReAct: Agent реагирует на изменения в среде


## 9. Фреймворки для Multi-Agent collaboration

### 9.1. LangGraph

Agent-фреймворки во главе с LangChain сейчас являются самыми широко используемыми open source-фреймворками в Китае. Изначальная идея дизайна LangChain заключалась в том, чтобы представлять workflow как DAG (directed acyclic graph, направленный ациклический граф); отсюда и произошло Chain.

По мере распространения идеи Multi-Agent и постепенного закрепления парадигмы Agent workflow становится все сложнее: в нем появляются циклы и другие условия. Для этого нужен Graph-подход, и так был разработан LangGraph.

### 9.3. AutoGen
AutoGen проектирует Multi-Agent collaboration с точки зрения организации коммуникации и в основном делит ее на четыре стратегии:
- два agents
- последовательные agents
- Group agents
- Nested agents

### 9.4. two agents
Похоже на совместную работу двух людей над задачей; это самый простой режим сотрудничества.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/8.png)

### 9.5. Последовательные agents
Последовательные Agents означают, что приходит задача, agentA опрашивает других agents и каждый раз приносит с собой вопрос и результаты общения с предыдущими участниками, чтобы в итоге получить решение.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/9.png)

### 9.6. Group agents

Похоже на компанию или команду: приходит задача, она передается manager, manager отвечает за распределение задач между разными agent, получает feedback, рассылает его и выбирает следующего agent.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/10.png)

### 9.7. Nested agents

Nested agents означает, что внутри одного agent есть еще один agent. Это самый сложный режим сотрудничества. В AutoGen Nested agents наружу открывают интерфейс для общения с human, а внутри работает взаимодействие нескольких agent.

![alt text](../../../07-第七章-Agent/assest/Agent设计范式与常见框架/11.png)

## Ссылки

<div id="refer-anchor-1"></div>

[1] [www.deeplearning.ai](https://www.deeplearning.ai/the-batch/how-agents-can-improve-llm-performance/?ref=dl-staging-website.ghost.io)

[2] [autogen](https://github.com/microsoft/autogen)

[3] [2025，Agent生死竞速](https://36kr.com/p/3113897985658368)

## Подписывайтесь на мой GitHub и WeChat Official Account. Некогда объяснять, все на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы. Все полностью open source, буду рад вашим Star и Fork!
