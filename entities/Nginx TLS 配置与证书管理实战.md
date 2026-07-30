---
title: Nginx TLS 配置与证书管理实战
category: entities
tags: [nginx, tls, ssl, certificate, hsts, ocsp, pfs, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    Nginx TLS 配置实战：启用 TLS 1.3、AEAD 套件、强制 PFS
    （ECDHE 曲线 X25519/P-256）、证书链与私钥部署、OCSP Stapling、
    HSTS、会话复用/0-RTT 取舍、TLS offload 与性能（ssl_session_cache、
    keepalive、reuseport）、常见配置错误与排障。配合
    [[concepts/Nginx 架构与事件模型]]、[[concepts/TLS 协议握手与记录层]]、
    [[entities/证书与 X.509 公钥基础设施实战]]。
base_confidence: 0.8
lifecycle: draft
---

# Nginx TLS 配置与证书管理实战

> 原理见 [[concepts/TLS 协议握手与记录层]]；Nginx 框架见 [[concepts/Nginx 架构与事件模型]]。

## 1. 最小安全配置

```nginx
server {
    listen 443 ssl;
    server_name example.com;

    # 证书链（含中间证）与私钥
    ssl_certificate     /etc/nginx/tls/fullchain.pem;
    ssl_certificate_key /etc/nginx/tls/privkey.pem;

    # 协议：仅 TLS 1.2/1.3（禁用 SSLv3/TLS1.0/1.1）
    ssl_protocols TLSv1.2 TLSv1.3;

    # 套件：优先 AEAD（见 [[concepts/对称加密 AES与ChaCha20]]）
    ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:
                ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:
                ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;       # 1.3 由客户端优先级（更安全）

    # 强制前向保密：仅 ECDHE
    ssl_ecdh_curve X25519:P-256;

    # 会话复用（降握手成本，见 [[concepts/TLS 协议握手与记录层]] §5）
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;             # 严格 PFS 场景关 ticket
}
```

- `ssl_certificate` 必须是**完整链**（服务器证 + 中间证），否则部分客户端不信任。
- `ssl_ecdh_curve X25519` 优先现代曲线（见 [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]）。

## 2. OCSP Stapling（省去客户端查询）

```nginx
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/nginx/tls/chain.pem;   # 用于验证 OCSP 响应的 CA
resolver 8.8.8.8 valid=300s;
```

服务端在握手时附上证书吊销状态，客户端不必再发 OCSP 请求 → 省一个 RTT、保护隐私。

## 3. HSTS（防降级/劫持）

```nginx
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
```

> 一旦开启，浏览器在 max-age 内强制 HTTPS。preload 需提交到 HSTS 预加载列表。**谨慎**：配置错误会导致长期无法回退 HTTP。

## 4. 性能优化（数据面视角）

```nginx
# 1) 复用上游 TLS 连接（反代场景）
proxy_ssl_session_reuse on;
proxy_http_version 1.1;

# 2) 监听多队列 + reuseport（配合 [[concepts/Nginx 架构与事件模型]] §2.3）
listen 443 ssl reuseport;

# 3) 开启底层 OpenSSL 加速（AES-NI 自动；见 [[concepts/加密硬件加速 AES-NI与协处理器]]）
#    Nginx 无需特殊配置，OpenSSL 编译时启用即可

# 4) 0-RTT（TLS 1.3，仅幂等请求！有重放风险）
ssl_early_data on;        # 配合 proxy_set_header Early-Data $ssl_early_data;
```

批量小文件/短连接时，握手是非对称运算瓶颈 → 靠 **session 复用 + OCSP stapling + HTTP/2** 摊薄。

## 5. TLS 终止与内网

典型架构：边缘 Nginx/LB 终止 TLS，内网用明文或 mTLS：

```nginx
location / {
    proxy_pass http://backend;          # 内网明文（信任网络）
    # 或更安全：proxy_pass https://backend; + proxy_ssl_verify on;
}
```

- 内网不加密省 CPU，但需网络隔离；合规场景用 **mTLS**（双向证书，见 [[entities/证书与 X.509 公钥基础设施实战]]）。

## 6. 证书自动化（Let's Encrypt）

```bash
certbot --nginx -d example.com        # 自动签发+写入配置+续期
```

续期后 `nginx -s reload` 加载新证书（热加载，见 [[concepts/Nginx 架构与事件模型]] Master/Worker 平滑升级）。

## 7. 常见错误与排障

| 现象 | 原因 | 解决 |
|------|------|------|
| NET::ERR_CERT_AUTHORITY_INVALID | 缺中间证 | `ssl_certificate` 用 fullchain |
| 握手慢 | 无 session 复用 / RSA 套件 | 开 `ssl_session_cache`、用 ECDHE |
| 协议被降级 | 仍允许 TLS1.0/1.1 | `ssl_protocols TLSv1.2 TLSv1.3` |
| 私钥不匹配 | 证书与 key 不对 | `openssl x509 -noout -modulus` 比对 |
| 0-RTT 重放攻击 | 非幂等请求走 early_data | 仅幂等请求开 0-RTT + 重放缓存 |

## 排障命令

```bash
openssl s_client -connect example.com:443 -servername example.com   # 看握手/证书
openssl x509 -in cert.pem -noout -text                               # 看证书
curl -I https://example.com --tlsv1.3                                # 验证 1.3
testssl.sh example.com                                               # 全面证书/协议审计
```

## 参考来源

- Mozilla TLS 配置生成器 (ssl-config.mozilla.org)
- RFC 6797 (HSTS), RFC 6066 (OCSP Stapling)
- [[concepts/TLS 协议握手与记录层]]
- [[concepts/Nginx 架构与事件模型]]
- [[entities/证书与 X.509 公钥基础设施实战]]
