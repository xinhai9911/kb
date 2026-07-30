# Nginx 模块开发示例工程（nginx-module-examples）

本目录是 [[entities/Nginx 模块开发实战]] 中四类的**可编译**代码骨架，配套
[[concepts/Nginx 框架内部实现]] 的原理说明。

每个子目录是一个独立 nginx 模块（含 `.c` + `config`）：

| 目录 | 类型 | 功能 |
|------|------|------|
| `hello/` | Handler | location 写 `hello;` 返回自定义文本（content 阶段） |
| `xfilter/` | Filter | 给响应加 `X-Powered-By: ngx-xfilter` 头 |
| `myupstream/` | Upstream | content 阶段转给 TCP 后端，自定义 `process_header` |
| `mylb/` | 负载均衡器 | upstream 写 `mylb;` 启用自定义轮转选节点（per-request `peer.init` → `get`/`free`） |

## 目录结构

```
nginx-module-examples/
├── hello/        ngx_http_hello_module.c   + config
├── xfilter/      ngx_http_xfilter_module.c + config
├── myupstream/   ngx_http_myupstream_module.c + config
├── mylb/         ngx_http_mylb_module.c    + config
├── scripts/build.sh
├── nginx.conf                              # 最小启动配置（一键 -c 起）
└── README.md
```

## 编译

```bash
cd Q:/AI/kb/projects/nginx-module-examples
bash scripts/build.sh                 # 自动下载 nginx-1.25.4 并编出动态 .so
# 或指定已有源码
NGINX_SRC=/opt/nginx-1.25.4 bash scripts/build.sh
# 静态编进二进制
bash scripts/build.sh --static
```

产物（动态模式）：`build/modules/ngx_http_{hello,xfilter,myupstream,mylb}_module.so`

> 版本 / 编译参数必须匹配运行中的 nginx（动态模块务必加 `--with-compat`），否则加载崩溃。
> 见 [[entities/Nginx 模块开发实战]] §0、§7。

### 编译状态

- 代码对照 nginx 1.25.x 公共 API 编写（`ngx_http_upstream_srv_conf_t`、
  `ngx_http_upstream_server_t`、`ngx_peer_connection_t` 等），并修正了负载均衡器模块
  的挂接方式（`us->peer.init` 设 per-request init，在 init 内把 `get`/`free` 挂到
  `r->upstream->peer`）。
- **本目录在 Windows/Git-Bash 环境无法实际编译**（无 C 工具链与 nginx 源码）。
  在 Linux 上执行 `bash scripts/build.sh` 即可产出 `.so`。如构建报错，对照
  [[entities/Nginx 模块开发实战]] §7 排错。

## 运行配置示例

```nginx
# nginx.conf 顶部加载动态模块
load_module modules/ngx_http_hello_module.so;
load_module modules/ngx_http_xfilter_module.so;
load_module modules/ngx_http_myupstream_module.so;
load_module modules/ngx_http_mylb_module.so;

http {
    # 负载均衡器：在 upstream 启用
    upstream backend {
        mylb;
        server 127.0.0.1:9001;
        server 127.0.0.1:9002;
    }

    server {
        listen 80;

        location = /hello { hello; }              # Handler 模块

        location / {
            proxy_pass http://backend;            # 受 xfilter 影响（加响应头）
        }

        location /myup {
            myupstream;                           # Upstream 模块
            proxy_pass http://127.0.0.1:9000;     # 后端地址（演示用）
        }
    }
}
```

验证：

```bash
# 用新二进制测试
build/nginx -t -c /path/nginx.conf      # 动态模式用系统 nginx -t
# 请求
curl -i http://127.0.0.1/hello
curl -i http://127.0.0.1/                # 应看到 X-Powered-By: ngx-xfilter
```

## 一键启动（nginx.conf）

工程根目录已含最小 `nginx.conf`，四个模块全部接线：

```bash
cd Q:/AI/kb/projects/nginx-module-examples

# 动态模块（系统 nginx 已带 --with-compat）：以当前目录为 prefix 启动
nginx -p $PWD -c nginx.conf
# 或静态二进制：
./build/nginx -p $PWD -c nginx.conf
```

启动后验证：

```bash
curl -i http://127.0.0.1:8080/hello          # hello 模块
curl -i http://127.0.0.1:8080/               # 走 backend，xfilter 加响应头
curl -i http://127.0.0.1:8080/myup          # myupstream 模块（需后端首行 "OK"）

# 模拟后端（myupstream 判定 200 的条件是首行 "OK"）：
#   while true; do printf 'OK\n' | nc -l -p 9000; done
# 模拟 backend 上游（看 mylb 轮转）：在 9001/9002 起两个回显服务
```

> 注：nginx 的 `load_module` / `proxy_pass` 等需要对应内置模块（http、http_proxy）。
> 若用 `build.sh` 静态编译默认已包含；系统 nginx 通常也包含。

## 调试

见 [[entities/Nginx 模块开发实战]] §6（gdb 单 worker 前台 + 断点）。

## 排错速查

| 现象 | 根因 | 解决 |
|------|------|------|
| 编译报 `ngx_module_t` 缺字段 | 没用 `NGX_MODULE_V1`/padding | 用标准宏 |
| 配置指令不识别 | commands 掩码层级不符 | 检查 `NGX_HTTP_LOC_CONF` 等 |
| location 不生效 | handler 注册到错误阶段 | content 用 `clcf->handler` |
| 子级配置是垃圾值 | 漏 merge | 实现 `merge_loc_conf` |
| 响应卡住/502 | `process_header` 返回值错 | 区分 `NGX_AGAIN` / `NGX_OK` |
| 动态模块加载崩溃 | 版本/参数不一致 | 加 `--with-compat`，版本对齐 |

## 参考

- [[entities/Nginx 模块开发实战]]
- [[concepts/Nginx 框架内部实现]]
- [[concepts/Nginx 架构与事件模型]]
- Nginx 官方模块范例：nginx 源码 `src/http/modules/`
