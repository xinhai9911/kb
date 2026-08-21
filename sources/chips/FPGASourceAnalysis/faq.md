# FAQ：NSFOCUS FPGA 智能网卡已知坑与排错

> 汇总各代理深读 rtl/sim/constraint 时发现的**具体问题**、**陷阱**和**待核实项**。来源标注模块简称。

## 1. 死代码 / 未实例化功能（勿误以为生效）

| 模块 | 现状 | 影响 |
|---|---|---|
| `blacklist_tcam` | `blacklist_proc.sv` 用 `generate if(0)` 阻断，AXI 被 8-bit 空壳 `axi_cam_slave` 吸走 | TCAM 配置无效，黑名单只走 DDR 哈希；tcam_mem_map 所有寄存器读回 0 |
| `qos_block` | `top.sv` 注释掉（`/* */`），mem_out[12] 无驱动 | 0x08_8000 寄存器窗口不存在；QoS 路由走 `route_sel_in→crs_crd` 直连 |
| `pkt_tracing_mem_map` | top 注释，mem_out[13] 无驱动 | 0x08_f000 寄存器读写落 0 |
| `ddr4_1_dns`（16-bit 第二片 DDR） | `DDR_GEN j=1` 段整体注释，但 `ui_clk[i*2+1]` 仍被 FIFO 引用 | 第二片 DDR 时钟悬空，相关 FIFO 时钟无驱动——**综合警告/仿真 X 值** |
| `Axis2Avls` / `Eth_package` / `Message_package` | top 内遗留未实例化 | 不进入当前数据面 |
| `clk_010m_in` | `top.sv:1832` 被 `design_bd_wrapper.m_dna_clk` 引用但顶层未声明 | 悬空网线，综合可能报错 — **待核实** |

## 2. 命名陷阱（同名/拼写不一致）

| 问题 | 正确事实 |
|---|---|
| `mtu_comb.sv` 文件 vs 模块名 | 模块名实为 `mut_comb`（字母 u/t 互换） |
| `host_intf.v` 文件 vs 模块名 | 模块名实为 `host_inft` |
| `pkt_tracing_hit.sv` 文件名 | 模块名实为 `pkt_tracing_detection` |
| `slp_decode` | **不是** SRAM 链路表读侧；是逐包头 VLAN/IPv4/IPv6/UDP/TCP 偏移译码（5 拍，无反压） |
| `Forward_shunt` 新旧两版同名 | 现版（CARD_ID 分支）供 `Forward_top` 用；旧版（ETH_NUM 分支）仅在遗留 `Message_package` 实例化，接口不对齐 |
| `ckes` | checksum 的拼写变体（出现于 `Tcp_ckes_calc`/`ckes_calc` 等） |
| `updata/` 目录 | 非 update，是 updata（固件升级目录名，勿改） |
| Xilinx IP 名 | `xxv_ethernet`=10G；`l_ethernet`=40G（反直觉，按模块头 `C_LINE_RATE` 核实） |
| `CRC16_D64`（模块名大写下划线） | 文件名 `crc16_d64.sv`，模块名 `CRC16_D64`——引用时注意大小写 |

## 3. 协议号 / 字段定义冲突

| 问题 | 事实 |
|---|---|
| TCP/UDP 协议号 **在本工程两处相反** | `blacklist_filter.sv`: TCP=1, UDP=6, ICMP=17；session 表（`Typdef_pkg.sv`/上游数据面）: TCP=6, UDP=17——系统内两套并存，跨界复用必须核对 |
| `session-table.md` §6 `dout2 ch` 的 FLAG==0x18 | 虚拟线模式下 macid 区全 0，模式区写 8'h18——注意 FLAG 与 Route_mux `ruser[164:157]` 解码值（0x18 同义） |

## 4. 寄存器地址陷阱

| 问题 | 事实 |
|---|---|
| 顶层综述 §3.1 槽位 [6] 记为 `0x08_0000` | 实为 `top_mem_map` 的槽 [0] BASE=0x8_0000；session_t_sch（槽 [6]）的基址在其模块内部，两处容易混 |
| `st_sch_mem_map` 被复用两次 | 0x08_6000（session 实例，GBL_TIMEOUT/AGING/RSS 全功能）；0x08_7000（blacklist 实例，这些输入全接地，只有读统计有效） |
| mem_out[12]/[13]/[14]/[15] 无驱动 | 真实构建中这些槽为 0，但 `reg_axi_rdata` 逻辑 OR 合并，是地址空间的「静默 X 源」 |
| `Forward_lbs` FORWARD_BADDR | 模块默认 `12'h1`，top 传 `12'h084`（基址 0x084_000，槽 8）；内部统计口在 top 被置 0，读回恒零属预期 |

## 5. 仿真 / 测试已知失败

| 用例 | 状态 | 原因 |
|---|---|---|
| tc0 | ⚠️ 旧接口 | 部分老式用例驱动 `axis_eth_rx`，当前 DUT 只有 `axis_eth_40g_rx` + `axis_eth_10g_rx`，层次口不存在，elab 失败 |
| tc4 | ❌ pre-existing | `axis_eth_rx` → `axis_eth_10g_rx` DUT 接口变更 |
| tc5 | ❌ pre-existing | 采样 buffer 时序依赖 |
| tc6+ | ⚠️ UNTESTABLE | 缺 `inst_ddr_ctrl_1`（当前 DUT 只有一片 DDR） |
| 当前 tc_summary.log | 仅 tc1 PASS | `msim_setup.tcl` 第 180 行 `set tc_list {tc1}`，其余用例未跑——**要跑其他用例需改该行** |
| QuestaSim 10.7c 限制 | 不支持 `import pkg::*` 带层次引用 | 用例改用 `` `include ``，不用 package import |
| tc_drivers.svh | 用 `generate if()` 非 `` `ifdef `` | 兼容 Questa 10.7c，不可改为 ifdef |

## 6. DMA / PCIe 已知问题

| 问题 | 事实 |
|---|---|
| `up_stream_block.v` 的 `up_str_drop_cntr` | 输出悬空未驱动（ndma_core 透传），软件读恒 0 |
| `desc_used`（desc_til）计数逻辑 | 实际只数**报文读请求**（`s_tid[0]=1`），描述符读（tid[0]=0）不计入——注释名「已取走描述符」有误导 |
| `single_port_dma.v` 端口集 | 引用了 `block_ofst` / `BLOCK_ID` / `m_length` 等当前 ndma_core 没有的端口，属另一工程版本，本套件下不可直接编译 |
| `st_gp_fifo_w360` 读侧 `tx_eof_cnt` | 采样 `rx_fifo_rdata[72]`（tdata 数据位），且注释「5×BRAM36K」与 `ADDR_WIDTH=10`（1024 深）需核实 |
| `xil_rc` 只放行成功完成 | compl_status≠0 的 CPL 静默丢弃（仅计 `rc_error_status_cpl_cnt`），调试需关注 |
| `pci_xil_wrapper_top` | 传给 `pci_xil_wrapper` 的 `R_BACK_SORT_W`/`PTR_W` 参数在后者没有定义，elaboration 应报错——属死代码 **待核实** |
| `s_axi_r` SIM/real 两分支 | SIM 插 `axi_data_split` 和随机反压；real 直通 FIFO——跨仿真/上板时通路结构不同 |

## 7. 约束 / 引脚陷阱

| 问题 | 事实 |
|---|---|
| `pin.xdc` vs `pin.fdc` PCIe LaneN 编号 | Vivado `pcie_7x_mgt_0_txp[0]`=AC4 对应 Pango/UCF 的 `PCIE_L4_TXP`（AC5 附近），即 Vivado Lane0 ≡ 板级 PCIE_L4——**待核实：需对照 .xpr IP 配置** |
| `timing.fdc` 名称误导 | 内容全为引脚 LOC（`PAP_IO_LOC`），**不含任何时序约束**——Pango 时序约束应在 `.sdc`（本工程未附） |
| TIMER_CFG 公式 | `WATCH_DOG_TIME = TIMER_CFG × (1000/cclk) ns`；`TIMER_CFG=0x1DCD650`，`cclk`=3 MHz（默认）→ 约 10.4 s 看门狗 |

## 8. common/ 遗失依赖

| 问题 | 事实 |
|---|---|
| `fifo_sc` / `fifo_dc` / `dsp_macro_cnt` | 三个原语不在仓库 rtl/ip 内，依赖既有综合/仿真库，移植需自备 |
| `axis_rxq_demux` N_NUM=4 形态但 genvar i<1 | 实际只驱动 ch0，其余 3 路输出悬空 |
| `eth_pkt_gen` 输出当前悬空 | top.sv TLV 源 `if(1)` 分支生效（走 AXI），`if(0)` 分支才用 eth_pkt_gen 发包，综合可能优化掉 |

## 9. 顺序排错流程

### 黑名单不生效
1. 确认 `top.sv` 中 `bypass_en=r_bypass_en[i][5]|…` 未置 1（寄存器地址 top_mem_map）。
2. 确认 blacklist_proc 的 `eth_dout0` 路径（filter 已生效，TCAM 永不生效）。
3. 检查 DDR 写路径：`ddr_ft_info_db` 写使能是否依赖 `o_db_fwd_cfg`（**待核实**）。

### 会话表未命中
1. 查 st_sch_mem_map 0x80~88（AGING_CFG）是否配置；GBL_TIMEOUT 是否为 0。
2. 查 `dout3` 旁路路径（ARP/DDR 未命中）是否误触发。
3. 查 TLV 下发链路：`tl_parsing` 统计 `ddr_cfg_cnt` 是否递增。

### 仿真整卡 TB 编译失败
1. 确认 `msim_setup.tcl` 中 tc_list 填写的用例名存在于 `sim/nic_top/testcase/`。
2. 确认 lib 已编译（`com_ip.tcl`→`com_ddr_*.tcl`→`com_dma.tcl`→`com_vlog.tcl` 顺序执行）。
3. tc4/tc16/tc17/tc24/tc25 与当前 RTL 接口不兼容（`axis_eth_rx` 旧接口），暂不可用。

### 寄存器读回恒 0
1. 检查对应模块是否在 top 注释掉（qos_block / pkt_tracing_mem_map）。
2. 检查 LBS 基址是否与 mem_out 槽位表匹配（`lbs-register-map.md` 全表）。
3. tcam_mem_map（0x08_9000）全部寄存器恒 0 是预期行为（TCAM 死代码）。

## 10. 以太网解析器（rtl/eth/）新发现

| 问题 | 事实 |
|---|---|
| `eth_ul_pkt_parsing_v2` 是否在用？ | **全工程 grep 无例化**；top.sv 8 口全用 v1，v2 仅出现在 vlog 编译清单，属重构候选，勿当生效路径 |
| 综述 §4.7 协议端口号 | **错位**：综述写「Telnet+24/FTP+33/IMAP+42」，源码实际为 23=FTP-Ctl / 21=FTP-Data / 143=SIP / 110=POP3 / 80=HTTP / 3306=MySQL |
| `pkt_parsing_sch` 是否有仲裁逻辑？ | **无**：vld/sop/eop 全体 OR + 固定优先级；正确性依赖「上游同一时刻单包」前提——并发两包入 sch 会 OR 出脏数据 |
| `pkt_parsing_mem_map` 含统计计数吗？ | **不含** CRC/MIN/JUMBO/FC/BYPASS_EN——这些在 `Ingress_chnl`（eth_rx_pkts_*）与 `top_mem_map`，查统计要去那里 |
| `eth_reset` lnkdwn_cnt 清零方式 | `clear_lnkdwn_cnt` 在 top 接 `'d0`，**无软件清零通道**（待核实） |
| check_en 14-bit 偏移语义 | `[13:5]` = 256-bit 行号，`[4:0]` = 行内字节偏移；`position_check` 按此格式消费 |

## 11. DDR 调度器（rtl/ddr_ctrl/）新发现

| 问题 | 事实 |
|---|---|
| `hash_inv` 的作用 | **不是校验**，是 25-bit 位反转（`hash_inv[i]=din[25-i]`）用于打散行地址防 DDR bank 冲突；综述「hash_inv 校验」表述不准确 |
| `0x5a` 自检是否周期性？ | **一次性 POST**（Power-On Self Test）：INIT_WRITE→INIT_READ→IDLE；`self_check_cnt[7]` 置 1 后常驻，自检期 DDR 读回不外送（门控） |
| 仲裁策略是 round-robin？ | **写绝对优先**（8 态 FSM，READ 期间新写随时抢占）；`app_addr[2:0]`（mask_sel/debug）实际恒 0 未用；`app_rd_data_end`/`t_ddr_empty` 未使用 |
| 黑名单 DDR 读能否正常返回？ | **不能**：`rd_res_demux.pkt_in[1]` 依赖 DDR 通道 j=1（`ddr_ctrl_1`），但 `ddr_ctrl_1`/`ddr4_1_dns` 已注释、`d_rd_res[i*2+1]` 强制 0 → blacklist DDR 哈希读请求永无响应（影响面待核实） |
| `ddr_ctrl` 内 FIFO 复位域 | `sc_fifo_idx` 跑 ui_clk / 复位 ui_rst，但配对 FIFO 的 `rst` 接 `clr`（sys_rst）——**跨时钟域复位风险** |
| `error_status` 信号 | 无驱动（赋值在注释里），`error_flag` 输出恒 0 |

> 返回：[skill.md](skill.md)
