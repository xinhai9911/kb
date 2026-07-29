---
title: DPDK 开发实战
category: entities
tags: [dpdk, development, tutorial, pmd, l2fwd, packet-processing]
created: 2026-07-29
updated: 2026-07-29
summary: DPDK 从零到生产的开发指引 — 环境搭建、最小应用、l2fwd 示例、多核 pipeline、ring/mbuf 用法、调试与常见陷阱
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# DPDK 开发实战

> 本文假设读者熟悉 C 语言和 Linux 网络基础。每段代码均来自 DPDK 官方示例的简化版本，可独立编译运行。

## 1. 环境搭建

### 1.1 系统要求

- Linux 4.0+（推荐 5.x）
- 支持 DPDK 的网卡（Intel i40e/ixgbe、Mellanox CX 系列等）
- x86_64 / ARM64 CPU
- **至少 1GB 巨页内存**

### 1.2 安装与编译 DPDK

```bash
# 下载
wget https://fast.dpdk.org/rel/dpdk-26.03.tar.xz
tar xf dpdk-26.03.tar.xz && cd dpdk-26.03

# 编译（DPDK 21.11+ 使用 meson）
meson setup build
ninja -C build
sudo ninja -C build install   # 安装到 /usr/local/

# 配置环境变量（建议加 ~/.bashrc）
export RTE_SDK=$PWD
export RTE_TARGET=x86_64-native-linux-gcc
```

### 1.3 配置巨页

```bash
# 分配 1024 个 2MB 巨页
echo 1024 | sudo tee /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages

# 挂载 hugetlbfs
mkdir -p /mnt/huge
mount -t hugetlbfs nodev /mnt/huge

# 永久配置（/etc/default/grub）
GRUB_CMDLINE_LINUX="default_hugepagesz=1G hugepagesz=1G hugepages=4"
```

### 1.4 绑定网卡到 UIO/VFIO

```bash
# 加载 UIO 内核模块
sudo modprobe uio
sudo insmod dpdk-26.03/build/kernel/linux/igb_uio/igb_uio.ko

# 或使用 VFIO（支持 SR-IOV）
sudo modprobe vfio-pci

# 查看网卡 PCI 地址
dpdk-devbind.py --status

# 绑定（示例：0000:02:00.0 和 0000:02:00.1）
sudo dpdk-devbind.py --bind=igb_uio 0000:02:00.0

# 验证
dpdk-devbind.py --status
```

### 1.5 CPU 隔离（生产环境）

```bash
# 内核 cmdline — 隔离核 2-7 (+ 0-1 给 OS)
GRUB_CMDLINE_LINUX="... isolcpus=2-7 nohz_full=2-7 rcu_nocbs=2-7"

# DPDK EAL 参数 — 只在隔离核运行
-c 0xFC          # coremask: 核 2-7
-n 4             # 内存 channel 数（查 dmidecode）
--socket-mem=1024,0  # 只从 NUMA node 0 分配
```

## 2. 最小 DPDK 应用（Hello World）

```c
// hello_dpdk.c — 验证 EAL 初始化成功
#include <rte_eal.h>
#include <rte_lcore.h>

int main(int argc, char **argv)
{
    int ret = rte_eal_init(argc, argv);  // 初始化 EAL
    if (ret < 0)
        rte_exit(EXIT_FAILURE, "EAL init failed\n");

    argc -= ret;
    argv += ret;

    unsigned lcore_id;
    RTE_LCORE_FOREACH(lcore_id) {
        printf("lcore %u is ready\n", lcore_id);
    }

    rte_eal_cleanup();
    return 0;
}
```

```makefile
# Makefile
include $(RTE_SDK)/mk/rte.vars.mk

APP = hello_dpdk
SRCS-y := hello_dpdk.c
CFLAGS += -O2 -g

include $(RTE_SDK)/mk/rte.extapp.mk
```

```bash
# 编译
make

# 运行
sudo ./build/hello_dpdk -l 0-3 -n 4
# -l 0-3: 使用核 0-3
# -n 4: 内存 channel 数
```

## 3. L2 Forwarding (二层转发)

### 3.1 核心逻辑

```c
// l2fwd.c — 从 port A 收包转到 port B
#include <rte_eal.h>
#include <rte_ethdev.h>
#include <rte_mbuf.h>

#define RX_RING_SIZE 1024
#define TX_RING_SIZE 1024
#define NUM_MBUFS    8191
#define MBUF_CACHE_SIZE 250
#define BURST_SIZE   32

// 端口映射：偶数 port <-> 奇数 port
static int l2fwd_ports[RTE_MAX_ETHPORTS];
static unsigned int nb_ports;

// 初始化一个端口
static int port_init(uint16_t port, struct rte_mempool *mp)
{
    struct rte_eth_conf conf = {0};
    struct rte_eth_dev_info info;
    struct rte_eth_txconf txconf;
    struct rte_eth_rxconf rxconf;

    // 1. 配置设备
    rte_eth_dev_info_get(port, &info);
    conf.rxmode.mtu = 1500;
    int ret = rte_eth_dev_configure(port, 1, 1, &conf);
    if (ret < 0) return ret;

    // 2. 设置 RX/TX 队列
    rxconf = info.default_rxconf;
    ret = rte_eth_rx_queue_setup(port, 0, RX_RING_SIZE,
            rte_eth_dev_socket_id(port), &rxconf, mp);
    if (ret < 0) return ret;

    txconf = info.default_txconf;
    ret = rte_eth_tx_queue_setup(port, 0, TX_RING_SIZE,
            rte_eth_dev_socket_id(port), &txconf);
    if (ret < 0) return ret;

    // 3. 启动设备
    ret = rte_eth_dev_start(port);
    if (ret < 0) return ret;

    // 4. 启用混杂模式
    rte_eth_promiscuous_enable(port);

    return 0;
}

// lcore 主循环 — run-to-completion
static __rte_noreturn int l2fwd_loop(void *dummy)
{
    uint16_t port;
    struct rte_mbuf *bufs[BURST_SIZE];

    for (;;) {
        // 遍历所有 port
        for (port = 0; port < nb_ports; port++) {
            // 收包
            uint16_t nb_rx = rte_eth_rx_burst(port, 0,
                                bufs, BURST_SIZE);
            if (nb_rx == 0)
                continue;

            // 转发：偶数→奇数，奇数→偶数
            uint16_t out_port = port ^ 1;

            // 批量发包
            uint16_t nb_tx = rte_eth_tx_burst(out_port, 0,
                                bufs, nb_rx);

            // 若有发丢，回收 mbuf
            if (nb_tx < nb_rx) {
                for (uint16_t i = nb_tx; i < nb_rx; i++)
                    rte_pktmbuf_free(bufs[i]);
            }
        }
    }
}

int main(int argc, char **argv)
{
    // 1. EAL 初始化
    int ret = rte_eal_init(argc, argv);
    if (ret < 0) rte_exit(EXIT_FAILURE, "EAL failed\n");
    argc -= ret; argv += ret;

    // 2. 检测可用 port
    nb_ports = rte_eth_dev_count_avail();
    if (nb_ports < 2 || (nb_ports & 1))
        rte_exit(EXIT_FAILURE, "Need even ports >= 2\n");

    // 3. 创建 mbuf pool
    struct rte_mempool *mp = rte_pktmbuf_pool_create(
            "mbuf_pool", NUM_MBUFS, MBUF_CACHE_SIZE, 0,
            RTE_MBUF_DEFAULT_BUF_SIZE,
            rte_socket_id());

    // 4. 初始化每个 port
    for (uint16_t p = 0; p < nb_ports; p++)
        if (port_init(p, mp) < 0)
            rte_exit(EXIT_FAILURE, "Port %u init fail\n", p);

    // 5. 在 master lcore 上运行转发
    rte_eal_mp_remote_launch(l2fwd_loop, NULL, CALL_MAIN);
    rte_eal_mp_wait_lcore();
    return 0;
}
```

```bash
# 编译运行
make
sudo ./build/l2fwd -l 0-1 -n 4
```

## 4. 多核 Pipeline 模式

### 4.1 架构

```
lcore 0: RX stage      → ring0
lcore 1: Worker stage   → ring1
lcore 2: TX stage       → (网卡发送)
```

### 4.2 核心代码

```c
// pipeline.c — 使用 rte_ring 连接 stage
#include <rte_ring.h>

#define RING_SIZE 8192

// 两个 ring 做跨核通信
static struct rte_ring *ring_in;
static struct rte_ring *ring_out;

// Stage 1: RX（在 lcore 0 运行）
static int rx_stage(void *arg)
{
    struct rte_mbuf *bufs[BURST_SIZE];

    for (;;) {
        uint16_t nb = rte_eth_rx_burst(0, 0, bufs, BURST_SIZE);
        if (nb == 0) continue;

        // 包入 ring — 交给 worker
        uint16_t enq = rte_ring_enqueue_burst(ring_in,
                        (void **)bufs, nb, NULL);
        if (enq < nb) // ring 满，丢剩余包
            for (; enq < nb; enq++)
                rte_pktmbuf_free(bufs[enq]);
    }
    return 0;
}

// Stage 2: Worker（在 lcore 1 运行）
static int worker_stage(void *arg)
{
    struct rte_mbuf *bufs[BURST_SIZE];

    for (;;) {
        uint16_t nb = rte_ring_dequeue_burst(ring_in,
                        (void **)bufs, BURST_SIZE, NULL);
        if (nb == 0) continue;

        for (uint16_t i = 0; i < nb; i++) {
            // 处理包（解析、修改、分类）
            process_packet(bufs[i]);
        }

        // 处理完推入 TX ring
        rte_ring_enqueue_burst(ring_out,
            (void **)bufs, nb, NULL);
    }
    return 0;
}

// Stage 3: TX（在 lcore 2 运行）
static int tx_stage(void *arg)
{
    struct rte_mbuf *bufs[BURST_SIZE];

    for (;;) {
        uint16_t nb = rte_ring_dequeue_burst(ring_out,
                        (void **)bufs, BURST_SIZE, NULL);
        if (nb == 0) continue;

        rte_eth_tx_burst(1, 0, bufs, nb);
    }
    return 0;
}

int main(int argc, char **argv)
{
    rte_eal_init(argc, argv);

    // 创建两个 ring
    ring_in  = rte_ring_create("rx_queue", RING_SIZE,
                rte_socket_id(), RING_F_SC_DEQ);
    ring_out = rte_ring_create("tx_queue", RING_SIZE,
                rte_socket_id(), RING_F_SC_DEQ);

    // 启动 3 个 stage
    rte_eal_remote_launch(rx_stage,    NULL, 0); // lcore 0
    rte_eal_remote_launch(worker_stage, NULL, 1); // lcore 1
    rte_eal_remote_launch(tx_stage,    NULL, 2); // lcore 2

    rte_eal_mp_wait_lcore();
    return 0;
}
```

**运行**：
```bash
sudo ./build/pipeline -l 0-2 -n 4
```

## 5. 核心 API 详解

### 5.1 rte_mempool — 内存池

```c
// 创建 mbuf 池
struct rte_mempool *mp = rte_pktmbuf_pool_create(
    "pool",              // 名称（调试用）
    NUM_MBUFS,          // 池中数量
    MBUF_CACHE_SIZE,    // 每核缓存数
    0,                  // 私有数据大小
    RTE_MBUF_DEFAULT_BUF_SIZE,  // 每个 mbuf 数据区大小
    rte_socket_id()     // NUMA socket
);

// 从池取 mbuf（应用中一般不直接调，由 rte_eth_rx_burst 完成）
struct rte_mbuf *m = rte_pktmbuf_alloc(mp);

// 释放
rte_pktmbuf_free(m);
```

### 5.2 rte_mbuf — 包缓冲区

```c
// 常用字段
m->port      // 来源端口
m->pkt_len   // 包总长（含多段）
m->data_len  // 当前段数据长度
m->data_off  // 数据起始偏移（默认 RTE_PKTMBUF_HEADROOM）
m->ol_flags  // 卸载标志

// 数据指针（等价于 m->buf_addr + m->data_off）
char *pkt_data = rte_pktmbuf_mtod(m, char *);

// 追加/裁剪数据
rte_pktmbuf_append(m, len);     // 追加到末尾（发包时用）
rte_pktmbuf_adj(m, len);        // 移除头部（剥协议头）
rte_pktmbuf_prepend(m, len);    // 头部前插（加协议头）
rte_pktmbuf_trim(m, len);       // 裁掉末尾

// 链式 mbuf（jumbo frame）
while (m->next) {
    m = m->next;
    printf("seg len=%u\n", m->data_len);
}
```

### 5.3 rte_ring — 无锁队列

```c
// 创建（SPSC: 单生产者单消费者）
struct rte_ring *r = rte_ring_create("my_ring",
    1024,                      // 大小（须 2 的幂）
    rte_socket_id(),
    RING_F_SP_ENQ | RING_F_SC_DEQ);

// 入队 — 批量（推荐）
uint16_t enq = rte_ring_enqueue_burst(r, (void **)mbufs, nb, NULL);

// 出队 — 批量
uint16_t deq = rte_ring_dequeue_burst(r, (void **)mbufs, BURST_SIZE, NULL);

// 入队 — 单元素
rte_ring_enqueue(r, ptr);

// 查询
uint32_t count = rte_ring_count(r);
uint32_t free  = rte_ring_free_count(r);
```

### 5.4 rte_timer — 定时器

```c
// 初始化
struct rte_timer timer;
rte_timer_init(&timer);

// 设置周期定时器（每 1 秒触发）
rte_timer_reset(&timer, rte_get_timer_hz(), SINGLE,
        lcore_id, timer_cb, NULL);

// 回调
void timer_cb(__rte_unused struct rte_timer *t,
              __rte_unused void *arg)
{
    printf("Timer tick on lcore %u\n", rte_lcore_id());
}
```

**注意**：定时器回调在 lcore 主循环中轮询执行，非中断。

## 6. DPDK 通用 Makefile 模板

```makefile
# Makefile — DPDK 应用通用模板
include $(RTE_SDK)/mk/rte.vars.mk

APP = my_app
SRCS-y := main.c

CFLAGS += -O2 -g -Wall -Werror
LDFLAGS += -lrte_eal -lrte_mbuf -lrte_mempool -lrte_ring -lrte_ethdev

include $(RTE_SDK)/mk/rte.extapp.mk
```

对于 meson 项目：
```python
# meson.build
project('my_app', 'C')
dpdk = dependency('libdpdk')
sources = files('main.c')
executable('my_app', sources, dependencies: dpdk)
```

## 7. 调试与调优

### 7.1 常用 EAL 参数

```bash
# 最常用
-l <cores>           # 使用的核列表，如 -l 0-3
-l coremask          # coremask 方式，如 -c 0x0F
-n <channels>        # 内存 channel 数（dmidecode -t memory 确认）
--socket-mem=N0,N1   # 各 NUMA node 内存大小 (MB)

# 调试
--log-level=8        # 设置日志级别
--trace=*            # 启用所有 trace
--log-level=lib.eal:8

# 性能
--no-pci             # 不使用 PCI 设备
--file-prefix=xxx    # 多实例时区分
--proc-type=primary/secondary  # 多进程
```

### 7.2 dpdk-devbind.py

```bash
# 查看状态
dpdk-devbind.py --status

# 绑定到 DPDK
dpdk-devbind.py --bind=igb_uio 0000:02:00.0

# 归还内核
dpdk-devbind.py --bind=ixgbe 0000:02:00.0
```

### 7.3 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| EAL: No free hugepages | 巨页未配置 | `echo 1024 > /sys/kernel/mm/hugepages/...` |
| EAL: PCI device not found | 网卡未绑定 | `dpdk-devbind.py --bind=igb_uio <pci>` |
| rte_eth_rx_burst 总是返回 0 | 设备未启动 | 确认 `rte_eth_dev_start()` 成功 |
| TX burst 返回 < nb_rx | TX ring 满或速率限制 | 增大 TX ring、检查流控、增加 TX desc |
| 内存分配失败 | mbuf 池太小 | 增大 `NUM_MBUFS` 或 `MBUF_CACHE_SIZE` |
| 跨 NUMA 性能差 | lcore 绑定错误 | 确保 lcore 和网卡在同一 socket |
| 包顺序乱 | 多队列 RSS 哈希 | 设置 `rte_eth_rss_conf` 或关闭 RSS |
| 空轮询 CPU 100% | 无流量时 PMD 忙等 | 低流量时 `rte_eth_dev_rx_intr_enable` 休眠 |
| VFIO 失败 | IOMMU 未配置 | 检查 IOMMU，VFIO 需 iommu=pt |

### 7.4 性能调优检查清单

- [ ] CPU 隔离 (`isolcpus`) — 避免调度抖动
- [ ] NUMA 对齐 — lcore 和网卡同一 socket
- [ ] 1GB 巨页 — 减少 TLB miss
- [ ] Burst 大小 32-64 — 摊销函数调用开销
- [ ] TX/RX descriptor 1024-2048 — 足够深
- [ ] Cache line 对齐数据结构 — 避免 false sharing
- [ ] `rte_prefetch0` — 提前加载 mbuf data 到 cache
- [ ] 禁用 Turbo Boost / C-States — 稳定频率
- [ ] 网卡流控关闭 — `rte_eth_dev_set_link_up` 后确认
- [ ] RSS 多队列 — 多核分担

## 8. 完整项目参考

| 示例 | 路径 (dpdk/examples/) | 学习内容 |
|------|----------------------|---------|
| helloworld | `examples/helloworld/` | 最小 EAL 初始化 |
| l2fwd | `examples/l2fwd/` | 二层 MAC 转发 |
| l3fwd | `examples/l3fwd/` | 三层 IP 路由查找 |
| skeleton | `examples/skeleton/` | DPDK 最小应用框架 |
| multi_process | `examples/multi_process/` | 主备/对称多进程 |
| pipeline | `examples/pipeline/` | 流水线配置引擎 |
| kni | `examples/kni/` | 与内核协议栈互通 |

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/DPDK 核心架构]]
- [[synthesis/DPDK 与 eBPF XDP 技术对比]]
- [[concepts/XDP 高速数据路径]]
