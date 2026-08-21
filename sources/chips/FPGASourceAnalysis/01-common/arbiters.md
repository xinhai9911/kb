# 包/请求调度原语族（common/arbiters）

> 覆盖 rtl/common/ 的 `bus_c_sch`、`pkt_with_rdy_sch`、`rd_req_sch` 三个 N→1 复用调度器：共同的「每路输入 sc_fifo_idx 缓冲 + FSM 选路 + 包粒度/拍粒度放行」架构，差异在总线格式与放行策略。不复述综述（综述仅一句 `bus_c_sch / pkt_with_rdy_sch`）。

## 1. 三者定位一览

| 模块 | 输入总线 | 粒度 | FSM | 核心用途 |
|---|---|---|---|---|
| bus_c_sch | `BUS#(DW,CHW)::C`（vld/sop/eop/left/data/ch） | 整包（一次选路放行到 eop） | IDLE/SEL（2 态） | 多路并行流水线汇聚（eth_rx、DMA 上行、DDR 会话写） |
| pkt_with_rdy_sch | 扁平位宽 `[BUSW-1:0]`（vld 在最高位、eop 在 EOP_BIT） | 整包 + 下游 ready 逐拍反压 | IDLE/SEL/WAIT（3 态，WAIT 实际不可达） | 带 ready 的 AXIS 式汇聚（NUMA 交叉、跨卡） |
| rd_req_sch | `BUS#(DW,0)::B`，sop==eop（单拍请求） | 单拍（一拍出队一次） | IDLE/SEL | DDR 读请求仲裁（2 源表读 + 主机调试读） |

> 注意：bus_c_sch / rd_req_sch 实际为 **2 态**（IDLE/SEL）；仅 `pkt_with_rdy_sch` 枚举含 WAIT（SEL 直接回 IDLE，WAIT 不可达）。「WAIT+优先级+RR」的概括以代码实际为准。

## 2. bus_c_sch —— BUS::C 整包调度

```systemverilog
module bus_c_sch #(
    parameter N_NUM = 4, DEPTH = 7, DW = 256, CHW = 120, AFULL = 48,
    parameter BUS_W = DW+CHW+$clog2(DW/8)+3
)(
    input  logic clk, rst,
    input  [N_NUM-1:0][BUS_W-1:0] pkt_din,   // N 路 C 总线展平输入
    output [BUS_W-1:0]            pkt_dout   // 单路 C 总线输出（寄存器输出）
);
```

| 参数/信号 | 位宽/方向 | 说明 |
|---|---|---|
| N_NUM | 输入通道数 | 默认 4，最大表格解码到 8（`DUMMY_DATA_GEN` 把 N_NUM..7 的 `cur_rdy_sel` 拉 0） |
| DEPTH | FIFO 深度 | ≤7 用 distributed RAM，否则 block RAM |
| AFULL | 伪满阈值 | 写指针距离满多少后置 afull |
| pkt_no_drop[i] | 每路 1bit | sop 拍采样 `~fifo_afull`；为 0 时该包整体丢弃（`fifo_in_vld = pkt_din_d.vld & pkt_no_drop`） |

**逐路数据通路**（generate `CH_DATA_GEN`，每路相同）：
1. 输入打一拍 `pkt_din_d`（C 总线字段全量寄存）。
2. `sc_fifo_idx` 缓冲（DEPTH×BUS_W），入读节拍分离：
   - 写：`fifo_in_vld = pkt_din_d[i].vld & pkt_no_drop[i]`；
   - 读：`fifo_rdy = fifo_rdy[i][1] & next_rdy_sel[i]`（仅被选中的路可出队）。
3. FIFO 输出再打一拍 `pkt_dpre`（作为 FSM eop 判决点与输出数据源）。
4. 出队判决信号：
   - `fifo_rdy[i][0] = fifo_threshold=='h0 ? ~fifo_empty : fifo_threshold`，`fifo_threshold = wr_data_count[DEPTH-2]` —— 即「水位低于一半时看非空、接近满时看水位位」，用作 IDLE 选路的 rdy 判据。
   - `fifo_rdy[i][1] = ~(fifo_rd_vld & fifo_dout.eop)` —— 本拍若正读出的字是 eop，下一拍才允许接收新读命令。

**调度 FSM（IDLE/SEL）与优先级**：
```systemverilog
IDLE: case(1'b1) // 固定优先级：端口 0 最高
          cur_rdy_sel[0]: next_st=SEL; next_rdy_sel=7'h01;
          ...cur_rdy_sel[7]: ...
          default: IDLE, 7'h0;
SEL:  next_st = pkt_dpre[fifo_dsel].eop ? IDLE : SEL;   // 整包放行
      next_rdy_sel = pkt_dpre[fifo_dsel].eop ? 7'h0 : rdy_sel_d;
```
- `fifo_dsel` 由 `next_rdy_sel` one-hot 注册解码。IDLE 时按**固定端口优先级**（0 最高）选一个非空路；SEL 期间只让被选路持续出队直到其 eop，其余路 head-of-line 等待。
- 输出 `bus_pkt_dout <= pkt_dpre[fifo_dsel]`：**寄存器输出**，天然断掉组合路径。
- 反压：各输入路 `pkt_no_drop` 在包首对 afull 采样，afull 即丢整包（不半包写入）；`afull` 由 sc_fifo_idx 的 `wr_afull` 上送。

**实例化点（top 中的实际挂接）**：
| 实例 | 位置 | 参数 | 汇聚内容 |
|---|---|---|---|
| `ul_dma_sch_mux1` | top.sv `PROC_GEN` 内 | N_NUM=4, DEPTH=8, DW=256, CHW=48 | `ul_dma_sch_in[i*5+:4]`（黑名单旁路/未知包/ovb/position_check_match）→ `axis_rxq_in[i]` |
| `ul_pkt_sch0` | blacklist/blacklist_proc.sv | N_NUM=2, DEPTH=8, DW=256, CHW=CHW | 2 路黑名单流 `b_list_in` → `eth_din` |
| `ul_pkt_parsing_mux` | i_e_gress/eth_rx_pkt_sch.sv | N_NUM=3, DEPTH=7, DW/CHW/AFULL 穿透 | 3 路 MAC 收包（40G×2+10G）→ 解析前汇聚 |
| `ddr_sesstion_wr_mux` | top.sv DDR_GEN（i==0 专属） | N_NUM=4, DEPTH=6, DW=512, CHW=28 | 4 路 DDR 会话表写请求 → `ddr_wr_sch_out[0]` |

选路语义即「高优先级端口优先、一次放完整包」，靠「只有被选路出队、其余 FIFO 攒包」实现天然背压隔离。

## 3. pkt_with_rdy_sch —— 扁平 AXIS-ready 汇聚

| 特点 | 说明 |
|---|---|
| 输入 | `pkt_din[i][BUSW-1]`=vld、`pkt_din[i][EOP_BIT]`=eop、`pkt_din[i][DW-1:0]`=data（DW=BUSW-1）；**sop 与 vld 不对齐**（sop 恒 0，注释：sop 存在时不与 vld 对齐）、eop 与 vld 对齐 |
| 背压 | `pkt_din_rdy[i] = ~fifo_afull[i]`（输入 0 拍直通 ready）；输出 `pkt_dout_rdy` 参与 FIFO 读门控 |
| FIFO 读 | `fifo_rdy = ~(fifo_dout.vld&fifo_dout.eop) & rdy_sel_d[i] & pkt_dout_rdy` —— **逐拍**：下游 ready 才能读出一字，读到 eop 后停 |
| 水位 | `fifo_threshold[i] = \|wr_data_count[DEPTH-1 -:2]`（顶 2 位或），`cur_rdy_sel = threshold==0 ? ~empty : threshold` |
| 输出 | `pkt_dout = {选中路 vld, data}` **组合输出**（无末级寄存器，靠读门控对齐时序） |

FSM：SEL 检出 `fifo_dout[fifo_dsel].eop` 回 IDLE；`next_rdy_sel` 在 SEL 保持 `rdy_sel_d`。WAIT 态存在（next_st=IDLE, next_rdy_sel=0）但当前数据流不会进入，属预留。

**实例化点**：`forward/crs_crd_numa.sv` 与 `forward/up_numa.sv`，均 N_NUM=2, DEPTH=9, `BUSW=MUX_DW`、`EOP_BIT=MUX_DW-2` —— 把跨卡/NUMA 通道两侧 dc_fifo 输出 2→1 汇聚，配合 `pkt_dout_rdy` 实现跨卡忙时逐拍反压。这解释了该项目为什么要单独做一个「with ready」版本而非复用 bus_c_sch：NUMA 输出要给下游 AXI 侧按拍握手。

## 4. rd_req_sch —— 单拍请求仲裁

| 特点 | 说明 |
|---|---|
| 输入 | 展平 `[DW+LF+2:0]`，内部作 `BUS#(DW,0)::B`：sop==eop==vld（单拍请求，`pkt_din_d.sop <= pkt_din.vld`） |
| LF | `left` 字段宽度参数（DDR 请求只携带碰撞检测用的左移信息；实例化时 `DW=C1_APP_ADDR_WIDTH=28, LF=2`，`left`=$clog2(DW/8) 需与 LF 匹配，否则位宽不一致，使用方需自洽） |
| FIFO | `sc_fifo_idx`，RAM_TYPE 固化 "distributed"、AFULL=10 |
| 读使能 | `fifo_rdy[i] = ~fifo_empty[i] & next_rdy_sel[i]`（仅被选路出队 1 拍） |
| FSM | IDLE：固定优先级选 `~fifo_empty` 首路；SEL：**下一拍直接回 IDLE**（单拍语义，不等待 eop） |
| 输出 | `pkt_dpre` 再打一拍后 `bus_pkt_dout <= pkt_dpre[fifo_dsel]`，共 2 拍延迟 |

**实例化点**：top.sv `DDR_GEN` 内 `rd_req_sch1`（N_NUM=2, DEPTH=6, DW=C1_APP_ADDR_WIDTH=28, LF=2）—— 汇聚 2 个来源的 DDR 读地址请求：
1. `db_rd_req_fifo`（`dc_fifo_across`，clk_100m_in→sys_clk）：top_mem_map 的 DDR 调试读口 `DDR_DB_RD_A0`（主机经 LBS 发起的 DDR 直读）；
2. 会话/表查询的 cfg 读请求 `rd_req_sch_in[...]` 的另一路。
输出经 `cfg_req_fifo`（`dc_fifo_across`，sys_clk→ui_clk）进 DDR 用户接口（MC UI 时钟域），`ui_clk` 侧再用 `sc_fifo_ctrl/sc_fifo_idx` 做请求-响应配编址（见 fifo-primitives.md）。这是「读请求压缩成单拍、多源仲裁一次一拍」的典型用法。

## 5. 横向小结（可复用要点）

- 同构外腔：三者为 `sc_fifo_idx` per-channel 缓冲 + one-hot 选路表格 + 末级打拍，改总线格式只换打包结构。
- 包丢弃统一：sop 拍采样 afull 得 `no_drop`，afull 即整包丢（丢包在入口，FIFO 不含半包）。
- 粒度选型：整包 bus_c_sch、逐拍握手 pkt_with_rdy_sch、单拍请求 rd_req_sch。
- 优先级固定（端口 0 最高），无真正 round-robin，靠包粒度自然公平。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)