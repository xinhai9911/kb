---
title: Nginx 模块开发实战
category: entities
tags: [nginx, module, plugin, handler, filter, upstream, load-balance, active]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    Nginx 插件（模块）从零开发实战：项目骨架 + config 编译、Handler 模块
    （content 阶段自定义输出）、Filter 模块（修改响应头/体）、
    Upstream 模块（自定义后端协议 + process_header 状态机）、
    负载均衡器模块（peer 选择回调）。含 gdb 调试、常见坑
    （merge 遗漏、shmtx 漏锁、NGX_AGAIN 误用、结构体版本不匹配）。
    配合 [[concepts/Nginx 框架内部实现]]（框架原理）与
    [[concepts/Nginx 架构与事件模型]]（运行视图）。
base_confidence: 0.8
lifecycle: draft
---

# Nginx 模块开发实战

> 原理看 [[concepts/Nginx 框架内部实现]]，运行模型看 [[concepts/Nginx 架构与事件模型]]。
> 本文是「动手写一个能编译、能加载、能跑」的 nginx 模块全过程。

目标：产出 4 类模块的可编译骨架——**Handler / Filter / Upstream / 负载均衡器**，并讲清构建、调试、踩坑。

## 0. 环境准备

```bash
# 需要 nginx 源码（与运行版本一致！），用其头文件与 ngx_module 链接约定
wget https://nginx.org/download/nginx-1.25.4.tar.gz
tar xzf nginx-1.25.4.tar.gz
# 编译参数记下（动态模块必须与 --with-compat 一致）
nginx -V        # 查看运行版编译参数

# 工作目录
mkdir -p ~/ngx-modules/hello && cd ~/ngx-modules/hello
```

> 版本/编译参数不匹配是动态模块崩溃的首要原因。生产建议把模块源码放进 nginx 源码树一起静态编译。

## 1. 通用骨架与编译（所有模块共用）

每个模块目录至少含：`ngx_http_xxx_module.c` + `config` 文件。

**config**（告诉 nginx build 系统如何编译本模块）：

```bash
# 静态模块用 ngx_module 变量；动态模块用 ngx_add_dynamic_module
ngx_module_type=HTTP
ngx_module_name=ngx_http_hello_module
ngx_module_srcs="$ngx_addon_dir/ngx_http_hello_module.c"
# 如需额外链接
# ngx_module_libs="-lfoo"
. auto/module          # 固定结尾
```

**编译（静态）**：

```bash
cd nginx-1.25.4
./configure --add-module=/abs/path/ngx-modules/hello \
            --with-compat            # 若后续要动态加载
make -j$(nproc)
objs/nginx -t                        # 用新二进制测试配置
```

**编译（动态 .so）**：

```bash
./configure --add-dynamic-module=/abs/path/ngx-modules/hello --with-compat
make
# 产物 objs/ngx_http_hello_module.so → 拷贝到 nginx modules 目录
# 运行时 nginx.conf: load_module modules/ngx_http_hello_module.so;
```

---

## 2. Handler 模块（content 阶段输出自定义内容）

最基础的「插件」：处理某个 location，直接输出响应。

```c
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

static ngx_int_t ngx_http_hello_handler(ngx_http_request_t *r);
static char *ngx_http_hello_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

static ngx_command_t ngx_http_hello_commands[] = {
    { ngx_string("hello"),
      NGX_HTTP_LOC_CONF | NGX_CONF_NOARGS,
      ngx_http_hello_set,                 // 在 location 写 "hello;" 即启用
      NGX_HTTP_LOC_CONF_OFFSET, 0, NULL },
    ngx_null_command
};

static ngx_http_module_t ngx_http_hello_module_ctx = {
    NULL, NULL, NULL, NULL, NULL, NULL,
    NULL,                                 // create_loc_conf
    NULL                                  // merge_loc_conf
};

ngx_module_t ngx_http_hello_module = {
    NGX_MODULE_V1,
    &ngx_http_hello_module_ctx,
    ngx_http_hello_commands,
    NGX_HTTP_MODULE,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NGX_MODULE_V1_PADDING
};

// location 指令回调：把自己挂到 content 阶段
static char *ngx_http_hello_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf) {
    ngx_http_core_loc_conf_t *clcf =
        ngx_http_conf_get_module_loc_conf(cf, ngx_http_core_module);
    clcf->handler = ngx_http_hello_handler;   // ★ 注册 content handler
    return NGX_CONF_OK;
}

static ngx_int_t ngx_http_hello_handler(ngx_http_request_t *r) {
    static const u_char body[] = "Hello from nginx module!\n";

    r->headers_out.status = NGX_HTTP_OK;
    r->headers_out.content_type.len  = sizeof("text/plain") - 1;
    r->headers_out.content_type.data = (u_char *) "text/plain";
    r->headers_out.content_length_n = sizeof(body) - 1;

    ngx_http_send_header(r);

    ngx_buf_t *b = ngx_pcalloc(r->pool, sizeof(ngx_buf_t));
    b->start = b->pos = (u_char *) body;
    b->end   = b->last = b->pos + sizeof(body) - 1;
    b->last_buf = (r == r->main) ? 1 : 0;     // 主请求最后一包

    ngx_chain_t out = { b, NULL };
    return ngx_http_output_filter(r, &out);
}
```

配置：

```nginx
location = /hello { hello; }
```

---

## 3. Filter 模块（修改响应头 / 体）

Filter 串在响应输出链上，可改写头、改写/替换 body。要点：注册到 `top_header_filter` / `top_body_filter`，并**调用链上下一个 filter**。

```c
static ngx_int_t ngx_http_xfilter_header_filter(ngx_http_request_t *r);
static ngx_int_t ngx_http_xfilter_body_filter(ngx_http_request_t *r, ngx_chain_t *in);
static ngx_int_t ngx_http_xfilter_postconfiguration(ngx_conf_t *cf);

static ngx_http_output_header_filter_pt  ngx_http_next_header_filter;
static ngx_http_output_body_filter_pt    ngx_http_next_body_filter;

static ngx_http_module_t ngx_http_xfilter_module_ctx = {
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    ngx_http_xfilter_postconfiguration     // ★ postconfiguration 挂 filter
};

ngx_module_t ngx_http_xfilter_module = {
    NGX_MODULE_V1, &ngx_http_xfilter_module_ctx, NULL,
    NGX_HTTP_MODULE, NULL,NULL,NULL,NULL,NULL,NULL,NULL, NGX_MODULE_V1_PADDING
};

static ngx_int_t ngx_http_xfilter_postconfiguration(ngx_conf_t *cf) {
    ngx_http_next_header_filter = ngx_http_top_header_filter;
    ngx_http_top_header_filter   = ngx_http_xfilter_header_filter;
    ngx_http_next_body_filter    = ngx_http_top_body_filter;
    ngx_http_top_body_filter     = ngx_http_xfilter_body_filter;
    return NGX_OK;
}

// 头过滤器：加一个自定义响应头
static ngx_int_t ngx_http_xfilter_header_filter(ngx_http_request_t *r) {
    ngx_table_elt_t *h = ngx_list_push(&r->headers_out.headers);
    if (h) {
        h->hash = 1;
        ngx_str_set(&h->key, "X-Powered-By");
        ngx_str_set(&h->value, "ngx-xfilter");
    }
    return ngx_http_next_header_filter(r);   // 务必继续链
}

// 体过滤器：示例只透传（可在此做替换/压缩/分块）
static ngx_int_t ngx_http_xfilter_body_filter(ngx_http_request_t *r, ngx_chain_t *in) {
    // 想改 body：遍历 in 链，对 ngx_buf_t 做替换后重组 chain
    return ngx_http_next_body_filter(r, in); // 务必继续链
}
```

> **易错点**：忘记 `return ngx_http_next_*_filter(r, ...)` 会导致响应直接断流、客户端收不到完整内容。

---

## 4. Upstream 模块（对接自定义后端协议）

以「向一个 TCP 后端发请求、解析其响应头」为例，核心是 `process_header` 状态机（见 [[concepts/Nginx 框架内部实现]] §9）。

```c
typedef struct {
    ngx_http_upstream_conf_t  upstream;
    ngx_str_t                 backend_uri;
} ngx_http_my_upstream_loc_conf_t;

static ngx_int_t ngx_http_my_up_handler(ngx_http_request_t *r);
static ngx_int_t ngx_http_my_up_create_request(ngx_http_request_t *r);
static ngx_int_t ngx_http_my_up_process_header(ngx_http_request_t *r);
static ngx_int_t ngx_http_my_up_merge_loc_conf(ngx_conf_t *cf, void *p, void *c);

// 1) content handler：建立 upstream 并启动状态机
static ngx_int_t ngx_http_my_up_handler(ngx_http_request_t *r) {
    ngx_http_my_upstream_loc_conf_t *lcf =
        ngx_http_get_module_loc_conf(r, ngx_http_my_up_module);
    ngx_http_upstream_t *u = ngx_http_upstream_create(r);
    if (u == NULL) return NGX_HTTP_INTERNAL_SERVER_ERROR;

    u->conf = &lcf->upstream;
    u->create_request = ngx_http_my_up_create_request;
    u->process_header = ngx_http_my_up_process_header;  // ★ 必须
    u->abort_request  = NULL;
    u->finalize_request = NULL;

    r->main->count++;                  // 异步引用 +1
    ngx_http_upstream_init(r);
    return NGX_DONE;                   // 交还，等后端
}

// 2) 构造发往后端的请求
static ngx_int_t ngx_http_my_up_create_request(ngx_http_request_t *r) {
    ngx_buf_t *b = ngx_create_temp_buf(r->pool, 64);
    b->last = ngx_sprintf(b->last, "GET %V\r\n", &r->uri);
    r->upstream->request_bufs = ngx_alloc_chain_link(r->pool);
    r->upstream->request_bufs->buf = b;
    r->upstream->request_bufs->next = NULL;
    return NGX_OK;
}

// 3) 解析后端响应头（最易写错）
static ngx_int_t ngx_http_my_up_process_header(ngx_http_request_t *r) {
    ngx_http_upstream_t *u = r->upstream;
    // 头未收全：移动 pos 等待更多数据
    if (u->buffer.last - u->buffer.pos < 4) return NGX_AGAIN;
    if (ngx_strncmp(u->buffer.pos, "OK", 2) == 0) {
        u->headers_in.status_n = 200;
        u->headers_in.content_length_n = 0;
        return NGX_OK;                // 头解析完成
    }
    u->headers_in.status_n = 502;
    return NGX_OK;
}

// 4) merge 配置（继承 upstream 默认项）
static ngx_int_t ngx_http_my_up_merge_loc_conf(ngx_conf_t *cf, void *p, void *c) {
    ngx_http_my_upstream_loc_conf_t *prev = p, *conf = c;
    ngx_conf_merge_str_value(conf->backend_uri, prev->backend_uri, "/");
    if (conf->upstream.upstream == NULL)
        conf->upstream.upstream = prev->upstream.upstream;
    return NGX_CONF_OK;
}
```

配置：

```nginx
location /myup {
    my_upstream;                 # 启用
    proxy_pass http://127.0.0.1:9000;   # 复用 upstream 寻址
}
```

---

## 5. 负载均衡器模块（peer 选择）

自定义 upstream 的选节点算法（替代 round-robin / ip_hash）。

```c
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

typedef struct {
    ngx_uint_t               current;   // 简单轮转游标
    ngx_http_upstream_rr_peers_t *peers;
} ngx_http_mylb_srv_conf_t;

static ngx_int_t ngx_http_mylb_init(ngx_conf_t *cf, ngx_http_upstream_srv_conf_t *us);
static ngx_int_t ngx_http_mylb_get_peer(ngx_peer_connection_t *pc, void *data);
static void      ngx_http_mylb_free_peer(ngx_peer_connection_t *pc, void *data, ngx_uint_t state);

// 在 init 里把自己的 peer 回调挂到 us->peer
static ngx_int_t ngx_http_mylb_init(ngx_conf_t *cf, ngx_http_upstream_srv_conf_t *us) {
    ngx_http_mylb_srv_conf_t *sc = us->srv_conf[ngx_http_mylb_module.ctx_index];
    sc->peers = us->peer.data;            // 复用 rr peers 列表
    us->peer.get  = ngx_http_mylb_get_peer;
    us->peer.free = ngx_http_mylb_free_peer;
    return NGX_OK;
}

// 选节点：这里演示「轮转」
static ngx_int_t ngx_http_mylb_get_peer(ngx_peer_connection_t *pc, void *data) {
    ngx_http_mylb_srv_conf_t *sc = data;
    ngx_http_upstream_rr_peer_t *peer = &sc->peers->peer[sc->current];
    sc->current = (sc->current + 1) % sc->peers->number;
    pc->sockaddr = peer->sockaddr;
    pc->socklen  = peer->socklen;
    pc->name     = &peer->name;
    return NGX_OK;
}

static void ngx_http_mylb_free_peer(ngx_peer_connection_t *pc, void *data, ngx_uint_t state) {
    // 失败计数 / 熔断可在此处理（state 含 NGX_PEER_FAILED 等）
}
```

配置：

```nginx
upstream backend {
    mylb;                          # 启用自定义负载均衡
    server 10.0.0.1:80;
    server 10.0.0.2:80;
}
```

---

## 6. 调试（gdb）

```bash
# 1) 单 worker + 前台运行，便于 attach
nginx -g 'daemon off; master_process off;' &
# 或 gdb 直接起
gdb --args objs/nginx -c /etc/nginx/nginx.conf -g 'daemon off;'

# 2) 在模块函数打断点
(gdb) break ngx_http_my_up_process_header
(gdb) continue

# 3) 看请求/配置
(gdb) p r->uri
(gdb) p *u->buffer.pos@16          # 看后端响应缓冲前 16 字节

# 4) 内存池 / 共享内存
(gdb) p *r->pool
```

常用排查清单：
- 启动即崩溃 → 多半 `ngx_module_t` 字段漏填 / 结构体版本不匹配 / 漏 `. auto/module`。
- 配置 reload 后行为异常 → `merge_loc_conf` 没把字段合进来（用了未初始化哨兵值）。
- 偶发数据错乱 → 共享内存操作漏 `ngx_shmtx_lock`（`[[concepts/Nginx 框架内部实现]]` §8）。
- 响应卡住 / 502 → `process_header` 返回值错（`NGX_AGAIN` vs `NGX_OK` 用反）。
- 客户端收不全 → filter 忘记继续调用 `ngx_http_next_*_filter`。

## 7. 常见坑速查

| 现象 | 根因 | 解决 |
|------|------|------|
| 编译报 `ngx_module_t` 缺字段 | 没用 `NGX_MODULE_V1` / padding | 用标准宏 |
| 配置指令不识别 | commands 掩码层级不符 | 检查 `NGX_HTTP_LOC_CONF` 等 |
| location 不生效 | handler 注册到错误阶段 | content 用 `clcf->handler` |
| 子级配置是垃圾值 | 漏写 merge | 实现 `merge_loc_conf` |
| 多 worker 计数不准 | 用了进程内全局变量 | 改共享内存 + slab + shmtx |
| 动态模块加载崩溃 | 与运行版编译参数不一致 | 加 `--with-compat`，版本对齐 |

## 8. 最小交付清单（Checklist）

- [ ] `config` 文件 + `. auto/module` 结尾
- [ ] `ngx_module_t` 完整（V1 + padding）
- [ ] 配置指令 commands 掩码 + set 回调
- [ ] 有层级配置的模块实现 merge
- [ ] handler/filter 在 `postconfiguration` 正确挂载
- [ ] filter 必须调用 next filter
- [ ] upstream 模块实现 `process_header`
- [ ] 共享状态用共享内存并加 `shmtx`
- [ ] `objs/nginx -t` 通过 + gdb 验证关键路径

## 参考来源

- [[concepts/Nginx 框架内部实现]]
- [[concepts/Nginx 架构与事件模型]]
- Emiller's Guide to Nginx Module Development (timetrap.github.io)
- Nginx 源码: `src/http/modules/`（官方 handler/filter/upstream 范例，最权威参考）
- nginx.org/en/docs/dev/development_guide.html
