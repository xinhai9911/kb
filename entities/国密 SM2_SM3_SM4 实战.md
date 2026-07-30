---
title: 国密 SM2_SM3_SM4 实战
category: entities
tags: [crypto, 国密, sm2, sm3, sm4, gmssl, compliance, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    国密算法实战：SM2（椭圆曲线公钥，签名/密钥交换，类似 ECDSA/ECDH）、
    SM3（256-bit 哈希，类似 SHA-256）、SM4（128-bit 分组密码，类似 AES，
    CBC/GCM 模式）、TLCP（国密 TLS 协议，双证书体系）、实现库
    （GmSSL/BabaSSL/OpenSSL 国密 provider）、合规场景与互通陷阱。
    配合 [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]、
    [[concepts/哈希函数与消息认证 HMAC]]、[[concepts/对称加密 AES与ChaCha20]]。
base_confidence: 0.78
lifecycle: draft
---

# 国密 SM2 / SM3 / SM4 实战

> 国密是国家密码管理局发布的商用密码算法族。本文落地「如何用」，原理对照见对应概念文。

## 1. 三种算法定位

| 国密 | 类型 | 类比 | 用途 |
|------|------|------|------|
| **SM2** | 椭圆曲线公钥 | ECDSA / ECDH（但用国密曲线 sm2p256v1） | 签名、密钥交换、加密 |
| **SM3** | 哈希 256-bit | SHA-256 | 摘要、HMAC、签名哈希 |
| **SM4** | 分组密码 128-bit | AES | 对称加密（CBC/ECB/GCM） |

> 注意：SM2 曲线 `sm2p256v1` **不同于** NIST P-256，不能混用。实现/库必须支持国密曲线。

## 2. SM3（哈希）

与 SHA-256 输出同为 256-bit，内部结构不同（含消息扩展 + 32 轮）。用途同 SHA-256：数据完整性、签名哈希、HMAC-SM3。

```c
// GmSSL 高层接口
#include <openssl/sm3.h>
unsigned char out[SM3_DIGEST_LENGTH];
SM3(data, datalen, out);
```

## 3. SM4（对称）

128-bit 分组、32 轮非线性迭代；模式：ECB（不推荐）、CBC、CTR、**SM4-GCM**（AEAD，等同 AES-GCM 思路）。

```c
#include <openssl/evp.h>
// 与 AES-GCM 调用方式一致，仅替换算法为 EVP_sm4_gcm()
EVP_EncryptInit_ex(ctx, EVP_sm4_gcm(), NULL, NULL, NULL);
```

- 国产 CPU（海光/飞腾/鲲鹏）与加密卡提供 SM4 硬件加速，类似 AES-NI（见 [[concepts/加密硬件加速 AES-NI与协处理器]]）。
- **绝不用 ECB**；优先 SM4-GCM（AEAD）。

## 4. SM2（公钥）

基于椭圆曲线离散对数，曲线 `sm2p256v1`。三种用法：

| 用法 | 类比 | 函数 |
|------|------|------|
| 签名 | ECDSA | `SM2_sign` / `EVP_PKEY_sign` |
| 密钥交换 | ECDH | SM2 协商（含双方 ID 的 Z 值） |
| 公钥加密 | RSA-OAEP | `SM2_encrypt` |

```c
// 签名（Z 值含用户 ID，影响签名）
EVP_PKEY *pkey = ...; // SM2 密钥
EVP_MD_CTX *mdctx = EVP_MD_CTX_new();
EVP_DigestSignInit(mdctx, NULL, EVP_sm3(), NULL, pkey);
EVP_DigestSign(mdctx, sig, &siglen, msg, msglen);
```

> SM2 签名用 SM3 做哈希（算法绑定），与 ECDSA-P256+SHA256 不同。

## 5. TLCP（国密 TLS，GB/T 38636）

国密 TLS 称为 **TLCP**（原 GM/T 0024），关键特征：**双证书体系**。

```
TLCP 握手：
  - 签名证书（长期，SM2，用于认证/签名握手）
  - 加密证书（长期，SM2，用于协商对称密钥）
  两本证书 + 两套密钥 —— 与标准 TLS 单证书不同
  - 密钥交换用 SM2（而非 ECDHE/RSA）
  - 记录层用 SM4（+ SM3 做 MAC，或 SM4-GCM）
```

- 为什么双证书：分离「身份认证」与「密钥加密」，符合国内合规与审计要求。
- 互通前提：客户端/服务端**都支持 TLCP**，标准 TLS 栈默认不支持，需用 GmSSL/BabaSSL/国密 OpenSSL provider。

## 6. 实现库选型

| 库 | 说明 |
|----|------|
| **GmSSL** | 国密开源实现，API 接近 OpenSSL，支持 SM2/3/4 + TLCP |
| **BabaSSL** | 阿里维护，源自 BoringSSL，支持国密与 TLCP |
| **OpenSSL 国密 provider** | OpenSSL 3.0 通过 provider 加载国密（需编译启用） |
| 商用 HSM/加密机 | 金融/政务合规，私钥不出硬件 |

## 7. 合规与陷阱

| 场景 | 要求 |
|------|------|
| 政务/金融内网 | 强制国密（SM2/3/4 + TLCP） |
| 跨境/对外 | 通常标准 TLS 1.3 |
| 混合部署 | 双栈：同时支持标准 TLS 与 TLCP，按客户端能力协商 |

常见坑：
- 把 SM2 曲线当 P-256 用 → 握手失败。
- 单证书当 TLCP 双证书 → 不合规/连不上。
- SM3 当 SHA-256 直接替换（输出长度同但值不同）→ 校验失败。
- 标准 nginx/OpenSSL 默认**不含** TLCP，需换库或 provider。

## 8. 可编译示例

`projects/openssl-crypto-examples/gmssl/` 提供 SM3 / SM4-GCM / SM2 三个可直接用
GmSSL 编译运行的示例（API 与 OpenSSL 3.x 的 EVP 接口一致）：

```bash
cd Q:/AI/kb/projects/openssl-crypto-examples
GMSL_PREFIX=/opt/gmssl bash scripts/build.sh gmssl
./build/sm3 && ./build/sm4_gcm && ./build/sm2
```

详见 [[projects/openssl-crypto-examples/README|OpenSSL 示例工程 README]]。

## 参考来源

- GB/T 32918 (SM2), GB/T 32905 (SM3), GB/T 32907 (SM4), GB/T 38636 (TLCP)
- GmSSL / BabaSSL 文档
- [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]
- [[concepts/哈希函数与消息认证 HMAC]]
- [[concepts/对称加密 AES与ChaCha20]]
- [[projects/openssl-crypto-examples/README|OpenSSL/GmSSL 示例工程]]
