---
title: Nginx 架构与事件模型
category: concepts
tags: [nginx, architecture, epoll, event-driven, master-worker, phases, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    Nginx 核心架构：Master/Worker 进程模型、惊群解决与 accept_mutex、
    事件驱动（epoll/kqueue/select/iocp）、
    请求处理 11 阶段（NGX_HTTP_POST_READ → ... → NGX_HTTP_LOG_PHASE）、
    内存池（ngx_pool_t）分配策略、共享内存与 slab 分配器、
    模块链与过滤器、upstream 机制与子请求（subrequest）。
    对比 Apache prefork/event MPM 和 C10K 问题。
base_confidence: 0.85
lifecycle: draft
---

# Nginx 架构与事件模型

> 前置 [[concepts/Linux 内核网络栈]]（epoll/accept/NET 事件），[[entities/Linux 性能诊断工具集]]（perf/ftrace 排查）。
> 本文从 Nginx 内部架构理解 "为什么 Nginx 快"。

## 1. Master / Worker 模型

```
Master Process (root)
  │
  ├── Worker 0 (nobody)     ← epoll_wait → 处理连接
  ├── Worker 1 (nobody)     ← epoll_wait → 处理连接
  ├── Worker 2 (nobody)     ← epoll_wait → 处理连接
  ├── ...
  ├── Cache Manager         ← 管理缓存 LRU/LFU
  └── Cache Loader          ← 启动时加载缓存元数据
```

| 进程 | 责任 | 用户 | 特点 |
|------|------|------|------|
| **Master** | 配置重载、平滑升级、信号管理、Worker 管理 | root | 单线程、非阻塞信号驱动 |
| **Worker** | 处理所有 HTTP 连接和请求 | nobody/www-data | 单线程事件循环、无锁设计 |
| **Cache Manager** | 管理缓存文件（过期/淘汰） | nobody | 定期扫描缓存元数据 |
| **Cache Loader** | 加载缓存索引到共享内存 | nobody | 启动时一次 |

**无锁设计**：每个 Worker 是单线程 + 事件驱动，不需要锁（except accept_mutex）
**CPU 亲和**：`worker_cpu_affinity` 每个 Worker 绑定专属核

```nginx
worker_processes auto;                     # 等于 CPU 核数
worker_cpu_affinity auto;                  # 自动绑定
worker_priority -5;                        # 比普通进程稍高优先级（nice -5）
```

## 2. 事件驱动模型

### 2.1 事件循环

```
Worker 主循环：
while (1) {
    events = epoll_wait(epfd, events, max_events, timeout);
    for (i = 0; i < events; i++) {
        if (events[i].data.fd == listening_socket) {
            accept() → ngx_http_init_connection(conn);
        } else {
            handler = events[i].data.ptr→handler;
            handler(events[i]);  // read/write/timer
        }
    }
    // 处理定时器（超时关闭、keepalive、延迟）
    ngx_event_expire_timers();
}
```

### 2.2 事件驱动对比

| 服务器 | I/O 模型 | 连接/进程 | 适用场景 |
|--------|---------|----------|---------|
| **Nginx** | epoll (事件驱动) | 单进程 10K-100K+ | 反向代理、静态、TLS |
| **Apache prefork** | select (每请求一进程) | 约 256 | 兼容性（.htaccess） |
| **Apache event** | epoll + 线程池 | 几千 | 传统 LAMP |
| **Node.js** | libuv (事件驱动) | 单进程 10K+ | I/O 密集型应用 |
| **HAProxy** | epoll (事件驱动) | 单进程 100K+ | TCP/HTTP L4-L7 代理 |

### 2.3 Accept 惊群与 mutex

```nginx
# 惊群问题：多个 Worker 同时 accept() 只有一个成功
# Nginx 解决：accept_mutex 轮流 accept

accept_mutex on;              # 默认 on
accept_mutex_delay 500ms;     # 等不到时的退让时间

# 多队列网卡场景：SO_REUSEPORT（Linux 3.9+）
# 内核直接将连接分发到不同的 socket
# 彻底解决惊群 + 更均匀的负载均衡
listen 80 reuseport;

# reuseport 模式下每个 Worker 独立 listen socket
# 每个 socket 绑定在不同 CPU 上（配合 worker_cpu_affinity）
# 连接分布由内核哈希决定（均匀性佳）
```

## 3. 请求处理的 11 阶段

```
Client Request
  │
  ├── NGX_HTTP_POST_READ         # 读请求头（最前，可做请求头改写）
  ├── NGX_HTTP_SERVER_REWRITE    # server 级别 rewrite（if/return/set）
  ├── NGX_HTTP_FIND_CONFIG       # location 匹配（不可编辑）
  ├── NGX_HTTP_REWRITE           # location 级别 rewrite
  ├── NGX_HTTP_POST_REWRITE      # rewrite 后重定向（不可编辑）
  │
  ├── NGX_HTTP_PREACCESS         # 访问前（limit_conn/limit_req）
  ├── NGX_HTTP_ACCESS            # 访问控制（allow/deny/auth_basic/auth_jwt）
  ├── NGX_HTTP_POST_ACCESS       # access 后处理（不可编辑，return 403 等）
  │
  ├── NGX_HTTP_PRECONTENT        # 内容前（try_files/mirror）
  ├── NGX_HTTP_CONTENT           # 内容生成（proxy_pass/fastcgi_pass/static）
  └── NGX_HTTP_LOG               # 日志记录（access_log）
```

**数据面视角**：每个阶段可以注入 handler（模块），阶段按顺序不可跳过。
**反向代理路径**：`POST_READ → ... → FIND_CONFIG → CONTENT(proxy_pass) → 响应回来 → LOG`

## 4. 内存池（ngx_pool_t）

```c
// Nginx 内部使用内存池分配——减少 malloc/free 碎片和系统调用
// 每个连接创建一个池，连接关闭时一次性释放

// 结构：
// ngx_pool_t → ngx_pool_large_t (大块 > 4KB)
//            → ngx_pool_small_t (小块，链表)
//            → 一次性释放全部，无内存泄漏风险

// 碎片控制：请求处理完整池释放 → 无内存碎片积累
// 相比 Apache 每请求 malloc/free：Nginx 节省约 5-10% CPU 时间

// 配置中不直接暴露，理解即可：
// 反向代理场景：大响应体 → 大块通过 ngx_pool_large 分配
// 正常请求：~4KB 池足够
```

## 5. Upstream 机制与子请求

```
Client (请求)
  │
  └── Nginx Worker
        │  proxy_pass http://backend
        │
        ├── Upstream 连接池（keepalive）
        ├── 创建子请求（subrequest — 内部重定向）
        ├── 写入请求体（buffered/streaming）
        ├── 读取响应体（buffered/streaming）
        │
        └── 响应回客户端（可能再缓冲）
```

```
子请求场景：
  ├── SSI (Server Side Include): 主请求 + 多个子请求嵌入片段
  ├── auth_request: 主请求 → /internal/auth (子请求验证)
  └── mirror: 主请求 ↔ 镜像到另一后端（同时返回）
```

## 6. 模块链与过滤器

```
请求进入 → handler 模块（如 proxy_pass）→ 响应生成
                                         ↓
                                    Filter 链（响应体处理）：
                                    ├── ngx_http_chunked_filter     # 分块传输
                                    ├── ngx_http_gzip_filter        # 压缩
                                    ├── ngx_http_ssi_filter         # SSI 替换
                                    ├── ngx_http_sub_filter         # 内容替换
                                    └── ngx_http_header_filter      # 写响应头
                                         → ngx_http_write_filter    # 写响应体
```

**过滤器顺序可控**（`output_filters`）：模块可插入不同位置

## 7. 共享内存与 Slab

```nginx
# 共享内存：多个 Worker 进程间通信的唯一方式
# 通过 mmap MAP_SHARED 或 System V shm 实现

# 用途：
# - HTTP cache（proxy_cache_path 的 keys_zone）
# - 限流（limit_req_zone / limit_conn_zone）
# - SSL session cache
# - 连接跟踪（sticky）

# 例子：cache 共享内存
proxy_cache_path /data/nginx/cache levels=1:2 keys_zone=mycache:10m;
# keys_zone=mycache:10m → 10MB 共享内存存缓存元数据
# Nginx slab 内部管理这 10MB 的分配/释放

# 查看 slab 使用（生产环境）
curl http://nginx-status/nginx_status  # 需 stub_status 模块
# Active connections: 256
# server accepts handled requests
#  12345 12345 54321
# Reading: 0 Writing: 5 Waiting: 251

# 共享内存满 → 分配失败 → 直接报错（502/500）
# 合理设置 keys_zone 大小是关键调优点
```

## 8. 对比 Apache 的 C10K 优势

```
C10K 问题在不同架构下的表现：

Apache (prefork MPM):
- 500 并发 → 500 进程 → 500 × 8MB = 4GB
- 上下文切换：500 进程争抢 CPU
- select() 每次扫描所有 fd
- 瓶颈出现在 ~5000 连接

Nginx (事件驱动):
- 50000 并发 → 几 Worker × 1 epoll
- 无锁事件处理（简单请求）
- epoll O(1) 返回就绪事件
- 瓶颈在 CPU/带宽而非连接数
```

## 参考来源

- [[concepts/Linux 内核网络栈]]
- [[entities/Nginx 反向代理实战]]
- Nginx 官方文档: ngx_core_module / event / http
- Nginx Internals (nginx.org/en/docs/dev/development_guide.html)
- Apache MPM documentation (prefork/worker/event)
- C10K problem: kegel.com/c10k.html
