#!/usr/bin/env bash
#
# rollback.sh — 秒级回滚到上一版本（对应 [[entities/CI_CD 流水线实战]] §4、[[concepts/CI_CD与测试策略]] §6）
#
# 用法： ./scripts/rollback.sh <release> <namespace>
#   金丝雀失败或 SLO 异常时由流水线调用。
#
set -euo pipefail

RELEASE="${1:?usage: rollback.sh <release> <namespace>}"
NAMESPACE="${2:?usage: rollback.sh <release> <namespace>}"

echo "==> 回滚 $RELEASE (ns=$NAMESPACE)"

# 1) 删除金丝雀部署（若存在）
if kubectl get deploy "$RELEASE-canary" -n "$NAMESPACE" >/dev/null 2>&1; then
  kubectl delete deploy "$RELEASE-canary" -n "$NAMESPACE"
  echo "    已删除金丝雀部署"
fi

# 2) Helm 回滚到上一版本（不可变镜像标签保证可复现）
helm rollback "$RELEASE" 0 -n "$NAMESPACE"
echo "    已回滚 $RELEASE 到上一 release"

# 3) 等待就绪
kubectl rollout status deploy/"$RELEASE" -n "$NAMESPACE" --timeout=60s
echo "==> 回滚完成"
