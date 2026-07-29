---
title: Elasticsearch / ELK 书籍蒸馏
tags: [reference, sources, elasticsearch, elk, search, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\常规书籍
---

# Elasticsearch / ELK 书籍蒸馏

> 8 本 Elasticsearch 与 ELK 栈中文书籍的索引。与 [[20-protocols/elasticsearch]]（协议分析）、[[50-reference/director-intro]] 无关但同属知识库参考。

## 书目清单（原文路径 `Q:\常规书籍\`）

| 文件名 | 体量 | 侧重点 |
|---|---|---|
| 《Elasticsearch实战 in action中文版》_黄申译_2018-9-30.pdf | ~186 MB | 实战入门，Radu Gheorge 原书中文版 |
| 《Elasticsearch技术解析与实战》.pdf | ~147 MB | 技术原理 + 实战 |
| 《Elasticsearch搜索引擎开发实战》_罗刚等.pdf | ~140 MB | 搜索引擎开发视角 |
| 《Elasticsearch服务器开发（第2版）》.pdf | ~17 MB | 服务端开发（Clinton Gormley 等） |
| 《Kibana 中文指南》.pdf | ~12 MB | Kibana 可视化 |
| 《PaaS实现与运维管理：基于Mesos+Docker+ELK的实战指南》.pdf | ~174 MB | ELK 在 PaaS 运维中的落地 |
| 《大数据搜索与日志挖掘及可视化方案ELKStack…(第2版)》.pdf | ~93 MB | ELK 日志挖掘与可视化 |
| 《深入理解Elasticsearch》.pdf | ~167 MB | 原理深入（Rafał Kuć 等） |

## 关键要点

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
