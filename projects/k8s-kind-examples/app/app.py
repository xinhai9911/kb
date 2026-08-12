"""
app.py — 最小可部署服务（对应 [[projects/k8s-kind-examples/README]]）
演示 K8s 核心对象：Pod / Deployment / Service / Ingress / ConfigMap / 探针。
路径设计方便验证 Ingress 路由与健康检查：
  /         -> 默认欢迎页（含 Pod 名，验证负载均衡到多个副本）
  /healthz  -> 就绪/存活探针端点
  /version  -> 版本信息（配合 image tag 验证滚动更新）
  /ready?x= -> 自检就绪（readiness 探针的演示开关）
"""
import os
import time

from flask import Flask, request

app = Flask(__name__)

# 从环境变量读取（部署时注入），展示 ConfigMap 生效
GREETING = os.environ.get("GREETING", "Hello")
VERSION = os.environ.get("APP_VERSION", "dev")
POD_NAME = os.environ.get("POD_NAME", "unknown")
FAIL_READY = os.environ.get("FAIL_READY", "false") == "true"


@app.route("/")
def index():
    """默认页：回显 Pod 名与问候语。多副本时每次访问 Pod 名不同。"""
    return f"{GREETING} from pod {POD_NAME} (v{VERSION})\n"


@app.route("/healthz")
def healthz():
    """存活/就绪探针端点：容器健康即返回 200。"""
    return "ok\n"


@app.route("/version")
def version():
    return f"v{VERSION}\n"


@app.route("/ready")
def ready():
    """就绪演示：FAIL_READY=true 时返回 503，用于演示 readiness 摘流。"""
    if FAIL_READY:
        return "not ready\n", 503
    return "ready\n"


if __name__ == "__main__":
    # 慢启动模拟（默认关闭），配合 startupProbe 演示
    if os.environ.get("SLOW_START", "false") == "true":
        time.sleep(10)
    app.run(host="0.0.0.0", port=8080)
