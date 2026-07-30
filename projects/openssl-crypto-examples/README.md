---
project: true
topic: 加密（AES/HMAC/ECDHE/TLS）
stack: C
deps: OpenSSL dev
run: "`bash scripts/build.sh`"
docs: "OpenSSL_BoringSSL 开发集成实战 / 加密算法总览与分类"
updated: 2026-07-30
---

# OpenSSL 加密示例工程（openssl-crypto-examples）

本目录是 [[entities/OpenSSL_BoringSSL 开发集成实战]] 中示例的**可编译**代码，配套
[[concepts/加密算法总览与分类]] 系列原理文。覆盖四类最核心的工程场景，并包含**国密**
（SM2/SM3/SM4）子目录，对应 [[entities/国密 SM2_SM3_SM4 实战]]。

| 目录 | 示例 | 对应文档 |
|------|------|---------|
| `aes_gcm/` | AES-256-GCM 加解密 + tamper 检测 | [[concepts/对称加密 AES与ChaCha20]]、[[entities/OpenSSL_BoringSSL 开发集成实战]] §1 |
| `hmac_hkdf/` | HMAC-SHA256 + HKDF 密钥派生 | [[concepts/哈希函数与消息认证 HMAC]]、实战 §2 |
| `ecdh_pfs/` | X25519 ECDHE 密钥协商（前向保密） | [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]、[[concepts/TLS 协议握手与记录层]] |
| `tls_server/` | 最小 TLS 1.3 服务端 + 客户端 | [[entities/Nginx TLS 配置与证书管理实战]]、实战 §5 |
| `gmssl/` | 国密 SM3 / SM4-GCM / SM2 示例 | [[entities/国密 SM2_SM3_SM4 实战]] |

## 目录结构

```
openssl-crypto-examples/
├── aes_gcm/aes_gcm.c
├── hmac_hkdf/hmac_hkdf.c
├── ecdh_pfs/ecdh_pfs.c
├── tls_server/tls_server.c  + tls_client.c
├── gmssl/  sm3.c  sm4_gcm.c  sm2.c
├── scripts/build.sh
└── README.md
```

## 依赖

- OpenSSL 示例（aes_gcm/hmac_hkdf/ecdh_pfs/tls_server）：OpenSSL 开发包（≥ 1.1.1，推荐 3.x）
  - Debian/Ubuntu: `apt-get install libssl-dev`
  - RHEL/CentOS:  `yum install openssl-devel`
  - macOS:        `brew install openssl`
- **国密示例（gmssl）**：需 [GmSSL](https://github.com/guanzhi/GmSSL)（OpenSSL 国密分支），
  用 `GMSL_PREFIX` 指向其安装前缀（头文件/库名与 OpenSSL 相同，必须独立前缀避免冲突）。
- C 编译器（gcc/clang）与 pkg-config

## 编译

```bash
cd Q:/AI/kb/projects/openssl-crypto-examples
bash scripts/build.sh                 # 编译全部 OpenSSL 示例 → ./build/
bash scripts/build.sh aes_gcm        # 只编译某一项
OPENSSL_PREFIX=/opt/openssl bash scripts/build.sh  # 指定非系统 OpenSSL

# 国密示例（需先安装 GmSSL）
GMSL_PREFIX=/opt/gmssl bash scripts/build.sh gmssl           # 编译全部国密
GMSL_PREFIX=/opt/gmssl bash scripts/build.sh gmssl sm2       # 只编译 sm2
```

> [!warning] 编译环境要求
> 本工程在 Windows/Git-Bash 无 OpenSSL 开发包与 POSIX 网络头，**需 Linux/macOS 编译运行**。
> 代码结构按 POSIX（`<arpa/inet.h>` 等），Windows 需用 WSL 或 MinGW 适配。

## 运行

```bash
cd build

# 1) AES-GCM：加密→解密→篡改检测
./aes_gcm

# 2) HMAC + HKDF：派生 client/server 两把方向密钥
./hmac_hkdf

# 3) ECDHE (X25519)：演示临时密钥协商得到共享秘密
./ecdh_pfs

# 4) TLS 1.3 服务端/客户端
#    先生成自签证书（见下），再起服务端，最后客户端连接
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
    -nodes -keyout server.key -out server.crt -days 365 \
    -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost"
cp server.key server.crt ../tls_server/     # 程序在 tls_server 目录读取

./tls_server 4433 &
./tls_client 127.0.0.1 4433
```

预期：服务端打印握手协议/套件，客户端打印 HTTP 响应；自签证书因 `SSL_VERIFY_NONE`
（演示用）可连通，生产应加载 CA 并开启校验（见 [[entities/证书与 X.509 公钥基础设施实战]]）。

# 5) 国密示例（需先用 GMSL_PREFIX 编译，见上）
cd build
./sm3        # SM3 摘要 + HMAC-SM3
./sm4_gcm    # SM4-GCM 加解密（国密 AEAD，类比 AES-GCM）
./sm2        # SM2 密钥生成 + 签名验签 + 公钥加密解密
```

> [!note] 国密与 NIST 的差异
> SM2 曲线为 `sm2p256v1`（**≠ NIST P-256**）；SM3 输出 256-bit 与 SHA-256 等长但值不同；
> 这些示例对应 [[entities/国密 SM2_SM3_SM4 实战]]。

## 与文档对应关系

- 常量时间/侧信道：`aes_gcm` 的 tag 比对、`hmac_hkdf` 的 `CRYPTO_memcmp` 即对应
  [[concepts/侧信道攻击与常量时间实现]]。
- 硬件加速：若 OpenSSL 编译时启用 AES-NI，上述 AES-GCM 自动受益
  （[[concepts/加密硬件加速 AES-NI与协处理器]]）。

## 排错

| 现象 | 原因 | 解决 |
|------|------|------|
| `openssl/evp.h: No such file` | 未装 libssl-dev | 装开发包 |
| `pkg-config: openssl not found` | 非系统路径 | 设 `OPENSSL_PREFIX` |
| TLS 握手失败 | 证书/私钥不匹配或缺失 SAN | 重生成带 SAN 的证书 |
| `SSL_VERIFY_NONE` 警告 | 演示关闭校验 | 生产加载 CA 并开启 |

## 参考

- [[entities/OpenSSL_BoringSSL 开发集成实战]]
- [[concepts/加密算法总览与分类]]
- [[synthesis/加密算法技术全景综述]]
