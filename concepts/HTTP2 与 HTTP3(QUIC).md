---
title: HTTP/2 与 HTTP/3(QUIC)
category: concepts
tags: [http2, http3, quic, tcp, tls, hpack, multiplexing, udp, active]
created: 2026-08-12
updated: 2026-08-17
summary: >-
    HTTP/2 与 HTTP/3(QUIC)：HTTP/1.1 的队头阻塞与多连接问题、HTTP/2 多路复用/帧流/HPACK 头压缩/
    服务端推送、HTTP/3 基于 QUIC(UDP) 解决 TCP 队头阻塞/0-RTT/连接迁移。QUIC 握手时序与 TLS 1.3
    合并、gRPC 基于 HTTP/2 的双向流、帧结构（HEADERS/DATA/RST_STREAM）。
    衔接 [[concepts/TLS 协议握手与记录层]]、[[concepts/Linux 内核网络栈]]、[[concepts/Kubernetes 网络模型]]（Ingress/gRPC）。
base_confidence: 0.88
lifecycle: review
sources: []
---

# HTTP/2 与 HTTP/3(QUIC)

> 现代 Web/微服务传输层。K8s Ingress、gRPC 都建立在这之上。见 [[concepts/Kubernetes 网络模型]]。

---

## 1. HTTP/1.1 的痛点

- **队头阻塞（应用层）**：同连接请求串行，前一个没回后面等着。
- **多连接**：浏览器开 6+ TCP 连接并发，握手/内存开销大。
- **冗余头部**：每次请求重复带 Cookie/UA 等大头。

---

## 2. HTTP/2（基于 TCP）

| 机制 | 作用 |
|---|---|
| **多路复用** | 单 TCP 连接上并发多个**流（stream）**，帧（frame）交错传输，彻底解决应用层队头阻塞 |
| **二进制分帧** | 数据切成 HEADERS/DATA 等帧，不再是明文文本 |
| **HPACK** | 头部压缩（维护静态+动态字典，差值编码），大幅瘦身 |
| **流优先级/权重** | 告知接收端哪些流更重要 |
| **服务端推送** | 服务端主动推资源（已少用，常被 preload 替代） |

```
一个 TCP 连接
 ├─ Stream 1: [HEADERS][DATA][DATA]
 ├─ Stream 3:        [HEADERS][DATA]   ← 与 Stream1 交错，互不阻塞
 └─ Stream 5:                  [HEADERS]
```

> [!note] HTTP/2 仍有 TCP 队头阻塞
> 若底层 TCP 一个包丢失，整个连接的所有流都等它重传——这是 HTTP/3 要解决的。

---

## 3. HTTP/3（基于 QUIC，跑在 UDP 上）

QUIC = 在 UDP 之上自己实现**可靠传输 + 加密 + 多路复用**：

| 能力 | 收益 |
|---|---|
| **无 TCP 队头阻塞** | 一个流丢包只阻塞该流，其他流在 UDP 上照跑 |
| **0-RTT / 1-RTT 握手** | QUIC 握手与 TLS 1.3 合并，复用连接时 0-RTT 发数据（[[concepts/TLS 协议握手与记录层]]） |
| **连接迁移** | 用 Connection ID 标识连接，换 IP（切 WiFi/4G）不断流 |
| **内置加密** | 默认 TLS 1.3，包级加密 |

> QUIC 把「可靠有序」从内核 TCP 上移到用户态（类似 [[concepts/eBPF 核心架构]] 把能力从内核搬到用户态的思路）。

### QUIC 握手时序（对比 TCP+TLS 1.3）

```
TCP + TLS 1.3（2-RTT）：
Client                    Server
  │──── SYN ────────────────▶│  ① TCP 握手
  │◀─── SYN-ACK ────────────│
  │──── ACK + ClientHello ──▶│  ② TLS 握手
  │◀─── ServerHello + Fin ──│
  │──── Finished ───────────▶│
  │◀─── 0-RTT Data ─────────│  共 2-RTT 才传数据

QUIC（1-RTT 首次，0-RTT 复用）：
Client                    Server
  │──── Initial (CH+Transport)▶│  ① 一次性发
  │◀─── Initial (SH+Fin) ─────│
  │──── 0-RTT Data ──────────▶│  首次 1-RTT 即可传数据
  │◀─── Application Data ─────│
  
复用时：Client 直接发 0-RTT Data，无需握手
```

> [!note] 为什么 QUIC 更快
> TCP 必须先建连接（1-RTT）再做 TLS（1-RTT），共 2-RTT。QUIC 把传输层握手和加密握手合并，首次只需 1-RTT，复用时 0-RTT。

---

## 4. 部署要点

- 终止在哪：Ingress/网关做 TLS+HTTP/2 终止（[[entities/Kubernetes 网络实战]]、[[entities/Ingress-Nginx 详解实战]]）；后端多用 HTTP/2（gRPC 默认）。
- 启用 HTTP/3 需反向代理/网关支持（现代 Envoy/Cilium/NGINX 渐支持）。
- **gRPC** 基于 HTTP/2，天然多路复用、双向流——微服务间通信优选（[[entities/微服务拆分实战]]）。

### HTTP/2 帧结构详解

```
+-----------------------------------------------+
|                 Length (24)                    |  帧长度
+---------------+---------------+---------------+
|   Type (8)    |   Flags (8)  | R | Stream ID |
+---------------+---------------+---------------+
|             Frame Payload ...                 |
+-----------------------------------------------+

常见帧类型：
- HEADERS：请求/响应头（HPACK 压缩）
- DATA：请求/响应体
- SETTINGS：连接级配置（最大并发流、窗口大小）
- RST_STREAM：单流终止（错误处理，不中断整个连接）
- PING：连接级心跳（检测死连接）
- GOAWAY：优雅关闭（停止接受新流，等旧流完成）
```

> [!note] 与 HTTP/1.1 对比
> HTTP/1.1 是文本协议（`\r\n` 分隔），无法区分「头结束」和「体开始」的边界。HTTP/2 用二进制帧，每帧有明确的 Type + Length，解析更高效。

---

## 5. 衔接

- 握手/加密：[[concepts/TLS 协议握手与记录层]]
- 内核传输：[[concepts/Linux 内核网络栈]]
- 网络入口：[[concepts/Kubernetes 网络模型]]、[[entities/Kubernetes 网络实战]]
- 数据面加速：[[concepts/eBPF 核心架构]]、[[entities/Cilium 容器网络]]

---

## 参考链接

**库内双链**
- [[concepts/TLS 协议握手与记录层]] — QUIC 内嵌的 TLS 1.3
- [[concepts/Linux 内核网络栈]] — TCP/UDP 基础
- [[concepts/Kubernetes 网络模型]]、[[entities/Kubernetes 网络实战]] — Ingress/gRPC 落地
- [[entities/Cilium 容器网络]]、[[concepts/eBPF 核心架构]] — 现代数据面

**外部资料**
- RFC 9113 (HTTP/2)、RFC 9114 (HTTP/3)、RFC 9000 (QUIC)
- Cloudflare / Fastly 的 HTTP/3 科普
