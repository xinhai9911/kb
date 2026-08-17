---
aliases: ["es-book-05-paas"]
title: 《PaaS实现与运维管理》蒸馏
tags: [reference, sources, elasticsearch, elk, paas, mesos, docker, book, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\常规书籍
source_pdf: 《PaaS实现与运维管理：基于Mesos+Docker+ELK的实战指南》.pdf
extract: 文本层提取（447 页，2026-07-29）
base_confidence: 0.85
lifecycle: reviewed
---

# 《PaaS实现与运维管理：基于Mesos+Docker+ELK的实战指南》_余何（电子工业出版社，2016）

> 内容来自 **文本层提取（447 页，2026-07-29）** 正文提炼。索引见 [[Elasticsearch ELK]]。

- **定位**：以平安科技实践经验为背景，阐述 PaaS 平台的**理论 + 技术实现 + 运维管理**。四大部分：①概念模型（运维与开发的矛盾、PaaS 如何缓解）②基础资源（计算/网络/存储三大主干）③平台实现（用开源产品构建完整 PaaS）④运维管理实践。强调"PaaS 绝不是改个容器或虚拟机那么简单"，是对平台建设理论、技术实现、配套系统、流程管理的全覆盖（蓝鲸/腾讯、优维等业界推荐）。
- **核心技术栈（第7-12章）**：计算单元 **Docker** + 分布式协调 **ZooKeeper** + 资源管理 **Mesos** + 服务调度 **Marathon** + 大数据 **Spark** + 日志集中管理 **ELK**（Logstash 采集 → ES 存储 → Kibana 展现）。
- **ELK 在 PaaS 中的角色（第12章）**：将 ELK 作为日志集中管理组件纳入 PaaS，解决分布式环境下多节点日志的采集、检索与可视化。
- **可提炼要点（实证）**：PaaS 落地 = 容器编排(Mesos/Marathon) + 协调(ZK) + 日志可观测(ELK) 的组合；对运维工作流是重新编排而非简单封装。
- **关联**：ELK 链路与 [[20-protocols/Elasticsearch 2]]、[[50-reference/sources/chips/3 TAP]] 的可观测性主题呼应；Mesos/Marathon 资源调度思路可与 [[50-reference/sources/chips/Centec SDK]] 的集群管理对照。
