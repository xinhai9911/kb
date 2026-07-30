---
title: 工程示例总览导航
category: projects
tags: [project, examples, navigation, index, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    projects/ 下所有示例工程与项目的导航总览：nginx-module-examples（C 模块）、
    openssl-crypto-examples（加密/C+GmSSL）、resilience-examples（限流熔断 C）、
    observability-examples（OTel 可观测栈）、cicd-pipeline-examples
    （GitHub Actions+Helm 金丝雀）、db-decoder-ironhive（Hive 协议解码）。
    每个工程标注语言/依赖/一键启动方式，并回链对应知识文档。
base_confidence: 0.9
lifecycle: reviewed
---

# 工程示例总览导航

> `projects/` 下是可**编译/可运行**的示例工程与真实项目。本文是它们的一眼导航，
> 每条都回链到对应知识文档（concepts/entities）。

## 页内搜索

> 在**浏览器**打开本页时，下方搜索框可实时过滤下面的「速览表」；
> 在 **Obsidian / 普通 markdown 阅读器**中 JS 不执行，搜索框不显示，
> 请直接用下方的**静态关键词索引**查找（见文末「关键词索引」一节）。

<input type="text" id="projSearch" placeholder="输入关键字过滤（如 nginx / 国密 / 熔断 / CI）" style="width:100%;padding:8px;font-size:14px;box-sizing:border-box;">

<ul id="projSearchHint" style="color:#888;font-size:12px;"></ul>

<script>
(function () {
  var input = document.getElementById('projSearch');
  var hint  = document.getElementById('projSearchHint');
  var table = document.getElementById('projTable');
  if (!input || !table) return;            // Obsidian 下不执行，安全退化
  var rows = table.getElementsByTagName('tr');
  input.addEventListener('input', function () {
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    for (var i = 1; i < rows.length; i++) {        // 跳过表头
      var text = rows[i].textContent.toLowerCase();
      var match = q === '' || text.indexOf(q) !== -1;
      rows[i].style.display = match ? '' : 'none';
      if (match) shown++;
    }
    hint.textContent = q === '' ? '' : ('匹配 ' + shown + ' 项');
  });
})();
</script>

## 速览表

<a id="projTable"></a>

| 工程 | 主题 | 语言/栈 | 依赖 | 一键启动 | 对应文档 |
|------|------|---------|------|---------|---------|
| [nginx-module-examples](nginx-module-examples/README.md) | Nginx 模块开发 | C | nginx 源码 + gcc | `bash scripts/build.sh` | [[entities/Nginx 模块开发实战]]、[[concepts/Nginx 框架内部实现]] |
| [openssl-crypto-examples](openssl-crypto-examples/README.md) | 加密（AES/HMAC/ECDHE/TLS） | C | OpenSSL dev | `bash scripts/build.sh` | [[entities/OpenSSL_BoringSSL 开发集成实战]]、[[concepts/加密算法总览与分类]] |
| [openssl-crypto-examples](openssl-crypto-examples/README.md) › gmssl | 国密 SM2/3/4 | C | GmSSL | `GMSL_PREFIX=/opt/gmssl bash scripts/build.sh gmssl` | [[entities/国密 SM2_SM3_SM4 实战]] |
| [resilience-examples](resilience-examples/README.md) | 限流/熔断/重试 | C | gcc（零依赖） | `bash scripts/build.sh` | [[entities/限流熔断实战]]、[[concepts/韧性设计]] |
| [observability-examples](observability-examples/README.md) | 可观测性栈 | Python + Docker | Docker Compose | `docker compose up -d` | [[entities/可观测性接入实战]]、[[concepts/可观测性工程]] |
| [cicd-pipeline-examples](cicd-pipeline-examples/README.md) | CI/CD 流水线 | YAML + Python | kubectl/helm（可选） | pytest / `helm upgrade` | [[entities/CI_CD 流水线实战]]、[[concepts/CI_CD与测试策略]] |
| [db-decoder-ironhive](db-decoder-ironhive/db-decoder-ironhive.md) | Hive 协议解码器 | — | — | — | 项目概述 |

## 按主题归类

### 网络 / 数据面（Nginx）
- **nginx-module-examples**：4 类可编译模块（Handler/Filter/Upstream/负载均衡器）+ 最小 nginx.conf
  - 文档：[[entities/Nginx 模块开发实战]]、[[concepts/Nginx 框架内部实现]]、[[concepts/Nginx 架构与事件模型]]

### 安全 / 加密
- **openssl-crypto-examples**：AES-GCM、HMAC/HKDF、ECDHE(PFS)、TLS 1.3 服务端/客户端
- **openssl-crypto-examples › gmssl**：国密 SM3 / SM4-GCM / SM2
  - 文档：[[entities/OpenSSL_BoringSSL 开发集成实战]]、[[entities/国密 SM2_SM3_SM4 实战]]、[[concepts/加密算法总览与分类]]、[[concepts/对称加密 AES与ChaCha20]]、[[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]

### 软件工程 / 可靠性
- **resilience-examples**：限流（令牌桶/滑动窗口）、熔断（三态）、指数退避重试+幂等
- **observability-examples**：OTel Collector + Prometheus + Loki + Tempo + Grafana + 埋点服务
- **cicd-pipeline-examples**：GitHub Actions 多阶段 + Helm 金丝雀 + 回滚脚本
  - 文档：[[concepts/韧性设计]]、[[concepts/可观测性工程]]、[[concepts/CI_CD与测试策略]]、[[entities/限流熔断实战]]、[[entities/可观测性接入实战]]、[[entities/CI_CD 流水线实战]]

### 协议分析 / 真实项目
- **db-decoder-ironhive**：IronHive Hive 协议解码器项目（概述/协议分析/Track/实现）
  - 文档：[[projects/db-decoder-ironhive/db-decoder-ironhive|项目概述]]

## 关键词索引（静态查找表，Obsidian 可用）

> 按「想找什么」快速定位工程 / 文档。相当于页内搜索的离线版。

| 我想找… | 去哪个工程 | 对应文档 |
|---------|-----------|---------|
| Nginx 模块 / Handler / Filter / 负载均衡 | [nginx-module-examples](nginx-module-examples/README.md) | [[entities/Nginx 模块开发实战]]、[[concepts/Nginx 框架内部实现]] |
| AES / GCM / HMAC / ECDHE / TLS 1.3 | [openssl-crypto-examples](openssl-crypto-examples/README.md) | [[entities/OpenSSL_BoringSSL 开发集成实战]]、[[concepts/加密算法总览与分类]] |
| 国密 SM2 / SM3 / SM4 / TLCP | [openssl-crypto-examples › gmssl](openssl-crypto-examples/README.md) | [[entities/国密 SM2_SM3_SM4 实战]] |
| 限流 / 熔断 / 重试 / 幂等 | [resilience-examples](resilience-examples/README.md) | [[entities/限流熔断实战]]、[[concepts/韧性设计]] |
| 可观测性 / 日志 / 指标 / 追踪 / Grafana | [observability-examples](observability-examples/README.md) | [[entities/可观测性接入实战]]、[[concepts/可观测性工程]] |
| CI/CD / 流水线 / 金丝雀 / 回滚 | [cicd-pipeline-examples](cicd-pipeline-examples/README.md) | [[entities/CI_CD 流水线实战]]、[[concepts/CI_CD与测试策略]] |
| C 语言 / 零依赖 / 算法演示 | resilience-examples、nginx-module-examples | — |
| Docker / Compose / OTel 栈 | observability-examples | [[concepts/可观测性工程]] |
| Kubernetes / Helm / 部署 | cicd-pipeline-examples › deploy/ | [[entities/CI_CD 流水线实战]] |
| Hive / 协议解码 / 真实项目 | [db-decoder-ironhive](db-decoder-ironhive/db-decoder-ironhive.md) | 项目概述 |
| 加密原理总览 | — | [[concepts/加密算法总览与分类]]、[[synthesis/加密算法技术全景综述]] |
| 软件工程全景 | — | [[concepts/软件设计原则与代码质量]]、[[synthesis/软件工程与架构技术全景综述]] |

## 通用构建说明

- **C 工程**（nginx/openssl/resilience）：在 Linux/macOS 用 gcc/clang 编译；Windows 用 WSL。
  本仓库编写时未在编译环境实跑验证，按标准 API 编写，报错请把日志贴回修订。
- **Docker 工程**（observability）：需 Docker + Compose。
- **CI/CD 工程**：流水线文件可直接放进 GitHub 仓库；本地可用 pytest/helm 验证部分阶段。

## 与知识库的衔接

这些工程是 [[synthesis/加密算法技术全景综述|加密全景]]、[[synthesis/软件工程与架构技术全景综述|软件工程全景]]
里「原理 → 实战」的落地。每个工程 README 都回链到对应 concepts/entities 文档。

## 参考来源

- 各工程 README（见上表链接）
- 各对应知识文档（见上表链接）
