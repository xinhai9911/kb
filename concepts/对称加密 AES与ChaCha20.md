---
title: 对称加密 AES与ChaCha20
category: concepts
tags: [crypto, symmetric, aes, aes-ni, chacha20, gcm, aead, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    对称加密深挖：AES 结构（SubBytes/ShiftRows/MixColumns/AddRoundKey）、密钥
    长度（128/192/256）、模式（ECB 禁用/CBC/CTR/GCM/ChaCha20-Poly1305），
    AEAD 认证加密原理、Nonce 复用灾难、ChaCha20 在无 AES 指令设备上的优势、
    与硬件加速（AES-NI）的关系。配合 [[concepts/加密算法总览与分类]]、
    [[concepts/加密硬件加速 AES-NI与协处理器]]。
base_confidence: 0.85
lifecycle: draft
---

# 对称加密：AES 与 ChaCha20

> 入口 [[concepts/加密算法总览与分类]] §4。本文聚焦「对称批量加密」的内部结构与工程陷阱。

## 1. AES 是什么

AES（Advanced Encryption Standard，FIPS 197）是**分组密码**：固定处理 128-bit（16 字节）明文块，密钥 128/192/256 bit。所谓 AES-128 / AES-256 仅指密钥长度，块大小不变。

### 1.1 轮结构（SPN 网络）

加密分多轮（128 密钥 10 轮、192 为 12 轮、256 为 14 轮），每轮四个变换：

```
State(4x4 字节矩阵)
  ├─ SubBytes      : 每个字节经 S-box 非线性替换（唯一非线性层，抗线性/差分分析）
  ├─ ShiftRows     : 行循环移位（扩散）
  ├─ MixColumns    : 列混合（GF(2^8) 上矩阵乘，强扩散）
  └─ AddRoundKey   : 与轮密钥异或（密钥混入）
最后一轮省略 MixColumns。
```

- **S-box** 是唯一非线性来源，精心设计为抗差分/线性密码分析，同时可代数化（AES 的弱点之一被用于侧信道）。
- 解密是逆向变换；AES 的**等效解密结构**让软硬件可复用同一电路/指令。

## 2. 模式（mode）：安全语义由模式决定，不止算法

AES 本身只加密一个块。任意长度报文需要模式：

| 模式 | 并行加密 | 并行解密 | 完整性 | 头注释 |
|------|---------|---------|--------|--------|
| ECB | ✓ | ✓ | ✗ | **禁用**：相同明文块→相同密文块 |
| CBC | ✗（依赖前块） | ✓ | ✗ | IV 必须随机且不可预测 |
| CTR | ✓ | ✓ | ✗ | 变成流密码，IV=nonce||counter |
| GCM | ✓ | ✓（解密需认证） | ✓ AEAD | 计数器模式 + GHASH 认证 |
| ChaCha20-Poly1305 | ✓ | ✓ | ✓ AEAD | 流密码 + Poly1305 MAC |

**关键工程原则**：永远用 AEAD（GCM 或 ChaCha20-Poly1305），不要自己「先加密后 MAC」。

## 3. AEAD 的工作原理（以 AES-GCM 为例）

```
加密：
  nonce (12B, 必须唯一) + 明文 + AAD(关联数据,如包头)
    → AES-CTR 加密明文
    → GHASH 计算认证标签 (16B)
  输出 = 密文 || 标签

解密：
  用同一 nonce 解密 → 重算 GHASH 标签 → 与附带标签比对
  不匹配 → 拒绝（防篡改）
```

- **Nonce 复用是灾难性错误**：同一密钥下 nonce 重复，攻击者可恢复明文甚至伪造标签。Nonce 通常 12 字节、计数器式单调递增。
- **AAD**（Additional Authenticated Data）：不参与加密但参与认证，常用于保护报文头/长度字段。

## 4. ChaCha20-Poly1305：没有 AES 指令时的首选

ChaCha20 是 **Salsa20 的改良流密码**，基于 32-bit 加法/异或/旋转（ARX），无需查表、无 S-box：

- 在**没有 AES-NI** 的 CPU（老旧 x86、ARM 低端、微服务容器）上，ChaCha20 比 AES 快 2–5 倍，且天然**抗时序侧信道**（运算时间不依赖数据）。
- Poly1305 是一次性 MAC，与 ChaCha20 组合为 AEAD（RFC 8439），是 TLS 1.3 的标准套件之一。
- 移动端 / 边缘设备首选 `TLS_AES_128_GCM_SHA256` 与 `TLS_CHACHA20_POLY1305_SHA256` 双套件，由客户端优先级决定。

## 5. 性能与硬件加速的边界

- AES-NI（Intel/AMD）把「单块加解密」做成 1–2 条指令（`AESENC`/`AESDEC`），吞吐从 ~100 MB/s 提升到 ~1–10 GB/s。
- 但 **GCM 的 GHASH（认证）没有免费指令**（部分平台有 `PCLMULQDQ`  Galois 乘加速）；ChaCha20 纯算术，反而适合无专用指令的场景。
- 网络数据面（[[20-protocols/vpp|VPP]]、DPDK、[[concepts/Nginx 架构与事件模型]]）常把 TLS 加解密 offload 到 NIC（TLS 卸载 / kTLS），让 CPU 只处理应用逻辑。

## 6. 常见实现陷阱

| 陷阱 | 后果 | 正确做法 |
|------|------|---------|
| Nonce 复用 | 明文泄露/可伪造 | 每密钥每消息唯一 nonce，计数器式 |
| 用 ECB | 结构暴露 | 用 GCM/ChaCha20-Poly1305 |
| 自己拼 encrypt+MAC | 长度/填充 oracle | 直接用 AEAD |
| IV 用固定值 | CBC 可攻击 | CBC IV 必须随机不可预测 |
| 密钥硬编码 | 全盘泄露 | KMS / 环境变量 / 密钥协商 |

## 参考来源

- FIPS 197 (AES), NIST SP 800-38D (GCM), RFC 8439 (ChaCha20-Poly1305)
- [[concepts/加密算法总览与分类]]
- [[concepts/加密硬件加速 AES-NI与协处理器]]
- [[concepts/侧信道攻击与常量时间实现]]
