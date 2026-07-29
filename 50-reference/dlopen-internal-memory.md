---
title: dlopen 内部内存动作详解
category: reference
summary: >-
    一个 .so 文件（ET_DYN 类型）内部由多个 Section 组成，加载时真正关心的是这些：
created: 2026-07-29
updated: 2026-07-29
sources: []
tags: [kb]
base_confidence: 0.4
lifecycle: reviewed
---

# dlopen 内部内存动作详解

> 本文从内存视角，逐层剖析 dlopen 加载一个 .so 文件时在进程地址空间中发生的所有动作。
> 目标读者：理解 ELF 基础概念，但对动态加载的内存细节尚不清晰的工程师。

---

## 第〇章：前提知识

### 0.1 ELF 文件中的关键 Section

一个 .so 文件（ET_DYN 类型）内部由多个 Section 组成，加载时真正关心的是这些：

| Section                  | 作用                                       | 内存属性                         |
| ------------------------ | ---------------------------------------- | ---------------------------- |
| `.text`                  | 机器指令（函数体）                                | 只读 + 可执行 (RX)                |
| `.rodata`                | 常量数据（字符串常量、const 变量）                     | 只读 (R)                       |
| `.data`                  | 已初始化的全局/静态变量                             | 可读写 (RW)                     |
| `.bss`                   | 未初始化的全局/静态变量（文件中不占空间）                    | 可读写 (RW)，运行时零填充              |
| `.got`                   | 全局偏移表——存储符号的绝对地址                         | 加载时写，之后部分变只读                 |
| `.got.plt`               | 延迟绑定用的 GOT 子表                            | 可读写 (RW)，运行时被改               |
| `.plt` / `.plt.sec`      | 过程链接表——跳转桩代码                             | 只读 + 可执行 (RX)                |
| `.dynamic`               | 动态链接元数据（依赖列表、重定位表指针等）                    | 只读 (R)                       |
| `.rel.dyn` / `.rela.dyn` | 数据段的重定位条目                                | 加载时用，不映射到内存                  |
| `.rel.plt` / `.rela.plt` | PLT 的重定位条目                               | 加载时用，不映射到内存                  |
| `.symtab` / `.dynsym`    | 符号表                                      | `.dynsym` 映射，`.symtab` 通常不映射 |
| `.strtab` / `.dynstr`    | 符号名字字符串                                  | `.dynstr` 映射                 |
| `.init_array`            | 构造函数指针数组（`__attribute__((constructor))`） | 只读 (R)，加载后执行                 |

### 0.2 ELF 中的 Program Header（PT_LOAD）

文件中的 Section 只是逻辑划分。真正决定"哪些内容映射到内存、怎么映射"的是 **Program Header** 中的 `PT_LOAD` 类型条目。

一个典型 .so 有 2~3 个 PT_LOAD：

```
PT_LOAD[0]:  .text + .rodata + .plt + ...   →  RX 段
PT_LOAD[1]:  .data + .got + .got.plt + ...   →  RW 段
PT_LOAD[2]:  （有时 .text 和 .rodata 分开） →  R 段
```

**关键理解**：`dlopen` 不是逐个 Section 映射的，而是逐个 PT_LOAD 映射的。多个 Section 被打包在一个 PT_LOAD 里，共享同一段虚拟地址区间和同一种内存权限。

### 0.3 进程地址空间的"已有内容"

调用 `dlopen` 之前，进程地址空间中已经存在：

- **主程序 (a.out)** 的各 PT_LOAD 段
- **ld.so（动态链接器）** 自身——它也是 ELF，早已被映射
- **启动时已加载的依赖库**（如 libc.so、libm.so 等）
- **栈、堆、vdso 等**

`dlopen` 要做的是：在空闲的虚拟地址区间中，再插入一个新的 .so 的各段映射，并与已有的内容建立连接（符号解析、重定位）。

---

## 第一章：文件打开与映射

### 1.1 定位文件

```
dlopen("libfoo.so", RTLD_NOW)
  │
  ├─ 如果 filename == NULL → 返回主程序的 link_map handle
  │
  └─ 否则，搜索路径：
       1. DT_RPATH (已废弃)
       2. LD_LIBRARY_PATH 环境变量
       3. DT_RUNPATH (编译时 -Wl,-rpath)
       4. 默认路径 /lib、/usr/lib 等
       5. ldconfig 缓存 (/etc/ld.so.cache)
```

### 1.2 打开文件并 mmap

找到文件后，`_dl_map_object_from_fd()` 执行：

```
fd = open("libfoo.so", O_RDONLY | O_CLOEXEC)

// 第一步：读取 ELF header 和所有 Program Header
read(fd, ehdr, sizeof(Elf64_Ehdr))      // 64 字节
read(fd, phdr[], ehdr.e_phnum * sizeof(Elf64_Phdr))

// 第二步：为整个库分配一块连续的虚拟地址区间
//   先计算所有 PT_LOAD 的总跨度：
total_size = max_pt_load_vaddr + max_pt_load_memsz - min_pt_load_vaddr
//   在进程地址空间中找一个空闲位置：
load_base = _dl_find_free_address(total_size)

// 第三步：逐个 PT_LOAD 映射
```

### 1.3 逐个 PT_LOAD 的 mmap

这是最核心的内存动作。以一个有 2 个 PT_LOAD 的 .so 为例：

```
PT_LOAD[0]:  p_offset=0x0000  p_vaddr=0x0000  p_filesz=0x1000  p_memsz=0x1000  p_flags=RX
PT_LOAD[1]:  p_offset=0x1000  p_vaddr=0x2000  p_filesz=0x0100  p_memsz=0x0800  p_flags=RW
             （注意：vaddr 之间有 0x1000 的间隙，这是 .so 的典型布局）
```

映射过程：

```
对于 PT_LOAD[0]（RX 段——代码段）:

  mmap(load_base + 0x0000,       // 目标虚拟地址
       0x1000,                    // 映射长度 = p_filesz
       PROT_READ | PROT_WRITE,   // ⚠️ 注意：初始设为可写！
       MAP_PRIVATE | MAP_FIXED,  // MAP_PRIVATE = COW；MAP_FIXED = 指定地址
       fd,
       0x0000)                    // 文件偏移 = p_offset（需页对齐）

  → 结果：0x1000 字节的文件内容被映射到进程地址空间
  → 物理页：与磁盘文件共享（同一 .so 被多个进程加载时共享物理页）
  → 但 PROT_WRITE 意味着：进程可以写这段内存（暂时）
```

```
对于 PT_LOAD[1]（RW 段——数据段）:

  // 先映射文件内容部分（p_filesz）
  mmap(load_base + 0x2000,
       0x0100,                    // 文件中实际有数据的部分
       PROT_READ | PROT_WRITE,
       MAP_PRIVATE | MAP_FIXED,
       fd,
       0x1000)

  // 再映射 BSS 部分（p_memsz - p_filesz = 0x0800 - 0x0100 = 0x0700）
  mmap(load_base + 0x2100,
       0x0700,                    // BSS 大小
       PROT_READ | PROT_WRITE,
       MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED,
       -1,                        // 无文件
       0)

  → BSS 是纯内存，不对应文件任何内容，内容全为零
  → 这就是"未初始化的全局变量"在运行时所占的内存
```

#### 为什么初始设为 PROT_WRITE？

所有段初始都设为 **PROT_READ | PROT_WRITE**，包括代码段。

原因：接下来的重定位步骤需要修改 GOT 中的条目。而 GOT 位于代码段（RX PT_LOAD）的末尾或数据段中。如果代码段是 PROT_READ | PROT_EXEC，就无法写入 GOT。

**后续会改回正确的权限**——见第四章。

#### MAP_PRIVATE 的意义

`MAP_PRIVATE` 意味着"写时复制 (Copy-On-Write)"：

- 多个进程加载同一个 libfoo.so 时，共享同一份物理页（节省内存）
- 当某个进程因重定位而修改了 GOT 中的某个条目时，内核才为该页分配一个私有副本
- 这就是为什么 .so 的代码段（.text）在所有进程中内容相同，但 GOT 内容各进程不同

---

## 第二章：依赖库的递归加载

### 2.1 读取 DT_NEEDED

映射完成后，`_dl_map_object_deps()` 读取 `.dynamic` section：

```
.dynamic section 中每个条目格式：
  { d_tag: DT_NEEDED, d_val: offset_in_dynstr }
  → d_val 是 .dynstr 中的偏移，指向字符串如 "libc.so.6"

遍历所有 DT_NEEDED 条目，得到依赖列表：
  libfoo.so 依赖于：
    libc.so.6
    libbar.so.1
```

### 2.2 递归加载

对每个依赖库名字，执行与第一章相同的流程（mmap），但：

- 如果该库已经在进程的 link_map 链表中 → **不重新映射**，只增加引用计数
- 递归处理依赖库自身也有 DT_NEEDED 的情况（如 libbar.so 可能还依赖 libc.so）

### 2.3 构建依赖图

最终形成一棵依赖树，用 `link_map.l_initfini` 数组记录拓扑排序结果，确保初始化顺序正确。

---

## 第三章：重定位——修改内存中的数据

这是 dlopen 中最复杂的步骤，也是真正"改内存"的核心环节。

### 3.1 重定位的本质

一个 .so 在编译时不知道自己会被加载到哪个地址（`load_base` 是运行时才确定的）。因此：

- 代码中引用本库内部符号时，用的是相对偏移（R_X86_64_PC32 等），运行时自动修正——不需要重定位
- 代码中引用外部符号（其他库的函数/变量）时，用的是 GOT 间接引用——需要在 GOT 中写入真实地址
- 代码中引用绝对地址时（如全局指针指向本库内部），需要加上 load_base——这就是 RELATIVE 重定位

### 3.2 两类重定位表

```
.rela.dyn  →  数据段的重定位（必须立即处理）
.rela.plt  →  PLT 的重定位（可以延迟处理，即 lazy binding）
```

`RTLD_NOW` 模式下两类都立即处理；`RTLD_LAZY` 模式下 `.rela.plt` 在函数首次调用时才处理。

### 3.3 重定位条目的格式

```
struct Elf64_Rela {
    Elf64_Addr  r_offset;    // 需要修改的内存位置的偏移（相对于 load_base）
    Elf64_Xword r_info;      // 高32位=符号索引，低32位=重定位类型
    Elf64_Sxword r_addend;   // 附加值
};
```

例如：
```
r_offset = 0x2050    → 要修改 load_base + 0x2050 处的内存
r_info   = 0x000001  → 类型 R_X86_64_64，符号索引 1
r_addend = 0x0       → 附加值
```

### 3.4 各重定位类型的内存修改动作

#### 类型一：R_X86_64_RELATIVE（基址修正）

**最常见、最简单**。含义："这个位置存放的是一个绝对地址，但它指向的是本库内部，需要加上 load_base。"

```
内存修改动作：
  addr = load_base + r_offset
  *addr = *addr + load_base + r_addend

示例：
  .so 文件中 .data 段有一个全局指针变量 static_ptr，
  编译时 static_ptr 的值 = 0x1000（指向本库 .text 内某个位置）
  文件中记录：r_offset = static_ptr 的位置，r_addend = 0x1000

  运行时 load_base = 0x7f000000
  → 修改：*(load_base + r_offset) = 0x7f000000 + 0x1000 = 0x7f001000

  写入的是数据段（RW PT_LOAD）中的某个 8 字节位置
```

#### 类型二：R_X86_64_GLOB_DAT（全局符号立即绑定）

**写入 GOT**。含义："GOT 中第 N 个条目，请填入符号 `foo` 的真实地址。"

```
内存修改动作：
  addr = load_base + r_offset      // GOT 中某个条目的位置
  sym = lookup_symbol(r_info)      // 在所有已加载库中查找符号 "foo"
  *addr = sym.st_value + r_addend  // 将符号的真实地址写入 GOT

示例：
  libfoo.so 的代码中调用了 printf
  编译时：代码生成 call *GOT[printf_slot]
  GOT[printf_slot] 此时内容未知

  运行时：lookup_symbol("printf") → 在 libc.so 中找到 printf 地址 = 0x7f800100
  → 修改：*(load_base + GOT_printf_offset) = 0x7f800100

  写入的是 GOT（位于 RW PT_LOAD 或 RX PT_LOAD 末尾）
```

#### 类型三：R_X86_64_JUMP_SLOT（PLT 延迟绑定）

**也写入 GOT**，但对应 `.rela.plt` 表。与 GLOB_DAT 类似，区别在于：

```
RTLD_NOW 模式：
  与 GLOB_DAT 完全相同——立即查找符号，写入 GOT

RTLD_LAZY 模式：
  不立即查找。GOT.plt 中写入 PLT 跳转桩的地址
  首次调用时，跳转桩触发 _dl_runtime_resolve()
  _dl_runtime_resolve() 才真正查找符号并写入 GOT.plt
  之后再调用就直接跳到真实地址，不再经过桩
```

#### 类型四：R_X86_64_COPY（变量复制）

**特殊：从主程序复制变量定义到新库**。只出现在主程序是 ET_EXEC（固定地址）的场景。

```
场景：
  主程序 a.out 中定义了：int errno = 0;
  libfoo.so 中也引用了 extern int errno;
  但 .so 不知道 errno 在主程序中的地址

内存修改动作：
  src  = main_program_load_base + sym.st_value    // 主程序中 errno 的地址
  dst  = libfoo_load_base + r_offset               // libfoo .bss 中为 errno 分配的位置
  memcpy(dst, src, sizeof(int))                     // 复制值

  → 之后 libfoo 中对 errno 的引用指向自己的副本（而非主程序的原变量）
  → 这就是为什么同一个全局变量在不同库中可能有不同副本（COPY 重定位的副作用）
```

#### 类型五：其他常见类型

| 类型              | 内存动作                                          | 说明                |
| --------------- | --------------------------------------------- | ----------------- |
| `R_X86_64_64`   | `*addr = sym_value + addend`                  | 64 位绝对符号引用        |
| `R_X86_64_32`   | `*(uint32_t*)addr = sym_value + addend`       | 32 位符号引用（截断）      |
| `R_X86_64_32S`  | `*(int32_t*)addr = sym_value + addend`        | 32 位符号引用（有符号截断）   |
| `R_X86_64_PC32` | `*(int32_t*)addr = sym_value + addend - addr` | PC 相对引用（通常不需 GOT） |

### 3.5 符号查找的搜索顺序

当重定位需要查找一个符号（如 `printf`）时，搜索范围取决于加载模式：

```
RTLD_GLOBAL 模式（dlopen 的默认）：
  搜索顺序：
    1. 被加载的库 (libfoo.so) 自身的 .dynsym
    2. libfoo.so 的依赖链（按依赖图的拓扑序）
    3. 全局加载链中所有 RTLD_GLOBAL 库（libc.so 等）
    4. 主程序 a.out

RTLD_LOCAL 模式：
  被加载的库的符号不对外可见
  但查找依赖时仍然走上述顺序
```

符号的可见性（`STV_DEFAULT` / `STV_HIDDEN` / `STV_PROTECTED`）也影响查找结果。

---

## 第四章：内存权限收紧

### 4.1 代码段恢复为不可写

重定位完成后，代码段不再需要被写入。`_dl_protect_relro()` 和后续的 mprotect 恢复权限：

```
对 PT_LOAD[0]（代码段）：

  初始：PROT_READ | PROT_WRITE    ← 重定位时需要写 GOT
  恢复：PROT_READ | PROT_EXEC     ← 重定位完成后改回

  mprotect(load_base + 0x0000, 0x1000, PROT_READ | PROT_EXEC)

  → 之后任何对代码段的写操作都会触发 SIGSEGV
  → 代码段中的 GOT 条目被固化，不可再改（除非在 .got.plt 中）
```

### 4.2 RELRO 机制（PT_GNU_RELRO）

RELRO 是一种安全加固机制，将不需要运行时修改的 GOT 条目改为只读：

```
PT_GNU_RELRO 描述了一段地址区间：
  relro_start = load_base + PT_GNU_RELRO.p_vaddr
  relro_end   = relro_start + PT_GNU_RELRO.p_memsz

这段区间包含：
  .got（非 .got.plt 部分）    ← GLOB_DAT 重定位写入的条目，之后不会再改
  .data 中的部分 const 变量    ← 初始化完成后不应被改
  .dynamic section             ← 加载完成后不再需要被改

操作：
  mprotect(relro_start, relro_end - relro_start, PROT_READ)

  → 这些区域变成只读，任何运行时篡改都会 SIGSEGV
  → 这是防御 GOT overwrite 攻击的关键机制
```

### 4.3 .got.plt 保持可写

`.got.plt`（延迟绑定用的 GOT 子表）**不被 RELRO 保护**，始终保持 PROT_READ | PROT_WRITE。

原因：lazy binding 模式下，`_dl_runtime_resolve()` 需要在函数首次调用时写入 `.got.plt` 中的条目。

这也意味着 `.got.plt` 是攻击者最常利用的篡改目标。启用 `FULL RELRO`（`-Wl,-z,relro,-z,now`）时，`.rela.plt` 也立即处理，`.got.plt` 被纳入 RELRO 区，变为只读——但代价是放弃 lazy binding。

### 4.4 权限变更总结

```
时间段          代码段(RX PT_LOAD)     数据段(RW PT_LOAD)
─────────────── ──────────────────── ────────────────────
mmap 初始       PROT_READ|PROT_WRITE  PROT_READ|PROT_WRITE
重定位进行中    可写（修改 GOT）       可写（修改 GOT/data/指针）
重定位完成后    mprotect → RX          RELRO 区 → PROT_READ
                                      其余保持 PROT_READ|PROT_WRITE
```

---

## 第五章：TLS（线程局部存储）内存

### 5.0 为什么要先理解 TLS

TLS 是 dlopen 中**最容易让人困惑的部分**，因为它涉及"每个线程都要分配独立内存"这个特殊性。理解 TLS 的关键是搞清三个问题：

1. **为什么每个线程需要独立副本？** → 因为 `__thread` 变量的语义就是"每个线程各一份"
2. **为什么 dlopen 加载新库时很贵？** → 因为已有线程的 TLS block 要扩展
3. **扩展到底在内存中做了什么？** → realloc + memcpy，每个线程都要做一遍

下面从最基础的概念开始，逐步展开。

---

### 5.1 什么是 `__thread` 变量

```c
// libfoo.c
__thread int thread_counter = 0;    // 每个线程有自己的 thread_counter
__thread char thread_name[32] = "unknown";
```

含义：

- 线程 A 看到 `thread_counter = 0`，线程 B 也看到 `thread_counter = 0`
- 但它们是**不同的内存位置**，互不影响
- 线程 A 修改 `thread_counter = 5`，线程 B 的 `thread_counter` 仍然是 0
- 线程退出时，它的副本被销毁

**对比普通全局变量**：

```c
int global_counter = 0;      // 所有线程共享同一个内存位置
__thread int thread_counter = 0;  // 每个线程各有一份
```

---

### 5.2 编译时：PT_TLS 的生成

编译器遇到 `__thread` 变量时，做了两件事：

**第一：把 `__thread` 变量打包成 PT_TLS segment**

```
libfoo.so 的 ELF 文件中新增：

PT_TLS Program Header:
  p_offset = 0x3000    ← init image 在文件中的偏移
  p_vaddr  = 0x3000    ← init image 在虚拟地址中的偏移
  p_filesz = 36        ← init image 的字节数（thread_counter=4 + thread_name=32）
  p_memsz  = 40        ← TLS 总大小（含对齐填充）
  p_align  = 4         ← 对齐要求

init image 的内容（文件中 36 字节）：
  offset 0:  00 00 00 00                ← thread_counter 的初始值 = 0
  offset 4:  "unknown" + 24字节零填充    ← thread_name 的初始值

为什么 p_memsz > p_filesz？
  p_filesz = 有初始值的部分（36字节）
  p_memsz  = 总大小含对齐（40字节，多了4字节对齐填充）
  多出来的4字节运行时零填充（类似 BSS）
```

**第二：代码中对 `__thread` 变量的访问改为 TLS 间接引用**

```
编译前（想象中的"直接访问"）：
  thread_counter = 5;
  → mov [0x3000], 5          ← 这是错的！0x3000 是 init image，不是线程的私有副本

编译后（实际生成的代码）：
  thread_counter = 5;
  → mov fs:[offset_of_thread_counter], 5

  其中：
  fs 寄存器 → 指向当前线程的 TLS block 起始地址
  offset_of_thread_counter → thread_counter 在 TLS block 中的偏移（编译时确定）

  即：真正写入的是"当前线程 TLS block 中偏移 offset 处的位置"
  每个线程的 TLS block 不同，所以写入的物理内存位置也不同
```

**关键理解**：

- `__thread` 变量在 ELF 文件中只存储一份**初始值**（init image）
- 运行时，每个线程各自从 init image 拷贝一份，放在自己的 TLS block 中
- 代码通过 `fs寄存器 + 偏移` 来访问当前线程的私有副本
- fs 寄存器是内核在创建线程时设置的，每个线程的 fs 值不同

---

### 5.3 运行时：TLS 的两种模型

glibc 支持两种 TLS 实现模型，理解它们对理解 dlopen 很重要：

#### 模型一：TLS Variant I（x86_64 使用的模型）

```
TLS block 位于线程栈的下方（高地址方向）：

  线程栈布局（x86_64）：

  高地址 ┌─────────────────────────────────┐
         │ TLS block                       │ ← fs 寄存器指向这里
         │ ┌─────────────────────────────┐ │
         │ │ 库1的 TLS 区域 (libc)       │ │ ← 偏移 0（离 fs 最近）
         │ │ 库2的 TLS 区域 (libbar)     │ │ ← 偏移 = 库1区域大小
         │ │ 库3的 TLS 区域 (libfoo)     │ │ ← 偏移 = 库1+库2区域大小
         │ │ ...                          │ │
         │ └─────────────────────────────┘ │
         ├─────────────────────────────────┤
         │ dtv 数组                        │ ← 动态线程向量
         │ dtv[0] = generation 计数器       │
         │ dtv[1] → libc TLS 区域指针       │
         │ dtv[2] → libbar TLS 区域指针     │
         │ dtv[3] → libfoo TLS 区域指针     │ ← dlopen 后新增
         ├─────────────────────────────────┤
         │ 线程栈（向下增长）               │ ← 正常的栈空间
         │ ...                             │
  低地址 └─────────────────────────────────┘

  访问 thread_counter 的汇编：
    mov fs:[thread_counter_offset], 5

  其中 thread_counter_offset 是负数（从 fs 向低地址偏移）
  或者编译器使用正偏移（从 TLS block 起始处算）
  具体取决于 ABI 规范
```

#### 模型二：TLS Variant II（少用，某些架构使用）

```
TLS block 位于线程栈的上方（低地址方向）：
  与 Variant I 类似，但布局方向相反
  glibc 在 x86_64 上只用 Variant I，所以这里不详述
```

---

### 5.4 dtv（Dynamic Thread Vector）详解

dtv 是每个线程持有的一个**指针数组**，用来定位各库的 TLS 区域。

```
dtv 的结构：

  dtv[0] = generation 计数器    ← 每次 dlopen 有 PT_TLS 的库时 generation++
                                    用于检测 dtv 是否需要更新

  dtv[1] → libc.so 的 TLS 区域指针
  dtv[2] → libbar.so 的 TLS 区域指针
  dtv[3] → libfoo.so 的 TLS 区域指针    ← dlopen libfoo.so 后新增

  每个指针指向的是"该线程中该库的 __thread 变量的私有副本区域"

  dtv 本身是一块动态分配的内存（malloc 或类似机制）
  位于 TLS block 旁边（具体位置取决于实现）
```

**为什么需要 dtv**：

- TLS block 中的各库 TLS 区域是**连续排列**的（紧凑布局，节省内存）
- 但 dlopen 新库时，新库的 TLS 区域要追加到末尾 → TLS block 要扩展
- dtv 提供一个间接层：代码通过 `dtv[module_id] → TLS区域 → 变量偏移` 来定位
- 这样即使 TLS block 被扩展/重分配，只要更新 dtv 指针，代码不需要改

---

### 5.5 程序启动时的 TLS 初始化（作为对照）

理解"正常启动时"的 TLS 处理，才能理解 dlopen 时为什么不同。

```
程序启动（exec + ld.so 加载所有依赖库）：

  1. ld.so 读取所有库的 PT_TLS
  2. 计算总 TLS 大小：
     total_tls_size = sum(各库 PT_TLS.p_memsz) + 对齐填充

  3. 主线程创建时（或首次线程创建前）：
     分配一块连续内存作为 TLS block
     大小 = total_tls_size

     按顺序将各库的 init image 拷贝到 TLS block 的对应位置：
     for each library (按加载顺序):
       memcpy(tls_block + offset, init_image, p_filesz)
       memset(tls_block + offset + p_filesz, 0, p_memsz - p_filesz)  ← BSS部分零填充

  4. 设置 dtv：
     dtv[0] = generation = 2  （假设加载了2个有 TLS 的库）
     dtv[1] → libc TLS 区域地址
     dtv[2] → libbar TLS 区域地址

  5. 设置 fs 寄存器 → 指向 TLS block 起始

  关键点：启动时所有库的 TLS 是**一次性分配**的
  TLS block 大小已经包含所有库的需求，之后不需要扩展
```

```
新线程创建时（pthread_create → clone）：

  1. 分配新的 TLS block（大小 = total_tls_size）
  2. 拷贝所有库的 init image 到对应位置
  3. 分配新的 dtv，设置各指针
  4. 设置新线程的 fs 寄存器 → 指向新 TLS block

  → 每个线程的 TLS block 是独立的，互不干扰
  → init image 中的初始值被拷贝到每个线程
```

---

### 5.6 dlopen 时的 TLS 处理（核心难点）

现在，假设程序已经启动，有 3 个线程在运行，此时 dlopen("libfoo.so")。

libfoo.so 有 PT_TLS（包含 `__thread int thread_counter = 0`）。

#### 问题：新库的 TLS 区域怎么放进已有线程的 TLS block？

```
已有线程的 TLS block（dlopen 前）：

  ┌────────────────────────────────┐
  │ libc TLS 区域  (大小 A)        │ ← 偏移 0，位置固定，不能移动
  │ libbar TLS 区域 (大小 B)       │ ← 偏移 A，位置固定，不能移动
  │                                │ ← TLS block 到此为止，大小 = A + B
  └────────────────────────────────┘

  问题：libfoo 的 TLS 区域要放在哪？

  答案：追加到末尾

  ┌────────────────────────────────┐
  │ libc TLS 区域  (大小 A)        │ ← 偏移 0，不变
  │ libbar TLS 区域 (大小 B)       │ ← 偏移 A，不变
  │ libfoo TLS 区域 (大小 C)       │ ← 偏移 A+B，新增 ← dlopen 追加
  │                                │ ← TLS block 总大小变为 A + B + C
  └────────────────────────────────┘
```

#### 为什么不能插到中间或重新排列？

```
因为代码中访问 __thread 变量使用的是"编译时确定的偏移"：

  libc 中的代码访问 errno：
    mov fs:[libc_errno_offset], eax

  libc_errno_offset 是编译时写入代码中的常量
  如果 libc 的 TLS 区域被移动了（偏移变了），这条指令就访问到错误的位置

  所以：
  → 已有库的 TLS 区域位置绝对不能改变
  → 新库只能追加到末尾
  → 这就是 dlopen TLS 处理的根本约束
```

#### dlopen TLS 处理的完整步骤

```
步骤1：记录新库的 TLS 信息到全局 slotinfo 数组

  全局维护一个 slotinfo[] 数组（所有库的 TLS 元数据）：
  slotinfo[0] = libc   { tls_offset, tls_block_size, init_image_ptr }
  slotinfo[1] = libbar { tls_offset, tls_block_size, init_image_ptr }
  slotinfo[2] = libfoo { tls_offset = A+B, tls_block_size = C, init_image_ptr }
                  ↑ 新增，offset 追加到已有总大小之后

  全局 generation 计数器 ++（从 2 变为 3）
  这个 generation 值会写入每个线程的 dtv[0]

步骤2：扩展所有已有线程的 TLS block

  遍历所有已存在的线程（线程1、线程2、线程3）：
  对每个线程执行：

  2a. 扩展 TLS block 的内存：
      旧 TLS block 大小 = A + B
      新 TLS block 大小 = A + B + C

      方式1（glibc 默认）：在 TLS block 后面直接 mmap 新区域
        → 如果后面的虚拟地址空间有空位，直接追加
        → 不需要拷贝旧数据，新区域与旧区域逻辑上连续

      方式2（fallback）：malloc 新 TLS block + memcpy 旧数据
        → 如果后面没有空位，分配一块全新的内存
        → 把旧的 libc + libbar TLS 区域拷贝过去
        → fs 寄存器更新为新 TLS block 地址
        → 旧 TLS block 释放

      ⚠️ 无论哪种方式，libc 和 libbar 的 TLS 区域内容保持不变
         它们的偏移也不变，只是 TLS block 变大了

  2b. 拷贝新库的 init image 到扩展区域：
      memcpy(tls_block + A + B, libfoo_init_image, p_filesz)
      → 将 thread_counter 的初始值(0)和 thread_name 的初始值("unknown")写入
      memset(tls_block + A + B + p_filesz, 0, p_memsz - p_filesz)
      → 对齐填充部分零初始化

  2c. 更新该线程的 dtv：
      旧 dtv 大小 = 3（generation + 2个库指针）
      新 dtv 大小 = 4（generation + 3个库指针）

      realloc(dtv, new_size)
      dtv[0] = 3                   ← 新的 generation
      dtv[1] → libc TLS 区域       ← 不变
      dtv[2] → libbar TLS 区域     ← 不变
      dtv[3] → libfoo TLS 区域     ← 新增，指向 tls_block + A + B

步骤3：对之后创建的新线程

  pthread_create 时，自动分配完整的 TLS block（大小 = A + B + C）
  拷贝所有库的 init image 到对应位置
  设置 dtv（generation = 3，包含所有 3 个库的指针）
  设置 fs 寄存器
  → 新线程天生就有 libfoo 的 TLS 变量，不需要额外处理
```

---

### 5.7 为什么 dlopen TLS 很贵

```
假设场景：程序有 100 个线程在运行，此时 dlopen 一个有 PT_TLS 的库

  → 需要遍历 100 个线程
  → 每个线程都要：扩展 TLS block + memcpy init image + realloc dtv
  → 100 次 realloc，100 次 memcpy
  → 如果 TLS block 后面没有空位（地址空间碎片化），还要 100 次 malloc + 100 次 memcpy旧数据

  对比程序启动时：
  → 只需要分配一次 TLS block（包含所有库的需求）
  → 新线程创建时也只分配一次
  → 不需要扩展操作

  这就是为什么 glibc 文档建议：
  "如果库有 __thread 变量，尽量在程序启动时加载（LD_PRELOAD），不要 dlopen"
```

---

### 5.8 dlopen TLS 的一个陷阱：generation 不一致

```
场景：线程1 正在执行，此时线程2 dlopen 了 libfoo.so

  dlopen 修改了全局 slotinfo 数组和 generation
  线程2 的 dtv 已更新（generation = 3）

  但线程1 的 dtv 还是旧的（generation = 2）
  线程1 的 TLS block 也还没扩展

  如果线程1 此时访问 libfoo 的 __thread 变量：
    → 代码通过 dtv[3] 查找 → dtv 只有2个条目，dtv[3] 不存在！
    → 或者 dtv[3] 指向过期的地址

  glibc 的处理方式：
    在每次访问 __thread 变量时，先检查 dtv[0]（generation）
    如果 dtv[0] < 全局 generation → 说明 dtv 过期了
    → 调用 __tls_get_addr() 进行"延迟更新"（lazy TLS update）
    → __tls_get_addr() 扩展该线程的 TLS block + 更新 dtv

  这意味着：
    dlopen 不一定立即扩展所有线程的 TLS block
    有些线程可能延迟到首次访问新库的 __thread 变量时才扩展
    这叫做 "lazy TLS allocation"（glibc 默认行为）

    但即使如此，全局 slotinfo 数组必须立即更新（因为要记录偏移）
    否则新线程创建时无法分配正确的 TLS block
```

---

### 5.9 dlclose 时 TLS 的处理

```
dlclose libfoo.so 时：

  1. 全局 slotinfo[2] 标记为"已释放"
     但不删除条目，也不调整其他库的偏移（偏移不能变！）

  2. generation 不变（不回退）
     → 因为偏移已经分配过了，即使库卸载了，偏移位置仍然"占着"

  3. 各线程的 dtv[3] → 标记为 NULL 或指向一个"已卸载"标记
     → 之后再访问这个模块的 __thread 变量会返回 NULL 或触发错误

  4. 各线程的 TLS block 不缩小
     → libfoo 的 TLS 区域仍然占着空间，只是不再被使用
     → 这是 dlopen/dlclose 反复调用时的**已知内存泄漏源**

  关键理解：
    TLS 偏移一旦分配就不会回收
    即使 dlclose 了库，TLS block 中该库的区域仍然存在（只是不用了）
    这和 munmap 释放代码/数据段不同——代码段可以完全回收，TLS 不行
```

---

### 5.10 TLS 内存动作总结表

| 动作 | 操作方式 | 触发时机 | 对象 | 可否撤销 |
|------|----------|----------|------|----------|
| init image 存储在文件中 | ELF PT_TLS segment | 编译时 | .so 文件 | N/A |
| init image 映射到内存 | mmap（随 PT_LOAD） | dlopen 阶段1 | 进程地址空间 | dlclose munmap |
| 全局 slotinfo 注册 | 数组追加 | dlopen 阶段5 | ld.so 全局数据 | 标记释放但不删除 |
| generation ++ | 计数器增加 | dlopen 阶段5 | 全局计数器 | 不回退 |
| TLS block 扩展 | mmap追加 或 malloc+memcpy | dlopen 阶段5 或 lazy TLS | 各线程栈附近 | 不缩小 |
| init image 拷贝到各线程 | memcpy | dlopen 阶段5 或 lazy TLS | 各线程 TLS block | 不可撤销 |
| dtv 扩展 | realloc | dlopen 阶段5 或 lazy TLS | 各线程 dtv 数组 | 标记NULL但不缩小 |
| fs 寄存器更新 | 内核 arch_prctl | TLS block 重分配时 | 当前线程 | 仅重分配时更新 |

---

### 5.11 源码定位

| 功能 | glibc 源文件 | 关键函数 |
|------|-------------|---------|
| 全局 slotinfo 管理 | `elf/dl-tls.c` | `_dl_add_to_slotinfo()` |
| TLS 布局计算 | `elf/dl-tls.c` | `_dl_determine_tlsoffset()` |
| 已有线程 TLS 扩展 | `elf/dl-tls.c` | `_dl_update_slotinfo()` |
| 延迟 TLS 分配 | `elf/dl-tls.c` | `__tls_get_addr()` |
| 新线程 TLS 初始化 | `nptl/ptl_create.c` → `__pthread_create_2_1()` | 调用 `_dl_allocate_tls_storage()` |
| dtv 管理 | `elf/dl-tls.c` | `_dl_allocate_dtv()` / `_dl_resize_dtv()` |

---

## 第六章：构造函数执行

### 6.1 初始化函数的来源

`.dynamic` section 中可能包含：

```
DT_INIT        → 指向老式 .init 函数（如 void _init()）
DT_INIT_ARRAY  → 指向 __attribute__((constructor)) 函数数组
DT_INIT_ARRAYSZ → 数组大小
```

### 6.2 执行顺序

```
按依赖图的拓扑逆序（叶→根）执行各库的初始化：

  1. libc.so 的 init / init_array    （最深依赖，最先初始化）
  2. libbar.so 的 init / init_array
  3. libfoo.so 的 init / init_array  （最后初始化）

  对每个库：
    先调用 DT_INIT（如果存在）
    再按索引顺序遍历 DT_INIT_ARRAY 中的每个函数指针
```

### 6.3 内存角度

初始化函数本身不做特殊的内存映射操作，但它们可能：

- 调用 malloc 分配内存（堆上的数据结构）
- 调用其他 dlopen（递归加载更多库）
- 修改全局变量（写 .data / .bss）

---

## 第七章：link_map 元数据

### 7.1 分配

```
struct link_map *l = calloc(1, sizeof(struct link_map));
// 在 ld.so 自身的内存区域中分配（不是用户 malloc 的堆）
```

### 7.2 关键字段

```c
struct link_map {
    Elf64_Addr l_addr;        // load_base ——库被加载到的基地址
    char      *l_name;        // 库的文件路径字符串
    Elf64_Dyn *l_ld;          // .dynamic section 在内存中的指针
    struct link_map *l_next;  // 链表下一个
    struct link_map *l_prev;  // 链表上一个

    // 符号查找相关
    Elf64_Sym  *l_symtab;     // .dynsym 在内存中的指针
    char       *l_strtab;     // .dynstr 在内存中的指针
    Elf64_Hash *l_hash;       // 符号 hash 表（加速查找）

    // 依赖相关
    struct link_map **l_initfini; // 拓扑排序后的依赖列表

    // TLS 相关
    size_t l_tls_blocksize;   // TLS 区域大小
    void  *l_tls_initimage;   // TLS init image 在内存中的指针

    // ... 更多字段
};
```

### 7.3 加入全局链表

```
_dl_loaded 链表（所有已加载库）：
  a.out → libc.so → libm.so → ... → libfoo.so (新加入)

新 link_map 被插入链表尾部（或根据依赖顺序）
```

---

## 第八章：完整流程串联

### 8.1 时序图

```
时间 ──────────────────────────────────────────────────────────→

阶段1: 文件映射
  │ open fd
  │ mmap PT_LOAD[0] (代码段, PROT_R|PROT_W, MAP_PRIVATE)
  │ mmap PT_LOAD[1] (数据段, PROT_R|PROT_W, MAP_PRIVATE)
  │ mmap BSS        (PROT_R|PROT_W, MAP_ANONYMOUS)
  │ 分配 link_map

阶段2: 依赖加载
  │ 读取 DT_NEEDED
  │ 对 libc.so: 已加载 → refcount++
  │ 对 libbar.so: 未加载 → 递归执行阶段1
  │ 构建依赖拓扑

阶段3: 重定位（写内存）
  │ 处理 .rela.dyn：
  │   RELATIVE → *addr += load_base          （写 .data/.got）
  │   GLOB_DAT → *addr = sym_value           （写 .got）
  │   COPY     → memcpy(dst, src, size)       （写 .bss）
  │ 处理 .rela.plt：
  │   JUMP_SLOT → *addr = sym_value           （写 .got.plt）
  │              或 *addr = PLT stub (lazy)

阶段4: 权限收紧
  │ mprotect(代码段, PROT_READ|PROT_EXEC)
  │ mprotect(RELRO区, PROT_READ)
  │ .got.plt 保持 PROT_READ|PROT_WRITE

阶段5: TLS 扩展
  │ 分配新 TLS 区域大小
  │ 遍历所有线程 → 扩展 TLS block + 更新 dtv
  │ 拷贝 init image 到各线程 TLS

阶段6: 初始化执行
  │ 拓扑逆序调用 DT_INIT / DT_INIT_ARRAY
  │ 各构造函数可能分配堆内存、修改全局变量

阶段7: 返回
  │ 返回 link_map handle 给调用者
```

### 8.2 内存动作汇总表

| 动作 | 操作方式 | 目标内存区域 | 时机 | 可否撤销 |
|------|----------|-------------|------|----------|
| 映射代码段 | mmap(MAP_PRIVATE, fd) | 新虚拟地址区间 | 阶段1 | dlclose 时 munmap |
| 映射数据段 | mmap(MAP_PRIVATE, fd) | 新虚拟地址区间 | 阶段1 | dlclose 时 munmap |
| 映射 BSS | mmap(MAP_ANONYMOUS) | 新虚拟地址区间 | 阶段1 | dlclose 时 munmap |
| RELATIVE 重定位写 | *(addr) = value | .data / .got | 阶段3 | 不可撤销（写入私有页） |
| GLOB_DAT GOT 写 | *(addr) = sym_addr | .got | 阶段3 | 不可撤销 |
| JUMP_SLOT GOT 写 | *(addr) = sym/PLT | .got.plt | 阶段3 | lazy 模式下后续改 |
| COPY 复制 | memcpy(dst, src) | .bss | 阶段3 | 不可撤销 |
| 代码段权限恢复 | mprotect → RX | PT_LOAD[0] | 阶段4 | dlclose 时整段释放 |
| RELRO 只读化 | mprotect → R | RELRO 区 | 阶段4 | 不可撤销 |
| TLS block 扩展 | realloc + memcpy | 各线程栈附近 | 阶段5 | dlclose 时缩小 dtv |
| init image 拷贝 | memcpy | TLS block | 阶段5 | 不可撤销 |
| link_map 分配 | calloc | ld.so 堆 | 阶段1 | dlclose 时 free |
| 堆分配(构造函数) | malloc | 用户堆 | 阶段6 | 需手动 free |

---

## 第九章：dlclose 时的内存动作（反向参考）

dlclose 基本是 dlopen 的逆过程，但有差异：

```
1. 引用计数 --
   如果 refcount > 0 → 不卸载，只减计数

2. 调用 DT_FINI / DT_FINI_ARRAY（析构函数）
   → 析构函数应 free 自己分配的堆内存

3. munmap 各 PT_LOAD 段
   → 释放虚拟地址区间
   → COW 的私有页被丢弃，共享物理页不变

4. 减少 TLS 区域大小
   → 更新全局 TLS 布局
   → 各线程的 dtv 中对应条目标记为无效
   → 但不缩小各线程的 TLS block（空间浪费）

5. 从 link_map 链表中移除
   → free(link_map)
```

**注意**：dlclose 不保证内存立即回收。munmap 释放虚拟地址，但物理页的回收由内核决定。TLS block 的空间不会缩小——这是 dlopen/dlclose 反复调用时的已知内存泄漏源。

---

## 附录：源码定位

| 功能 | glibc 源文件 | 关键函数 |
|------|-------------|---------|
| dlopen 入口 | `elf/dl-open.c` | `_dl_open()` |
| 文件映射 | `elf/dl-load.c` | `_dl_map_object_from_fd()` |
| 依赖解析 | `elf/dl-deps.c` | `_dl_map_object_deps()` |
| 重定位 | `elf/dl-reloc.c` | `_dl_relocate_object()` |
| 符号查找 | `elf/dl-lookup.c` | `_dl_lookup_symbol_x()` |
| 权限收紧 | `elf/dl-protect-relro.c` | `_dl_protect_relro()` |
| TLS 处理 | `elf/dl-tls.c` | `_dl_add_to_slotinfo()` |
| 初始化执行 | `elf/dl-init.c` | `_dl_init()` |
| link_map 管理 | `elf/dl-object.c` | `_dl_new_object()` |