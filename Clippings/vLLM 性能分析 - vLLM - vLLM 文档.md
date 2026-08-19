---
title: "vLLM 性能分析 - vLLM - vLLM 文档"
source: "https://docs.vllm.com.cn/en/latest/contributing/profiling/"
author:
published:
created: 2026-08-18
description:
tags:
  - "clippings"
---
## vLLM 性能分析

> [!warning] 警告
> 性能分析仅供 vLLM 开发者和维护者使用，以了解代码库不同部分所消耗的时间比例。 **vLLM 最终用户绝不应开启性能分析** ，因为这会显著降低推理速度。

> [!tip] 选择性能分析工具
> - 使用 **Nsight Systems** 进行低开销、对性能敏感的性能分析。
> - 使用 **PyTorch Profiler** 进行中等开销的性能分析，以获取更丰富的调试信息（例如堆栈追踪、内存、张量形状）。请注意，启用这些功能会增加额外开销，不建议用于基准测试。

## 使用 PyTorch Profiler 进行性能分析

我们支持使用不同的性能分析工具对 vLLM worker 进行追踪。您可以在启动服务器时通过设置 `--profiler-config` 标志来启用性能分析。

> [!note] 注意
> `--profiler-config` 标志在 vLLM v0.13.0 及更高版本中可用。如果您使用的是更早的版本，请升级以使用此功能。

要使用 `torch.profiler` 模块，请将 `profiler` 条目设置为 `'torch'` ，并将 `torch_profiler_dir` 设置为您希望保存追踪文件的目录。此外，您可以通过在配置中指定以下额外参数来控制性能分析内容：

- `torch_profiler_record_shapes` ：启用记录张量形状（Tensor Shapes），默认关闭
- `torch_profiler_with_memory` ：记录内存，默认关闭
- `torch_profiler_with_stack` ：启用记录堆栈信息，默认开启
- `torch_profiler_with_flops` ：启用记录 FLOPs，默认关闭
- `torch_profiler_use_gzip` ：控制对性能分析文件进行 gzip 压缩，默认开启
- `torch_profiler_dump_cuda_time_total` ：控制导出并打印汇总的 CUDA 自增时间表，默认开启

使用 `vllm bench serve` 时，您可以通过传递 `--profile` 标志来启用性能分析。

追踪结果可以使用 [https://ui.perfetto.dev/](https://ui.perfetto.dev/) 进行可视化。

> [!tip] 提示
> 您可以使用 `python -m vllm.entrypoints.cli.main bench` 直接调用 bench 模块，而无需安装 vLLM。

> [!tip] 提示
> 在进行性能分析时，请仅通过 vLLM 发送少量请求，因为追踪文件可能会变得非常大。此外，无需解压追踪文件，它们可以直接进行查看。

> [!tip] 提示
> 要停止性能分析工具——它会将所有性能分析追踪文件刷新并写入到目录中。这需要一些时间，例如，对于 Llama 70B 模型约 100 个请求的数据量，在 H100 上写出大约需要 10 分钟。引擎客户端会等待此刷新过程完成而不会超时，因此只需让停止调用运行至完成即可。

### 示例命令与用法

#### 离线推理

请参考 [examples/features/profiling/simple\_profiling\_offline.py](https://github.com/vllm-project/vllm/blob/main/examples/features/profiling/simple_profiling_offline.py) 获取示例。

#### OpenAI 服务端

```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --profiler-config '{"profiler": "torch", "torch_profiler_dir": "./vllm_profile"}'
```

vllm bench 命令

```bash
vllm bench serve \
    --backend vllm \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --dataset-name sharegpt \
    --dataset-path sharegpt.json \
    --profile \
    --num-prompts 2
```

或者使用 HTTP 请求

```shell
# We need first call /start_profile api to start profile.
$ curl -X POST https://:8000/start_profile

# Call model generate.
curl -X POST https://:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
                "model": "meta-llama/Llama-3.1-8B-Instruct",
                "messages": [
                        {
                                "role": "user",
                                "content": "San Francisco is a"
                        }
                ]
    }'

# After need call /stop_profile api to stop profile.
$ curl -X POST https://:8000/stop_profile
```

## 使用 NVIDIA Nsight Systems 进行性能分析

Nsight Systems 是一款高级工具，可以展示更多性能分析细节，例如寄存器和共享内存使用情况、已标注的代码区域以及低层级 CUDA API 和事件。

使用您的包管理器 [安装 nsight-systems](https://docs.nvda.net.cn/nsight-systems/InstallationGuide/index.html) 。以下代码块是以 Ubuntu 为例的示例。

```bash
apt update
apt install -y --no-install-recommends gnupg
echo "deb http://developer.download.nvidia.com/devtools/repos/ubuntu$(source /etc/lsb-release; echo "$DISTRIB_RELEASE" | tr -d .)/$(dpkg --print-architecture) /" | tee /etc/apt/sources.list.d/nvidia-devtools.list
apt-key adv --fetch-keys http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/7fa2af80.pub
apt update
apt install nsight-systems-cli
```

> [!tip] 提示
> 在使用 `nsys` 进行性能分析时，建议设置环境变量 `VLLM_WORKER_MULTIPROC_METHOD=spawn` 。默认使用的是 `fork` 方法而非 `spawn` 。关于该主题的更多信息可以在 [Nsight Systems 发行说明](https://docs.nvda.net.cn/nsight-systems/ReleaseNotes/index.html#general-issues) 中找到。

可以通过 `nsys profile ...` 启动 Nsight Systems 性能分析器，针对 vLLM 推荐使用以下标志： `--trace-fork-before-exec=true --cuda-graph-trace=node` 。

### 示例命令与用法

#### 离线推理

对于基本用法，您只需在用于离线推理的任何现有脚本之前加上性能分析命令即可。

以下是使用 `vllm bench latency` 脚本的示例

```bash
nsys profile  \
    --trace-fork-before-exec=true \
    --cuda-graph-trace=node \
vllm bench latency \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --num-iters-warmup 5 \
    --num-iters 1 \
    --batch-size 16 \
    --input-len 512 \
    --output-len 8
```

#### OpenAI 服务端

要对服务端进行性能分析，就像离线推理一样，您需要在 `vllm serve` 命令前添加 `nsys profile` ，但您需要指定其他一些参数以启用类似于 Torch Profiler 的动态捕获

```bash
# server
nsys profile \
    --trace-fork-before-exec=true \
    --cuda-graph-trace=node \
    --capture-range=cudaProfilerApi \
    --capture-range-end repeat \
    vllm serve meta-llama/Llama-3.1-8B-Instruct --profiler-config.profiler cuda

# client
vllm bench serve \
    --backend vllm \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --dataset-name sharegpt \
    --dataset-path sharegpt.json \
    --profile \
    --num-prompts 2
```

传入 `--profile` 后，vLLM 将为 `vllm bench serve` 的每次运行捕获性能分析数据。一旦终止服务端进程，所有分析数据都将被保存。

#### 分析

您可以利用 `nsys stats [profile-file]` 在 CLI 中将这些分析数据作为摘要查看，也可以 [按照此处的说明在本地](https://developer.nvidia.com/nsight-systems/get-started) 安装 Nsight 在 GUI 中进行查看。

CLI 示例
```bash
nsys stats report1.nsys-rep
...
** CUDA GPU Kernel Summary (cuda_gpu_kern_sum):

Time (%)  Total Time (ns)  Instances   Avg (ns)     Med (ns)    Min (ns)  Max (ns)   StdDev (ns)                                                  Name
--------  ---------------  ---------  -----------  -----------  --------  ---------  -----------  ----------------------------------------------------------------------------------------------------
    46.3   10,327,352,338     17,505    589,965.9    144,383.0    27,040  3,126,460    944,263.8  sm90_xmma_gemm_bf16bf16_bf16f32_f32_tn_n_tilesize128x128x64_warpgroupsize1x1x1_execute_segment_k_of…
    14.8    3,305,114,764      5,152    641,520.7    293,408.0   287,296  2,822,716    867,124.9  sm90_xmma_gemm_bf16bf16_bf16f32_f32_tn_n_tilesize256x128x64_warpgroupsize2x1x1_execute_segment_k_of…
    12.1    2,692,284,876     14,280    188,535.4     83,904.0    19,328  2,862,237    497,999.9  sm90_xmma_gemm_bf16bf16_bf16f32_f32_tn_n_tilesize64x128x64_warpgroupsize1x1x1_execute_segment_k_off…
    9.5    2,116,600,578     33,920     62,399.8     21,504.0    15,326  2,532,285    290,954.1  sm90_xmma_gemm_bf16bf16_bf16f32_f32_tn_n_tilesize64x64x64_warpgroupsize1x1x1_execute_segment_k_off_…
    5.0    1,119,749,165     18,912     59,208.4      9,056.0     6,784  2,578,366    271,581.7  void vllm::act_and_mul_kernel<c10::BFloat16, &vllm::silu_kernel<c10::BFloat16>, (bool)1>(T1 *, cons…
    4.1      916,662,515     21,312     43,011.6     19,776.0     8,928  2,586,205    199,790.1  void cutlass::device_kernel<flash::enable_sm90_or_later<flash::FlashAttnFwdSm90<flash::CollectiveMa…
    2.6      587,283,113     37,824     15,526.7      3,008.0     2,719  2,517,756    139,091.1  std::enable_if<T2>(int)0&&vllm::_typeConvert<T1>::exists, void>::type vllm::fused_add_rms_norm_kern…
    1.9      418,362,605     18,912     22,121.5      3,871.0     3,328  2,523,870    175,248.2  void vllm::rotary_embedding_kernel<c10::BFloat16, (bool)1>(const long *, T1 *, T1 *, const T1 *, in…
    0.7      167,083,069     18,880      8,849.7      2,240.0     1,471  2,499,996    101,436.1  void vllm::reshape_and_cache_flash_kernel<__nv_bfloat16, __nv_bfloat16, (vllm::Fp8KVCacheDataType)0…
...
```

GUI 示例

[![Screenshot 2025-03-05 at 11 48 42 AM](https://github.com/user-attachments/assets/c7cff1ae-6d6f-477d-a342-bd13c4fc424c)](https://github.com/user-attachments/assets/c7cff1ae-6d6f-477d-a342-bd13c4fc424c)

## 持续性能分析

PyTorch 基础架构仓库中包含一个 [GitHub CI 工作流](https://github.com/pytorch/pytorch-integration-testing/actions/workflows/vllm-profiling.yml) ，用于在 vLLM 上针对不同模型提供持续性能分析。这种自动化性能分析有助于跨时间和不同模型配置跟踪性能特征。

### 工作原理

该工作流目前每周为选定模型运行性能分析会话，生成详细的性能追踪数据，以便使用不同的工具进行分析，从而发现性能下降或优化机会。不过，它也可以使用 GitHub Actions 工具手动触发。

### 添加新模型

要将持续性能分析扩展到更多模型，您可以修改 PyTorch 集成测试仓库中的 [profiling-tests.json](https://github.com/pytorch/pytorch-integration-testing/blob/main/vllm-profiling/cuda/profiling-tests.json) 配置文件。只需将您的模型规范添加到此文件中，即可将其包含在自动性能分析运行中。

### 查看性能分析结果

持续性能分析工作流生成的性能分析追踪数据已公开在 [vLLM 性能仪表板](https://hud.pytorch.org/benchmark/llms?repoName=vllm-project%2Fvllm) 上。找到 **Profiling traces** 表格，即可获取并下载不同模型和运行的追踪数据。

## 对 vLLM Python 代码进行性能分析

Python 标准库包含用于对 Python 代码进行性能分析的 [cProfile](https://docs.pythonlang.cn/3/library/profile.html) 。

### 示例用法 - 函数调用

如果指定了文件名，性能分析结果将保存到该文件。如果没有指定文件名，分析数据可以打印到 stdout（标准输出）。

```python
import cProfile

def expensive_function():
    # some expensive code
    pass

profiler = cProfile.Profile()
profiler.runcall(expensive_function)
profiler.dump_stats("expensive_function.prof")
```

### 示例用法 - 上下文管理器风格

```python
import cProfile

def another_function():
    # more expensive code
    pass

profiler = cProfile.Profile()
profiler.enable()
try:
    another_function()
finally:
    profiler.disable()
    profiler.dump_stats("another_function.prof")
```

### 分析性能分析结果

有多种工具可以帮助分析性能分析结果。例如 [snakeviz](https://jiffyclub.github.io/snakeviz/) 。

```bash
pip install snakeviz
snakeviz expensive_function.prof
```

### 分析垃圾回收 (GC) 开销

利用 VLLM\_GC\_DEBUG 环境变量来调试 GC 开销。

- VLLM\_GC\_DEBUG=1：启用 GC 调试器，记录 gc.collect 的耗时
- VLLM\_GC\_DEBUG='{"top\_objects":5}'：启用 GC 调试器，在每次 gc.collect 时记录收集到的前 5 个对象