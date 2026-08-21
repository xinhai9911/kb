# 下行数据流：down_stream_block / down_stream_unit（读请求 FSM 与报文解析）

源文件：rtl/dma/down_stream_block.v、rtl/dma/down_stream_unit.v

## 1. down_stream_block 视图

与 up_stream_block 同构：`s0`(256b) 描述符输入 → `fifo_sync_axis_256x512` → `axis_dwidth_converter_1`(256→64) → 每队列 `down_stream_unit`；分发 `s_axis_tvalid_unit[i]=s_axis_tvalid_nrw&(i==s_axis_tdest_nrw[$clog2(QUEUE_COUNT)+1:2])`（=tdest[4:2]），`s_axis_tready_nrw` 由目标单元回。与 up 侧差异：

| 项 | down 侧 | up 侧对比 |
|---|---|---|
| unit 参数 | `W_O=2`、`MAX_DESC_NUM=64`、`DESC_CNT_LEN=11/DIFF_DW=12` | 最大取 64 / 128 / 13+1/14 |
| 描述符内容 | 每条 64b 除地址外**内含报文 len/port/地址字段**（§2） | 仅地址 |
| 输出 | `desc_used[511:0]`（16×32b）→ ptr_update_block 供软件回读 | — |
| 读请求合并 | 3 级 `abtr_4to1`，但 s00~s02_tid **直连** unit 的 s_tid | 上抬 tid[0] 再还原 |

`desc_hdr_til_diff_n`、`desc_til_ofst_n`（n=0..3）调试量级输出同 up。

## 2. down_stream_unit：取描述符 + 报文读请求产生

### 2.1 描述符取回（desc_req）
与 up_stream_unit 同逻辑：`desc_hdr_til_diff=hdr-til`、`desc_end_til_diff=num-til截断`（截位 `down_desc_num[6..12]`，默认 512 档）；`num_reg=min(两差)`；请求序号握手（`desc_req_seq` vs `desc_ack_seq`，均用 `s_axis_tvalid&s_axis_tlast` 经 3 拍移位判定整批返回）后 `desc_req <= ena`（`ena` 由 `down_desc_load` 置位）。地址 `desc_addr={start[63:48],{start[47:3],3'h0}+{ofst_trunc,3'b000}}`；`desc_length={3'b0,delta,3'b000}`。差异点：
- `desc_hdr_til_diff_r` 在 `|pkt_req_pre && diff>=256` 时高位自增（防饱和，调试）。
- 可装空间算法与 up 不同：`fifo_desc_in_avlb_spc <= desc_buf_pe_th<DESC_BUFF_DEPTH-1-MAX_DESC_NUM ? MAX_DESC_NUM : 0`，`desc_cntr_delta = num_reg>avlb?avlb:num_reg`（真 min，up 为 all-or-nothing，见上行文 §2），配合 fifo 的 `prog_empty_thresh`（待核实）。

### 2.2 描述符字段解析 → 4 个报文子队列
单元内生成 4 路 `fifo_sync_fwft_72x512 fifo_desc_in`（子队列 i=0..3，按描述符内 2 位队列选择）：

```verilog
.din({8'h0, s_axis_tdata[3:0], s_axis_tdata[15:4], s_axis_tdata[63:59], s_axis_tdata[58:16]}),
//  cfg/flag[3:0]   pkt_len[11:0]   port_id[4:0]    pkt_addr[42:0]
.wr_en(s_axis_tvalid && s_axis_tdata[60:59] == i)
```
（`NSFOCUS_KU15P_FRAME` 分支 wr_en 用 `data[59]==i` 且只例化 2 路；else 分支 i 恒 4 路。）`pkt_req_pre[i]=` 各子队列 valid；填充满置 `fifo_desc_in_ae[i]`。`s_axis_tready=1'b1` 恒通，溢出置 `desc_fifo_overflow`。

### 2.3 轮询读取与读请求组装
`rd_cnt` 记录上次 pop 的子队列；优先序 (rd_cnt→rd_cnt+1→rd_cnt+2→rd_cnt+3)（模 4），取非空子队列锁存：
```
pkt_length = odata[59+i*72 : 48+i*72];      // 12b
pkt_addr   = {start_addr[47:43], odata[42+i*72 : 0+i*72]};  // 高 5b 全局 + 43b 本地
pkt_uflag  = odata[63+i*72 : 60+i*72];      // 4b
pkt_dest   = odata[47+i*72 -: 5];           // 5b port id
```
`req_cnt` 记录本次拿走的是哪个子队列。请求发出：
```verilog
M00_AXIS_TDATA = desc_req ? {desc_length,desc_addr} : {4'h0,pkt_length,pkt_addr};
s_tid = desc_req ? {1'b0, UNIT_NUM[5:0], `DOWN_STREAM, 1'b0}     // 描述符读，bit1=0 下行
                 : {2'b0, pkt_dest[4:0], pkt_uflag[0]|`DOWN_STREAM, 1'b1}; // 报文读，bit0=1，[6:2]=port
s_req  = desc_req | pkt_req;                 // desc 优先（pkt_req 等 desc_req 空）
desc_ack = s_ack & desc_req;
```
- `pkt_req`：`|pkt_req_pre` 置位 ⇒ s_ack&pkt_req&~desc_req 清；`|pause[2:0]` 时抑制（`pause` 为 12 拍移位节流）。`pkt_ack[i]` 按 `req_cnt` 回弹对应子队列 FIFO，同时用作 `rd_cnt` 更新。
- **`desc_used`**：`s_req&s_ack&s_tid[0]` 自增（即**报文读请求**计数；注释名"已取走的描述符计数"——一笔报文对应消耗一条描述符，语义待核实）。
- 错误标志：取到零长度（`!data[15:4]`）或零地址（`!data[47:16]`）置 `desc_err`。

> 继续：[down-stream_part2.md](down-stream_part2.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)