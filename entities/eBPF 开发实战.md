---
title: eBPF 开发实战
category: entities
tags: [ebpf, development, tutorial, bcc, libbpf, xdp]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF 从零到生产的开发指引 — 环境搭建、BCC/libbpf 示例、XDP/TC/追踪开发、maps 使用、调试与常见陷阱
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF 开发实战

> 本文假设读者有 C 语言基础。每段代码均可独立运行。

## 1. 环境准备

### 1.1 内核要求

```
# 查看内核版本 — XDP 需要 4.8+，CO-RE 建议 5.8+
uname -r

# 确认 BTF 可用（CO-RE 前提）
ls -lh /sys/kernel/btf/vmlinux

# 确认 BPF 系统调用可用
grep CONFIG_BPF /boot/config-$(uname -r)

# 挂载 BPF 文件系统
mount -t bpf bpf /sys/fs/bpf/
```

### 1.2 安装工具链

```bash
# Ubuntu / Debian
apt install clang llvm libbpf-dev bpftool bpftrace linux-tools-common

# Fedora / RHEL
dnf install clang llvm libbpf-devel bpftool bpftrace kernel-devel

# 验证
clang --version          # 需支持 bpf 目标
llc --version            # 确认 BPF 后端
bpftool --version
```

### 1.3 开发目录结构（libbpf 项目）

```
xdp-example/
├── Makefile
├── xdp_prog.bpf.c       # BPF 内核程序（.bpf.c 约定）
├── xdp_prog.skel.h      # bpftool 生成的 skeleton
├── xdp_user.c            # 用户空间加载器
└── common.h
```

## 2. BCC 快速原型 —— 适合学习/调试

### 2.1 Hello World (kprobe)

```c
// hello.c — BCC 嵌入式 C
#include <uapi/linux/ptrace.h>

int hello_world(void *ctx)
{
    bpf_trace_printk("Hello from BPF!\n");
    return 0;
}
```

```python
# hello.py
from bcc import BPF

b = BPF(src_file="hello.c")
b.attach_kprobe(event="__x64_sys_clone", fn_name="hello_world")

print("Tracing... Ctrl-C to exit")
b.trace_print()
```

**运行**：`sudo python3 hello.py`

### 2.2 XDP 黑名单丢包

```c
// xdp_drop.c
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <linux/if_ether.h>
#include <linux/ip.h>

#define DENY_IP(a,b,c,d) ((__u32)((a) | (b<<8) | (c<<16) | (d<<24)))

SEC("xdp")
int xdp_drop_ip(void *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data     = (void *)(long)ctx->data;
    struct ethhdr *eth = data;

    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (bpf_ntohs(eth->h_proto) != ETH_P_IP)
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    if (ip->saddr == DENY_IP(10,0,0,1))
        return XDP_DROP;       // 丢弃

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
```

```python
# xdp_drop.py
from bcc import BPF

b = BPF(src_file="xdp_drop.c")
fn = b.load_func("xdp_drop_ip", BPF.XDP)
b.attach_xdp(dev="eth0", fn=fn)

try:
    print("XDP loaded on eth0. Ctrl-C to detach")
    import time; time.sleep(60)
except KeyboardInterrupt:
    pass
finally:
    b.remove_xdp(dev="eth0")
```

### 2.3 文件打开追踪 (Hash Map)

```c
// fopen_trace.c
#include <uapi/linux/ptrace.h>

BPF_HASH(counter, __u64, __u64);

int trace_fopen(struct pt_regs *ctx)
{
    __u64 pid = bpf_get_current_pid_tgid();
    counter.increment(pid, 1);
    return 0;
}
```

```python
# fopen_trace.py
from bcc import BPF
import time

b = BPF(src_file="fopen_trace.c")
b.attach_kprobe(event="do_sys_openat2", fn_name="trace_fopen")

for _ in range(10):
    time.sleep(1)
    for k, v in b["counter"].items():
        print(f"PID {k.value}: {v.value} opens")
    b["counter"].clear()
```

## 3. libbpf + CO-RE 生产开发

### 3.1 XDP 丢弃程序（生产风格）

```c
// xdp_block.bpf.c
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <linux/if_ether.h>
#include <linux/ip.h>

char LICENSE[] SEC("license") = "GPL";

SEC("xdp")
int xdp_block(struct xdp_md *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data     = (void *)(long)ctx->data;
    struct ethhdr *eth = data;

    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (bpf_ntohs(eth->h_proto) != ETH_P_IP)
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    // 等价功能：拒绝特定网段
    __u32 block_start = 0xC0A80000; // 192.168.0.0
    __u32 block_mask  = 0xFFFF0000;
    if ((ip->saddr & block_mask) == block_start)
        return XDP_DROP;

    return XDP_PASS;
}
```

### 3.2 生成 skeleton

```bash
clang -g -O2 -target bpf -c xdp_block.bpf.c -o xdp_block.o
bpftool gen skeleton xdp_block.o > xdp_block.skel.h
```

### 3.3 用户空间加载器

```c
// xdp_block_user.c
#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include <net/if.h>
#include "xdp_block.skel.h"

int main(int argc, char **argv)
{
    struct xdp_block_bpf *skel;
    int err, ifindex;

    if (argc < 2) {
        fprintf(stderr, "Usage: %s <ifname>\n", argv[0]);
        return 1;
    }

    // 1. 打开并加载 BPF 程序
    skel = xdp_block_bpf__open_and_load();
    if (!skel) {
        fprintf(stderr, "Failed to open/load BPF obj\n");
        return 1;
    }

    // 2. 挂载到网卡
    ifindex = if_nametoindex(argv[1]);
    err = bpf_program__attach_xdp(skel->progs.xdp_block, ifindex);
    if (err) {
        fprintf(stderr, "XDP attach failed\n");
        goto cleanup;
    }

    printf("XDP loaded on %s. Press Ctrl-C to detach\n", argv[1]);
    for (;;) pause();

    // 3. 卸载
    bpf_xdp_detach(ifindex, 0);

cleanup:
    xdp_block_bpf__destroy(skel);
    return 0;
}
```

```makefile
# Makefile
CC = gcc
CFLAGS = -g -O2 -Wall
BPF_CLANG = clang
BPF_CFLAGS = -g -O2 -target bpf

all: xdp_block

xdp_block.bpf.o: xdp_block.bpf.c
	$(BPF_CLANG) $(BPF_CFLAGS) -c $< -o $@

xdp_block.skel.h: xdp_block.bpf.o
	bpftool gen skeleton $< > $@

xdp_block: xdp_block_user.c xdp_block.skel.h
	$(CC) $(CFLAGS) -lbpf -lelf -lz $< -o $@

clean:
	rm -f *.o *.skel.h xdp_block
```

### 3.4 TC 入向流量整形

```c
// tc_ingress.bpf.c — TC 入口过滤
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <linux/pkt_cls.h>

SEC("tc")
int tc_ingress(struct __sk_buff *skb)
{
    // 限制特定目标端口的流量
    if (skb->protocol == __constant_ntohs(ETH_P_IP)) {
        // 示例：统计包数
        return TC_ACT_OK;  // 放行
    }
    return TC_ACT_OK;
}
```

挂载命令：
```bash
tc qdisc add dev eth0 clsact
tc filter add dev eth0 ingress bpf da obj tc_ingress.o sec tc
```

### 3.5 fentry 内核函数追踪（5.5+）

```c
// trace_exec.bpf.c
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

SEC("fentry/do_execveat_common")
int BPF_PROG(trace_exec, int fd, const char __user *filename,
             void __user *argv, void __user *envp, int flags)
{
    __u32 pid = bpf_get_current_pid_tgif() >> 32;
    bpf_printk("PID %d exec file: %s\n", pid, filename);
    return 0;
}
```

## 4. Maps 开发模式

### 4.1 Hash Map — 键值查找

```c
// 内核端
struct { __uint(type, BPF_MAP_TYPE_HASH);
         __uint(max_entries, 1024);
         __type(key, __u32);
         __type(value, __u64);
} pkt_count SEC(".maps");
```

```c
// 更新计数
__u32 key = ip->saddr;
__u64 *val = bpf_map_lookup_elem(&pkt_count, &key);
if (val)
    __sync_fetch_and_add(val, 1);
else {
    __u64 init = 1;
    bpf_map_update_elem(&pkt_count, &key, &init, BPF_NOEXIST);
}
```

### 4.2 Ring Buffer — 推送事件到用户空间

```c
// 内核端
struct event { __u32 pid; char comm[16]; };

struct { __uint(type, BPF_MAP_TYPE_RINGBUF);
         __uint(max_entries, 1 << 24);  // 16 MB
} rb SEC(".maps");

SEC("kprobe/sys_openat")
int trace_openat(struct pt_regs *ctx)
{
    struct event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
    if (!e) return 0;

    e->pid = bpf_get_current_pid_tgif() >> 32;
    bpf_get_current_comm(&e->comm, sizeof(e->comm));
    bpf_ringbuf_submit(e, 0);
    return 0;
}
```

```c
// 用户空间（libbpf）
void handle_event(void *ctx, void *data, size_t sz)
{
    struct event *e = data;
    printf("PID=%d COMM=%s\n", e->pid, e->comm);
}

// 设置回调
struct ring_buffer *rb = ring_buffer__new(
    bpf_map__fd(skel->maps.rb), handle_event, NULL, NULL);
while (ring_buffer__poll(rb, 100) >= 0);  // 轮询等待
```

### 4.3 Per-CPU Array — 计数器无锁

```c
struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
         __uint(max_entries, 256);
         __type(key, __u32);
         __type(value, __u64);
} cpu_stats SEC(".maps");
```

无锁累加，用户空间读汇总：
```c
// 用户空间
for (int cpu = 0; cpu < nr_cpus; cpu++) {
    __u64 val;
    bpf_map_lookup_elem(map_fd, &zero_idx, &val);
    total += val;
}
```

## 5. 调试实践

### 5.1 bpftool 查看状态

```bash
# 列出所有已加载程序
bpftool prog list

# 查看 XDP 程序详情（含字节码和 JIT）
bpftool prog show id <id>
bpftool prog dump xlated id <id>
bpftool prog dump jit   id <id>

# 遍历 map 内容
bpftool map list
bpftool map dump id <id>

# 查看挂载点
bpftool net list
```

### 5.2 bpf_trace_printk 日志

```bash
# 内核端写日志
bpf_printk("packet src=%x\n", ip->saddr);

# 用户空间读取
cat /sys/kernel/debug/tracing/trace_pipe
# 或
bpftrace -e 'tracepoint:syscalls:sys_enter_openat { printf("%s\n", comm); }'
```

### 5.3 Verifier 日志分析

```bash
# 捕获 verifier 拒绝原因
bpftool prog load xdp_block.o /sys/fs/bpf/xdp_block \
    -d 2>&1 | tail -50
```

常见 verifier 错误：

| 错误信息 | 原因 | 解决 |
|---------|------|------|
| `unbounded memory access` | 指针未检查边界 | 加 data_end 检查 |
| `invalid access to map value` | 访问 map 值超出范围 | 验证 key/value 大小 |
| `program too large` | 指令 > 1M | 简化逻辑或用 bpf_loop |
| `R0 invalid mem access` | 返回值不合法 | 确保返回正确 enum |
| `NULL pointer dereference` | 未检查 map lookup 返回值 | 加 `if (!val) return 0` |

### 5.4 bpftrace 快速诊断

```bash
# 跟踪所有 XDP 程序丢包计数
bpftrace -e 'kfunc:__xdp_do_redirect { @[probe_name] = count(); }'

# 查看系统调用延迟分布
bpftrace -e 'kprobe:do_sys_openat { @start[tid] = nsecs; }
             kretprobe:do_sys_openat /@start[tid]/ {
                 @us = hist((nsecs - @start[tid]) / 1000);
                 delete(@start[tid]); }'

# 列出可用的 tracepoint
bpftrace -l 'tracepoint:*'
```

### 5.5 bpftool 热替换 XDP 程序

```bash
# 编译并加载
clang -O2 -target bpf -c xdp_v2.bpf.c -o xdp_v2.o
bpftool net attach xdp id <new_id> dev eth0
# 无流量中断
```

## 6. 常见陷阱

| 陷阱 | 现象 | 解决方法 |
|------|------|----------|
| 未检查 data_end | verifier 拒绝 | 每个指针访问前 `if (ptr + size > data_end) return` |
| 栈太大 | verifier 报栈访问越界 | BPF 栈限 512 字节，用 per-CPU map 代替 |
| 无界循环 | verifier 超时 | 用 `bpf_loop()` 或 `#pragma unroll` |
| 忽略 map NULL | 内核 panic | `bpf_map_lookup_elem` 必须检查 NULL |
| clang 未用 `-target bpf` | 加载失败 | 确保编译目标为 bpf，非 x86_64 |
| 缺失 BTF | CO-RE 重定位失败 | 确认 `/sys/kernel/btf/vmlinux` 存在 |
| BPF 程序未卸载 | 下次加载失败 | 退出前 `bpf_xdp_detach` 或 `ip link set dev eth0 xdp off` |
| helper 版本不足 | verifier 报 unknown func | 查 ebpf.io/linux/helper-function/ 确认内核版本 |

## 7. 完整项目模板

```bash
# 使用 libbpf-bootstrap 快速起项目
git clone https://github.com/libbpf/libbpf-bootstrap
cd libbpf-bootstrap/examples/c
make
sudo ./xdp1 eth0    # 直接跑
```

## 参考来源

- [[sources/eBPF 调研来源]]
- [[entities/eBPF 工具链]]
- [[concepts/eBPF 核心架构]]
- [[concepts/XDP 高速数据路径]]
- [[concepts/eBPF Maps 存储模型]]
- [[synthesis/eBPF 技术全景]]
- [[synthesis/DPDK 与 eBPF XDP 技术对比]]
