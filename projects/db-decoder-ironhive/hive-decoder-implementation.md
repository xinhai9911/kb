---
title: >-
    Hive 解码器实现
category: projects
tags: [hive, decoder, cpp, thrift, falcon]
sources: [projects/db-decoder-ironhive]
summary: >-
    libhive.so 解码器结构：11 个 C++ 文件，含 TBinaryProtocol 解码层、主解码器、Suricata 集成。
provenance:
  extracted: 0.7
  inferred: 0.2
  ambiguous: 0.1
base_confidence: 0.62
lifecycle: reviewed
lifecycle_changed: 2026-07-29
created: 2026-07-29
updated: 2026-07-29
---

# Hive 解码器实现

## 文件结构

| 文件 | 说明 |
|------|------|
| hivedef.h | 协议定义（proto_id=36，端口 11300，枚举类型） |
| hivethriftdef.h | Thrift TBinary/TCompact 类型定义 |
| hive_thrift_binary_decoder.\* | TBinaryProtocol 解码 |
| hive.\* | 主解码器（HandlePkt/HandleThrift/OutPutDBSql） |
| hive-c-api.\* | Suricata C API 接口 |
| app-layer-hive.\* | Suricata 应用层注册 |
| broxyproc\_hive.\* | Broxy 代理模式 |
| hivetcpfragment.\* | TCP 分片重组 |

## 关键实现点

- checkThrift() 检测 0x80 0x01 魔数，HiveServer1/TFramedTransport 双模式
- 端口无关：接受框架分发的任何端口
- ALPROTO\_HIVE=35（StringToAppProto("hive") 返回值）

## 部署问题

falcon 的 `app-layer.protocols` 不支持动态加载自定义协议 .so 文件。
`RegisterHiveParsers` 函数从未被执行。需挂到 `hbase` 键名下使用。
