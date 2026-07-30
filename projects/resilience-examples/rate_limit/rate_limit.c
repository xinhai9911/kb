/*
 * rate_limit.c — 限流算法演示（令牌桶 + 滑动窗口）
 *
 * 对应 [[entities/限流熔断实战]] §1/§2、[[concepts/韧性设计]] §4。
 * 纯 C、无外部依赖，可直接编译运行。
 *
 * 编译：见 ../scripts/build.sh
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <time.h>

/* ---------- 令牌桶 ---------- */
typedef struct {
    double rate;        /* 每秒补充令牌数 */
    double capacity;    /* 桶容量（允许突发） */
    double tokens;      /* 当前令牌 */
    double last;        /* 上次补充时间（秒，monotonic） */
} token_bucket_t;

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1e9;
}

void tb_init(token_bucket_t *tb, double rate, double capacity) {
    tb->rate = rate; tb->capacity = capacity;
    tb->tokens = capacity; tb->last = now_sec();
}

bool tb_allow(token_bucket_t *tb, int n) {
    double t = now_sec();
    tb->tokens = tb->capacity < (tb->tokens + (t - tb->last) * tb->rate)
                    ? tb->capacity
                    : (tb->tokens + (t - tb->last) * tb->rate);
    tb->last = t;
    if (tb->tokens >= n) { tb->tokens -= n; return true; }
    return false;
}

/* ---------- 滑动窗口 ---------- */
typedef struct {
    int limit;          /* 窗口内最大请求数 */
    double window;      /* 窗口时长（秒） */
    double *hits;       /* 记录每次请求的时间 */
    int count;          /* 当前记录数 */
    int cap;            /* hits 数组容量 */
} sliding_window_t;

void sw_init(sliding_window_t *sw, int limit, double window) {
    sw->limit = limit; sw->window = window;
    sw->cap = limit > 0 ? limit * 2 : 16;
    sw->hits = malloc(sizeof(double) * sw->cap);
    sw->count = 0;
}

bool sw_allow(sliding_window_t *sw) {
    double t = now_sec();
    /* 丢弃窗口外的旧记录 */
    int i = 0, w = 0;
    for (i = 0; i < sw->count; i++) {
        if (sw->hits[i] > t - sw->window) sw->hits[w++] = sw->hits[i];
    }
    sw->count = w;
    if (sw->count < sw->limit) {
        if (sw->count == sw->cap) { /* 扩容 */
            sw->cap *= 2;
            sw->hits = realloc(sw->hits, sizeof(double) * sw->cap);
        }
        sw->hits[sw->count++] = t;
        return true;
    }
    return false;
}

void sw_free(sliding_window_t *sw) { free(sw->hits); }

int main(void) {
    /* 演示令牌桶：速率 5/s，容量 10（允许突发 10） */
    token_bucket_t tb; tb_init(&tb, 5.0, 10.0);
    printf("=== 令牌桶 (rate=5/s, capacity=10) ===\n");
    for (int i = 0; i < 15; i++) {
        bool ok = tb_allow(&tb, 1);
        printf("req %2d: %s (tokens=%.2f)\n", i, ok ? "ALLOW" : "DENY", tb.tokens);
        /* 不 sleep：前 10 突发放行，之后因补充慢而限流 */
    }

    /* 演示滑动窗口：窗口 1s 内最多 3 次 */
    sliding_window_t sw; sw_init(&sw, 3, 1.0);
    printf("\n=== 滑动窗口 (limit=3, window=1s) ===\n");
    for (int i = 0; i < 5; i++) {
        bool ok = sw_allow(&sw);
        printf("req %2d: %s\n", i, ok ? "ALLOW" : "DENY");
        struct timespec ts = {0, 150 * 1000000}; /* 150ms 间隔 */
        nanosleep(&ts, NULL);
    }
    sw_free(&sw);
    return 0;
}
