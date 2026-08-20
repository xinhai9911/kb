# llama.cpp 开发知识库

> 基于 llama.cpp 源码的结构化知识库，涵盖构建、API、工具、架构等核心内容。

## 项目概述

llama.cpp 是一个用纯 C/C++ 实现的 LLM/VLM 推理引擎，支持在多种硬件上进行本地和云端推理。

**核心特性：**
- 无依赖的纯 C/C++ 实现
- Apple Silicon 一等公民（ARM NEON、Accelerate、Metal）
- x86 架构支持（AVX、AVX2、AVX512、AMX）
- RISC-V 架构支持（RVV、ZVFH、ZFH、ZICBOP、ZIHINTPAUSE）
- 多种量化格式（1.5-bit 至 8-bit）
- GPU 加速（CUDA、HIP、MUSA、Vulkan、SYCL、Metal）
- CPU+GPU 混合推理

## 文档结构

```
output/
├── skill.md                    # 本文件
├── faq.md                      # 常见问题
├── _module_plan.md             # 模块规划
├── 01-overview/                # 项目概述与快速开始
├── 02-build/                   # 构建指南与平台支持
├── 03-backends/                # 硬件后端集成
├── 04-server/                  # HTTP 服务器与 REST API
├── 05-cli-tools/               # 命令行工具
├── 06-multimodal/              # 多模态模型支持
├── 07-grammars/                # GBNF 语法与约束生成
├── 08-examples/                # 示例程序与教程
├── 09-development/             # 开发指南与贡献规范
├── 10-architecture/            # 架构设计与技术规范
├── 11-ui/                      # Web UI 文档
├── 12-benchmarks/              # 性能基准测试
├── 13-cicd/                    # CI/CD 与开发运维
└── 14-python/                  # Python 工具库
```

## 快速开始

### 安装方式

1. **预构建二进制**：访问 https://llama.app 或 [GitHub Releases](https://github.com/ggml-org/llama.cpp/releases)
2. **Docker**：参考 `02-build/` 目录
3. **源码编译**：参考 `02-build/` 目录

### 基本使用

```bash
# 下载并运行模型
llama cli -hf ggml-org/Qwen3.5-0.8B-GGUF

# 启动 OpenAI 兼容 API 服务器
llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF
```

## 支持的后端

> 完整后端详情见 `03-backends/backends-overview.md`

| 后端 | 目标设备 | 状态 |
|------|----------|------|
| BLAS | 所有 | 稳定 |
| BLIS | 所有 | 实验性 |
| CANN | 华为昇腾 NPU | 稳定 |
| CUDA | NVIDIA GPU | 稳定 |
| HIP | AMD GPU | 稳定 |
| Hexagon | 高通骁龙 NPU | 实验性 |
| IBM zDNN | IBM Z 大型机 | 稳定 |
| MUSA | 摩尔线程 GPU | 实验性 |
| Metal | Apple Silicon | 稳定 |
| OpenCL | Adreno GPU | 实验性 |
| OpenVINO | Intel CPU/GPU/NPU | 实验性 |
| RPC | 所有（远程） | 稳定 |
| SYCL | Intel GPU | 稳定 |
| VirtGPU | 虚拟 GPU | 实验性 |
| Vulkan | GPU | 稳定 |
| WebGPU | 所有 | — |
| ZenDNN | AMD CPU | 实验性 |

## 详细模块索引

| 模块 | 路径 | 说明 |
|------|------|------|
| 构建指南 | `02-build/` | 编译与平台支持 |
| 后端详情 | `03-backends/` | 硬件后端配置 |
| HTTP 服务器 | `04-server/` | REST API 与 Web UI |
| CLI 工具 | `05-cli-tools/` | 命令行使用指南 |
| 多模态 | `06-multimodal/` | 图像/音频/视频支持 |
| GBNF 语法 | `07-grammars/` | 约束生成 |
| 示例程序 | `08-examples/` | 教程与用例 |
| 开发指南 | `09-development/` | 贡献规范 |
| 架构设计 | `10-architecture/` | 技术规范 |
| Web UI | `11-ui/` | 前端界面文档 |
| 性能测试 | `12-benchmarks/` | 基准测试数据 |
| CI/CD | `13-cicd/` | 持续集成 |
| Python 工具 | `14-python/` | gguf-py 等 |

## 相关链接

- [ggml 库](https://github.com/ggml-org/ggml)
- [项目宣言](https://github.com/ggml-org/llama.cpp/discussions/205)
- [贡献指南](CONTRIBUTING.md)
