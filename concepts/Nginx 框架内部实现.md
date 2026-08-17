---
title: Nginx 框架内部实现
category: concepts
tags: [nginx, module, ngx_module_t, config-merge, phase, upstream, slab, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    Nginx 框架核心实现：ngx_module_t 模块三元组（ctx/commands/type）与模块生命周期
    （init_module → init_process → 各阶段 handler）、配置指令解析与多级合并
    （create_srv_conf/create_loc_conf + merge）、11 阶段handler 注册机制、
    内存池 ngx_pool_t 与 slab 分配器、共享内存、upstream 内部状态机
    （connect→send→process_header→input_filter）与 subrequest 协作。
    配合 [[concepts/Nginx 架构与事件模型]]（进程/事件视图）与
    [[entities/Nginx 模块开发实战]]（动手写模块）。
base_confidence: 0.82
lifecycle: draft
---

# Nginx 框架内部实现

> 前置 [[concepts/Nginx 架构与事件模型]]（Master/Worker、epoll、11 阶段总览）。
> 动手见 [[entities/Nginx 模块开发实战]]。
> 本文从「框架如何把模块组织起来」理解 Nginx 的可扩展性——这是开发插件（模块）的地基。

Nginx 的扩展性来自一个**高度规约化的模块框架**：所有功能（哪怕是 `ngx_http_core` 本身）都实现为模块，框架负责加载、配置解析、阶段调度、内存与共享状态管理。理解框架 = 理解「模块能挂在哪、能做什么、配置怎么来」。

## 1. 模块的三元组：ngx_module_t

每个模块都必须定义一个 `ngx_module_t` 结构体，它是模块对框架的「自述书」：

```c
ngx_module_t  ngx_http_xxx_module = {
    NGX_MODULE_V1,                 // 版本/签名 (0,0,0,0,0,0,1)
    &ngx_http_xxx_module_ctx,      // ctx:   模块上下文（生命周期钩子 + 配置类型）
    ngx_http_xxx_commands,         // commands: 该模块能解析哪些配置指令
    NGX_HTTP_MODULE,               // type:  CORE / HTTP / EVENT / MAIL
    NULL,                          // init_master
    NULL,                          // init_module（所有 worker 之前，master 内）
    NULL,                          // init_process（每个 worker 启动时）
    NULL,                          // init_thread
    NULL,                          // exit_thread
    NULL,                          // exit_process
    NULL,                          // exit_master
    NGX_MODULE_V1_PADDING
};
```

| 字段 | 含义 | 插件常用度 |
|------|------|-----------|
| `ctx` | 模块上下文。HTTP 模块是 `ngx_http_module_t`（含 create_main/srv/loc_conf、pre/postconfiguration 钩子） | ★★★ |
| `commands` | `ngx_command_t[]`，声明「配置里能写什么」 | ★★★ |
| `type` | 决定模块被哪个核心子系统加载（HTTP 模块必须 `NGX_HTTP_MODULE`） | ★★★ |
| `init_module` | 配置解析完成后、fork worker 前（master 进程内） | ★ |
| `init_process` | 每个 worker 启动后调用一次，常用于初始化 per-worker 状态、注册定时器 | ★★ |
| `exit_process` | worker 退出清理 | ★ |

> 关键认知：**模块不是「被调用」的，而是向框架「注册能力」**。框架在启动流程中按顺序回调各模块的钩子。

## 2. 模块加载与启动流程

```
nginx 启动 (master)
  │
  ├─ 1. 加载所有 ngx_module_t（静态链入或动态 SO 通过 --add-dynamic-module）
  ├─ 2. 调用各模块 ctx->create_main_conf / create_srv_conf / create_loc_conf
  │      （为每个配置作用域分配配置结构体）
  ├─ 3. 逐行解析 nginx.conf：
  │      └─ 每遇到一条指令，查 commands 表 → 调用其 set() 回调写入配置
  ├─ 4. 调用各模块 ctx->init_main_conf + merge_srv_conf + merge_loc_conf
  │      （把上层配置向下合并，见 §4）
  ├─ 5. 调用各模块 ctx->postconfiguration
  │      （★关键：HTTP 模块在此把自己挂到 11 阶段 handler 链 / filter 链）
  ├─ 6. init_module 钩子
  ├─ 7. fork() → 每个 worker:
  │      ├─ init_process 钩子
  │      └─ 进入事件循环 epoll_wait（见 [[concepts/Nginx 架构与事件模型]] §2）
  └─ 8. 收到信号 → reload/upgrade
```

`postconfiguration` 是大多数 HTTP 功能模块的「挂载点」：

```c
static ngx_int_t ngx_http_xxx_postconfiguration(ngx_conf_t *cf) {
    ngx_http_core_main_conf_t *cmcf =
        ngx_http_conf_get_module_main_conf(cf, ngx_http_core_module);
    // 把本模块的 handler 挂到某个阶段（例如 ACCESS 阶段）
    h = ngx_array_push(&cmcf->phases[NGX_HTTP_ACCESS_PHASE].handlers);
    *h = ngx_http_xxx_access_handler;
    return NGX_OK;
}
```

## 3. 配置指令：ngx_command_t

`commands` 数组声明模块「认得」的每条指令，框架据此把配置文本写进你的结构体：

```c
static ngx_command_t ngx_http_xxx_commands[] = {
    { ngx_string("xxx_enable"),
      NGX_HTTP_MAIN_CONF | NGX_HTTP_SRV_CONF | NGX_HTTP_LOC_CONF | NGX_CONF_FLAG,
      ngx_conf_set_flag_slot,            // 内置 set 回调：直接解析 on/off
      NGX_HTTP_LOC_CONF_OFFSET,          // 写入 loc_conf
      offsetof(ngx_http_xxx_loc_conf_t, enable),  // 字段偏移
      NULL },

    { ngx_string("xxx_param"),
      NGX_HTTP_LOC_CONF | NGX_CONF_TAKE1,
      ngx_http_xxx_set_param,            // 自定义 set 回调（复杂解析）
      NGX_HTTP_LOC_CONF_OFFSET,
      offsetof(ngx_http_xxx_loc_conf_t, param),
      NULL },

      ngx_null_command
};
```

| 元素 | 作用 |
|------|------|
| 指令名 | 配置里写的名字 |
| 配置层级掩码 | 允许出现在 main / server / location（决定 `create_*_conf` 用哪个） |
| `NGX_CONF_TAKE1` 等 | 参数个数校验（TAKE1/TAKE2/TAKE12/ANY/1MORE） |
| set 回调 | `ngx_conf_set_*` 系列内置解析器，或自定义函数 |
| OFFSET 宏 | 告诉框架把值写到哪个 conf 结构体的哪个字段 |

**自定义 set 回调**用于非标量（如解析上游名字、正则、复杂列表）：

```c
static char *ngx_http_xxx_set_param(ngx_conf_t *cf, ngx_command_t *cmd, void *conf) {
    ngx_http_xxx_loc_conf_t *lcf = conf;
    ngx_str_t *value = cf->args->elts;          // value[0]=指令名, value[1]=参数
    lcf->param = value[1];
    return NGX_CONF_OK;                          // 出错返回 NGX_CONF_ERROR
}
```

## 4. 配置合并：为什么需要 merge

Nginx 配置是**层级继承**的（main → server → location）。上层没写的值，要从上层继承；写了的覆盖。`create_*_conf` 分配结构体后，框架用 `merge_srv_conf` / `merge_loc_conf` 把父级值「补」到子级：

```c
static char *ngx_http_xxx_merge_loc_conf(ngx_conf_t *cf, void *parent, void *child) {
    ngx_http_xxx_loc_conf_t *prev = parent;
    ngx_http_xxx_loc_conf_t *conf = child;

    ngx_conf_merge_value(conf->enable, prev->enable, 0);   // 默认 off
    ngx_conf_merge_str_value(conf->param,  prev->param,  "");
    ngx_conf_merge_uint_value(conf->timeout, prev->timeout, 3000);

    if (conf->param.data == NULL) {     // 继承后仍为空 → 报错或给默认值
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "xxx_param is required");
        return NGX_CONF_ERROR;
    }
    return NGX_CONF_OK;
}
```

`ngx_conf_merge_*_value` 宏语义：**child 若未设置（unset 哨兵值），则取 parent 的值，否则保留 child**。这正是 `location` 里没写 `xxx_enable` 却自动继承 `server` 级别配置的实现原理。这是插件开发最常见的「坑」来源——忘记 merge 会导致子级配置是未初始化哨兵值。

## 5. 11 阶段 handler 的挂载与执行

回顾 [[concepts/Nginx 架构与事件模型]] §3 的 11 阶段。框架在 `cmcf->phases[]` 为每个阶段维护一个 handler 数组（`ngx_array_t` of `ngx_http_handler_pt`）。请求处理时 `ngx_http_core_run_phases` 依次遍历阶段、调用 handler：

```c
// 阶段遍历核心（简化）
for (ph = cmcf->phase_engine.handlers; ; ph++) {
    rc = ph->handler(r);            // 调用模块 handler
    if (rc == NGX_AGAIN) continue; // 交还控制权，等事件再回来
    if (rc >= NGX_OK)   break;     // 进入下一阶段
    // rc == NGX_DECLINED 表示该阶段此 handler 不处理，继续同阶段下一个
}
```

handler 返回值语义（务必记牢）：

| 返回值 | 含义 |
|--------|------|
| `NGX_OK` / 具体状态码 | 阶段结束，按 rc 继续（如 `NGX_HTTP_FORBIDDEN` 直接响应） |
| `NGX_DECLINED` | 本 handler 不处理，交给同阶段下一个 handler |
| `NGX_AGAIN` | 异步等待（如需要读后端/定时器），事件就绪后重入 |
| `NGX_DONE` | 已自行安排后续（常见于 content handler 自管输出） |

`NGX_DECLINED` vs `NGX_AGAIN` 是新手最常混淆的：前者是「我不负责」，后者是「我负责但要等」。

## 6. 内存池 ngx_pool_t

请求级分配全部走内存池，避免频繁 `malloc/free` 与碎片（见 [[concepts/Nginx 架构与事件模型]] §4）：

```c
// 连接建立时：ngx_create_pool(size, log)  —— 通常 4KB 块
// 请求进入时：r->pool 复用连接池或新建子池
void *p = ngx_palloc(r->pool, n);             // 对齐分配，小块
void *p = ngx_pcalloc(r->pool, n);            // 清零
void *p = ngx_pnalloc(r->pool, n);            // 不对齐（存字符串更省）

// 大块（> pool 块阈值）走 ngx_pool_large_t 链表，仍随池一起释放
// 连接/请求结束：ngx_destroy_pool → 一次性回收全部，无泄漏
```

**划重点**：模块里**几乎不要用裸 `malloc`**。用 `ngx_palloc(r->pool, ...)`，连接断开自动回收。需要跨请求存活的状态用共享内存（§8），不要存模块全局裸指针（worker 间不共享）。

清理钩子（需要在释放前做事，如关闭 fd）：

```c
ngx_pool_cleanup_t *c = ngx_pool_cleanup_add(r->pool, 0);
c->handler = ngx_http_xxx_cleanup;   // 池销毁前调用
c->data    = ctx;
```

## 7. 请求与响应结构体（handler/filter 的操作用户）

```c
ngx_http_request_t *r;
r->main;                 // 主请求（区分 subrequest）
r->connection;           // 连接（含 fd、读/写事件）
r->headers_in;           // 客户端请求头（ngx_list_t）
r->headers_out;          // 响应头（status / content_length / headers）
r->args;                 // URI 查询串
r->method;               // NGX_HTTP_GET / POST ...
r->phase_handler;        // 当前阶段游标（框架内部推进）
```

`headers_out` 典型设置（`content handler` 出口）：

```c
r->headers_out.status = NGX_HTTP_OK;
r->headers_out.content_type.len  = sizeof("text/plain") - 1;
r->headers_out.content_type.data = (u_char *) "text/plain";
r->headers_out.content_length_n = body_len;
ngx_http_send_header(r);                 // 发响应头
return ngx_http_output_filter(r, &out);  // 发响应体（走 filter 链）
```

## 8. 共享内存与 slab 分配器

多 worker 共享状态（限流计数、缓存索引、sticky 表）必须放共享内存。模块通过 `ngx_shared_memory_add` 注册一段 zone，框架 `mmap MAP_SHARED`：

```c
shm = ngx_shared_memory_add(cf, &name, size, &ngx_http_xxx_module);
shm->init = ngx_http_xxx_shm_init;        // worker 启动时初始化（每个 worker 都调）
```

zone 内部用 **slab 分配器**管理（红黑树 + slab 页），按 8/16/32... 分级，避免碎片：

```c
// 在 init 回调里建红黑树 / 队列挂在 shm->data
ngx_slab_pool_t *shpool = (ngx_slab_pool_t *) shm->shm.addr;
ngx_shmtx_lock(&shpool->mutex);           // ★ 共享内存操作必须加锁（shmtx）
void *p = ngx_slab_alloc(shpool, sz);     // 从 zone 内分配
ngx_shmtx_unlock(&shpool->mutex);
```

> 为什么要 `shmtx`？多 worker 并发访问同一 zone。Nginx 用 **spinlock + 原子** 实现无系统调用的轻量锁（`ngx_shmtx_lock`/`unlock`）。漏加锁 = 偶发数据损坏，极难排查。

## 9. Upstream 内部状态机（对接后端的核心）

`proxy_pass` 等本质是把请求转给 upstream 子系统。模块要实现一套回调，框架用状态机驱动：

```
ngx_http_upstream_t 状态流转：
  CREATE_REQUEST   → 构造发往后端的请求体
  CONNECT          → 建连（用 keepalive 池 / 新建）
  SEND_REQUEST     → 发送
  PROCESS_HEADER   → 解析后端响应头（★必须实现）
  PROCESS_BODY     → input_filter 逐块收响应体
  FINALIZE         → 结束，交给 content 阶段输出
```

模块最小实现（自定义协议 upstream）：

```c
static ngx_int_t ngx_http_xxx_handler(ngx_http_request_t *r) {
    ngx_http_upstream_t *u = ngx_http_upstream_create(r);
    u->conf = &lcf->upstream;                 // 复用 upstream 配置
    u->create_request  = ngx_http_xxx_create_request;
    u->process_header  = ngx_http_xxx_process_header;  // 解析后端响应头
    u->input_filter    = ngx_http_xxx_input_filter;
    r->main->count++;                         // 引用计数 +1（异步）
    ngx_http_upstream_init(r);               // 启动状态机
    return NGX_DONE;                          // 交还控制权，等后端
}
```

`process_header` 是**最易写错**的环节：必须正确设置 `u->headers_in.status_n`、`u->buffer` 的 `pos/last`，并返回 `NGX_AGAIN`（头未收全）或 `NGX_OK`（头解析完）。返回错值会导致连接卡死或 502。

## 10. Subrequest 协作

auth_request、mirror、SSI 都基于 subrequest：主请求内部派生「子请求」访问另一 location/后端，互不阻塞主流程：

```c
ngx_http_post_subrequest_t ps = { ngx_http_xxx_subreq_done, NULL };
ngx_http_subrequest(r, &uri, &args, &sr, &ps, NGX_HTTP_SUBREQUEST_IN_MEMORY);
// 子请求完成后回调 ps.handler，通过 r->main->count 控制主请求何时结束
```

子请求的响应默认**不输出到客户端**，只供主请求逻辑使用（如 auth_request 拿 200/401 决定放行）。

## 11. 动态模块（SO 插件）

不重新编译 nginx 主干也能加模块（1.9.11+ 的 `--add-dynamic-module`，编译出 `.so`）：

```nginx
# nginx.conf
load_module modules/ngx_http_xxx_module.so;
```

动态模块的限制：必须与目标 nginx 版本、编译参数（如 `--with-compat`）严格匹配，否则 `symbol version` 或结构体布局不一致导致崩溃。生产环境优先静态编译；动态模块适合第三方快速迭代。

## 12. 与其他数据面框架对照

| 维度 | Nginx 模块 | [[20-protocols/VPP 2|VPP 插件]] | eBPF |
|------|-----------|-------------------------------|------|
| 挂载点 | 11 阶段 / filter 链 | Graph node | 内核挂载点 |
| 生命周期 | init_module/process | node init/verify | load/attach |
| 状态共享 | 共享内存 + slab + shmtx | 共享内存向量 | BPF Map |
| 并发模型 | per-worker 事件循环 | 矢量批处理 + 核亲和 | 单 CPU 上下文 |

## 参考来源

- [[concepts/Nginx 架构与事件模型]]
- [[entities/Nginx 模块开发实战]]
- [[concepts/Linux 内核网络栈]]（epoll/accept 事件）
- Nginx 开发指南: nginx.org/en/docs/dev/development_guide.html
- 《Nginx 模块开发完全指南》 / Emiller's Guide to Nginx Module Development
- Nginx 源码: `src/core/ngx_module.c`, `src/http/ngx_http.c`, `src/http/ngx_http_upstream.c`
