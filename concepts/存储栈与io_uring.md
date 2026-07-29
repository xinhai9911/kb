---
title: 存储栈与 io_uring
category: concepts
tags: [storage, block-layer, nvme, iouring, spdk, kernel, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    Linux 存储栈与 io_uring 高性能 I/O。Block 层（bio/request/plugging/
    scheduler/mq-deadline/kyber）、NVMe 驱动与队列模型（Admin/SQ/CQ）、
    io_uring 提交队列（SQ）+ 完成队列（CQ）环、sqpoll/kernel 模式、
    fixed-buf/splice 零拷贝、IORING_REGISTER_FILES 预注册 fd、
    SPDK 用户态 NVMe 驱动（与 DPDK 对称的设计）、
    数据面 NVMe over Fabrics 与 SPDK 集成。
    对照 DPDK 网络数据面的存储端对称技术。
base_confidence: 0.85
lifecycle: draft
---

# 存储栈与 io_uring

> 前置 [[concepts/PCIe 子系统]]（NVMe 是 PCIe EP），[[concepts/Linux 内存管理]]（DMA/bio 内存）。
> 本文视角：存储数据面（SPDK/io_uring）与网络数据面（DPDK/内核网络栈）的对称性。

## 1. Linux Block 层架构

```
用户态 (read/write/io_uring)
  │
  ├── VFS (虚拟文件系统)
  │     ↓
  ├── 文件系统 (ext4/xfs/btrfs)
  │     ↓ block mapping → IO 对齐 → fallocate
  │
  ├── Block Layer
  │     ├── bio (Block I/O) — 一个 I/O 请求的基本单位
  │     ├── request (多个 bio 合并)
  │     ├── I/O Scheduler (mq-deadline, kyber, none)
  │     ├── multi-queue (blk-mq) — 每个 CPU 队列
  │     └── SCSI/ATA 翻译层（NVMe 不走此层）
  │
  ├── NVMe 驱动（直接 blk-mq → NVMe SQ）
  │     ├── Admin Queue (控制命令）
  │     └── I/O Queues (ncpus 个，每个绑定一个核)
  │
  └── PCIe → NVMe SSD
```

### 1.1 bio 结构

```c
struct bio {
    sector_t        bi_sector;       // 起始扇区
    struct bio      *bi_next;        // 链表（合并）
    struct block_device *bi_bdev;    // 块设备
    blk_status_t    bi_status;       // 状态
    unsigned short  bi_vcnt;         // bi_io_vec 数量
    struct bio_vec  *bi_io_vec;      // 数据向量（page+offset+len）
    struct bio_vec  bi_inline_vecs[];// 内联 vector（0 长度）
    // ...
};
// bio_vec: { page, offset, len }
// 一个 bio 可含多个 bio_vec（分段 I/O）
// 请求合并：多个连续 bio 通过 bi_next 合并为一个 request
```

### 1.2 I/O Scheduler

```bash
# 查看当前调度器
cat /sys/block/nvme0n1/queue/scheduler

# NVMe 推荐 none（无调度器，直通 NVMe 硬件队列）
# SATA SSD 推荐 mq-deadline
# HDD 推荐 bfq

# none 模式：bio → request → NVMe SQ（最短路径）
# mq-deadline: 合并+重排请求（读写分离）
# kyber: 延迟感知调度

# 数据面全闪存场景 → none
echo none | sudo tee /sys/block/nvme0n1/queue/scheduler
```

## 2. NVMe 队列模型

```
NVMe Controller
├── Admin Queue (ACQ + ASQ)     # 管理命令（创建/删除 I/O 队列等）
└── I/O Queue Pairs × N
      ├── Submission Queue 0    # 提交命令（绑定 core 0）
      ├── Completion Queue 0   # 完成通知（绑定 core 0）
      ├── Submission Queue 1    # （绑定 core 1）
      ├── Completion Queue 1
      └── ...                   # 最大 64K 队列
```

```bash
# 查看 NVMe 队列数
nvme list
nvme id-ctrl /dev/nvme0 | grep -i "num queues\|ioqes"

# 查看 per-CPU 队列
ls /sys/block/nvme0n1/mq/
# 0/  1/  2/  ... → 每个 CPU 一个队列

# 调队列深度
cat /sys/block/nvme0n1/device/queue_depth

# NVMe 中断亲和
cat /proc/interrupts | grep nvme
# nvme0q0 → admin q
# nvme0q1 → I/O q core 1
# nvme0q2 → I/O q core 2
# ...
```

**原生 NVMe 延迟**：
```bash
# NVMe SSD 延迟分布（Intel P5800X Optane）
# 4KB 随机读: ~5μs (Q1)
# 4KB 随机写: ~8μs (Q1)
# PCIe Gen4 x4: ~7 GB/s
# PCIe Gen5 x4: ~14 GB/s

# 软件开销叠加：
# VFS + 文件系统: +1-2μs
# Block layer + I/O scheduler: +0.5-1μs
# NVMe 驱动: ~0.5μs
# 总软件开销 ~2-4μs (每 I/O)
```

## 3. io_uring

### 3.1 架构

```
                     应用
                      │
           ┌──────────┴──────────┐
           │  io_uring           │
           │  ┌─────────────┐    │
           │  │ Submission   │    │  ←  应用写入提交项（SQ tail）
           │  │ Queue (SQ)   │    │  ↓  内核消费（SQ head）
           │  ├─────────────┤    │
           │  │ Completion   │    │  ↑  内核写入 CQE（CQ tail）
           │  │ Queue (CQ)   │    │  →  应用消费（CQ head）
           │  └─────────────┘    │
           └──────────┬──────────┘
                      │ 系统调用：io_uring_enter / 轮询
                  ┌───▼───┐
                  │ Kernel │ → NVMe / block layer / socket
                  └───────┘
```

### 3.2 io_uring 模式

| 模式 | 说明 | 延迟节省 |
|------|------|---------|
| **中断模式** (default) | 提交后系统调用唤醒内核，完成时 IRQ 通知 | 无系统调用开销（1 syscall/batch） |
| **SQPOLL** | 内核线程轮询 SQ，无需 `io_uring_enter` | 0 syscall | 
| **IOPOLL** | 用户轮询 CQ，无需中断 | 0 syscall + 0 中断延迟 |
| **Fixed Buffer** | 预注册 buffer，消除内存映射 | +-0.5μs/buf |
| **Register Files** | 预注册 fd，消除文件描述符查找 | +-0.1μs/fd |

**延迟对比**：
```bash
# read() 系统调用全程
# syscall enter/exit: ~100ns
# VFS path lookup: ~200ns
# block → NVMe: ~1μs
# IRQ → 唤醒: ~2μs
# 合计: ~3.5μs + 设备延迟 5μs = ~8.5μs

# io_uring (中断模式)
# 系统调用: 0 (batch)
# VFS: ~200ns
# block → NVMe: ~1μs
# IRQ → 唤醒: ~2μs
# 合计: ~3.2μs + 5μs = ~8.2μs（省 0.3μs 主要是 syscall）

# io_uring (IOPOLL + SQPOLL + fixed_buf)
# syscall: 0
# VFS: ~200ns (可优化)
# block → NVMe: ~1μs
# 轮询 CQ: 0（类似 DPDK PMD）
# 合计: ~1.2μs + 5μs = ~6.2μs（省 2+ μs 中断延迟）

# == 结论 ==
# io_uring IOPOLL 对 NVMe 场景可省 ~30% 延迟
# 对比传统 syscall 模式
```

### 3.3 代码模式

```c
// io_uring 基本使用（liburing）
struct io_uring ring;
struct iovec *iovecs;
int fd;

// 初始化（固定 buffer + SQPOLL）
io_uring_queue_init(1024, &ring, IORING_SETUP_SQPOLL);
io_uring_register_buffers(&ring, iovecs, nr_vecs);
io_uring_register_files(&ring, &fd, 1);

// 提交
struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
io_uring_prep_readv(sqe, fd, &iovecs[0], 1, 0);
// 不调用 io_uring_enter（SQPOLL 线程自动消费）
// 只需写 tail 即完成提交

// 等待完成
struct io_uring_cqe *cqe;
io_uring_wait_cqe(&ring, &cqe);
io_uring_cqe_seen(&ring, cqe);
```

## 4. SPDK（Storage Performance Development Kit）

### 4.1 SPDK 与 DPDK 的对称性

| 层面 | DPDK（网络） | SPDK（存储） |
|------|------------|-------------|
| 驱动模型 | 用户态 PMD | 用户态 NVMe/ioat/virtio |
| 内存模型 | mempool + hugepages | spdk_malloc + hugepages |
| 队列模型 | RX/TX 描述符环 | NVMe SQ/CQ |
| 中断模式 | 轮询（PMD） | 轮询（NVMe poller） |
| I/O 抽象 | rte_ring | spdk_ring / spdk_poller |
| 驱动层级 | 绕过内核 TCP/IP | 绕过内核 VFS/Block |
| 典型实现 | l2fwd | hello_nvme / perf |

### 4.2 SPDK 架构

```
用户态
┌──────────────────────────────────────┐
│  SPDK app (spdk_nvme_perf / 自定义)   │
│  ┌────────────────────────────────┐   │
│  │ spdk_nvme_ns_cmd_read/write    │   │  ← 直接下发 NVMe cmd
│  ├────────────────────────────────┤   │
│  │ spdk_nvme_qpair  (SQ/CQ)       │   │  ← 队列对
│  ├────────────────────────────────┤   │
│  │ spdk_nvme_pcie  (PCIe BAR mmap) │   │  ← 用户态 PCIe 驱动
│  │ UIO/VFIO                        │   │
│  └────────────────────────────────┘   │
├──────────────────────────────────────┤
│ DPDK EAL (大页 + VFIO)                │
└──────────────────────────────────────┘
    ↓ hugepages + vfio-pci
NVMe SSD (PCIe Ep)
```

```bash
# SPDK 绑定 NVMe SSD
scripts/setup.sh                    # 解绑内核 nvme 驱动 → vfio-pci
scripts/gen_nvme.sh                 # NVMe 配置文件

# 跑 hello_nvme
examples/nvme/hello_nvme/hello_nvme

# SPDK 性能验证
sudo build/bin/spdk_nvme_perf -q 128 -s 4096 -w randread -t 30
# -q: 队列深度
# -s: I/O 大小
# -r: 随机读/写/混合
# 典型结果（NVMe Gen4 with SPDK）:
# 4KB random read: ~1.5M IOPS
# 延迟: ~5μs (设备) + ~1μs (SPDK 软件)
```

### 4.3 NVMe over Fabrics + SPDK

```bash
# SPDK NVMe-oF Target + Initiator
# 网络端用 DPDK，存储端用 SPDK

# Target (存储服务器):
sudo build/bin/nvmf_tgt
# 创建子系统
nvmf_create_subsystem nqn.2024-07.com.example:ns0 -a
nvmf_subsystem_add_listener nqn.2024-07.com.example:ns0 \
    -t rdma -a 192.168.1.1 -s 4420
nvmf_subsystem_add_ns nqn.2024-07.com.example:ns0 \
    /dev/nvme0n1

# Initiator (计算节点):
# SPDK initiator + DPDK RDMA
# 性能：接近本机 NVMe（延迟差 ~5μs RDMA 跨网络）
```

## 5. 数据面场景对比

```bash
# 网络数据面（DPDK/VPP）
# ════════════════════
# 包到达 → PMD 轮询 → 处理 → TX
# 延迟: ~500ns-5μs
# 吞吐: 20M pps / core

# 存储数据面（SPDK）
# ════════════════════
# IO 请求 → SPDK poller → NVMe cmd → 完成
# 延迟: ~5-15μs
# 吞吐: 1.5M IOPS / core (4KB)

# 混合场景（网+存交汇）：
# - NVMe over TCP (nvmf_tcp + DPDK)
# - NVMe over RDMA (nvmf_rdma + DPDK)
# - SPDK 作为 VPP 的存储插件

# 适用场景判断：
# 硬盘延迟 < 10μs → SPDK（OLED/Optane）
# 硬盘延迟 > 100μs → io_uring（SATA SSD/HDD，SPDK 收益不大）
# 混合场景大文件 → io_uring + 文件系统（不需要绕过 VFS 的开销）
# 随机小 I/O 密集 → SPDK（极致 IOPS）
```

## 参考来源

- [[concepts/PCIe 子系统]]
- [[concepts/Linux 内存管理]]
- Linux kernel: Documentation/block (Block layer, blk-mq)
- liburing: github.com/axboe/liburing
- SPDK: spdk.io documentation
- Jens Axboe: io_uring deep dive (LWN, 2019)
- NVMe Base Specification (NVMe over Fabrics)
