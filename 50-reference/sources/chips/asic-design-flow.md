---
title: ASIC 芯片设计全流程
tags: [chip, asic, eda, design, tsmc, flow, active]
created: 2026-08-07
summary: >-
    ASIC（专用集成电路）设计全流程：RTL 设计→功能仿真→综合→STA→布局布线→签核→流片→封装→测试。前端/后端分工、EDA 工具链（Synopsys/Cadence/Siemens）、设计方法学（DFT/UPF/形式验证）、工艺节点选择、成本估算。
category: reference
updated: 2026-08-07
sources:
  - synopsys.com
  - cadence.com
base_confidence: 0.82
lifecycle: draft
---

# ASIC 芯片设计全流程

> 从一行 Verilog 到一颗上亿晶体管的芯片，ASIC 设计是一条精密的工业流水线。本文梳理全流程、前端/后端分工、EDA 工具链、关键检查点和成本结构。

## 1. 全流程概览

```
规格定义 ──► RTL 设计 ──► 功能仿真 ──► Lint/CDC ──► 综合(Synth)
                                                   │
                  ┌────────────────────────────────┘
                  ▼
              门级网表 ──► 形式验证 ──► STA ──► DFT 插入
                                                   │
                  ┌────────────────────────────────┘
                  ▼
              布局布线(P&R) ──► 签核 Sign-off ──► GDS-II ──► 流片(Tapeout)
                                                                    │
                  ┌─────────────────────────────────────────────────┘
                  ▼
              晶圆制造(Wafer) ──► 封装(Package) ──► 测试(Test) ──► 出货
```

## 2. 前端（Front-End）：RTL → 网表

### RTL 设计

| 任务 | 说明 | 工具 |
|------|------|------|
| 架构设计 | 微架构、接口定义、时钟规划 | Visio/手写 |
| RTL 编写 | Verilog/SystemVerilog/VHDL | VS Code + LSP |
| Lint 检查 | 代码规范、可综合性 | Spyglass/Verilator |
| CDC 检查 | 跨时钟域正确性 | Spyglass CDC/Quartus CDC |
| 功能仿真 | Testbench 验证 | VCS/QuestaSim/Xcelium |

### 综合（Logic Synthesis）

将 RTL 映射到标准单元（Standard Cell）门级网表：

```
RTL (Verilog)
    │
    ▼  综合工具 (Design Compiler / Genus)
    │  输入: RTL + 约束(SDC) + 标准单元库(.lib)
    │
门级网表 (Netlist)
    │  输出: .v (门级) + .sdc (时序约束) + .lib (时序/功耗)
```

关键输出：
- **面积（Area）**：标准单元占用数
- **时序（Timing）**：WNS/TNS 是否满足
- **功耗（Power）**：动态 + 静态

### 形式验证（Formal Verification）

数学证明 RTL 与网表功能等价，**无需测试激励**：
- **LEC（Logic Equivalence Check）**：RTL vs 网表逐信号比对
- **Model Checking**：证明属性恒成立

## 3. 后端（Back-End）：网表 → GDS-II

### 布局布线（Place & Route）

```
门级网表
    │
    ▼  布局 (Placement)
    │  将标准单元放到芯片区域
    │
    ▼  时钟树综合 (CTS)
    │  插入 Buffer 保证时钟偏斜(Skew)最小
    │
    ▼  布线 (Routing)
    │  金属连线连接所有单元
    │
    ▼  签核 (Sign-off)
    │  STA + DRC + LVS + 功耗分析
    │
GDS-II 文件 (版图数据)
```

### 签核检查（Sign-off）

| 检查 | 说明 | 工具 |
|------|------|------|
| **STA** | 静态时序分析，全角/全工艺 | PrimeTime |
| **DRC** | 设计规则检查（最小线宽/间距） | Calibre/ICV |
| **LVS** | 版图 vs 网表一致性 | Calibre/ICV |
| **ERC** | 电气规则检查 | Calibre |
| **IR Drop** | 电源网络压降分析 | RedHawk/Predictive |
| **EM** | 电迁移检查 | RedHawk |
| **功耗分析** | 动态/静态功耗 | PrimePower |

## 4. DFT（可测试性设计）

在 RTL 中插入测试逻辑，确保制造后可测试：

| DFT 技术 | 说明 |
|----------|------|
| **Scan Chain** | 将所有寄存器串成扫描链，可逐位读写 |
| **BIST（内建自测试）** | 芯片内部生成测试向量 |
| **MBIST** | Memory 内建自测试（BRAM/SRAM） |
| **ATPG** | 自动测试向量生成 |
| **JTAG/Boundary Scan** | IEEE 1149.1 边界扫描 |

## 5. EDA 工具链

| 阶段 | Synopsys | Cadence | Siemens EDA |
|------|----------|---------|-------------|
| 仿真 | VCS | Xcelium | QuestaSim |
| Lint/CDC | Spyglass | — | Questa CDC |
| 综合 | Design Compiler (DC) | Genus | — |
| STA | PrimeTime | Tempus | — |
| P&R | IC Compiler II (ICC2) | Innovus | — |
| DFT | DFT Compiler | Modus | — |
| 签核 DRC/LVS | IC Validator | Pegasus | Calibre |
| 功耗 | PrimePower | Voltus | — |
| 形式验证 | Formality | JasperGold | Questa Formal |
| 物理验证 | StarRC (寄生提取) | Quantus (QRC) | — |

## 6. 工艺节点

| 节点 | 代工厂 | 典型应用 | 掩模成本（估算） |
|------|--------|---------|:--------------:|
| 28nm | TSMC/中芯国际 | IoT/汽车/工业 | ~$2M |
| 14nm | TSMC/中芯国际 | 移动/网络 | ~$5M |
| 7nm | TSMC | 高端 SoC/AI | ~$15M |
| 5nm | TSMC/三星 | 旗舰手机/AI | ~$30M |
| 3nm | TSMC | 最先进 AI/HPC | ~$50M+ |

**选择逻辑**：
- 成本敏感/量产大 → 尽量用成熟节点（28nm/14nm）
- 性能极致 → 7nm/5nm/3nm
- 国产化 → 中芯国际（28nm/14nm 可用）

## 7. 成本结构

```
设计成本 (NRE)
├── EDA 工具许可    ~$1-5M/年（全套）
├── IP 授权         ~$0.5-10M（ARM/SerDes/PHY 等）
├── 设计人力        ~$5-20M（10-50 人团队 × 1-2年）
├── 掩模(Mask)      ~$2-50M（取决于工艺）
└── 测试设备        ~$0.5-2M

量产成本
├── 晶圆            ~$3000-15000/片（12寸）
├── 封装            ~$0.5-5/颗
└── 测试            ~$0.1-2/颗
```

一颗 28nm 的中等规模芯片（~50M 晶体管）：
- NRE 总成本：~$10-20M
- 量产单位成本：~$5-15/颗
- 盈亏平衡：~100-500 万颗

## 8. ASIC vs FPGA vs CPU 对比

| 维度 | ASIC | FPGA | CPU |
|------|------|------|-----|
| 开发周期 | 12~24 月 | 1~6 月 | 0（软件） |
| NRE 成本 | $10M+ | ~$0 | ~$0 |
| 单位成本 | $1~50 | $100~5000 | $100~5000 |
| 性能/功耗 | 最优 | 中 | 低 |
| 灵活性 | 无 | 高 | 最高 |
| 量产盈亏平衡 | >100 万颗 | 任意 | 任意 |

## 9. 国产 EDA 生态

| 厂商 | 产品 | 覆盖阶段 |
|------|------|---------|
| **华大九天** | Aether | 仿真/综合/P&R |
| **概伦电子** | NanoSpice/MEASURE | SPICE 仿真/噪声分析 |
| **芯华章** | 系列 | 验证（仿真/形式） |
| **国微集团** | 步天 | 综合/STA |
| **芯行纪** | UniVista | P&R |

## 延伸

- FPGA：[[20-protocols/fpga|FPGA 知识]]（ASIC 原型验证常用 FPGA）
- 高速接口：[[50-reference/sources/chips/serdes-phy|高速 SerDes/PHY]]（SerDes IP 是 ASIC 常见硬核）
- 交换芯片：[[50-reference/sources/chips/centec-ctc7132|盛科 CTC7132]]（典型 ASIC 产品案例）
- Zynq SoC：[[20-protocols/fpga-zynq-soc|Zynq SoC 开发]]（硬核 SoC 设计参考）
