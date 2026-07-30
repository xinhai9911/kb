---
title: OpenSSL_BoringSSL 开发集成实战
category: entities
tags: [crypto, openssl, boringssl, evp, api, integration, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    OpenSSL/BoringSSL 开发集成实战：EVP 高层 API（加密/AEAD/HMAC/密钥派生）、
    正确初始化（RAND、错误处理）、证书加载与校验、TLS 客户端/服务端最小示例、
    OpenSSL 与 BoringSSL 差异、常见坑（1.1.0/3.0 API 变更、内存管理、
    常量时间比较）、国密引擎。配合 [[concepts/对称加密 AES与ChaCha20]]、
    [[concepts/TLS 协议握手与记录层]]、[[entities/国密 SM2_SM3_SM4 实战]]。
base_confidence: 0.8
lifecycle: draft
---

# OpenSSL / BoringSSL 开发集成实战

> 原理见 [[concepts/加密算法总览与分类]] 系列。本文是「动手集成」落地。

## 0. 选型：OpenSSL vs BoringSSL

| 维度 | OpenSSL | BoringSSL |
|------|---------|-----------|
| 来源 | 老牌、生态最大 | Google，源自 OpenSSL 分支 |
| API 稳定性 | 1.0.2/1.1.0/3.0 有破坏变更 | 不保证 ABI 稳定（随 Chromium 走） |
| 安全默认 | 需显式设 | 更严格默认（常量时间、去弱算法） |
| FIPS | 3.0 有 FIPS 模块 | 另有 BoringCrypto FIPS |
| 适用 | 服务端/通用 | 客户端/嵌入（Android、curl 可选） |

> 推荐：服务端用 OpenSSL 3.x（长期支持 + FIPS）；新项目优先高层 `EVP` API，避免裸 `AES_*`/`RSA_*`。

## 1. EVP 高层 API：加密（AEAD）

用 `EVP_CIPHER` + `EVP_Encrypt*` 做 AES-256-GCM（**永远 AEAD**，见 [[concepts/对称加密 AES与ChaCha20]]）：

```c
#include <openssl/evp.h>
#include <openssl/rand.h>

int aes_gcm_encrypt(const unsigned char *key,   // 32 字节
                    const unsigned char *iv,    // 12 字节 nonce
                    const unsigned char *aad, int aadlen,
                    const unsigned char *plain, int plainlen,
                    unsigned char *ct, int *ctlen,
                    unsigned char *tag) {        // 16 字节输出
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) return -1;

    EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL);
    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, 12, (void*)iv);
    EVP_EncryptInit_ex(ctx, NULL, NULL, key, iv);

    int len;
    if (aad && aadlen)
        EVP_EncryptUpdate(ctx, NULL, &len, aad, aadlen);
    EVP_EncryptUpdate(ctx, ct, &len, plain, plainlen);
    *ctlen = len;
    EVP_EncryptFinal_ex(ctx, ct + len, &len);
    *ctlen += len;

    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, 16, tag);
    EVP_CIPHER_CTX_free(ctx);
    return 0;
}
```

- **nonce 必须唯一**（见 [[concepts/对称加密 AES与ChaCha20]] §3）——用 `RAND_bytes(iv, 12)` 或计数器。
- 解密时先 `EVP_DecryptUpdate` 再 `EVP_CIPHER_CTX_ctrl(GET_TAG)` 比对，**不匹配即拒绝**。

## 2. HMAC 与 HKDF

```c
#include <openssl/hmac.h>
#include <openssl/kdf.h>

// HMAC-SHA256
unsigned char mac[32];
unsigned int maclen;
HMAC(EVP_sha256(), key, keylen, msg, msglen, mac, &maclen);

// HKDF（密钥派生，TLS 用）
EVP_PKEY_CTX *pctx = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, NULL);
EVP_PKEY_derive_init(pctx);
EVP_PKEY_CTX_set_hkdf_md(pctx, EVP_sha256());
EVP_PKEY_CTX_set1_hkdf_key(pctx, secret, secretlen);
EVP_PKEY_CTX_set1_hkdf_info(pctx, info, infolen);   // 不同用途不同 info
EVP_PKEY_derive(pctx, out, &outlen);
EVP_PKEY_CTX_free(pctx);
```

## 3. 随机数

```c
unsigned char buf[32];
RAND_bytes(buf, sizeof(buf));     // 加密用随机（必须成功）
// RAND_priv_bytes：长期密钥材料
```

> 不要自己写 PRNG，也不要用 `rand()`。OpenSSL 3.0 默认用系统熵（getrandom/rdrand）。

## 4. 证书加载与校验

```c
// 加载 CA 信任库
X509_STORE *store = X509_STORE_new();
X509_LOOKUP *lu = X509_STORE_add_lookup(store, X509_LOOKUP_file());
X509_LOOKUP_load_file(lu, "ca-bundle.pem", X509_FILETYPE_PEM);

// 校验证书链（见 [[entities/证书与 X.509 公钥基础设施实战]]）
X509_STORE_CTX *vctx = X509_STORE_CTX_new();
X509_STORE_CTX_init(vctx, store, cert, chain);
int ok = X509_verify_cert(vctx);   // 1 = 通过
```

常见坑：忘记设 `X509_V_FLAG_CRL_CHECK` 会跳过吊销检查；生产应开启 OCSP/CRL 校验。

## 5. TLS 服务端最小骨架

```c
SSL_CTX *ctx = SSL_CTX_new(TLS_method());
SSL_CTX_set_min_proto_version(ctx, TLS1_3_VERSION);     // 强制 1.3
SSL_CTX_use_certificate_chain_file(ctx, "server.pem");
SSL_CTX_use_PrivateKey_file(ctx, "server.key", SSL_FILETYPE_PEM);
SSL_CTX_set_ciphersuites(ctx, "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256");

SSL *ssl = SSL_new(ctx);
SSL_set_fd(ssl, sockfd);
SSL_accept(ssl);                       // 握手（非阻塞需处理 WANT_READ/WRITE）
SSL_write(ssl, "hello", 5);           // 应用数据（自动走记录层 AEAD）
```

- **非阻塞模式**：`SSL_accept`/`SSL_read` 返回 `WANT_READ`/`WANT_WRITE` 时，配合事件循环（epoll，参考 [[concepts/Nginx 架构与事件模型]] §2）。
- 客户端用 `SSL_connect` + `SSL_set1_host`(用于 SNI/校验主机名)。

## 6. 常见坑

| 坑 | 后果 | 解决 |
|----|------|------|
| 用裸 `AES_*`/`RSA_*` | 非常量时间/易错 | 用 `EVP_*` |
| OpenSSL 1.1.0 旧 API | 3.0 编译失败 | 迁移到 `EVP`、`SSL_CTX_new(TLS_method())` |
| 自己 `memcmp` 比 tag | 时序泄露 | 用 `CRYPTO_memcmp` |
| nonce 复用 | 明文泄露 | 每消息新 nonce |
| 不校验证书链 | 中间人 | 严格 `X509_verify_cert` + 主机名校验 |
| 内存泄漏 | 长期运行 OOM | 配对 `*_free` |

## 7. 国密引擎

OpenSSL 3.0 通过 **provider** 机制加载国密（SM2/SM3/SM4）；BoringSSL 也含实验性 SM。详见 [[entities/国密 SM2_SM3_SM4 实战]]。

## 参考来源

- OpenSSL man: EVP_EncryptInit, SSL_CTX_new, X509_verify_cert
- BoringSSL docs (boringssl.googlesource.com)
- [[concepts/对称加密 AES与ChaCha20]]
- [[concepts/TLS 协议握手与记录层]]
- [[concepts/侧信道攻击与常量时间实现]]
