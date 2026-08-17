---
title: 认证授权 OAuth2 OIDC JWT
category: concepts
tags: [auth, oauth2, oidc, jwt, token, rbac, zero-trust, active]
created: 2026-08-12
updated: 2026-08-17
summary: >-
    认证授权 OAuth2/OIDC/JWT：认证 vs 授权、Cookie/Session 与 Token(JWT) 对比、OAuth2 四种授权
    （授权码+PKCE 完整流程图）、OIDC 的 id_token、JWT 结构/签名/过期/刷新、Token 吊销与自省、
    K8s RBAC 与 ServiceAccount 衔接（[[concepts/Kubernetes 安全模型]]）、K8s OIDC 集成、零信任。
    衔接 [[concepts/容器安全]]、[[concepts/分布式系统基础]]。
base_confidence: 0.87
lifecycle: review
sources: []
---

# 认证授权 OAuth2 OIDC JWT

> 应用级身份是库里安全域的缺口：已有容器/K8s 加固（[[concepts/容器安全]]、[[concepts/Kubernetes 安全模型]]）、
> 密码学（[[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]），但缺「用户/服务怎么证明身份、拿到什么权限」。

---

## 1. 认证 vs 授权

- **认证（Authentication, 你是谁）**：登录、证明身份（密码/OTP/证书）。
- **授权（Authorization, 你能做什么）**：基于身份给权限（RBAC）。
- 常见混淆：拿到 JWT ≠ 有权限，JWT 只证明「谁」，权限由资源服务端 RBAC 判定。

---

## 2. 会话 vs Token

| 方案 | 机制 | 优点 | 缺点 |
|---|---|---|---|
| Cookie+Session | 服务端存 session | 易吊销 | 需共享存储、跨域难、扩缩复杂 |
| **JWT (Token)** | 自包含签名令牌 | 无状态、跨服务、移动/API 友好 | 吊销难（短 TTL+刷新）、payload 别放大 |

---

## 3. OAuth2（授权框架）

给「第三方应用」有限度访问「用户资源」，不发密码。常见四种授权：

| 授权类型 | 场景 |
|---|---|
| **授权码 + PKCE** | 主流（Web/移动 App），防授权码拦截 |
| 客户端凭证 | 服务到服务（机对机） |
| 密码（弃用） | 第一方原生 App，已不推荐 |
| 隐式（弃用） | SPA，已被 PKCE 取代 |

> PKCE：用 `code_challenge` 把授权码与客户端绑定，公共客户端（无法藏 secret）也能安全用授权码流。

### 授权码 + PKCE 完整流程

```
用户 ──▶ 第三方App ──▶ 授权服务器
         │                │
    ① 生成 code_verifier (随机字符串)
       计算 code_challenge = SHA256(code_verifier)
         │
         │  ② 重定向到授权服务器
         │  GET /authorize?
         │    response_type=code&
         │    client_id=xxx&
         │    redirect_uri=xxx&
         │    scope=openid profile&
         │    code_challenge=xxx&          ← PKCE
         │    code_challenge_method=S256
         │───────────────────────────────▶│
         │                                │ 用户登录 + 授权
         │◀────── 重定向回 App ───────────│
         │       ?code=AUTH_CODE
         │
    ③ 用 code 换 token
       POST /token
         grant_type=authorization_code&
         code=AUTH_CODE&
         code_verifier=原始字符串          ← PKCE 验证
         │───────────────────────────────▶│
         │◀────── 返回 tokens ────────────│
         │   { access_token, id_token,    │
         │     refresh_token }            │
```

> [!note] PKCE 的意义
> 公共客户端（SPA/移动 App）无法安全存储 client_secret，授权码可能被恶意 App 拦截。PKCE 用「挑战-应答」绑定：只有发起者知道 `code_verifier`，拦截到 `code` 也没用。

---

## 4. OIDC（身份层）

OIDC = 在 OAuth2 上加**身份**：除 access_token 外发 **id_token（JWT）**，含 `sub`/签发者/过期。SSO（单点登录）基于此：一个 IdP（如 Keycloak）发 token，多个业务系统信任。

---

## 5. JWT 结构与实践

```
header.payload.signature   (base64url 三段)
header:  {alg: RS256, typ: JWT}
payload: {sub, iss, aud, exp, scope, ...}   # 别放敏感明文
signature: 对前两段用私钥签名（RS256）或对称（HS256）
```

- **校验**：验签名 + `exp` 未过 + `aud`/`iss` 匹配。
- **刷新**：access_token 短（15min），refresh_token 长（存服务端可吊销）。
- **算法陷阱**：服务端必须**固定允许算法**（防 `alg: none` / RS256→HS256 密钥混淆攻击，[[concepts/侧信道攻击与常量时间实现]] 同类思维）。

---

## 6. Token 吊销与自省

JWT 是自包含的，发出去就无法「收回」（直到过期）。吊销方案：
- **短 TTL + 刷新**：access_token 15min，refresh_token 可吊销（存服务端黑名单）。
- **Token Introspection**（RFC 7662）：资源服务器调用授权服务器验证 token 有效性（增加延迟，但实时）。
- **Token Revocation**（RFC 7009）：客户端调用 `/revoke` 端点吊销 refresh_token，连带所有 access_token 失效。
- **Backchannel Logout**（OIDC）：IdP 主动通知所有已登录客户端登出。

---

## 7. 与 K8s / 零信任衔接

- **K8s 身份**：ServiceAccount 发 token（[[concepts/Kubernetes 安全模型]] 的 SA/RBAC）；工作负载身份用 SPIFFE/mTLS 做服务间认证（[[entities/Cilium 容器网络]]）。
- **零信任**：不认网络位置，每个请求都验身份+权限（[[concepts/容器安全]] 的默认拒绝网络）。
- **密钥**：JWT 签名私钥用 KMS/Vault 管（[[concepts/容器安全]] 镜像/密钥供应链）。

### K8s OIDC 集成

K8s API Server 支持 OIDC 认证（`--oidc-issuer-url`），让外部 IdP（Keycloak/Dex）发放的 token 直接用于 kubectl：
```bash
# 配置 API Server
--oidc-issuer-url=https://dex.example.com/dex
--oidc-client-id=kubernetes
--oidc-username-claim=email
--oidc-groups-claim=groups

# kubectl 用 oidc-token 插件获取 token
kubectl config set-credentials oidc-user \
  --exec-api-version=client.authentication.k8s.io/v1beta1 \
  --exec-command=kubelogin \
  --exec-arg=get-token \
  --exec-arg=--oidc-issuer-url=https://dex.example.com/dex
```

> 登录后拿到的 JWT token 会被 K8s 验证签名和 claims，再映射到 RBAC（`ClusterRoleBinding` 的 `subjects` 指向 OIDC user/group）。

---

## 参考链接

**库内双链**
- [[concepts/Kubernetes 安全模型]] — K8s RBAC/SA/SPIFFE
- [[concepts/容器安全]] — 零信任/密钥管理
- [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]] — JWT 签名算法基础
- [[concepts/侧信道攻击与常量时间实现]] — 算法混淆类攻击防御思维
- [[concepts/分布式系统基础]] — 服务身份/信任的分布式背景
- [[concepts/Redis 缓存与数据结构]] — Token 黑名单/刷新令牌存储（Cache-Aside 模式）
- [[entities/GitOps 与 ArgoCD 实战]] — ArgoCD SSO 集成（OIDC 同一机制）

**外部资料**
- OAuth 2.0 / OIDC 规范（RFC 6749 / OpenID Connect）
- JWT 规范（RFC 7519）、Auth0/Keycloak 文档
