---
project: true
topic: 限流/熔断/重试
stack: C
deps: gcc（零依赖）
run: "`bash scripts/build.sh`"
docs: "限流熔断实战 / 韧性设计"
updated: 2026-07-30
---

# 限流熔断示例工程（resilience-examples）

本目录是 [[entities/限流熔断实战]] 中算法的**可编译** C 实现，配套
[[concepts/韧性设计]]。纯 C、零依赖，聚焦算法本身，便于读懂与改造。

| 目录 | 示例 | 对应文档 |
|------|------|---------|
| `rate_limit/` | 令牌桶 + 滑动窗口限流 | [[entities/限流熔断实战]] §1/§2、[[concepts/韧性设计]] §4 |
| `circuit_breaker/` | 熔断三态（Closed/Open/Half-Open） | [[entities/限流熔断实战]] §3、[[concepts/韧性设计]] §3 |
| `retry/` | 指数退避重试（带抖动）+ 幂等去重 | [[entities/限流熔断实战]] §4、[[concepts/分布式系统基础]] §5 |

## 目录结构

```
resilience-examples/
├── rate_limit/rate_limit.c
├── circuit_breaker/circuit_breaker.c
├── retry/retry.c
├── scripts/build.sh
└── README.md
```

## 依赖

- C 编译器（gcc / clang），POSIX 时钟（`clock_gettime`/`nanosleep`）。
- **无** TLS/网络/第三方库依赖——算法逻辑纯净可移植。

> [!info] 编译环境
> Linux / macOS 直接编译；Windows 需用 WSL（本工程面向 POSIX）。

## 编译

```bash
cd Q:/AI/kb/projects/resilience-examples
bash scripts/build.sh            # 全部 → ./build/
bash scripts/build.sh retry     # 单项
```

## 运行与预期输出

```bash
cd build

# 1) 限流：令牌桶前 10 次突发放行，之后被限流；滑动窗口 1s 内最多 3 次
./rate_limit

# 2) 熔断：连续失败触发 OPEN；冷却后 HALF_OPEN 探活成功恢复
./circuit_breaker

# 3) 重试：指数退避（前3次失败最终成功）；幂等键去重演示
./retry
```

预期：
- `rate_limit`：令牌桶 `req 0..9 ALLOW`、之后 `DENY`；滑动窗口前 3 次 `ALLOW`、其余 `DENY`。
- `circuit_breaker`：失败率到 50% 打印 `CLOSED -> OPEN`；冷却 2s 后 `OPEN -> HALF_OPEN`，探活成功 `HALF_OPEN -> CLOSED`。
- `retry`：attempt 1–3 FAIL 并 sleep 退避，attempt 4 OK；幂等演示下游只执行 1 次。

## 与生产结合

- 算法是内核，生产要接：指标上报（限流/熔断次数 → [[concepts/可观测性工程]]）、
  网关层限流（Nginx `limit_req`，见 [[entities/Nginx 反向代理实战]]）、
  库（resilience4j / Sentinel / Envoy）。详见 [[entities/限流熔断实战]] §5/§7。

## 排错

| 现象 | 原因 | 解决 |
|------|------|------|
| `clock_gettime` 未声明 | 老 glibc 需 `_POSIX_C_SOURCE` | 编译加 `-D_POSIX_C_SOURCE=199309L` |
| Windows 编译失败 | 用 WSL/MinGW | 本工程面向 POSIX |

## 参考

- [[entities/限流熔断实战]]
- [[concepts/韧性设计]]
- [[concepts/分布式系统基础]]
- [[concepts/可观测性工程]]
