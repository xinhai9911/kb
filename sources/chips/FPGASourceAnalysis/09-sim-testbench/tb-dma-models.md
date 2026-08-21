# tb_dma 验证环境 + tb_model 行为模型分工

## A. sim/tb_dma —— 模块级 DMA 验证环境

有独立的 UVM 风格 env/driver（非 RTL testbench 集成，独立于 nic_top 整卡），验证 `design_1_sim`（ndma DMA 核 + AXI 主/从 VIP + 指针轮询/更新块）。

### 组件文件

| 文件 | 角色 |
|------|------|
| testbench.sv | 顶层模块：生成 clk(500M=2ns 周期)、reset_n(#123=1)；例化 `design_1_sim uut`、`xge_axis_intf xge_axis_if`、`testcase itestcase`；配置两 VIP `set_verbosity(0)`+`start_master/start_slave`+`mem_model` 全 0；`op_mon` 观测 `ndma_core_0_rd_req&axi_master_0_rd_ack` 分类打印（tid[1:0] 区分下行描述符/下行数据/上行描述符请求） |
| env.sv | class env：持 drv + 两 VIP agent；run() 先 `drv.read_pcap_file + init_dma`，再 fork 16 组 `drv.up_proc(k)/up_ptr(k)/wr_up_hdr(k)/down_proc(k)/wr_down_til(k)/poll_down_tail(k)`，最后 `send_packet()` |
| driver.sv | class driver（参 DESC_BUF_DEPTH=16384, QUEUE_COUNT=16）：`init_dma` 用随机地址初始化 16 队列上下行描述符缓冲（backdoor 写）；`up_proc` 轮询收包标志位→计数+清标志、`share_queue[j].put`;`down_proc` 从共享队取描述符写下行缓冲;`wr_up_hdr/wr_down_til` AXI4LITE 写 `PTR_POLL_BLK`(0x50000)±8k;`poll_down_tail` AXI4LITE 读 `PTR_UPDATE_BLK`(0x51000)`；`send_packet` 从 frame_array 逐 beat 驱动 xge_axis |
| xge_intf.sv | `interface xge_axis_intf(256b tdata, tlast, tvalid, tready, 32b tkeep)` + `default clocking cb @(posedge clk)`（tready 输入、tdat/tvalid/tkeep/tlast 输出, #0.1 skew）+ `init_signals()` |
| axi_vip_mst_pkg.sv | Vivado 生成的 master VIP 参数包（axi_vip_mst_t；64b 地址/256b 数据/9b id, "READ_WRITE"） |
| axi_vip_rtl_slv_stimulus.sv | 无内存模型的 slave VIP 响应示例：`agent=axi_vip_rtl_slv_t`，fork awready(OSC policy)/wr_response/rd_response，`fill_rd_reactive` 按地址填数据 |
| bd/design_1_sim | Block Design（`design_1_sim.bd/.bda`）：含 `axi_vip_mstr/axi_vip_slv/axis_data_fifo_0/ptr_poll_block_0/ptr_update_block_0/ndma_core_0/axi_master_0/axi_lite_slave_0/rx_info_gen_0` 等 |
| pkts_sample/*.pcap | 报文源（由 `read_pcap_file` 解析字节流） |

> 依赖说明：`driver`/`testbench` 引用 `class testcase` 与 `class packet`，但本抽取目录中未含其定义（疑似在 ip 生成源或其他未解压目录），**待核实**。

### pkts_sample pcap 角色（只读名+字节数）

| 文件 | 字节 | 用途推断 |
|------|------|---------|
| nsfocus_in1.pcap | 153,371 | 上行/入向业务报文集 1 |
| nsfocus_in2.pcap | 286,372 | 上行/入向业务报文集 2 |
| nsfocus_out1.pcap | 32,830 | 下行/出向报文集 1 |
| nsfocus_out2.pcap | 337,232 | 下行/出向报文集 2 |
| random_0.pcap | 370,108 | 随机混合长度/内容报文 |
| more_than_4k.pcap | 941,627 | >4K 超长帧压力样本 |
| test.pcap | 17,391 | 冒烟小样本 |

`read_pcap_file` 硬编码：跳过 pcap 文件头 24B；每报文先跳 8B(时间戳)再读 4B 长度（wireshark 记录头）→跳 4B→读报文本体；以 `{32{8'hef}}` 哨兵值代表空位，`frame_array[p][261]`=eop、`[260:256]`=长度低 5 位。

## B. sim/nic_top/tb_model —— 整卡 TB 的行为模型

### ddr/（DDR4 行为模型 + microblaze MCS）

| 文件 | 性质 | 角色 |
|------|------|------|
| ddr4_model.sv (2473 行) | 加密 (pragma protect) | DDR4 存储体时序模型 |
| MemoryArray.sv / StateTable.sv / StateTableCore.sv | 加密 | 存储阵列 / 命令状态机 |
| ddr4_sdram_model_wrapper.sv | 复用 tb_def | 拓扑/时序宏选择（4G×16, 833ps） |
| ddr_sdram.sv | NSFOCUS | `ddr_sdram ` 顶层行为模型，TB 的 `DDR_GEN` 例化它（c0 64b DQ, c1 16b DQ） |
| ddr4_v2_2_hw_tg.sv / tg_*.sv / prbs_gen.sv / pattern_gen_* | Xilinx | 硬件测试生成器（hw_tg）与 PRBS 地址/数据生成；参数 TG_PATTERN_MODE_PRBS_ADDR_SEED=44'hba987654321 等，vio_* 指令式控制 |
| ddr4_0_dns_microblaze_mcs_0.sv (18,385 行) | vendor 加密(MCS 控制器) | 只读头部识别：microblaze_mcs_v1_2 网表，ML605 时代 netgen 产物 |
| ddr4_v2_2_16_ddr4_stimulus_mem_x16.txt / temp_mem.txt | 数据 | 训练/初始化激励与中间内存镜像 |

### dma/（PCIe 桥/DMA 主行为模型）

| 文件 | 角色 |
|------|------|
| design_1_xdma_0_0.sv (45KB) | 「pcie bridge tb model」（文件头注明）；`module design_1_xdma_0_0 #(parameter ID=0)`，端口 sys_clk/sys_rst_n、cfg_ltssm_state、user_lnk_up、pci_exp_* 8bit 串行、axi_aclk；注释阐明 ar id 编码：9'hxx0 dl 描述符 / xx1 dl 数据 / xx2 ul 描述符 / xx3 dl 配置 / 0x100 cpu index；含单端口 DMA s0/s1 axis 的 FREQ_HZ 250M 约束注解 |
| axi_master_new.v (30KB) | `module axi_master`：AXI4 full master（awid 9b/awaddr 64b/wdata 256b, WR_FSM_NORMAL 等状态机），作 ndma 的数据通路 AXI 主模型 |

### pcie/ 与 eth/

| 文件 | 角色 |
|------|------|
| pcie/design_1_axi_pcie3_0_0.sv (29KB) | PCIE3 桥 tb 模型：sys_rst_n/cfg_ltssm_state/user_link_up/sys_clk_gt + s_axi 全 AXI4 主从口（255b 数据） |
| eth/xxv_ethernet_{0,1}.sv (38KB) | **10G** Ethernet MAC+PCS/PMA（模块 `xxv_ethernet_0`，C_LINE_RATE=10, 64-bit AXI-S, C_NUM_OF_CORES=4, 4×GTH）行为包装 |
| eth/l_ethernet_{0,1}.sv (14KB) | **40G** Ethernet MAC+PCS/PMA（模块 `l_ethernet_0`，C_LINE_RATE=40, 256-bit AXI-S, C_NUM_OF_LANES=4, BASE-R）行为包装 |

> 命名易混：xilinx IP 名 `xxv_ethernet` 是 10G、`l_ethernet` 是 40G；文件名 `xxv_ethernet_0.sv` 与模块名一致，`l_ethernet_0.sv` 同理（已按模块头 C_LINE_RATE 核实映射）。

> 分工总结：eth/ 提供 40G/10G MAC/PCS/PMA 线速行为（AXI-S 收/发用户接口）；dma/ 提供 PCIe 侧 DMA 主与 xdma 桥（把 pci_exp 串行抽象成 AXI）；pcie/ 桥承接 AXI 主从；ddr/ 提供 DDR4 颗粒时序+训练模型。整卡 TB（tb_nic_top）把后两者经 `DMA_GEN`/`DDR_GEN` 的 TOP 内部 wrapper（`WBAPPER_GEN...axi_vip_0` / `ddr_sdram`）连到 RTL。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
