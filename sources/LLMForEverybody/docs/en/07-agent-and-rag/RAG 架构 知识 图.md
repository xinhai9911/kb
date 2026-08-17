---
aliases: ["rag-arhitektura-s-knowledge-graph"]
---

# RAG Architecture with Knowledge Graph

## 1. RAG

Retrieval-Augmented Generation (`RAG`) improves the accuracy and relevance of generated text by combining large language models (`LLM`) with information retrieval systems. This approach lets the model first retrieve relevant information from an authoritative knowledge base before generating an answer, which keeps the result current and professional without retraining the model itself.

RAG matters because it solves several key LLM problems: producing false information, generating outdated information, relying on non-authoritative sources, and giving inaccurate answers because of terminology confusion. With RAG, information can be retrieved from authoritative and predefined knowledge sources, which strengthens control over generated text and also increases user trust in AI solutions.

![alt text](<../../../07-第七章-Agent/assest/搭配Knowledge Graph的RAG架构/8.PNG>)

## 2. Knowledge Graph

Knowledge Graph is a structured semantic knowledge base designed to store information related to real-world entities, such as people, places, organizations, events, and so on, and to describe different relationships between these entities. Knowledge Graph is often used to strengthen search engine capabilities, provide richer search results, and improve semantic understanding of data in different AI applications.

Key components of a Knowledge Graph:

- Entities:

Entities are the basic units of a Knowledge Graph. They represent real-world objects or concepts, such as "Eiffel Tower", "New York", or "Apple Inc."

- Relations:

Relations describe semantic connections between entities, such as "located in", "founder", or "starred in." These relations allow a Knowledge Graph to express complex facts, for example "the Eiffel Tower is located in Paris."

- Attributes:

Entities usually have a set of attributes that provide additional information about the entity, such as the height or construction year of the Eiffel Tower.

![alt text](<../../../07-第七章-Agent/assest/搭配Knowledge Graph的RAG架构/4.png>)

## 3. Knowledge Graph + RAG

In the RAG (`Retrieval-Augmented Generation`) framework, we cut documents into small fragments (`chunks`), then use a retrieval module to find document fragments relevant to the query. This approach improves the accuracy and relevance of generated text while keeping it current and professional.

However, in real texts, chunks have relationships with other chunks, and RAG does not take these relationships into account well enough. To solve this problem, we can introduce a Knowledge Graph and represent relationships between document chunks as a graph structure. During retrieval, we can then not only find document fragments relevant to the query, but also use relationships in the Knowledge Graph to find information connected to the query-relevant chunks.

![alt text](<../../../07-第七章-Agent/assest/搭配Knowledge Graph的RAG架构/3.png>)

Each entity stores information from the corresponding chunk. Each relation stores information about the connection between chunks.

During retrieval, we can semantically find several relevant entities, then traverse other related entities for each one. Even if an entity was not directly returned by semantic search, we can return it through related relations. This approach effectively prevents information loss that may happen when a document is split.

In this way, the RAG framework not only improves retrieval accuracy and relevance, but also strengthens understanding of complex internal document relationships, making generated text more coherent and professional.

## 4. Misconceptions

When using RAG + Knowledge Graph, keep several common misconceptions in mind:

1. This is not about directly reusing an old Knowledge Graph. The knowledge graph needs to be rebuilt for the specific task.
2. Building a Knowledge Graph here does not mean generating a traditional entity-relationship diagram. It mainly borrows the idea of a graph database, where relationships between chunks in a document are represented as a graph structure.

## References

<div id="refer-anchor-1"></div>

[1] [deeplearning.ai](https://www.deeplearning.ai/short-courses/knowledge-graphs-rag/)

## Follow my GitHub and WeChat channel: no time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files. The project is fully open source, and stars and forks are welcome!
