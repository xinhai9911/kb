---
title: GPU Kernel 执行模型与编译链
category: concepts
tags: [gpu, cuda, kernel, ptx, sass, cubin, elf, driver, cuda-graph, torch-compile, vllm, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    GPU kernel 从编码到执行的完整链路：CUDA C → PTX（虚拟 ISA，跨代兼容）→ SASS（真实机器码，
    绑定架构）→ cubin（ELF 打包）→ 驱动 module load 上传显存 → launch（param buffer/pushbuffer/
    门铃）→ GigaThread 分发 block → SM 按 warp 执行。以及两大消除 launch 开销的图优化：
    torch.compile（融合 kernel）与 CUDA Graph（录制重放命令流），对应 vLLM 的 enforce_eager 开关。
base_confidence: 0.88
lifecycle: draft
---

# GPU Kernel 执行模型与编译链

> 前置 [[concepts/Transformer 架构]]（为什么要跑 kernel）、[[50-reference/sources/chips/GPU AI 加速器]]（CUDA 编程模型总表）、
> [[concepts/FlashAttention 注意力内核]]（真实 kernel 例子）、[[sources/推理引擎/vLLM 对外接口与运行参考]]（`--enforce-eager` / CUDA Graph 配置）。
>
> 本地可运行演示：`scratch/gpu-kernel-sim/gpu_sim.py`（纯 Python 模拟全流程）+ `scratch/gpu-kernel-sim/gpu_flow.html`（8 步可视化）。

## 1. 为什么需要懂这条链：eager 模式的瓶颈

LLM decode 每生成一个 token 就要跑一遍完整前向。PyTorch eager 模式下，每个算子单独发起一次 GPU kernel 启动（launch）：

- 每次 launch 有 **5~10µs CPU 侧固定开销**（参数打包→驱动组装命令→写 pushbuffer→碰门铃，见 §5）
- 一个模型前向有几百个算子 = 每步几百次 launch
- decode 时 kernel 计算量极小，**launch 开销占比反超计算本身**，GPU 大量时间空转等 CPU 派活

两大优化各自解决一半问题：

| 优化 | 解决什么 | 类比 |
|---|---|---|
| **torch.compile** | kernel 本身低效：融合算子，300 个 kernel → 几十个，减少显存往返 | 做菜不反复端盘子，一口锅做完 |
| **CUDA Graph** | launch 调度开销：把命令流录制下来，每步一次重放，CPU 全程旁路 | 菜谱录成语音，喊一声"播放"全自动做菜 |

vLLM 的 `enforce_eager=True`（CLI `--enforce-eager`）= 关掉这两层，退回"CPU 逐行发令"模式——换取启动快、省显存（不需要图捕获池）、好调试。

## 2. 编译链四形态：CUDA C → PTX → SASS → cubin

```text
CUDA C / Triton Python（源码，__global__ 函数）
   │  nvcc / Triton 编译器
   ▼
PTX   虚拟 ISA，文本汇编，不绑定芯片（类比 JVM 字节码）—— 跨代兼容的"备胎"
   │  ptxas（编译期或驱动 JIT 时运行）
   ▼
SASS  真实硬件机器码，绑定具体架构（sm_80/sm_89/sm_90…）
   │  打包
   ▼
cubin 二进制容器，ELF 格式（与 Linux 可执行文件同宗）
   │  多架构 SASS + 一份 PTX 打包
   ▼
fatbin 嵌进 .so / 可执行文件的最终形态
```

### 2.1 PTX 是什么（Parallel Thread Execution）

NVIDIA 定义的**虚拟指令集**——文本汇编，只描述"逻辑上要做什么"，不描述任何真实芯片。存在的理由：GPU 架构换代快（sm_70→80→89→90 每代指令集都变），但用户拿老 PyTorch 装新卡期望直接能跑。中间抽象一层，新卡上市时**驱动 JIT** 现场把 PTX 翻成新卡的 SASS，旧二进制获得生命力。

**类比 Java**：源码→javac→**JVM 字节码**（跨平台）→目标机器 JIT 成机器码 ≙ CUDA C→nvcc→**PTX**（跨代 GPU）→驱动 JIT 成 SASS。

PTX 读法要点（示例）：

```text
mov.s32        %r2, %ctaid.x;      // 专用寄存器 %ctaid = blockIdx（硬件填）
mul.lo.s32     %r4, %r2, %r3;      // 类型后缀跟指令走：有符号乘取低半
setp.lt.s32    %p1, %r6, %r1;      // 谓词寄存器 %p1 = (i < N)
@!p1 bra       SKIP;               // 条件跳转（源码的 if 到这层变成显式分支）
ld.global.f32  %f1, [%rd5];        // 显存读再也藏不住——看 PTX 能数出打几次显存
```

- **无限寄存器**：%r/%rd(64位)/%f(浮点)/%p(谓词) 随便用，压进有限物理寄存器是 ptxas 的活
- 检查工具：`cuobjdump -ptx xxx.cubin` 直接抖出 PTX

### 2.2 SASS 与 JIT 陷阱

ptxas 做三件事：**寄存器分配**（虚拟 %r2~%r7 压进物理 r0~r3，决定每 SM 能塞几个 block）、**指令调度**（两条显存读之间插无关指令掩盖延迟）、**二进制编码**（每条 128-bit 指令字）。

`nvcc` 目标写法：

| 写法 | 产物 | 后果 |
|---|---|---|
| `-arch=sm_80` | 只有 SASS | 只认 Ampere，新卡跑不了 |
| `-arch=compute_80` | 只有 PTX | 靠驱动 JIT 兼容未来卡，**首跑巨慢** |
| `-gencode`（双放） | SASS+PTX | 老卡走现成 SASS，新卡走 JIT —— **fatbin** 名字的由来 |

两个实际撞过的报错：

- **新卡 + 老 PyTorch 首跑巨慢几秒** = 驱动在 JIT PTX（结果按"PTX内容+GPU型号"缓存磁盘，只慢第一次）
- **`no kernel image is available for execution on the device`** = 老 fatbin SASS 太旧、PTX 也太旧（新驱动放弃支持老虚拟架构），两头没得翻译

### 2.3 谁生产 PTX、谁消费 PTX

| 生产者 | 说明 |
|---|---|
| nvcc | 编 CUDA C 时生成，打包进 fatbin |
| **Triton**（torch.compile 后端） | Python kernel → PTX → 驱动/ptxas JIT。**torch.compile 首跑要编译几分钟**的物理原因；产物缓存 `~/.triton/cache` |
| PyTorch 内置算子 | AOT 预编译，SASS+PTX 打包在 `libtorch_cuda.so` |

消费端唯一：**驱动内置 JIT 编译器**（cuModuleLoad 时无现成 SASS 则 JIT）。

### 2.4 cubin = ELF

ELF 头固定 `7f 45 4c 46`（`\x7fELF`）。关键 section：

- `.text` — SASS 指令字节流
- `.nv.info` — 元数据：每线程寄存器数、共享内存用量、blockDim（驱动加载时读，决定 SM 资源分配）

## 3. 运行期八步全流程

前 4 步是**编译期**（只发生一次）；5~8 步是**运行期**（每次进程启动都走）。

```text
① 编码      写 CUDA C：C[i]=A[i]+B[i]，每线程一个元素（纯文本）
② nvcc→PTX  虚拟 ISA，不绑芯片
③ ptxas→SASS 真机器码，寄存器已分配
④ 打包 cubin ELF 格式（magic 7f454c46）
   ──────── 编译期 ↓ 运行期 ────────
⑤ cuModuleLoad 驱动验 ELF → 解析段头表找 .text → SASS 上传显存 → 登记函数句柄
⑥ H2D        DMA 引擎把输入穿过 PCIe 搬进显存（A@0x20000, B@0x30000）—— 数据就位
⑦ Launch     参数打包(只有地址!) → 写 pushbuffer → 碰门铃 → GigaThread 分发
             block→SM → SM 拆 warp(32线程) → warp 锁步执行 SASS
⑧ D2H        DMA 引擎把结果搬回内存条校验
```

### 3.1 物理前提：两个内存隔离的世界

```text
        CPU 世界（主机）                          GPU 世界（设备）
┌───────────────────────┐        ┌────────────────────────────┐
│  内存条 DDR5           │  PCIe  │  显存 GDDR/HBM              │
│  a_data = [1,2,...]   │ ~25GB/s│  0x20000: [1,2,...] ←H2D    │
│  pushbuffer 命令缓冲   │ ─────► │  0x1000:  SASS 代码         │
│                       │        │  ⚠ GPU 够不着 CPU 内存条      │
└───────────────────────┘        └────────────────────────────┘
```

### 3.2 H2D 与 Launch 的分工（最易混）

| | H2D（第⑥步） | Launch（第⑦步） |
|---|---|---|
| 干什么 | 搬**数据**进显存 | 发**命令**（不含数据） |
| param 内容 | — | **全是地址**：`A=0x20000, B=0x30000, C=0x40000, N=8`，28 字节无一字节是向量本身 |
| 执行者 | **DMA 拷贝引擎**（不是 SM） | GigaThread → SM |
| 大数据怎么办 | — | 传不了！大东西必须先 H2D 进显存，参数只留指针（kernel 参数空间几 KB 顶天） |

**顺序坑**：先 launch 后 H2D → kernel 读到显存残留（通常全 0 或上进程垃圾）→ **一声不吭算出错误结果**，不报错不崩溃。CUDA 无初始化/越界检查。

> vLLM 联系：启动慢的主因 = 几十 GB 权重一次性 H2D；之后每 decode 步只有小张量在**显存内部**流动，不再跨 PCIe。

### 3.3 执行层级：Grid → Block → Warp → Thread

```text
Grid（一次 launch 的全部线程）
 └─ Block（分配到单个 SM 的线程组，共享 shared memory）
     └─ Warp = 32 线程，GPU 实际的锁步执行单位
         └─ Thread（ lane，各自寄存器）
```

- GigaThread 引擎把 block 按资源占用（寄存器/shared mem）分发到各 SM
- SM 内 warp 调度器把 block 拆成 warp，锁步执行同一条指令
- kernel 专用寄存器：`%ctaid.x`=blockIdx、`%tid.x`=threadIdx、`%ntid.x`=blockDim

## 4. 两大图优化（对应 enforce_eager 关掉的东西）

### 4.1 torch.compile —— 优化 kernel 本身

三步：**抓图**（TorchDynamo 把几百行 Python 翻成算子图）→ **融合**（核心收益：RMSNorm 类 4 算子合 1 kernel，中间结果不落显存——显存带宽是稀缺资源）→ **生成代码**（Inductor 出 Triton kernel，运行时 JIT）。

代价：启动编译几分钟（有磁盘缓存）；shape 变化触发重编译。

### 4.2 CUDA Graph —— 消除 launch 调度

torch.compile 精简后仍剩几十次 launch。CUDA Graph 把**整段命令流原样录制**，之后每步一次 `replay()`，GPU 命令处理器自己消化，CPU 全程旁路。

**硬约束（录制时固化的东西）**：

- 图里引用的 param buffer 地址、输入输出地址都是录制时的**物理地址** → 新数据必须先拷进录制时的固定显存槽位
- shape 必须匹配已捕获档位

**vLLM 的实际做法**（见 [[sources/推理引擎/vLLM 对外接口与运行参考]]）：

1. 启动 profile 阶段，对常用 batch size 各捕获一档图（1, 2, 4, 8, 16…）
2. 运行时 batch=5 → padding 到 8（空位填无效数据），真实数据拷进固定槽位，重放 batch=8 那版图
3. **捕获要预留显存** → 捕获失败常报 "CUDA error: out of memory"；显存紧时 `--enforce-eager` 或降 `--cuda-graph-max-bs`
4. 真实 launch 开销路径见 [[sources/推理引擎/vllm]] 的 `--enforce-eager` 参数表

### 4.3 两者关系：一层管 kernel，一层管调度

| | 优化对象 | 效果 |
|---|---|---|
| torch.compile | kernel 本身（融合/减少数量） | 300 个 → 几十个 |
| CUDA Graph | kernel 序列的调度方式 | 几十次 launch → 1 次重放 |

可叠加：先 compile 精简图，再 Graph 录制重放。**CPU 部署（vLLM CPU 后端 / OpenVINO / ONNX Runtime）时两者收益有限**：CUDA Graph 是 CUDA 专属机制根本不可用；CPU 瓶颈在内存带宽与算力而非 launch 调度，且 CPU 后端 compile 支持不完善 → `enforce_eager=True` 几乎无损失。

## 5. Launch 开销的完整路径（5~10µs 花在哪）

```text
CPU 侧                                    GPU 侧
kernel<<<grid, block>>>(args)
  │ 1. 参数打包进 param buffer
  │ 2. 驱动组装 launch 命令（kernel 句柄、
  │    grid/block 维度、参数地址、shared mem 大小）
  │ 3. 写入 pushbuffer（主存里的环形命令缓冲区）
  │ 4. 碰门铃 doorbell 通知 GPU
  │                                        5. 命令处理器取走命令
  │                                        6. GigaThread：按 grid 生成全部
  │                                           block，分发到各 SM
  │                                        7. SM 拆 warp，排进执行单元
  │                                        8. warp 从显存取 SASS 流水执行
  │                                        9. 全部 block 完成 → kernel 结束
```

全是 CPU 侧固定成本（软件调用链+打包+屏障+门铃），与 kernel 计算量无关——这就是每次 5~10µs 的来源。

## 6. pushbuffer 统一视角：三种命令、两个执行者

H2D、launch、D2H 本质都是**写进同一个 pushbuffer 的命令**，只是执行者不同：

```text
pushbuffer 命令流：
[H2D 拷贝A] [H2D 拷贝B] [launch vector_add] [D2H 拷贝C]
   ▲ DMA 引擎执行     ▲ GigaThread→SM 执行       ▲ DMA 引擎执行
```

命令队列是异步的，CPU 可连发很多、GPU 排队消化——这正是"CPU 领先跑、GPU 在后面追"的原因，也是 CUDA Graph 重放能绕开 CPU 的机制基础。

## 7. 常见误解澄清

| 误解 | 澄清 |
|---|---|
| "kernel 启动"是 Linux kernel？ | 不是。GPU kernel = 编译后在 GPU 上被数千线程并行执行的**函数**。"Linux kernel"（操作系统内核）只是 launch 路径路过的东西：CPU→CUDA runtime→NVIDIA 驱动(nvidia.ko 内核态)→GPU 执行 GPU kernel |
| kernel 还有一个含义 | CNN 的卷积核（滑动小权重矩阵，如 3×3），与前两者无关 |
| launch 传的是数据？ | 只传**地址**+维度。数据必须先 H2D 搬进显存 |
| PTX 是机器码？ | 是虚拟 ISA 文本汇编；SASS 才是机器码。新卡跑老二进制首跑慢 = 驱动在 JIT PTX |

## 8. 本地可运行演示

- `scratch/gpu-kernel-sim/gpu_sim.py` — 零依赖纯 Python 模拟器，真实走：编码→PTX(带注释)→SASS(反汇编)→**真 ELF 字节的 cubin**(驱动按段头表解析)→显存上传→param buffer 打包(hex 可见)→门铃→GigaThread→SM/warp 逐 lane 执行→结果校验；彩蛋：eager 5 步 vs CUDA Graph 录制+4 次重放的 CPU 开销对比
- `scratch/gpu-kernel-sim/gpu_flow.html` — 8 步可视化图解（颜色区分 CPU/命令/数据搬运，含顺序坑提示）

## 9. 学习检查点

- [ ] 能说出 PTX 与 SASS 的分工，以及 fatbin 为什么"胖"
- [ ] 能解释 launch 的 param buffer 里为什么全是地址
- [ ] 能画出 H2D/launch/D2H 与 DMA 引擎/SM 的执行者对应关系
- [ ] 能解释 enforce_eager=True 省了什么、代价是什么
- [ ] 能说出 CUDA Graph 重放为什么要求"数据拷进固定槽位、shape 匹配档位"

---

> 关联：[[50-reference/sources/chips/GPU AI 加速器]]（芯片全景）· [[concepts/cuBLAS 线性代数库]]（内置算子即编译好的 kernel）· [[concepts/TensorRT 推理优化器]]（另一条图优化路线）· [[sources/推理引擎/vLLM-Deep-Dive]]（引擎侧应用）
