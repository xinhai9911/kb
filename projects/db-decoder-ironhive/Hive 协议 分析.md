---
aliases: ["hive-protocol-analysis"]
title: >-
    Hive 协议分析
category: projects
tags: [hive, protocol, thrift, tpr, database]
sources: [projects/db-decoder-ironhive]
summary: >-
    HiveServer1 ThriftHive 协议分析：TBinaryProtocol strict，7 个 RPC 方法，TSocket 裸流传输。
provenance:
  extracted: 0.7
  inferred: 0.25
  ambiguous: 0.05
base_confidence: 0.65
lifecycle: reviewed
lifecycle_changed: 2026-07-29
created: 2026-07-29
updated: 2026-07-29
---

# Hive 协议分析

## 协议特征

| 属性 | 值 |
|------|-----|
| **传输** | TSocket（裸 TCP 流，无帧头） |
| **编码** | TBinaryProtocol（strict 模式） |
| **消息头** | `[4B: 0x80010001/0x80010002]` + method string + seqid |
| **结构体结束** | T_STOP (0x00) |

## RPC 方法

| 方法 | 参数 | 返回 |
|------|------|------|
| execute(String) | query: T_BINARY id=1 | void + 可选 HiveServerException |
| fetchOne() | 无 | String |
| fetchN(i32) | numRows: T_I32 id=1 | List\<String\> |
| fetchAll() | 无 | List\<String\> |
| getSchema() | 无 | Schema struct |
| clean() | 无 | void |

## 与会话流程

SET → execute(SHOW DATABASES) → getSchema → fetchN(50) → fetchN(50) → execute(CREATE TABLE) → ...

## 与 HiveServer2 差异

| 对比项 | HiveServer1 (0.10.0) | HiveServer2 (1.2.2) |
|--------|---------------------|---------------------|
| 传输 | TSocket（裸流） | TFramedTransport（4B 帧头） |
| 协议 | ThriftHive（7 方法） | TCLIService（19 方法） |
| JDBC URL | jdbc:hive:// | jdbc:hive2:// |
