# def/ 总线族与宏定义深度解析（part 1：ver_define + user_bus_def / user_bus_if）

> 源码位置（只读）：`Q:\AI\fpga_work\ips_test_2025_add_mpls_6que\rtl\def\`（`ver_define.svh` / `user_bus_def.sv` / `user_bus_if.sv`）。`pci_bus_def.sv` 见 part 2。

## 1. ver_define.svh —— 全局宏（全 6 条，无条件）

| 宏 | 值 | 含义 | 在 top.sv / 工程中的生效点 |
|---|---|---|---|
| `NSFOCUS_KU060` | 无值 | 器件选择宏：Kintex UltraScale+ KU060 构建 | top：启用 2 号 40G 核（`l_ethernet_1`）+ 4×10G（`xxv_ethernet_0`）与 DMA 槽 4..7（top.sv:508/2022）；`timeout_gen` PERIOD=200e6（非 KU060 为 250e6，top.sv:639）；`clk_rst_ctrl` KU060 复位链；pci 侧选 Gen3 |
| `PCIE_DUAL` | 无值 | 双通道（双卡）构建 | `DMA_GEN` 循环 2 次（top.sv:1818）；SIM 分支清 `mem_out[1]` 槽；`pci_xil_core_wrapper` 双路 |
| `DEF_NIC_DATE` | `32'h2026_0605` | 固件构建日期 2026-06-05 | `top_mem_map.sv:148` `r_nic_date`（RO） |
| `DEF_NIC_TIME` | `32'h0011_0326` | 构建时刻 00:11:32.6 | `top_mem_map.sv:149` `r_nic_time`（RO） |
| `DEF_NIC_REV`  | `32'h01_02_06_04` | 版本 01.02.06.04 | `top_mem_map.sv:150` `r_nic_rev`（RO） |
| `DEF_NIC_VER`  | `32'h03_0D_0014` | 版本 03.0D.0014 | `r_nic_ver = DEF_NIC_VER + DEV_ID*32'h10_0000`（卡号 0/1 加偏移，RO） |

- 文件头注释「auto generate by script」——四个 `DEF_*` 由构建脚本（`build_lib/set_version*.tcl`）回写，只读寄存器用。
- **仿真 flag 不在本文件**：`SIM_MODE` 是 top 参数（0=真实/含 DDR MIG，1=仿真接 'h0）；`GOLDEN` 宏由 golden 构建脚本定义（top.sv `ifdef GOLDEN` 分支：置 `init_calib_complete/ui_rst/self_check`、`eth_sta.UNKNOW=1`、`b_list_out1=0`、禁用真实 DDR MIG）；另有 `NSFOCUS_KU060_SWITCH` 在 `session_t_sch` 出现（board 变体），不在此文件。
- **CHNL_NUM 不是宏**，而是 top 参数 `CHNL_NUM = ETH_NUM/CHNL_ETH_NUM = 8/4 = 2`，双卡形态由 `PCIE_DUAL` 决定是否编译。

## 2. user_bus_def 包（virtual class 仅作命名空间/参数化 typedef）

### 2.1 `BUS#(DW,CHW)` —— 全工程数据面统一裸总线，四级变体

| 变体 | 字段（packed struct） | left/ch 说明 | 典型用法 |
|---|---|---|---|
| A | `vld, sop, eop, data[DW-1:0]` | 无 left、无 ch | 最简包流 |
| B | A + `left[$clog2(DW/8)-1:0]` | 尾拍有效字节数（DW=256 → left[4:0]） | `BUS#(256,0)::B eth_rx_bypass / eth_tx_user` |
| C | B + `ch[CHW-1:0]` | ch=元数据侧带「包护照」 | 数据面主力：`eth_rx(6)`、`b_list(72)`、`route_sel(185)`、`pkt_parsing(125)` |
| D | A + `ch[CHW-1:0]` | 有 ch 无 left | — |

`vld/sop/eop` 各 1 bit；`left` 宽度依赖 DW。ch 宽度每级不同，印证「每级只改写自己负责位域」的包护照模式。

### 2.2 `DDR#(DW,CHW)` —— DDR 读/写请求与响应

| typedef | 字段 | 说明 |
|---|---|---|
| `REQ` | `vld, addr[CHW-1:0]` | 请求地址（CHW 即地址位宽） |
| `RES` | `vld, addr[CHW-1:0], data[DW-1:0]` | 响应带回地址标签 |

top 实例：`DDR#(512,29)::REQ ddr_db_rd_req`（addr[28] 选 DDR 片 j，addr[27:0] 进 MIG）、`DDR#(512,28)::REQ/RES d_rd_req/d_rd_res`（512-bit 数据面、28 位地址）、`DDR#(512,29)::RES ddr_db_wr`。

### 2.3 `MEM#(DW=32)` —— LBS 本地寄存器总线

| typedef | 字段 | 说明 |
|---|---|---|
| `IN`  | `address[23:0], wr_vld, wr_data[DW-1:0], rd_req` | 24-bit 地址、32-bit 数据，握手极简 |
| `OUT` | `rd_vld, rd_data[DW-1:0]` | 单拍读响应 |

top 上 `mem_in[CHNL_NUM-1:0]` 与 `mem_out[CHNL_NUM-1:0][15:0]` 即此结构；全部 `*_mem_map` 从模块共享同一 `mem_in`（按地址译码），各占 `mem_out` 一个槽（见 top-dataflow 槽位表）。

### 2.4 `AXI#(DW,CHW)::S` 与 `AXI_256`

| typedef | 字段 | 说明 |
|---|---|---|
| `AXI#(DW,CHW)::S` | `vld, last, keep[DW/8-1:0], data[DW-1:0], user[CHW-1:0]` | 参数化 AXI-Stream 流（user 侧带） |
| `AXI_256` | `vld, last, keep[31:0], data[255:0]` | 扁平 256-bit 流（无参数），用于 `tlv_din` 与 `axi_out` |

top 实际位宽：MAC 侧 `AXI(256,1)::S`、10G `AXI(64,1)::S`、UL DMA `AXI(256,20)`、DL DMA `AXI(256,8)`、`DMA_axis` `AXI(256,2)`、`numa_din/axi_in` `AXI(256,8)`。

### 2.5 `ETH_FIELD` —— 以太/IP 头解析结果（逐字段）

| 字段 | 位宽 | 用途 |
|---|---|---|
| dmac / smac | 48+48 | 目的/源 MAC |
| eth_type | 16 | 以太类型（0800/86DD/0806） |
| frag | 16 | 分片字段（标识+偏移） |
| ttl | 8 | IPv4 TTL（或 IPv6 hop 数） |
| p_id | 8 | 协议号（TCP=6/UDP=17） |
| dip / sip | 128+128 | 目的/源 IP（v4 用低 32 位，v6 全用） |
| dport / sport | 16+16 | 四元组 TCP/UDP 端口 |
| tcp_flag | 8 | TCP 标志 |
| l4_h_len / l3_h_len | 4+4 | L4/L3 头长（单位：字） |
| l3_len | 16 | L3 总长度字段 |

### 2.6 `MTU_PKT_INFO` 与工具类

- `MTU_PKT_INFO`：`bypass`、`saddr[13:0]`、`length[11:0]`、`mtu_length[11:0]`、`l3_offset/l4_offset[7:0]`、`ipv4_length[15:0]`、`ipv4_flags[2:0]`、`ipv4_fragment[12:0]`、`other_info[95:0]`——mtu 引擎的包描述符（注释：带 hdr / 不带 hdr 两套长度口径用 `-p/-s` 标注）。
- `pg#(IDW=9,CFGW=32)`：`cfg_c{id[IDW-1:0], details[CFGW-1:0]}`、`cfg{vld, content}`——端口组查询请求。
- `fifo#(DW)::lite`（wren/wd/rden/rdv/rd）、`ram#(AW,DW)::lite/rdv`（写读双端口 + 可选 rdv）——同步 FIFO/双口 RAM 统一薄封装。

## 3. `axi_lite_if`（`user_bus_if.sv`，SystemVerilog interface）

- 参数 `DATA_W=32, ADDR_W=13`；信号：`aclk/aresetn` + AW（`awaddr[ADDR_W-1:0]/awvalid/awready`）+ W（`wdata[DATA_W-1:0]`、`wstrb[3:0]`、`wvalid/wready`）+ B（`bresp[1:0]/bvalid/bready`）+ AR（`araddr/arvalid/arready`）+ R（`rdata/rvalid/rready/rresp`）。
- 提供 `master`/`slave` 双 modport，标准的 5 通道 AXI4-Lite 时序。
- top 实例：`axi_bcam[2]` / `axi_tcam[2]`（每通道各 1），aclk 绑 `clk_100m_in`、aresetn 绑 `clk_100m_lock`；下游接 `axi_cam_slave`（BCAM）与 `blacklist_proc.axi_tcam`（TCAM 侧），网表侧是 `design_bd_wrapper` 的 `reg_axi_1/2`。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)。