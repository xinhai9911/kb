#!/usr/bin/env bash
#
# build.sh — 编译 resilience-examples（限流/熔断/重试）
#
# 纯 C、无外部依赖，只需 C 编译器（gcc/clang）。POSIX 时钟，
# Linux/macOS 直接编译；Windows 用 WSL。
#
# 用法：
#   ./scripts/build.sh            # 编译全部 → ./build/
#   ./scripts/build.sh retry      # 只编译某一项
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$HERE/build"
mkdir -p "$BUILD"
CC="${CC:-cc}"

compile() {
    local dir="$1" src="$2" out="$3"
    echo "==> 编译 $dir/$src"
    $CC -O2 -Wall "$HERE/$dir/$src" -o "$BUILD/$out" -lpthread
}

TARGET="${1:-all}"

if [ "$TARGET" = "all" ]; then
    compile rate_limit    rate_limit.c    rate_limit
    compile circuit_breaker circuit_breaker.c circuit_breaker
    compile retry         retry.c         retry
else
    case "$TARGET" in
        rate_limit)      compile rate_limit rate_limit.c rate_limit ;;
        circuit_breaker) compile circuit_breaker circuit_breaker.c circuit_breaker ;;
        retry)           compile retry retry.c retry ;;
        *) echo "未知目标: $TARGET (可选: rate_limit circuit_breaker retry)"; exit 1 ;;
    esac
fi

echo "==> 产物在 $BUILD:"
ls -1 "$BUILD"
echo "==> 完成。运行示例见 README.md"
