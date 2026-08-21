# 黑名单 / 端口组（续 3/4）：port_group

## 8. port_group 查表改写（pg_top / port_group）

`rtl/port_group/pg_top.sv`（LBS 寄存器壳）+ `port_group.sv`（查表改写核）。综述 §4.12 给了寄存器 offset 0x0/4/8/c/10/14，这里补**映射与流水**。

### 8.1 pg_top LBS 寄存器

| 偏移 | 读写 | 内容 |
|---|---|---|
| 0x0 | RW/RO | 写=`pg_cfgw_id`，读回 `pg_cfgw_id` |
| 0x4 | RW | `pg_cfgw`（写表条目数据） |
| 0x8 | RW | `pg_cfgr_id`（读表条目索引） |
| 0xc | RO | 读回 `pg_cfgr`（读表结果） |
| 0x10 | RO | `{24'b0, pg_id_cur}`（当前包 pg_id） |
| 0x14 | RO | `pg_tab_value`（当前包查到的表值） |

- 写译码：`pg_cfgw_vld = wr_vld & addr[23:12]==BASE & addr[11:0]==4`；`pg_cfgr_vld = wr_vld & addr[23:12]==BASE & addr[11:0]==8`。BASE 为实例参数（12 位高段）。
- 读：`tmp_rd` 一拍锁存 + `tmp_rdv` 一拍 → `local_out.rd_vld/rd_data`（共 2 拍）。
- `local_sid`(8b)、`ovc_sid`(8b) 透传进 port_group。base `BASE` pg_top 实例由上层给定（**rtl/port_group/ 内未定值，待核实顶层**）。

### 8.2 port_group 数据通路

- 输入 `din.ch[180:0]`：`[180:177]=RSS(4b)`、`[176]=pak_tracing(1b)`、`[175:0]=macid(2B)+flag(1B)+ethid(1B)+natip(16B opt)+natport(2B opt)`。关键索引 `eth_id` 位在 `ch[175-16-8 -:8]`（flg 之后的 ethid 字节）。
- 三级移位 `din_ff1/ff2/ff3` 对齐 `pg_ram`（`XPM_SDP_RAM block 2^IDW × CFGW`，默认 256×32）查表延迟。
- 查表启动：`din.vld&din.sop` 时 `pg_ram.raddr<=din.ch[175-16-8 -:8]`（用包内 ethid 查）；`mux_vld=ff3_id[7]`（ethid 最高位做门控，7 判定该包需改 PG）。
- `tab_vld = pg_ram.rd[31:16]!=0`（表项计数段非 0 才改写）。
- 改写逻辑（`mux_vld & tab_vld`，ff3 对齐）：
  - `pg_ram.rd[31:16]` 存 8 个 2-bit 幅度 `eth_num[7:0]`；`eth_sum[i]=add(eth_num,i)` 前缀和；`cnt_sum=add(eth_num,7)`。
  - 用 `pg_ram.rd[15:0]`（包序计数器）`< eth_sum[7..0]` 分级映射 ethid → `local_sid..+3` 或 `ovc_sid..+3`。
  - 同时 `dout.ch[175-16-8 -:8]` 被改写，其余 ch/data 直通。
- 表自学习：`din_ff3.vld&din_ff3.sop` 时写回 `pg_ram`：`wd[15:0]<= rd[15:0]+1`（达到 `cnt_sum-1` 清零循环），`wd[31:16]<=rd[31:16]`。即 **pg_ram[15:0] 是同一 pg_id 的包序计数**，`[31:16]` 是软件写的各端口幅度。
- 配置/回读经两条 `XPM_ASYNC_FIFO`（clk_100m→clk）：
  - `FIFOw`（IDW+CFGW 位）：`pg_cfgw_vld` 写入 `{pg_cfgw,pg_cfgw_id}`；`pg_cfgw_rden` 读取。`pg_cfgw_rden` 默认 1，`din_ff2.vld&sop` 时清 0（避免查表期间灌配置）。写 RAM 时 `waddr<=pg_cfgw_rd[IDW-1:0]`、`wd[15:0]<=0`、`wd[31:16]<=pg_cfgw_rd[IDW+CFGW-1-:16]`。
  - `FIFOr`（IDW 位）：`pg_cfgr_id` 作索引读表，结果 `pg_cfgr<=pg_ram.rd`（经 `pg_cfgr_vld_ff1/2/3` 对齐）。

时序要点：**查表与改写在 ff3 级对齐**（`din_ff3` 读到 `pg_ram.rd` 恰好 SOP），保证首字即用新 ethid；配置读写均经异步 FIFO 跨 100M/核心钟域，`pg_cfgw_rden/pg_cfgr_rden` 均被 `din.*sop` 拉低以让路报文查表。


> 继续：[part4](filters-portgroup-replay_part4.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
