---
aliases: ["vpp-plugin-dev"]
title: VPP 插件开发（自定义 Node / Plugin）
tags: [vpp, networking, plugin, development, reference, active]
created: 2026-07-29
summary: >-
    VPP 自定义插件的开发方法：插件目录结构、VLIB_REGISTER_NODE 注册节点、node function 编写范式、Process Node 协程、VNET 功能挂接、CMake 构建、加载与调试。结合 [[50-reference/NPP 定时器 机制|NPP 定时触发机制]] 的实际写法。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# VPP 插件开发（自定义 Node / Plugin）

> 前置：先读 [[20-protocols/VPP 2|VPP 知识]]（节点图、Process Node、缓冲管理）与 [[50-reference/VPP 用法|VPP 使用方法]]（CLI、插件加载）。本文聚焦"如何写一个 `.so` 插件"。

## 1. 插件是什么

- 插件是一个动态库 `xxx_plugin.so`，放在 VPP 的 `plugin_path`（默认 `/usr/lib/vpp_plugins/` 或构建目录 `build-root/.../plugins`）。
- VPP 启动时扫描 `plugin_path`，按 `startup.conf` 的 `plugins { plugin xxx_plugin.so { enable } }` 决定加载哪些。
- 插件在 `vlib_main` 初始化阶段被 `dlopen`，通过导出符号 `xxx_plugin_register` / `xxx_plugin_version` 注册自己。
- 一个插件可注册：多个 **VLIB node**、**CLI 命令**、**API 消息**、**VNET 功能**（如新隧道类型）、**配置项**。

## 2. 目录结构（标准布局）

以仓库内插件路径为例（`src/plugins/<your_plugin>/`）：

```
src/plugins/your_plugin/
├── CMakeLists.txt          # 构建（VPP 用 CMake，旧版用 Makefile）
├── your_plugin.c           # 插件入口 + node 注册
├── your_plugin.h
├── node.c                  # 各 node 的 function 实现
├── cli.c                   # CLI 命令（可选）
├── api/                    # API 定义（.api 文件，codegen 生成桩）
└── test/                   # 单元测试 / 集成测试（可选）
```

最小插件只需一个 `.c` 文件：`your_plugin.c`。

## 3. 插件入口（注册到 VPP）

```c
#include <vlib/vlib.h>
#include <vnet/vnet.h>

/* 插件版本，必须导出，VPP 校验 ABI 兼容 */
VLIB_PLUGIN_REGISTER () = {
    .version = VPP_BUILD_VER,
    .description = "My custom VPP plugin",
};

/* 可选：插件初始化钩子（在所有 node 注册后、数据面启动前） */
static clib_error_t *
your_plugin_init (vlib_main_t * vm)
{
    /* 这里做一次性初始化：hash 表、计时器、注册 CLI/API 等 */
    return 0;
}
VLIB_INIT_FUNCTION (your_plugin_init);
```

- `VLIB_PLUGIN_REGISTER`：告知 VPP 这是一个插件（含版本）。
- `VLIB_INIT_FUNCTION`：注册一个初始化函数，返回 `clib_error_t *`，成功返回 0 / `0`。

## 4. 注册一个 Node

### INPUT / INTERNAL Node（数据面处理）

```c
/* node 处理函数：一次处理整批包（vector） */
static uword
your_node_fn (vlib_main_t * vm,
              vlib_node_runtime_t * node,
              vlib_frame_t * frame)
{
    u32 * from = vlib_frame_vector_args (frame);  /* 这批包的 buffer 索引 */
    uword n_left = frame->n_vectors;

    while (n_left > 0)
    {
        u32 bi = from[0];
        vlib_buffer_t * b = vlib_get_buffer (vm, bi);

        /* 读/改写包：b->data + b->current_data 指向 L2 头 */
        /* 例：打标记、改字段、做识别 */

        /* 决定下一跳 node：用 vlib_buffer_advance / 设置 next[0] */
        /* 这里直接交给默认 next */
        from++;
        n_left--;
    }
    return frame->n_vectors;
}

/* 注册节点 */
VLIB_REGISTER_NODE (your_node) = {
    .function = your_node_fn,
    .name = "your-node",
    .type = VLIB_NODE_TYPE_INTERNAL,
    .vector_size = sizeof (u32),
    .n_next_nodes = 1,
    .next_nodes = {
        [0] = "ethernet-output",   /* 默认下一跳 */
    },
};
```

要点：
- `frame->n_vectors` 是批大小；循环内逐包处理，但**函数只调用一次**——这就是向量化的收益点。
- `vlib_get_buffer(vm, bi)` 拿 buffer；`bi` 是索引不是指针。
- 想改变包走向：用一个 `nexts[...]` 数组给每个包指定 next-node 索引，最后 `vlib_put_next_frame`。
- 真实例子见 [[50-reference/NPP 定时器 机制|NPP]]：`flowtable_cleaner_node` 是一个 INTERNAL node，由 process node 触发。

### 把 Node 挂进数据面图

插件通常要把自己的 node 串到已有路径（否则没人调用）：
- 用 `vlib_node_add_next(vm, "ip4-input", "your-node")` 把你的 node 接到 `ip4-input` 之后。
- 或在注册时通过 `next_nodes` 指向已有节点名（VPP 启动时解析字符串 → 索引）。
- 也可替换默认邻接/feature：`vnet_feature_enable_disable("ip4-unicast", "your-node", sw_if_index, 1)` 把 node 作为 VNET feature 挂到某接口的 IPv4 单播路径上（更干净的方式，推荐）。

### PROCESS Node（协程 / 后台任务）

用于定时/事件驱动的"非数据面"逻辑（如流表老化，参见 NPP）：

```c
static uword
your_process_fn (vlib_main_t * vm,
                 vlib_node_runtime_t * rt,
                 vlib_frame_t * f)
{
    while (1)
    {
        /* 阻塞等待事件或超时（协作式，不占 CPU） */
        vlib_process_wait_for_event_or_clock (vm, 1.0 /*秒*/);
        /* ... 做清理/统计/下发 ... */
        /* 需要时给某 input/cleaner node 置 pending： */
        /* vlib_node_set_interrupt_pending(vm, cleaner_node_index); */
    }
    return 0;
}

VLIB_REGISTER_NODE (your_process) = {
    .function = your_process_fn,
    .type = VLIB_NODE_TYPE_PROCESS,
    .name = "your-process",
};
```

- `vlib_process_wait_for_event_or_clock` 是"暂停点"，让出 CPU。
- 唤醒方式：外部 `vlib_process_signal_event(vm, node_index, type, data)`。
- **禁止**在 process node 里做阻塞 syscall（如 `sleep`、等锁）、长时间循环——会卡死数据面。

## 5. 注册 CLI 命令

```c
static clib_error_t *
your_cli_set (vlib_main_t * vm,
              unformat_input_t * input,
              vlib_cli_command_t * cmd)
{
    u32 val = 0;
    if (!unformat (input, "%u", &val))
        return clib_error_return (0, "expect a number");
    your_config.val = val;
    return 0;
}

VLIB_CLI_COMMAND (your_cli_set_cmd) = {
    .path = "your set value",
    .short_help = "your set value <n>",
    .function = your_cli_set,
};
```

- 然后在 VPP CLI（`vppctl`）里即可输入 `your set value 42`。
- 查询类命令类似，把结果用 `vlib_cli_output(vm, "...", ...)` 输出。

## 6. API（二进制控制面）

需要程序化控制时，定义 `.api` 文件让 VPP codegen 生成桩：

```
# src/plugins/your_plugin/api/your_plugin.api
define your_plugin_set
{
  u32 client_index;
  u32 context;
  u32 value;
};
define your_plugin_set_reply
{
  u32 context;
  i32 retval;
};
```

构建后生成 C 头/源，插件里实现 handler 即可被外部（via shared-memory API）调用。适合与控制器对接。

## 7. 构建（CMake）

`CMakeLists.txt` 最小示例（VPP 已提供 `vpp_plugin` 宏）：

```cmake
add_vpp_plugin (your_plugin
  SOURCES
    your_plugin.c
    node.c
    cli.c
  API_FILES
    api/your_plugin.api
)
```

构建流程（在 VPP 源码树内）：

```bash
# 源码树方式（推荐，能拿到内部头）
cd vpp && make build            # 或 cmake 流程
# 产物：build-root/install-vpp-native/vpp/lib/vpp_plugins/your_plugin.so

# 单独开发可用 vpp_ext_repo（外部插件仓库）模式：
# 把插件放外部仓库，cmake 时指向 VPP 源码
```

> 外部插件（out-of-tree）用 `VPP_EXTERNAL_DEPEND` / `vpp_ext_repo` 模式，避免整树编译。具体见 VPP 文档 `docs/extending.md`。

## 8. 加载与调试

```bash
# 1) 把 .so 放到插件路径
sudo cp your_plugin.so /usr/lib/vpp_plugins/
# 2) startup.conf 启用
#    plugins { plugin your_plugin.so { enable } }
# 3) 启动并看加载情况
sudo vppctl "show plugins"        # 确认 your_plugin 在列表、无报错
sudo vppctl "show node"           # 确认 your-node / your-process 已注册
sudo vppctl "show runtime"        # 看节点调用计数、耗时
sudo vppctl "your set value 42"   # 触发你的 CLI

# 调试崩溃 / 加载失败
journalctl -u vpp -f
cat /tmp/vpp.log
# .so 依赖缺失：ldd your_plugin.so
# 符号未导出：nm -D your_plugin.so | grep your_plugin_register
```

### 常见问题

| 现象 | 原因 | 排查 |
|---|---|---|
| `show plugins` 不显示 | 未 `VLIB_PLUGIN_REGISTER` 或未被 enable | 查 `plugins { }` 配置、`.so` 路径 |
| 启动崩溃 | 版本/ABI 不符 | `VLIB_PLUGIN_REGISTER` 的 `.version` 要对齐 VPP 构建版本 |
| node 不跑 | 没挂进数据面图 | 用 `vnet_feature_enable_disable` 或 `vlib_node_add_next` 串接 |
| 数据面卡死 | process node 里阻塞/长循环 | 检查 `wait_for_event_or_clock` 是否正确让出 |

## 9. 与 NPP 的对应（实战参考）

本项目 [[50-reference/NPP 定时器 机制|NPP]] 是 VPP 插件范式的真实样例：

- `flowtable_clear_process`（PROCESS node）：`while(1){ wait_for_event_or_clock(1s); 若空闲 set_interrupt_pending(cleaner); }`。
- `flowtable_cleaner_node`（INTERNAL node）：被中断 pending 后执行实际流表清理。
- 通过外部 `flowtable_exapi_plugin.so` 用 `vlib_plugin_get_symbol` 式加载扩展函数（如 `del_handler` 会话删除回调），实现协议识别/falcon 引擎在会话老化时的解耦清理。

这套"PROCESS 定时 + INTERRUPT 触发 cleaner"的两级模型，是 VPP 插件里做周期后台任务的标准写法。

## 延伸

- [[20-protocols/VPP 2|VPP 知识]]、[[50-reference/VPP 用法|VPP 使用方法]]
- 源码/文档：`git clone https://github.com/FDio/vpp`，`docs/` 下的 `extending.md`、`node.rst`
