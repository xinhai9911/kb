---
aliases: ["es-book-04-kibana"]
title: 《Kibana 中文指南》蒸馏
tags: [reference, sources, elasticsearch, elk, kibana, book, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\常规书籍
source_pdf: 《Kibana 中文指南》.pdf
extract: 全量 OCR（653 页标记，2026-07-29）
base_confidence: 0.7
lifecycle: reviewed
---

# 《Kibana 中文指南》

> 内容来自 **全量 OCR（653 页标记，2026-07-29）** 正文提炼。该书为社区维护的 Elastic Stack 5.0 中文指南（chenryn 版），含大量 ELK 实战经验。中文噪点多，但 Logstash 配置、命令、字段名清晰可辨。索引见 [[Elasticsearch ELK]]。

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
- **关联**：可视化与 [[50-reference/sources/chips/3 TAP]] 流量可视化设备的前端思路可对照；Logstash 管道与 [[20-protocols/Elasticsearch 2]] 的索引写入链路衔接。
