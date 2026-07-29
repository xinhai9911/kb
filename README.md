---
title: 个人知识库（Personal Knowledge Base）
category: index
summary: >-
    主题化的 Markdown 笔记集合。Git 版本化，远端同步到 GitHub。
created: 2026-07-29
updated: 2026-07-29
sources: []
tags: [kb]
base_confidence: 0.7
lifecycle: reviewed
---

# 个人知识库（Personal Knowledge Base）

> 主题化的 Markdown 笔记集合。Git 版本化，远端同步到 GitHub。

## 地图

| 类别 | 目录 | 用途 |
|---|---|---|
| 索引 | [00-index/](00-index/) | 使用说明、标签字典 |
| 项目 | [10-projects/](10-projects/) | 进行中的项目笔记 |
| 协议 | [20-protocols/](20-protocols/) | 协议分析报告 |
| 片段 | [30-snippets/](30-snippets/) | 可复用的代码、命令、配置 |
| 想法 | [40-ideas/](40-ideas/) | 闪念、TODO、未成形 |
| 参考 | [50-reference/](50-reference/) | 速查、API、架构决策记录 (ADR) |
| 归档 | [90-archive/](90-archive/) | 已完成/不再活跃 |
| 来源蒸馏 | [50-reference/sources/](50-reference/sources/) | `Q:\常规书籍` / `Q:\芯片资料` 资料索引 |

## 双链示例

- 协议笔记：[[20-protocols/influxdb]]、[[20-protocols/hbase]]、[[20-protocols/elasticsearch]]
- 项目笔记：[[10-projects/database-decoder]]、[[10-projects/training]]

## 标签速查

详见 [00-index/tag-glossary.md](00-index/tag-glossary.md)。

## 最近更新

<!-- 手动维护：每次重要新增/更新追加一行，格式: - YYYY-MM-DD: [标题](path) -->
- 2026-06-10: 知识库初始化
- 2026-06-10: 迁入 5 个 HBase 笔记到 [[20-protocols/]]（静态分析、dropTable 报文、测试计划/执行、报告模板）
- 2026-06-11: 新增 [[50-reference/dlopen-internal-memory]]（dlopen 内部内存动作详解：mmap、重定位、GOT/PLT、RELRO、TLS 全链路拆解）
- 2026-06-15: 新增 [[50-reference/npp-timer-mechanism]]（NPP flowtable 定时触发机制：PROCESS + INTERRUPT 两级架构、空闲判定、慢/快清理策略）
- 2026-07-13: 新增导演系列参考笔记到 [[50-reference/]]：[[50-reference/director-intro]]（入门+ffmpeg秒点）、[[50-reference/montage-techniques]]（平行/积累/对比蒙太奇）、[[50-reference/shot-sizing-axes-storyboard]]（景别/轴线图+分镜模板）
- 2026-07-29: 蒸馏 `Q:\常规书籍` 与 `Q:\芯片资料` 到 [[50-reference/sources/]]（常规书籍 5 篇 + 芯片资料 9 篇，索引式笔记，保留原文路径便于回查）
- 2026-07-29: 新增 VPP 网络数据面笔记：[[20-protocols/vpp|VPP 知识]]（向量化节点图架构、缓冲管理、多线程模型）+ [[50-reference/vpp-usage|VPP 使用方法]]（startup.conf、CLI 命令、抓包调试、运维）+ [[50-reference/vpp-plugin-dev|VPP 插件开发]]（自定义 node/plugin、Process Node 协程、CMake 构建、加载调试）+ [[50-reference/vpp-plugin-perf|VPP 插件性能调优]]（批处理范式、无锁多核、巨页缓冲、瓶颈定位、NPP 实战）
- 2026-07-29: 新增 [[50-reference/npp-flowtable-cleanup-example|NPP 流表清理代码实例]]（三级协作完整可编译骨架：clear-process 定时调度 + cleaner 中断执行 + try_cleanup slow/fast 双策略，per-thread 无锁、exapi del_handler 解耦）
- 2026-07-29: 新增 [[50-reference/npp-flowtable-perf-test|NPP 流表性能测试实例]]（四类用例：基线转发/空闲清理开销/满表 fast_cleanup 回收/多核无锁扩展，观测 show cpu·runtime·errors，含结果表与判定标准）
- 2026-07-29: 增加 CI 链接校验：`.github/workflows/check-links.yml`（push/PR 时跑 `scripts/check-links.js`，校验 wikilink 与目录链接，可选 `--check-external` 验外链可达性）
- 2026-07-29: 新增 FPGA 知识库：[[20-protocols/fpga|FPGA 知识]]（LUT/FF/BRAM/DSP 架构、RTL→仿真→综合→实现→比特流全流程、VHDL/Verilog 对比、时序/CDC、与 ASIC/CPU/GPU 取舍）+ [[50-reference/fpga-usage|FPGA 使用方法]]（iverilog/Verilator/GHDL 仿真、Vivado/Quartus 综合上板、CDC 同步器、Makefile 流程，引用本地 Q:/AI/vhdl_examples）
- 2026-07-29: 扩充 FPGA 知识库（丰富化）：+ [[20-protocols/fpga-design-patterns|RTL 设计模式]]（FSM/流水线/同步·异步FIFO/握手/AXI-S/仲裁器，含可综合代码）+ [[50-reference/fpga-verification|FPGA 验证方法]]（自检查 testbench/SVA 断言/功能覆盖率/约束随机/Verilator CI）+ [[entities/fpga-vendors|FPGA 厂商与开源工具链]]（AMD/Intel/Lattice/Microchip 选型 + Yosys/nextpnr/SymbiFlow）；主篇 fpga.md 增「深入主题」（时序收敛/SoC 软核/部分重配置/功耗面积权衡）并全量双链
