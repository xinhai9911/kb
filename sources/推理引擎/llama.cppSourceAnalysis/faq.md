# llama.cpp 常见问题

> 各主题详细文档请参阅对应模块：`02-build/`（构建）、`03-backends/`（后端）、`04-server/`（服务器）、`05-cli-tools/`（CLI）、`06-multimodal/`（多模态）

## 构建问题

### Q: 如何在 Linux 上构建 llama.cpp？

**A:** 基本构建命令：
```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release
```

### Q: 如何启用 GPU 加速？

**A:** 根据你的 GPU 类型选择对应的 CMake 选项：

| GPU 类型 | CMake 选项 |
|----------|------------|
| NVIDIA | `-DGGML_CUDA=ON` |
| AMD | `-DGGML_HIP=ON` |
| Apple Silicon | `-DGGML_METAL=ON` (默认启用) |
| Intel | `-DGGML_SYCL=ON` |
| 摩尔线程 | `-DGGML_MUSA=ON` |
| Vulkan | `-DGGML_VULKAN=ON` |

### Q: 编译速度太慢怎么办？

**A:** 使用并行编译：
```bash
cmake --build build --config Release -j 8  # 使用 8 个并行任务
```

或安装 ccache 加速重复编译。

### Q: 如何构建静态库？

**A:** 添加 `-DBUILD_SHARED_LIBS=OFF`：
```bash
cmake -B build -DBUILD_SHARED_LIBS=OFF
cmake --build build --config Release
```

## 服务器问题

### Q: 如何启动 HTTP 服务器？

**A:** 使用 `llama serve` 命令：
```bash
llama serve -m /path/to/model.gguf
```

或使用 Docker：
```bash
docker run -p 8080:8080 -v /path/to/models:/models ghcr.io/ggml-org/llama.cpp:server -m /models/model.gguf
```

### Q: 服务器支持哪些 API？

**A:** 服务器提供 OpenAI 兼容的 REST API，包括：
- `POST /v1/chat/completions` - 聊天补全
- `POST /v1/completions` - 文本补全
- `POST /v1/embeddings` - 文本嵌入
- `GET /v1/models` - 列出可用模型
- `GET /health` - 健康检查

### Q: 如何使用多 GPU？

**A:** 使用 `--tensor-split` 参数指定 GPU 分配比例：
```bash
llama serve -m model.gguf --tensor-split 0.5,0.5
```

## 量化问题

### Q: 什么是量化？如何选择量化格式？

**A:** 量化是将模型权重从高精度（如 FP16）转换为低精度格式，以减少内存占用和提高推理速度。

常用量化格式：
- **Q4_0**: 4-bit 量化，内存占用小，速度快
- **Q4_K_M**: 4-bit 量化，质量更好
- **Q5_K_M**: 5-bit 量化，质量与速度平衡
- **Q8_0**: 8-bit 量化，质量接近原始模型

### Q: 如何量化模型？

**A:** 使用 `llama-quantize` 工具：
```bash
llama-quantize input.gguf output.gguf Q4_K_M
```

## 多模态问题

### Q: llama.cpp 支持哪些多模态模型？

**A:** 支持的模型包括：
- LLaVA 系列
- BakLLaVA
- Obsidian
- 其他兼容的多模态模型

### Q: 如何使用多模态功能？

**A:** 使用 `llama cli` 并指定图像路径：
```bash
llama cli -m model.gguf --image /path/to/image.jpg
```

## 性能问题

### Q: 如何提高推理速度？

**A:**
1. 使用 GPU 加速（CUDA、Metal 等）
2. 使用量化模型
3. 调整上下文长度（`-c` 参数）
4. 使用 Flash Attention（`--flash-attn`）
5. 调整线程数（`-t` 参数）

### Q: 内存不足怎么办？

**A:**
1. 使用更小的量化格式
2. 减少上下文长度
3. 使用 CPU+GPU 混合推理
4. 启用统一内存（`GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`）

## 模型问题

### Q: 支持哪些模型格式？

**A:** 主要支持 GGUF 格式。可以从 Hugging Face 下载预转换的 GGUF 模型，或使用转换工具将其他格式转换为 GGUF。

### Q: 如何下载模型？

**A:** 使用 `llama cli` 直接从 Hugging Face 下载：
```bash
llama cli -hf ggml-org/Qwen3.5-0.8B-GGUF
```

或手动下载 GGUF 文件并使用 `-m` 参数指定路径。

## 故障排除

### Q: 出现 "CUDA out of memory" 错误怎么办？

**A:**
1. 减少 `-ngl` 参数（GPU 层数）
2. 减少 `-c` 参数（上下文长度）
3. 使用更小的量化格式
4. 启用统一内存

### Q: 服务器无法启动怎么办？

**A:**
1. 检查端口是否被占用
2. 确认模型路径正确
3. 检查依赖库是否安装
4. 查看详细日志

### Q: 如何报告问题？

**A:** 在 [GitHub Issues](https://github.com/ggml-org/llama.cpp/issues) 中报告，并提供：
- 操作系统和版本
- 硬件信息
- 完整的错误信息
- 复现步骤
