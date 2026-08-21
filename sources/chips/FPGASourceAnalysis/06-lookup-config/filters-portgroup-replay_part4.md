# 黑名单 / 端口组（续 4/4）：pg_tab 与 pg_req

## 9. pg_tab：端口组下发表（DL/UL 双路）

`rtl/port_group/pg_tab.sv`，`ETH_NUM=64`，clk_100m 域做表、clk 域查表。BASE 12 位高段参数化。负责把「某 ethid → 落到 local/ovc 跨度内第几个可用端口」下发，含 DL（下含 session 查表）与 UL（上行 trunk）两半。

- **配置表** `ram_tdp`(7×32b distributed，地址 `local_in.address[8:2]`)：软件按 ethid 写 64 项。`pg_cfg_rd_hit` 一拍命中判断，读回 `pg_cfg_rd`。
- **link_list[63:0]**：按 `link_cnt(6b 循环)` 与 `local_sid[0]/[1]` 拼接的 8 个本地口 `link_status[7:0]` 填到表内相对槽位（VLAN_ID==0 分支）；VLAN_ID==1 时直接 `link_list<=link_status_switch`（64b 整表）。
- **cycle_trigger**：`cycle_trigger_cnt` 每 64(clk_100m) 拍触发一次，`cycle_trigger_seq` 0..63 轮转——每周期遍历 64 个表项/端口。
- **cfgcnt 配置导出**：`cfging` 在 cycle_trigger 置位、`&cfgcnt(63)` 清位；每拍 `cfgcnt+1`，`ram_b_addr={seq,1'b0|1}` 双口读两项；`rd_b_dout_v=rd_b_dout[cfgcnt[4:0]]`、`link_list_v=link_list[cfgcnt]`；`wren=cfging_ff1 & rd_b_dout_v & link_list_v`（表项使能且链路在 list 中）→ `XPM_ASYNC_FIFO`(8b) 写 `wd=cfgcnt_ff1`。
- **num 表** `XPM_SDP_RAM`(64×6b distributed)：每 seq 周期 `num_waddr<=cycle_trigger_seq`、`num_wd` 累计可下发端口数，`num_wren<=&cycle_trigger_cnt`。读侧 `num_raddr<=pg_sop_id`。
- **端口分配表** `XPM_SDP_RAM`(4096×8b block)：`ram_waddr=64*seq + 递增`，`ram_wd<=rd`（FIFO 弹出的 port id）。查表：`ram_raddr=pg_dl_req_id_ff[2]*64 + num_cnt_lat`。
- **DL 流程**（配合 pg_req）：
  - `num_rden<=|pg_sop`，`num_raddr=pg_sop_id[0]/[1]`：`num_rd`=该 pg_id 可用端口数。
  - `num_cnt[i]`（64 个 6b）：`pg_dl_req_ff[1]` 且命中 i 时，按 `num_rd` 取模回绕（`num_cnt[i]>=num_rd-1` 则清 0，否则 +1）——轮询分配。
  - `no_avaliable`：`num_rd==0` 置 1（无可用端口），经 3 级延迟 `no_avaliable_ff3`。
  - `pg_rdv[i]`：`ram_rdv & i==sw_ff[5]`（sw 选 0/1 路）；`pg_rd[i] <= no_avaliable_ff3 ? pg_dl_req_id_ff[5] : ram_rd`——**无可用端口时回原 pg_id（自环），否则下发分配到的端口号**。
- **UL 流程**：`ul_pg_vld_l/h[i]` 由软件写 `address[8:3]==i & address[2]==0/1` 置位（写 0 清除）——两条 64b 掩码；`ul_pg_vld=ul_pg_vld_l|ul_pg_vld_h`。`session_eth_id_g=local_sid+session_eth_id`（全局 ethid）→ `session_pg_vld=ul_pg_vld[ethid[5:0]]` → `trunk_port[i]`。即 session 上送时判断其目标 ethid 是否属于某端口组（trunk 判定）。

## 10. pg_req：报文原语 与 下发端口 的 FIFO 配对

`rtl/port_group/pg_req.sv`，`CHW=181, VLAN_ID` 参数。两状态 `IDLE/RD`。

- 三段 `XPM_ASYNC_FIFO`（均 clk 域同步，distributed）：
  - `Rq`(16×8b)：入 `din.vld&din.sop` 时的 `din_eth_id`；出 `rq_rdv/rq_rd`。
  - `Rs`(16×8b)：入 `pg_rdv/pg_rd`（下发端口）；出 `rs_rdv/rs_rd`。
  - 数据 `FIFO0`(32×`$bits(din)`=32×256+ch)：完整报文缓存。
- 时序：`IDLE` 且 `rs_rdv`（有下发端口）→ `RD`；`RD` 中 `rden&rdv&rd.eop` → 回 IDLE。读允许 `rden` 在进入 RD 后置 1。
- **改写**（对齐 `rd.sop`）：
  - `VLAN_ID==0`：`dout.ch[175-16-8 -:8] <= rs_rd`（把包内 ethid 换成下发端口）；ch 其余 + data 直通。
  - `VLAN_ID==1`：改 `dout.data[255-15*8 -:8] <= rs_rd`（VLAN 场景 ethid/端口字节在数据位）。
- `pg_sop = rq_rden & rq_rdv`；`pg_sop_id = rq_rd`（把入向 ethid 上报给 pg_tab 查可下发端口）；`rq_rden=~pg_fb`（下行忙反馈时停止取请求）。
- `rs_rden = c_state==RD & rden & rdv & rd.eop`（一包读毕才取下一个下发端口，保证报文与端口一一配对不串包）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
