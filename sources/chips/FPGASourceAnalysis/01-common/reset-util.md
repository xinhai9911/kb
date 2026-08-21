# 时钟/复位管理与周期工具（common/reset-util）

> 覆盖 rtl/common/ 的 `clk_rst_ctrl`（时钟/复位管理）、`timeout_gen`（秒级超时产生器）、`pps_async_cnt`（PPS 跨时钟计数）、`xadc_capture`（XADC 采集）。它们是控制面/运维面基础件，综述未展开。源路径统一记 rtl/common/xxx.sv；eth_reset 位于 rtl/eth/。

## 1. clk_rst_ctrl —— MMCM 时钟 + 系统复位 + 每口以太网复位

```systemverilog
module clk_rst_ctrl #(parameter ETH_NUM=4)(
    input clk,                    // 板级 100MHz 源时钟
    input [ETH_NUM-1:0] stat_rx_bad_code/block_lock/status/local_fault/remote_fault,
    input [ETH_NUM-1:0] eth_core_rst, input [31:0] r_user_rst,
    output sys_clk, sys_rst, clk_100m_in, clk_005m_in,
    output [ETH_NUM-1:0] gt_rst_out, mac_rst_out, eth_led_en,
    output [ETH_NUM-1:0][31:0] eth_lnkdwn_cnt,
    output clk_100m_lock, clk_100m_unlock);
```

| 信号 | 生成逻辑 |
|---|---|
| clk_100m / clk_200m / clk_005m | `clk_100m` 时钟向导（MMCM）`clk_out1/2/3`，`locked`→`clk_lock` |
| sys_clk | = clk_200m_in（用户面 200MHz 主时钟） |
| sys_rst | `sys_rst_pre[3]`，`sys_rst_pre <= {sys_rst_pre[2:0], ~sys_rst_cnt[7]}`（4 级移位） |
| sys_rst_cnt | `NSFOCUS_KU060` 下 `posedge clk_100m_in or negedge clk_lock`：`~clk_lock` 异步清零；`r_user_rst[0]` 清零；`~sys_rst_cnt[7]` 时自增（计数到 128 饱和）。即 MMCM 失锁立即复位，锁后延时≥128 个 100M 周期 + 4 拍级联退出复位 |
| clk_100m_lock/unlock | `pll_lock_pre/unlock_pre` 4 级移位取 [3]：锁/失锁脉冲转电平，`max_fanout=999` 直通给用户面 |
| gt/mac_rst、eth_led_en、eth_lnkdwn_cnt | 每口例化 `eth_reset`（rtl/eth/eth_reset.sv，跑在 5MHz `clk_005m_in` 上），复位源 `pll_unlock_pre[0] \| eth_core_rst[i]` |

**eth_reset 链路状态机**（eth_reset.sv，CLK_FREQ=5MHz）：
```
eth_status        = stat_rx_status & stat_rx_block_lock & ~bad_code & ~local_fault & ~remote_fault
eth_reset_status  = ~stat_rx_block_lock | stat_rx_local_fault
cntr: 复位清 0；cntr<CLK_FREQ 自加；eth_reset_status & cntr>=CLK_FREQ → 清 0（重新计时）
gt_reset_out ≤ 10ms(50 cycle) 高有效; cnter≥1s(P周期) 且线路故障未消 → 周期复发
mac_reset_pre: gt_reset_out 期间拉高；gt 释放后 time_cnt 计数 100ms 末端再补 16 拍高 → mac_reset_out
lnkdwn_cnt: eth_status_r3 & ~eth_status_r2（status 下降沿）计数，clear_lnkdwn_cnt 清零
eth_status 3 级 async_reg 打拍 → eth_status_r3
```
即「失锁/故障持续 ≥1s → 拉 GT 复位 10ms → 100ms 后释放 MAC 复位」的 健康探测+复位序列。`eth_lnkdwn_cnt` 记录链路down次数，供软件诊断。

实例化：top.sv `inst_clk_rst_ctrl`（ETH_NUM 穿透），`stat_rx_*` 来自 40G/10G MAC。

## 2. timeout_gen —— us + 秒 两级时间戳/超时

```systemverilog
module timeout_gen #(parameter PERIOD=250e6, DW=48)(
    input clk, rst, gbl_timeout_ce,
    output [19:0] gbl_us_out, output [47:0] gbl_timeout, output gbl_s_unit_p);
```
- 三个 `dsp_macro_cnt`（DSP 式计数器原语）：`unit_us` 数时钟（US_PERIOD=PERIOD/1e6，每 us 清零）、`unit_1s` 数 us（SUB_PERIOD=1e6，每 1s 清零）、`gbl_timeout_pre` 数秒（使能 `gbl_timeout_ce`，48b 秒计数）。
- **提前一拍清零**：`cnt_pulser[1][0] = unit_us[7:0]==(US_PERIOD-3)`（第 2 个计数器）清 `unit_us`；“us 域提前 3 拍还差 1 拍到达秒沿”触发 `cnt_pulser[2][0] = us==US_PERIOD-3 && unit_1s[19:0]==SUB_PERIOD-1` 清 `unit_1s`，`r_clear` 两级移相后：`gbl_us_out <= r_clear[1] ? 0 : unit_1s[19:0]`（0~999999 us 翻转）、`gbl_s_unit_p = cnt_pulser[2][0]`（秒脉冲）。
- 即：`gbl_us_out` 实际是「当前秒内 us 低 20 位」，`gbl_timeout` 从 0 上翻的**上电秒数**（48b 足够 8.9 千年不翻转）。
- top.sv `inst_timeout_gen`：KU060 下 `PERIOD=200e6`（sys_clk=200MHz），`gbl_timeout` → 会话老化（st_timeout）、`gbl_us_out` 供软件读时戳。

## 3. pps_async_cnt —— PPS 周期窗的跨时钟脉冲计数

```systemverilog
module pps_async_cnt #(parameter PERIOD=250_000_000, MODE=0, DW=32)(
    input clka, rsta, clkb, d_en, output [31:0] dout);
```
- clka 域：`pps_pul_cnt` 0~(PERIOD-1) 循环，`==PERIOD-1` 即每秒一个脉冲（clka=clk_005m、PERIOD=5e6 ⇒ 5MHz/5e6 = 1pps）。
- clkb 域：`sample_pul_d` 3 级移位同步该脉冲，`sample_pul_pos = sample_pul_d[2:1]=='b01`（**3 级 CDC 同步链 + 边沿检测**）。
- MODE=0（电平计数）：`d_en` 高期间 `pps_tmp0_cnt` 每拍 +1；PPS 沿时**快照**到 `pps_dout_cnt` 并重置（`d_en ? 1 : 0`）。
- MODE=1（脉冲计数）：`data_pul_d` 3 级同步 `d_en` 边沿，`data_pul_pos` 每脉冲 +1；PPS 沿快照重置。
- 数据并非实时，而是「上一 PPS 周窗内的计数快照」，天然抗跨时钟亚稳态又每 1s 刷新。

top.sv 三个实例（每组 XADC 对应）：
| 实例 | MODE | clkb | d_en | 统计 |
|---|---|---|---|---|
| inst0 | 0 | ui_clk[i*2] | d_rd_res[i*2].vld | DDR 读响应条数/秒 |
| inst1 | 0 | ui_clk[i*2] | d_rd_req[i*2].vld | DDR 读请求条数/秒 |
| inst2 | 1 | clk_005m_in | fpga_fan_fg | 风扇 FG 脉冲/秒（转速间接度量） |
输出各接 `ddr_rd_db[i*3+0..2]` → top_mem_map `DDR_RD_DB0..2` 寄存器，供软件轮询。

## 4. xadc_capture —— XADC 温度采集（AXI-Lite 只读）

- 实例化 `system_management_wiz_0`（System Management Wizard，XADC），把其 s_axi 从机口**全部常拉无效**（aw/w/ar `/1'b0`），改走 `channel_out/busy_out/temp_out` 数据通道被动读取。
- 时序：`cnt` 1 起步，等 `busy_out=='b10`（转换空闲/有效）→ 递增 `cnt`；`sync_rstn = ~(|cnt[3:1])` 复位向导（保持若干拍后释放）。
- 温度回读：`temp_out` 10-bit MSB justified → `s_axi_rdata <= {22'h0,temp_out[9:0]}`，每次 `busy_out` 变化打拍锁存（busy_out[1]<=busy_out[0] 打拍串接）。
- 地址形式 `{2'b00, channel_tb+9'h100, 2'b00}`（= 基址+0x400）为向导 AXI 数据窗，但因 aw/w/ar 恒 0 实际不产生读写，`temp_out` 直接作为结果。
- top.sv `GEN_XADC`（SIM_MODE==0 才综合）：clk_100m_in → `xadc_temp` → top_mem_map `XADC_TEMP`。

## 5. 小结要点

1. 复位策略：**MMCM 失锁异步复位 + 锁后计数延时 128 拍 + 4 级移位去毛刺**；以太网口复位由 eth_reset 独立 5MHz 健康探测（1s 判决 + 10ms GT + 100ms MAC）。
2. 所有周期工具（timeout_gen/pps_async_cnt）都标定在 `PERIOD`，同一时钟参数可跨工程复用；跨时钟一律 3 级同步链 + 边沿检测（pps_async_cnt 显式）。
3. `dsp_macro_cnt`（Xilinx 计数宏）同时服务 timeout_gen，未在工程内定义原语（**待核实**仿真/约束侧来源）。
4. XADC 用向导的被动通道而非 AXI 主动读写，节省主机访问复杂度。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)