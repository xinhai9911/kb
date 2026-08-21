# PCIe 顶层桥与四条 TLP 队列通道

> 深读 `rtl/pci/` 的 `pci_top.sv`/`pci_xil_wrapper.sv`/`pci_xil_wrapper_top.sv`/`xil_rq.sv`/`xil_rc.sv`/`xil_cq.sv`/`xil_cc.sv`，配套 `axi2pci.sv`/`pci_xil_core_wrapper.sv`/`def/pci_bus_def.sv`。综述 §4.6 已有的 mwr/mrd/mreq/scompd/tag_manger 内部细节不复述。

## 1. 层次结构

实路（design_bd_wrapper.sv 例化）：

```
dma/bd/design_bd_wrapper.sv
├── axi2pci                    # 用户 AXI-256 + AXI-Lite 寄存器
│   ├── pci_xil_wrapper        # TLP 桥
│   │   ├── pci_top            # mwr/mrd/mreq/tag_manger/scompd 装配层
│   │   ├── xil_rq  →s_axis_rq # 上行请求（DMA 数据面）
│   │   ├── xil_rc  ←m_axis_rc # 下行完成（DMA 读回）
│   │   ├── xil_cq  ←m_axis_cq # 下行寄存器读/写请求（host MMIO）
│   │   └── xil_cc  →s_axis_cc # 上行寄存器读完成
│   ├── s_axi_w/s_axi_r        # AXI-256 → mwr/mrd
│   ├── m_axi_lite_w/_r        # CQ → AXI-Lite 主
│   └── axi_reg                # 统计/状态寄存器从
└── pci_xil_core_wrapper       # Xilinx PCIe IP（4 条 AXIS）
```

`pci_xil_wrapper_top` 是另一完整封装（自带差分时钟、`pci_exp_*` x8、AD_W=62），但库内**无例化，属备胎/骨架**：以 `.R_BACK_SORT_W(5)` `.PTR_W(11)` 例化 `pci_xil_wrapper`，而后者参数表没有这两个参数→elaboration 应报错（**待核实**）；大量统计悬空、`ramp_prog` 硬接 32'h200、`s_axis_*_tready[3:0]` 只取 `[0]`、mrdb 用 `#(256,AD_W+16)` 对不上端口 `#(256,10)`。其 W/R_MAX_TLP_LEN=256、TAG_W=6。

`axi2pci` 用 `localparam AD_W=62`，`W_MAX_TLP_LEN = SIM_MODE?256:512`；时钟均取 PCIe IP 的 `user_clk`。

## 2. pci_top：TLP 桥装配层

端口三组：用户侧 `mwr`@#(256,AD_W)、`mrd`@#(64,16+AD_W)、`mrdb`@#(256,10)；PCIe 侧 `mreq_tlp`@#(256,AD_W) avl_tlp_mm、`compd_tlp`@#(256,0) avl_tlp_comp、`mreq_tlp_pfull`、`compd_tlp_rdy`、`cpl_sop_gap[63:0][4:0]`；另有一长串统计输出（mwr/mrd 各 cnt/tlp_cnt/max_len/min_len、sort_*_pkt_hisroty、tag_id_hisroty、tlp_addr_info、rc_back_cnt、mrdb_cnt、seg_err_status_cpl_cnt，输入 ramp_prog）。

| 例化（参数） | 关键连线 |
|---|---|
| `mwr`(W_MAX_TLP_LEN,AD_W) | mwr(256)→mwr_tlp；反馈 pfull |
| `mrd`(AD_W,R_MAX_TLP_LEN,R_MAX_USR_LEN,TAG_W) | mrd(64)→mrd_tlp；产 cpl_sop_gap |
| `mreq`(AD_W,W_MAX_TLP_LEN) | 合并两路→mreq_tlp；对 pfull 反压 |
| `tag_manger`(AFULL_TH=32) | mrd_tag_info/compd_tlp→cpl_tag_wrinfo |
| `scompd`(PTR_W=10,AFULL_TH=30) | cpl_tag_wrinfo+compd_tlp→mrdb |

两条链：**上行** mwr/mrd→mreq→mreq_tlp；**下行** compd_tlp→tag_manger→scompd→mrdb（用户读回），mrdb_afull 反馈。`cpl_sop_gap` 由 mrd 产出供 xil_rc 对齐完成流。`tlp_addr_info[2:0]=[0]mwr/[1]mrd/[2]scompd`；文件尾 `ramp_rcnt='h0` 悬空占位。

**W_MAX_TLP_LEN 生效处**：仅经 mwr/mreq（pci_top 默认 128，axi2pci 覆盖 256/SIM 512）；mwr.sv 用 `$clog2(W_MAX_TLP_LEN/32)` 作对齐分帧窗+满长判定，并按 `W_MAX_TLP_LEN>128?8:16` 设 FIFO AFULL。读方向由 mrd.sv 用 `R_MAX_TLP_LEN`/`R_MAX_USR_LEN` 切 MRD（Gen3 `link_speed_mode=1` 时单拍 64DW，否则 32DW）。

## 3. xil_rq：上行请求队列（→ s_axis_rq）

`mreq_tlp` → `d_slide_right`(din_slide=16, INFO_W=$bits(tlp_mm)) → 拼头 → `fifo_sync_0` → `s_axis_rq`。

- 头 discr[127:0]（sop 拍）：`force_ecrc,attr,tc,requester_id_en,completer_id,tag,requester_id,poisoned_req,req_type,dw_count,address,at`；`req_type=MRD(无数据)?MEM_READ_REQ:MEM_WRITE_REQ`；`dw_count={1'b0,length[9:0]}`；`address=AD_W==62?tlp_mm.address:{32'b0,address[29:0]}`（xil_rq 默认 AD_W=30，real=62）。
- 读请求 left 恒 16（4DW 头），避开右滑移位。
- tuser：`[3:0]=fbe`、`[7:4]=lbe`、`[27:24]=pcie_rq_seq_num`（eop 自增，每 TLP 流号）、`[60]=f_p`→tdebug；`tkeep=left2keep(left[4:2]+|left[1:0])`；sop 拍 128b 内字序重排、非 sop 256b 全重排（`conver_seq128/256`）。
- `fifo_sync_0`：DW=326(1+256+8+60+1)、AFULL=12；`mreq_tlp_pfull=fifo_afull` 提前反压 mreq。
- 统计：rq_cnt(eop)、rq_wr/rq_rd_cnt（tdata[78:75]=0001/0000）。

## 4. xil_rc：下行完成接收（← m_axis_rc）

`m_axis_rc`(256b, tuser[74:0]) → `compd_tlp`(avl_tlp_comp) 送 scompd。

- tready：空闲 `=compd_tlp_rdy`；eop 后 `~compd_tlp_rdy||tkeep>'h7` 拉低（分片停收）。
- 首拍 `rc.data={tdata[95:0],bsc_160b(tdata[255:96])}`，其余 `bsc_256b`；`rc_first_left=be_calc(tuser[15:12])`、`rc_last_left` 按最后拍 tkeep 位选 `tuser[4*k+:4]`。
- **丢弃短完成**：`rc.sop & left∈{1,2,3}` → rc_ff1.vld=0（`rc_drop_cnt` 统计）。
- **多片重组**（64 路）：`req_cpld_cnt[i]` 记在途片数、`uncpld_left/uncpld_data[i]` 存残余；`rc_ff3_ch[95:91]=sop_gap=req_cpld_cnt!=0?uncpld_left+cpl_sop_gap[tag]:cpl_sop_gap[tag]`，作第二个 `d_slide_right` 的 din_slide(INFO_W=96)；`rc_ff5` 拼 `uncpld_data|left_data_clr`，`ch[90]|=uncpld_1_clk`。ch 高 96b：`[90]req_cpld`、`[89:85]sop_gap`，低 90b 为 CPL 头字段（status/length/byte_count/tag/rid/lower_addr）直供 compd_tlp 映射。
- **仅放行成功完成**：compl_status≠0 时 compd_tlp_u.vld=0；`rc_error_status_cpl_cnt[31:28]` 锁存最近 status、低 28b 累加。
- 统计：rc_cnt、compd_tlp_cnt/u_cnt。

## 5. xil_cq：下行寄存器读写请求（← m_axis_cq）

`m_axis_cq`(256b)；`tuser[84:0]` **完全未用**，字段均解析自 TLP 头 tdata：`attr[126:124]`、`tc[123:121]`、`bar_aperture[120:115]`、`bar_id[114:112]`、`target_function[111:104]`、`tag[103:96]`、`requester_id[95:80]`、`req_type[78:75]`(0=MRd 1=MWr)、`dw_cnt[74:64]`、`address[63:2]`、`at[1:0]`。

- tready `=~(wr|rd|rdb_pfull)`，eop 拍发现满则吸收完本 TLP 再拉低。
- `din_unsupport`：首拍 req_type∉{0000,0001} → 丢拍，`cq_unsupport_cnt` 计数。
- 流水：`din`(sop/eop/vld 捕获；left=`keep2left(tkeep)<=4?20:keep2left*4`)→ `din_ff1`(`trf2bigedding` 256b 倒序、ch=头 128b)→ `d_slide_left`(INFO_W=128, din_slide=16)→ `din_ff2`。
- 分流：按 `din_ff2_ch[78:75]`，0001→`xil_cq_wr`（写），0000→`xil_cq_rd`（读，data/left 清零只走 ch）。
- 三个分布式 `sc_fifo_idx`(DEPTH=5)：fifo_sync_w(DW=160={data[255-:32],ch})→cq_wr；fifo_sync_r(DW=128)→cq_rd；fifo_sync_rdb(DW=128)→`cq_rdb_rd`（**无 out_vld**，专供 xil_cc）。
- `cq_rd_wait_cnt`：sop 清零 →`cq_rdb_rden` 置 0x80 → 至 bit7 置位，延时锁存 `tlp_addr_info[1]`（读地址）；`tlp_addr_info[0]`=写地址（sop 锁存 ch[31:2]）。
- 统计：cq_cnt(eop)、cq_wr_cnt/cq_rd_cnt（首拍 req_type）、cq_unsupport_cnt。

## 6. xil_cc：寄存器读完成生成（→ s_axis_cc）

组合头生成；`cc_rd[31:0]`（AXI-Lite 读回 rdata）作 CPLD 数据：

```systemverilog
wire [31:0] dw2 = {fecrc,attr,tc,compl_id_en,completer_id,tag};     // tag=cq_rdb_rd[103:96], attr=[126:124], tc=[123:121]
wire [31:0] dw1 = {requester_id,1'b0,poisoned,compl_status,dw_cnt='d1}; // rid=[95:80]
wire [31:0] dw0 = {2'b0,lk,byte_count='d4,6'b0,at,1'b0,low_address};    // at=[1:0], low={[6:2],2'b0}
// s_axis_cc_tdata = {128'b0, cc_rd, dw2, dw1, dw0};   // 另有注释掉的字节序变体
s_axis_cc_tkeep=8'h0f; s_axis_cc_tuser=33'b0;
// tvalid=tlast=cc_rdv; cq_rdb_rden = cc_rdv & cc_rdv_rdy(=s_axis_cc_tready)
```

固定：fecrc=0、completer_id=0（EP 自身）、poisoned=0、compl_status=0、locked=0、byte_count=4。`cc_cnt` 按 `tready&tvalid&tlast` 计。

## 7. 与 Xilinx PCIe IP 的贴合点

- 4 条 AXIS 与 `pci_xil_core_wrapper`（xcku060=PCIE3；KU15P/VU13P 宏切 PCIE4）逐位直连（RQ tuser[59:0]、RC [74:0]、CQ [84:0]、CC [32:0]）。
- CQ 承载 host 对 BAR 的 MMIO 读写，拆成 3 条内部 FIFO；CC 回答 host 读（12B CPL+4B 数据），`pcie_cq_np_req=1` 不回压 CPU。
- RC/RQ 只管 DMA 数据面；寄存器面走 CQ/CC，与 tag 无关；`s_axis_*_tready[3:0]` 为多信用位宽，只用 `[0]`。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)