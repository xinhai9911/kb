# A Long Guide to Prompt Engineering: Unlocking the Power of LLMs

You know that a periodic function, if it satisfies the Dirichlet conditions, can be perfectly represented by a Fourier series.

You know that before observation, an atom is in a superposition of decayed and undecayed states, which means Schrödinger's cat is also in a superposition of alive and dead until someone opens the box and observes it.

You know that "understanding the structure of the world is knowledge, while understanding people is already literature."

You know how to safely lead an 800-kilogram cow across a bridge rated for 700 kilograms.

You know that Natsume Soseki translated "I Love You" as "The moon is beautiful tonight."

But in front of the person you like, you do not know where to start. Every time you open the chat, all you can come up with is a plain: "Are you there?"

## 1. Introduction

**A phenomenal product**

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/1.PNG>)

**An extremely simple UI**

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/2.PNG>)

## 2. Basic concepts

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/3.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/4.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/5.png>)

### Prompt Engineering == how to communicate effectively (human-machine)

Prompt Engineering is the art and science of optimizing prompts to get effective results. It includes designing, writing, and changing prompts to guide an AI model toward high-quality, relevant, and useful answers.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/6.png>)

### Why Prompt Engineering matters

Prompt Engineering is critical for using AI models effectively because it can:

- improve the quality and relevance of model output
- reduce the chance that the model generates harmful or inappropriate answers
- tune model output for specific needs
- unlock the model's full potential

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/7.png>)

### Components of prompts

System message (`Instruction`): defines the role of the LLM

Human message (`Question`): each user request

History message: conversation history

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/8.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/9.png>)

### Personal settings

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/10.png>)

#### Temperature

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/11.png>)

#### Top-p

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/12.png>)

#### Maximum number of messages in context

Memory/History

#### Maximum number of tokens in context: Token

- OpenAI cost estimate: [Open AI Pricing](https://openai.com/api/pricing/)

- prompt and completion are both billed: [token and cost calculator](https://gpt-tokenizer.dev/)

- Usually, 1000 tokens are roughly equal to 750 English words or 400-500 Chinese characters: [How ChatGPT counts tokens](https://www.zhihu.com/question/594159910/answer/2996337752)

#### Maximum number of tokens in the generated answer

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/13.png>)

## 3. Prompt Engineering practice[<sup>1</sup>](#refer-anchor-1)

### 1. Write clear instructions

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/19.jpg>)

The model cannot read your mind.

If the output feels too long, ask it to be brief. If the output is too simple, ask for expert-level writing. If you do not like the format, show the format you want. The less the model has to guess what you want, the more likely you are to get the answer you need.

P.S.:

If you want your husband to buy you a bag, tell him you want a bag, instead of saying: "Guess what my friend's husband bought her?"

If you want your wife to buy you a game console... uh, then sorry, just keep dreaming...

#### 1.1 Add details to the request to get more relevant answers

To get a highly relevant answer, make sure you provide "important and detailed information." Do not make the model guess what you mean.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/20.png>)

#### 1.2 Ask the model to take a specific role

The system message can be used to define the role the model should use in its answers.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/21.png>)

#### 1.3 Use delimiters to clearly mark different parts of the input

Triple quotes, XML tags, section titles, and other delimiters help separate fragments that should be handled differently.

**Translation task**

> Language models can confidently invent fake answers, especially when asked about esoteric topics or for citations and URLs. In the same way that a sheet of notes can help a student do better on a test, providing reference text to these models can help in answering with fewer fabrications.

**Google Translate**

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/22.png>)

> Result: language models can confidently invent false answers, especially when asked about esoteric topics, citations, and URLs. In the same way that a sheet of notes can help a student do better on a test, providing reference text to these models can help ***reduce the number of answers***.

***LLM***

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/23.png>)

> prompts: Translate the following text into Chinese, use professional terminology, and make the text natural for Chinese readers, ''' Language models can confidently invent fake answers, especially when asked about esoteric topics or for citations and URLs. In the same way that a sheet of notes can help a student do better on a test, providing reference text to these models can help in answering with fewer fabrications.'''

> completions: Language models can confidently invent false answers, especially when asked about difficult topics, citations, and URLs. Just as notes help a student do better on an exam, providing reference text to such models helps ***reduce fabricated answers***.

#### 1.4 Specify the steps needed to complete the task

Some tasks are better described as a sequence of steps. If you write these steps explicitly, it becomes easier for the model to follow them.

When writing a scientific paper, you usually need to write an English abstract. How can you make AIGC generate an English abstract?

> System: Use the following step-by-step instructions to answer the user's input.
              Step 1 - the user will provide you with text in triple quotes. Summarize this text in one sentence and add the prefix "Summary:".
              Step 2 - translate the summary from step 1 into English and add the prefix "Translation:".
User: ''' I have worked for eight or nine years, supervised seven or eight groups of master's students, and also graduated three groups of doctoral students.
I have seen all kinds of students: tearful young women, talented people who drift with the current, very driven people, and people who still do not move even if you push them with a stick...
To summarize it in one sentence: good results come from students who know how to "cry" and actively look for "milk."
"Cry" is not an insult here. A baby cries because it is hungry, and therefore has motivation to search.
It is the same with graduate students: they understand their shortcomings, and they have the desire and motivation to fill them. On one hand, they actively make up knowledge themselves, reading literature and talking on forums. On the other hand, they go to their supervisor to discuss the work, get advice, and grow through it.'''

>AI: Summary: The text describes various types of students the author has encountered over the years, pointing out that students who are willing to seek help proactively tend to achieve good results.

>Translation: Summary: The text describes various types of students the author has encountered over the years, pointing out that students who are willing to seek help proactively tend to achieve good results.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/24.png>)

#### 1.5 Provide examples

Instructions are usually more effective than examples, but in some cases it is easier to give an example. For instance, when you want the model to reproduce a certain style that is hard to describe explicitly while answering the user's request. This is called a prompt with a small number of examples, or Few-shot learning.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/25.png>)

#### 1.6 Specify the desired output length

Ask the model to generate output with a target length. The target length can be specified by number of words, sentences, paragraphs, bullet points, and so on.

- Roughly

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/26.png>)

- No more than

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/27.png>)

- Two sentences

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/28.png>)

### 2. Provide reference text

Language models can confidently invent false answers, especially when asked about difficult topics, citations, and URLs (the large model hallucination problem). Just as a cheat sheet helps a student do better on an exam, providing reference text to such models helps reduce fabricated answers.

#### 2.1 Ask the model to answer using reference text

Prompts-System: Use the article enclosed in triple quotes to answer the question. If the answer cannot be found in the article, write "I cannot find the answer."

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/29.png>)

- case1

>'''I have worked for eight or nine years, supervised seven or eight groups of master's students, and also graduated three groups of doctoral students.
I have seen all kinds of students: tearful young women, talented people who drift with the current, very driven people, and people who still do not move even if you push them with a stick...
To summarize it in one sentence: good results come from students who know how to "cry" and actively look for "milk."
"Cry" is not an insult here. A baby cries because it is hungry, and therefore has motivation to search.
It is the same with graduate students: they understand their shortcomings, and they have the desire and motivation to fill them. On one hand, they actively make up knowledge themselves, reading literature and talking on forums. On the other hand, they go to their supervisor to discuss the work, get advice, and grow through it.
For example, here are three students I worked with:
Postdoc Hu was very diligent and hardworking. At that time, her topic had hit a dead end and the direction was unclear. Six months before finishing her postdoc, she asked everyone for help at a group seminar. I had just started the job and said she could try a certain direction. She tried it, and less than half a year passed from my suggestion to publication in Cancer Letters, after which she successfully completed her postdoc. Later, NSFC grants and the rest came naturally.
PhD student B, a student of the big boss whom I supervised, was very proactive. His topic was related to my NSFC youth grant, so we explored it together a lot. On that basis, he more actively looked for his own direction, later also received an NSFC grant, and became an independent specialist at his new workplace.
PhD student H was also very proactive. At that time, I gave her a new gene, and everything had to start from scratch. This was actually very difficult, because some results contradicted common sense and some contradicted each other. She was a very strict researcher, so she decided there was no way forward and came to me. She put forward her views and questions, while I had to explain possible reasons, encourage her, and study hard myself to answer some of her questions. This communication lasted 3-4 years. In her words, we "argued" for three years. In those arguments, we brought this gene back to life, expanded a new research field, and proposed a new theory. Although she graduated because of work without finishing this topic, she played a major role in the study of this gene.
The counterexample seems to be me. When I was doing my master's, I barely communicated with my supervisor: I just did experiments with enthusiasm. If the expected result did not appear, I repeated them again and again, so in the end I did not really produce much. At the defense, my supervisor said his impression of me was: "you have a lot of energy."
So if a doctoral or master's student wants to achieve something, initiative is unavoidable.
Knowing how to "cry" means knowing your needs and shortcomings, being proactive, having inner motivation that pushes you forward, and actively looking for external advice and help to maximize work efficiency. Supervisors like such students too.
A supervisor's advantage is that they already have a relatively complete knowledge structure and can see the big picture well. But it is harder for them to keep every detail in mind: they do not have that much energy and time, and their thinking can inevitably get stuck in familiar frames. This is exactly why students need unusual, bold, even rebellious ideas to shake the supervisor up. Only then does learning become mutual and the results get better.
If a student actively comes to the supervisor to "cry", the supervisor will only be happy. If a student almost never comes, and even when the supervisor looks for them they have nothing to say, and they need to be pushed and forced to explore, then after a few rounds the supervisor also gives up: such a student is impossible to supervise.
So, whether you are a master's student or a doctoral student, be the student who knows how to "cry."'''

>Question: Which kind of master's or doctoral student will grow?

>Completion: The master's or doctoral student who will grow is the one who knows how to "cry" and actively look for "milk." Such a student not only knows their needs and shortcomings, but can also actively seek external advice and help, has inner motivation, and can push themselves forward. They actively fill knowledge gaps in different ways, communicate with the supervisor, keep exploring and developing, and therefore improve work efficiency and get better results. Such students can awaken a supervisor's interest and potential, support mutual growth, and get better research results.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/30.png>)

- case2

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/31.png>)

### 2.2 Ask the model to answer with citations from the reference text

Prompt-system: Use the article enclosed in triple quotes to answer the question. If the answer cannot be found in the article, write "I cannot find the answer." If the answer is provided, it must include citations. Use the following format to cite relevant paragraphs ({"quote": ...}).

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/32.png>)

- case3

> '''I have worked for eight or nine years, supervised seven or eight groups of master's students, and also graduated three groups of doctoral students.
I have seen all kinds of students: tearful young women, talented people who drift with the current, very driven people, and people who still do not move even if you push them with a stick...
To summarize it in one sentence: good results come from students who know how to "cry" and actively look for "milk."
"Cry" is not an insult here. A baby cries because it is hungry, and therefore has motivation to search.
It is the same with graduate students: they understand their shortcomings, and they have the desire and motivation to fill them. On one hand, they actively make up knowledge themselves, reading literature and talking on forums. On the other hand, they go to their supervisor to discuss the work, get advice, and grow through it.
For example, here are three students I worked with:
Postdoc Hu was very diligent and hardworking. At that time, her topic had hit a dead end and the direction was unclear. Six months before finishing her postdoc, she asked everyone for help at a group seminar. I had just started the job and said she could try a certain direction. She tried it, and less than half a year passed from my suggestion to publication in Cancer Letters, after which she successfully completed her postdoc. Later, NSFC grants and the rest came naturally.
PhD student B, a student of the big boss whom I supervised, was very proactive. His topic was related to my NSFC youth grant, so we explored it together a lot. On that basis, he more actively looked for his own direction, later also received an NSFC grant, and became an independent specialist at his new workplace.
PhD student H was also very proactive. At that time, I gave her a new gene, and everything had to start from scratch. This was actually very difficult, because some results contradicted common sense and some contradicted each other. She was a very strict researcher, so she decided there was no way forward and came to me. She put forward her views and questions, while I had to explain possible reasons, encourage her, and study hard myself to answer some of her questions. This communication lasted 3-4 years. In her words, we "argued" for three years. In those arguments, we brought this gene back to life, expanded a new research field, and proposed a new theory. Although she graduated because of work without finishing this topic, she played a major role in the study of this gene.
The counterexample seems to be me. When I was doing my master's, I barely communicated with my supervisor: I just did experiments with enthusiasm. If the expected result did not appear, I repeated them again and again, so in the end I did not really produce much. At the defense, my supervisor said his impression of me was: "you have a lot of energy."
So if a doctoral or master's student wants to achieve something, initiative is unavoidable.
Knowing how to "cry" means knowing your needs and shortcomings, being proactive, having inner motivation that pushes you forward, and actively looking for external advice and help to maximize work efficiency. Supervisors like such students too.
A supervisor's advantage is that they already have a relatively complete knowledge structure and can see the big picture well. But it is harder for them to keep every detail in mind: they do not have that much energy and time, and their thinking can inevitably get stuck in familiar frames. This is exactly why students need unusual, bold, even rebellious ideas to shake the supervisor up. Only then does learning become mutual and the results get better.
If a student actively comes to the supervisor to "cry", the supervisor will only be happy. If a student almost never comes, and even when the supervisor looks for them they have nothing to say, and they need to be pushed and forced to explore, then after a few rounds the supervisor also gives up: such a student is impossible to supervise.
So, whether you are a master's student or a doctoral student, be the student who knows how to "cry."'''

>Question: Which kind of master's or doctoral student will grow??

>Completion:
According to the provided article, the master's or doctoral student who will grow is the one who knows how to "cry" and actively look for "milk." Such a student actively seeks external advice and help, knows their needs and shortcomings, and has inner motivation to move forward. They communicate with the supervisor, seek mentoring, and try to fill their gaps to improve work efficiency and get better results. Overall, initiative and willingness to ask for help are key factors in the growth of a master's or doctoral student.
{"quote": '''To summarize it in one sentence: good results come from students who know how to "cry" and actively look for "milk."''', '''If a student actively comes to the supervisor to "cry", the supervisor will only be happy. If a student almost never comes, and even when the supervisor looks for them they have nothing to say, and they need to be pushed and forced to explore, then after a few rounds the supervisor also gives up: such a student is impossible to supervise.''', '''So, whether you are a master's student or a doctoral student, be the student who knows how to "cry."'''}

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/33.png>)

### 3. Split complex tasks into simpler subtasks

Just as decomposing a complex system into modular components is good practice in software engineering, the same applies to tasks passed to a language model. Complex tasks usually have a higher error rate than simple ones. Also, complex tasks can often be redefined as a workflow made from simpler tasks, where the output of earlier tasks is used to build the input of later tasks.

[Basic application frameworks for large models (ReACT\SFT\RAG), innovation, and adoption in retail business](https://www.infoq.cn/article/bixpxZtgIvpMGWWKlI77)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/34.png>)

#### 3.1 Use intent classification to decide which instructions are most relevant to the user's request

For tasks that need many independent instruction sets for different situations, it can be useful to first classify the request type, then use that classification to decide which instructions are needed.

Product and engineering folks, Attention!!! Next you will see two different QA groups, and in the end we will combine them into a finite-state machine.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/35.png>)

Based on the classification of a customer request, we can provide the model with a more specific instruction set for the next steps. For example, suppose the customer needs help with "troubleshooting."

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/36.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/37.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/38.png>)

Attention! Notice that the model was told to output a special string when the dialogue state changes. This lets us turn the system into a finite-state machine, where the state determines which instructions should be injected.

Think about it: if you needed to design an intelligent customer support product, how would you do it? If you needed to develop an intelligent support service, what ideas would you have?

#### 3.2 For long conversational applications, summarize or filter previous dialogue fragments

Because a model has a fixed context length, a dialogue between user and assistant where the whole conversation is kept in the context window cannot continue forever.

There are several ways to solve this. One is to summarize previous turns. When the input size reaches a predefined threshold, it can trigger a request to summarize part of the conversation, and the previous conversation summary can be included as part of the system message. Or previous dialogue fragments can be summarized asynchronously in the background throughout the conversation.

Another solution is to dynamically select the previous parts of the conversation most relevant to the current request.

#### 3.3 Summarize long documents and recursively build a full summary

Because a model has a fixed context length, it cannot summarize very long texts all at once.

To summarize a very long document, such as a book, you can use a series of requests, each summarizing one section of the document. Chapter summaries can then be combined and summarized again, producing a summary of summaries. This process can be repeated recursively until the whole document is summarized.

### 4. Give the model time to "think"

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/39.png>)

If someone asks you to multiply 13 by 19, you may not answer instantly, but if given a little time, you can do it.

Similarly, a model is more likely to make reasoning errors when it tries to answer immediately instead of spending time searching for the answer.

Asking for a CoT "chain of thought" before the final answer can help the model derive the correct answer more reliably.

**Let's look at a homework-help example**

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/40.png>)

#### 4.1 Ask the model to find its own solution before rushing to a conclusion

Sometimes the result is better when we explicitly ask the model to reason from first principles before drawing a conclusion.

Suppose we want the model to evaluate a student's solution to a math problem.

The most obvious way is simply to ask the model whether the student's solution is correct. But will we really get the right answer?

***Incorrect example***

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/41.png>)

***Correct example***

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/42.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/43.png>)

#### 4.2 Use inner monologue or a series of requests to hide the model's reasoning process

The previous strategy shows that sometimes it is important for the model to reason carefully about a question before answering.

For some applications, the reasoning process by which the model reaches the final answer should not be shown to the user.

For example, in an educational app, we may want to encourage the student to reach the answer independently, but the model's reasoning about the student's solution might reveal the answer to the student.

Inner monologue is a strategy that helps soften this problem. The idea is to instruct the model to put parts of the output that should be hidden from the user into a structured format that is easy to parse. Then, before showing the output to the user, the output is parsed and only the visible part remains.

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/44.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/45.png>)

#### 4.3 Ask the model whether it missed anything earlier

Suppose we use a model to list source fragments relevant to a specific question. After each fragment, the model must decide whether to start writing the next fragment or stop. If the source document is large, the model often stops too early and does not list all relevant fragments. In that case, quality can usually be improved with a follow-up request asking the model to find fragments missed in the previous pass.

### 5. Use external tools

Compensate for the model's weaknesses by giving it the output of other tools. For example, a text search system, sometimes called RAG (`retrieval-augmented generation`), can tell the model which documents are relevant. A code execution engine, such as OpenAI Code Interpreter, can help the model perform math calculations and run code.

#### 5.1 Use embedding-based search to retrieve knowledge efficiently

**Embedding**

If external sources of information are provided as part of the input, the model can use them. This helps the model generate more meaningful and up-to-date answers. For example, if a user asks about a specific movie, it is useful to add high-quality information about that movie to the model input: actors, director, and so on. Embeddings can be used for efficient knowledge retrieval, dynamically adding relevant information to the model input at runtime.

Text Embedding is a vector that can measure relevance between text strings. Similar or related strings are closer to each other than unrelated ones. This fact, together with fast vector search algorithms, means Embedding can be used for efficient knowledge retrieval.

#### 5.2 Use code execution for more accurate calculations or external API calls

Do not rely on a language model to perform arithmetic or long calculations accurately by itself.

When needed, you can ask the model to write and run code instead of doing the calculation itself.

P.S. a demo of tool use is available through the GitHub link at the end of the article.

## Advanced prompt: ReAct demo

Combining reasoning and action in LLMs

How do humans solve complex tasks? Q-T-A-O

- Question

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/46.png>)

- Thought

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/47.png>)

- Action

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/48.png>)

- Observation

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/49.png>)

- Again

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/50.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/51.png>)

***How do we run ReAct? Prompts!***

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/52.png>)

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/53.png>)

## Demo: Talk is Cheap, Show Me the Code:

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/54.png>)

Here is a small demo of tool use and ReAct:

>https://github.com/luhengshiwo/LLMForEverybody/blob/main/ReAct/PromptEngineeringReAct.ipynb

## Summary

I hope everyone can improve how efficiently they communicate with LLMs and make more money!

**Before:**

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/55.png>)

**After:**

![alt text](<../../../06-第六章-Prompt Engineering/assest/万字长文 Prompt Engineering-解锁大模型的力量/56.png>)

## References

<div id="refer-anchor-1"></div>

[1] [openai prompt engineering guides](https://platform.openai.com/docs/guides/prompt-engineering/strategy-write-clear-instructions)

[2] [generative-ai-with-llms](https://www.deeplearning.ai/courses/generative-ai-with-llms/)

[3] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)
