---
aliases: ["vpp-plugin-perf"]
title: VPP 插件性能调优（节点 / 批处理 / 多核）
tags: [vpp, networking, plugin, performance, reference, active]
created: 2026-07-29
summary: >-
    VPP 插件性能调优实战：向量化批处理原则、node function 热点写法、避免 per-packet 分配与锁、多核 worker 与 RSS 流绑定、巨页/缓冲池调优、用 show runtime/perf 定位瓶颈、NPP 流表清洗的调优经验。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# VPP 插件性能调优（节点 / 批处理 / 多核）

> 前置：[[20-protocols/VPP 2|VPP 知识]]（向量化原理、缓冲管理）、[[50-reference/VPP 插件 开发|VPP 插件开发]]（node/plugin 写法）、[[50-reference/VPP 用法|VPP 使用方法]]（CLI 与 `show runtime`/`show cpu`）。

## 1. 调优心智模型

VPP 的高吞吐来自四条铁律，插件只要违反其中任一条就会断崖式掉速：

1. **永远向量化**：node function 一次处理整批，别拆成 per-packet 调用。
2. **零拷贝、零分配**：处理中不为每个包做堆分配。
3. **无锁 / 线程局部**：数据面不在热路径拿锁。
4. **轮询、不中断**：PMD 轮询模式，避免中断与系统调用。

调优目标 = 让每个 worker 核的 `show cpu` pps 接近线速、让 `show runtime` 里你的 node 单次调用耗时最小、让 `show errors` 无丢包。

## 2. Node Function 热路径写法

### 2.1 批处理循环范式

```c
static uword
your_node_fn (vlib_main_t * vm,
              vlib_node_runtime_t * node,
              vlib_frame_t * frame)
{
    u32 * from = vlib_frame_vector_args (frame);
    uword n_left = frame->n_vectors;
    u16 nexts[VLIB_FRAME_SIZE];   /* 批量决定下一跳，避免逐包函数调用 */

    while (n_left > 0)
    {
        u32 bi = from[0];
        vlib_buffer_t * b = vlib_get_buffer (vm, bi);

        /* 关键：用 buffer 元数据，别重解析 */
        ip4_header_t * ip = vlib_buffer_get_current (b);  /* 已在正确偏移 */

        /* 处理逻辑……尽量线性、少分支 */

        nexts[0] = (判断) ? NEXT_DROP : NEXT_ETH_OUTPUT;
        from += 1; nexts += 1; n_left -= 1;
    }

    /* 一次性下发整批 */
    vlib_buffer_enqueue_to_next (vm, node, vlib_frame_vector_args (frame),
                                 nexts, frame->n_vectors);
    return frame->n_vectors;
}
```

要点：
- 用 `vlib_buffer_enqueue_to_next` 批量入队，而非逐包 `vlib_put_next_frame`。
- 下一跳决策先存数组，循环结束统一下发，减少分支与函数调用开销。

### 2.2 避免 per-packet 分配与初始化

| 反模式（慢） | 正确做法（快） |
|---|---|
| 每个包 `clib_mem_alloc` / `pool_get` | 预分配对象池，用 buffer 的 `opaque` 存上下文 |
| 每个包 `memset` 整个 buffer | 只初始化用到的字段 |
| 每个包 `clock_gettime` | 节点入口取一次时间，批内复用 |
| 每个包 `format` 打日志 | 累计计数，周期（process node）输出 |

- buffer 自带 `opaque` / `opaque2`（两个 `u32[10]` 区）可挂临时状态，跨 node 传递，免分配。
- 需要按流状态？用 **per-flow 哈希表**（如 `clib_bihash`），键为 5 元组，值是预分配条目；避免线性查找。

### 2.3 减少缓存未命中

- 顺序访问 `from[]` 与 `nexts[]`（连续内存，硬件预取友好）。
- 节点里**不要**跳着访问大结构体；把热字段紧凑排布。
- 大表（如流表）用 `clib_bihash`（基于哈希的 bihash，对多核友好）而非链表。

### 2.4 分支优化

- 数据面常见分支（是 IPv4 还是 IPv6、是否命中）尽量**批量前判**，减少循环内分支摆动。
- 用 likely/unlikely 标注（`CLIB_UNIX` 上可用 `__builtin_expect`）帮助分支预测，但优先级低于"批量 + 顺序"。

## 3. Process Node 与定时任务

- 周期任务（流表老化、统计刷新）放 **PROCESS node**，用 `wait_for_event_or_clock` 让出 CPU，别用 `sleep` 或忙等。
- 触发实际工作时用 **interrupt pending** 唤醒一个轻量 INTERNAL cleaner node（见 NPP：[[50-reference/NPP 定时器 机制|PROCESS 定时 + INTERRUPT 触发 cleaner]]），让重活在节点图里被向量化处理、受 `show runtime` 统计。
- 周期不要太碎：1 秒级足够，避免频繁唤醒打断数据面批处理。

## 4. 多核与流绑定

### 4.1 Worker 数量

```bash
# startup.conf
cpu {
  main-core 1
  workers 4            # worker 数 ≈ 收包队列数（RSS），过多反而抢 cache
}
```

- worker 数应匹配 NIC 的 RSS 队列数与 NUMA。典型：每核 1 worker。
- 用 `show threads` 确认绑核生效。

### 4.2 流亲和（RSS / 流哈希）

- 不同流靠 NIC RSS 或 VPP 流哈希分散到不同 worker，**同一条流的包永远落同一 worker**，从而数据面无锁。
- 插件里若维护 per-flow 状态表，**不要跨 worker 共享可写状态**；要么 per-worker 副本，要么用无锁结构 + 明确的所有权。
- 测试时关掉 NIC 的松散 RSS，避免一条流被两个核分到（导致状态错乱 / 锁竞争）。

### 4.3 NUMA 亲和

- 网卡、巨页、worker 尽量在同一 NUMA 节点。跨 NUMA 访问内存会显著掉速。
- `show numa` / `lscpu` 确认；绑定 worker 到本地核。

## 5. 内存与缓冲池调优

```bash
# 巨页：DPDK 需要足够大页
sudo sysctl -w vm.nr_hugepages=2048     # 或 /etc/default/grub 持久化

# startup.conf
buffers {
  buffers-per-numa 16384    # 每 NUMA 节点缓冲数，按流量调大
}
dpdk {
  no-multi-seg              # 小包场景关 multi-seg 省开销；巨包场景需开
}
```

- `show buffers` 看缓冲池占用：若频繁接近上限 → 丢包，调大 `buffers-per-numa`。
- `show dpdk interface` 看 `rx_mbuf_alloc_fail` / `rx_no_bufs`：有计数说明内存不足或队列太小。

## 6. 定位瓶颈（观测手段）

### 6.1 VPP 内建

```bash
show cpu                 # 每 worker 实时 pps，第一观感
show runtime             # 每个 node 的调用次数 + 累计/平均时钟周期 → 找最耗时 node
show errors              # 丢包原因计数（区分 buffer 不足 / 校验错 / 策略丢）
show interface           # 每接口 rx/tx/drops
show node graph <node>   # 确认你的 node 在正确位置、被调用
trace add <input> 100    # 抽 100 个包看走过哪些 node、每跳决策
```

### 6.2 系统级（host）

```bash
# 定位到具体函数热点
perf top -p $(pgrep vpp)            # 实时函数热点
perf record -g -p $(pgrep vpp) -a sleep 10 && perf report

# CPU 是否跑满 / 是否跑错核
htop                                # 看 vpp 主线程/worker 占用
# 中断是否打到正确队列
cat /proc/interrupts | grep -i eth
```

- 调优循环：**测基线 pps → `show runtime` 找最耗时 node → 改 node function → 重测**。

## 7. 插件常见性能陷阱

| 陷阱 | 现象 | 修复 |
|---|---|---|
| node function 内 `clib_mem_alloc` | pps 上不去、`show runtime` 你的 node 耗时高 | 预分配池 / 用 buffer opaque |
| 热路径拿锁（mutex/spinlock） | 多核反而更慢、抖动 | 改为 per-worker 状态或无锁 bihash |
| 逐包打日志 / 计数 `format` | CPU 全耗在格式化 | 累计整数，process node 周期输出 |
| 流被 RSS 分到多核共享状态 | 偶发错乱、丢包 | 保证流亲和，状态按流/按 worker 隔离 |
| worker 数 > 队列数 | cache 争用、降速 | 对齐 RSS 队列数 |
| 巨页不足 / buffer 池小 | `show errors` 丢包、`rx_no_bufs` | 调大 `hugepages` 与 `buffers-per-numa` |
| 跨 NUMA 取内存 | 延迟翻倍 | 绑核 + 本地大页 |
| process node 忙等/长循环 | 整个数据面卡死 | 用 `wait_for_event_or_clock` 让出 |

## 8. NPP 流表清洗调优经验（实战）

本项目 [[50-reference/NPP 定时器 机制|NPP]] 的流表老化是典型调优对象：

- **两级解耦**：PROCESS node 每秒唤醒一次只做"是否空闲"判定；真正清理交给被 interrupt pending 的 `flowtable_cleaner_node`（INTERNAL，向量化处理），不阻塞数据面。
- **慢/快清理**：低负载走慢清理（低频率大批量），高负载触发快清理（小批量、降频），避免一次性遍历全表卡住。
- **会话删除回调解耦**：通过 `flowtable_exapi_plugin.so` 的 `del_handler` 把协议识别/falcon 清理延后到会话删除时执行，不在热路径同步做。
- 调优时重点看 `show runtime` 里 `flowtable-clear-process` / `flowtable_cleaner_node` 的调用次数与耗时，确认清理未拖垮转发。

## 延伸

- [[20-protocols/VPP 2|VPP 知识]]、[[50-reference/VPP 插件 开发|VPP 插件开发]]、[[50-reference/VPP 用法|VPP 使用方法]]
- FD.io 性能调优指南、VPP `docs/perf.md`；DPDK 官方 PMD / 巨页调优文档。
