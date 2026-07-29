---
title: eBPF 验证器与安全模型
category: concepts
tags: [ebpf, verifier, security, kernel]
created: 2026-07-29
updated: 2026-07-29
summary: eBPF 验证器内部机制与安全授权模型 — 寄存器状态追踪、复杂度约束、CAP_BPF、BPF Token、BPF LSM
base_confidence: 0.85
lifecycle: draft
lifecycle_changed: 2026-07-29
sources:
  - sources/eBPF 调研来源
---

# eBPF 验证器与安全模型

## 验证器作用

验证器是 eBPF 安全基座的核心。每个 BPF 程序在加载时必经验证器静态分析，通过后才可执行。验证器永不崩溃内核——拒绝加载是系统正常工作的表现。

### 验证器保证

1. **无不可达指令** — 所有代码路径必须最终到达 EXIT
2. **无越界/未检查内存访问** — 追踪每个寄存器的边界
3. **程序终止** — 循环必须是"可证明有界的"（5.3+ 引入 bounded loops，verifier 证明循环终止）
4. **栈使用 <= 512 字节/帧**
5. **仅调用允许的 helpers/kfuncs**
6. **R0 在 EXIT 前必须持有有效返回值**
7. **map 查找结果必须 NULL-check 后再解引用**

### 复杂度限制

| 限制 | 值 | 说明 |
|-----|-----|------|
| 最大验证指令数 | 1,000,000 | 5.2 起，早期仅 4,096 |
| 每路径复杂度 | 4,096 单位 | 条件分支加倍复杂度 |
| 栈大小 | 512 字节 | 建议大结构体放 per-CPU maps |
| tail call 深度 | 32 层 | 防止无限递归 |
| 验证日志默认缓冲 | 16 KB | 复杂程序需增大到 MB 级 |

### 寄存器状态追踪

验证器维护 `struct bpf_reg_state`，追踪每个寄存器和栈槽的类型与值范围。

**示例验证日志解读：**
```
R1=pkt(id=0,off=0,r=14)          → R1 指向包，已验证 14 字节可访问
R2=pkt_end(id=0,off=0)           → R2 标记包尾
R3=scalar(id=2,umin=0,umax=7)    → R3 是标量，范围 0-7
R4=pkt(id=2,off=8,r=0)           → R4 指向包偏移 8，暂无范围
```

- **状态剪枝 (Pruning)**：当寄存器/栈槽状态匹配已遍历路径时终止探索，防止路径爆炸
- **CFG + SSA 符号执行**：构建控制流图，按 SSA 风格追踪值在分支中的分化

### 常见验证器错误

| 错误信息 | 原因 | 修复 |
|---------|------|------|
| `R1 invalid mem access 'scalar'` | 直接解引用原始内核指针 | 使用 `bpf_probe_read_kernel()` |
| `BPF stack limit exceeded` | 局部结构体超过 512 字节 | 用 `BPF_PERCPU_ARRAY` 代替栈变量 |
| `back-edge from insn X to Y` | 循环不能被验证器证明有界 | `#pragma unroll` 或 `bpf_loop()` |
| `invalid indirect read from stack` | 向 helper 传递未初始化的栈 | 零初始化：`struct foo bar = {};` |
| `map_value or possibly-null pointer` | map 查找结果未做 NULL 检查 | 立即检查 `if (!val) return 0;` |
| `BPF program is too large` | 超出 1M 验证指令预算 | 简化分支或用 tail call 拆分 |

**调试策略**：只读验证日志最后几行——拒绝原因在最底部。先缩到最小可运行的 C 宏，再逐步加代码直到出错。

### 验证器前沿

- **PREVAIL**：基于抽象解释的验证器，允许更宽松的策略
- **BeePL**：2025 年形式化验证方案，安全接受 95% 真实世界程序 vs 内核验证器的 66%
- **Serval**：JIT 正确性的形式化验证

## 安全模型

### CAP_BPF（Linux 5.8+）

传统上加载 BPF 程序需要 root（CAP_SYS_ADMIN）。5.8 引入 CAP_BPF，细分 BPF 权限：

| 权限 | 需要的能力 | 允许操作 |
|------|-----------|---------|
| 加载追踪程序 | CAP_BPF + CAP_PERFMON | kprobe、tracepoint、perf_event 程序 |
| 加载网络程序 | CAP_BPF + CAP_NET_ADMIN | XDP、TC、socket filter 程序 |
| 操作 maps | CAP_BPF | 创建/读写/删除 maps |
| 查看 BPF 对象 | CAP_BPF | 枚举 programs/maps |

### BPF Token（Linux 6.9+）

进一步细化：通过 BPF 文件系统（bpffs）委派有限权限给非特权进程（容器）。

工作流程：
```
1. 特权进程创建 BPF token（BPF_TOKEN_CREATE syscall）
2. 指定允许的操作子集（加载某类型程序、操作 maps 等）
3. token 挂载到 bpffs 的已知路径
4. 非特权进程打开 token fd 并传入 bpf() syscall
5. 内核检查 token 允许的操作范围
```

意义：容器无需 CAP_BPF wide open，只需绑定到特定 hooks 和 maps 的 token。

### BPF LSM（Linux 5.7+）

将 eBPF 程序附加到 Linux Security Module hook 点，动态实现安全策略：

- 与 SELinux/AppArmor 在同一 hook 点执行
- 无需重新编译内核或加载策略模块
- Cloudflare 用 bpf-lsm 在运行时缓解内核漏洞（如 "Copy Fail" 漏洞）
- Tetragon 用 BPF LSM + tracing hooks 构建运行时安全阻断

### 非特权 eBPF

内核可通过 `kernel.unprivileged_bpf_disabled` sysctl 禁用非特权 BPF：

- `0`：允许（默认或发行版配置，但风险较高）
- `1`：永久禁用（需回写 0 重启）
- `2`：当前会话禁用（重启恢复为 0）

主流安全建议：生产环境设为 1 或 2，使用 BPF token 替非特权进程授权。

### 安全性一览

```
安全优势：
  - 验证器静态防止所有已知的内存安全违规
  - JIT 编译器位于可信计算基内
  - BPF token 最小权限原则
  - 拒绝加载是正常行为

已知绕过：
  - CVE-2023-2163：验证器整数溢出绕过（6.8 修复）
  - CVE-2024-xxxx：寄存器状态剪枝疏忽（6.12 修复）
  - 模糊测试最密集的内核组件，新 CVE 较少且修复快
```

## 参考来源

- [[sources/eBPF 调研来源]]
- [[concepts/eBPF 核心架构]]
- [[entities/eBPF 工具链]]
