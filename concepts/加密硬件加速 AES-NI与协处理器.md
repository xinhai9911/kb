---
title: 加密硬件加速 AES-NI与协处理器
category: concepts
tags: [crypto, aes-ni, hardware-accel, offload, tls-offload, nic, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    加密硬件加速：CPU 指令级（AES-NI / PCLMULQDQ / SHA-NI / ARM Crypto
    Extension）、协处理器（加解密引擎、TPM/HSM 密钥保护）、TLS offload
    （kTLS / SmartNIC / 网卡 TLS）、数据面（VPP/DPDK/Nginx）如何利用加速、
    国密硬件支持。配合 [[concepts/对称加密 AES与ChaCha20]]、
    [[concepts/CPU 指令集加速]]、[[concepts/TLS 协议握手与记录层]]。
base_confidence: 0.82
lifecycle: draft
---

# 加密硬件加速：AES-NI 与协处理器

> 入口 [[concepts/加密算法总览与分类]] §6。本文是「系统/性能」视角的核心。

## 1. 为什么需要硬件加速

纯软件加密的瓶颈：
- AES 每 16 字节块需多轮 S-box 查表 → 单核约 100–300 MB/s。
- TLS 握手的非对称运算（ECDHE + 验签）在短连接场景占满 CPU。
- 现代网卡 10/25/100 Gbps，软件 TLS 根本喂不满。

硬件加速把加密从「通用指令循环」变成「专用电路/指令」，吞吐提升 5–50 倍。

## 2. CPU 指令级加速

### 2.1 AES-NI（Intel/AMD，x86）

指令集扩展（SSE/AVX 域）：
- `AESENC` / `AESDEC`：单条指令完成 AES 一轮（SubBytes+ShiftRows+MixColumns+AddRoundKey 的硬件实现）。
- `AESKEYGENASSIST`：密钥扩展。
- 效果：AES-128 吞吐从 ~150 MB/s → **~1–10 GB/s**（单核），延迟降到纳秒级。

### 2.2 PCLMULQDQ（GHASH 加速）

AES-GCM 的认证（GHASH）是 GF(2^128) 上的多项式乘，软件慢。`PCLMULQDQ` 提供硬件 Galois 乘法，使 GCM 认证不再拖后腿。

### 2.3 SHA-NI / ARM Crypto Extension

- x86 `SHAEXT`：SHA-1/SHA-256 指令。
- ARMv8 **Cryptography Extension**：`AESE/AESMC`（AES）、`SHA256*`、`PMULL`（GHASH）——手机/ARM 服务器 TLS 加速关键。

> ChaCha20 没有专用指令，但纯 ARX 运算在没 AES-NI 的 CPU 上仍快于软件 AES——这就是它存在的工程理由（见 [[concepts/对称加密 AES与ChaCha20]] §4）。

## 3. 协处理器与专用密钥保护

| 器件 | 角色 | 用途 |
|------|------|------|
| **HSM**（硬件安全模块） | 私钥**不出硬件**，签名在内部完成 | CA 根密钥、金融合规 |
| **TPM** | 平台绑定密钥、磁盘加密 | 设备身份、BitLocker |
| **加密引擎/IPsec 协处理** | 批量对称加解密 offload | 路由器/VPN/[[20-protocols/vpp|VPP]] 数据面 |
| **SmartNIC / DPU** | 网卡内做 TLS/IPsec | 数据中心 TLS 卸载 |

关键区别：**加速**（更快算出结果）vs **密钥隔离**（私钥永不离开硬件）。HSM/TPM 主打后者——即使主机被入侵，私钥仍安全。

## 4. TLS Offload：把加密移出 CPU

```
方案 A：kTLS（内核 TLS）
  应用 write() → 内核加密 → 网卡 DMA
  加密在内核态完成，省用户态拷贝；配合 NIC 的 TLS 卸载更好。

方案 B：网卡 TLS 卸载（TLS-offload NIC）
  NIC 持有记录层密钥，硬件加解密每个 TLS 记录
  CPU 只看到明文 → 接近线速 TLS，CPU 占用骤降
  需固件支持 + kTLS 配合

方案 C：卸载到代理/SLB
  TLS 在负载均衡器终止，内网用明文或 mTLS
  见 [[entities/Nginx TLS 配置与证书管理实战]]
```

- **数据面框架**直接受益：DPDK/VPP（[[20-protocols/vpp|VPP]]）可在轮询线程里调用 AES-NI/协处理做线速 IPsec/TLS。
- 反代 Nginx（[[concepts/Nginx 架构与事件模型]]）开启 `ssl_engine` / 底层 OpenSSL 加速即可。

## 5. 在 Nginx/VPP 中的实际切入点

- **Nginx**：`ssl_protocols TLSv1.3; ssl_ciphers ...;` 选 AEAD 套件；OpenSSL 自动用 AES-NI（若编译开启）。开启 `ssl_session_cache`/`OCSP stapling` 降握手成本。详见 [[entities/Nginx TLS 配置与证书管理实战]]。
- **VPP / DPDK**：IPsec 用 AES-NI 或 crypto 加速子系统（DPSDK cryptodev）；可绑定到 QAT/网卡 crypto 队列。
- **内核**：`/proc/crypto` 查看已注册算法；`aesni_intel` 内核模块。

## 6. 国密硬件支持

国密 SM2/SM3/SM4 的硬件加速由国产 CPU（海光/飞腾/鲲鹏）和加密卡提供；SM4 有类似 AES-NI 的指令或协处理。详见 [[entities/国密 SM2_SM3_SM4 实战]]。

## 7. 选型与陷阱

| 误区 | 事实 |
|------|------|
| 有 AES-NI 就万事大吉 | GCM 还需 PCLMULQDQ；握手非对称仍是瓶颈 |
| Offload 一定安全 | 卸载后密钥进 NIC/内核，需评估密钥暴露面 |
| 加速=密钥安全 | 加速器件不保护私钥；合规用 HSM/TPM |
| 旧 CPU 也能线速 TLS | 无 AES-NI 应优先 ChaCha20-Poly1305 |

## 参考来源

- Intel AES-NI / SHA-NI 白皮书
- RFC 8749 (kTLS), 网卡 TLS offload 厂商文档
- [[concepts/CPU 指令集加速]]
- [[concepts/对称加密 AES与ChaCha20]]
- [[concepts/TLS 协议握手与记录层]]
