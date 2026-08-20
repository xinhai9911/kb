# llama.cpp 模块规划

## 文档类型判定
- 类型：mixed（混合型）
- 原因：包含构建指南（config-guide）、API文档（api-manual）、工具文档、示例代码等多种类型

## 模块规划

### 01-overview
**描述**：项目概述与快速开始
**源文件**：
- S073: README.md
- S041: docs/usage.md
- S036: docs/models.md
- S035: docs/install.md

### 02-build
**描述**：构建指南与平台支持
**源文件**：
- S028: docs/build.md（36KB，需拆分）
- S029: docs/build-riscv64-spacemit.md
- S030: docs/build-s390x.md
- S011: docs/android.md
- S043: docs/windows.md
- S033: docs/docker.md

### 03-backends
**描述**：硬件后端集成指南
**源文件**：
- S013: docs/backend/BLIS.md
- S014: docs/backend/CANN.md
- S015: docs/backend/CUDA-FEDORA.md
- S016: docs/backend/ET.md
- S017: docs/backend/OPENCL.md
- S018: docs/backend/OPENVINO.md
- S023: docs/backend/SYCL.md
- S024: docs/backend/VirtGPU.md
- S027: docs/backend/ZenDNN.md
- S019-S022: docs/backend/snapdragon/*.md

### 04-server
**描述**：HTTP服务器与REST API
**源文件**：
- S095: tools/server/README.md（104KB，需拆分）
- S096: tools/server/README-dev.md
- S093: tools/server/bench/README.md
- S094: tools/server/bench/speed-bench/README.md

### 05-cli-tools
**描述**：命令行工具
**源文件**：
- S078: tools/cli/README.md（30KB）
- S079: tools/completion/README.md（56KB，需拆分）
- S082: tools/fit-params/README.md
- S083: tools/gguf-split/README.md
- S084: tools/imatrix/README.md
- S085: tools/llama-bench/README.md
- S089: tools/perplexity/README.md
- S090: tools/quantize/README.md
- S091: tools/results/README.md
- S092: tools/rpc/README.md
- S098: tools/tts/README.md

### 06-multimodal
**描述**：多模态模型支持
**源文件**：
- S087: tools/mtmd/README.md
- S088: tools/mtmd/README-dev.md
- S086: tools/mtmd/debug/mtmd-debug.md
- S012: docs/autoparser.md（32KB，需拆分）
- S034: docs/function-calling.md

### 07-grammars
**描述**：GBNF语法与约束生成
**源文件**：
- S071: grammars/README.md

### 08-examples
**描述**：示例程序与教程
**源文件**：
- S044-S069: examples/*/README.md

### 09-development
**描述**：开发指南与贡献规范
**源文件**：
- S010: CONTRIBUTING.md
- S002: AGENTS.md
- S074: SECURITY.md
- S075: skills/add-new-model/SKILL.md
- S076: skills/code-review/SKILL.md

### 10-architecture
**描述**：架构设计与技术规范
**源文件**：
- S037: docs/specs/kv-cache.md
- S038: docs/specs/medn.md
- S039: docs/tech/node-overlap.md
- S040: docs/tech/tree-attention.md
- S099-S100: tools/ui/docs/architecture/*.md

### 11-ui
**描述**：Web UI文档
**源文件**：
- S110: tools/ui/README.md（21KB）
- S101-S109: tools/ui/docs/flows/*.md
- S111: tools/ui/src/lib/components/app/SKILL.md

### 12-benchmarks
**描述**：性能基准测试
**源文件**：
- S003: benches/dgx-spark/dgx-spark.md
- S004: benches/mac-m2-ultra/mac-m2-ultra.md
- S005: benches/nemotron/nemotron-dgx-spark.md

### 13-cicd
**描述**：CI/CD与开发运维
**源文件**：
- S006: ci/README.md
- S007: ci/README-MUSA.md

### 14-python
**描述**：Python工具库
**源文件**：
- S070: gguf-py/README.md
- S009: common/jinja/README.md

---

## 文件拆分规划

| 源文件 | 大小(bytes) | 目标文件 | 拆分原因 |
|--------|-------------|----------|----------|
| docs/build.md | 36,611 | 02-build/build-overview.md<br>02-build/build-cpu.md<br>02-build/build-gpu.md | 超过8KB，按后端类型拆分 |
| tools/server/README.md | 104,721 | 04-server/server-overview.md<br>04-server/server-params.md<br>04-server/server-api.md<br>04-server/server-extended.md | 超过8KB，按功能拆分 |
| tools/completion/README.md | 56,982 | 05-cli-tools/completion-overview.md<br>05-cli-tools/completion-params.md<br>05-cli-tools/completion-api.md | 超过8KB，按参数类型拆分 |
| docs/autoparser.md | 32,036 | 06-multimodal/autoparser-overview.md<br>06-multimodal/autoparser-usage.md | 超过8KB，按功能拆分 |
| tools/cli/README.md | 30,135 | 05-cli-tools/cli-overview.md<br>05-cli-tools/cli-params.md | 超过8KB，按功能拆分 |

---

## 章节映射表（部分示例）

| chapterId | 来源标题 | 目标文件 |
|-----------|----------|----------|
| S073-C001 | llama.cpp | 01-overview/overview.md |
| S073-C002 | Quick start | 01-overview/quickstart.md |
| S073-C003 | Description | 01-overview/overview.md |
| S073-C004 | Supported backends | 03-backends/backends-overview.md |
| S028-C001 | Build llama.cpp locally | 02-build/build-overview.md |
| S028-C002 | CPU Build | 02-build/build-cpu.md |
| S028-C003 | BLAS Build | 02-build/build-gpu.md |
| S095-C001 | LLaMA.cpp HTTP Server | 04-server/server-overview.md |
| S095-C002 | Usage | 04-server/server-params.md |
| S095-C003 | API endpoints | 04-server/server-api.md |
