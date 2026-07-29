---
title: VPP 开发实战
category: entities
tags: [vpp, development, plugin, plugin, node, packet-processing]
created: 2026-07-29
updated: 2026-07-29
summary: VPP (Vector Packet Processing) 从零到生产的插件开发指引 — 环境搭建、完整插件项目模板、node function 编写、CLI/API 注册、构建与调试、性能调优速查
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources: []
---

# VPP 开发实战

> 本文教你从零开始写一个 VPP 插件。每段代码均可编译运行。
>
> 背景知识见 [[20-protocols/vpp|VPP 知识（架构）]]，深度 API 见 [[50-reference/vpp-plugin-dev|VPP 插件开发参考]]，性能调优见 [[50-reference/vpp-plugin-perf]]。

## 1. 环境搭建

### 1.1 安装 VPP

```bash
# Ubuntu 24.04 — 添加 FD.io 仓库（版本号按需替换）
echo "deb [trusted=yes] https://packagecloud.io/fdio/2502/ubuntu/ $(lsb_release -sc) main" \
  | sudo tee /etc/apt/sources.list.d/99fdio.list
sudo apt update && sudo apt install vpp vpp-plugin-core vpp-plugin-dpdk

# 验证
vpp -v                    # 查看版本
systemctl status vpp      # 服务状态
dpdk-devbind.py --status  # 网卡状态（可选）
```

### 1.2 编译环境（源码 + 外部插件）

```bash
# 克隆 VPP 源码（需要内部头文件）
git clone https://github.com/FDio/vpp.git
cd vpp
git checkout stable/2502   # 或指定版本
make install-deps          # 安装依赖
make build-release         # 全量构建（20-40 分钟首次）

# 产物路径
ls build-root/install-vpp-native/vpp/lib/vpp_plugins/
# dpdk_plugin.so, nat_plugin.so ...
```

### 1.3 开发环境速配

```bash
# 巨页（DPDK 需要）
echo 2048 | sudo tee /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages

# 简单启动（无需网卡）
sudo vpp unix { interactive } &
# 进入 CLI 交互模式
vppctl show version
vppctl show node
```

## 2. 完整插件项目 —— 从零开始

我们在 VPP 源码 `src/plugins/` 下创建插件，这是最直接的方式。

### 2.1 目录结构

```
src/plugins/hello_vpp/
├── CMakeLists.txt
├── hello_vpp.c              # 插件入口 + node 注册
├── hello_vpp_node.c         # 核心 node function
└── cli.c                    # CLI 命令
```

### 2.2 插件入口

```c
// hello_vpp.c — 插件入口
#include <vlib/vlib.h>
#include <vnet/vnet.h>
#include <vnet/plugin/plugin.h>

// VPP 插件的"身份证"——必须导出，否则 VPP 不加载
VLIB_PLUGIN_REGISTER () = {
    .version = "1.0",
    .description = "Hello VPP — 第一个自定义插件",
};

// 初始化钩子：VPP 启动时调用
static clib_error_t *
hello_vpp_init (vlib_main_t * vm)
{
    clib_warning ("hello_vpp plugin loaded successfully!");
    return 0;
}
VLIB_INIT_FUNCTION (hello_vpp_init);
```

### 2.3 核心 Node —— 包计数器

```c
// hello_vpp_node.c — 数据面处理节点
#include <vlib/vlib.h>
#include <vnet/vnet.h>
#include <vnet/ethernet/ethernet.h>
#include <vnet/ip/ip4.h>

// 节点运行上下文（per-node 运行时状态）
typedef struct {
    u64 packet_count;
} hello_vpp_node_ctx_t;

// ─── node function ──────────────────────────────
// 这是 VPP 数据面的核心：一次处理一批包（vector）
static uword
hello_vpp_node_fn (vlib_main_t * vm,
                   vlib_node_runtime_t * node,
                   vlib_frame_t * frame)
{
    u32 * from   = vlib_frame_vector_args (frame);
    uword n_left = frame->n_vectors;

    hello_vpp_node_ctx_t * ctx = vlib_node_get_runtime_data (node, sizeof (*ctx));
    ctx->packet_count += n_left;

    // 批量决定下一跳——全部默认到 error-drop（仅做计数不做实际转发）
    u16 nexts[VLIB_FRAME_SIZE];
    for (int i = 0; i < frame->n_vectors; i++)
        nexts[i] = 0;   // 0 == .n_next_nodes[0] = "error-drop"

    vlib_buffer_enqueue_to_next (vm, node, vlib_frame_vector_args (frame),
                                 nexts, frame->n_vectors);
    return frame->n_vectors;
}

// 注册节点
VLIB_REGISTER_NODE (hello_vpp_node) = {
    .function  = hello_vpp_node_fn,
    .name      = "hello-vpp-node",
    .type      = VLIB_NODE_TYPE_INTERNAL,
    .vector_size = sizeof (u32),
    .n_next_nodes = 1,
    .next_nodes = { [0] = "error-drop", },
};
```

### 2.4 CLI 命令

```c
// cli.c — 添加自定义 CLI 命令
#include <vlib/vlib.h>
#include <vnet/vnet.h>

// 节点名（需与 VLIB_REGISTER_NODE 的 .name 一致）
extern vlib_node_registration_t hello_vpp_node;

static clib_error_t *
show_hello_vpp_count_fn (vlib_main_t * vm,
                         unformat_input_t * input,
                         vlib_cli_command_t * cmd)
{
    // 遍历所有 worker，累加计数
    u64 total = 0;
    vlib_node_runtime_t * rt;
    vlib_node_main_t * nm = &vm->node_main;

    // vlib_node_runtime_for_each 宏遍历所有运行时实例
    // 这里简化：取 node 索引后读 runtime data
    u32 node_index = hello_vpp_node.index;
    vlib_worker_thread_t * wts = vlib_worker_threads;
    for (int i = 0; i < wts->n_threads; i++) {
        vlib_main_t * wvm = wts[i].vlib_main;
        vlib_node_runtime_t * wrt = vlib_node_get_runtime (wvm, node_index);
        hello_vpp_node_ctx_t * ctx = vlib_node_get_runtime_data (wrt, sizeof (*ctx));
        total += ctx->packet_count;
    }

    vlib_cli_output (vm, "hello-vpp-node packet count: %lu", total);
    return 0;
}

VLIB_CLI_COMMAND (show_hello_vpp_count) = {
    .path       = "show hello-vpp count",
    .short_help = "show hello-vpp packet count",
    .function   = show_hello_vpp_count_fn,
};
```

### 2.5 CMakeLists.txt

```cmake
# CMakeLists.txt
add_vpp_plugin (hello_vpp
  SOURCES
    hello_vpp.c
    hello_vpp_node.c
    cli.c
)
```

### 2.6 构建

```bash
# 在 VPP 源码根目录
cd vpp

# 方式一：增量构建（仅编译你的插件，快）
make build

# 方式二：若只测试插件可单独 cmake
cd build-root
cmake --build . --target hello_vpp_plugin

# 产物
ls build-root/install-vpp-native/vpp/lib/vpp_plugins/hello_vpp_plugin.so
```

### 2.7 加载与验证

```bash
# 复制插件到 VPP 插件路径
sudo cp build-root/install-vpp-native/vpp/lib/vpp_plugins/hello_vpp_plugin.so \
      /usr/lib/vpp_plugins/

# 配置加载（startup.conf 或启动时指定）
sudo vpp unix { \
  cli-listen /run/vpp/cli.sock \
  interactive \
} plugins { \
  plugin hello_vpp_plugin.so { enable } \
}

# 在另一个终端验证
vppctl show plugins          # 确认 hello_vpp 在列表中
vppctl show node             # 确认 hello-vpp-node 已注册

# 测试 CLI
vppctl show hello-vpp count  # 输出 0（还没流量经过）
```

## 3. 实用插件：VNET Feature 节点

真正常见的开发模式是将 node 挂到 VNET 的 ip4-unicast 或 ip4-output 功能链上，让每个经过接口的 IP 包自动经过你的处理。

```c
// ip_counter.c — 在 ip4-unicast feature 上挂一个包计数节点
#include <vlib/vlib.h>
#include <vnet/vnet.h>
#include <vnet/ip/ip4.h>
#include <vnet/fib/fib_table.h>

// ─── node function ──────────────────────────────
static uword
ip_counter_node_fn (vlib_main_t * vm,
                    vlib_node_runtime_t * node,
                    vlib_frame_t * frame)
{
    u32 * from   = vlib_frame_vector_args (frame);
    uword n_left = frame->n_vectors;

    // 拿 per-node 上下文
    static u64 total = 0;
    total += n_left;

    while (n_left >= 4) {
        // 4 路展开 + 预取，优化 cache
        vlib_buffer_t * b0, *b1, *b2, *b3;
        u32 bi0, bi1, bi2, bi3;

        bi0 = from[0]; bi1 = from[1]; bi2 = from[2]; bi3 = from[3];
        b0 = vlib_get_buffer (vm, bi0);
        b1 = vlib_get_buffer (vm, bi1);
        b2 = vlib_get_buffer (vm, bi2);
        b3 = vlib_get_buffer (vm, bi3);

        // 预取下一批
        if (n_left > 4) {
            rte_prefetch0 (vlib_get_buffer (vm, from[4]));
            rte_prefetch0 (vlib_get_buffer (vm, from[5]));
            rte_prefetch0 (vlib_get_buffer (vm, from[6]));
            rte_prefetch0 (vlib_get_buffer (vm, from[7]));
        }

        // 全部 PASS——不修改，不 drop
        from += 4; n_left -= 4;
    }

    // 残余包处理
    while (n_left > 0) {
        from++; n_left--;
    }

    return frame->n_vectors;
}

VLIB_REGISTER_NODE (ip_counter_node) = {
    .function  = ip_counter_node_fn,
    .name      = "ip-counter",
    .type      = VLIB_NODE_TYPE_INTERNAL,
    .vector_size = sizeof (u32),
    .n_next_nodes = 1,
    .next_nodes = { [0] = "ip4-lookup", },  // 处理完回到 ip4 路径
};
```

**挂接到 VNET feature 链**：

```c
// 在插件初始化时挂接到指定接口的 ip4-unicast 功能链
#include <vnet/feature/feature.h>

static clib_error_t *
ip_counter_init (vlib_main_t * vm)
{
    // 对所有已存在和未来的接口启用
    vnet_feature_enable_disable ("ip4-unicast", "ip-counter",
                                 ~0,  // sw_if_index（~0 表示所有接口）
                                 1,   // enable
                                 0,   // 优先级
                                 0);
    return 0;
}
VLIB_INIT_FUNCTION (ip_counter_init);
```

**效果**：每个 IP 包经过时 `vppctl show runtime` 可见 `ip-counter` 节点被调用且有计数。

## 4. 处理并修改包内容

```c
// 在 node function 内部修改包头的示例
static uword
modify_ttl_node_fn (vlib_main_t * vm,
                    vlib_node_runtime_t * node,
                    vlib_frame_t * frame)
{
    u32 * from   = vlib_frame_vector_args (frame);
    uword n_left = frame->n_vectors;

    while (n_left > 0) {
        u32 bi = from[0];
        vlib_buffer_t * b = vlib_get_buffer (vm, bi);

        // 取 IP 头（VPP 已经帮我们偏移好了）
        ip4_header_t * ip = vlib_buffer_get_current (b);
        ip->ttl--;                     // TTL 减 1

        // 更新 IP 校验和
        ip->checksum  = ip4_header_checksum (ip);

        from++; n_left--;
    }

    // 全部放行到 ip4-lookup
    vlib_buffer_enqueue_to_next (vm, node, vlib_frame_vector_args (frame),
                                 NULL, frame->n_vectors);  // NULL = 统一默认 next
    return frame->n_vectors;
}
```

## 5. Process Node（后台定时任务）

适合做流表老化、定时统计、周期性清理：

```c
// timer_process.c — 每秒打印一次计数的 process node
#include <vlib/vlib.h>

static uword
timer_process_fn (vlib_main_t * vm,
                  vlib_node_runtime_t * rt,
                  vlib_frame_t * f)
{
    u32 count = 0;

    while (1) {
        // 每 1 秒被唤醒一次
        vlib_process_wait_for_event_or_clock (vm, 1.0);

        // 消费掉可能的唤醒事件
        vlib_process_get_events (vm, NULL);

        // 做周期任务（这里只是递增打印）
        count++;
        vlib_cli_output (vm, "timer_process: count = %u\n", count);

        // 重要：process node 不能长时间循环
    }
    return 0;
}

VLIB_REGISTER_NODE (timer_process_node) = {
    .function = timer_process_fn,
    .type = VLIB_NODE_TYPE_PROCESS,
    .name = "timer-process",
};
```

**process node 要点**：
- `wait_for_event_or_clock` 是让出点，**不能阻塞或忙等**
- 数据面**不能**放在 process node 里——用 interrupt pending 唤醒 INTERNAL node
- 实际案例参考 NPP 的 `flowtable-clear-process`（[[50-reference/npp-timer-mechanism]]）

## 6. 完整外部插件项目模板

如果不想在 VPP 源码树内开发（推荐独立仓库）：

```
my-vpp-plugin/
├── CMakeLists.txt
├── plugin.c
├── plugin_node.c
└── cli.c
```

```cmake
# CMakeLists.txt — 外部插件构建
cmake_minimum_required(VERSION 3.16)
project(my_vpp_plugin C)

# 指向 VPP 安装目录
set(VPP_DIR "/usr/local" CACHE PATH "VPP install prefix")

find_package(VPP REQUIRED)

add_vpp_plugin(my_plugin
  SOURCES
    plugin.c
    plugin_node.c
    cli.c
)
```

```bash
# 构建
mkdir build && cd build
cmake .. -DVPP_DIR=/path/to/vpp/build-root/install-vpp-native
make
sudo make install
```

## 7. 常用调试手段

### 7.1 包追踪（最常用）

```bash
# 捕获前 100 个经过 dpdk-input 的包
vppctl trace add dpdk-input 100

# 放一些流量，然后查看
vppctl show trace

# 输出示例：
# Packet 1
#   dpdk-input:  eth0 rx queue 0
#     ethernet-input: IP4
#       ip4-input: ...
#         hello-vpp-node: count=1     ← 你的节点被调用了！
#           error-drop
```

### 7.2 运行时性能分析

```bash
vppctl show runtime         # 查看所有节点调用次数 + 平均时钟周期
vppctl show cpu             # 每 worker 的 pps
vppctl show errors          # 丢包原因
vppctl show buffers         # 缓冲池占用
```

### 7.3 GDB 调试

```bash
# 前台启动 VPP（避免 systemd 包装）
sudo vpp unix { interactive gdb /tmp/vpp-gdb } &
# 或直接 gdb attach
sudo gdb -p $(pgrep vpp)

# 常用 GDB 命令
(gdb) bt                    # 看当前调用栈
(gdb) p vm->thread_index    # 确认在哪个 worker 线程
(gdb) break your_node_fn   # 断点到你的节点
```

### 7.4 日志与崩溃

```bash
# VPP 运行时日志
journalctl -u vpp -f

# 启动日志
cat /tmp/vpp.log

# 检查插件加载失败原因
ldd my_plugin.so                    # 依赖缺失
nm -D my_plugin.so | grep register  # 确认符号导出了
```

## 8. 常见陷阱

| 现象 | 原因 | 解决 |
|------|------|------|
| `show plugins` 无你的插件 | 插件未 enable 或路径不对 | `plugins { plugin xxx.so { enable } }` 或放对目录 |
| 启动崩溃 / 段错误 | ABI 版本不匹配 | `VLIB_PLUGIN_REGISTER` 的 version 须对齐 VPP 构建版本 |
| node 不调用 | 没挂进数据面图 | 用 `vnet_feature_enable_disable` 或 `vlib_node_add_next` 串接 |
| 数据面卡死 | process node 阻塞 | 避免 sleep/等锁，用 `wait_for_event_or_clock` 让出 |
| 修包后校验和错 | 改了 IP/TCP/UDP 头没重算校验和 | `ip4_header_checksum()` / 用 VPP 的 checksum 计算函数 |
| 多核丢包 / 乱序 | 流被 RSS 分到多核 | 确认 RSS 哈希一致，流状态 per-worker |
| 内存相关崩溃 | buffer 越界访问 | `vlib_buffer_validate()` 检查 buffer 状态 |
| 性能差 / pps 上不去 | node function 逐包分配或拿锁 | 预分配 + per-worker 状态，见 [[50-reference/vpp-plugin-perf]] |

## 9. 快速参考

```bash
# ===== 开发速查 =====
# 1. 插件声明
VLIB_PLUGIN_REGISTER () = { .version, .description };
VLIB_INIT_FUNCTION (my_init);

# 2. Internal node
VLIB_REGISTER_NODE (my_node) = {
    .function = my_node_fn,
    .name = "my-node",
    .type = VLIB_NODE_TYPE_INTERNAL,
};

# 3. Process node
VLIB_REGISTER_NODE (my_proc) = {
    .function = my_proc_fn,
    .type = VLIB_NODE_TYPE_PROCESS,
};

# 4. CLI
VLIB_CLI_COMMAND (my_cmd) = {
    .path = "my command",
    .function = my_cmd_fn,
};

# 5. VNET feature 挂接
vnet_feature_enable_disable ("ip4-unicast", "my-node", sw_if_index, 1);

# 6. 包追踪
vppctl trace add dpdk-input 100
vppctl show trace

# 7. 性能观测
vppctl show runtime
vppctl show cpu
```

## 参考来源

- [[20-protocols/vpp|VPP 核心架构]]
- [[50-reference/vpp-usage|VPP 使用方法]]
- [[50-reference/vpp-plugin-dev|VPP 插件开发参考]]
- [[50-reference/vpp-plugin-perf|VPP 性能调优]]
- [[50-reference/npp-timer-mechanism|NPP 定时触发机制（实战案例）]]
- FD.io 文档: https://s3-docs.fd.io/
