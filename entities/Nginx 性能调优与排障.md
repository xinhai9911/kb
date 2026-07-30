---
title: Nginx 性能调优与排障
category: entities
tags: [nginx, performance, tuning, troubleshooting, sysctl, connection-pooling, monitoring, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    Nginx 数据面级性能调优与生产排障速查。Worker 与内核参数
    （worker_connections/sendfile/tcp_nopush/epoll）、
    Linux 内核优化（net.core.somaxconn/tcp_fastopen/backlog）、
    SSL 性能（session cache/hardware offload/async）、
    Upstream 连接池调优（keepalive/connection pooling）、
    HTTP/2 多路复用与 h2 陷阱、大文件/流媒体场景优化、
    OpenResty Lua 扩展性能注意、监控（stub_status/Prometheus exporter）、
    常见问题排障（502/499/upstream timed out/too many open files/
    worker_connections 不足/共享内存满/缓存碎片）。
    附带生产参考配置模板。
base_confidence: 0.85
lifecycle: draft
---

# Nginx 性能调优与排障

> 前置 [[concepts/Nginx 架构与事件模型]]（事件模型/共享内存），[[entities/Nginx 反向代理实战]]（配置基础）。
> 本文从数据面视角看待 Nginx——把它当作 L7 数据面节点来调优。

## 1. Worker 全面调优

```nginx
worker_processes auto;                   # = CPU 核数（或 N-1 留 1 给系统）
worker_cpu_affinity auto;                # 自动绑核
worker_priority -10;                     # 优先级（nice -10）
worker_rlimit_nofile 65535;              # worker 最大文件描述符数（需系统 ulimit -n）

events {
    worker_connections 65535;            # 每 worker 最大连接数（> rlimit_nofile 时以 rlimit_nofile 为准）
    use epoll;                           # Linux 明确指定 epoll（默认也是）
    multi_accept on;                     # 一次 accept 全部连接（减少 epoll 循环次数）
    accept_mutex off;                    # reuseport 时关掉（无惊群）
}
```

### 1.1 参数详解

```nginx
# sendfile — 零拷贝发送文件（静态文件代理必开）
sendfile on;
sendfile_max_chunk 1m;    # 单次 sendfile 最多发 1MB（防长时间占 CPU）

# tcp_nopush — 积累到完整包再发（减少小包数量）
tcp_nopush on;

# tcp_nodelay — 立即发送（Nagle 算法关掉，对延迟敏感场景重要）
tcp_nodelay on;

# 连接池
keepalive_requests 10000;   # 单连接允许多少请求（默认 100，代理场景调大）
keepalive_timeout 65s;      # 客户端 keepalive 超时
```

## 2. Linux 内核参数

```bash
# /etc/sysctl.conf 或 /etc/sysctl.d/99-nginx.conf

# ===== 连接队列 =====
net.core.somaxconn = 65535           # listen 队列最大长度（Nginx listen backlog）
net.ipv4.tcp_max_syn_backlog = 65535 # SYN 队列长度
net.core.netdev_max_backlog = 100000 # 网卡 backlog

# ===== TIME_WAIT 复用 =====
net.ipv4.tcp_tw_reuse = 1            # 客户端连接重用 TIME_WAIT（出站连接）
net.ipv4.tcp_fin_timeout = 15        # FIN-WAIT-2 超时

# ===== TCP Fast Open =====
net.ipv4.tcp_fastopen = 3            # 启用 TFO（客户端 + 服务端）
# 配合 Nginx：listen 443 ssl http2 fastopen=256;
# TFO 在 TLS 场景节省 1 RTT（从 3 次握手中减掉 data 前的等待）

# ===== 文件句柄 =====
fs.file-max = 10000000               # 系统级文件句柄上限
# ulimit -n 65535 (需在 systemd service 或 /etc/security/limits.conf 中设置)

# ===== TIME-WAIT 连接数控制 =====
net.ipv4.tcp_max_tw_buckets = 2000000 # TIME_WAIT 总数上限

# ===== 端口范围（作为客户端代理时）=====
net.ipv4.ip_local_port_range = 1024 65535
```

## 3. SSL 性能专项

```bash
# ===== 1. Session Cache + Session Tickets =====
ssl_session_cache shared:SSL:50m;    # 50MB ≈ 40 万 session
ssl_session_timeout 4h;              # 缓存 4 小时
# TLS 1.3 0-RTT 需要 session ticket（建议关掉 ticket 用 cache）
ssl_session_tickets off;

# ===== 2. 硬件加速（QAT / 内建 AES 指令）=====
# Intel QAT (Quick Assist Technology)：SSL 卸载卡
# 配置方式：模块 ngx_ssl_engine
ssl_engine qat_engine;

# 无硬件时：CPU AES-NI 已够
# openssl speed -evp aes-128-gcm   # 看 CPU 吞吐

# ===== 3. SSL 连接性能 =====
# 单核 ~5000-10000 完整 TLS 握手/秒（Xeon Gold）
# 50% 请求复用 session → 降到 2000-5000 新握手/秒
# 调优目标：尽量复用 session（减少握手）

# ===== 4. OCSP Stapling（必须开）=====
# 否则客户端自己请求 OCSP 服务器 → 额外 1 RTT + 连接延迟
```

```nginx
# async 模式（OpenSSL 3.0+）：SSL 操作异步化
# 避免 SSL 操作阻塞事件循环
ssl_conf_command Options KTLS;
ssl_conf_command Options Async;
```

## 4. Upstream 连接池

```nginx
upstream backend {
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;

    # ===== keepalive 连接池 =====
    keepalive 256;                  # 每个 worker 保持 256 条空闲连接
    keepalive_requests 10000;       # 单连接最大请求数（默认 100，太小导致频繁拆建）
    keepalive_timeout 60s;          # 空闲超时
    # 效果：
    # 缓存前：每请求 → TCP 连接 3 次握手 + HTTP 请求 + 4 次挥手
    # 缓存后：无握手开销，省 ~2ms + CPU
    # 注意：keepalive 数 × worker 数 × 后端数 = 总连接数

    # ===== 排队 =====
    queue 100 timeout=30s;          # Nginx Plus 功能
}

# proxy_http_version 1.1（必须，keepalive 需要 HTTP/1.1）
location / {
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_pass http://backend;
}
```

## 5. HTTP/2 多路复用

```nginx
server {
    listen 443 ssl http2;
    # http2 复用同一条连接上的多个请求
    # 头压缩（HPACK）减少重复头开销

    # 调优参数：
    http2_max_concurrent_streams 128;   # 同连接最大并发流（默认 128）
    http2_chunk_size 4k;                 # 响应的分块大小
    http2_idle_timeout 3m;               # 空闲连接超时
    http2_max_requests 1000;              # 单连接请求数

    # 常见问题：
    # - HTTP/2 + proxy_pass 会导致 stream 排队（头线阻塞）
    #   → 多 upstream + least_conn 缓解
    # - gRPC 必须 HTTP/2（但 gRPC 本身多路复用效率高）
}
```

## 6. 监控

```nginx
# ===== stub_status（基础）=====
location /nginx_status {
    stub_status on;
    access_log off;
    allow 10.0.0.0/8;
    deny all;
}
# 输出：
# Active connections: 256
# server accepts handled requests
#   12345 12345 54321
# Reading: 0 Writing: 5 Waiting: 251

# ===== Prometheus Exporter =====
# 安装 nginx-prometheus-exporter
# 配置：/usr/local/bin/nginx-prometheus-exporter \
#   -nginx.scrape-uri http://localhost:8080/nginx_status

# ===== 日志分析（实时 QPS）=====
tail -F /var/log/nginx/access.log | pv -l -r | awk '{print $7}' | sort | uniq -c | sort -rn
```

## 7. 常见问题排障

### 7.1 502 Bad Gateway

```bash
# 上游不可达
curl -v http://10.0.0.1:8080/health  # 直接检查上游

# 上游连接数满（connection refused）
ss -s | grep estab                    # 看当前连接数
netstat -s | grep "connection refused"

# upstream timed out（110: Connection timed out）
# 解决：proxy_read_timeout 调大或上游太慢
tail -f /var/log/nginx/error.log | grep "upstream timed out"
```

### 7.2 499 Client Closed Connection

```nginx
# 客户端提前关闭（不等上游响应）
# 常见原因：
# 1. 浏览器超时（proxy_read_timeout > 客户端超时）
# 2. 客户端取消请求（用户刷新/关闭页面）
# 3. 负载均衡器健康检查（短连接）

# 解决方向：
proxy_read_timeout 300s;      # 给上游足够时间
proxy_ignore_client_abort on; # 忽略客户端断开（慎用，上游可能一直跑无用任务）
```

### 7.3 too many open files

```bash
# Nginx error.log:
# 2024/01/01 12:00:00 [crit] 1234#0: *5678 open() "/path" failed (24: Too many open files)

# 排查：
lsof -p <nginx_worker_pid> | wc -l     # 当前 fd 数
cat /proc/<nginx_master_pid>/limits     # 当前限制

# 解决链：
# 1. worker_rlimit_nofile 65535;
# 2. /etc/security/limits.conf: nginx soft nofile 65535
# 3. /etc/systemd/system/nginx.service: LimitNOFILE=65535
# 4. fs.file-max = 10000000 in sysctl

# 根因：epoll fd 用完了或 TIME_WAIT 太多
# `ss -s` 看 TIME_WAIT，调整 tw_reuse
```

### 7.4 Worker 连接数满

```nginx
# nginx_status 中 Reading+Writing 接近 worker_connections
# 解决：
events {
    worker_connections 65535;   # 调大
}

# 但也要检查：
# - keepalive_timeout 太长 → 堆积空闲连接
# - upstream 响应太慢 → 连接长时间占用
# - HTTP/2 stream 过多
```

### 7.5 共享内存满

```nginx
# 错误：ngx_slab_alloc() failed: no memory
# 排查：
# - keys_zone 设置过小（proxy_cache_path 的 keys_zone）
# - limit_req_zone 太小
# - SSL session cache 太小

# 解决：调大 keys_zone/zone 大小
# 查看 slab 使用（需修改 Nginx 源码编译 debug 模式）
```

## 8. 生产参考配置模板

```nginx
user nginx;
worker_processes auto;
worker_cpu_affinity auto;
worker_priority -10;
worker_rlimit_nofile 65535;

error_log /var/log/nginx/error.log crit;
pid /run/nginx.pid;

events {
    worker_connections 65535;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # 基础优化
    sendfile on;
    sendfile_max_chunk 1m;
    tcp_nopush on;
    tcp_nodelay on;
    server_tokens off;

    # 连接池
    keepalive_requests 10000;
    keepalive_timeout 65s;

    # 代理缓冲
    proxy_buffers 8 8k;
    proxy_buffer_size 4k;
    proxy_busy_buffers_size 16k;

    # 上游超时
    proxy_connect_timeout 5s;
    proxy_send_timeout 10s;
    proxy_read_timeout 30s;

    # 限流（全局）
    limit_req_zone $binary_remote_addr zone=global:10m rate=1000r/s;

    # 日志
    access_log /var/log/nginx/access.log combined buffer=32k flush=5s;

    # Gzip（代理场景关掉——上游压缩好再发）
    gzip off;

    include /etc/nginx/conf.d/*.conf;
}
```

## 参考来源

- [[concepts/Nginx 架构与事件模型]]
- [[entities/Nginx 反向代理实战]]
- [[entities/Linux 性能诊断工具集]]
- Nginx 官方性能调优文档 (nginx.org/en/docs/performance.html)
- Linux kernel 网络调优: Documentation/networking/ip-sysctl.txt
- nginx-prometheus-exporter: github.com/nginxinc/nginx-prometheus-exporter
- Nginx + SSL perf: istlsfastyet.com
