# 黑名单 / 端口组（续 2/4）

### 3.5 背压与带宽

`ddr_rd_rdy_pre` 4 级链，`rd_gap_lvl`(0/1) 在 `~ddr_rd_rdy & ddr_rd_rdy_d & fifo_empty[1]` 时置 1，否则在 `ddr_rd_rdy_d` 时按 `pkt_ft_match!=4'hf` 刷新——注释称短包带宽 64×75%(gap1)/67.5%(gap1.5)/60%(gap2)。pps 计数 `pps_async_cnt(PERIOD=5_000_000)` 测 `ddr_req_cnt/ddr_res_cnt`。

## 4. blacklist_tcam：不综合的 TCAM 数据通路（参考）

`rtl/blacklist/blacklist_tcam.sv`（`if(0)` 死代码，但**注释与接口仍具参考价值**，与 filter 结构高度对称）。

- 输入 ch=44b，匹配键 `{sip[127:96]?,sip...}`。查 TCAM `tcam_64p`：
  - 键 64b：`s_axis_lkup_tdata <= fifo_key_dout[1]`，`fifo_key_din={st_e_feild.sip[127-:32], st_e_feild.sip[31:0]}`（sipH32+sipL32）——两 FIFO（eth_key_fifo 64b×6、eth_data_fifo 全包×6）各 DEPTH=6。
  - 响应 `m_axis_lkup_tdata[103:0]`：`[103:96]=key(8B)`、`[39:8]=priority(2B)`、`[7:0]=response_id`、`[33:32]=err_flag(1b)+match_flag(1b)`（注释 `[103:0]`，实际位宽 104 / **待核实**）。
  - `pkt_drop_flag[0] <= (m_axis_lkup_tdata[33:32]!=0)`（err 或 match 即丢）。
- `tcam_64p` 顶层封装：`key_clk=clk`、`rstn=~rst`、AXI 配置口 awaddr 13b。含 `rst_busy/sbiterr/dbiterr/debug_status[31:0]` 上送 `i_tcam_info[0]`。
- `buf_afull_cnt` 初始 `32'h8000_0000`，在 `fifo_afull[1]/[0]`（死代码里还含 `1'b0` 恒假分支）置位各段计数。

**结论**：该模块整体不被综合（`if(0)`），其 TCAM IP、AXI 配置、sc_fifo 全部失效；生效路径见 §2 else 分支。因此 `tcam_mem_map` 的 TCAM 相关计数器不会变化（待核实）。

## 5. pkt_rply_defines.v 常量

`rtl/pkt_replay/pkt_rply_defines.v`，两段：

| 宏 | 值 | 含义 |
|---|---|---|
| `PKT_LENB` | 16'h0800 | 报文长度寄存器地址（BASE+0x800）；也是缓存容量上限（0x800/4=512 word） |
| `BUSY_STAT` | 16'h0804 | 忙状态寄存器（BIT0=busy） |
| `W_CNTR` | 16'h0808 | 回写入包计数 |
| `R_CNTR` | 16'h080c | 回放出包计数 |
| `PW_ERR` | 16'h0810 | 写错误标志（BIT0=pkt_wr_err） |
| `RD_IDLE` | 3'b000 | 读 FSM 空闲 |
| `RD_FIRST_WORD` | 3'b001 | 读第一字 |
| `RD_LOAD_FETCH` | 3'b010 | 读第二字（首字已寄存） |
| `RD_TX` | 3'b011 | 帧发送中 |
| `RD_EOF` | 3'b100 | 帧尾发出 |
| `U_DLY` | 1（可覆盖） | 寄存器赋值延迟 `#`U_DLY` |

寄存器地址均为 BASE+偏移，BASE 默认 `24'h9_0000`。


## 6. pkt_rply：BRAM 回放写/读时序

`rtl/pkt_replay/pkt_rply.v`（综述 §4.13 覆盖了状态命名，补细节）。

### 6.1 写入侧（s_axis_aclk 域）

- 容量：`xpm_memory_sdpram`，`ADDR=512`、`MEMORY_SIZE=72*512`、写/读各 72b。写宽 9b×8（`.wea(bram_wren)` 8-bit 每字节位），`BYTE_WRITE_WIDTH_A=9`。
- 每地址存 72b=`{9b×8}`：高 36b 与低 36b 对称，各含 4 组 `{tlast_bit(1), data(8), cnt_bit(1)}` 9b。`address[2]` 选高/低 4 字节；`bram_wren[7:4]/[3:0]`。
- **写数据格式**：非末拍 `{1'b0,data,1'b0,...}`；末拍 `last_beat` 时 `{1'b1,data,byte_count[2],1'b1,data,byte_count[1],1'b1,data,byte_count[0],1'b1,data}`——tlast 比特与**字节低 3 位**一起写入，供读侧还原 tkeep。
- `byte_count`：`range_hit & wr_vld & (PKT_LENB==addr) & ~busy` 时锁存 `wr_data`（报文总字节数）。
- `busy`：`bufr_we` 时 `busy ? (byte_cntr>4|!byte_cntr) : (|byte_count)&(!bufr_waddr)`——首拍必须**地址 0 起写**，否则忙标志不置（数据无效）。
- `byte_cntr`：`busy ? byte_cntr-4 : byte_count-4`（每拍减 4）；`last_beat=busy & byte_cntr<5 & |byte_cntr`。
- `pkt_wr_err`：`bufr_we & ~busy` 时 `|bufr_waddr`——**未忙时非 0 地址写即报写错**（PW_ERR）。
- `tgl`：末拍 `bram_wdata[35] & bufr_we` 翻转（指示一包写完）；`write_pkt_cntr` 同条件累加。

### 6.2 读侧回放（eth_rx_clk 域）

- 跨时钟：`tgl` 经 `HARD_SYNC(LATENCY=2)` 同步到 `tgl_sync_rd`；`tgl_sync_rd_ff1` 再寄存一拍。`pkt_wr = tgl_sync_rd_ff1 ^ tgl_sync_rd`（边沿检测，一包一脉冲）；`pkt_rd = RD_LOAD_FETCH==rd_fsm_curr`。
- `rmn_pkt_cntr`：`{pkt_wr,pkt_rd}`=10 加一 / 01 减一（未回放完的包数）。
- 读 FSM：`RD_IDLE`（|rmn_pkt_cntr→FIRST_WORD）→ `RD_FIRST_WORD`（无条件→LOAD_FETCH）→ `RD_LOAD_FETCH`（→TX）→ `RD_TX`（`m_axis_tready & rx_done_rd`→EOF，rx_done_rd=`ram_do[35]|ram_do[71]`，即高/低半字任一带 tlast）→ `RD_EOF`（tready→IDLE）。
- `bram_rden`：`RD_FIRST_WORD | RD_LOAD_FETCH | (RD_TX & m_axis_tready)`（BRAM 读 latency=1）。
- `bram_do_valid`（=`m_axis_tvalid`）：`RD_LOAD_FETCH` 置 1，EOF&tready 清 0。
- `bufr_raddr`：IDLE 清 0，`bram_rden` 时自增。
- **tkeep 还原**（末拍 `ram_do[35]` 高半或 `ram_do[71]` 低半 tlast）：每字节打 `{cnt bit 3 位}>i | !值`，即 `!{b2,b1,b0}` 时该字节使能（取反自适应的空字节）；tkeep[7] 单列。
- `m_axis_tdata`：打散 `ram_do` 8×9b，去掉 tlast/cnt 位＝64b 净数据。`m_axis_tuser=0`。
- `read_pkt_cntr`：`m_axis_tlast & m_axis_tvalid & m_axis_tready` 累加。

## 7. pkt_rprx_comb：回放 与 网口接收 二选一

`rtl/pkt_replay/pkt_rprx_comb.v`。组合两个部分：
1. `pkt_rply` 实例（`BASE_ADDR=24'h9_0000, READ_LATECNY=2, REG_AW=15`）。
2. 回放报文与网口接收报文 2to1 mux，**网口接收优先级高**：
```verilog
assign m_axis_tdata  = s_axis_tvalid ? s_axis_tdata  : pr_axis_tdata;
assign m_axis_tuser  = s_axis_tvalid ? {7'd0,s_axis_tuser} : {7'd0,pr_axis_tuser};
assign m_axis_tkeep  = s_axis_tvalid ? s_axis_tkeep  : pr_axis_tkeep;
assign m_axis_tlast  = s_axis_tvalid ? s_axis_tlast  : pr_axis_tlast;
assign m_axis_tvalid = s_axis_tvalid | pr_axis_tvalid;
assign pr_axis_tready= m_axis_tready & ~s_axis_tvalid;
```
- **无缓存、不缓存切换瞬间的 packet**：网口数据有效期间 `pr_axis_tready=0`（回放被 backpressure），网口 tlast 后下一拍才让回放继续。代码注释明示「目前未加入缓存，以及在 tlast 时切换 grant 的情况，**后续务必补充**」——这是已知限制项。
- 复归 `tuser` 上送时高位补 7'h0（`{7'd0,s_axis_tuser}`，s_axis_tuser 1b、m_axis_tuser 8b）。


> 继续：[part3](filters-portgroup-replay_part3.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
