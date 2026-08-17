---
title: "MindSpore Transformers 安装指南（官方文档 r1.8.0）"
tags: [mindspore, ascend, installation, version-matrix, official-docs, active]
lifecycle: active
category: reference
base_confidence: 0.85
created: 2026-08-17
updated: 2026-08-17
summary: >-
  MindSpore Transformers r1.8.0 官方安装指南：版本配套关系表（MindFormers/MindSpore/CANN/固件驱动）、
  依赖安装、源码编译和 pip 安装两种方式、安装验证。
source: https://www.mindspore.cn/mindformers/docs/zh-CN/r1.8.0/installation.html
---

# MindSpore Transformers 安装指南（官方文档 r1.8.0）

> 📄 本文档抓取自 MindSpore Transformers v1.8.0 官方文档，作为参考归档。

## 硬件要求

| 硬件 | 芯片 |
|------|------|
| Atlas 800T A2 | 昇腾 910B |
| Atlas 800I A2 | 昇腾 910B |
| Atlas 900 A3 SuperPoD | 昇腾 910C |

**建议 Python 版本**：3.11.4

## 版本配套关系（关键！）

> ⚠️ **版本必须严格配套**，否则无法运行。

### 最新配套（r1.8.0）

| MindSpore Transformers | MindSpore | CANN | 固件与驱动 |
|:----------------------:|:---------:|:----:|:----------:|
| **1.8.0** | 2.7.2 | 8.5.0 | 25.5.0 |

### 历史版本配套

| MindSpore Transformers | MindSpore | CANN | 固件与驱动 |
|:----------------------:|:---------:|:----:|:----------:|
| 1.7.0 | 2.7.1 | 8.3.RC1 | 25.3.RC1 |
| 1.6.0 | 2.7.0 | 8.2.RC1 | 25.2.0 |
| 1.5.0 | 2.6.0-rc1 | 8.1.RC1 | 25.0.RC1 |
| 1.3.2 | 2.4.10 | 8.0.0 | 24.1.0 |
| 1.3.0 | 2.4.0 | 8.0.RC3 | 24.1.RC3 |
| 1.2.0 | 2.3.0 | 8.0.RC2 | 24.1.RC2 |

### 版本配套速查图

```
MindFormers 1.8.0
  └── MindSpore 2.7.2
        └── CANN 8.5.0
              └── 固件驱动 25.5.0
                    └── 硬件: Atlas 800T A2 / 800I A2 / 900 A3
```

## 安装步骤

### Step 1：安装固件与驱动

通过版本匹配关系中的固件与驱动链接下载安装包，参考昇腾官方教程安装。

### Step 2：安装 CANN 和 MindSpore

按照 MindSpore 官网的「手动安装」章节进行安装。

### Step 3：安装 MindSpore Transformers

#### 方式一：源码编译安装

```bash
git clone -b r1.8.0 https://gitee.com/mindspore/mindformers.git
cd mindformers
bash build.sh
```

#### 方式二：pip 安装

```bash
pip install https://ms-release.obs.cn-north-4.myhuaweicloud.com/2.7.2/MindFormers/any/mindformers-1.8.0-py3-none-any.whl \
  --trusted-host ms-release.obs.cn-north-4.myhuaweicloud.com \
  -i https://repo.huaweicloud.com/repository/pypi/simple
```

> ⚠️ 注意：
> - pip 安装需要访问公网，内网环境需配置网络代理
> - pip 方式只安装基础软件包，模型文件和脚本需从 Gitee 仓库获取

## 验证安装

```bash
python -c "import mindformers as mf; mf.run_check()"
```

成功输出：
```
- INFO - All checks passed, used **** seconds, the environment is correctly set up!
```

## 知识关联

- → [[entities/mindspore-transformers]] — MindFormers 套件详解
- → [[concepts/ascend-software-stack]] — 昇腾全栈架构
- → [[50-reference/sources/mindspore/mindformers-overview-r1.8.0|整体架构]] — 架构与能力
- → [[50-reference/sources/mindspore/mindformers-models-r1.8.0|模型库]] — 支持的模型列表

---

**抓取时间**：2026-08-17
**文档版本**：r1.8.0
**维护者**：Claudian