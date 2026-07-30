---
title: 证书与 X.509 公钥基础设施实战
category: entities
tags: [crypto, x509, pki, certificate, ca, csr, mtls, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    X.509 证书与 PKI 实战：证书结构（主体/ issuer/ 公钥/ 扩展/SAN）、
    证书链与信任锚、CSR 生成与 CA 签发（自签/中间 CA）、
    CRL/OCSP 吊销、mTLS 双向认证、密钥管理与轮换、常见陷阱
    （SAN 缺失、私钥泄露、链不完整）。配合
    [[concepts/TLS 协议握手与记录层]]、[[entities/Nginx TLS 配置与证书管理实战]]、[[entities/国密 SM2_SM3_SM4 实战]]。
base_confidence: 0.8
lifecycle: draft
---

# 证书与 X.509 公钥基础设施实战

> TLS 握手靠证书建立信任（[[concepts/TLS 协议握手与记录层]] §2/§3）。本文落地 PKI 操作。

## 1. X.509 证书是什么

证书 = **公钥 + 身份 + 签发者签名**，把「公钥」与「域名/组织」绑定：

```
Certificate:
  Version / Serial Number
  Signature Algorithm (ECDSA-SHA256 / SM3 ...)
  Issuer        (签发 CA 的可分辨名)
  Validity      (Not Before / Not After)
  Subject       (持有者 DN)
  Subject Public Key Info (算法 + 公钥)
  Extensions:
    - Subject Alternative Name (SAN): 域名/IP 列表 ★现代必须
    - Key Usage / Extended Key Usage (签名/TLS server/auth)
    - Basic Constraints (是否为 CA)
    - CRL/OCSP 分发点
  Signature     (Issuer 用其私钥对上面内容签名)
```

> **SAN 取代了 CN**：现代客户端只看 SAN，不信任 Common Name。没 SAN 的证书会被拒。

## 2. 信任链

```
根 CA (自签, 离线保存, 内置浏览器/OS 信任库)
  └─ 中间 CA (由根签发, 实际签发服务器证)
       └─ 服务器证书 (example.com, 由中间 CA 签发)
```

- 客户端内置**根 CA 列表**（信任锚）。验证：用根公钥验证中间证签名，再用中间证验证服务器证签名。
- Nginx 的 `ssl_certificate` 必须含**服务器证 + 中间证**（fullchain），让客户端能一路验到信任根。

## 3. 生成 CSR 与签发

```bash
# 1) 生成私钥 + CSR（2048/3072 RSA 或 P-256/ECDSA）
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
    -keyout example.key -out example.csr \
    -subj "/CN=example.com" -addext "subjectAltName=DNS:example.com,DNS:www.example.com"

# 2) CA 签发（或用 Let's Encrypt / 内部 CA）
openssl x509 -req -in example.csr -CA intermediate.crt -CAkey intermediate.key \
    -CAcreateserial -out example.crt -days 365 \
    -extfile <(printf "subjectAltName=DNS:example.com")

# 3) 验证链
openssl verify -CAfile fullchain.pem example.crt
```

- 用 ECDSA P-256 证书：握手更快、证书更小（见 [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]）。
- 私钥权限 `600`，绝不进版本库/镜像。

## 4. 自签与内部 CA

```bash
# 根 CA（自签）
openssl req -x509 -newkey rsa:4096 -nodes -keyout root.key -out root.crt -days 3650

# 中间 CA（由根签发，Basic Constraints CA:TRUE）
openssl x509 -req -in int.csr -CA root.crt -CAkey root.key -out int.crt ...
```

内部服务（k8s、微服务 mTLS）常用**私有 CA** + 自动签发（如 vault、cert-manager）。

## 5. 吊销：CRL 与 OCSP

证书泄露/过期前需吊销：
- **CRL**：证书吊销列表，客户端定期拉取（笨重）。
- **OCSP**：实时查询单张证书状态（Nginx 用 OCSP Stapling，见 [[entities/Nginx TLS 配置与证书管理实战]] §2）。
- **OCSP Must-Staple**：证书扩展强制 stapling，防 OCSP 劫持。

## 6. mTLS（双向认证）

不仅客户端验服务端，服务端也验客户端证书：

```nginx
server {
    listen 443 ssl;
    ssl_certificate     server.crt;
    ssl_certificate_key server.key;
    ssl_client_certificate /etc/nginx/ca-client.crt;  # 信任的客户端 CA
    ssl_verify_client on;                              # 强制验客户端证
    # 在应用里读 $ssl_client_cert / $ssl_client_verify
}
```

场景：服务间零信任（SPIFFE/mTLS）、API 强身份、设备准入。

## 7. 密钥管理与轮换

- **轮换**：证书到期前换新密钥对 + 重签（cert-manager/vault 自动）。旧证保留短期以免中断。
- **HSM**：高价值 CA 私钥存 HSM，签名在硬件内（见 [[concepts/加密硬件加速 AES-NI与协处理器]] §3）。
- **泄露响应**：立即吊销 + 轮换；HSM 可使泄露影响限于已签名证书。

## 8. 常见陷阱

| 陷阱 | 后果 | 解决 |
|------|------|------|
| 缺 SAN | 浏览器报错 | CSR 加 subjectAltName |
| 链不完整 | 部分客户端不信任 | 用 fullchain |
| 私钥泄露 | 可伪造身份 | 吊销 + 轮换 + HSM |
| 自签根未被信任 | 连接失败 | 客户端导入根 / 用公共 CA |
| 证书过期 | 服务中断 | 监控 + 自动续期（certbot/cert-manager） |

## 参考来源

- RFC 5280 (X.509), RFC 6962 (CT 证书透明度)
- OpenSSL req/x509/ca 手册
- [[concepts/TLS 协议握手与记录层]]
- [[entities/Nginx TLS 配置与证书管理实战]]
- [[entities/国密 SM2_SM3_SM4 实战]]
