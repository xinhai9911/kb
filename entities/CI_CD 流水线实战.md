---
title: CI_CD 流水线实战
category: entities
tags: [se, cicd, github-actions, pipeline, canary, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    CI/CD 流水线实战：GitHub Actions 最小多阶段流水线（lint→单测→构建→
    镜像→部署 staging→金丝雀）、制品与缓存、密钥管理、环境分级、
    金丝雀发布用 SLO 自动判定（配合 [[concepts/可观测性工程]]）、
    回滚。对照 [[concepts/CI_CD与测试策略]]、[[concepts/韧性设计]]。
base_confidence: 0.8
lifecycle: draft
---

# CI/CD 流水线实战

> 原理见 [[concepts/CI_CD与测试策略]]。本文给一条可复制的最小多阶段流水线。

## 1. 流水线全景

```
push ─► lint ─► unit-test ─► build(镜像) ─► scan ─► deploy-staging
                                                          │
                                                       smoke-test
                                                          │
                                                    canary(5% 流量)
                                                          │ 观察 SLO
                                                      全量 / 回滚
```

## 2. GitHub Actions 示例

```yaml
name: ci-cd
on: { push: { branches: [main] } }

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { java-version: 21, cache: gradle }
      - run: ./gradlew lint test          # 静态检查 + 单测（快反馈）

  build:
    needs: test
    steps:
      - run: ./gradlew build -x test
      - run: docker build -t registry/order:${{ github.sha }} .
      - run: docker push registry/order:${{ github.sha }}   # 制品入库（SHA 做不可变标签）

  deploy-staging:
    needs: build
    steps:
      - run: helm upgrade order ./chart --set image.tag=${{ github.sha }} -n staging
      - run: curl -f https://staging/healthz                    # 冒烟

  canary:
    needs: deploy-staging
    environment: production
    steps:
      - run: kubectl set image deploy/order order=registry/order:${{ github.sha }} --canary=5%
      # 观察 SLO（错误率/延迟），异常则 kubectl rollout undo
```

## 3. 关键实践

| 实践 | 说明 |
|------|------|
| 不可变制品 | 镜像用 git SHA 打标签，不覆盖 `latest` |
| 缓存依赖 | gradle/maven/npm 缓存加速（上例 `cache: gradle`） |
| 密钥不进仓库 | 用 Actions Secrets / Vault，运行时注入 |
| 分级环境 | dev→staging→prod，逐步验证 |
| 冒烟测试 | 部署后最小健康检查，失败即停 |
| 金丝雀 | 先 5% 流量，配 SLO 自动判定（[[concepts/可观测性工程]] §5） |

## 4. 回滚

```bash
kubectl rollout undo deploy/order          # K8s 秒级回滚上一版
helm rollback order 42                     # Helm 回滚
```
> 回滚必须**演练过**、秒级。结合特性开关（[[concepts/CI_CD与测试策略]] §7）可「关功能不回滚」。

## 5. 测试分层对应流水线

- `lint + unit-test` 在 `test` 阶段（快，分钟级）。
- 集成测试（带 DB/依赖）在 `build` 后单独 job，可用 testcontainers。
- 端到端在 staging 后跑关键路径，不宜全量。

## 6. 质量门禁

- 单测覆盖率阈值（如 < 60% 红）。
- SAST（静态安全扫描）失败阻断。
- 契约测试（[[concepts/CI_CD与测试策略]] §5）验证 API 兼容。

## 7. 常见反模式

| 反模式 | 后果 |
|--------|------|
| 依赖 `latest` 标签 | 不可复现、回滚失效 |
| 密钥硬编码 | 泄露 |
| 只单测无集成 | 边界 bug 漏 |
| 直接全量发布 | 故障影响全部用户 |
| 回滚未演练 | 出事救不回 |

## 8. 可运行示例工程

`projects/cicd-pipeline-examples/` 提供上述流水线的**可直接套用工程**：GitHub Actions
多阶段工作流（lint→单测→构建 SHA 镜像→staging→金丝雀）+ Helm canary 部署 + 秒级回滚脚本，
外加一个带 pytest 的最小服务：

```bash
cd Q:/AI/kb/projects/cicd-pipeline-examples
pytest app/test_app.py -q          # 等价流水线 test 阶段
./scripts/rollback.sh order prod   # 等价流水线回滚
```

详见 [[projects/cicd-pipeline-examples/README|cicd-pipeline-examples 工程 README]]。

## 参考来源

- GitHub Actions 文档、GitLab CI、ArgoCD/Flux
- 《Continuous Delivery》(Humble/Farley)
- [[concepts/CI_CD与测试策略]]
- [[concepts/可观测性工程]]
- [[projects/cicd-pipeline-examples/README|cicd-pipeline-examples 工程]]
- [[concepts/韧性设计]]
