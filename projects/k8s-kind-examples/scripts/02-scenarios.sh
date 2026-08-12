#!/usr/bin/env bash
# 体验 K8s 核心机制：负载均衡 / 滚动更新 / 探针 / ConfigMap
# 对应文档：[[projects/k8s-kind-examples/README]]
# 用法：bash scripts/02-scenarios.sh [cluster-name]   （默认 kind-k8s-demo）
set -euo pipefail

CLUSTER=${1:-kind-k8s-demo}
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo "==> 场景 1：Service 负载均衡（多次访问，Pod 名轮换）"
for i in 1 2 3 4 5; do
  kubectl run test-curl -i --rm --restart=Never --image=curlimages/curl -- \
    -s http://web.demo.svc.cluster.local/ | sed 's/^/     /'
done

echo
echo "==> 场景 2：滚动更新（升级镜像 → 观察 Pod 逐个替换）"
# 复用 v1 镜像打个 v2 tag 注入，演示「换 tag 触发滚动更新」的机制
docker tag k8s-kind-examples/web:v1 k8s-kind-examples/web:v2
kind load docker-image k8s-kind-examples/web:v2 --name "$CLUSTER" >/dev/null
kubectl set image deploy/web web=k8s-kind-examples/web:v2 -n demo
kubectl rollout status deploy/web -n demo
kubectl rollout history deploy/web -n demo | tail -3

echo
echo "==> 场景 3：readiness 摘流演示（FAIL_READY=true 的 Pod 被摘出 Service）"
kubectl scale deploy/web --replicas=1 -n demo
kubectl set env deploy/web FAIL_READY=true -n demo
kubectl rollout status deploy/web -n demo
kubectl get pods -n demo -l app=web
kubectl run test-curl -i --rm --restart=Never --image=curlimages/curl -- \
  -s http://web.demo.svc.cluster.local/healthz || true
echo "  （预期：Service 端点为空/返回错误，因为唯一 Pod 未就绪）"
kubectl set env deploy/web FAIL_READY- -n demo   # 恢复
kubectl rollout status deploy/web -n demo

echo
echo "==> 场景 4：ConfigMap 更新（改配置 → 重建 Pod 生效）"
kubectl patch configmap web-config -n demo --type merge -p '{"data":{"GREETING":"已更新"}}'
kubectl rollout restart deploy/web -n demo
kubectl rollout status deploy/web -n demo
kubectl run test-curl -i --rm --restart=Never --image=curlimages/curl -- \
  -s http://web.demo.svc.cluster.local/ | sed 's/^/     /'

echo
echo "完成。清理：bash scripts/03-kind-destroy.sh"
