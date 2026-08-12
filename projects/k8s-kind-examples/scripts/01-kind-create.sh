#!/usr/bin/env bash
# 一键搭建 kind 集群 + 部署示例应用 + ingress-nginx + 验证
# 对应文档：[[projects/k8s-kind-examples/README]]、[[entities/Ingress-Nginx 详解实战]]
#
# 依赖：docker、kind、kubectl、helm
# 用法：bash scripts/01-kind-create.sh [cluster-name]   （默认 kind-k8s-demo）
set -euo pipefail

CLUSTER=${1:-kind-k8s-demo}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> [1/5] 创建 kind 集群: $CLUSTER (control-plane + 2 worker)"
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER}$"; then
  echo "    已存在，跳过创建"
else
  cat <<EOF | kind create cluster --name "$CLUSTER" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
EOF
fi

echo "==> [2/5] 构建并注入示例应用镜像"
docker build -q -t k8s-kind-examples/web:v1 "$ROOT/app"
kind load docker-image k8s-kind-examples/web:v1 --name "$CLUSTER"

echo "==> [3/5] 安装 ingress-nginx (Helm)"
if kubectl get deploy -n ingress-nginx ingress-nginx-controller >/dev/null 2>&1; then
  echo "    已安装，跳过"
else
  helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
    -n ingress-nginx --create-namespace --wait \
    --set controller.service.type=NodePort \
    --set controller.admissionWebhooks.enabled=false
fi

echo "==> [4/5] 部署示例应用 (namespace demo)"
kubectl create ns demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$ROOT/manifests"
kubectl wait --for=condition=available --timeout=120s deploy/web -n demo

echo "==> [5/5] 验证"
echo "  -- Service (ClusterIP) 访问："
kubectl run test-curl -i --rm --restart=Never --image=curlimages/curl -- \
  -s http://web.demo.svc.cluster.local/ | sed 's/^/     /'
echo "  -- Ingress (NodePort) 访问："
INGRESS_PORT=$(kubectl get svc -n ingress-nginx ingress-nginx-controller \
  -o jsonpath='{.spec.ports[?(@.name=="http")].nodePort}')
for ip in $(kubectl get nodes -o jsonpath='{.items[*].status.addresses[?(@.type=="InternalIP")].address}'); do
  echo "     http://$ip:$INGRESS_PORT/demo/"
done

echo
echo "集群就绪。下一步："
echo "  curl -H 'Host: demo.example.com' http://<node-ip>:$INGRESS_PORT/demo/"
echo "  bash scripts/02-scenarios.sh   # 体验滚动更新 / 探针 / 负载均衡"
echo "  bash scripts/03-kind-destroy.sh"
