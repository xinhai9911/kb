---
title: Hot Cache
updated: 2026-07-29
---

# Hot Cache

*A ~500-word semantic snapshot of recent activity.*

## Recent Activity

- [2026-07-29] WIKI_UPDATE db-decoder-ironhive — 新项目同步，4 篇页面（项目概述、协议分析、Track 设计、实现）

## Active Threads

- **db-decoder-ironhive** — Hive 解码器开发一期，解码器代码已完成（libhive.so），falcon 部署因框架限制受阻，待平台团队介入

## Key Takeaways

- HiveServer1 (ThriftHive) 和 HiveServer2 (TCLIService) 协议不兼容，注意区分
- falcon 的 app-layer 配置 key 需挂到 hbase 名下才能加载（StringToAppProto 限制）
- IronHive decoder track 支持编译和验证双回环，适合迭代调试解码器
