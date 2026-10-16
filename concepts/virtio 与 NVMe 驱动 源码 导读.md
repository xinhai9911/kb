---
title: virtio 与 NVMe 驱动 源码 导读
category: concepts
tags: [kernel, virtio, nvme, scsi, block-layer, source-reading, 内核, active]
created: 2026-10-16
updated: 2026-10-16
summary: >-
    三种挂载形态的 guest 侧内核驱动源码导读（路径 C 深潜）：
    virtio_blk（feature 协商 → blk-mq tag_set → 多队列 virtqueue → virtblk_queue_rq/done 与 virtio_blk_outhdr）、
    virtio_scsi（control/event/request 三类队列 → scsi_host_template → CDB 构建与 TMF/热插拔事件）、
    nvme 驱动分层（nvme-core 与 nvme-pci、admin 队列与 I/O 队列创建、命名空间与 add_disk、
    SQ/CQ 门铃与 MSI-X 完成路径）；以及从 sysfs 反查驱动、用 blktrace/perf/ftrace 观测请求路径的方法。
    前置 QEMU 设备模型 与 virtio 协议、存储栈与 io_uring。
base_confidence: 0.85
lifecycle: reviewed
---

# virtio 与 NVMe 驱动 源码 导读

> 前置：[[concepts/QEMU 设备模型 与 virtio 协议]]（virtqueue 三环与设备 ID）、[[concepts/存储栈与io_uring]]（块层与 NVMe 队列）。
> 定位：这是[[synthesis/公有云镜像适配 学习路径]]里的**路径 C（深潜）**材料；不读源码也能做完镜像适配，读了能把"为什么必须打这三个驱动"落到代码上。

## 0. 先说结论：三条路径在代码里长什么样

| 形态 | guest 驱动 | 关键结构 | 一次 IO 走的路 |
|---|---|---|---|
| virtio-blk | `virtio_blk.ko` | `struct virtio_blk` + blk-mq tag_set | blk-mq → 填 `virtio_blk_outhdr` → virtqueue → kick |
| virtio-scsi | `virtio_scsi.ko` + `scsi_mod` + `sd_mod` | `struct virtio_scsi` + `Scsi_Host` | SCSI 中层 → 构 CDB → 请求队列 virtqueue |
| NVMe 云盘 | `nvme.ko` / `nvme_core.ko` | `struct nvme_ctrl` + `struct nvme_queue` | blk-mq → 填 64B command → SQ 门铃 → CQ 中断 |

**两条"分叉"要记住**：
- virtio-blk **不进 SCSI 中层**；virtio-scsi **进**（这就是设备名 `vda` vs `sda` 的根源）
- NVMe 完全不走 virtio，用**标准 NVMe 协议**（门铃 + SQ/CQ），与裸机同一套驱动

## 1. virtio_blk（`drivers/block/virtio_blk.c`）

### 1.1 私有结构与 probe 流程

```
struct virtio_blk {
    struct virtio_device *vdev;     // 底层 virtio 设备
    struct blk_mq_tag_set tag_set;  // blk-mq 的一座 tag set（多队列）
    struct gendisk *disk;           // 块设备对象
    struct virtqueue *vqs[];        // 多队列：每个 hw queue 一个 virtqueue
    char disk_name[];               // "vda"…
};
```

`virtblk_probe()` 主干（按顺序读就懂）：

1. **feature 协商**：读 `VIRTIO_BLK_F_MQ`（多队列）、`_F_FLUSH`、`_F_DISCARD`、`_F_WRITE_ZEROES`、`_F_BLK_SIZE`…
2. **建 tag_set**：`blk_mq_alloc_tag_set()`，`nr_hw_queues` 来自协商结果
3. **申请 virtqueue**：`virtio_find_vqs()`，回调注册为 `virtblk_done`
4. **注册块设备**：`add_disk()` / `blk_mq_alloc_disk()`（内核版本不同写法不同）
5. 读容量、扇区大小、拓扑等配置（`virtio_cread_feature`）

### 1.2 请求与完成路径

```
上层的 read/write
  → 块层 multiplex（bio → request）
  → blk-mq 取出一个 tag，调用 队列的 .queue_rq = virtblk_queue_rq()
      → 取 req 内嵌的 virtio_blk_outhdr（type/ioprio/sector）
      → blk_rq_map_sg() 把数据段转成 scatterlist
      → virtqueue_add_sgs() 挂到该 hw queue 的 virtqueue
      → virtqueue_kick() 通知 host（QEMU）
  → host 处理完毕后写 used ring 并发中断
  → 回调 virtblk_done() 读 status 字节
      → blk_mq_complete_request() 交回块层
```

**wire 格式**（`include/uapi/linux/virtio_blk.h`）：

```c
struct virtio_blk_outhdr {   // 请求头
    __virtio32 type;          // IN/OUT/FLUSH/GET_ID/DISCARD/WRITE_ZEROES
    __virtio32 ioprio;
    __virtio64 sector;
};
/* 之后是数据段，末尾 1 字节 status（OK / IOERR / UNSUPP） */
```

**注意**：这里**没有 SCSI CDB**。想加 `UNMAP`/`VPD`/`PR` 这类能力，virtio-blk 协议里根本没有对应命令
→ 所以云上要"完整 SCSI 语义"就得用 virtio-scsi（回到 [[concepts/QEMU 设备模型 与 virtio 协议]] §3.3 的结论）。

## 2. virtio_scsi（`drivers/scsi/virtio_scsi.c`）

### 2.1 三类队列（与 SCSI 语义一一对应）

| 队列 | 宏 | 用途 |
|---|---|---|
| control | `VIRTIO_SCSI_VQ_CTRL` | TMF（abort/reset）、参数设置 |
| event | `VIRTIO_SCSI_VQ_EVENT` | 热插拔、参数变更事件 |
| request | `VIRTIO_SCSI_VQ_REQUEST` | **命令 CDB 队列（每 CPU 一个）** |

### 2.2 与 SCSI 中层的对接

```
scsi_mod（SCSI 中层）: 错误恢复、队列、命令重试
   └─ 调用 host template 的 .queuecommand = virtio_scsi_queuecommand()
        → virtio_scsi_build_cmnd(): 组 struct virtio_scsi_cmd_req { lun[8], tag, task_attr, cdb[32] }
        → virtqueue_add_sgs() 到 request vq → kick
   └─ 完成后 → virtscsi_complete_cmd() → scsi_done()
```

**关键差异**：命令是**真正的 SCSI CDB**（READ(10/16)、WRITE、UNMAP…），
所以中间多了 SCSI 中层的一整套逻辑（重试、sense 处理、`sd_mod` 把 SCSI 磁盘变成 `/dev/sdX`）。
**这就是 virtio-scsi "开销略高但语义完整"的代码级解释。**

### 2.3 TMF 与热插拔

- `virtio_scsi_eh_abort_handler` / `eh_device_reset_handler` → 走 **control 队列**的 TMF
- `viritscsi_event_done()` 收事件 → `scsi_scan_target()` → 触发 LUN 的添加/移除
  → **云上"在线挂载数据盘后 lsblk 能立刻看到"就是这条路径**

## 3. NVMe 驱动（`drivers/nvme/`）

### 3.1 分层结构（重要：不是一个大驱动）

```
drivers/nvme/
├── host/          ← 传输无关（nvme-core）：协议、队列、命名空间、块设备
├── host/pci.c     ← nvme-pci：PCIe transport（BAR、门铃、MSI-X、DMA 环）
├── host/tcp.c / rdma.c / fc.c  ← 其他 transport（NVMe-oF）
└── target/        ← NVMe target（服务端，与本文无关）
```

- **nvme-core**：`struct nvme_ctrl`、`struct nvme_queue`、命令构造、超时/复位、命名空间扫描
- **nvme-pci**：映射 BAR（寄存器 + **门铃**）、申请 DMA 内存、建 MSI-X 中断
- 云上"NVMe 协议云盘"用**同一套** nvme-pci + nvme-core（只是 host 侧由厂商实现）

### 3.2 队列与命令

```
struct nvme_queue {
    u16 qid;                    // 队列 ID：0 = admin，其他为 I/O
    struct nvme_command *sq_cmds;   // Submission Queue 环形缓冲
    struct nvme_completion *cqes;   // Completion Queue 环形缓冲
    u16 sq_tail, cq_head;
};
/* 门铃：writel(sq_tail, dev->dbs + SQ_TAIL(qid)); */
```

- **队列创建顺序**：`nvme_pci_configure_admin_queue()` → 建 admin 队列（qid 0）→
  `nvme_create_io_queues()` → 通过 admin 命令 `Create CQ` / `Create SQ` 建 I/O 队列
- **命名空间**：`nvme_alloc_ns()` → 每个 namespace 一个 `gendisk` → `/dev/nvme0n1…`
  （**"每块云盘 = 一个 namespace"落在代码上就是这里**）
- **一次 IO**：`nvme_queue_rq()` → `nvme_setup_rw()` 填 64 字节命令 → 写 SQ → 敲门铃；
  完成：MSI-X → `nvme_irq()` → 扫 CQ → `nvme_complete_rq()`

**命令是 NVMe 原生的**（opcode：Read 0x02 / Write 0x01 / Flush 0x00 / Write Zeroes 0x08 / DSM Deallocate 0x09），
与裸机 SSD 完全一致 —— 这就是能直接复用 `nvme-cli` / `smartctl` 的原因。

## 4. 从 sysfs 反查驱动（排障必备手法）

```bash
# virtio-blk
ls -l /sys/block/vda/device/driver     # -> bus/virtio/drivers/virtio_blk
readlink -f /sys/block/vda             # .../pci.../virtio2/block/vda

# virtio-scsi（走 SCSI 栈）
ls -l /sys/block/sda/device/driver     # -> bus/scsi/drivers/sd
readlink -f /sys/block/sda             # .../host0/target0:0:0/0:0:0:0/block/sda

# NVMe
ls -l /sys/block/nvme0n1/device/driver # -> bus/pci/drivers/nvme
ls /sys/class/nvme/nvme0/              # 控制器属性（model/serial/queue_count…）
cat /sys/block/nvme0n1/queue/scheduler # 常见 none
```

> 这三条 `ls -l .../device/driver` 是最快的"这个盘属于哪个驱动"判据，
> 也是 `projects/kvm-image-check` 判断挂载形态的底层依据。

## 5. 请求路径观测（你的 perf/ftrace 经验可直接迁移）

```bash
# 块层请求级观测
blktrace -d /dev/vda -o - | blkparse -i -
#   看 Q(排队)/D(下发)/C(完成) 三态，能算出驱动与设备各自的耗时

# 追踪具体函数（ftrace）
cd /sys/kernel/debug/tracing
echo virtblk_queue_rq   > set_ftrace_filter
echo function           > current_tracer
cat trace_pipe

# 动态追踪（若装了 bpftrace）
bpftrace -e 'kprobe:virtblk_queue_rq { @[comm] = count(); }'

# 中断分布（看中断是否落在你想要的核上）
cat /proc/interrupts | grep -E 'virtio|nvme'
```

> 与 [[entities/CPU 中断与MSI-X]]、[[entities/CPU 隔离与实时调优]] 连着看：
> 云上数据面性能问题，经常最后归因到"驱动在哪个核上收完成中断"。

## 6. 读到什么程度算够

| 目标 | 需要读到的深度 |
|---|---|
| 做镜像适配（本库主线） | §0 + §4（能判断挂载形态、能解释为什么要三个驱动） |
| 排查云盘性能问题 | §1.2/§3.2 + §5（能定位在哪一层耗时） |
| 开发/改驱动或 PMD | §1–§3 全读 + 上游 `Documentation/` 与 virtio 规范对照 |
| 判断"云厂商换设备会不会影响我" | §0 的两条分叉 + §4 的反查手法 |

## 7. 自测

1. virtio-blk 的请求头里有哪些字段？为什么它实现不了 UNMAP 的细粒度语义？
2. virtio-scsi 的 control / event / request 三类队列各干什么？"在线挂载数据盘立刻可见"走哪条？
3. NVMe 驱动为什么分 nvme-core 与 nvme-pci？云上"NVMe 云盘"用的是哪一层？
4. 一个命令如何判断某块盘是 virtio-blk、virtio-scsi 还是 NVMe？
5. 想量化"驱动与设备各自耗时"，用什么工具？

## 来源

- Linux 内核源码：`drivers/block/virtio_blk.c`、`drivers/scsi/virtio_scsi.c`、`drivers/nvme/host/{core.c,pci.c}`、
  `include/uapi/linux/virtio_blk.h`、`include/linux/nvme.h`
- OASIS virtio 规范 https://docs.oasis-open.org/virtio/
- NVMe 规范（NVMe Base Specification，nvmexpress.org）
- 内核文档：`Documentation/block/`、`Documentation/trace/`

> 断言分级：结构体/函数/队列语义为内核源码事实（不同内核版本字段与函数名可能微调，以本机版本源码为准）；
> 本页不引用具体行号，避免版本漂移导致错误索引。
