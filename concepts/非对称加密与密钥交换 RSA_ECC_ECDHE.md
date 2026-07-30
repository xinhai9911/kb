---
title: 非对称加密与密钥交换 RSA_ECC_ECDHE
category: concepts
tags: [crypto, rsa, ecc, ecdhe, dh, key-exchange, pfs, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    非对称加密与密钥交换：RSA 原理与填充（PKCS#1 v1.5 风险 / OAEP）、
    ECC 椭圆曲线（secp256r1/P-256、X25519、Ed25519）、
    DH/ECDH 密钥协商、ECDHE 前向保密（PFS）、RSA vs ECDHE 在 TLS 中的角色、
    数字签名（ECDSA/EdDSA）。配合 [[concepts/加密算法总览与分类]]、
    [[concepts/TLS 协议握手与记录层]]。
base_confidence: 0.85
lifecycle: draft
---

# 非对称加密与密钥交换：RSA / ECC / ECDHE

> 入口 [[concepts/加密算法总览与分类]] §3。本文聚焦「慢但解决密钥分发」的非对称体系。

## 1. 非对称加密解决什么问题

对称加密快，但**如何把密钥安全交给对方**是难题（密钥分发问题）。非对称用**密钥对**：

- 公钥公开，可自由分发；私钥保密。
- 用公钥加密 → 只有对应私钥能解（机密性）。
- 用私钥签名 → 任何人有公钥可验（认证+不可否认）。

非对称**只用于小数据**（协商对称密钥、签证书），绝不批量加密。

## 2. RSA

基于大整数分解难题：n = p·q，公钥 (e, n)，私钥 (d, n)。

```
加密：c = m^e mod n
解密：m = c^d mod n
签名：s = m^d mod n   （对消息哈希签名）
验签：m == s^e mod n
```

### 2.1 填充是 RSA 的安全生命线

**裸 RSA（教科书式）不安全**，必须填充：

| 填充 | 状态 | 风险 |
|------|------|------|
| PKCS#1 v1.5 | 老旧 | Bleichenbacher 百万消息攻击（BB'06/ROBOT）→ 可解密 |
| **OAEP** | 推荐 | 带随机化，抗选择密文攻击 |
| PSS（签名） | 推荐 | 概率化签名，比 PKCS#1 v1.5 签名更强 |

> 工程结论：**RSA 必须用 RSA-OAEP 加密、RSA-PSS 签名**。新系统优先 ECC，避免 RSA。

### 2.2 RSA 的退场

- 密钥短（1024/2048）已不够；建议 ≥3072 bit。
- 运算慢（比 ECC 慢一个数量级），且**不支持前向保密**（私钥泄露则历史流量可解密）。
- TLS 1.3 **已移除 RSA 密钥传输**，仅保留 RSA 用于证书签名（且推荐 ECDSA/EdDSA）。

## 3. 椭圆曲线密码 ECC

基于椭圆曲线离散对数难题（ECDLP），**相同安全强度下密钥短得多**：

| 曲线 | 密钥 | 等价 RSA |
|------|------|---------|
| NIST P-256 (secp256r1) | 256 bit | ~3072 bit |
| P-384 | 384 bit | ~7680 bit |
| **Curve25519 / X25519** | 256 bit | ~3072 bit | 现代、无参数陷阱 |
| **Ed25519** | 256 bit | 签名，快且安全 |

ECC 优势：密钥短 → 握手数据小、计算快、适合移动/IoT。

### 3.1 命名对照

- **ECDSA**：基于 ECC 的数字签名（P-256 上签名）——证书标配。
- **ECDH / ECDHE**：基于 ECC 的密钥协商。带 **E**（Ephemeral）表示用临时密钥对 → 前向保密。
- **X25519**：ECDH 的现代曲线实现，用于密钥交换。
- **Ed25519**：EdDSA 在 Curve25519 上的签名实现。

## 4. Diffie-Hellman 与密钥协商

DH 让双方**在不安全信道上各自生成公私钥、交换公钥，算出同一个共享秘密**，窃听者无法推算：

```
Alice: a 随机 → A = g^a mod p   发给 Bob
Bob:   b 随机 → B = g^b mod p   发给 Alice
共享:  s = B^a = A^b = g^(ab) mod p
```

- **静态 DH**（长期密钥）：密钥固定，无前向保密。
- **ECDHE**（临时密钥）：每次连接重生密钥对 → **前向保密（PFS）**：即使服务器私钥日后泄露，历史会话仍安全。

> 现代 TLS 强制 ECDHE：**没有 PFS 的套件视为不合格**。

## 5. 数字签名：认证的核心

| 算法 | 用途 | 备注 |
|------|------|------|
| RSA-PSS | 证书/文档签名 | 配 RSA 公钥 |
| **ECDSA P-256** | 证书签名主流 | 需良好随机数 |
| **Ed25519** | 现代签名 | 确定性（不需 RNG），快 |

签名流程：`签名 = Sign(private_key, Hash(message))`；验证：`Verify(public_key, 签名, Hash(message))`。

ECDSA 的隐患：随机数 k **重用或泄露**会直接推出私钥（Sony PS3 事故、比特币漏洞）。Ed25519 用确定性 k 规避。

## 6. 在 TLS 中的角色分工

```
TLS 握手：
  1. ClientHello/ServerHello 协商曲线 (X25519 / P-256)
  2. ECDHE：双方交换临时公钥 → 算出共享秘密 (master secret)
  3. 服务器用证书里的公钥 (ECDSA/RSA) 签名握手 → 客户端验签确认身份
  4. 共享秘密派生对称密钥 → 记录层用 AES-GCM / ChaCha20
```

- **密钥交换用 ECDHE**（提供 PFS）
- **身份认证用证书签名**（ECDSA/Ed25519/RSA 仅签名不传输）
- RSA 作为密钥传输在 TLS 1.3 已删除

## 7. 性能视角

- 单次 ECDHE P-256 握手约 0.5–2 ms CPU；RSA-2048 签名约 0.2–1 ms，验签更快。
- 大量短连接时握手是非对称运算瓶颈 → 用 **session 复用 / 0-RTT / TLS offload**（见 [[concepts/TLS 协议握手与记录层]] §5、[[entities/Nginx TLS 配置与证书管理实战]]）。
- X25519/Ed25519 比 NIST 曲线更快且在实现上更不易出错（常量时间天然易做）。

## 参考来源

- NIST SP 800-56A (密钥协商), FIPS 186-4 (DSA/ECDSA)
- RFC 7748 (Curve25519/X25519), RFC 8032 (Ed25519)
- [[concepts/加密算法总览与分类]]
- [[concepts/TLS 协议握手与记录层]]
- [[concepts/侧信道攻击与常量时间实现]]
