#!/usr/bin/env bash
#
# build.sh — 编译 openssl-crypto-examples 下的示例
#
# OpenSSL 示例（aes_gcm/hmac_hkdf/ecdh_pfs/tls_server）：
#   依赖系统 OpenSSL 开发包（>= 1.1.1，推荐 3.x）
#     Debian/Ubuntu: apt-get install libssl-dev
#     RHEL/CentOS:  yum install openssl-devel
#     macOS:        brew install openssl
#   指定非系统 OpenSSL：OPENSSL_PREFIX=/opt/openssl ./scripts/build.sh
#
# 国密示例（gmssl：sm3/sm4_gcm/sm2）：
#   依赖 GmSSL（OpenSSL 国密分支）。用 GMSL_PREFIX 指向其安装前缀：
#     GMSL_PREFIX=/opt/gmssl ./scripts/build.sh gmssl
#   （GmSSL 头文件/库名与 OpenSSL 相同，故用独立前缀避免与系统 OpenSSL 冲突）
#
# 用法：
#   ./scripts/build.sh                 # 编译全部 OpenSSL 示例（不含国密）
#   ./scripts/build.sh aes_gcm        # 只编译某一个
#   ./scripts/build.sh gmssl          # 编译全部国密示例（需 GMSL_PREFIX）
#   ./scripts/build.sh gmssl sm3      # 只编译某一个国密示例
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$HERE/build"
mkdir -p "$BUILD"

CC="${CC:-cc}"

# 计算 OpenSSL 编译/链接参数（优先 pkg-config）
get_ossl_flags() {
    local pfx="${OPENSSL_PREFIX:-}"
    if [ -n "$pfx" ]; then
        echo "-I$pfx/include -L$pfx/lib -lssl -lcrypto"
    elif command -v pkg-config >/dev/null 2>&1 && pkg-config --exists openssl; then
        echo "$(pkg-config --cflags openssl) $(pkg-config --libs openssl)"
    else
        echo "-lssl -lcrypto"
    fi
}

# 计算 GmSSL 编译/链接参数（必须显式前缀，避免误链系统 OpenSSL）
get_gmssl_flags() {
    local pfx="${GMSL_PREFIX:-}"
    if [ -z "$pfx" ]; then
        echo "ERROR: 编译国密示例需设置 GMSL_PREFIX=/path/to/gmssl" >&2
        exit 1
    fi
    echo "-I$pfx/include -L$pfx/lib -lssl -lcrypto"
}

compile() {
    local flags="$1" dir="$2" src="$3" out="$4"
    echo "==> 编译 $dir/$src"
    # tls_server/tls_client 需要 pthread（及网络库，部分平台）
    $CC $flags -O2 -Wall "$HERE/$dir/$src" -o "$BUILD/$out" -lpthread
}

TARGET="${1:-all}"
SUB="${2:-}"

# ---- 国密目标 ----
if [ "$TARGET" = "gmssl" ]; then
    FLAGS="$(get_gmssl_flags)"
    if [ -z "$SUB" ] || [ "$SUB" = "all" ]; then
        compile "$FLAGS" gmssl sm3.c      sm3
        compile "$FLAGS" gmssl sm4_gcm.c  sm4_gcm
        compile "$FLAGS" gmssl sm2.c      sm2
    else
        case "$SUB" in
            sm3)     compile "$FLAGS" gmssl sm3.c      sm3 ;;
            sm4_gcm) compile "$FLAGS" gmssl sm4_gcm.c  sm4_gcm ;;
            sm2)     compile "$FLAGS" gmssl sm2.c       sm2 ;;
            *) echo "未知国密目标: $SUB (可选: sm3 sm4_gcm sm2)"; exit 1 ;;
        esac
    fi
    echo "==> 产物在 $BUILD:"
    ls -1 "$BUILD"
    echo "==> 完成。国密示例运行见 README.md"
    exit 0
fi

# ---- OpenSSL 目标 ----
FLAGS="$(get_ossl_flags)"

if [ "$TARGET" = "all" ]; then
    compile "$FLAGS" aes_gcm    aes_gcm.c    aes_gcm
    compile "$FLAGS" hmac_hkdf  hmac_hkdf.c  hmac_hkdf
    compile "$FLAGS" ecdh_pfs   ecdh_pfs.c   ecdh_pfs
    compile "$FLAGS" tls_server tls_server.c tls_server
    compile "$FLAGS" tls_server tls_client.c tls_client
else
    case "$TARGET" in
        aes_gcm)   compile "$FLAGS" aes_gcm    aes_gcm.c    aes_gcm ;;
        hmac_hkdf) compile "$FLAGS" hmac_hkdf  hmac_hkdf.c  hmac_hkdf ;;
        ecdh_pfs)  compile "$FLAGS" ecdh_pfs   ecdh_pfs.c   ecdh_pfs ;;
        tls_server) compile "$FLAGS" tls_server tls_server.c tls_server
                   compile "$FLAGS" tls_server tls_client.c tls_client ;;
        *) echo "未知目标: $TARGET (可选: aes_gcm hmac_hkdf ecdh_pfs tls_server | gmssl)"; exit 1 ;;
    esac
fi

echo "==> 产物在 $BUILD:"
ls -1 "$BUILD"
echo "==> 完成。运行示例见 README.md"
