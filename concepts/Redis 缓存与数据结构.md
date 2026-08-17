---
title: Redis 缓存与数据结构
category: concepts
tags: [redis, cache, data-structure, cluster, sentinel, aof, rdb, active]
created: 2026-08-12
updated: 2026-08-17
summary: >-
    Redis 缓存与数据结构：为何缓存（解耦 DB 压力/降延迟，回扣分布式与韧性）、核心数据结构
    （string/hash/list/set/zset/bitmap/hyperloglog/stream/geo）、持久化（RDB/AOF）、
    高可用（主从/哨兵/Cluster 分片/resharding）、缓存经典三坑（穿透/击穿/雪崩）与一致性
    （Cache-Aside 代码模式）、分布式锁（SET NX + Redlock）、内存淘汰策略（LRU/LFU）、
    与 Kafka 配合做异步更新。衔接 [[concepts/分布式系统基础]]、[[concepts/韧性设计]]、[[concepts/Kafka 消息队列与流处理]]。
base_confidence: 0.88
lifecycle: review
sources: []
---

# Redis 缓存与数据结构

> Redis 是分布式系统里最常见的**缓存/共享状态**组件。坑不在「会用」，在「缓存一致性三连」。

---

## 1. 为什么需要缓存

- 数据库（[[concepts/关系型数据库内核]]）磁盘 IO 慢、连接贵；热点数据放内存，降延迟、抗突发（削峰，[[concepts/韧性设计]]）。
- 共享状态：分布式锁、限流计数、会话、排行榜——需多实例可见（[[concepts/分布式系统基础]] 多副本共享）。

---

## 2. 核心数据结构（选型是重点）

| 结构 | 典型用途 |
|---|---|
| `string` | 缓存 value、计数器（`INCR`）、分布式锁（`SET NX`） |
| `hash` | 对象字段（用户资料），避免整对象序列化 |
| `list` | 队列、最新 N 条（LPUSH+LTRIM） |
| `set` / `zset` | 去重 / **排行榜**（按 score 排序，延迟低） |
| `bitmap` | 用户在线/签到（位操作省内存） |
| `hyperloglog` | UV 近似去重（误差 ~0.8%，极省） |
| `stream` | 轻量消息队列（消费组，类 Kafka 但更轻） |
| `geo` | 附近的人（GEOADD+GEORADIUS） |

> `zset` 是排行榜/延迟队列神器：`ZADD` 打分、`ZRANGE` 取 TopN、`ZRANGEBYSCORE` 取到期任务。

---

## 3. 持久化：内存数据如何不丢

| 方式 | 机制 | 优点 | 缺点 |
|---|---|---|---|
| **RDB** | 定时快照 | 恢复快、文件小 | 可能丢最后一次快照后的数据 |
| **AOF** | 追加每条写命令 | 更耐丢（可配每秒 fsync） | 文件大、恢复慢 |
| 混合 | RDB+AOF 重写 | 兼得 | 默认推荐 |

---

## 4. 高可用

- **主从**：主写从读，从异步复制（主挂丢未同步数据）。
- **哨兵（Sentinel）**：监控+自动故障转移（选主），客户端查哨兵拿主地址。
- **Cluster**：**数据分片**（16384 槽），每分片主从；天然水平扩展，但跨槽事务/多 key 操作受限。

### Cluster 分片实战

```
key → CRC16(key) % 16384 → 槽号 → 所属节点
```

- **MOVED 重定向**：客户端访问错节点，收到 `MOVED 3999 127.0.0.1:7002`，自动重定向。
- **ASK**：槽正在迁移中，临时重定向。
- **客户端缓存**：Jedis/Lettuce/redis-cli 都缓存槽→节点映射，只在 MOVED 时更新。
- **resharding**：`redis-cli --cluster reshard` 在线迁移槽，对业务透明。
- **限制**：多 key 操作必须在同一槽（用 `{tag}` 强制同槽：`SET {user:1000}:name "tom"`）。

---

## 5. 缓存经典三坑（必考）

| 坑 | 现象 | 解法 |
|---|---|---|
| **穿透** | 查不存在的 key，每次打 DB | 缓存空值（短 TTL）/ **布隆过滤器**拦截 |
| **击穿** | 某热点 key 过期瞬间，大量请求同时打 DB | 互斥锁重建 / 逻辑过期（不真删） |
| **雪崩** | 大量 key 同时过期 / Redis 挂 | 过期时间加随机抖动 / 高可用（Cluster）+ 限流 |

> [!warning] 击穿用锁重建要设超时
> 重建时 `SETNX` 拿锁，拿不到的sleep重试；锁必须带 TTL，否则重建进程挂了别的请求永久阻塞。

---

## 6. 分布式锁（Redisson/Redlock）

单节点用 `SET key val NX EX 30`（原子设置 + 过期）；释放时**必须用 Lua 脚本**保证「只有持锁者能删」：
```lua
-- release_lock.lua
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else return 0 end
```

**Redlock（多节点）**：向 N 个独立 Redis 实例加锁，多数（N/2+1）成功才算拿锁。争议点：时钟漂移/GC 停顿可能导致安全边界松动（Martin Kleppmann vs Antirez 论战）。实践中单节点 + 看门狗续期（Redisson `watchdog`）更常用。

---

## 7. 内存淘汰策略

| 策略 | 行为 |
|---|---|
| `noeviction` | 不淘汰，写满报错（默认） |
| `allkeys-lru` | 所有 key 中淘汰最近最少使用（最常用） |
| `volatile-lru` | 仅淘汰设了 TTL 的 key |
| `allkeys-lfu` | 所有 key 中淘汰最不频繁（Redis 4.0+，热点更准） |
| `volatile-ttl` | 淘汰最快过期的 |

> 容器场景：`maxmemory` 设为容器 limit 的 70-80%，配 `allkeys-lru`。

---

## 8. 缓存与数据库一致性

常见 **Cache-Aside（旁路）** 模式：
- **读**：缓存没有 → 查 DB → 写缓存。
- **写**：先更新 DB → **再删缓存**（删除而非更新，避免并发写导致脏数据）。

### Cache-Aside 代码模式
```python
def get_user(user_id):
    # 1. 读缓存
    val = redis.get(f"user:{user_id}")
    if val:
        return json.loads(val)
    # 2. 缓存 miss → 查 DB
    user = db.query("SELECT * FROM users WHERE id=%s", user_id)
    if user:
        # 3. 写缓存（加随机 TTL 防雪崩）
        redis.setex(f"user:{user_id}", 300 + random(0,60), json.dumps(user))
    return user

def update_user(user_id, data):
    # 1. 先更新 DB
    db.execute("UPDATE users SET ... WHERE id=%s", user_id)
    # 2. 再删缓存（不是更新！）
    redis.delete(f"user:{user_id}")
    # 3. 可选：发 Kafka 事件让下游刷新（[[concepts/Kafka 消息队列与流处理]]）
```

> [!note] 为什么「删」不「更新」
> 并发写时，两个请求更新 DB 后各自写缓存，后写缓存的可能不是最新值。删缓存让下一次读重建，保证一致性。

问题：删缓存失败/并发读写仍可能短暂不一致。要求强一致的业务不适合纯缓存，用「写 DB + 发事件（[[concepts/Kafka 消息队列与流处理]]）让下游按事件刷新」或接受最终一致（[[concepts/分布式系统基础]] BASE）。

---

## 9. 与消息队列配合

`Redis stream` 可做轻量队列；但高吞吐/可靠投递请用 **Kafka**（[[concepts/Kafka 消息队列与流处理]]）。典型：请求写 DB → 发 Kafka 事件 → 消费者更新 Redis 缓存，保证最终一致。

---

## 参考链接

**库内双链**
- [[concepts/分布式系统基础]] — 多副本共享、最终一致、BASE
- [[concepts/关系型数据库内核]] — 缓存背后的 DB
- [[concepts/韧性设计]] — 削峰/限流/降级
- [[concepts/Kafka 消息队列与流处理]] — 异步刷新缓存
- [[concepts/容器安全]] — Redis 认证/网络暴露加固

**外部资料**
- Redis 官方文档（redis.io）
- 《Redis 设计与实现》— 数据结构与持久化源码
