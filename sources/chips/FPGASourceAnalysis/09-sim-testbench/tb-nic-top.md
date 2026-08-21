# tb_nic_top 整卡测试台解剖

> 源路径 `sim/nic_top/tb_top/tb_nic_top.sv`（约 480 行）、`sim/nic_top/tb_def/`、`sim/nic_top/tb_top/{tb_dc_fifo_top,tb_sc_fifo_top,tb_sp_ram_top,tb_tdp_top}.sv`。
> 本节补深综述 §5 的 TB 层级结构，不复述已给出的时钟组一句话。

## 1. DUT 实例与层次

- 顶层 `tb_nic_top` 内例化 `top #(.SIM_MODE(1), .ETH_NUM(ETH_NUM)) inst_top(...)`。
- `ETH_NUM`：`NSFOCUS_KU040` 定义为 4，否则（KU060）为 8；`ETH_TOTAL=ETH_NUM`（当前 cfg 走 KU060 分支 → 8）。
- RTL `rtl/top.sv` 同步：`CHNL_NUM = ETH_NUM/CHNL_ETH_NUM = 8/4 = 2`（2 个 PCIe/DMA 通道、2 组 DDR）。
- 关键内部层次名（TB 以绝对路径驱动/观测）：
  - `inst_top.inst_clk_rst_ctrl`（clk_lock 复位握手）
  - `inst_top.DMA_GEN[i].pcie_dma.WRAPPER_GEN.design_1_i.axi_vip_0.inst.IF`（AXI VIP agent 挂点，i=0/1）
  - `inst_top.DDR_GEN[i].inst_ddr_sdram0 / inst_ddr_sdram1`（TB 侧经 generate 例化，见 §5）
  - `inst_top.PROC_GEN[0].inst_ddr_ctrl_0.SIM_MODE`（tc16 用 defparam 置 1/2）
  - `inst_top.inst_flow_ctrl_proc.inst_ip_tdp_bucket.RAM_INIT`（tc24/25 defparam）

## 2. 时钟组（`tb_nic_top` 本地生成）

| 信号 | 周期 | 源 | 用途（TB 侧） |
|------|------|----|----|
| clk_250m | 4 ns | `always #(2)` | 主 sys 时钟（`assign clk_250m`→`inst_top.clk_100m` 无关；rst=rst_250m） |
| clk_100m | 10 ns | `always #(5)` | `inst_top.clk_100m` |
| clk_80p03m | 14.070 ns | 硬件留 12.495 但改 14.070「match XCO on board」 | DDR c0/c1 `sys_clk_p/n`（经 generate `assign c0_sys_clk_p[i]=clk_80p03m`） |
| clk_312p5m | 3.2 ns | `always #(1.6)` | 经 `force` 强驱动 `inst_top.eth_rx_clk/eth_tx_clk`（全部 ETH_TOTAL 位） |

> 40G/10G 参考与高速 GT 端口在 inst_top 实例中都留空（`gt_40g_*`、`gt_10g_*`、`pcie_*` GT 均 `()`），仿真用行为模型覆盖。
> `clk_312p5m` 并非 `always` 发出的 eth 时钟之外额外；eth 收/发时钟在 `init()` 用 `force eth_rx_clk={ETH_TOTAL{clk_312p5m}}` 统一打到 312.5M。

### init() 复位时序（`tb_nic_top.init`）

1. `force eth_rx_clk/eth_tx_clk = clk_312p5m`、`force eth_tx_rst=sys_rst`。
2. `force inst_clk_rst_ctrl.clk_lock=1` → 置 `axis_eth_40g/10g_tx_rdy=~0`。
3. `#1` 后 `force clk_lock=0`、`force user_rx_reset=~0`；等 500×clk_250m。
4. `force clk_lock=1`、`user_rx_reset=0`、`force eth_led_en=~0`。
5. 关闭 DDR 模型告警：`DDR_GEN[0].inst_ddr_sdram0.mem_model_x16.mem.memModels_Ri2[0].memModel2[0..3].ddr4_model.set_memory_warnings(0,0)`（及 sdram1、PCIE_DUAL 时 DDR_GEN[1]）。

## 3. AXI VIP agent 与 32b 读写封装

- `m_agent[1:0]` 类型 `design_1_axi_vip_0_0_mst_t`；每卡一个，`initial` 各 `new(...IF)` + `start_master()` + `wr_driver.create_transaction`。
- 任务/函数别名（TB 全局可见，testcase 直接调 `tb_nic_top.axi_wr32(...)` 等）：
  - `axi_wr32(dev_id,addr,data)` → `AXI4_WRITE_BURST(id=9'h0,addr,len=0,size=4B,INCR,...)`。
  - `axi_rd32(dev_id,addr)` → `AXI4_READ_BURST`，返回 `data[dev_id][31:0]`。
  - `axi_wr/axi_rd`：`send_multi_wrbursts/rdbursts(4,addr,...,size 32B,INCR)` 512 位总线量变体（tc 内少用）。
- `dma_init(dev_id=0)`：写 DMA 描述符内存高低地址/深度、上下行描述符、CPU/FPGA 指针区（`'h0_0080/0_00a0/0_00c0` 上行、`'h0_0020/0040/0060` 下行、`'h0_4500~4560` 指针）。
- `log2file(tc_name,tc_result,tc_status)`：按 pass/fail `$system("echo 'tcX ...' >> ./tc_summary.log")`，写入 `sim/nic_top/tc_summary.log`。
- `drive(iter)`：耗 iter 个 clk_250m 沿。

## 4. cfg_queue（TLV 配置队列）与 ft_monitor（期望特征）

- `bit [256:0] cfg_queue[$]`：testcase 任务 `cfg_*` 以 `push_back({last,data})` 填充（257 位 = 1b last + 256b data）。测试台本身不消费，注释掉的对拍块说明 `ft_monitor` 用于与 `d_rd_res[1]` 帧统计回读比对（`ft_monitor[511-:304]==d_rd_res[1].data[511-:304]`）。
- `logic [511:0] ft_monitor`：由 testcase 的 `cfg_session_table` 依 fwd_mode 装配「期望 512b 特征」（dip/sip/dport/sport/p_id + 封包头字节），同一 TLV 以 `ft_monitor[511-:232]` + `ft_monitor[279-:256]` 两片进入 256b cfg 数据。
- 配置方式：testcase 直接写 `tb_nic_top.cfg_queue` 与 `tb_nic_top.ft_monitor`（TB 声明为 `logic`/`bit`，非 localparam，因此可被外部模块跨层次访问）。

## 5. 两个 DMA 通道的 `initial` 业务寄存器序列

卡 0（`initial` 块 1）/卡 1（`initial` 块 2）各 `init(); drive(40);` 后写：
- 业务寄存器：`'h8_0014`(核心配置按需)、`'h8_0024=0xf`(core_rx_enable)、`'h8_6108~6144` (session table D15..D0)、`'h8_5000~0180`(上行各网口队列指针=0x200)、`'h0_4600`(fpga 队列数)。
- 随后 `#10us`、`m_agent[i].wait_drivers_idle()` 结束。

## 6. tb_def

| 文件 | 内容 |
|------|------|
| `tb_def/arch_defines.v` | Micron DDR4 型号宏映射：`DDR4_4G_X16` 等 → 展开 `DDR4_X4/X8/X16` + `DDR4_2G/4G/8G/16G` |
| `tb_def/ddr4_sdram_model_wrapper.sv` | Xilinx MIG 行为模型包装：`define DDR4_4G_X16`、`DDR4_833_Timing`、`SILENT`、`FIXED_2400`（选择 4G×16 拓扑，833ps 时序） |

## 7. tb_top 的 4 个 modal TB

均为被注释掉的独立小 TB（模块名也都叫 `tb_nic_top`），用于单独验证 RTL 内 FIFO/RAM 行为模型，先于整卡 TB 存在：

| 文件 | 激励 DUT | 参数 | 行为 |
|------|---------|------|------|
| tb_sc_fifo_top | `fifo_sc`（单时钟） | DW=64, DEPTH=5, AFULL=8 | init→drive(30)→drive_read(30) |
| tb_dc_fifo_top | `fifo_dc`（双时钟） | 同上 | 同上（wr_clk=rd_clk=clk 测试） |
| tb_sp_ram_top | `ram_sp`（单端口） | DW=64, DEPTH=5 | drive(30)+drive_read(31)，带 wr/rd addr |
| tb_tdp_top | `ram_tdp`（真双端口） | RAM_SYNC="sync" | drive(30)+两次 drive_read(31) |

公共结构：`clk_250m=0` 生成 4ns 时钟、`BUS#(32,5)::A din` 打 `5a5a_abcd_5a5a_abcd` 自检位序、init/drive/drive_read 三任务滥用写/读使能。目的是行为模型冒烟。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
