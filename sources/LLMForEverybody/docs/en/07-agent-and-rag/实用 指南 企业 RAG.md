---
aliases: ["prakticheskoe-rukovodstvo-po-enterprise-rag"]
---

# Practical Guide to Enterprise RAG

Useful material: a practical guide to implementing enterprise RAG.

In enterprise data, much of the content comes from different document types, such as PDFs, Word documents, emails, and web pages. We need to focus on two stages: Load & Process and Split/Chunking.

## 1. What is RAG?

Retrieval-Augmented Generation (`RAG`) improves the accuracy and relevance of generated text by combining large language models (`LLM`) with information retrieval systems. This approach lets the model first retrieve relevant information from an authoritative knowledge base before generating an answer, which keeps the result current and professional without retraining the model itself.

RAG matters because it solves several key LLM problems: producing false information, generating outdated information, relying on non-authoritative sources, and giving inaccurate answers because of terminology confusion. With RAG, information can be retrieved from authoritative and predefined knowledge sources, strengthening control over generated text and increasing user trust in AI solutions.

![alt text](<../../../07-第七章-Agent/assest/干货： 落地企业级RAG的实践指南/01.png>)

## 2. Challenges in implementing enterprise RAG

In enterprise data, much of the content comes from different document types, such as PDFs, Word documents, emails, and web pages. We need to focus on two stages:

- Load & Process, marked as A in the diagram above, is the data loading process. In real applications, data formats and structures vary widely. So loading and processing such data effectively is a very difficult task.

- Split/Chunking, marked as B in the diagram above, is the process of splitting data into several parts. In real applications, data is usually unstructured, so it needs to be split and processed carefully so the model can understand and use it better.

## 3. Information that needs to be loaded

Besides extracting text from a document, other structural information is also important, such as filename, page number, and so on. In RAG practice, we need to extract all of this information to understand and process the data better.

**Document elements**: basic components of a document that can be used for different RAG tasks, such as filtering and chunking:

- Title
- Narrative text
- List item
- Table
- Image

**Element metadata**: additional information about elements that can be used for filtering in hybrid search and for identifying answer sources:

- Filename
- File type
- Page number
- Section

> Note: if you do not know what hybrid search is, no problem. We will explain it in detail below.

## 4. Data processing

Data processing is necessary but difficult, mainly because:

- Content hints: different document types provide different hints about element types (visual, markdown).
- Need for standardization: to process content from different document types, it needs to be standardized.
- Different extraction methods: different document formats may require different extraction methods.
- Metadata understanding: in many cases, extracting metadata requires understanding the document structure.

We need to convert different document types (PDF, Word, EPUB, MarkDown, and so on) into a unified format so the model can understand and process them better. One simple and effective way is to convert them into JSON.

JSON has the following features:

- The structure is common and easy to understand.
- It is a standard HTTP response.
- It can be used in many programming languages.
- It can be converted to JSONL for streaming scenarios.

Here is an example of conversion to JSON:

```Json
[
    {
        "element_id":"bff1fd0ec25e78f1224ad7309a1e79c4",
        "metadata":{
        "filename": "CoT.pdf",
        "filetype":"application/pdf",
        "languages":[
            "eng"
        ],
        "page_number":1,
        },
        "text":"B All Experimental Results",
        "type": "Title"
    },
    {
        "element_id":"ebf8dfb149bcbbd8c4b7f9a7046900a9",
        "metadata":{
        "filename": "CoT.pdf",
        "filetype":"application/pdf",
        "languages":[
            "eng"
        ],
        "page_number":1,
        },
        "text": "This section contains tables for experimental results for varying models and model sizes, on all benchmarks, for standard prompting vs. chain-of-thought prompting.",
        "type": "NarrativeText"
    }
]
```

For developers, this means finding a framework that can process different document types and convert them into JSON.

Some document types, such as HTML, Word Docs, and Markdown, contain formatting information and can be preprocessed by rule-based parsers. But PDFs or image documents require other processing technologies. These technologies are usually not open source: you have to buy them or develop them yourself.

## 6. Semantic search and hybrid search

For most people, semantic search is familiar: its goal is to find semantically similar content in a document corpus for a given input text, then add it to the Prompt.

But semantic search is not omnipotent. It has limits, such as:

- Too many search results: with many documents, there are too many semantically similar matches.
- Freshest information: the user may need the latest information, not simply the most semantically similar information.
- Loss of important information: important document structure related to retrieval can be lost, such as titles, page numbers, and so on.

Hybrid strategy: hybrid search is a retrieval strategy that combines semantic search with other information retrieval technologies, such as filtering and keyword search. Filtering parameters come from document metadata.

## 7. Chunking

A vector database needs to split a document into chunks for search and prompt generation. Depending on the chunking method, the same query over the same document can return different content.

**Equal-size chunks**: the simplest method is to split a document into chunks of roughly equal size. This causes similar content to be split across several chunks.

**Splitting by atomic elements**: after recognizing atomic elements, chunks can be formed by combining elements instead of cutting the original text. This produces more coherent chunks.

***Steps***:

1. Split: first split the document into atomic elements.
2. Combine elements into chunks: add document elements to a chunk until a character or token threshold is reached.
3. Apply break conditions: apply conditions for starting a new chunk, for example when reaching a new title element (meaning a new section), when element metadata changes (meaning a new page or section), or when content similarity exceeds a threshold.
4. Merge smaller chunks: optionally merge small chunks so they are large enough for effective semantic search.

***Key points***:

- Coherent chunks: content from the same document element stays together, making chunks more coherent.
- Structured chunks: the chunking method can use document structure, unlike traditional splitting techniques that divide text by token or character count.

![alt text](<../../../07-第七章-Agent/assest/干货： 落地企业级RAG的实践指南/17.png>)

## 8. Approaches to processing images in data

For other documents, such as PDFs and images, the information is visual. We need Document Image Analysis (`DIA`) to extract formatting information and text from the original document images.

Currently, DIA has two main approaches:

- Document Layout Detection (`DLD`) uses an object detection model to draw and label bounding boxes around layout elements in a document image.
- VisionTransformer (`ViT`) takes a document image as input and generates a text representation of the structured result, for example JSON.

![alt text](<../../../07-第七章-Agent/assest/干货： 落地企业级RAG的实践指南/2.png>)

More specifically, the DLD steps are: 1. visual detection, use a computer vision model such as YOLOX or Detectron2 to recognize and classify bounding boxes. 2. text extraction, use optical character recognition (`OCR`) if needed to extract text from bounding boxes.

Note: for some documents, such as PDFs, text can be extracted directly from the document without OCR.

![alt text](<../../../07-第七章-Agent/assest/干货： 落地企业级RAG的实践指南/22.png>)

ViT means the document image is passed into an encoder, after which a decoder generates text output. Document Understanding Transformer (`DONUT`) is a common architecture: it does not need OCR, directly converts the input image into text, and can even be trained to output valid JSON strings directly.

## 9. Approaches to processing tables in data

Most RAG scenarios focus on document text content. At the same time, some industries, such as finance and insurance, actively work with structured data embedded in unstructured documents. To support scenarios such as table Q&A, we need to extract tables from documents.

There are currently three technologies in the industry:

- Table Transformer: recognizes bounding boxes of table cells and converts the result to HTML.
- Vision Transformer: uses the visual transformer model from the previous section (PDF and image preprocessing), but outputs HTML.
- OCR + Table Parser: uses OCR to extract the table, then Table Parser to convert it into structured data.

## References

[1] [deeplearning.ai](https://www.deeplearning.ai/short-courses/preprocessing-unstructured-data-for-llm-applications/)

[2] [unstructured.io](https://unstructured.io/)

[3] [github:unstructured](https://github.com/Unstructured-IO/unstructured)

## Follow my GitHub and WeChat channel: no time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files. The project is fully open source, and stars and forks are welcome!


---

## 📚 相关概念

[[concepts/RAG 检索 增强 生成|RAG 检索 增强 生成]] | [[concepts/向量 DB 嵌入|向量 DB 嵌入]] | [[concepts/混合 检索 bm 25 语义 融合|混合 检索 bm 25 语义 融合]] | [[concepts/智能体 编排 模式|智能体 编排 模式]] | [[concepts/智能体 编程|智能体 编程]] | [[concepts/智能体 工具 使用 MCP|智能体 工具 使用 MCP]] | [[concepts/智能体 长 期 内存|智能体 长 期 内存]] | [[concepts/多 智能体 协作|多 智能体 协作]] | [[concepts/LLM 智能体 测试框架|LLM 智能体 测试框架]] | [[concepts/浏览器 智能体|浏览器 智能体]] | [[concepts/轻量 智能体 框架|轻量 智能体 框架]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/LangChain|LangChain]] | [[entities/CrewAI|CrewAI]] | [[entities/Anthropic|Anthropic]] | [[entities/OpenAI|OpenAI]] | [[entities/Google ADK|Google ADK]] | [[sources/Anthropic 智能体 构建|Anthropic 智能体 构建]] | [[sources/LangChain 入门|LangChain 入门]] | [[sources/MCP 规范|MCP 规范]] | [[sources/智能体 框架 对比|智能体 框架 对比]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：Agent
