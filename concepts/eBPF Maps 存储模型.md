---
title: eBPF Maps 存储模型
category: concepts
tags: [ebpf, maps, kernel, data-structure]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF Maps 的类型体系与使用模式 — BPF 程序与用户空间共享数据的核心机制
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF Maps 存储模型

## 概述

BPF maps 是内核与用户空间之间共享数据的通用存储，支持多种数据结构。BPF 程序通过 helper 函数访问 maps，用户空间通过 bpf() syscall 进行创建/查询/更新/删除。

创建 map 时需指定：type、key_size、value_size、max_entries、flags。

## Map 类型体系

### 基础类型

| Map 类型 | 特性 | 典型用途 |
|---------|------|---------|
| BPF_MAP_TYPE_HASH | 通用哈希表，任意 key/value | 计数、聚合、状态存储 |
| BPF_MAP_TYPE_ARRAY | 预分配数组，O(1) 查找，不可删除 | 最快查找路径，可 JIT 内联 |
| BPF_MAP_TYPE_PROG_ARRAY | 存储 BPF 程序 fd | tail call（尾调用链） |
| BPF_MAP_TYPE_PERF_EVENT_ARRAY | 与 perf 事件关联 | 性能采样 |

### 高性能变体

- **BPF_MAP_TYPE_PERCPU_HASH / PERCPU_ARRAY**：每个 CPU 一份副本，消除锁竞争，随核数线性扩展
- **BPF_MAP_TYPE_LRU_HASH / LRU_PERCPU_HASH**：最近最少使用淘汰策略，控制内存上限

### 数据传输

| Map 类型 | 机制 | 适用场景 |
|---------|------|---------|
| BPF_MAP_TYPE_PERF_EVENT_ARRAY | Per-CPU ring buffer | 传统高性能事件流 |
| BPF_MAP_TYPE_RINGBUF | 共享 ring buffer (5.8+) | 推荐的事件流方案，支持多生产者/单消费者 |
| BPF_MAP_TYPE_QUEUE / BPF_MAP_TYPE_STACK | FIFO/LIFO | 消息传递 |

### 存储映射

- **BPF_MAP_TYPE_STACK_TRACE**：存储内核栈跟踪
- **BPF_MAP_TYPE_CGROUP_ARRAY / CGROUP_STORAGE**：cgroup 层级关联存储
- **BPF_MAP_TYPE_TASK_STORAGE / INODE_STORAGE / SK_STORAGE**：task/inode/socket 局部存储
- **BPF_MAP_TYPE_ARENA**：内核-用户共享内存区域

### 特殊类型

- **BPF_MAP_TYPE_BLOOM_FILTER**：高效的存在性判断
- **BPF_MAP_TYPE_LPM_TRIE**：最长前缀匹配 trie 树（路由表）

## BCC 宏与 API 映射

```c
BPF_HASH(name, key_t, val_t)       // hash map
BPF_ARRAY(name, val_t, max)         // array map
BPF_PERF_OUTPUT(name)               // perf buffer
BPF_PERCPU_ARRAY(name)              // per-cpu array
BPF_RINGBUF_OUTPUT(name, pgs)       // ring buffer
```

## 使用模式

### 聚合计数

BPF 程序递增 map 值，用户空间周期性读取。典型如 syscall 计数器。

### 事件流

BPF 程序将结构化事件写入 ringbuf/perf buffer，用户空间守护进程 poll 消费。最快的事件路径，零拷贝。

### 配置与状态

用户空间写入 map 作为 BPF 程序的配置（如过滤规则），程序运行时读取。热更新无需重启程序。

### 关联状态

kprobe entry 保存开始时间戳，kretprobe exit 计算延迟。跨函数调用的状态协调。

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF 核心架构]]
