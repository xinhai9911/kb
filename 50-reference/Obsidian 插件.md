---
aliases: ["obsidian-plugins"]
title: Obsidian 已安装插件说明
category: reference
tags: [obsidian, plugin, tooling, kb]
created: 2026-07-30
updated: 2026-07-30
summary: >-
  记录本 vault（Q:\AI\kb）实际安装的 Obsidian 插件：11 个社区插件（含版本与用途）
  与 29 个已启用核心插件，并为每个插件提供详细使用说明（安装/配置/在本库的具体操作）。
base_confidence: 0.95
lifecycle: reviewed
---

# Obsidian 已安装插件说明

本文档记录本 vault（`Q:\AI\kb`）**当前实际安装**的 Obsidian 插件，数据取自
`.obsidian/community-plugins.json` 与各插件 `manifest.json`（版本号为安装时真实值）。
配套阅读：[[50-reference/Obsidian 用法|Obsidian 使用方法]]。

> 插件列表通过 `cat .obsidian/community-plugins.json` 与 `.obsidian/plugins/*/manifest.json`
> 实地读取，未凭记忆编造。

## 一、社区插件一览（11 个）

| 插件 | 版本 | 一句话用途 |
|------|------|-----------|
| **Dataview** | 0.5.68 | 用 DSL 查询 frontmatter，生成动态表格/列表 |
| **Excalidraw** | 2.25.3 | 在笔记内画手绘草图 / 4D 视觉 PKM |
| **Excalidraw Extras** | 0.0.15 | Excalidraw 的高权限/大组件伴侣插件 |
| **Admonition** | 11.0.0 | 增强型 callout（可折叠、自定义块） |
| **obsidian-git** | 2.38.6 | Git 版本控制集成，自动备份/提交/同步 |
| **Templater** | 2.20.6 | 高级模板与自动化（类 handlebars 语法） |
| **PDF++** | 0.40.31 | 最"原生"的 PDF 标注工具 |
| **Mind Map** | 1.1.0 | 把笔记预览成 Markmap 思维导图 |
| **Omnisearch** | 1.30.1 | "开箱即用"的全文搜索引擎 |
| **Importer** | 1.8.12 | 从 Notion/Evernote/OneNote/Roam 等导入 |
| **Open in Terminal** | 0.10.1 | 在终端打开 vault / 跑 CLI / 快速 Git 命令 |
| **Kanban** | 2.0.51 | 基于 markdown 的看板 |

## 二、各插件详细使用说明

下面逐个插件说明 **安装/启用 → 关键配置 → 在本库的具体操作 → 小贴士**。
（安装路径统一为：左下角「设置 ⚙」→「社区插件」→ 关闭「安全模式」→「浏览」→ 搜插件名 → 安装 → 启用。）

### 2.1 Dataview（0.5.68）

**是什么**：把 vault 当成数据库，用类似 SQL 的 DSL 查询每篇笔记的 frontmatter / 行内字段，
生成动态表格或列表。笔记增删改后视图自动刷新。

**关键配置**
- 设置 → Dataview → 打开「Enable JavaScript Queries」（如需高级查询）。
- 默认渲染内联字段（`[key:: value]`）即可，无需额外配置。

**在本库的操作示例**
1. 打开 `projects/README` —— 其「速览表」已用 Dataview 渲染（见 [[50-reference/Obsidian 插件|下文]]）；
   新增示例工程只要在对应 README 写好 frontmatter，表格自动出现新行。
2. 汇总某主题笔记（命令面板 `Dataview: Table`)：
   ```dataview
   TABLE summary FROM #crypto SORT updated DESC
   ```
3. 列出所有 `lifecycle: draft` 待审笔记：
   ```dataview
   LIST FROM "" WHERE lifecycle = "draft"
   ```

**小贴士**
- 字段只在 **frontmatter** 或 **行内 `[key:: value]`** 时才可被查询；正文里的普通文字查不到。
- 与核心插件 `bases` 功能重叠，简单表格用 Dataview `TABLE` 更灵活。

### 2.2 Excalidraw（2.25.3）+ Excalidraw Extras（0.0.15）

**是什么**：在笔记里插入可手绘的 Excalidraw 画布（存为 `*.excalidraw.md`，仍是纯文本、
可纳入 Git）。Extras 提供脚本、大组件等高级能力。

**关键配置**
- 命令面板 → `Excalidraw: Create a new drawing` 新建；或在笔记里输入 ```` ```excalidraw ```` 代码块内嵌。
- Extras 一般随 Excalidraw 自动启用，无需单独配置。

**在本库的操作示例**
- 协议分析、架构图适合手绘：库内已有 `Excalidraw/Drawing 2026-07-30 11.38.24.excalidraw.md`
  可参考。
- 画完在文档里用 `![[Drawing 2026-07-30 11.38.24.excalidraw.md]]` 嵌入，或用代码块内嵌。

**小贴士**
- 画布文件也是双链笔记，可在 `[[...]]` 中引用，纳入关系图谱。
- 手绘草图比截图更易版本化（diff 友好）。

### 2.3 Admonition（11.0.0）

**是什么**：增强 Obsidian 原生的 callout，支持自定义类型、可折叠块、嵌套。

**关键配置**
- 设置 → Admonition → 可新增自定义类型（如 `warning`、`todo`），指定图标与颜色。
- 本库已用原生 callout 语法 `> [!note]` / `> [!info]` 等，Admonition 让它们更美观/可折叠。

**在本库的操作示例**
- 写注意事项：
  ```markdown
  > [!warning] 编译注意
  > 动态模块务必加 `--with-compat`，否则加载崩溃。
  ```
- 折叠块：在类型后加 `-` → `> [!note]- 点开看细节`。

**小贴士**
- 自定义类型建议与全库约定一致（如统一用 `note/info/warning/tip`），避免风格发散。

### 2.4 obsidian-git（2.38.6）

**是什么**：把 vault 接入 Git，支持自动提交、拉取、推送、查看文件历史。本库 `Q:\AI\kb`
本身就是 Git 仓库，此插件直接可用。

**关键配置**
- 设置 → Git → `Vault backup interval (minutes)` 设自动提交间隔（如 10）。
- `Auto push` / `Auto pull` 按需要开启（多设备同步时建议开 pull）。
- `Commit message` 模板可设成 `vault backup: {{date}}`。

**在本库的操作示例**
- 命令面板 `Git: Commit all changes` 手动提交；`Git: Open source control view` 看改动。
- 配合提交约定（`<type>: <subject>`），可在插件里自定义提交信息格式。
- 误删笔记：`Git: View file history` → 找回历史版本。

**小贴士**
- 自动提交会频繁产生 commit；若介意，可只开「手动提交」+ 定期 `Git: Commit`。
- Windows 上需先装 Git 且 `git` 在 PATH；否则插件报"找不到 git"。

### 2.5 Templater（2.20.6）

**是什么**：高级模板引擎，支持变量、JS 脚本、文件/日期自动填充，比核心 `templates` 更强。

**关键配置**
- 设置 → Templater → `Template folder location` 指向放模板的目录（如 `30-snippets/`）。
- 可设「Trigger Templater on new file」自动套用。

**在本库的操作示例**
- 建一个 frontmatter 模板（`30-snippets/note-template.md`）：
  ```markdown
  ---
  title: <% tp.file.title %>
  category: <%* if (tp.file.path().includes("concepts")) { %>concepts<%* } %>
  tags: []
  created: <% tp.date.now("YYYY-MM-DD") %>
  updated: <% tp.date.now("YYYY-MM-DD") %>
  summary: ""
  base_confidence: 0.6
  lifecycle: draft
  ---
  ```
- 新建笔记时 `Templater: Create new note from template` 选它，日期自动填好，避免漏字段。

**小贴士**
- 与核心 `templates` 二选一即可；需要条件/JS 逻辑时用 Templater。
- 模板文件本身会被 Dataview/图谱当成普通笔记，建议放在 `30-snippets/` 并用 `tags` 排除。

### 2.6 PDF++（0.40.31）

**是什么**：增强 PDF 阅读与标注，标注可双向链接到笔记，是读论文/报告的利器。

**关键配置**
- 设置 → PDF++ → 可开启「Annotation link」让高亮生成可点击回链。
- 配合核心 `backlink`，标注会反向出现在对应概念笔记里。

**在本库的操作示例**
- 打开 `sources/`、`50-reference/sources/` 下的论文 PDF（或外部 PDF）。
- 选中文字高亮 → 自动生成 `[[概念笔记]]` 式链接，回到对应 `concepts/`、`entities/` 笔记。
- 形成闭环：原始资料（PDF 标注）→ 知识卡片（双链笔记）。

**小贴士**
- PDF 文件本身不放进 vault 也能标注（PDF++ 读外部路径）；但放进来更利于统一版本。

### 2.7 Mind Map（1.1.0）

**是什么**：把当前笔记的 Markdown 标题层级渲染成 Markmap 思维导图，一键预览。

**关键配置**
- 一般无需配置；命令面板 `Mind Map: Preview` 即可。
- 视图可导出 PNG/SVG。

**在本库的操作示例**
- 打开长综述（`synthesis/加密算法技术全景综述.md` 等）→ `Mind Map: Preview`。
- 用 `#`/`##` 层级梳理知识骨架，导图帮助检查结构是否失衡（某一支过长）。

**小贴士**
- 思维导图只读当前文件的标题，跨文件关系还是看 Graph 更合适。

### 2.8 Omnisearch（1.30.1）

**是什么**：比 Obsidian 默认搜索更强的全文搜索引擎，模糊/近似匹配、中文友好。

**关键配置**
- 设置 → Omnisearch → 可开启「Index PDFs / Canvas」扩大索引范围。
- 它独立于核心 `global-search`，用命令面板 `Omnisearch: Open` 触发。

**在本库的操作示例**
- `Ctrl/Cmd+P` 输入 `Omnisearch: Open` → 搜「熔断」「ECDHE」「SM4」等中文关键词，
  命中率高于默认搜索（默认对中文分词较弱）。

**小贴士**
- 与默认搜索互补：精确短语用默认搜索，模糊/记不全用 Omnisearch。

### 2.9 Importer（1.8.12）

**是什么**：从 Notion、Evernote、Apple Notes、OneNote、Google Keep、Bear、Roam 等导入笔记。

**关键配置**
- 命令面板 `Importer: Open` → 选来源 → 按向导导入。
- 可勾选「Clean HTML」「Convert to Markdown」等。

**在本库的操作示例**
- 把外部资料库迁进来后，用 `00-index/how-to-use` 的分类体系重新归置到
  `concepts/`、`entities/`、`sources/` 等目录。

**小贴士**
- 导入后务必跑链接审计（见 [[50-reference/Obsidian 用法|Obsidian 使用方法]] 的维护流程），
  外部双链风格可能不一致。

### 2.10 Open in Terminal（0.10.1）

**是什么**：一键在 vault 根目录打开终端，或运行预设的 CLI/Git 命令。

**关键配置**
- 设置 → Open in Terminal → 指定终端类型（Windows 默认用系统终端 / PowerShell）。
- 可配置「在文件所在目录打开」还是「在 vault 根目录打开」。

**在本库的操作示例**
- 右键文件或命令面板 `Open in Terminal` → 直接开到 `Q:\AI\kb`。
- 在终端跑仓库级维护脚本：
  - `node _audit_links.js`（断链审计，临时脚本）
  - `wiki-lint`（frontmatter/链接规范检查）
  - `git status` / `git diff` 快速看改动

**小贴士**
- 与 obsidian-git 搭配：平时用插件按钮提交，复杂操作（rebase/分支）用此插件开终端做。

### 2.11 Kanban（2.0.51）

**是什么**：基于 markdown 的看板（数据存为 `.md`，可纳入 Git），适合管理待办/流程。

**关键配置**
- 命令面板 `Kanban: Create new board` → 新建看板文件。
- 设置里可开启「Date / Time triggers」「Archive done cards」等。

**在本库的操作示例**
- 建 `10-projects/kb-tasks-kanban.md`，列如「待补实体 / 待审 draft / 进行中 / 已完成」。
- 把审计发现的缺口（如 `coppola-francis` 等缺失实体）做成卡片，补完即拖到「已完成」。

**小贴士**
- 看板文件也是笔记，会被图谱/搜索收录；建议用 `tags: [kanban]` 标记并在 Dataview 里排除或汇总。

## 三、与本库工作流强相关的组合

- **Dataview + frontmatter**：让 `projects/README` 速览表自动跟随文件更新（见下文第四节）。
- **obsidian-git + Open in Terminal**：版本与维护闭环（自动备份 + 终端跑 lint/审计）。
- **Templater + 核心 templates**：统一 frontmatter，避免漏字段。
- **Excalidraw + 双链**：架构/协议图可版本化、可跳转。
- **PDF++ + 双链**：源文献标注回链到知识卡片，形成资料闭环。
- **Omnisearch + 默认搜索**：中文模糊检索互补。

## 四、用 Dataview 把 projects/README 速览表自动化

`projects/README` 的「速览表」已用 Dataview 渲染。原理：每个示例工程 README 写好
frontmatter 字段（`topic` / `stack` / `deps` / `run` / `docs`），再由如下查询聚合：

```dataview
TABLE topic AS "主题", stack AS "语言/栈", deps AS "依赖", run AS "一键启动", docs AS "对应文档"
FROM "projects"
WHERE project = true
SORT file.name ASC
```

新增工程只需在它的 README 加 `project: true` 与那几个字段，表格自动多出一行，
无需手改 `projects/README`。

## 五、已启用的核心插件（29 个）

下列核心插件处于启用状态（取自 `.obsidian/core-plugins.json`）：

`file-explorer`（文件树）、`global-search`（全局搜索）、`switcher`（快速切换）、
`graph`（关系图谱）、`backlink`（反向链接）、`canvas`（画布）、`outgoing-link`（出链）、
`tag-pane`（标签面板）、`footnotes`（脚注）、`properties`（属性）、`page-preview`（悬浮预览）、
`daily-notes`（日记）、`templates`（核心模板）、`note-composer`（笔记组合）、
`command-palette`（命令面板）、`editor-status`（编辑器状态）、`bookmarks`（书签）、
`markdown-importer`（Markdown 导入）、`random-note`（随机笔记）、`outline`（大纲）、
`word-count`（字数统计）、`slides`（幻灯片）、`audio-recorder`（录音）、`workspaces`（工作区）、
`file-recovery`（文件恢复）、`publish`（发布）、`sync`（同步）、`bases`（Bases 数据库视图）、
`webviewer`（网页查看）。

> 其中与本库日常最相关：`graph`（看知识拓扑/孤岛）、`backlink`（看引用关系）、
> `outline`（长综述导航）、`tag-pane`（按 `tags` 聚合）、`templates`/`properties`
> （配合 frontmatter）、`bases`（Obsidian 原生的表格/数据库视图，可替代部分 Dataview 场景）。

## 六、维护建议

- **新增插件前**：先在 `community-plugins.json` 确认，再在文档「一、社区插件一览」表补一行
  （含真实版本号，从 `manifest.json` 读）。
- **版本升级后**：同步更新本表版本号，避免文档与实际不符。
- **本库已装插件覆盖的场景**：检索（Omnisearch/全局搜索）、版本（Git/Open in Terminal）、
  模板（Templater/核心 templates）、可视化（Excalidraw/Mind Map/Graph/Canvas）、
  资料导入（Importer/PDF++/markdown-importer）、任务管理（Kanban）、动态视图（Dataview/Bases）。
  基本无需再装额外插件即可支撑现有知识库工作流。

## 参考链接

- [[50-reference/Obsidian 用法|Obsidian 使用方法]] — 上手与日常维护流程
- [[50-reference/标注 规范|全库 Callout 使用清单与规范]] — 各类型约定与待补候选
- [[00-index/如何 使用|如何使用本知识库]] — 分类体系与 frontmatter 规范
- 插件数据来源：`.obsidian/community-plugins.json`、`.obsidian/plugins/*/manifest.json`
