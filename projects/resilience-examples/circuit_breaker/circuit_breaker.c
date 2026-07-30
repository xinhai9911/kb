/*
 * circuit_breaker.c — 熔断三态（Closed/Open/Half-Open）演示
 *
 * 对应 [[entities/限流熔断实战]] §3、[[concepts/韧性设计]] §3。
 * 纯 C、无外部依赖。
 *
 * 编译：见 ../scripts/build.sh
 */
#include <stdio.h>
#include <stdbool.h>
#include <time.h>

typedef enum { CLOSED, OPEN, HALF_OPEN } cb_state_t;

typedef struct {
    double failure_threshold;  /* 失败率阈值 (0~1) */
    int window;                /* 滑动窗口大小 */
    int calls[64];             /* 1=成功 0=失败，环形缓冲 */
    int idx;                   /* 下一个写入位置 */
    int n;                     /* 当前窗口内样本数 */
    cb_state_t state;
    double opened_at;          /* 进入 OPEN 的时间 */
    double cooldown;           /* 冷却时长（秒） */
} circuit_breaker_t;

static double now_sec(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1e9;
}

void cb_init(circuit_breaker_t *cb, double ft, int window, double cooldown) {
    cb->failure_threshold = ft; cb->window = window; cb->cooldown = cooldown;
    cb->idx = 0; cb->n = 0; cb->state = CLOSED; cb->opened_at = 0;
}

/* 是否允许发起调用（OPEN 且冷却未到则拒绝） */
bool cb_allow(circuit_breaker_t *cb) {
    if (cb->state == OPEN) {
        if (now_sec() - cb->opened_at > cb->cooldown) {
            cb->state = HALF_OPEN;   /* 冷却到，放少量探活 */
            printf("  [breaker] OPEN -> HALF_OPEN (探测)\n");
            return true;
        }
        return false;               /* 直接拒绝，走降级 */
    }
    return true;
}

/* 记录一次调用结果，决定是否切换状态 */
void cb_record(circuit_breaker_t *cb, bool ok) {
    cb->calls[cb->idx] = ok ? 1 : 0;
    cb->idx = (cb->idx + 1) % 64;
    if (cb->n < cb->window) cb->n++;

    int fails = 0;
    for (int i = 0; i < cb->n; i++) if (cb->calls[i] == 0) fails++;

    if (cb->state == HALF_OPEN) {
        if (ok) { cb->state = CLOSED; printf("  [breaker] HALF_OPEN -> CLOSED (恢复)\n"); }
        else    { cb->state = OPEN; cb->opened_at = now_sec(); printf("  [breaker] HALF_OPEN -> OPEN (再熔断)\n"); }
        return;
    }
    double rate = (double)fails / cb->n;
    if (cb->n >= cb->window && rate >= cb->failure_threshold) {
        cb->state = OPEN; cb->opened_at = now_sec();
        printf("  [breaker] CLOSED -> OPEN (失败率 %.0f%%)\n", rate * 100);
    }
}

int main(void) {
    circuit_breaker_t cb; cb_init(&cb, 0.5, 10, 2.0); /* 失败率>=50% 熔断，冷却2s */
    printf("=== 熔断器 (阈值50%%, 窗口10, 冷却2s) ===\n");

    /* 阶段1：连续失败 -> 应熔断 */
    printf("-- 连续失败 --\n");
    for (int i = 0; i < 12; i++) {
        if (!cb_allow(&cb)) { printf("  req %2d: 被熔断拒绝(降级)\n", i); continue; }
        cb_record(&cb, false);
    }
    /* 阶段2：熔断期内请求应被拒 */
    printf("-- 熔断期内 -- (应全拒绝)\n");
    for (int i = 0; i < 3; i++) {
        if (!cb_allow(&cb)) printf("  req %2d: 被熔断拒绝(降级)\n", i);
        else cb_record(&cb, true);
    }
    /* 阶段3：sleep 过冷却 -> HALF_OPEN 探活，成功则恢复 */
    printf("-- 等待冷却 2.1s --\n");
    struct timespec ts = {2, 100 * 1000000}; nanosleep(&ts, NULL);
    printf("-- 冷却后探活 --\n");
    for (int i = 0; i < 3; i++) {
        if (!cb_allow(&cb)) { printf("  req %2d: 被熔断拒绝(降级)\n", i); continue; }
        cb_record(&cb, true);
    }
    return 0;
}
