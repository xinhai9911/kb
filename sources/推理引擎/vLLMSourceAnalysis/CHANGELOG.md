# 变更日志（Changelog）

本文件记录 `vLLMSourceAnalysis` 知识库的维护性变更（补完、拆分、一致性修复等）。转换过程与统计见 `_pipeline_report.md`。

## 2026-08-20

### 第八轮：模型索引表 + 页脚统一
- **新增** `30-model-families/model-index_part1~3.md`：`model_executor/models/` 全部 268 个模型文件 → 架构类（architecture）→ 12 族索引表。
- **修复** `00-overview/architecture.md` 页脚：`[`skill.md`]` → `[skill.md]`，去除反引号，与全库 99 个文件页脚格式统一。
- 同步：`skill.md` 索引新增 3 行，`markdown_file_count` 96→99；`_pipeline_report.md` 更新覆盖率/统计/遗留问题。

### 第七轮：v0 历史标注统一
- 模块 20 三个文件（`executor-architecture.md`/`v0-model-runner.md`/`llm-generator.md`）标注统一为 `> **历史来源**`。
- 建立模块 20 ↔ 24 双向交叉引用（历史 v0 实现 ↔ 当前 `engine/` shim 现状）。
- `skill.md` 索引对三行 v0 内容加注「历史」。

### 第六轮：超限文件拆分
- `01-config/sub-configs_part1.md`（8.29KB）→ `sub-configs_part1`（Cache/Scheduler）+ `sub-configs_part2`（Parallel）。
- `04-attention/attention-architecture.md`（8.35KB）→ `attention-architecture` + `attention-architecture_part2`（元数据/层接线）。
- 至此全部 96 个分析文件 ≤8KB。

### 第五轮：一致性审计
- 统一 `device-communicators-part1/2.md` → `_part1/_part2` 命名规范（与全库 `_partN` 一致）。
- 修复 3 处正文悬空 `.md` 引用：`comm-ops.md`→`device-communicators_part1.md`×2、`ray-integration.md`→`../08-distributed/worker-executor.md`、`weight-loading.md`→`../06-model-executor/loader.md`。
- 复核：无孤立文件、无重复文件、无空目录、代码围栏全部配对。

### 前四轮（模块补完历程）
- 第一轮（前序会话）：模块 00–06、08–11，26 文件。
- 第二轮：新增 07、12–18（输入/量化/LoRA/平台/v1 Worker/结构化/编译/工具解析），3 个根文件。
- 第三轮：新增 19–26（模型定义/执行器/层组件/v1 内核/HF 适配/v0 兼容/分布式内核/入口协议）。
- 第四轮：新增 27–32（渲染器/插件可观测/剖析工具/模型家族/内核基建/Ray 三方库）。
- 期间拆分：`14-platforms` part1 15.2KB→5 段、`18-tool-parsers` part1 11.0KB→3 段；修复 `17-compilation` 1 处断链；清理空目录。
