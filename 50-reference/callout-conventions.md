---
title: 全库 Callout 使用清单与规范
category: reference
tags: [obsidian, admonition, callout, convention, style]
created: 2026-07-30
updated: 2026-07-30
summary: >-
  全库 Admonition/callout 使用清单与转换进度：现有 callout 库存（11 处）、推荐类型约定、
  待补候选已全部转换完成，以及 Admonition 全局样式建议。本库已装 Admonition 11.0.0。
base_confidence: 0.95
lifecycle: reviewed
---

# 全库 Callout 使用清单与规范

本清单盘点 `Q:\AI\kb` 中 **Admonition / callout** 的使用现状，并给出全库统一的类型约定。
配套：[[50-reference/obsidian-plugins|Obsidian 已安装插件说明]]（含 Admonition 详述）、
[[50-reference/obsidian-usage|Obsidian 使用方法]]。

> 基础语法（Obsidian 原生 + Admonition 兼容）：
> `> [!type] 标题` 起一行，后续 `>` 续行；标题后加 `-` 可变可折叠：`> [!warning]- 标题`。

## 一、类型约定（本库推荐）

| 类型 | 含义 | 本库适用场景 | 图标建议 |
|------|------|------------|---------|
| `note` | 补充说明 / 背景知识 | 概念澄清、原理补充（如"SM2≠P-256"） | 📝 |
| `info` | 环境 / 前置条件 | 编译环境、依赖、运行要求 | ℹ️ |
| `tip` | 实践技巧 / 提速 | 省事命令、调试窍门 | 💡 |
| `warning` | 必犯错误 / 强约束 | "不加 `--with-compat` 会崩溃"、"Windows 不能编译" | ⚠️ |
| `danger` | 不可逆 / 高危操作 | `git reset --hard`、删库、生产开关 | 🔥 |
| `caution` | 需权衡的风险 | 性能/安全折中、兼容性坑 | ⚠️ |
| `success` | 验证通过 / 预期结果 | 测试应出现的输出、健康信号 | ✅ |

> 建议全库**只固定用这 7 种**，避免自定义类型发散，便于统一上色与检索。

## 二、现有 Callout 库存（真实渲染的，11 处）

不含代码栅栏里的示例文本。按"类型 / 文件:行 / 用途"列出：

| 类型 | 位置 | 用途 |
|------|------|------|
| `warning` | `projects/nginx-module-examples/README.md:51` | 动态模块务必加 `--with-compat`，否则加载崩溃 |
| `info` | `projects/nginx-module-examples/README.md:134` | `load_module`/`proxy_pass` 需内置 http 模块 |
| `warning` | `projects/openssl-crypto-examples/README.md:61` | Windows/Git-Bash 无法编译，需 Linux/macOS/WSL |
| `note` | `projects/openssl-crypto-examples/README.md:100` | SM2≠P-256、SM3 与 SHA-256 值不同 |
| `info` | `projects/resilience-examples/README.md:38` | Windows 需用 WSL（面向 POSIX） |
| `note` | `concepts/哈希函数与消息认证 HMAC.md:30` | 抗碰撞 O(2^(n/2)) 弱于原像 O(2^n)，256-bit 抗碰撞≈128 bit |
| `note` | `concepts/设计模式精讲.md:43` | Nginx filter 链即装饰器模式典型实现 |
| `info` | `entities/fpga-vendors.md:51` | 开源 bitstream 链路在 Lattice 最完整；Vivado 有免费 WebPACK |
| `warning` | `entities/国密 SM2_SM3_SM4 实战.md:30` | SM2 曲线 `sm2p256v1` ≠ NIST P-256，不可混用 |
| `caution` | `entities/重构实战：识别并消除代码坏味道.md:58` | "巧合重复"别强行合并，仅语义相同才抽 |
| `warning` | `projects/db-decoder-ironhive/hive-decoder-implementation.md:43` | falcon 不支持动态加载自定义协议 .so |

> 统计口径：`grep -rnE '^> \[!([a-z]+)\]'` 全库得 11 处；`obsidian-plugins.md` 里的
> `> [!info]` 均为文档示例（在代码栅栏内），**不渲染**，不计入。

## 三、待补转换进度（已全部完成）

| 候选位置 | 目标类型 | 状态 |
|---------|---------|------|
| `concepts/哈希函数与消息认证 HMAC.md:30` | `note` | ✅ 已转 |
| `concepts/设计模式精讲.md:43` | `note` | ✅ 已转 |
| `entities/fpga-vendors.md:51` | `info` | ✅ 已转 |
| `entities/国密 SM2_SM3_SM4 实战.md:30` | `warning` | ✅ 已转 |
| `entities/重构实战：识别并消除代码坏味道.md:58` | `caution` | ✅ 已转 |
| `projects/db-decoder-ironhive/hive-decoder-implementation.md:43` | `warning` | ✅ 已转 |
| `projects/README.md` 顶部搜索框说明 | `info`（可选）| ⏸ 保留普通引用（导航性，非警示）|

全库 callout 由 **5 处 → 11 处**。后续审计可用：
`grep -rnE '^> (注意|注[:：]|警告|务必|谨慎|风险)'` 找出新的裸引用。

## 四、Admonition 全局样式建议

在 Obsidian 设置 → Admonition 中统一，保证全库视觉一致：

1. **固定类型集**：只保留第一节的 7 种；删除/不改名其它自带类型，避免风格碎片化。
2. **统一配色**（建议）：
   - `warning` / `caution`：琥珀→红，强提醒
   - `danger`：红底，仅高危操作
   - `info` / `note` / `tip` / `success`：蓝/绿系，低干扰
3. **可折叠默认**：`warning`/`danger` 默认展开；长 `note` 可用 `> [!note]-` 折叠。
4. **图标**：用内置 emoji 或 Obsidian 图标库，避免外链图片（保证离线/发布可用）。
5. **检索兼容**：callout 内文字仍会被全文搜索与 Dataview（行内字段除外）命中，无需特殊处理。

## 五、维护约定

- **新增警示内容时**：先判断属于哪一型（见第一节），直接用 `> [!type]`，
  不要再用裸 `> 注意：…`。
- **审计**：定期跑 `grep -rnE '^> (注意|注[:：]|警告|务必|谨慎|风险)'` 找出仍是裸引用的警示，
  转为 callout（本清单第三节即一次审计结果）。
- **版本记录**：若 Admonition 升级导致类型名变化，同步更新本清单第一节。

## 参考链接

- [[50-reference/obsidian-plugins|Obsidian 已安装插件说明]] — Admonition 详细用法
- [[50-reference/obsidian-usage|Obsidian 使用方法]] — 上手与维护流程
- [[00-index/how-to-use|如何使用本知识库]] — 分类与 frontmatter 规范
