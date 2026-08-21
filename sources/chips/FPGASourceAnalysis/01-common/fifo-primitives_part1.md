# 同步/异步 FIFO 与打排（common/fifo-primitives）– part1

> 覆盖 rtl/common/ 的 `sc_fifo_ctrl`、`sc_fifo_idx`（同步 FIFO 两代封装）、`dc_fifo_across`、`dc_fifo_c_ctrl`（异步跨时钟 FIFO）与 `dff`（打拍）。寄存器适配 `reg_axi_b`、整卡 `top_mem_map` 见 [part2](fifo-primitives_part2.md)。重点在握手协议、满/空/伪满逻辑与请求-响应编址，不回放综述。

## 1. 底层原语 fifo_sc / fifo_dc（项目内未提供源码）

`sc_fifo_ctrl/sc_fifo_idx` 例化 `fifo_sc`、`dc_fifo_across/dc_fifo_c_ctrl` 例化 `fifo_dc`。这两个模块**不在工程内**（rtl/ 与 ip/ 均无定义；sim/tb_top 下有使用例 tb_sc_fifo_top.sv），推断为 XPM 风格的可综合 FIFO，接口如下（依据封装侧反推），实现细节**待核实**：

| 信号 | 方向 | 含义 |
|---|---|---|
| wr_vld / wr_din / wr_busy | 写 | 写请求、数据；busy 时暂不接受 |
| wr_afull / wr_full | 写状态 | 伪满（可配阈值）/真满 |
| wr_data_count | 写状态(可选) | 占位计数器（仅 sc_fifo_idx 变体走此口） |
| rd_rdy / rd_vld / rd_dout | 读 | 读允许（rd_rdy 为 1 才出数）；rd_vld 为数据有效 |
| rd_aempty / rd_empty | 读状态 | 伪空/真空 |

关键点：**读出的组合路径是 rd_vld/rd_dout 与 rd_rdy 交叉**。sc_fifo_ctrl 用 `rd_vld = fifo_out_vld & fifo_rdy` 是纯组合读（无输出寄存）；sc_fifo_idx 用 `fifo_out_vld = rd_vld & fifo_rdy` 则读允许晚一拍、输出 `fifo_out` 直接来自 `rd_dout`，属**寄存输出型**。跨时钟 `fifo_dc` 的指针同步（格雷码双指针 + 同步链级数）在原语内部，封装层无显式 CDC 链。

## 2. sc_fifo_ctrl / sc_fifo_idx —— 同步 FIFO 两代封装

```systemverilog
module sc_fifo_idx #(parameter RAM_TYPE="block", DW=256, DEPTH=6, AFULL=10)(...);
// 写：fifo_in_vld/fifo_in；读：fifo_rdy / fifo_out_vld / fifo_out
```
- **写流水化**：`wr_vld_pre` 在 `fifo_in_vld` 来 1 拍后置起、`wr_full` 时清零；`wr_vld = (rst|wr_busy)?'b0:wr_vld_pre`，`fifo_in_d <= fifo_in` 同步打拍——即「先登记写请求，原语不忙时再执行」，保证即便 `fifo_sc` 写端有忙间隔也不丢。
- **差异表**：

| 项 | sc_fifo_ctrl | sc_fifo_idx |
|---|---|---|
| 读语义 | 输出 `fifo_out = fifo_out_pre`（`generate if(1)` 直通） | 输出 `fifo_out` 直连 `rd_dout` |
| 接口 | 只暴露 afull/empty，无 out_vld | 多 `wr_data_count[DEPTH-1:0]` 与 `fifo_out_vld` |
| 用途 | DDR 请求-响应路径、AXI 外设 | 调度器/哈希/协议检测等需水位判据处 |

- **请求-响应编址典型用法**（rtl/ddr_ctrl/ddr_ctrl.sv `inst_sc_fifo_ctrl`）：写 `d_rd_req`（读请求）→ `sc_fifo_idx`(DW=28 地址, distributed, DEPTH=6, AFULL=10) → 读端 `fifo_rdy=d_rd_res.vld`、`fifo_out=d_rd_res.addr` —— 同一 FIFO 同时完成「请求排队」与「响应编址回填」，读地址即写地址的镜像，保证 DDR 响应对齐原请求。`axi_master_0_axi_periph.v` 也用 sc_fifo_ctrl 做 AXI 通道缓冲。
- 仿真计数（`synthesis translate_off`）：`user_req_cnt / user_res_cnt / user_r_diff` 观测积压深度。

## 3. dc_fifo_across / dc_fifo_c_ctrl —— 异步跨时钟 FIFO

| 项 | dc_fifo_across | dc_fifo_c_ctrl |
|---|---|---|
| 数据 | 裸 `[DW-1:0]` 字 | 整个 `BUS#(DW,CHW)::C`（含 ch 侧带） |
| 数据宽度 | `DW` | `$bits(fifo_in)`（含 ch）打包进原语 |
| 写 | `wr_clk` 域登记 `wr_vld_pre` → `wr_vld`（同 sc 版写流水化） | 同左，`fifo_in.vld` 作登记源 |
| 读 | `fifo_out_vld = rd_vld & fifo_rdy`，直接输出 | 字段解包：`.sop/.eop/.data/.left/.ch` 来自 `fifo_out_pre`，`vld = rd_vld & fifo_rdy` |

- CDC 职责全在 `fifo_dc` 原语：写读指针跨域同步（标准格雷码 + 同步链，级数不可见，**待核实**）。封装只保证「写边登记一拍」与「读边握手一拍」。
- **实例化点**（top.sv `DDR_GEN` 周边，即会话表/DDR 控制跨时钟窗口）：
| 实例 | 类型 | 方向 | 用途 |
|---|---|---|---|
| db_rd_req_fifo | dc_fifo_across, distributed, DW=28, DEPTH=4, AFULL=6 | clk_100m_in → sys_clk | 主机 DDR 调试读请求（top_mem_map `DDR_DB_RD_A0`） |
| cfg_req_fifo | dc_fifo_across, block, DEPTH=7, AFULL=48 | sys_clk → ui_clk | 仲裁后的 DDR 读地址 → MC UI |
| ddr_cfg_fifo | dc_fifo_c_ctrl, distributed, DW=512, CHW=28, DEPTH=6, AFULL=6 | sys_clk → ui_clk | 会话表 512b 写配置 + 28b ch |
| rxq_data_fifo（axis_rxq_demux 内） | dc_fifo_across, block, DEPTH=9, AFULL=296 | wr_clk → rd_clk | DMA 收包数据（含 20b ch） |
> AFULL 阈值差异（6/48/296）反映各处背压余量取值不同。

## 4. dff —— 参数化打排寄存器

```systemverilog
module dff #(parameter FF_NUM=2, CHW=32)(
    input clk, rst,
    input BUS#(256,CHW)::C din, output BUS#(256,CHW)::C dout);
// generate: din_ff[i] <= (i==0)? din : din_ff[i-1];  dout = din_ff[FF_NUM-1];
```
- 无复位（纯数据通路对齐，数据位不必复位）；`rst` 端口存在但代码未用。
- **实例化点**：forward/crs_crd.sv 3 处（CHW=185/181），对跨卡转发表项/报文打 FF_NUM 级对齐，配合 `din_dff/dout_dff` 做链路延迟匹配——网卡流水线做通道对齐的最小原语。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)