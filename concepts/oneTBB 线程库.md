---
title: oneTBB 线程并行库
category: concepts
tags: [onetbb, intel, tbb, threading, parallel, task-scheduler, performance, active]
created: 2026-09-07
updated: 2026-09-07
summary: >-
    oneTBB（oneAPI Threading Building Blocks，原 Intel TBB）是 C++ 模板并行库，
    提供 work-stealing 任务调度、parallel_for/reduce、并发容器与流图，是 oneDNN/oneMKL
    的并行后端之一，用于把计算均匀铺到多核。
base_confidence: 0.85
lifecycle: draft
---

# oneTBB 线程并行库

> 前置 [[concepts/oneDNN 深度学习性能库]]（并行后端之一）、[[concepts/CPU 微架构内部]]（多核/执行端口）、
> [[concepts/CPU 体系架构]]（NUMA 与亲和）。

## 1. 是什么

- **定位**：C++ **任务并行**库（非裸线程），用模板与算法描述并行，调度器负责映射到线程。
- **历史**：Intel **TBB**（2006，开源）→ 改名 **oneTBB**（oneAPI 体系），Apache 2.0。
- **对比 OpenMP**：TBB 是**基于任务的**泛型库（更灵活、可组合流图）；OpenMP 是指令式 pragma（更轻量、直接）。

## 2. 核心抽象

| 组件 | 说明 |
|------|------|
| **Task Scheduler** | work-stealing 线程池，每个线程一个 deque，空闲时偷取他人任务 |
| **parallel_for / parallel_reduce** | 循环并行与归约 |
| **parallel_pipeline** | 流水线阶段并行（生产者-消费者） |
| **Flow Graph** | 节点 + 边构成依赖图，支持异步/函数/continue 节点 |
| **并发容器** | `concurrent_vector` / `concurrent_queue` / `concurrent_hash_map` / `concurrent_priority_queue` |
| **可扩展分配器** | `scalable_allocator` / `cache_aligned_allocator`（降低锁与伪共享） |

```cpp
#include <oneapi/tbb/parallel_for.h>
#include <oneapi/tbb/blocked_range.h>
using namespace oneapi::tbb;

// 将数组逐元素加 1，自动按核切分
parallel_for(blocked_range<size_t>(0, n), [&](auto r) {
    for (size_t i = r.begin(); i < r.end(); ++i) a[i] += 1;
});

// 归约：并行求和
double s = parallel_reduce(blocked_range<size_t>(0, n), 0.0,
    [](auto r, double init) {            // 每个分块局部求和
        for (size_t i = r.begin(); i < r.end(); ++i) init += a[i];
        return init;
    },
    [](double x, double y) { return x + y; });  // 合并局部结果
```

## 3. 与 oneDNN / oneMKL 关系

- oneDNN 的并行后端可在 **OpenMP** 与 **oneTBB** 间切换（构建/运行时选择）。
- 框架层（如 PyTorch）常通过 oneTBB 或 OpenMP 做算子内多线程；流图适合把预处理→推理→后处理拼成 pipeline。

```bash
# 限制 TBB 可用线程数
export TBB_NUM_WORKERS=8
```

## 4. 常见误区

- **不要混用裸线程锁与任务**：在 task 内做阻塞锁会饿死调度器；用 `parallel_for` + 归约替代手动加锁累加。
- **NUMA 亲和**：大规模多路机上需配合 `numactl` 绑定，否则跨 NUMA 内存访问拖慢。

## 参考来源

- [[concepts/oneDNN 深度学习性能库]]
- [[concepts/CPU 微架构内部]]
- oneTBB 官方文档与 GitHub（https://github.com/oneapi-src/oneTBB）
- Intel oneAPI Threading Building Blocks Developer Guide
