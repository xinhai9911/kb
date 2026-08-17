# GraphRAG: Unlocking LLM Retrieval Over Narrative Private Data

https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/

## At the beginning

Some time ago, Microsoft's open source GraphRAG caused a noticeable stir. I read many materials, and the most valuable one was probably Microsoft's own blog: https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/

The material is detailed, so I tried translating it into Chinese, hoping it helps more people who need this information.

Because the translator's level is limited, mistakes are inevitable. Please be understanding. If you notice a problem, please point it out in the comments and I will try to fix it as soon as possible.

Narrative Private Data in the title is translated here as narrative private data. If there is a better option, suggestions are welcome.

Reading note: the dataset used in the article contains sensitive topics. The translator only translates the text. The translation does not reflect the translator's position.

## Main text starts:

Perhaps the greatest challenge for LLMs, and also the greatest opportunity, is to extend their powerful capabilities to tasks outside their training data and get comparable results on data the LLMs have never seen. This opens new possibilities for data discovery, such as identifying themes and semantic concepts based on context and dataset. In this article, we introduce GraphRAG, created by Microsoft Research, as an important step forward in strengthening LLM capabilities.

Retrieval-Augmented Generation (`RAG`) is a technique that searches for information based on a user query and provides the results as support for a generative AI answer. This technique is an important part of most LLM-based tools, and most RAG approaches use vector similarity as the retrieval technique. GraphRAG uses an LLM-generated knowledge graph and substantially improves Q&A quality when analyzing documents with complex information. This builds on our recent [research](https://www.microsoft.com/en-us/research/publication/can-generalist-foundation-models-outcompete-special-purpose-tuning-case-study-in-medicine/), where the power of prompt augmentation was noted for discovery on private datasets. Here we define a private dataset as data that the LLM was not trained on and has never seen, such as a company's internal research, business documents, or communications. Baseline RAG was created to help solve this problem, but we observed cases where Baseline RAG performs very poorly. For example:

- Baseline RAG has trouble connecting individual dots. This happens when answering a question requires moving across different pieces of information through shared attributes to synthesize a new understanding.
- Baseline RAG performs poorly when asked to comprehensively understand summary semantic concepts in a large dataset, or even in one large document.

To solve this problem, the technical community is actively developing ways to extend and strengthen RAG, such as [LlamaIndex](https://www.llamaindex.ai/). Microsoft Research's new approach, GraphRAG, uses an LLM to create a knowledge graph from a private dataset. Then this graph is used together with graph machine learning to perform prompt augmentation at query time. GraphRAG shows clear progress on both types of questions described above and demonstrates a higher level of intelligence or command of the material than other methods previously applied to private datasets.

## Applying RAG to a private dataset

To show the effectiveness of GraphRAG, let's first use the [Violence Information from News Articles (VIINA)](https://github.com/zhukovyuri/VIINA) dataset. This dataset was chosen because of its complexity, multiple points of view, and incomplete information. It is a messy real-world test case, and the time period is recent enough that it was not included in the training of base LLMs.

In this study, we used thousands of news articles from Russian and Ukrainian sources from June 2023, translated into English, to create a private dataset for LLM-based retrieval. The dataset is too large to fit into the LLM context window, so a RAG approach is needed.

We start with an exploratory query, asked to a baseline RAG system and to our new GraphRAG approach:

Query: "What is Novorossiya?" This part is not translated.

|Baseline RAG|GraphRAG|
| :--- |:--- |
|The term "Novorossiya" is not mentioned in the provided context. However, to provide some information, Novorossiya, or New Russia, is a historical term referring to a region in the south of Ukraine that was conquered by the Russian Empire in the 18th century. In recent years, the term has been revived by Russian-backed separatists in Eastern Ukraine to refer to the territories they claim, but it is not officially recognized as a separate entity by international bodies. |<ol><li>Novorossiya, also known as New Russia, is a term with historical and contemporary significance. Historically, it referred to a region in the southern part of the Russian Empire that is now part of Ukraine. In the contemporary context, it has been used by pro-Russian separatists to refer to certain areas of Ukraine [Data: Entities (6494, 912, 6493)].</li><li>The term Novorossiya has been used in the context of a political movement in Ukraine, particularly by Russian nationalists. This movement has been associated with efforts to destabilize Ukraine and create a so-called "Novorossiya" [Data: Entities (912); Relationships (15211, 15206)]. The term has also been used to denote a separatist state in Ukraine, known as the Federal Republic of Novorossiya (FRN) [Data: Entities (7690)].  </li><ol>|

These results show that both systems work well. This shows a class of queries where Baseline RAG succeeds. Now let's try a query that requires connecting the dots:

Query: "What has Novorossiya done?"

|Baseline RAG|GraphRAG|
| :--- |:---|
|The text does not provide specific information on what Novorossiya has done.| <ol><li>Novorossiya, a political movement in Ukraine, has been involved in a series of destructive activities, particularly targeting various entities in Ukraine [Entities (6494, 912)]. The movement has been linked to plans to destroy properties of several Ukrainian entities, including Rosen, the Odessa Canning Factory, the Odessa Regional Radio Television Transmission Center, and the National Television Company of Ukraine [Relationships (15207, 15208, 15209, 15210)]. In addition to these, Novorossiya has also been associated with plans to destroy properties of Roshen, the Odessa Conservatory Factory, the Odesa Regional Radio Television Transmission Center, and the National Telecommunications Company of Ukraine [Relationships (8329, 8330, 8331, 8332)]. Furthermore, Novorossiya has been implicated in plans to blow up ATMs of PrivatBank, the largest state bank in Ukraine[Relationships (8335, 8335)].</li><li>The Office of the General Prosecutor in Ukraine has reported on the creation of Novorossiya, indicating the government's awareness and potential concern over the activities of this movement [Relationships (8264, 8264)]. The destructive activities of Novorossiya have had significant impacts on the targeted entities and have likely contributed to the ongoing tensions and conflicts in the region. /  In summary, Novorossiya has been involved in a series of destructive activities targeting various entities in Ukraine. These activities have had significant impacts on the targeted entities and have likely contributed to the ongoing tensions and conflicts in the region. The Ukrainian government, through the Office of the General Prosecutor, has acknowledged the existence and activities of Novorossiya, indicating a level of concern over the movement's actions.</li><ol>|

Baseline RAG could not answer this question. If we look at the source documents inserted into the context window (see the figure below), no text fragment discusses "Novorossiya", which causes this problem.

![alt text](<../../../07-第七章-Agent/assest/GraphRAG 解锁大模型对叙述性私人数据的检索能力（中文翻译）/0.png>)

By contrast, the GraphRAG approach identified the entity in the query about Novorossiya. This gave the LLM a foothold in the graph and, by following links to the original supporting text, allowed it to infer a better answer with sources. For example, figure 2 below shows the exact content the LLM used for the generated statement "Novorossiya has been implicated in plans to blow up ATMs." We can see a fragment from the original English-translated document that the LLM used to support this statement through the relationship between two entities in the graph.

![alt text](<../../../07-第七章-Agent/assest/GraphRAG 解锁大模型对叙述性私人数据的检索能力（中文翻译）/1.png>)

Using an LLM-generated knowledge graph, GraphRAG substantially improves the "retrieval" part of RAG: the context window is filled with more relevant content, which gives better answers and records sources of evidence.

Trusting and verifying LLM-generated results is always important. We care whether the results are correct, coherent, and accurately reflect the source material. GraphRAG provides provenance or source grounding information for every generated answer. It shows that the answer is based on the dataset. Having citation sources available for each claim also allows the user to quickly and accurately compare the LLM output with the source material.

But this is not all GraphRAG can do.

## Reasoning over the whole dataset

Baseline RAG struggles with queries that require summarizing information from the whole dataset to produce an answer. Queries like "What are the top 5 themes in the data?" work poorly because Baseline RAG relies on vector search for semantically similar text content inside the dataset. There is nothing in the query itself that guides it to the right information.

With GraphRAG, we can answer such questions because the LLM-generated knowledge graph structure tells us the structure and themes of the whole dataset. This makes it possible to organize the private dataset into pre-summarized meaningful semantic clusters. When answering a user query, the LLM uses these clusters to summarize themes.

We illustrate whole-dataset reasoning by asking both systems the following question:

Query: "What are the top 5 themes in the data?"

|Baseline RAG|GraphRAG|
| :--- |:--- |
|<ol><li>Improving the quality of life in cities and urban development.</li><li>The meeting between Vladimir Putin and the President of the United Arab Emirates, Mohammed bin Zayed Al Nahyan.</li><li>The National Rating of the Investment Climate in the Regions of Russia.</li><li>The state of the Russian economy and the growth of domestic brands.</li><li>The discussion on the meaning of life and the role of science in understanding it. </li></ol> |<ol>The data presents a wide range of themes, but the top five most prevalent themes can be identified as follows: <li>Conflict and Military Activity: A significant portion of the data revolves around the ongoing conflict in Ukraine, with numerous reports detailing military activities, occupations, and attacks by various entities. This theme includes the actions of the Ukrainian military, Russian forces, and various other military units and entities [Data: Reports (513, 241, 151, 493, 343, +more)].</li><li>Political and Governmental Entities: Many reports focus on political figures and governmental entities, highlighting their roles, relationships, and actions in the context of the current situation. This includes entities like the Kremlin, the President of Ukraine, the US State Department, and various regional administrations [Data: Reports (98, 493, 265, 129, 196, +more)]. </li><li>Infrastructure and Environmental Concerns: Several reports highlight potential environmental impacts and infrastructure threats. These include potential environmental damage due to industrial activities, flooding crises, and threats to infrastructure due to military conflicts [Data: Reports (308, 154, 201, 348, 216, +more)].</li><li>Community Analysis and Threat Assessment: Several reports provide detailed analyses of specific communities, often centered around a particular location or entity. These analyses typically discuss the key entities within the community, their relationships, and any associated threats. Many reports also include assessments of potential threats associated with the entities or situations they discuss [Data: Reports (323, 596, 518, 583, 179, +more)]. </li><li>Health, Humanitarian Concerns, and Emergency Situations: Some reports focus on health and humanitarian issues, such as the Shereshevsky-Turner Syndrome community and the potential risk of intestinal diseases in the Odessa region. The data also covers emergency situations, including natural disasters, accidents, and attacks [Data: Reports (204, 149, 372, 154, 532, +more)]. <li>These themes provide a comprehensive overview of the current situation, highlighting the complexity and interconnectedness of the issues at hand.</li><ol>|

Looking at the Baseline RAG result, we can see that the listed themes have little to do with the war between the two countries. As expected, vector search retrieved irrelevant texts and inserted them into the LLM context window. The included results were probably related to the word "themes", which led to a not very useful assessment of what was happening in the dataset.

The GraphRAG result clearly fits the whole dataset much better. The answer gives the five main themes observed in the data and supporting details. The referenced reports are generated in advance by the LLM for each semantic cluster in GraphRAG, and then provide provenance for the source material.

## Creating an LLM-generated knowledge graph

We note the basic process behind GraphRAG. It builds on our previous [research](https://www.microsoft.com/en-us/worklab/patterns-hidden-inside-the-org-chart) using graph machine learning and on the [GitHub repository](https://github.com/graspologic-org/graspologic):

- The LLM processes the entire private dataset, creates references to all entities and relationships in the source data, and then uses those references to create an LLM-generated knowledge graph.
- This graph is then used to create bottom-up clustering, hierarchically organizing the data into semantic clusters (shown in different colors in the figure below). This partitioning allows semantic concepts and themes to be summarized in advance, which helps understand the dataset as a whole.
- During a query, both of these structures are used to provide material for the LLM context window when answering a question.

![alt text](<../../../07-第七章-Agent/assest/GraphRAG 解锁大模型对叙述性私人数据的检索能力（中文翻译）/2.jpg>)

The figure above shows an example visualization of this Graph. Each circle represents an entity, such as a person, place, or organization. The entity size shows how many relationships that entity has, and the color shows the grouping of similar entities. The color partitioning is a bottom-up clustering method built on top of the graph structure, and it allows questions to be answered at different levels of abstraction.

## Result metrics

The examples above represent stable GraphRAG improvement across several datasets in different domains. For evaluation, we use an LLM evaluator that determines the winner in a pairwise comparison between GraphRAG and Baseline RAG, measuring this improvement. We use a set of qualitative metrics, including comprehensiveness (coverage within the implicit contextual frame of the question), human empowerment (providing supporting source material or other context), and diversity (different viewpoints or angles on the given question). Preliminary results show that GraphRAG consistently outperforms Baseline RAG on these metrics.

Besides relative comparison, we also use [SelfCheckGPT](https://arxiv.org/pdf/2303.08896) for an absolute faithfulness measure, to help ensure that results are grounded in source material, truthful, and coherent. The results show that GraphRAG faithfulness is comparable to Baseline RAG. We are currently developing an evaluation framework for measuring quality across the question categories above. It will include more reliable mechanisms for generating test question and answer sets, as well as other metrics such as precision and contextual relevance.

## Next steps

By combining an LLM-generated knowledge graph and graph machine learning, GraphRAG can answer important questions that Baseline RAG alone cannot solve. After applying this technology in different scenarios, including social media, news articles, workplace productivity, and chemistry, we have already seen encouraging results. In the future, as we continue applying this technology, we plan to work closely with customers in different new domains while also working on metrics and reliable evaluation. As the research continues, we expect to share more information.

## Notes

[1] In this comparison, we used LangChain [Q&A](https://python.langchain.com/v0.1/docs/use_cases/question_answering/) as Baseline RAG, a known representative example of such a RAG tool that is widely used today.

[2] This dataset contains sensitive topics. The only purpose of choosing this dataset is to demonstrate data analysis tools that show all relevant information, including its sources. These tools are based on information in the dataset and allow users to reach grounded conclusions faster from opposing viewpoints in Ukrainian (`unian`) and Russian (`ria`) news articles, each taken in its original language. The tools highlight the source of each claim and can be used to determine information provenance.

## End of main text

## Welcome to my GitHub and WeChat channel: no time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown file, it is fully open, and stars and forks are welcome!
