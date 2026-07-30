#!/usr/bin/env bash
#
# build.sh — 把本目录的 4 个 nginx 模块分别编译为动态 .so
#
# 用法：
#   ./scripts/build.sh                       # 自动下载 nginx-1.25.4 到 ./nginx-src 并编译
#   NGINX_SRC=/path/to/nginx-1.25.4 ./scripts/build.sh   # 用已有源码
#   ./scripts/build.sh --static              # 静态编进 objs/nginx
#
# 产物：
#   动态： ./build/modules/ngx_http_{hello,xfilter,myupstream,mylb}_module.so
#   静态： ./build/objs/nginx
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
MODULES=(hello xfilter myupstream mylb)
NGINX_VER="${NGINX_VER:-1.25.4}"
NGINX_SRC="${NGINX_SRC:-$HERE/nginx-src/nginx-$NGINX_VER}"
BUILD="$HERE/build"
MODE="dynamic"

[ "${1:-}" = "--static" ] && MODE="static"

echo "==> 准备 nginx 源码 ($NGINX_SRC)"
if [ ! -d "$NGINX_SRC" ]; then
    echo "    下载 nginx-$NGINX_VER ..."
    mkdir -p "$HERE/nginx-src"
    curl -fSL "https://nginx.org/download/nginx-$NGINX_VER.tar.gz" \
        -o "$HERE/nginx-src/nginx-$NGINX_VER.tar.gz"
    tar xzf "$HERE/nginx-src/nginx-$NGINX_VER.tar.gz" -C "$HERE/nginx-src"
fi

mkdir -p "$BUILD"
cd "$NGX_SRC"

# 组装 configure 参数
CONF_ARGS=(--prefix="$BUILD" --with-compat --with-http_ssl_module)
for m in "${MODULES[@]}"; do
    if [ "$MODE" = "dynamic" ]; then
        CONF_ARGS+=(--add-dynamic-module="$HERE/$m")
    else
        CONF_ARGS+=(--add-module="$HERE/$m")
    fi
done

echo "==> configure ${CONF_ARGS[*]}"
./configure "${CONF_ARGS[@]}"

echo "==> make"
make -j"$(nproc 2>/dev/null || echo 4)"

if [ "$MODE" = "dynamic" ]; then
    mkdir -p "$BUILD/modules"
    cp objs/*.so "$BUILD/modules/" 2>/dev/null || true
    echo "==> 动态模块已生成："
    ls -1 "$BUILD/modules"
else
    echo "==> 静态二进制："
    ls -1 objs/nginx
fi

echo "==> 完成。配置示例见 README.md"
