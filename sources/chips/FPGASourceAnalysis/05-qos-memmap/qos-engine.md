# QoS 6 队列引擎分析（rtl/qos/ 五模块：qos_block · fc_bucket · pkt_info · host_intf · qos_defines）

> 源路径：`rtl/qos/qos_block.v`、`fc_bucket.v`、`pkt_info.v`、`host_intf.v`、`qos_defines.v`。综述 §4.15 仅一句（模块名 host_inft + BASE 8_8000），本文补全引擎拓扑、6 队列表空间、令牌桶表项结构与整块寄存器地图。QoS 附在 256-bit 报文数据面上，实现三级别（per_ip→policy→line）流控令牌桶。

## 1. qos_block.v：6 队列拓扑与数据通路

端口面：2 输入流 S0/S1 与 2 输出流 M0/M1（各 256-bit busy/left/sop/tuser/tlast/tvalid/tready），配置侧 cfg_clk(100M)+s_axis_aclk(200M) 双时钟，axi-lite 从口 `address/wr_vld/wr_data/rd_req/rd_vld/rd_data`。

```systemverilog
// qos_block.v 参数
parameter CIR_DW=24, TUSER_DW=72, REG_AW=8, BASE_ADDR=24'h8_8000,
          PER_IP_DEPTH=8192, POLICY_DEPTH=512, LINE_DEPTH=16,
          PKT_CNTR_DW=48, PPLN_STAGE=2
```

表项空间即“6 队列”，头注释明确地址分区：

| 索引区域 | 队列 | 深度 |
|---|---|---|
| 0~8191 | up, per_ip | 8192 |
| 8192~16383 | down, per_ip | 8192 |
| 16384~16895 | up, policy | 512 |
| 16896~17407 | down, policy | 512 |
| 17408~17423 | up, line | 16 |
| 17424~17439 | down, line | 16 |

查询流水：两路 `pkt_info`（TUSER_DW+1 例化）抽 QoS 字段→各存 `fifo_sync_fwft_36x1k info_fifo`→`qos_mux_2to1` 合并为 srch（带 ch 标识 CHNL_0/1）；`per_ip_en` 分流走 per_ip 或 policy 桶，输出再经 mux 进 line 桶；line 判决 `line_result=user[13]` 按 `line_id=user[12]` 分写 `fifo_sync_fwft_4x4k rslt_fifo_0/1`，与 `fifo_sync_axis_pkt_256x512` 报文 FIFO 对对时门控输出；**仅 pass 报文出**：`m0_tvalid <= pf_tvalid_0 & rslt_fifo_valid_0 & rslt_fifo_dout_0[0] & hold_one_cyc_0`（tlast 后 hold_one_cyc 停一拍防错配）。

辅助机制：
- 1ms 定时：`clk_cntr` 计数 `CLK_FRQ/1000`(200000) 产生 `pulse_1ms`；再计 1000 个 1ms 进位 5-bit `current_time`（0~31s）。
- 计数：`s0/s1_pkt_cnt`（输入 SOF）与 `m0/m1_pkt_cnt`（输出 SOF）各 48-bit，接 host_intf 读回。
- `over_flow`：init_done 后，任一 rslt_fifo full 或任一输入/查询口反压即置 1（寄存器可读）。

## 2. fc_bucket.v：流控令牌桶通用单元

可参数化 `TABLE_DEPTH(512/16384/1024/32 例化)、BRAM_RD_LATENCY=2、CIR_DW=24`。内部仲裁读请求（降优先级）：`HOSTOP(上位机)>SEARCH(前级查询)>UPDATE(1ms 刷新)`；写仲裁 88bit：`buffer_we>pktcntr_we>host_wdata`，且回写请求固定高优不阻塞。

BRAM 表项（`xpm_memory_sdpram`，144bit×TABLE_DEPTH，byte-wren[17:0]，read_first）：

| 位段 | 字段 | 说明 |
|---|---|---|
| [143:140] | 4'd0 | 填充 |
| [139:108] | pass_pkt_cntr[31:0] | 放行字节计数 |
| [107:104] | 4'd0 | 填充 |
| [103:72] | drop_pkt_cntr[31:0] | 丢弃字节计数 |
| [71:48] | token_c[23:0] | 当前令牌数 |
| [47:24] | CIR[23:0] | 承诺信息速率（/1ms 增量） |
| [23:5] | CBS[18:0] | 承诺突发（字节）；预算=CBS*32 |
| [4:0] | time_stamp | 最近更新时间戳 |

上位机“67-bit 表项回读”（`host_rdata=ram_do[71:5]`，即 `{token_c,CIR,CBS}` 共 24+24+19=67bit）；写字 `host_wdata[42:0]`={CIR[42:19],CBS[18:0]}，time_stamp 由硬件回填 `current_time`，token_c 初值=CBS<<5（注释：`{token_c_init(bit)=CBS(Byte)*32}, CIR & CBS`）。统计数据回读（s_t=1）：`host_rdata = {3'd0, pass_cntr, drop_cntr}`。

判决与回写（带数据相关反馈，4 级旁路拍 r1~r4 选最新文件）：
- 放行条件：`!CIR | ~tc_en`（未配置/未使能全放行）且 `token>>3 >= pkt_len+4`（令牌按 8B 单位、长度含 4B CRC），首级查找结果 frnt_srch=1。
- SEARCH：pass 则 `token_c -= (pkt_len+4)*8`，并 `pass_cntr += pkt_len`；否则 `drop_cntr += pkt_len`。
- UPDATE（每 1ms 全表扫描）：`token_c = min(token_cbs, token_c+CIR)` 刷新桶；同时 `(current_time - time_stamp) > TIMEOUT(15s)` 则清表项。
- 老化删除走 `bram_wren[5:0]` 的“timeout & update”分支清零 token/time_stamp。

## 3. pkt_info.v：QoS 字段提取与包长测量

256-bit 直通（tdata/left/tuser 原样透传，`m_axis_tuser=s_axis_tuser>>20`），`sop=tuser[TUSER_DW-1]`。字段在其上 EOP 采样：

```systemverilog
tc_en      <= s_axis_tuser[19];
up_dn      <= s_axis_tuser[18];   // 上/下行
per_ip_en  <= s_axis_tuser[17];
line_fc_id <= s_axis_tuser[16:13];
fc_id      <= s_axis_tuser[12:0];
```

包长：每 beat `rx_len_i += 32`，SOP 清零；EOP 拍 `rx_len = rx_len_i + i_left`（11-bit，字节），`rx_len_we` 触发写 info_fifo。

## 4. qos_defines.v 常量

`SEARCH=2'd0/UPDATE=2'd1/HOSTOP=2'd2`；`TIMEOUT=5'd15`；`TOKEN_C_MAX`；`CLK_FRQ='d200000000`；`CHNL_0/1`；及 host_intf 全部寄存器偏移宏（见 §5）。

## 5. host_intf.v（模块名 `host_inft`）：BASE 0x08_8000 窗口

`range_hit = BASE_ADDR>>REG_AW == address>>REG_AW`，即 address[23:8]==0x88，窗口 0x08_8000~0x08_80FF（256B）。寄存器（`qos_defines.v` 宏，相对偏移）：

| 偏移 | 宏 | 位宽 | 读写 | 说明 |
|---|---|---|---|---|
| 0x00/0x04 | S0_PKT_CNTR_H/L | 48 | R | 输入流 0 SOF 计数 |
| 0x08/0x0c | S1_PKT_CNTR_H/L | 48 | R | 输入流 1 |
| 0x10/0x14 | M0_PKT_CNTR_H/L | 48 | R | 输出流 0 |
| 0x18/0x1c | M1_PKT_CNTR_H/L | 48 | R | 输出流 1 |
| 0x28 | TABLE_WADDR | 32 | W | 间接写表项地址 |
| 0x2c/0x30/0x34 | TABLE_WDATA_2/1/0 | 32×3 | W | 间接写数据（72bit 拆 3 字） |
| 0x38 | TABLE_RADDR | 32 | W | 间接读表项地址（读触发） |
| 0x3c/0x40/0x44 | TABLE_RDATA_2/1/0 | 32×3 | R | 67-bit 回读拆 3 字 |
| 0x48 | TIMOUT_EN | 1 | RW | 默认上电 1（开老化） |
| 0x4c | OVER_FLOW | 1 | R | 反压溢出标志 |

间接读写协议：写侧依次写 WADDR+WDATA_0/1/2，各寄存器置位 `tbl_wden_*/tbl_waen`，四者齐后再触发一次 fifo_we 成一条命令；读侧写 `TABLE_RADDR` 即入 FIFO（`host_cmd_r=0`）。命令经 `fifo_async_fwft_72x512`（模块名，cfg 域→数据域异步 FIFO）在 fc_bucket 执行，`{host_wdata,host_cmd,s_t,host_fc_id}=fifo_dout`。回读：`rd_data` 用 rd_req 拍一拍锁存的 address_r 译码，延迟 READ_LATECNY=2 拍出 `rd_vld`。s_t=0 读表项、s_t=1 读统计（写统计=再写表区域，注释未明确意义，见待核实）。

## 6. 待核实

- qos_block 在 top.sv 中整块 `/* */` 注释**未实例化**（原接 mem_out[0][12]）。
- fifo_async_fwft_72x512 未随包提供源码，din 拼接 112bit 与“72x512”名是否匹配存疑。
- 源码无“优先级/权重”寄存器/参数，调度语义 = 三级别级联令牌桶 + 2 方向 6 队列（头注释），无显式 WRR/队列状态机。
- host 写 stats 无专用清零路径，计数器清零方式未见（可能是表项写回顺带清）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)