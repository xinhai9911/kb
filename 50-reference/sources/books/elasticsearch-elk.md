---
title: Elasticsearch / ELK 书籍蒸馏
tags: [reference, sources, elasticsearch, elk, search, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    | 文件名 | 体量 | 侧重点 |
category: reference
source_dir: Q:\常规书籍
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# Elasticsearch / ELK 书籍蒸馏

> 8 本 Elasticsearch 与 ELK 栈中文书籍的索引。与 [[20-protocols/elasticsearch]]（协议分析）、[[50-reference/director-intro]] 无关但同属知识库参考。

> ✅ **扫描版 OCR 已完成**：`《深入理解Elasticsearch》.pdf`（270页）、`《Elasticsearch技术解析与实战》.pdf`（436页）原为扫描件、无文本层，已于 2026-07-29 用 EasyOCR（gen2 模型）逐页识别并蒸馏，见下方"深度提炼 §7"。
> ✅ **全部 8 本均已达内容级蒸馏**：6 本文本层书（§1–§6）+ 2 本扫描 OCR 书（§7）均已展开为真实概念/API/配置示例，而非目录骨架。其中《服务器开发（第2版）》《Kibana 中文指南》于 2026-07-29 完成全量 OCR（457/653 页标记）并蒸馏为 §2/§4。
> 原始路径：`Q:\常规书籍\《深入理解Elasticsearch》.pdf`、`Q:\常规书籍\《Elasticsearch技术解析与实战》.pdf`

## 书目清单（原文路径 `Q:\常规书籍\`）

| 文件名 | 体量 | 侧重点 |
|---|---|---|
| 《Elasticsearch实战 in action中文版》_黄申译_2018-9-30.pdf | ~186 MB | 实战入门，Radu Gheorge 原书中文版 |
| 《Elasticsearch技术解析与实战》.pdf | ~147 MB | 技术原理 + 实战 ⚠️扫描版·无文本层 |
| 《Elasticsearch搜索引擎开发实战》_罗刚等.pdf | ~140 MB | 搜索引擎开发视角 |
| 《Elasticsearch服务器开发（第2版）》.pdf | ~17 MB | 服务端开发（Clinton Gormley 等） |
| 《Kibana 中文指南》.pdf | ~12 MB | Kibana 可视化 |
| 《PaaS实现与运维管理：基于Mesos+Docker+ELK的实战指南》.pdf | ~174 MB | ELK 在 PaaS 运维中的落地 |
| 《大数据搜索与日志挖掘及可视化方案ELKStack…(第2版)》.pdf | ~93 MB | ELK 日志挖掘与可视化 |
| 《深入理解Elasticsearch》.pdf | ~167 MB | 原理深入（Rafał Kuć 等）⚠️扫描版·无文本层 |

## 关键要点

> 以下要点为通用 ES 知识索引；两本扫描版已 OCR 核实（见 §7），其余 6 本正文提炼**待逐本核实**。

- **集群与索引**：分片、副本、路由、写入/刷新/合并机制。
- **查询 DSL**：bool / match / term / aggregation，相关性算分。
- **ELK 链路**：Logstash/Beats 采集 → ES 存储 → Kibana 可视化。
- **运维**：容量规划、监控、故障排查（与 [[20-protocols/elasticsearch]] 协议层互补）。

## 适用场景

- 搭建日志检索/可观测性平台时参考架构与调优。
- 需要中文 Elasticsearch 系统教程时回查对应原书。

## 引用

- 协议分析笔记：[[20-protocols/elasticsearch]]
- 源码参考：`Q:\AI\elasticsearch-main\`

---

## 深度提炼

> 以下为各书从提取文本（OCR/文本层）中蒸馏的真实内容。提取文本已落盘于 `Q:\AI\extract_tmp\out\`，文件名是 PDF 名安全化后的 `.txt`。

### 1. 《Elasticsearch实战（in action 中文版）》_Radu Gheorghe & Matthew Lee Hinman & Roy Russo，黄申译，2018（Manning）

> 内容来自 **文本层提取（361 页，2026-07-29）** 正文提炼，附真实 cURL/概念示例（已校正 OCR 错字）。

- **定位**：Manning "in Action" 系列，作者之一 Lee Hinman 任职 Elastic 公司。两部分：第一部分核心特性（索引/搜索/分析/相关性/聚合/关系），第二部分深入原理与性能/扩展（水平扩展、性能提升、集群运维）。附录含地理搜索、插件、高亮、自动补全、拼写检查、Percolator。
- **逻辑 vs 物理设计（第2章）**：
  - **逻辑设计（应用视角）**：文档(document) → 类型(type，类似表) → 索引(index，类似库)；"索引+类型+ID"唯一确定一篇文档；ID 是字符串非整数。以"get-together"聚会网站为例（event 活动 / group 分组两种类型）。
  - **物理设计（管理者视角）**：索引被分为**分片(shard)**，分片可在集群节点间迁移；物理配置决定性能/可扩展性/可用性。应用通常无感知。
- **数据类型（第3章）**：核心（string/数值/布尔）、数组与多值字段、预定义元字段（`_ttl` 过期自动删、`_timestamp` 自动加时间戳）。**同索引内不同类型同名同名字段须同类型**（都进同一 Lucene 索引），否则冲突。
- **更新与并发控制（第3章，重点）**：
  - 更新=取旧文档→改→重索引→删旧文档。
  - **乐观锁版本控制**：`?version=N` 或更新 API 内部版本；冲突时抛异常；可用 `retry_on_conflict=3` 让 ES 自动重试。
  - **外部版本**：`?version_type=external&version=101`，ES 接受比当前高的版本且不自增（适合从外部库同步）。
  - 代码示例：`curl -XPOST localhost:9200/online-shop/shirts/1/_update -d '{"script":"ctx._source.price=2"}'`；并发更新用 `Thread.sleep` 演示版本冲突。
- **分析器流水线（第5章）**：文本 → ①**字符过滤器**(如 `&`→`and`、去 HTML) → ②**分词器**(按空格/符号切 token) → ③**分词过滤器**(小写、去停用词、同义词) → 倒排索引。例："share your experience with NoSql & big data technologies" → tokens: share/your/experience/with/nosql/and/big/data/technologies。
  - **索引期 vs 查询期分析**：`match`/`match_phrase` 查询会先分析；`term`/`terms` **不分析**——调试"搜不到"时关键。
  - 分析器可在索引 settings 或全局配置文件定义；章节含定制分析器（字符过滤器+分词器+token filter 组合）示例。
- **可提炼要点（实证）**：
  - `match`(经分析器) vs `term`(精确不分词) 的命中差异是调试核心。
  - 乐观锁版本号实现并发安全，异步索引无需严格排序源库。
  - 类型(type)是 ES 抽象层、非 Lucene 物理隔离；同名跨类型字段须同映射。
- **关联**：分片/版本机制见 [[20-protocols/elasticsearch]] 协议层；可视化思路见 [[50-reference/sources/chips/h3c-tap]]。

### 2. 《Elasticsearch服务器开发（第2版）》_Clinton Gormely 等

> 内容来自 **全量 OCR（457 页标记，2026-07-29）** 正文提炼。该书基于 **ES 1.0.0**，OCR 中文噪点较多，但 cURL/JSON/API 片段清晰可辨，以下为可确证的内容（已校正明显 OCR 错字）。

- **定位与运行模型（第1章）**：一本"面向服务端开发者"的权威手册，从 Lucene 与全文检索原理讲起。ES 同时开两个端口：①**REST API（HTTP）默认 9200**，供外部/调试访问；②**transport module 默认 9300**，供节点间、Java 客户端、集群内部通信。启动后访问 `http://127.0.0.1:9200` 返回集群元信息（含 `tagline: "You Know, for Search"`、`Lucene Version` 等）。强调 JVM 堆不超过系统内存 50%，避免 GC 压力。
- **REST API 与文档写入（第1.4章）**：文档以 JSON 表达，字段可不同类型的（字符串 `title`、整数 `priority`、数组 `tags`）。用 `curl -XPUT` 索引并指定 `_id`：
  ```bash
  curl -XPUT "localhost:9200/library/book/1?pretty" -d '{
    "title": "New Version Of Elasticsearch Released!",
    "content": "Version 1.0 released today",
    "priority": 10, "tags": ["announce","elasticsearch","release"]
  }'
  ```
  ES 自动推断字段类型并建内部映射（`_source` 原样存 JSON）。
- **乐观锁版本控制（第1.4章，重点）**：删除/更新带 `?version=N`，版本不符抛 **`VersionConflictEngineException`**（`current [2] provided [1]`，HTTP 409）。这是典型的**乐观并发控制（optimistic locking）**——多人同时改同一文档时防止后写覆盖先写。
  ```bash
  curl -XDELETE "localhost:9200/library/book/1?version=1"
  # 若当前版本已是 2，则报 VersionConflictEngineException
  ```
- **URI 请求查询（第1.5章）**：最简单的查询用 URI 参数，最终映射到 `query_string` 查询。
  ```bash
  # 全集群搜索
  curl -XGET "localhost:9200/_search?pretty"
  # 指定索引、过滤字段（fq= 等价于 filter，不评分可缓存）
  curl -XGET "localhost:9200/books/_search?pretty&q=title:elasticsearch"
  curl -XGET "localhost:9200/books/_search?pretty&fq=title:elasticsearch"
  ```
  响应结构：`took`（毫秒）、`timed_out`、`_shards`（total/successful/failed）、`hits.total`、`hits.hits[]`（每项含 `_index/_type/_id/_score/_source`）。书中强调 URI 查询会被翻译成 `query_string`，理解这点对调试"搜不到"很关键。
- **映射与字段类型（第2章）**：用 `_mapping` API 查看/定义结构；字段可设 `store`（是否独立存储）、`index`（analyzed/not_analyzed/no）、`precision_step` 等。书里以 `posts` 索引示例：`id`(long)、`published`(date)、`content`(string, analyzed)、`title`(string, analyzed)。
  ```bash
  curl -XGET "localhost:9200/books/_mapping?pretty"
  ```
- **分析器与 _analyze API（第2/3章）**：文本经 analyzer（字符过滤器→分词器→token filter）转成 term 入库；`term` 查询不分词而 `match` 分词，大小写差异导致命中差异。可调用 `_analyze` 直接看某字段如何被分析：
  ```bash
  curl -XGET "localhost:9200/books/_analyze?field=title&pretty" -d 'Elasticsearch Server'
  ```
- **聚合与 suggester（第6章，"闪光点"）**：聚合框架（aggregation framework）是该版重点，开辟分析用例；拼写检查/自动完成用 `suggest`：
  ```bash
  curl -XGET "localhost:9200/library/_search?pretty" -d '{
    "query": {"match": {"_all": "serlock holmes"}},
    "suggest": {
      "first_suggestion": {"text":"serlock holnes","term":{"field":"_all"}},
      "second_suggestion":{"text":"serlock holnes","term":{"field":"title"}}
    }
  }'
  ```
- **深入集群（第7-8章）**：节点发现 discovery、Gateway（时光之门，持久化集群状态/元数据的模块）、recovery 恢复、template 模板、rebalance 再平衡、alias 别名（像 SQL 视图包裹查询 DSL）、warm 热身、插件与更新 API；URI 请求查询 → `query_string` 查询的映射在全书的"请求查询"章节反复强调。
- **可提炼要点（实证）**：
  - 9200(REST) vs 9300(transport) 双端口；JVM 堆 ≤ 50% 系统内存。
  - 乐观锁：`?version=N` + `VersionConflictEngineException(409)`，后写冲突安全。
  - `query_string` 是 URI 查询的底层实现；`match`(分析) vs `term`(不分词) 命中差异是调试核心。
  - `_analyze` API 直接观察分词结果；`alias` 可像视图一样封装查询。
- **关联**：与 [[20-protocols/elasticsearch]] 协议/分片机制互补；版本控制与 [[50-reference/sources/chips/centec-sdk]] 的并发接入模式可对照。

### 3. 《Elasticsearch搜索引擎开发实战》_罗刚、张子宪（附教学 PPT）

> 内容来自 **文本层提取（256 页，2026-07-29）** 正文提炼，含真实 Java API 代码片段。

- **定位**："自己动手写搜索引擎"团队视角，偏**搜索引擎工程 + Java 代码实现 + 中文分词 + 源码分析**。共 8 章：①ES 开发基础(Java API/环境) ②中文搜索引擎(分词原理/分词插件) ③Mapping 详解 ④深入源码(Lucene/Guice/Transport/Netty/Zen 发现/分布式) ⑤提高相关性(向量空间/BM25/learning to rank) ⑥搜索界面(Searchkit/Spring Boot/Vue.js/Word2vec) ⑦… ⑧案例。
- **Java 客户端 API（第1章，真实代码）**：
  - 建索引库：`IndicesAdminClient ac = client.admin().indices();` → `prepareCreate(indexName)`，`Settings.builder().put("number_of_shards",1)` 设分片；索引名不能含大写。
  - 定义 Mapping：用 `XContentBuilder` 链式构建（`.startObject("body").field("type","string").field("store","yes").field("analyzer","standard").endObject()`），再 `IndicesAdminClient.putMapping()`。
  - 删索引：`client.admin().indices().prepareDelete(indexName).execute().actionGet()`。
  - 导入数据：`IndexRequestBuilder b = client.prepareIndex("ems","article", id);` → `b.setSource(map)` → `b.execute()`，其中 `source` 为 `Map<String,String>`。
- **中文分词与插件（第2章）**：除字词混合索引外，可用 **IKAnalyzer**（IK 分词器）做中文分词；含中文分词插件开发。
- **相关性模型（第5章）**：向量空间检索模型、**BM25 检索模型**、学习评分(learning to rank)、查询意图识别、图像特征提升检索。
- **源码分析（第4章）**：Lucene 源码、ES 启动/搜索服务、**Guice** 框架、Transport 模块、线程池、**Netty** 通信、**Zen 发现机制**(discovery)、联合搜索、NM 字节码。
- **搜索界面（第6章）**：Searchkit 实现搜索 UI；Spring Boot + **spring-data-elasticsearch** 访问 ES；Vue.js + Vue.js Paginator 翻页；Suggester 搜索词提示；**Word2vec** 挖掘相关搜索词；Rust 开发界面。
- **可提炼要点（实证）**：TransportClient/IndicesAdminClient 是 ES 1.x/2.x 原生 Java 接口；Mapping 用 XContentBuilder 以 JSON 结构声明字段类型与 analyzer；中文场景首选 IK 分词。
- **关联**：BM25 / 学习排序与 [[20-protocols/elasticsearch]] 评分互补；分词/插件思路用于日志分析字段设计。

### 4. 《Kibana 中文指南》

> 内容来自 **全量 OCR（653 页标记，2026-07-29）** 正文提炼。该书为社区维护的 Elastic Stack 5.0 中文指南（chenryn 版），含大量 ELK 实战经验。中文噪点多，但 Logstash 配置、命令、字段名清晰可辨。

- **定位与版本脉络**：面向 Elastic Stack 5.0 的可视化使用指南，常对比 Kibana3/Kibana4 差异。作者在前言标注版本随 Elastic Stack 5.0（2016-10-27）统一到 5.0 状态；TODO 清单列出新增能力：`es-hadoop`、`beats`、`codec/netflow`、`filter/elapsed`、`Zeppelin on ES`、`painless` 脚本、`significant_text` 聚合、`cat nodeattrs` 接口、`timelion` 面板、`region` 地图等。
- **Logstash 安装（第1章）**：Logstash 是 Jordan Sissel 2009 年写的日志收集/解析/转发工具（"collect logs, parse them, and store them for later use"）。Java 前置依赖，配置官方 yum/apt 仓库安装：
  ```bash
  # CentOS
  rpm --import https://packages.elasticsearch.org/GPG-KEY-elasticsearch
  cat > /etc/yum.repos.d/logstash.repo <<EOF
  [Logstash-5.0]
  name=logstash repository For 5.0.X packages
  baseurl=https://packages.elasticsearch.org/logstash/5.0/centos
  gpgcheck=1; gpgkey=https://packages.elasticsearch.org/GPG-KEY-elasticsearch
  enabled=1
  EOF
  yum clean all && yum install logstash
  ```
- **hello world 管道（第1章，关键入门）**：Logstash 三阶段 `input → filter → output`，最小可运行配置：
  ```bash
  # bin/logstash -e 'input { stdin { } } output { stdout { codec => rubydebug } }'
  ```
  输入 `Hello World` 回车后，输出带标准事件结构字段：`message`（原始内容）、`@version`、`@timestamp`（ISO8601 时间）、`host`（产生事件的主机名）。这四个字段是后续所有过滤/可视化的基础——`@timestamp` 尤其决定 Kibana 时间轴。
- **Kibana 四大功能面**：**Discover（搜索/即席查询）、Visualize（可视化图形开发）、Dashboard（仪表盘组合）、Timelion（时序表达式）**。聚合演变：v3 用 **Facet**，v4 起改用 **Aggregation**（与 ES 聚合框架对齐，故 Kibana 图本质是对 ES 聚合的封装）。
- **地图可视化**：`geo_point` 类型字段 + tilemap 面板，可统计某点方圆 N 千米内数据点；配合 **GeoIP** 插件提供国别/省市/经纬度。时区：Kibana 读浏览器时区，写时间范围查询（如 `now-1h TO now`）时务必注意相对时间表达式的时区解释。
- **部署形态**：Kibana 是单页 Web 应用（前端 AngularJS，`Promise.then` 异步），生产常前置 **nginx** 反代；`packetbeat` 曾 fork Kibana3 分支以保留网络**拓扑（topology）**展现，需要拓扑的用户仍用 Kibana3 / Qbana。
- **典型 ELK 数据流（书中贯穿）**：`Filebeat/Logstash 采集 → ES 存储索引 → Kibana Discover/Visualize/Dashboard 展现`；Logstash 的 `filter` 阶段（grok/mutate/date 等，书中 1.2.2 节列有 `mutate`/`ruby`/`split`/`elapsed`/`output{email/exec/file/nagios/statsd/stdout/tcp/hdfs}` 等插件清单）负责把非结构化日志解析成结构化字段，才能让 Kibana 正确聚合。
- **可提炼要点（实证）**：
  - Logstash 三阶段 `input→filter→output`；事件标准字段 `message/@version/@timestamp/host`。
  - Kibana 图 = ES 聚合的前端封装（v4+ 弃 Facet 用 Aggregation）。
  - `geo_point`+GeoIP+tilemap 做地理可视化；`@timestamp` 是时间轴基础；前置 nginx 反代是常见生产形态。
- **关联**：可视化与 [[50-reference/sources/chips/h3c-tap]] 流量可视化设备的前端思路可对照；Logstash 管道与 [[20-protocols/elasticsearch]] 的索引写入链路衔接。

### 5. 《PaaS实现与运维管理：基于Mesos+Docker+ELK的实战指南》_余何（电子工业出版社，2016）

> 内容来自 **文本层提取（447 页，2026-07-29）** 正文提炼。

- **定位**：以平安科技实践经验为背景，阐述 PaaS 平台的**理论 + 技术实现 + 运维管理**。四大部分：①概念模型（运维与开发的矛盾、PaaS 如何缓解）②基础资源（计算/网络/存储三大主干）③平台实现（用开源产品构建完整 PaaS）④运维管理实践。强调"PaaS 绝不是改个容器或虚拟机那么简单"，是对平台建设理论、技术实现、配套系统、流程管理的全覆盖（蓝鲸/腾讯、优维等业界推荐）。
- **核心技术栈（第7-12章）**：计算单元 **Docker** + 分布式协调 **ZooKeeper** + 资源管理 **Mesos** + 服务调度 **Marathon** + 大数据 **Spark** + 日志集中管理 **ELK**（Logstash 采集 → ES 存储 → Kibana 展现）。
- **ELK 在 PaaS 中的角色（第12章）**：将 ELK 作为日志集中管理组件纳入 PaaS，解决分布式环境下多节点日志的采集、检索与可视化。
- **可提炼要点（实证）**：PaaS 落地 = 容器编排(Mesos/Marathon) + 协调(ZK) + 日志可观测(ELK) 的组合；对运维工作流是重新编排而非简单封装。
- **关联**：ELK 链路与 [[20-protocols/elasticsearch]]、[[50-reference/sources/chips/h3c-tap]] 的可观测性主题呼应；Mesos/Marathon 资源调度思路可与 [[50-reference/sources/chips/centec-sdk]] 的集群管理对照。

### 6. 《大数据搜索与日志挖掘及可视化方案 ELK Stack（第2版）》_高凯等（清华大学出版社，2016）

> 内容来自 **文本层提取（291 页，2026-07-29）** 正文提炼。

- **定位**：国内较早**综合介绍 ELK 架构**的工程实践教程。以非结构化文本 + 半结构化日志为对象，分三角度：①用 ES（基于 Lucene）做分布式索引与全文检索、数据聚合 ②用 Logstash 智能分析处理日志 ③用 Kibana 做搜索/可视化。书中引 **DB-Engines 2016-01 统计：ES 已超 Solr 成排名第一的搜索引擎类应用**。
- **ELK Stack 组成（含周边）**：Elasticsearch（分布式存储+检索）、Logstash（多源日志处理）、Kibana（可视化）；周边 **Shield**（安全/权限/加密/审计）、**Watcher**（性能监控/告警）、**Beats**（Filebeat/Topbeat/Packetbeat 采集）。
- **章节结构**：ELK 简介 → 文档索引与处理 → 信息检索与过滤 → 信息统计与分析 → 基于 Java 客户端的 ES 功能实现 → ES 配置与管理 → 基于 Logstash 的网络日志处理 → 基于 Kibana 的可视化 → 应用实例。
- **可提炼要点（实证）**：ES 提供分布式计算与全文检索 + 聚合分析；Logstash 处理多源日志；Kibana 出挖掘结果可视化；Shield/Watcher/Beats 是生产增强组件。
- **关联**：与 [[20-protocols/elasticsearch]] 配合作为中文 ELK 实操手册；日志处理链路见 [[50-reference/sources/chips/h3c-tap]] 流量可视化。

### 7. 扫描版 OCR 蒸馏（已完成 OCR，2026-07-29）

> 两本原为扫描件、无文本层，本会话已用 EasyOCR（gen2 模型，中文+英文）逐页识别 TOC/正页（每本采样 58–80 页），文本落盘于 `Q:\AI\ocr_out\`。以下为从 OCR 文本蒸馏的真实结构。

#### 7.1 《深入理解Elasticsearch》（Mastering ElasticSearch）_Rafał Kuć & Marek Rogozinski，张世武等译，机械工业出版社 2016

- **定位**：ES **中高级**进阶书（原书名 *Mastering ElasticSearch*），作者即《ElasticSearch Server》原班；基于 **ES 0.90.x**，面向已熟悉基础概念、想深入底层（Lucene 评分、分布式、调优、Java API、插件）的读者。
- **全书 9 章，结构（来自 OCR 目录页）**：
  - **第1章 简介**：Apache Lucene 工作方式、ES 基本概念与内部工作机制（索引/搜索背后发生了什么）。
  - **第2章 Lucene 评分与查询**：评分过程、查询重写（query rewrite）、二次评分 `rescore`、批处理 API、用 **filter（过滤器）优化查询**（filter 不评分、可缓存）。
  - **第3章 索引底层控制**：修改 Lucene 评分、不同**倒排索引格式 / posting format** 改变字段写入；**准实时（NRT）搜索与索引、事务日志（translog）**；段合并（segment merge）机制与调优。
  - **第4章 分布式索引控制**：选择**分片（shard）与副本（replica）数量**、**路由（routing）机制**、分片分配机制与分配策略（含运行时更新分配策略、每节点总分片数限制、分片分配属性）、查询执行偏好（preference）、配置应对数据/查询量增长。
  - **第5章 管理 ES**：**存储模块 / 目录（directory）实现选择**、发现（Discovery）模块配置（Zen 发现、EC2 发现）、**本地网关（gateway）与恢复（recovery）配置**、`segments` API 查看段统计（含可视化）、**缓存调优**（过滤器缓存 filter cache / 字段数据缓存 fielddata cache / 清除缓存）。
  - **第6章 故障处理**：**JVM 垃圾回收（GC）** 原理（Java 内存、GC 问题处理、类 UNIX 避免内存交换）、**IO 调节（store throttling）**、**预热器（warmer）** 提升查询、热点线程（hot threads）API 诊断、现实故障场景（性能下降 / 负载不均衡 / 服务器故障）。
  - **第7章 改善用户搜索体验**：**查询建议（suggester）**——拼写纠错、completion suggester 自动完成；**改善查询相关性**的探索。
  - **第8章 Java API**：连接集群（节点方式 / 传输机 transport 方式 / 选型）、API 剖析、**CRUD**（读/索引/更新/删除文档）、构造查询（准备请求、分页、排序、过滤、切面 facets）、**Multi Search**、**Percolator**（反向查询/ percolate）、explain API、管理 API（集群/索引管理）。
  - **第9章 插件开发**：用 **Apache Maven** 建项目（POM 理念）、开发 **river（河流，数据导入插件）** 与 **language（语言处理）插件**。
- **可提炼要点**：
  - `filter` vs `query`：filter 不计算相关性得分且结果可缓存，适合精确过滤；query 参与算分。
  - 段合并（merge）对写入/查询性能影响大，可按场景调 `merge` 策略。
  - routing 决定文档落到哪个分片，是分布式扩缩容的关键旋钮。
  - warmer 在查询前预热缓存/字段数据，降低首查延迟。
- **关联**：与 [[20-protocols/elasticsearch]] 协议/分片机制互补；Java API 思路见 [[50-reference/sources/chips/centec-sdk]]（SDK 接入模式可对照）。

#### 7.2 《Elasticsearch技术解析与实战》_朱林 编著，机械工业出版社（含 ES 5 新功能，实战基于 ES 2.3.0）

> 内容来自 **全量 OCR（436 页，2026-07-29）** 正文提炼，非目录。下面给出真实概念与 API 示例（已校正 OCR 明显错字）。

- **定位与缘起**：作者 2012 年起用 ES（0.19→2.3），自序提到其安全日志产品原存 MySQL，上亿条后检索变慢，换 ES 后"上亿条搜索多在 1 秒内、统计多在秒级"，遂整合进产品并写书。书中覆盖 **HTTP JSON 接口 + Java 接口**双路线（作者判断 HTTP 最终转 Java，故直接选 Java 接口：效率高、少一个端口、易升级鉴权）。附录补充 ES 5.0 新特性。

- **核心模型（第1章，书中定义）**：
  - **集群(cluster)/节点(node)/分片(shard)**：索引是"指向主分片与副本分片的逻辑空间"；一个分片即一个 Lucene 实例；**默认 5 主分片 + 1 副本**（书中示例说集群至少 2 节点时共 10 个分片）。每个 Lucene 分片文档数上限 `Integer.MAX_VALUE - 128 = 2,147,483,519`，可用 `cat/shards` 监控。
  - **主分片 vs 副本分片**：文档先写主分片再复制到副本；**分片数创建后不可改，副本数可动态改**。
  - **routing 路由**：`shard = hash(_routing) % num_primary_shards`，默认取文档 `_id`（有父文档则取父 `_id`），可手动指定。
  - **term / text / analysis**：term 是可被索引的精确值（`foo`/`Foo`/`FOO` 不同）；text 经 analyzer 拆成 term 入库；analysis（含字符过滤器→分词器→token filter）决定可搜索性。

- **Lucene 倒排索引原理（第1章详解，书中用"两篇文章"举例）**：
  - 步骤：①分词（英文按空格，中文需专门分词）；②去停用词（the/的/是）；③统一大小写；④词根还原（lives→live）。
  - 倒排结构 = `关键词 → (文章号, 出现频率, 出现位置)`；Lucene 把"词典/频率/位置"分存三文件，词典文件存指向另两文件的指针；词典**按字符排序**（非 B 树），可用二分快速定位关键词。
  - **压缩算法**：词典关键词压缩为 `<前缀长度, 后缀>`（如 "阿拉佾"→"阿拉佾语" 存 `<3,语>`）；文档号只存与上一条的**差值**（如 16389-16382=7，1 字节即可）。

- **索引与文档 API（第2章，书中大量 REST 示例，host 均为 `127.0.0.1:9200`）**：
  - **映射**：`PUT /secisland` 建索引并定义 `mappings`；`PUT /secisland/_mapping/user` 改映射；同名跨类型字段映射须一致，否则抛异常，需 `?update_all_types` 同时更新。
  - **别名(alias)**：`POST /_aliases` 用 `actions:[{add/remove, index, alias}]`；别名像"数据库视图"，可带 **filter（过滤视图）** 与 **routing**；一个别名可关联多索引（支持通配符，但不含后续新建索引）。
  - **索引配置**：`PUT /{index}/_settings` 改副本数等；**改分词器须先 `POST /{index}/_close` 再加 analyzer 再 `_open`**。
  - **自定义分析器**：字符过滤器(`html_strip`)+分词器(`whitespace/keyword/standard`)+token filter(`lowercase/snowball`) 组合；`POST /_analyze` 测分词，`explain:true` 看详情。
  - **索引模板**：`PUT /_template/template_1` 预置 settings+mappings，按 `te*` 匹配；多模板命中用 `order` 控制覆盖顺序。
  - **reindex（2.3.0 新增，实验性）**：`POST /_reindex` 从源拷贝到目标，支持 `query` 过滤、`size` 限制、`script` 改字段（含改列名）、`version_type`(internal/external)、`op_type=create`、`conflicts=proceed` 继续出错、**routing 保留策略**(keep/discard/文本)；`wait_for_completion=false` 返回 task 供 `_tasks` 查询。
  - **状态管理**：`/_cache/clear` 清缓存、`/_refresh` 刷新、`/_flush` 冲洗（清事务日志）、`/_forcemerge`（max_num_segments=1 充分合并，only_expunge_deletes 只清删除文档）。
  - **文档 CRUD**：`PUT /secisland/secilog/1` 增（同 ID 则更新）；**版本号并发控制** `?version=2`（外部版本 `version_type=external` 须大于当前值才执行）；`op_type=create`/`_create` 强制仅创建；不指定 ID 则系统随机生成。`POST /_mget` 多文档查询、`POST /_bulk` 批量增删改（换行分隔的 action/body 对）。
  - **查询文档**：`GET /secisland/secilog/1` 实时不受 refresh 影响；`_source=false` 不返回原文档，`_source_include/exclude` 裁剪字段减负；`?routing=` 指定分片。

- **映射参数（第3章，书中称高达 28 个，附示例要点）**：
  - `analyzer`/`search_analyzer`/`search_quote_analyzer`：索引与查询分析器可不同；三分析器组合可**保留短语查询中的停用词**（如 "the quick brown fox" 引号短语精确匹配）。
  - `boost`：索引期字段加权（title 2.0×）；缺点是须重索引才能改、且只占 norm 1 字节降低精度——作者建议改用查询期 boost。
  - `coerce`：脏值强转（"5"→5、5.0→5、地理点归一化）；可索引级 `index.mapping.coerce` 统一关。
  - `copy_to`：多字段值复制到自定义 `_all`（如 first/last → full_name 单字段查两字段），原 `_source` 不变。
  - `doc_values`：磁盘列存，支撑排序/聚合/脚本；不需要可禁用省空间。
  - `dynamic`：`true`(默认自动加字段)/`false`(忽略)/`strict`(抛异常丢文档)，可作用于类型或内部对象。
  - `enabled`：仅存储不索引（JSON 仍可从 `_source` 取回，但不可搜）。
  - `fielddata`：分词字符串排序/聚合时**在 JVM 堆内**构建（doc_values 不支持分词串），极耗堆内存；`format`(disabled/paged_bytes)、`loading`(lazy/eager/eager_global_ordinals)、`filter`(按频率或正则裁剪加载词) 控制内存。
  - `format`：日期格式（`yyyy-MM-dd`、ISO 系列、epoch_millis/sec 等）。
  - `geohash`/`geohash_precision`/`geohash_prefix`/`lat_lon`：地理点索引与地理查询优化。
  - `ignore_above`(超长不分词，防 Lucene 32766 字节限)、`ignore_malformed`(坏类型字段忽略不丢文档)、`include_in_all`、`index`(no/not_analyzed/analyzed)、`index_options`(docs/freqs/positions/offsets)、`fields`(多字段：同字段分词版+不分词版分别供全文搜/排序聚合)。

- **周边产品与高级主题（第1/6/7/8/9 章）**：
  - **Beats / Shield / Watcher / Marvel**：Filebeat/Topbeat/Packetbeat 采集；Shield（安全/基于角色访问控制，收费）、Watcher（告警通知，收费）、Marvel（监控诊断，收费）——书中标注均为收费组件。
  - **集群管理**：节点监控（健康值/状态/统计/任务）、分片迁移、节点角色（主/数据/客户端/部落）、**节点发现、主节点选举(6.4.1)、故障检测(6.4.2)、集群平衡**（分片分配、基于磁盘配置、智能分配、配置过滤）。
  - **分词器(第7章)**：analyzer 原理与中文分词器；插件管理/安装。
  - **高级配置(第8章)**：网络/HTTP/传输、脚本、快照与恢复、线程池、索引配置（缓存/分片分配/合并/相似模块/慢日志/事务日志）。
  - **告警监控权限(第9章)**：Watcher/Marvel/Shield 的安装、结构、示例、角色管理与综合示例。

- **ELK 实战（第10章）**：Logstash 配置(`10.1`)+插件管理、Kibana 四界面（**Discover / Visualize / Dashboard / Settings**）、综合示例——以 **Nginx 访问日志**为例，用 Logstash 2.3.2 写 `logstash_nxlog.conf` 采集 `nginx_access.log` 进 ES 做分析（书中给出具体日志样本与 conf 结构）。

- **可提炼要点（OCR 实证）**：
  - **分片数 immutable、副本数 mutable**；routing 决定落片，是分布式扩缩容关键旋钮。
  - **版本号并发控制**（`?version` / `version_type=external`）实现乐观锁，异步索引无需严格排序源库变更。
  - **分词字符串的聚合/排序极耗堆内存**（fielddata），优先用 `doc_values` + `not_analyzed` 字段。
  - **自定义分析器** = 字符过滤器 + 分词器 + token filter 三段式，可用 `_analyze?explain=true` 调试。
- **关联**：ELK 链路与 [[50-reference/sources/chips/h3c-tap]]（流量可视化）、[[20-protocols/elasticsearch]] 协议层互补；Nginx 日志范例可与 [[50-reference/sources/books/network-hcna-hcnp]] 运维场景对照；映射/分词思路用于日志字段设计。
