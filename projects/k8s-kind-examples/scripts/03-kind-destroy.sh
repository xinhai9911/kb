#!/usr/bin/env bash
# 一键销毁 kind 集群
# 用法：bash scripts/03-kind-destroy.sh [cluster-name]   （默认 kind-k8s-demo）
set -euo pipefail

CLUSTER=${1:-kind-k8s-demo}

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER}$"; then
  echo "==> 删除集群: $CLUSTER"
  kind delete cluster --name "$CLUSTER"
else
  echo "集群 $CLUSTER 不存在，无需删除"
fi

echo "完成。"
