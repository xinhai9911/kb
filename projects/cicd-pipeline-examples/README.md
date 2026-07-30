# CI/CD 流水线示例工程（cicd-pipeline-examples）

本目录是 [[entities/CI_CD 流水线实战]] 的可运行/可套用工程，配套 [[concepts/CI_CD与测试策略]]。
给出一条**可放进真实仓库**的 GitHub Actions 多阶段流水线 + Helm 金丝雀部署 + 秒级回滚脚本。

## 目录结构

```
cicd-pipeline-examples/
├── .github/workflows/ci-cd.yml   # 多阶段流水线：lint→单测→构建→staging→金丝雀
├── app/
│   ├── app.py            # 最小 Flask 服务（/healthz /order）
│   ├── test_app.py       # pytest 单测 + 冒烟
│   ├── requirements.txt
│   └── Dockerfile
├── deploy/                # Helm chart（含 canary 部署）
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/{deployment,service}.yaml
├── scripts/rollback.sh   # 秒级回滚（删金丝雀 + helm rollback）
└── README.md
```

## 流水线阶段（对应文档 §1/§2）

```
push main ─► test(lint+pytest) ─► build(SHA 镜像) ─► deploy-staging
                                                         └► smoke
                                                              └► canary(5% 流量)
                                                                    └► 观察 SLO → 全量 / 回滚
```

| 阶段 | 关键实践 | 文档对应 |
|------|---------|---------|
| test | flake8 + pytest，快反馈 | §5 测试分层 |
| build | 镜像用 git SHA 不可变标签 | §3 不可变制品 |
| deploy-staging | helm upgrade + curl 冒烟 | §3 |
| canary | 先 5% 流量，观察 SLO 再全量 | §6 金丝雀 |
| rollback | 删 canary + helm rollback 0 | §4 回滚 |

## 本地验证（无需 GitHub）

```bash
cd Q:/AI/kb/projects/cicd-pipeline-examples

# 1) 跑测试（等价流水线 test 阶段）
pip install -r app/requirements.txt
pytest app/test_app.py -q

# 2) 本地起服务，冒烟
docker build -t order:local -f app/Dockerfile app
docker run -p 8080:8080 order:local &
curl -f localhost:8080/healthz
curl -s -XPOST localhost:8080/order -H 'content-type: application/json' -d '{"user_id":"u1"}'

# 3) 模拟金丝雀 + 回滚（需 kubectl + helm + 集群）
helm install order ./deploy --set image.tag=local -n prod
helm upgrade order ./deploy --set image.tag=local --set canary.enabled=true --set canary.weight=5 -n prod
./scripts/rollback.sh order prod
```

## 质量门禁

- 单测覆盖关键路径；flake8 非零退出即阻断。
- 镜像 SHA 标签 → 回滚可复现。
- 金丝雀靠 SLO（错误率/延迟，见 [[concepts/可观测性工程]]）自动判定，异常即回滚。

## 与文档/其它工程关系

- 原理：[[concepts/CI_CD与测试策略]]、[[entities/CI_CD 流水线实战]]
- 金丝雀/回滚依赖可观测：[[concepts/可观测性工程]]、[[projects/observability-examples/README|observability-examples]]
- 韧性由限流/熔断兜底：[[projects/resilience-examples/README|resilience-examples]]

## 排错

| 现象 | 原因 | 解决 |
|------|------|------|
| 测试在 CI 过、本地不过 | 依赖版本不一致 | 固定 requirements 版本 |
| 金丝雀流量不均 | 简单 Service 不控权重 | 用 Istio/Argo Rollouts 做权重分流 |
| 回滚无效 | 用了 latest 标签 | 必须用 SHA 不可变标签 |
| 密钥泄露 | 硬编码 token | 用 Secrets/OIDC（env 已加 id-token: write） |

## 参考

- GitHub Actions、Helm、Argo Rollouts 文档
- 《Continuous Delivery》(Humble/Farley)
- [[entities/CI_CD 流水线实战]]
- [[concepts/CI_CD与测试策略]]
