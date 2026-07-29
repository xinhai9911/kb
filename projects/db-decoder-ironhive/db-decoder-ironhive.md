---
title: >-
    db-decoder-ironhive
category: projects
tags: [project, database, hive, decoder, ironhive]
sources: [Q:/AI/db-decoder-ironhive]
summary: >-
    IronHive 框架项目，用于 TPR 数据库协议能力建设。一期目标包括 Hive 协议解码器开发、AI 能力梳理、流程优化和 Harness trace 接入。
provenance:
  extracted: 0.6
  inferred: 0.35
  ambiguous: 0.05
base_confidence: 0.59
lifecycle: reviewed
lifecycle_changed: 2026-07-29
created: 2026-07-29
updated: 2026-07-29
---

# db-decoder-ironhive

## 项目概述

基于 IronHive 框架的 TPR 数据库协议能力建设一期项目。涵盖 Hive 数据库解码器开发、AI 能力沉淀、解码器开发 track 定义、以及平台部 Harness trace 接入。

## 架构

- **IronHive 框架**: 1+3+X+V 架构，SDD 规范驱动开发
- **解码器 Track**: 9 状态状态机（intake → pcap-capture → protocol-analysis → decoder-generation → remote-build → test-verify → fix-decoder/fix-build → archive）
- **协议分析**: HiveServer1 ThriftHive + TBinaryProtocol

## 关键决策

- Hive 0.10.0 (HiveServer1) 使用 TSocket + TBinaryProtocol strict，与 Hive 1.2.2 (TCLIService + TFramedTransport) 不兼容 ^[inferred]
- 解码器基于 thrift_binary_decoder 模板生成，复用 HBase Thrift 解码器框架
- 配置键 `hive` 在 falcon binary 的 `StringToAppProto` 中无映射，实际部署需挂到 `hbase` 键名下 ^[inferred]

## 产物

- `Q:\AI\output\hive\` — 15 个 C++ 源码 + Makefile + `libhive.so`
- `Q:\AI\db-decoder-ironhive\.ironhive\tracks\decoder.yaml` — 解码器开发 Track 定义
- 协议分析报告、pcap 抓包、测试验证报告

## 状态

解码器代码已完成，falcon 部署因框架限制（.so 不自动加载）需平台团队介入。
