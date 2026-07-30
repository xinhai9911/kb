---
title: API 设计
category: concepts
tags: [se, api, rest, grpc, versioning, idempotent, pagination, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    API 设计：REST 与 gRPC 取舍、资源建模与命名、版本化策略、幂等
    （[[concepts/分布式系统基础]]）、分页/过滤/排序、错误模型与状态码、
    安全（认证/授权/TLS，[[concepts/TLS 协议握手与记录层]]）、
    速率限制（[[concepts/韧性设计]]）、演进与弃用。配合 [[concepts/架构风格演进]]。
base_confidence: 0.85
lifecycle: draft
---

# API 设计

> API 是服务间（及前后端）的契约。契约一旦发布就难改——设计要慎。

## 1. REST vs gRPC

| 维度 | REST/JSON | gRPC/Protobuf |
|------|-----------|---------------|
| 传输 | HTTP/1.1+JSON（可读） | HTTP/2 + 二进制（紧凑快） |
| 类型安全 | 弱（运行时校验） | 强（.proto 生成） |
| 流式 | 弱 | 双向流原生 |
| 浏览器 | 直接可用 | 需 gateway 转 |
| 调试 | curl 即可 | 需工具 |
| 适用 | 对外公开 API、Web | 内部服务间、高性能、流式 |

> 对外门户用 REST + 网关（[[concepts/Nginx 架构与事件模型]]）；内部高频服务间用 gRPC。

## 2. 资源建模

- 用**名词复数**资源：`/users`、`/orders`，不用动词（`/getUser`）。
- 用 HTTP 方法表语义：`GET`读 `POST`建 `PUT`全量改 `PATCH`部分改 `DELETE`删。
- 嵌套表达从属：`/users/{id}/orders`。
- 层级别超过 2 层考虑扁平化或查询参数。

## 3. 版本化

| 方式 | 例子 | 取舍 |
|------|------|------|
| URL 版本 | `/v1/users` | 简单、显式、破坏旧链接 |
| Header 版本 | `Accept: application/vnd.api.v1` | URL 干净、不可见 |
| 不破坏式演进 | 加字段不删 | 最理想，但需纪律 |

> 弃用要提前公告 + 给宽限期 + 监控旧版调用量归零再下（见 [[concepts/可观测性工程]]）。

## 4. 幂等（跨文档重点）

- `GET`/`PUT`/`DELETE` 应幂等；`POST` 不幂等。
- 写 API 接受 **Idempotency-Key** 头，服务端去重（[[concepts/分布式系统基础]] §5）。
- 客户端重试（[[concepts/韧性设计]]）依赖服务端幂等才安全。

## 5. 分页 / 过滤 / 排序

- 游标分页（cursor）优于 offset 分页（深翻页慢、易漏数据）。
- 统一过滤语法：`?status=paid&created_after=...&sort=-created_at`。
- 返回总量/下一页游标，避免一次拉全表（DoS 风险）。

## 6. 错误模型

- 用标准 HTTP 状态码：`400` 参数错、`401` 未认证、`403` 无权限、`404` 不存在、`409` 冲突、`429` 限流、`5xx` 服务端。
- 错误体结构统一：`{ "code": "ORDER_NOT_FOUND", "message": "...", "request_id": "..." }`——`request_id` 便于链路追踪（[[concepts/可观测性工程]]）。
- 别泄露内部栈信息（安全风险）。

## 7. 安全

- 全程 **TLS**（[[concepts/TLS 协议握手与记录层]]），HSTS。
- 认证：API Key / JWT / OAuth2 / mTLS（服务间）。
- 授权：每个接口校验权限，默认拒绝。
- 输入校验 + 限流（[[concepts/韧性设计]]）防滥用。

## 8. 演进而非破坏

- 加字段向后兼容；删/改字段走新版本。
- 用 OpenAPI/Protobuf 作为**机器可读契约**，驱动文档与契约测试（[[concepts/CI_CD与测试策略]]）。

## 参考来源

- Microsoft REST API Guidelines / Google API Design
- 《API Design Patterns》
- [[concepts/架构风格演进]]
- [[concepts/分布式系统基础]]
- [[concepts/韧性设计]]
- [[concepts/TLS 协议握手与记录层]]
