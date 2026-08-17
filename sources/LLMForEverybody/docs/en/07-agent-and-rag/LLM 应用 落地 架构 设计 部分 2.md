---
aliases: ["llm-application-adoption-architecture-design-part-2"]
---

# LLM Application Adoption: Architecture Design, Part 2

## 1. Probability of task failure

### 1.1 Common sources of errors

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/11.png>)

### 1.2 Three capabilities of LLM applications

The three most important capabilities of an LLM application are architecture, knowledge, and model.

- Architecture
  - Task decomposition: the model completes one small task at a time. Why does CoT work? The reason is that large models have not seen data where a complex task is completed in one whole step, and they were not pre-trained on such data. But they have seen data where complex tasks are broken into small subtasks, and that is exactly what they are good at. Task decomposition is basically manual CoT.
  - Retrieval augmentation: make sure the retrieved knowledge is complete enough and as accurate as possible.
- Knowledge
  - Knowledge engineering: building knowledge in different ways, including knowledge for sparse retrieval such as BM25, knowledge for dense retrieval through semantic vector search, and knowledge graph construction. The best result can only come from hybrid retrieval across knowledge in different formats.
- Model
  - Use a better base model whenever possible.
  - Continue training the model, inject vertical-domain knowledge, and fine-tune for the specific task format.
  - Optimize the prompt.

## 2. Architecture approach for LLM applications

LLM application architecture mainly handles task decomposition and retrieval augmentation.

### 2.1 Architecture diagram

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/12.png>)

### 2.2 Task decomposition

For task decomposition, several Agents are usually separated.

- At the input side, there is usually an Agent for intent recognition
  - It clarifies ambiguity or missing information in the user's question.
  - It obtains relevant information through retrieval to help determine intent.
  - It routes the specific task to a specific Agent.

- Downstream Agents focus more on concrete tasks
  - They perform clarification at the task level.
  - They retrieve information related to task execution.
  - They perform further task decomposition. At this stage, each task may simply be a function or tool. If it becomes very complex, it may also be another Agent.

## 3. Knowledge engineering for LLM applications

Start from the original structural form of the data.

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/13.png>)

### 3.3 Structured data

- For data without semantic information, you can:
  - Build MinHash LSH.
  - Build a knowledge graph.
- For data with semantic information, you can additionally build a vector database.

### 3.4 Unstructured data

- Build an inverted index to support methods such as BM25.
- Build a vector database for semantic similarity vectors.
- Use an LLM for information extraction, convert the data into a structured format, then apply knowledge engineering for structured data.

## 4. Model optimization for LLM applications

### 4.1 Prompt optimization

- The prompt should be clear and specific, without built-in ambiguity.
- Use a structured prompt.
- For tasks where reasoning improves quality, use CoT.
- When maximum performance is needed, use Self Consistency.

### 4.2 Model fine-tuning

- If you need to inject knowledge into the model, you still need CT (`continued training`). SFT (`supervised fine-tuning`) still has trouble injecting knowledge.
- For some specific small tasks, SFT on smaller models works well. For certain tasks, you can even use a smaller BERT.

## 5. Iterative optimization process for LLM applications

### 5.1 Evaluation metrics

![alt text](<../../../07-第七章-Agent/assest/LLM应用落地指南/14.png>)

- For generative tasks with feedback: mainly Text-to-SQL and Text-to-Code. We can write reference SQL or unit tests to check task accuracy.
- For generative tasks without feedback: we can only use a large model for evaluation. Some people may think this makes the large model both player and judge. But first, we can improve the model's evaluation ability through fine-tuning, and second, changing the Prompt also changes the model capability bias, so this method is still usable. Of course, it has unavoidable limits. In that case, fine-tuning can be tried (see 4.2).

### 5.2 Experiment records

As in traditional machine learning and deep learning, each experiment run in an LLM application should be recorded. MLflow is a very good tool: it helps record Prompt, Temperature, Top P, and other parameters, as well as experiment run results. Below is a screenshot of several runs of one experiment in MLflow: each run's parameters and tracked metrics are clearly visible in the overview, and the test data and Prompt for each run are also recorded on the details page.

Note: aside from several redrawn diagrams, the content of this article is mostly copied from the Thoughtworks WeChat article listed as source 1.

## References

[1] [LLM应用落地实施手册](https://mp.weixin.qq.com/s/t-uYwd9NOxJIAIMAYWEqhg)
