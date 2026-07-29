---
title: Nginx 反向代理实战
category: entities
tags: [nginx, proxy, load-balancing, upstream, ssl, cache, configuration, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
    Nginx 反向代理完整配置实战。upstream 定义与五种负载均衡算法
    （轮询/least_conn/ip_hash/random/hash）、健康检查（被动/主动）、
    proxy_pass 包头改写（Host/X-Forwarded-*）、缓冲机制与关闭缓冲的场景、
    SSL/TLS 终止优化（session cache/OCSP stapling/HSTS）、
    proxy_cache 层级存储与缓存锁、限流（limit_req/limit_conn）、
    动态 upstream（API + DNS resolver）、WebSocket/gRPC 代理、
    OpenResty Lua 扩展。
    每种配置附带说明和常见陷阱。
base_confidence: 0.85
lifecycle: draft
---

# Nginx 反向代理实战

> 前置 [[concepts/Nginx 架构与事件模型]]（进程模型/事件驱动/阶段）。
> 本文配置片段均可直接使用——每段都标注了关键参数的意义和踩坑点。

## 1. 基础 Upstream 与 proxy_pass

```nginx
upstream backend {
    # 默认算法：加权轮询（weighted round-robin）
    server 10.0.0.1:8080 weight=5;
    server 10.0.0.2:8080 weight=3;
    server 10.0.0.3:8080 weight=1 backup;    # 备用
    server 10.0.0.4:8080 down;                # 手动下线

    keepalive 32;   # 每个 worker 保持的空闲长连接数
    keepalive_requests 1000;  # 每条连接最大请求数
    keepalive_timeout 60s;    # 连接空闲超时
}

server {
    listen 80;
    location / {
        proxy_pass http://backend;

        # 关键：不写 URI → 传递完整 URL
        # proxy_pass http://backend;          保留原路径
        # proxy_pass http://backend/;         截断 location 匹配部分

        # http://example.com/api/v1/users → backend/api/v1/users
        # http://example.com/api/v1/users → backend/v1/users（加了 /）
    }
}
```

### 1.1 常见陷阱

```
proxy_pass http://backend;      ← 带 URI？（不加）
proxy_pass http://backend/;     ← 带 URI/（截前缀）
proxy_pass http://backend/v2/;  ← 带 URI/v2/（替换前缀）

location /api/ {
    proxy_pass http://backend;  → 转发 /api/users → backend/api/users
}
location /api/ {
    proxy_pass http://backend/; → 转发 /api/users → backend/users（截掉了 /api）
}
location /api/ {
    proxy_pass http://backend/new-api/; → 转发 /api/users → backend/new-api/users
}
```

## 2. 负载均衡算法

| 算法 | 指令 | 特点 | 适用场景 |
|------|------|------|---------|
| **轮询** (默认) | `least_conn` 替代 | 按权重循环 | 同配置后端 |
| **最小连接** | `least_conn` | 发到当前连接最少的后端 | 请求处理时间不均 |
| **IP Hash** | `ip_hash` | 同源 IP → 同后端（session 保持） | 无共享 session 但有粘性需求 |
| **Hash** | `hash $request_uri` | 任意 key 哈希 | 缓存亲和（一致性哈希） |
| **Random** | `random two least_conn` | 随机选 2 个再挑最少连接 | 大集群均匀分布 |

```nginx
# IP Hash（不要和 proxy_next_upstream 混用，ip_hash 失败时无法换后端）
upstream backend_ip {
    ip_hash;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}

# 一致性哈希（适合缓存层：相同请求必定打到同一后端）
upstream backend_hash {
    hash $request_uri consistent;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}

# Random Two Choices（大集群最优）
upstream backend_random {
    random two least_conn;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080;
    server 10.0.0.4:8080;
}
```

## 3. 健康检查

```nginx
# Nginx 内置被动检查（默认，无需额外模块）
# 请求失败后标记 "不可用" 一定时间
upstream backend {
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    # max_fails=3: 连续 3 次失败
    # fail_timeout=30s: 30s 内不再转发
}

# Nginx Plus 主动健康检查（商业版）
# 或使用 nginx_upstream_check_module（淘宝 tengine 开源）
# health_check interval=5s fails=3 passes=2 uri=/health
```

**被动检查的缺陷**：只有请求失败才知道后端挂了，失败请求会被 502 返回给客户端。

```nginx
# 补救：给上游加一层缓冲
proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
proxy_next_upstream_tries 2;         # 最多尝试 2 个后端
proxy_next_upstream_timeout 5s;       # 总超时 5s
```

## 4. 请求头改写

```nginx
location / {
    proxy_set_header Host $host;                       # 原始 Host
    proxy_set_header X-Real-IP $remote_addr;           # 客户端真实 IP
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;  # 链式
    proxy_set_header X-Forwarded-Proto $scheme;        # http/https
    proxy_set_header X-Request-ID $request_id;          # 追踪 ID

    # 不转发客户端 Accept-Encoding（不压缩上游传输）
    proxy_set_header Accept-Encoding "";

    # 移除某些头（防止上游被欺骗）
    proxy_pass_request_headers on;    # 默认 on
    proxy_pass_request_body on;       # 默认 on
}

# 如果上游需要 HTTPS 但 Nginx 是 HTTP：
proxy_set_header X-Forwarded-Proto https;
proxy_set_header X-Forwarded-Port 443;
```

## 5. 缓冲机制

```nginx
location / {
    # ===== 缓冲（默认开） =====
    proxy_buffering on;
    proxy_buffers 8 8k;              # 8 个 8KB=64KB 缓冲
    proxy_busy_buffers_size 16k;     # 忙缓冲（发给客户端的先读）
    proxy_buffer_size 4k;            # 响应头缓冲区
    proxy_max_temp_file_size 1024m;  # 临时文件上限

    # ===== 何时关缓冲？ =====
    # 1. Server-Sent Events (SSE) — 实时推送
    # 2. WebSocket — 双向实时
    # 3. 流媒体 — 客户端需要立刻开始播放
    # 4. 大文件下载 — 不需要 nginx 全缓冲
}
```

```nginx
# SSE 示例（关缓冲）
location /events {
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
    proxy_pass http://backend;
}

# 大文件下载（关缓冲 + 零拷贝）
location /download/ {
    proxy_buffering off;
    proxy_request_buffering off;    # 不缓冲请求体
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_pass http://backend;
}
```

## 6. SSL/TLS 终止优化

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    # ===== 证书链 =====
    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # ===== 协议与密码套件 =====
    ssl_protocols TLSv1.2 TLSv1.3;    # 关掉 TLSv1.0/1.1
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;

    # ===== Session 复用（重要！减少 TLS 握手）=====
    ssl_session_cache shared:SSL:10m;   # 10MB 共享内存存 session
    ssl_session_timeout 10m;            # session 有效期
    ssl_session_tickets off;            # 建议关掉（安全原因）

    # ===== OCSP Stapling =====
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 1.1.1.1 valid=300s;
    resolver_timeout 5s;

    # ===== HSTS =====
    add_header Strict-Transport-Security "max-age=63072000" always;

    # ===== 性能：session cache 效果 =====
    # 首次 TLS 握手：1-RTT (~30ms)
    # 复用 session：0-RTT (TLS 1.3) / 1-RTT (TLS 1.2)
    # 10MB 共享内存 ≈ 40000-80000 个 session
}
```

## 7. 缓存

```nginx
# ===== 定义缓存 =====
proxy_cache_path /data/nginx/cache levels=1:2 keys_zone=static:100m
    max_size=10g inactive=7d use_temp_path=off;

# levels=1:2    → 目录散列 /data/nginx/cache/c/29/xxxxxc29
# keys_zone     → 共享内存 100MB（存缓存 key）
# max_size      → 磁盘缓存最大 10GB
# inactive      → 7 天无访问自动淘汰
# use_temp_path → 关掉临时路径（减少磁盘 IO）

server {
    location /static/ {
        proxy_cache static;                    # 引用 zone
        proxy_cache_key "$scheme$host$request_uri";
        proxy_cache_valid 200 302 60m;          # 成功响应缓存 1h
        proxy_cache_valid 404 1m;              # 404 缓存 1min
        proxy_cache_use_stale error timeout updating;  # 上游挂了也用旧缓存
        proxy_cache_background_update on;       # 后台异步更新
        proxy_cache_lock on;                    # 缓存锁（防惊群）
        proxy_cache_lock_timeout 5s;

        add_header X-Cache-Status $upstream_cache_status;
        # $upstream_cache_status: HIT/MISS/BYPASS/STALE/UPDATING

        proxy_pass http://backend;
    }
}
```

### 7.1 缓存微调

```nginx
# 按请求参数区分缓存（同 URL 不同参数）
proxy_cache_key "$scheme$host$request_uri";

# 禁用缓存（特定 cookie）
location / {
    proxy_no_cache $cookie_sessionid;
    proxy_cache_bypass $cookie_sessionid;
}

# 带宽与 IO 平衡
proxy_cache_min_uses 2;       # 至少 2 次请求才缓存（防冷数据占磁盘）
proxy_cache_max_size 10g;
proxy_cache_path ... loader_files=1000 loader_sleep=50ms;
# Cache Loader 进程每秒扫描 1000 个文件，间隔 50ms
```

## 8. 限流

```nginx
# ===== 限制请求率 =====
limit_req_zone $binary_remote_addr zone=login:10m rate=10r/s;
server {
    location /login/ {
        limit_req zone=login burst=20 nodelay;
        # burst=20: 突发 20 个排队
        # nodelay: 不延迟，超出立即返回 503
        proxy_pass http://backend;
    }
}

# ===== 限制并发连接 =====
limit_conn_zone $binary_remote_addr zone=addr:10m;
server {
    location /download/ {
        limit_conn addr 10;       # 单 IP 最多 10 并发
        limit_conn_status 429;    # 返回 429 Too Many Requests
        proxy_pass http://backend;
    }
}

# ===== 限制带宽 =====
location /download/ {
    proxy_set_header X-Accel-Buffering no;
    limit_rate 500k;             # 单连接 500KB/s
    limit_rate_after 1m;         # 前 1MB 不限速
    proxy_pass http://backend;
}
```

## 9. WebSocket 代理

```nginx
location /ws/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;

    # WebSocket 长连接超时
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;

    # 关缓冲（WebSocket 必须是流式）
    proxy_buffering off;
}
```

## 10. gRPC 代理

```nginx
server {
    listen 443 ssl http2;
    location / {
        grpc_pass grpc://backend;
        # 或加密：grpc_pass grpcs://backend;

        grpc_set_header Host $host;
        grpc_read_timeout 1800s;
        grpc_send_timeout 1800s;

        # 健康检查（grpc 健康协议）
        health_check type=grpc;
    }
}

# upstream 需指定 http2（gRPC 要求）
upstream backend {
    server 10.0.0.1:50051;
    server 10.0.0.2:50051;
}
```

## 11. DNS 动态解析

```nginx
# 变量 upstream（运行时 DNS 解析）
location / {
    resolver 10.0.0.53 valid=30s;         # 每 30s 重新 DNS 查询
    resolver_timeout 5s;

    set $backend http://service.consul:8080;
    proxy_pass $backend;                   # 变量方式 → 运行时 DNS
}
```

## 12. 日志格式

```nginx
# 代理日志（包含上游信息）
log_format proxy '$remote_addr - $remote_user [$time_local] '
                 '"$request" $status $body_bytes_sent '
                 '"$http_referer" "$http_user_agent" '
                 'upstream=$upstream_addr '
                 'upstream_status=$upstream_status '
                 'upstream_response_time=$upstream_response_time '
                 'request_time=$request_time '
                 'cache_status=$upstream_cache_status';

access_log /var/log/nginx/proxy_access.log proxy buffer=32k flush=5s;
# buffer=32k → 32KB 批量写磁盘（减少 IOPS）
# flush=5s  → 5s 内强制刷（避免丢日志）
```

## 参考来源

- [[concepts/Nginx 架构与事件模型]]
- Nginx 官方文档: ngx_http_upstream_module / ngx_http_proxy_module
- Nginx Plus Admin Guide
- OpenResty 最佳实践 (moonbingbing.gitbooks.io)
- Let's Encrypt / certbot OCSP stapling docs
