/*
 * retry.c — 指数退避重试（带抖动）演示，强调幂等
 *
 * 对应 [[entities/限流熔断实战]] §4、[[concepts/韧性设计]] §2、[[concepts/分布式系统基础]] §5。
 * 纯 C、无外部依赖。用模拟的“不稳定下游”演示重试直到成功。
 *
 * 编译：见 ../scripts/build.sh
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <time.h>

static double now_sec(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1e9;
}

/* 模拟一个不稳定的下游调用：前 fail_times 次失败，之后成功。
   真实场景里 fn 必须幂等（带 Idempotency-Key），见文档。 */
typedef struct { int remaining_failures; int call_count; } fake_downstream_t;

bool fake_call(fake_downstream_t *d) {
    d->call_count++;
    if (d->remaining_failures > 0) { d->remaining_failures--; return false; }
    return true;
}

/* 带幂等键的调用包装：同一 idempotency_key 重复调用只真正执行一次 */
typedef struct { const char *key; bool executed; bool result; } idempotency_t;

bool call_with_idempotency(idempotency_t *idm, fake_downstream_t *d) {
    if (idm->executed) {                      /* 已执行过：直接返回原结果 */
        printf("    [幂等] key=%s 去重，沿用结果\n", idm->key);
        return idm->result;
    }
    idm->executed = true;
    idm->result = fake_call(d);
    return idm->result;
}

/* 指数退避 + 抖动重试。fn 必须幂等。 */
bool call_with_retry(fake_downstream_t *d, int max_attempts, double base) {
    for (int i = 0; i < max_attempts; i++) {
        bool ok = fake_call(d);
        printf("  attempt %d: %s\n", i + 1, ok ? "OK" : "FAIL");
        if (ok) return true;
        if (i == max_attempts - 1) break;
        double sleep = base * (1 << i) + ((double)rand() / RAND_MAX) * base; /* 指数+抖动 */
        printf("    retry after %.3fs\n", sleep);
        struct timespec ts = { (time_t)sleep, (long)((sleep - (time_t)sleep) * 1e9) };
        nanosleep(&ts, NULL);
    }
    return false;
}

int main(void) {
    srand((unsigned)time(NULL));

    printf("=== 指数退避重试 (前3次失败, max_attempts=5) ===\n");
    fake_downstream_t d = { .remaining_failures = 3, .call_count = 0 };
    bool ok = call_with_retry(&d, 5, 0.1);
    printf("最终: %s (下游被调用 %d 次)\n\n", ok ? "成功" : "失败", d.call_count);

    printf("=== 幂等键去重演示 ===\n");
    idempotency_t idm = { .key = "req-123", .executed = false, .result = false };
    fake_downstream_t d2 = { .remaining_failures = 0, .call_count = 0 };
    call_with_idempotency(&idm, &d2);   /* 第一次真正执行 */
    call_with_idempotency(&idm, &d2);   /* 重复调用被去重 */
    printf("下游实际执行次数: %d (应为1)\n", d2.call_count);
    return 0;
}
