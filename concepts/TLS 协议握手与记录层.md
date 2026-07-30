---
title: TLS 协议握手与记录层
category: concepts
tags: [crypto, tls, tls13, handshake, record-layer, pfs, 0rtt, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    TLS 1.2/1.3 协议深挖：握手流程（ClientHello/ServerHello、ECDHE 密钥交换、
    证书与签名验证、Finished）、记录层（AEAD 加密、序号、防重放）、
    1.3 相对 1.2 的简化（1-RTT、移除 RSA 传输/静态 DH、加密扩展）、
    前向保密 PFS、0-RTT 与重放风险、会话复用、TLS offload 与性能。
    配合 [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]、
    [[concepts/对称加密 AES与ChaCha20]]、[[entities/Nginx TLS 配置与证书管理实战]]。
base_confidence: 0.85
lifecycle: draft
---

# TLS 协议：握手与记录层

> 入口 [[concepts/加密算法总览与分类]] §2。本文把前面三类算法编排成真实协议。

## 1. TLS 的分层

```
应用数据
  │
  └─ 记录层 (Record Layer)：分片、压缩(已废弃)、AEAD 加密、MAC、序号防重放
        ↑ 之上才是握手/告警/应用数据等「内容类型」
```

- TLS **不压缩**（CRIME 攻击后压缩被禁）。
- 记录层用**一个对称密钥 + 每方向独立**加密；握手阶段协商密钥，之后全走记录层。

## 2. TLS 1.2 握手（2-RTT）

```
Client                                     Server
  ClientHello ───────────────────────────►  (随机数、支持的套件/曲线、key_share 可选)
  ◄─────────────────────────── ServerHello  (选定套件/曲线、随机数)
  ◄─────────────────────────── Certificate  (服务器证书链，含公钥)
  ◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊ ServerKeyExchange (ECDHE 公钥, 用证书私钥签名)
  ◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊ ClientKeyExchange (客户端 ECDHE 公钥)
  [双方算出共享秘密 → 派生对称密钥]
  Finished ─────────────────────────────►  (验证握手完整性)
  ◄─────────────────────────── Finished
  应用数据开始 (AES-GCM / ChaCha20)
```

- 1.2 默认 2 个 RTT 才发应用数据。
- 支持 **RSA 密钥传输**（无 PFS，已不推荐）或 **ECDHE**（有 PFS）。
- 证书验证依赖 [[entities/证书与 X.509 公钥基础设施实战]] 的信任链。

## 3. TLS 1.3 握手（1-RTT，大幅简化）

```
Client                                              Server
  ClientHello (key_share=客户端临时公钥, 套件) ──────►
  ◄──────────────────────── ServerHello (key_share=服务端临时公钥)
  ◄──────────────────────── EncryptedExtensions (加密的扩展)
  ◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊ Certificate + CertificateVerify (签名)
  ◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊◊ Finished (加密)
  应用数据 (从 Client 第二个 flight 即可带，1-RTT)
```

**1.3 相比 1.2 的关键变化**：

| 项 | TLS 1.2 | TLS 1.3 |
|----|---------|---------|
| 握手 RTT | 2 | **1** |
| 密钥交换 | RSA / ECDHE 均可 | **仅 ECDHE**（强制 PFS） |
| 静态 DH | 支持 | 移除 |
| 记录层加密 | 部分明文扩展 | **几乎所有握手加密**（除 ClientHello） |
| 认证套件 | RSA / ECDSA | ECDSA / Ed25519 / RSA-PSS |
| 0-RTT | 无 | **支持**（但有重放风险） |
| 废弃算法 | RC4/3DES/CBC | 一并移除，仅留 AEAD |

## 4. 密钥派生：从共享秘密到多把密钥

ECDHE 共享秘密并不直接当密钥用，而是经 HKDF（见 [[concepts/哈希函数与消息认证 HMAC]]）派生：

```
shared_secret (ECDHE)
  → early_secret (0-RTT)
  → handshake_secret → 客户端/服务端握手密钥
  → master_secret → 应用流量密钥 (client/server, 各含加密密钥+IV+序列号)
```

- **双密钥**：客户端写密钥、服务端写密钥分离，防双方互重放。
- **密钥更新**（KeyUpdate）：长连接可定期轮换流量密钥，限制单次泄露影响。

## 5. 性能与数据面优化

TLS 握手是非对称运算密集（尤其证书链验证 + ECDHE），是短连接吞吐瓶颈：

| 优化 | 原理 | 备注 |
|------|------|------|
| 会话复用 (Session ID / Ticket) | 跳过完整握手 | 1.2 主流；1.3 用 PSK |
| **0-RTT** | 客户端首个包即带数据 | TLS 1.3；**不抗重放**，仅限幂等请求 |
| TLS offload | 卸载到 NIC / 代理 | kTLS、SmartNIC、[[concepts/加密硬件加速 AES-NI与协处理器]] |
| OCSP Stapling | 服务端附证书状态 | 省去客户端 OCSP 查询 RTT |
| HTTP/2 多路复用 | 单连接多请求 | 摊薄握手成本 |

> 在反向代理（[[concepts/Nginx 架构与事件模型]]、[[entities/Nginx TLS 配置与证书管理实战]]）中，通常「边缘终止 TLS，内网明文/复用连接」以省 CPU。注意内网段仍需考虑加密（mTLS / IPsec）。

## 6. 前向保密（PFS）为什么重要

- ECDHE 每次连接用**临时**密钥对，会话结束即销毁。
- 即使服务器长期私钥日后泄露，**历史流量无法解密**（攻击者没有当时的临时私钥）。
- 没有 PFS 的 RSA 传输：拿到服务器私钥即可解密所有历史流量——这是 1.3 移除 RSA 传输的根本原因。

## 7. 常见风险

| 风险 | 说明 | 缓解 |
|------|------|------|
| 0-RTT 重放 | 攻击者可重发首个包 | 仅幂等请求 + 服务端重放缓存 |
| 证书校验不严 | 中间人 | 严格链验证 + OCSP/CRL |
| 降级攻击 | 强制 1.2/弱套件 | 禁用旧协议，启用 TLS_FALLBACK_SCSV |
| 密钥共享复用 | nonce 复用 | 每连接新 key_share |

## 参考来源

- RFC 8446 (TLS 1.3), RFC 5246 (TLS 1.2), RFC 5705 (密钥导出)
- [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]
- [[concepts/对称加密 AES与ChaCha20]]
- [[concepts/哈希函数与消息认证 HMAC]]
- [[entities/Nginx TLS 配置与证书管理实战]]
