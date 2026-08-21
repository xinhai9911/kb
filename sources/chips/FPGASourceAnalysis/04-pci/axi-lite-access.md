# AXI 数据通路胶水

> 深读 `rtl/pci/` 的 `axi_data_split.sv`、`d_slide_left.sv`、`d_slide_right.sv`、`s_axi_r.sv`、`s_axi_w.sv`、`m_axi_lite_r.sv`、`m_axi_lite_w.sv`、`axi_reg.sv`。配套 `axi2pci.sv`（装配）、`pci_bus_def.sv`、`common/sc_fifo_idx.sv`。综述 §4.6 未展开这些胶水层。

## 1. 定位总览

`axi2pci`（real AD_W=62）把 AXI-256 主/从 + AXI-Lite 主/从四组接口接进 `pci_xil_wrapper`：

| 通道 | 模块 | 方向 | 连接 |
|---|---|---|---|
| s_axi_w | `s_axi_w` | 主机 AXI-256 写 → mwr | host→DMA 下行数据 |
| s_axi_r | `s_axi_r` | 主机 AXI-256 读 ← mrdb | PCIe 读数据回给主机 |
| m_axi_lite_w | `m_axi_lite_w` | cq_wr（CQ 寄存器写）→ AXI-Lite 主 | 下行写控制/状态 |
| m_axi_lite_r | `m_axi_lite_r` | cq_rd/cc_rd（CQ 读）→ AXI-Lite 主 | 下行读 |
| axi_reg | `axi_reg` | AXI-Lite 从 | host 经 CQ 读统计/配 ramp_prog |

关键结构体：`bus_pci#(DW,CH)::avl_ch`（vld/sop/eop/left[`$clog2(DW/8)`]/data[DW]/ch[CH]），`left` 以**字节数**(每 32B 计数——`keep2left<<2`)表示当前行有效长度，0 表示满 256b=32B。

## 2. d_slide_left / d_slide_right：移位对齐原语

两者都是"把不定长数据流按字节对齐"的重组器；`avl` 的 `left` 是流式有效长度信号，`din_slide` 是本次需要平移/保留的对齐量。

### d_slide_left（拼头，向高位左拼）

- 三级打拍 din_ff1/ff2，输出 = 前一拍尾 + 本拍头拼接，把跨 256b 行的包重新左对齐，`eop` 可因 `din_slide` 拆成两拍。
- **data 拼接**：`{din_ff2.data[高段], din_ff1.data[高N字节]}`，按 `din_slide[4:2]` 选择 N（S_W=5 时为 32B 粒度 N=1..7）。S_W==2 时按字节粒度（xil_cq 用 INFO_W=128、din_slide=16 即移位 16B）。
- `left`：`din_ff1.eop & slide>=left1 ? left2+left1-slide : (ff2_eop? left2-slide2 : 0)`；`ff2_eop` 表示 eop 之前拍的残余被补齐到本拍输出。
- `dout_u.sop`=`din_ff2.sop`；`dout_user`=`din_user_ff2`（INFO_W 随流带ch）。
- 用法：d_slide_left——xil_cq 完整重排 CQ 流（INFO_W=128,slide=16）；xil_rc 完成流 ff1→ff2（INFO_W=96,slide=12）；s_axi_r mrdb→ff1（INFO_W=8,din_slide=mrdb.ch[9:8] 即 2 位字节偏）。

### d_slide_right（右移补 0）

- 把数据右移 `din_slide` 字节，左边空位补 0；**用于把 data 区域对齐到规范字节边界**。跨行时 `eop_lat`/`left_lat` 记住尾拍残余，下一拍续传。
- data：`{din_data_lat[...], din.data[高段]}`（din_data_lat 为前一拍 latch），按 `din_slide[4:2]`（32B 粒度）或 eop_lat 分支。
- `left = (eop 且 slide+left<=32)? slide+left : (eop_lat? left_lat : 0)`；`dout_u.vld = din_vld | eop_lat`。
- 无 DIN_FIFO 时 `din_fifo_rden=1'b1`；DIN_FIFO 版本内部自产 rden。
- 用法：d_slide_right——xil_rq mreq_tlp 出流（INFO_W=$bits(tlp_mm),slide=16）；xil_rc 完成重组 ff3→ff4（INFO_W=96,din_slide=动态 `rc_ff3_ch[95:91]` 即 sop_gap）。

## 3. axi_data_split：把整片 AXI 写切成 4KB 对齐块

仅 SIM_MODE 下在 s_axi_r 的 SIM 分支例化（s_axi_r.sv:134，用于仿真的数据拆分随机 rdy 模拟）。

- 输入 `din`(avl_ch,DW=256) → 内部三级 ff + `rd_info_fifo`(DW=BUS_DW-1, DEPTH=5,AFULL=8) → `dout`，`din_rdy=~fifo_afull`。
- `cur_addr` 每推进一拍 +32（以 32B 记）；`cur_addr[11:5]==0` → 新 sop（4KB 边界起点，`&` 为 eop）；`din_ff3.data={din_ff2.data,din_ff1.data}` 跨行拼整。
- eop 判定：`&cur_addr[11:5]`（到 4KB 边界）/ `din_ff1.left>=32 && din_ff2.eop` / `din_ff1.eop`。ch 在整片 sop 时透传、eop 时 ch+1（片号递增）。

## 4. s_axi_w：AXI-256 写通道 → mwr

- 握手：`s_axi_awready=~fifo_afull[0]`、`s_axi_wready=~fifo_afull[1]`；`wlast&wuser` 界定一"包"。
- **AW 元数据 FIFO** `fifo_sync_0`(DW=62)：仅在 `awuser[15]`（长度有效位）写，内容 `{awuser[14:0](len), awaddr[48:12], awuser[27:18]}` → `mwr.ch`；`aw_rden=mwr.vld&mwr.eop`。
- **写数据 FIFO** `fifo_sync_1`(DW=263)：`{sw_endding(wdata), strb2left(wstrb), wlast&wuser, wfirst}` → `{mwr.data, mwr.left, mwr.eop, mwr.sop}`；`w_rden = fifo_empty==00 && mwr_rdy`。`s_axi_wleft=strb2left`：返回 31-i 第一个为 0 的字节（即末有效字节号）作 left；`sw_endding` 256b 字节倒序（LE→内部表示）。
- `mwr.vld=w_rdv`；`s_axi_bresp='h0`；bid：SIM 用 `fifo_sync_2`(DW=9) 配对，real 直接 `s_axi_bid<=s_axi_awid`；`s_axi_bvalid<= bready&wlast&wvalid&wready`。

## 5. s_axi_r：AXI-256 读通道 ← mrdb

- `mrd`（请求）：`mrd.vld/sop/eop=arvalid&aruser[15]`（长度有效才发包）；`mrd.left='0`；`mrd.ch = {len16b, arid[7:0], addr}`——`ch[AD_W+:16]=aruser[14:0]+aruser[17:16]`、`ch[AD_W-1:0]={arid[7:0], araddr[53:12], aruser[27:16]}`。
- `s_axi_arready=mrd_rdy`（连续无锁存）。
- `mrdb`（回读）→ `d_slide_left`(INFO_W=8, din_slide=mrdb.ch[9:8]) → `rd_data_fifo`(DW=$bits(mrdb)-1-2, DEPTH=6,AFULL=8) → `mrdb_ff2`。
- 输出组合：`s_axi_rdata=bsc_256b(data)`、`rid={1'b0,ch[7:0]}`、`rlast=eop`、`rvalid=vld`、`ruser={left,eop}`、`rresp='0`。
- **SIM 分支**：插入 `axi_data_split`，`dout_rdy=s_axi_rready&data_split_rdy`（`data_split_rdy=$random()%9>1` 模拟随机反压）。real：`mrdb_ff2=rd_fifo_dout`、`rd_fifo_rdy=s_axi_rready`。

## 6. m_axi_lite_r / m_axi_lite_w：CQ→AXI-Lite 主

### m_axi_lite_r（读）
纯组合直通（无内部状态）：`araddr={12'b0,cq_rd_ch[19:2],2'b0}`（cq_rd_ch 低 20 位即 32B 对齐地址）、`arsize=2`(4B)、`arburst=1`、`arlen=0`；`arvalid=cq_rd_vld`、`cq_rd_rdy=m_axi_arready`；`rready=cc_rdv_rdy`、`cc_rd=m_axi_rdata`、`cc_rdv=m_axi_rvalid`。**读数据直接返回 xil_cc 生成 CPLD**。

### m_axi_lite_w（写）
两个 FIFO + 握手占位状态机：
- `fifo_sync_0`(DW=32)：`cq_wr_data`→`m_axi_wdata`；`fifo_sync_1`(DW=18)：`cq_wr_ch[19:2]`→`m_axi_awaddr[19:2]`（`awaddr[31:20]=awaddr[1:0]=0`）。`cq_wr_rdy=~wfull&~awfull`。
- `wed/awed` 握手锁存：`~wed & m_axi_wready & ~fifo_empty[0]` 置位、`wed & m_axi_bvalid` 复位（写数据已完成等待 B 响应）；aw 同理。`m_axi_awvalid/wvalid` 由 rdv 且未在等响应时拉高，`wvalid=rdv_w&~wed&~awed`，`wlast=wvalid`。
- `awsize=5`(32B)、`arburst=1`、`arlen=0`、`wstrb='hf`、`bready=1`。

## 7. axi_reg：统计/配置寄存器堆（AXI-Lite 从）

读地址用 `{araddr[11:2],2'h0}` 索引（12 位地址，4B 对齐，因此偏移 0x0..0x7c，步进 4）：

| 偏移 | 读回 | 来源 |
|---|---|---|
| 0x00 | pci_cfg_status | PCIe 配置 |
| 0x04 | mwr_cnt | | 
| 0x08 | mwr_tlp_cnt | |
| 0x0c / 0x10 | mwr_max_len / mwr_min_len | |
| 0x14 / 0x18 | mrd_cnt / mrd_tlp_cnt | |
| 0x1c / 0x20 | mrd_tlp_max_len / mrd_tlp_min_len | |
| 0x24 / 0x28 | tlp_addr_info[0][47:32]/[31:0] | mwr 地址 |
| 0x2c / 0x30 | tlp_addr_info[1][47:32]/[31:0] | mrd 地址 |
| 0x34 / 0x38 / 0x3c | tlp_addr_info[2][31:0] / [3] / [4] | cpl / reg_wr / reg_rd |
| 0x40 | mrdb_cnt | |
| 0x44 / 0x48 / 0x4c | rq_cnt / rq_wr_cnt / rq_rd_cnt | |
| 0x50 / 0x54 | rc_cnt / rc_error_status_cpl_cnt | |
| 0x58 / 0x5c | seg_err_status_cpl_cnt / rc_back_cnt | |
| 0x60 / 0x64 | compd_tlp_u_cnt / compd_tlp_cnt | |
| 0x68 / 0x6c / 0x70 / 0x74 | cq_cnt / cq_wr_cnt / cq_rd_cnt / cq_unsupport_cnt | |
| 0x78 | cc_cnt | |
| 0x7c | ramp_prog | 读回 |
| 0x84 | （写）ramp_prog 更新 | `awaddr==0x84` 写 wdata |

握手（在 axi2pci 作 AXI-Lite 从暴露给 host）：
- 读：`arready` 恒 1（组合，初值）；`rvalid` 在 `arvalid` 拍置 1、`rready` 清 0；`rdata` 由 `arvalid` 时 case 组合选择。`rresp='0`。
- 写：`awready`/`wready` 在 `awvalid&wvalid` 同时置 1、完成清 0；`bvalid` 在 `awready&wready&awvalid&wvalid` 置 1、`bready` 清 0；`bresp='0`。
- `ramp_prog` 复位值 32'd4，`awvalid & {awaddr[11:2],2'h0}==0x84` 更新 —— 即 host 经 CQ/CC 写该寄存器再配 PCIe（mrd 用于 ramp 测试，见 mrd.sv 输入）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)