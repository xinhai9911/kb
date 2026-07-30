---
title: Database Decoder 工作流
tags: [project, decoder, database, active]
created: 2026-06-10
summary: >-
    端到端流程：抓包 → 协议分析 → 代码生成 → 编译验证 → 测试验证 → 提交。
category: projects
updated: 2026-06-10
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# Database Decoder 工作流

端到端流程：抓包 → 协议分析 → 代码生成 → 编译验证 → 测试验证 → 提交。

## 核心 skill

- `db-decoder-workflow`
- `es-db-quick-pcap-crud`
- `database-decoder`
- `db-test-verification`

## 范围

- 支持的数据库：InfluxDB、HBase、Elasticsearch、Milvus、...
- 输出：协议解码器（Go）

## 关键决策

参见 [[50-reference/adr/0001-use-markdown-for-kb]]（虽然这条 ADR 是关于 KB 本身的，可以另写一条关于 decoder 选型）。

## 进度

- [x] InfluxDB 完成（见 [[20-protocols/influxdb]]）
- [x] HBase 完成（见 [[20-protocols/hbase]]）
- [x] Elasticsearch 完成（见 [[20-protocols/elasticsearch]]）
- [ ] Milvus（进行中）

## 相关笔记

- [[20-protocols/influxdb]]
- [[20-protocols/hbase]]
- [[20-protocols/elasticsearch]]