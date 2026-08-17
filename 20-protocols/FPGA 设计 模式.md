---
aliases: ["fpga-design-patterns"]
title: FPGA 常用设计模式（RTL 范式）
tags: [fpga, verilog, vhdl, rtl, reference, active]
created: 2026-07-29
summary: >-
    FPGA 可复用的 RTL 设计模式：有限状态机(FSM)、流水线(Pipeline)、同步 FIFO 与异步 CDC FIFO、握手协议、AXI-Stream 数据流、仲裁器(Arbiter)。每个模式给出可综合写法、适用场景与坑点。配合 [[20-protocols/FPGA 2|FPGA 知识]] 与 [[50-reference/FPGA 用法|FPGA 使用方法]]。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.85
lifecycle: reviewed
---

# FPGA 常用设计模式（RTL 范式）

> 配合 [[20-protocols/FPGA 2|FPGA 知识]]（架构/时序）、[[50-reference/FPGA 用法|FPGA 使用方法]]（工具链/仿真）。本文给可直接套用的 RTL 范式。

## 1. 有限状态机（FSM）

最基础的"控制逻辑"范式。推荐 **Moore 型**（输出仅依赖状态）或 **Mealy 型**（输出依赖状态+输入）。用独热码（one-hot）编码对 FPGA 最友好（每个状态一个 FF，组合逻辑少、时序好）。

```verilog
typedef enum logic [2:0] {
    S_IDLE = 3'b001, S_RUN = 3'b010, S_DONE = 3'b100
} state_t;

state_t cur, nxt;
always_ff @(posedge clk or posedge rst)
    if (rst) cur <= S_IDLE; else cur <= nxt;

always_comb begin
    nxt = cur;
    case (cur)
        S_IDLE: if (start) nxt = S_RUN;
        S_RUN:  if (cnt == N-1) nxt = S_DONE;
        S_DONE: nxt = S_IDLE;
    endcase
end
// 输出用单独 always_ff/assign，避免锁存器
assign busy = (cur != S_IDLE);
```

**坑**：组合逻辑里忘记给 `nxt` 赋默认值会综合出锁存器（latch），既占资源又难满足时序。务必 `nxt = cur;` 打底。

## 2. 流水线（Pipeline）

把长组合逻辑切成多级，每级间插寄存器，提高 **Fmax** 与吞吐（吞吐↑，但单笔延迟↑、面积↑）。

```verilog
// 三级流水线：a*b + c
reg [31:0] p1_a, p1_b, p2_c;
reg [63:0] p2_mul;
always_ff @(posedge clk) begin
    p1_a <= a; p1_b <= b;          // 级1：打拍输入
    p2_mul <= p1_a * p1_b;         // 级2：乘法
    p2_c <= p1_c;
    result <= p2_mul + p2_c;       // 级3：相加
end
```

适用：DSP、FIR、矩阵乘、报文解析头字段提取。权衡：延迟敏感场景（如需要"下一拍就出结果"）不适合深流水。

## 3. 同步 FIFO（同频同域）

用双端口 BRAM 或分布式 RAM + 读写指针（二进制或格雷码）。Xilinx 直接用 `xpm_fifo_sync`、Intel 用 `scfifo` IP，比手搓稳。

```verilog
// 手搓最小同步 FIFO（基于寄存器阵列，浅深度演示）
reg [W-1:0] mem [0:D-1];
reg [$clog2(D)-1:0] wr, rd;
wire full  = (wr+1 == rd);
wire empty = (wr == rd);
always_ff @(posedge clk) if (!full && wen) mem[wr] <= din, wr <= wr+1;
always_ff @(posedge clk) if (!empty && ren) dout <= mem[rd], rd <= rd+1;
```

## 4. 异步 FIFO（跨时钟域 CDC）

多比特总线跨域的标准解：双端口 RAM + **格雷码（Gray code）指针**跨域同步（格雷码每次只变 1 位，同步时不会读错中间值），判空满比指针。

```verilog
// 要点（Verilog 示意）
// 1) 写指针 wr_ptr 经 Gray 编码后，用 dst 域 2-FF 同步器同步为 wr_ptr_gray_sync
// 2) 读指针 rd_ptr 同理同步到 src 域
// 3) 空：rd_ptr_gray == wr_ptr_gray_sync；满：高两位相反且低位相同
// 推荐直接用 Xilinx xpm_cdc_gray + xpm_fifo_async 或 Intel dcfifo
```

**不要**手搓除非必要——CDC FIFO 的空满判定极易出错，优先用原厂 IP。详见 [[50-reference/FPGA 用法|FPGA 使用方法]] §CDC。

## 5. 握手协议（Valid/Ready）

反压（backpressure）的标准范式，广泛用于 AXI：

```verilog
// 发送方：valid 表示数据有效；接收方：ready 表示可接收
// 传输发生在 valid && ready 同一拍
always_ff @(posedge clk or posedge rst)
    if (rst) valid <= 0;
    else if (ready) valid <= 0;          // 被接收后拉低
    else if (have_data) valid <= 1;      // 有数据则置位

assign transfer = valid && ready;        // 本拍发生一次传输
```

规则：
- `ready` 可以不等 `valid` 提前拉高（早就绪）；`valid` 一旦拉高，**在 ready 拉高前不能撤销**（必须保持数据稳定直到握手成功）。
- 用 `transfer` 信号推进状态机/计数/写 RAM。

## 6. AXI-Stream 数据流

AXI4-Stream 是 FPGA IP 互联的事实标准（Xilinx AXI4、Intel Avalon-ST 类似）。核心信号：`tvalid`/`tready`（握手）、`tdata`、`tlast`（包尾）、`tkeep`（字节有效）、`tuser`（侧带，如包起始）。

```verilog
// 一个"透传并打一拍"的 AXI-S slave->master
always_ff @(posedge clk) begin
    if (s_axis_tvalid && m_axis_tready) begin
        m_axis_tdata  <= s_axis_tdata;
        m_axis_tlast  <= s_axis_tlast;
        m_axis_tuser  <= s_axis_tuser;
    end
end
assign m_axis_tvalid = s_axis_tvalid;             // 透传 valid（可加寄存器改善时序）
assign s_axis_tready = m_axis_tready;             // 反压直传
```

设计习惯：模块间用 AXI-S 对齐接口 → 便于用厂商 DMA（AXI-DMA）、互联 IP（AXI Interconnect）拼接数据通路。

## 7. 仲裁器（Arbiter）

多主设备竞争同一从设备（如多个流共享一个 DDR 控制器口）。常用**轮询（round-robin）**避免饿死：

```verilog
// 简化轮询仲裁：req[N-1:0] -> grant[N-1:0]（独热）
reg [$clog2(N)-1:0] last_grant;
always_ff @(posedge clk or posedge rst) begin
    if (rst) last_grant <= 0;
    else if (|grant) last_grant <= grant_idx;
end
// 组合逻辑：从 last_grant 下一位起找第一个 req=1 的授权
```

变体：固定优先级（简单但可能饿死）、加权轮询（QoS）、严格优先级+超时。

## 8. 模式选型速查

| 需求 | 选 |
|---|---|
| 顺序控制 / 协议解析 | FSM |
| 高吞吐计算、长组合路径 | Pipeline |
| 同域速率匹配 / 缓冲 | 同步 FIFO |
| 跨时钟域传多比特 | 异步 FIFO |
| 模块间反压流控 | Valid/Ready 握手 / AXI-S |
| IP 互联标准化 | AXI-Stream |
| 多主共享资源 | 仲裁器 |

## 延伸

- 知识：[[20-protocols/FPGA 2|FPGA 知识]]
- 用法：[[50-reference/FPGA 用法|FPGA 使用方法]]
- 验证：[[50-reference/FPGA 验证|FPGA 验证方法]]
- 厂商/工具：[[entities/FPGA 厂商|FPGA 厂商与开源工具链]]
