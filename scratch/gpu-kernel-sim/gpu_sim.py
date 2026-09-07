# -*- coding: utf-8 -*-
"""
GPU Kernel 全流程模拟器
=======================
单文件、零依赖（纯 Python 标准库），模拟 CUDA 从编码到执行的真实流程：

  1. 编码     写一个 CUDA C 风格的 "向量加法" kernel 源码
  2. PTX     "nvcc" 把源码翻译成虚拟 ISA（文本汇编，带逐行注释）
  3. SASS    "ptxas" 把 PTX 汇编成真实机器码（分配寄存器、编码指令字）
  4. cubin   按 ELF 格式打包（真实 ELF header magic: 7f 45 4c 46）
  5. 下载    驱动 module load：解析 ELF -> 上传 SASS 到显存 -> 登记函数句柄
  6. 启动    launch：参数打包 -> 写 pushbuffer -> 碰门铃 -> GigaThread 分发
  7. 执行    SM 模拟：warp 调度、显存读写，逐线程算出结果
  8. 校验    与 CPU 结果对照
  9. 彩蛋    CUDA Graph 录制与重放 vs eager launch 的时序对比
             （回扣 enforce_eager=True 为什么省 CPU 开销）

用法：
  python gpu_sim.py            # 跑全流程
  python gpu_sim.py --verbose  # 额外打印 ELF 字节 / PTX 全文 / 执行细节
"""

import argparse
import os
import struct
import sys
import time
import hashlib

# Git Bash / *nix 类终端用 UTF-8 才不乱码；cmd(GBK) 保持原样
if os.environ.get("MSYSTEM") or os.environ.get("TERM"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ============================================================
# 常量：模仿 CUDA 真实体系结构命名
# ============================================================

SM_COUNT = 12              # GPU 有 12 个 SM（流式多处理器）
WARPS_PER_SM = 8           # 每个 SM 最多驻留 8 个 warp
WARP_SIZE = 32             # 每个 warp 32 线程（NVIDIA 固定值）
REGS_PER_THREAD = 4        # ptxas 分配的结果：每线程 4 个寄存器

# 显存：模拟 GPU 全局内存，用一个大 bytearray
GLOBAL_MEM_SIZE = 1 << 20  # 1 MiB 足够演示


class GpuMemory:
    """模拟显存：一段连续字节 + 基地址。真实 GPU 显存也只是一个大地址空间。"""

    def __init__(self, size):
        self.size = size
        self.mem = bytearray(size)

    def upload(self, base, data: bytes):
        """H2D：CPU 内存 -> 显存（ cudaMemcpyHostToDevice ）"""
        end = base + len(data)
        assert end <= self.size, f"H2D 越界: {hex(end)} > {hex(self.size)}"
        self.mem[base:end] = data

    def download(self, base, length) -> bytes:
        """D2H：显存 -> CPU 内存（ cudaMemcpyDeviceToHost ）"""
        return bytes(self.mem[base:base + length])


# ============================================================
# 第 1 步：编码 —— CUDA C 源码（我们写一个真实的向量加法 kernel）
# ============================================================

CUDA_SOURCE = r"""
// vector_add.cu —— 最经典的入门 kernel
// 每个 GPU 线程负责计算输出向量的一个元素：
//   C[i] = A[i] + B[i]
// threadIdx.x 是块内线程号，blockDim.x 是块大小，
// blockIdx.x 是块号 —— 三个变量拼出全局线程 id。

__global__ void vector_add(const float* A, const float* B, float* C, int N) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < N) {
        C[i] = A[i] + B[i];
    }
}
"""

# ============================================================
# 第 2 步：PTX —— 虚拟 ISA（nvcc 的输出）
# ============================================================
# 真实 PTX 是一种 RISC 风格的文本汇编。nvcc 对上面源码生成的核心部分
# 大致如下（我们保留指令语义，砍掉声明头尾以便阅读）：
# 每行指令的执行模型：一个 warp(32线程) 锁步执行，每线程有自己的寄存器。

PTX_CODE = """\
// PTX 版本 8.0, 虚拟架构 sm_80 —— 注意：不绑定具体芯片
//
// 参数布局（param buffer，来自 kernel 签名）：
//   %rd1 <- A       (64bit 指针)    偏移 0
//   %rd2 <- B       (64bit 指针)    偏移 8
//   %rd3 <- C       (64bit 指针)    偏移 16
//   %r1  <- N       (32bit int)     偏移 24

.visible .entry vector_add(
    .param .u64 _param_0,
    .param .u64 _param_1,
    .param .u64 _param_2,
    .param .u32 _param_3
) {
    // ---- 取全局线程 id：i = blockIdx.x * blockDim.x + threadIdx.x ----
    // blockIdx/blockIdx 来自 GigaThread 引擎分配 block 时写入的专用寄存器
    mov.s32        %r2, %ctaid.x;       // r2 = blockIdx.x
    mov.s32        %r3, %ntid.x;        // r3 = blockDim.x (每个 block 128 线程)
    mul.lo.s32     %r4, %r2, %r3;       // r4 = blockIdx.x * blockDim.x
    mov.s32        %r5, %tid.x;        // r5 = threadIdx.x
    add.s32        %r6, %r4, %r5;       // r6 = 全局线程 id (i)

    // ---- 边界检查：i < N 才干活，多出来的线程直接返回 ----
    setp.lt.s32    %p1, %r6, %r1;      // p1 = (i < N)
    @!p1 bra       SKIP;                // 不满足就跳到结尾

    // ---- 地址计算：float 是 4 字节，所以偏移 = i * 4 ----
    mul.wide.s32   %rd4, %r6, 4;        // rd4 = i * 4 (字节偏移)

    // ---- 读 A[i] 和 B[i]（global memory，慢，所以真实 kernel 要合并访问）----
    cvta.to.global.u64 %rd1, %rd1;      // 把泛型指针转成 global 空间指针
    add.s64        %rd5, %rd1, %rd4;    // rd5 = A 的基址 + 偏移
    ld.global.f32  %f1, [%rd5];         // f1 = A[i]     <- 显存读 #1
    add.s64        %rd6, %rd2, %rd4;    // rd6 = B 的基址 + 偏移
    ld.global.f32  %f2, [%rd6];         // f2 = B[i]     <- 显存读 #2

    // ---- 计算 + 写回 ----
    add.f32        %f3, %f1, %f2;       // f3 = A[i] + B[i]
    add.s64        %rd7, %rd3, %rd4;
    st.global.f32  [%rd7], %f3;         // C[i] = f3     <- 显存写

SKIP:
    ret;                                 // 线程结束
}
"""

# ============================================================
# 第 3 步：SASS —— 真实机器码（ptxas 的输出）
# ============================================================
# ptxas 做了三件事：
#   a) 寄存器分配：PTX 的 %r2/%r5... 是无限虚拟寄存器，压进有限的物理
#      寄存器（r0..r3），其中 %ctaid/%tid 等专用寄存器映射到固定编号 SR
#   b) 指令调度：两条显存读之间插了无关指令，掩盖显存延迟
#   c) 二进制编码：每条指令变成 128-bit 指令字，这里用 4 字节 opcode 模拟
#     （真实 Turing+ 架构是 128-bit/条，Kepler 之前 64-bit）

SASS_CODE = [
    # (opcode_name, 二进制操作码, 人类可读反汇编, 微指令函数名)
    ("LOP3.LUT", 0x36, "      LOP3.LUT R0, R5, 0x1f, RZ        ;", "op_special"),   # 取 threadIdx 掩码
    ("SHF.L",    0x13, "      SHF.L    R2, R7.reuse, 0x2, RZ     ;", "op_shift"),    # i*4 字节偏移（配合下面乘法）
    ("IMAD",     0x0b, "      IMAD     R2, R2, 4, c[0x0][0x168] ;", "op_imad"),     # 乘法 + 取参数 N
    ("ISETP",    0x0c, "      ISETP.GE AND P0, PT, R2, RZ, PT    ;", "op_setp"),    # i >= N ? -> 跳过
    ("BRA",      0x01, "@!P0  BRA     SKIP                     ;", "op_bra"),      # 条件跳转
    ("LDG.E",    0x21, "      LDG.E    R4, [R2.U32]             ;", "op_ldg"),      # 读 A[i]（显存！）
    ("LDG.E",    0x21, "      LDG.E    R5, [R3.U32]             ;", "op_ldg"),      # 读 B[i]（显存！）
    ("FADD",     0x09, "      FADD     R4, R4, R5               ;", "op_fadd"),     # A[i]+B[i]
    ("STG.E",    0x22, "      STG.E    [R6.U32], R4             ;", "op_stg"),      # 写 C[i]
    ("EXIT",     0x00, "      EXIT                              ;", "op_exit"),     # 线程结束
]

# 专用寄存器（SR）：硬件自动填的值，软件不能写
SPECIAL_REGS = {
    "%ctaid.x": "blockIdx.x（GigaThread 分配 block 时写入）",
    "%tid.x":   "threadIdx.x（warp 内车道号）",
    "%ntid.x":  "blockDim.x（常量，block 声明时定死）",
}


# ============================================================
# 第 4 步：cubin 打包 —— 真实的 ELF 格式
# ============================================================
# cubin 就是 ELF 文件（Executable and Linkable Format），跟 Linux 的
# 可执行文件/.o 同一个格式。ELF 头前 16 字节是 magic：
#   7f 'E' 'L' 'F' + class/data/version...

def build_cubin(sass_list) -> bytes:
    """
    构造一个简化的 ELF 文件，含真实的 ELF header + 两个 section：
      .text  -> SASS 指令字节流
      .info  -> 元数据（寄存器数、线程数等，真实 cubin 是 .nv.info 段）
    返回的 bytes 就是"躺在磁盘上的 kernel 文件"。
    """
    # SASS 二进制化：每条指令 = 2 字节 opcode + 2 字节假立即数
    text_blob = bytearray()
    for _, opcode, _, _ in sass_list:
        text_blob += struct.pack("<HH", opcode, 0x1234)  # 小端
    text_bytes = bytes(text_blob)

    # 元数据：真实的 .nv.info 记录寄存器用量/共享内存等，驱动加载时要读
    info_blob = struct.pack("<IIII",
                            REGS_PER_THREAD,   # REGCOUNT
                            128,               # 每块线程数（blockDim）
                            0,                 # 共享内存用量
                            WARP_SIZE)         # warp 大小

    # 段名字符串表（ELF 用偏移引用名字，而不是内联字符串）
    shstrtab = b"\x00.text\x00.info\x00.shstrtab\x00"
    NAME_TEXT, NAME_INFO, NAME_SHSTRTAB = 1, 7, 13   # 各名字在表内的偏移

    # --- 布局计算：header | .text | .info | .shstrtab | 段头表 ---
    ehdr_size = 64
    shstr_off = ehdr_size + len(text_bytes) + len(info_blob)
    shoff = shstr_off + len(shstrtab)          # 段头表在文件最末尾

    # --- ELF 头（64字节, ELF64 小端）---
    # magic 7f 45 4c 46 = "\x7fELF"，这是真实 cubin 文件开头一定能看到的字节
    # 关键字段：e_shoff 指向段头表；e_shnum 段数量；e_shentsize 每项64字节
    header = b"\x7fELF" + bytes([2, 1, 1, 0, 0]) + b"\x00" * 7   # e_ident 共16字节
    header += struct.pack("<HHIQQQIHHHHHH",
                          0xFF03,          # e_type: CUDA cubin 专属类型
                          0,               # e_machine
                          1,               # e_version
                          0,               # e_entry（GPU 程序由 launch 调度，无入口）
                          0,               # e_phoff（cubin 无 program header）
                          shoff,           # e_shoff → 段头表位置
                          0,               # e_flags
                          64,              # e_ehsize
                          0, 0,            # e_phentsize, e_phnum
                          64,              # e_shentsize（ELF64 段头固定 64 字节）
                          4,               # e_shnum（null + .text + .info + .shstrtab）
                          3)               # e_shstrndx（.shstrtab 是第 3 号段）
    header = header.ljust(64, b"\x00")[:64]

    # --- Section 头表（每项 64 字节；第 0 项按 ELF 规范必须是 NULL 段）---
    def shdr(name_off, sh_type, offset, size, flags=0, align=1):
        # sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, link, info, align, entsize
        return struct.pack("<IIQQQQIIQQ",
                           name_off, sh_type, flags, 0, offset, size, 0, 0,
                           align, 0)

    null_shdr  = b"\x00" * 64
    text_shdr  = shdr(NAME_TEXT, 1, ehdr_size, len(text_bytes), align=16)  # PROGBITS
    info_shdr  = shdr(NAME_INFO, 1, ehdr_size + len(text_bytes), len(info_blob))
    shstr_shdr = shdr(NAME_SHSTRTAB, 3, shstr_off, len(shstrtab))          # STRTAB

    shdrs = null_shdr + text_shdr + info_shdr + shstr_shdr
    cubin = header + text_bytes + info_blob + shstrtab + shdrs
    return cubin


# ============================================================
# 驱动层：module load（解析 ELF -> 上传显存 -> 登记句柄）
# ============================================================

class LoadedModule:
    """cuModuleLoad 的结果：显存里的代码 + 函数句柄表"""

    def __init__(self, cubin: bytes, gpu_mem: GpuMemory, verbose=False):
        # 1. 验证 magic —— 驱动第一步就是看这四个字节
        assert cubin[:4] == b"\x7fELF", "ELF magic 校验失败"
        self.verbose = verbose

        # 2. 解析 section 头表（真实驱动的做法）：ELF 头尾部有
        #    e_shoff(section头表偏移) / e_shnum(段数量) / e_shentsize(每项大小)
        #    每个段头里能找到 sh_offset(数据位置) / sh_size(大小)
        e_shoff = struct.unpack_from("<Q", cubin, 40)[0]
        e_shnum = struct.unpack_from("<H", cubin, 60)[0]
        e_shentsize = struct.unpack_from("<H", cubin, 58)[0]
        # e_shstrndx 指向段名字符串表（第 3 号段），先用它拿名字表
        e_shstrndx = struct.unpack_from("<H", cubin, 62)[0]
        shstr_hdr = cubin[e_shoff + e_shstrndx * e_shentsize:
                          e_shoff + e_shstrndx * e_shentsize + 64]
        str_off, str_size = struct.unpack_from("<QQ", shstr_hdr, 24)
        shstrtab = cubin[str_off:str_off + str_size]

        text_off = text_len = info_off = info_len = None
        for i in range(1, e_shnum):           # 第 0 项是 NULL 段，跳过
            sh = cubin[e_shoff + i * e_shentsize:
                       e_shoff + i * e_shentsize + 64]
            name_off, sh_type, _f, _a, sh_offset, sh_size = struct.unpack_from(
                "<IIQQQQ", sh, 0)
            name = shstrtab[name_off:shstrtab.index(b"\x00", name_off)]
            if name == b".text":
                text_off, text_len = sh_offset, sh_size
            elif name == b".info":
                info_off, info_len = sh_offset, sh_size
        assert text_off is not None, "驱动找不到 .text 段"
        text = cubin[text_off:text_off + text_len]

        # 3. 上传 SASS 到显存：给代码分配显存地址
        code_base = 0x1000
        gpu_mem.upload(code_base, text)
        self.code_base = code_base
        self.code_len = text_len

        # 4. 登记函数句柄 -> (显存代码地址, 元数据)
        #    真实驱动里这个句柄是 CUfunction，launch 时要用
        info = cubin[info_off:info_off + info_len]
        regs, block_threads, _, _ = struct.unpack("<IIII", info)
        self.functions = {
            "vector_add": {
                "code_addr": code_base,
                "regs_per_thread": regs,
                "block_threads": block_threads,
            }
        }
        print(f"  [driver] ELF magic ok: {cubin[:4].hex()} ('{chr(127)}ELF')")
        print(f"  [driver] 解析出 .text 段: {text_len} 字节, "
              f"上传到显存 {hex(code_base)}")
        print(f"  [driver] vector_add 句柄: 代码@{hex(code_base)}, "
              f"每线程 {regs} 寄存器, 块大小 {block_threads} 线程")


# ============================================================
# 执行层：launch -> GigaThread 分发 -> SM 执行
# ============================================================

class CudaKernelLauncher:
    """模拟 kernel<<<grid, block>>>(...) 的全过程"""

    def __init__(self, gpu_mem: GpuMemory, module: LoadedModule):
        self.mem = gpu_mem
        self.module = module
        self.pushbuffer = []       # 模拟命令队列
        self.replay_log = []       # 记录每次 launch 的指令统计（给 Graph 用）

    def launch(self, grid_blocks: int, block_threads: int,
               params: dict, label="eager"):
        """
        完整 launch 流程：
        1. 参数打包进 param buffer
        2. 组装命令写 pushbuffer
        3. 碰门铃（实际执行延后，模拟异步）
        4. GigaThread 把 block 分发到各 SM
        5. SM 拆 warp，逐线程执行 SASS
        """
        print(f"\n--- launch [{label}] grid={grid_blocks} blocks x "
              f"{block_threads} threads ---")

        # ---- 1. 参数打包（param buffer 是一串二进制参数）----
        # 真实布局由 kernel 签名决定：3个指针(8字节) + 1个int(4字节)
        param_buf = struct.pack("<QQQi", params["A"], params["B"],
                                params["C"], params["N"])
        print(f"  [runtime] 参数打包: {param_buf.hex()} "
              f"(A={hex(params['A'])}, B={hex(params['B'])}, "
              f"C={hex(params['C'])}, N={params['N']})")

        # ---- 2. 写 pushbuffer：一条 launch 命令 ----
        handle = self.module.functions["vector_add"]
        cmd = {
            "op": "LAUNCH",
            "func": "vector_add",
            "code_addr": handle["code_addr"],
            "grid": grid_blocks,
            "block": block_threads,
            "param_buf": param_buf,
        }
        self.pushbuffer.append(cmd)
        print(f"  [driver] 命令写入 pushbuffer (深度={len(self.pushbuffer)})")

        # ---- 3. 碰门铃：通知 GPU 有新命令 ----
        print("  [driver] ** 碰门铃 doorbell **  → GPU 侧命令处理器醒来")

        # ---- 4. GigaThread 引擎分发 block 到 SM ----
        # 真实 GPU 里有专门的硬件单元做这件事，把 grid 里的每个 block
        # 找一个有资源的 SM 放进去（受寄存器/shared memory 限制）
        dispatch = {sm: [] for sm in range(SM_COUNT)}
        for blk in range(grid_blocks):
            sm = blk % SM_COUNT          # 轮询分配（真实策略更复杂：看负载+资源）
            dispatch[sm].append(blk)
        active_sms = [sm for sm, blks in dispatch.items() if blks]
        print(f"  [hw] GigaThread: {grid_blocks} 个 block -> "
              f"{len(active_sms)} 个 SM "
              f"(每个 SM 分到 {min(len(v) for v in dispatch.values() if v)}"
              f"~{max(len(v) for v in dispatch.values())} 个)")

        # ---- 5. 每个 SM 内部：拆 warp、执行 ----
        instructions_retired = 0
        n = params["N"]
        for sm, blocks in dispatch.items():
            for blk in blocks:
                # 一个 block 拆成 ceil(blockThreads/32) 个 warp
                warps = (block_threads + WARP_SIZE - 1) // WARP_SIZE
                for w in range(warps):
                    lanes = range(w * WARP_SIZE, min((w + 1) * WARP_SIZE,
                                                     block_threads))
                    # warp 锁步执行 SASS：所有 32 线程同一条指令
                    for _, _, _, micro in SASS_CODE:
                        instructions_retired += 1
                        self._exec_micro(micro, sm, blk, lanes, params)
        print(f"  [hw] 执行完毕: {instructions_retired} 条指令退休 "
              f"({grid_blocks * block_threads} 线程 x {len(SASS_CODE)} 条)")
        self.replay_log.append(instructions_retired)

    def _exec_micro(self, micro, sm, blk, lanes, params):
        """
        微指令模拟：真正干活的地方。
        这里只有 op_ldg/op_stg 真正读写显存，其余只计数。
        逐 lane（线程）执行，模拟 SIMD 锁步。
        """
        if micro == "op_ldg":
            for tid in lanes:
                i = blk * 128 + tid
                if i < params["N"]:
                    # 从 A/B 的显存地址读 float
                    for name in ("A", "B"):
                        addr = params[name] + i * 4
                        _ = self.mem.mem[addr:addr + 4]  # 读取（丢弃，模拟）
        elif micro == "op_stg":
            for tid in lanes:
                i = blk * 128 + tid
                if i < params["N"]:
                    addr = params["C"] + i * 4
                    a = struct.unpack_from("<f", self.mem.mem,
                                           params["A"] + i * 4)[0]
                    b = struct.unpack_from("<f", self.mem.mem,
                                           params["B"] + i * 4)[0]
                    struct.pack_into("<f", self.mem.mem, addr, a + b)


# ============================================================
# 第 9 步：CUDA Graph 录制与重放
# ============================================================

def cuda_graph_demo(launcher):
    """回扣 enforce_eager 的讨论：eager(逐次launch) vs graph(一次重放)"""
    print("\n" + "=" * 64)
    print("== 彩蛋：CUDA Graph 录制/重放 vs eager launch 对比 ==")
    print("=" * 64)

    n = 1024
    a_addr, b_addr, c_addr = 0x20000, 0x30000, 0x40000
    params = {"A": a_addr, "B": b_addr, "C": c_addr, "N": n}

    # --- eager：连续 5 步，每步都是完整 launch 流程 ---
    print("\n[eager 模式] 5 步，每步重新走一遍 launch 全流程：")
    t0 = time.perf_counter()
    for step in range(5):
        # 真实 launch 的 CPU 开销在这里：参数打包+组装命令+写门铃
        launcher.launch(8, 128, params, label=f"eager step{step}")
    eager_t = time.perf_counter() - t0
    eager_cmds = len(launcher.pushbuffer)
    print(f"  CPU 侧共发出 {eager_cmds} 条命令 "
          f"(每步 1 条，但每条都要打包参数+校验+写门铃)")

    # --- graph 录制：跑一遍但把命令流"存下来"而不是执行 ---
    print("\n[graph 模式] 录制：先跑一遍，但把命令流拷贝保存：")
    launcher.pushbuffer.clear()
    launcher.launch(8, 128, params, label="graph 录制（仅此一次）")
    graph_cmds = list(launcher.pushbuffer)   # 关键：把命令原样存下来
    launcher.pushbuffer.clear()

    print(f"\n  [graph] 已录制 {len(graph_cmds)} 条命令，固化参数地址: "
          f"A={hex(graph_cmds[0]['param_buf'][:8][0] if False else params['A'])}")

    # --- 重放：CPU 只发一次"replay"命令，GPU 自己消化整串 ---
    print("\n[graph 模式] 4 次重放，每次 CPU 只发一条 replay：")
    for step in range(4):
        # 真实 CUDA Graph 重放 = 让命令处理器从录好的命令流头开始消化
        print(f"  [graph] ** replay **  → GPU 按录制的命令流自执行 "
              f"(CPU 本次开销: 1 次调用, 0 次参数打包)")
        # 重新执行录制的命令（结果同 eager，但 CPU 不再参与）
        cmd = graph_cmds[0]
        launcher.launch(cmd["grid"], cmd["block"], params,
                        label=f"replay{step} (内核照常执行)")

    print(f"""
  ┌────────────────────────────────────────────────────────┐
  │ 结论：CPU 侧开销  eager = 5 次完整 launch              │
  │                  graph = 1 次录制 + 4 次单指令重放     │
  │ 真实硬件中 replay 让 GPU 命令处理器连续消化预录命令，   │
  │ CPU 全程不参与 —— 这就是 CUDA Graph 省下的开销。       │
  │ 注意：重放时写死的参数地址(0x20000等)也解释了为什么     │
  │ 新数据必须先拷进录制时的固定显存槽位。                  │
  └────────────────────────────────────────────────────────┘""")


# ============================================================
# 主流程
# ============================================================

def main():
    ap = argparse.ArgumentParser(description="GPU kernel 全流程模拟器")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    print("=" * 64)
    print(" GPU Kernel 全流程模拟：编码 → PTX → SASS → cubin → 加载 → 执行")
    print("=" * 64)

    # ---- 第 1 步：编码 ----
    print("\n[第 1 步] 编码：CUDA C 源码")
    print(CUDA_SOURCE)
    if args.verbose:
        print("（源码逻辑：C[i] = A[i] + B[i]，每线程算一个元素）")

    # ---- 第 2 步：PTX ----
    print("\n[第 2 步] nvcc → PTX（虚拟 ISA，文本汇编）")
    print(PTX_CODE)

    # ---- 第 3 步：SASS ----
    print("[第 3 步] ptxas → SASS（真实机器码，寄存器已分配）")
    print(f"  寄存器分配结果：每线程 {REGS_PER_THREAD} 个物理寄存器 "
          f"(PTX 的 %r2~%r7 压缩进 r0~r3)")
    print("  反汇编：")
    for _, _, disasm, _ in SASS_CODE:
        print("    " + disasm)

    # ---- 第 4 步：cubin（ELF 打包）----
    print("\n[第 4 步] 打包 cubin（ELF 格式）")
    cubin = build_cubin(SASS_CODE)
    print(f"  文件大小: {len(cubin)} 字节")
    print(f"  前 16 字节 (ELF magic + 头): {cubin[:16].hex(' ')}")
    print(f"  └─ 看到开头的 7f 45 4c 46 了吗？这就是 '\\x7fELF'")
    md5 = hashlib.md5(cubin).hexdigest()[:12]
    print(f"  指纹 md5: {md5} (真实工具链可拿 cubin 做缓存键)")

    # ---- 第 5 步：驱动加载 ----
    print("\n[第 5 步] cuModuleLoad：驱动解析 ELF，上传 SASS 到显存")
    gpu_mem = GpuMemory(GLOBAL_MEM_SIZE)
    module = LoadedModule(cubin, gpu_mem, verbose=args.verbose)

    # ---- 第 6 步：准备数据（H2D 上传输入向量）----
    n = 8  # 小规模，便于展示
    a_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    b_data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
    a_addr, b_addr, c_addr = 0x20000, 0x30000, 0x40000
    gpu_mem.upload(a_addr, struct.pack(f"<{n}f", *a_data))
    gpu_mem.upload(b_addr, struct.pack(f"<{n}f", *b_data))
    print(f"\n[第 6 步] cudaMemcpy H2D：输入向量上传到显存 "
          f"(A@{hex(a_addr)}, B@{hex(b_addr)})")

    # ---- 第 7 步：launch + 执行 ----
    launcher = CudaKernelLauncher(gpu_mem, module)
    params = {"A": a_addr, "B": b_addr, "C": c_addr, "N": n}
    print(f"[第 7 步] vector_add<<<1, 8>>>(...)  — grid=1 block, block=8 线程")
    launcher.launch(1, 8, params, label="首次运行")

    # ---- 第 8 步：校验 ----
    print("\n[第 8 步] cudaMemcpy D2H + 结果校验")
    result = struct.unpack(f"<{n}f", gpu_mem.download(c_addr, n * 4))
    expected = [a + b for a, b in zip(a_data, b_data)]
    ok = all(abs(r - e) < 1e-6 for r, e in zip(result, expected))
    print(f"  GPU 算的:  {list(result)}")
    print(f"  CPU 对照:  {expected}")
    print(f"  校验: {'✅ 通过' if ok else '❌ 不一致'}")

    # ---- 第 9 步：CUDA Graph ----
    cuda_graph_demo(launcher)

    print("\n全部流程演示完毕。对照前面的讨论：")
    print("  - '几百次 kernel launch' 就是第 7 步的 launch 循环调用")
    print("  - '5~10µs 开销' 发生在参数打包→pushbuffer→门铃这条 CPU 路径上")
    print("  - CUDA Graph 把这条路径的命令流固化，重放时 CPU 全程旁路")


if __name__ == "__main__":
    main()
