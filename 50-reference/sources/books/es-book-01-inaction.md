---
title: 《Elasticsearch实战 in action》蒸馏
tags: [reference, sources, elasticsearch, elk, book, inaction, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\常规书籍
source_pdf: 《Elasticsearch实战 in action中文版》_黄申译_2018-9-30.pdf
extract: 文本层提取（361 页，2026-07-29）
base_confidence: 0.85
lifecycle: reviewed
---

# 《Elasticsearch实战（in action 中文版）》_Radu Gheorghe & Matthew Lee Hinman & Roy Russo，黄申译，2018（Manning）

> 内容来自 **文本层提取（361 页，2026-07-29）** 正文提炼，附真实 cURL/概念示例（已校正 OCR 错字）。索引见 [[elasticsearch-elk]]。

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
