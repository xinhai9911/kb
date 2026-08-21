# TLV 配置下发链路：cfg_axis → cfg_pkt_check → tl_parsing → t_hash_gen/邻接/会话

> 源路径：`rtl/tlv/tl_parsing.sv`、`rtl/tlv/cfg_pkt_check.sv`、`rtl/tlv/cfg_ip_parsing.sv`、`rtl/tlv/t_hash_gen.sv`、`rtl/table/session_t_sch.sv`（侧带校验 TLV 接口部分）
> 定位：表项（会话/ACL/黑名单/邻接）的**配置下发数据面**。CPU/PCIe 通过 AXI-Stream（`cfg_axis_*`）将"TLV 型以太网配置报文"写入，经本链路解包、译码、CRC 哈希、背压对接后落到 DDR4 表区与邻接表。**基线综述见 50-reference/sources/chips/ips_test_2025_fpga.md §4.4；本页只写配置下发专属链路，不复述数据面查表。** 会话表数据面查表 FSM 另见同目录 [session-table.md](session-table.md)。

## 0. 整链数据流与时钟域

```
cfg_axis_* (AXI-256, sys_clk)           -- top.sv L599:  byte 反序拼进 tlv_din[255:0]
  │  tlv_din = AXI_256{vld,last,keep,data[255:0]}
  ▼
cfg_pkt_check  (rtl/tlv/cfg_pkt_check.sv)  AXIS→BUS-C(vld/sop/eop/left/data/ch) 按以太长度截断、归类 ch[1:0]
  │  cfg_pkt_dout = BUS#(256,2)::C
  ▼
tlv_fifo (sc_fifo_idx, DEPTH=6)  -- 存 cfg_pkt_dout
  ▼
cfg_ip_parsing (rtl/tlv/cfg_ip_parsing.sv)  识别 VLAN/IP 层、提取 dmac/smac/ip/端口/pid，重组为"表项 TLV" 256b
  │  cfg_ip_dout[0..2], hash_o_pre[] (sip/dip 两路 CRC32)
  ▼
tl_parsing (rtl/tlv/tl_parsing.sv)
  ├─ v_dout= BUS#(256,6)::C  → t_hash_in → **t_hash_gen**（算 25b 表基址哈希）
  │     ├─ v_dout0 → ddr_wr_sch_in[i*2]   (会话/ACL：ch[28]=表型)
  │     └─ v_dout1 → ddr_wr_sch_out[i*2+1] (黑名单)
  │     bus_c_sch  汇聚 → dc_fifo_c_ctrl(跨 sys_clk→DDR ui_clk) → ddr_ctrl 表写
  │     ddr_db_wr   = DDR#(512,29)::RES   经 dc_fifo_across → clk_100m → ddr_ctrl DB 通道
  └─ adj_dout= BUS#(256,0)::B → top.sv L1669 `adj_tab_vld/adj_tab_val` → 邻接表模块
ddr_cfg_cnt[0..5] / t_hash_gen.ddr_cfg_cnt  → 寄存器统计
```

时钟：整链 TLV 处理在 **sys_clk**（业务时钟）；`t_hash_gen` 额外 `clk_100m`（DB 写跨域）、`ddr_ctrl` 用 **ui_clk**（DDR 用户时钟）读写。

`add_cfg[1:0]`（top `table_add_cfg`）用于 `cfg_ip_parsing` 选黑名单加/删（151/152），其来源是寄存器配置（非本链路数据）。

## 1. cfg_pkt_check —— AXIS→BUS-C 校验与归类

只吃"配置报文"，输出 `BUS#(256,2)::C`。ethertype 常量：`VLAN=16'h8100、IPV4=16'h0800、IPV6=16'h86DD、ARP=16'h0806、OTHERS=0`；`LEN_MAX='d4`（最多取 4 拍 256b=128B 即截断）。

判定（每帧 SOP 拍）：
- QINQ：`data[255-96-:16]==VLAN && data[255-128-:16]==VLAN` → etype 取 `data[255-160-:16]`
- 1 VLAN：`data[255-96-:16]==VLAN` → etype 取 `data[255-128-:16]`
- 无 VLAN：etype 取 `data[255-96-:16]`

`ch[1:0]` 归类（帧体位于 256b 高 12B 之后的 etype）：

| ch[1:0] | 含义 | 条件 |
|---|---|---|
| 0 | 黑名单配置报文 | etype==IPV4/IPV6/ARP（`case IPV4/IPV6/ARP: ch<=0`） |
| 1 | 会话或 MAC 替换报文 | etype==OTHERS 且 `tmp_sop&pkt_din_d.last` 为假（非单帧） |
| 2 | 报文非法 | etype 为其它 / OTHERS 且是单帧 `tmp_sop&last` |

输出时序（`pkt_din_d` 延迟一拍）：
- `eop = vld && (last || pkt_vld_cnt==LEN_MAX)`（截断到 4 拍）
- `vld = vld && pkt_vld_cnt<=LEN_MAX`
- `tmp_sop`：帧起点标记（rst 后=1，last 清回 1）

归错（ch=2）的帧会被 `tlv_fifo` 写侧 `~cfg_pkt_dout.ch[1]` 在 `tl_parsing` 中过滤掉。

## 2. tl_parsing —— 中央译码与分发

头部注释给出 `v_dout.ch[5:0]` 定义：

| 位 | 含义 |
|---|---|
| [5:4] | 0=null；1=add；2=del |
| [3:0] | 0=session；1=ACL；2=黑名单；3=邻接表（default 4=null） |

### 2.1 TLV type 表（SOP 拍读 `cfg_ip_dout[1].data[247-:8]`）

写侧经 `cfg_pkt_check`（ch[1]=0 才入 tlv_fifo）→ `cfg_ip_parsing` 重排后，在 `cfg_ip_dout[1]` 的 SOP 拍取 `data[247-:8]`（字节 1，即 TLV type 第二个字节）判决：

| TLV type | add/del | 表属 (ch[3:0]) | tlv_ctrl | 动作（v_dout 出口） |
|---|---|---|---|---|
| 151 | add | 2 黑名单 | {2'd1,4'd2} | 黑名单添加 |
| 152 | del | 2 黑名单 | {2'd2,4'd2} | 黑名单删除 |
| 161 | add | 0 会话 | {2'd1,4'd0} | 会话添加 |
| 162 | del | 0 会话 | {2'd2,4'd0} | 会话删除 |
| 171 | add | 1 ACL | {2'd1,4'd1} | ACL 添加 |
| 172 | del | 1 ACL | {2'd2,4'd1} | ACL 删除 |
| 196 | add | 3 邻接表 | {2'd1,4'd3} | 邻接添加 |
| 197 | del | 3 邻接表 | {2'd2,4'd3} | 邻接删除 |
| 其它 | — | 4 空 | {2'd0,4'd4} | 无效 |

> 奇 type=加、偶 type=删；type 数值本身不再下传，"表属+加删"编码进 ch[5:0] 与 `ddr_cfg_cnt` 计数索引。

### 2.2 输出 v_dout（BUS#(256,6)::C）三级流水

- `data_comb` = `{data_comb[0+:256], cfg_ip_dout[0].data}`（512b 窗口，跨两拍拼接）。
- 黑名单（ch[3:0]==2）：只出 SOP 拍，`data=data_comb[511-24-:256]`，eop=sop（单拍载荷）。
- 会话/ACL（ch[3:0]<3，# 即 0 或 1）：`sop`=dout[2].sop、`eop`=dout[1].eop、`vld=dout[1].vld&dout[2].vld`（两拍对齐）。
- 邻接/空（else）：vld 恒 0（走 adj_dout 或丢弃）。
- `ch<=tlv_ctrl`。

### 2.3 邻接输出 adj_dout（BUS#(256,0)::B）

仅 ch[3:0]==3（邻接，type 196/197）时 sop/eop/vld = `cfg_ip_dout[2].sop`；`left='d13`（13B 有用载荷）；`data[255-:16]`=邻接信息高 16b（`data_comb[511-24-:16]`），`data[0+:240]` 在 **del（ch[5]）** 时清 0，add 时填 `{96b 信息,144'b0}`。top.sv L1669 接 `adj_tab_vld/adj_tab_val` 进邻接表。

### 2.4 ddr_cfg_cnt[5:0] 统计

- `[0]`：每帧（tlv_din.vld&last）+1。
- `[4:1]`：add（tlv_ctrl[4]）且 SOP 时，按 ch[1:0] 表属 +1 → `[1]=session、[2]=ACL、[3]=黑名单、[4]=邻接`。
- `[5]`：del（tlv_ctrl[5]）且 SOP 时 +1（不分表属）。

## 3. tlv_fifo 背压（tl_parsing 内嵌 sc_fifo_idx）

- 写侧：`fifo_in_vld=cfg_pkt_dout.vld & ~ch[1]`（过滤非法帧 ch=2 / 部分黑名单帧标记）。
- `fifo_rdy`：`afull ? 1 : (dout_vld&eop ? 0 : fifo_pkt_cnt>0)`；`fifo_afull=10`（DEPTH=6）。
- `fifo_pkt_cnt` 维护读写包计数差，作为上游 ready 依据——cfg_pkt_check 无需 ready 信号（AXIS 假定 back-to-back 可吸收，靠 FIFO 深度 6 抖动）。


> 继续：[part2](tlv-config-path_part2.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
