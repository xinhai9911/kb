# top.sv 深度解剖（part 3：TLV 透传 / DDR 实例 / 双卡 NUMA / bypass_en）

> 承接 part 2。行号均指 `rtl/top.sv`。

## 4. TLV 透传路径（配置下发链路）

```systemverilog
// 源头：design_bd_wrapper.cfg_axis_0（AXIS 256bit，sys_clk 域）
//       cfg_axis_tdest[8:0] 标注目标；cfg_axis_tready 恒 1（top.sv:393）
// top.sv:598-605  `if(1)` 分支：TLV 数据 = cfg_axis_tdata，
//        字节序反转逐字节搬运：tlv_din[i].data[j*8 +: 8] = cfg_axis_tdata[i][255-j*8 -: 8]
//        备用注入源 eth_pkt_gen（寄存器写包，eth_pkt_ctrl 由 top_mem_map 给出）被禁用
tlv_din[i]（AXI_256）→ tl_parsing（add_cfg=table_add_cfg，来自 top_mem_map）
   ├─ v_dout → t_hash_in BUS#(256,6)::C → t_hash_gen（4 深流水线 CRC32）
   │           └→ ddr_wr_sch_in（写请求）→ 会话/流表 DDR
   └─ adj_dout BUS#(256,0)::B → mac_rep_tab.adj_tab_vld/val（全局单例，双卡合并）
```

`t_hash_gen` 又叫 `inst_t_hash_gen`，输入带 `ddr_cfg_cnt[i*7+6]`、`gbl_timeout`/`st_timeout`/`acc_aging_hold`——即 TLV 表项进 DDR 的写侧前端，与 `session_t_sch` 的哈希读侧配套。

## 5. DDR 实例数（有效 2 片，各卡 1 片；第二片为死代码）

| 项 | 事实 | 源码 |
|---|---|---|
| 每卡 MIG | `u_ddr4_0_dns`（c0：DQ=64b、UI 512b、地址 28b） | top.sv:1271-1309 |
| 每卡用户侧 | `inst_ddr_ctrl_0`（写调度/hash 自检/请求合并） | top.sv:1188-1227 |
| 活 DDR 控制器数 | 2 = CHNL_NUM × 1（双卡各 1） | — |
| c1（第二片 16b DQ/128b UI） | `ddr4_1_dns`+`inst_ddr_ctrl_1` 整段注释 | top.sv:1229-1268, 1316-1354 |
| 残留 | DDR_GEN j=1 的`dc_fifo_c_ctrl`/`dc_fifo_across` 仍例化，其 `rd_clk=ui_clk[i*2+1]` **无源**（全工程仅 `c0_ddr4_ui_clk→ui_clk[i*2]` 一处驱动） | top.sv:1098-1113, 1229+ |
| GOLDEN（仿真） | 改为 assign：`init_calib_complete/ui_rst/self_check/d_rd_res` 按 `SIM_MODE` 固定 | top.sv:1177-1185 |
| 用户 28b 地址 | MIG 端口拼 `{1'b0,c0_app_addr[i]}`（29b） | top.sv:1296 |
| 读响应分发 | `rd_res_demux`（2→3，DW=512,CHW=28）：会话/黑名单/host 调试读三路 | top.sv:1355-1366 |

`c0_app_*` 512b 写数据（`cmd/wdf_data/mask` 等）与 `d_rd_req/d_rd_res` 形成「用户 512b 数据面 ↔ MIG UI」桥接；`c1_app_*` 128b 信号仅注释块在用。

## 6. 双卡 NUMA 端口清单

| 信号 / 连接 | 说明 |
|---|---|
| `up_numa` 输入 `{ul_dma_in[4], ul_dma_in[0]}` | 硬连线取**口 4 与口 0** 汇聚双卡上行（P 端即 local 与对卡各一路） |
| `crs_crd_numa`（N_NUM=2，全卡单例） | `numa_din[1:0] → axi_in[1:0]` 双卡交错调度 |
| `pcie_channel_id_in / _in_en = 对卡 [1-i]` | top_mem_map 通道号交叉交换（双卡互识，top.sv:929-930） |
| `Forward_top[i]` 输入 `ovbc_tx[1-i]`、`dout_ovc_cnt[1-i]` | 对卡 OVC（对卡出包）快照反哺 |
| `crs_crd[i]`：`local_sid[0]` / `ovc_sid[1]` | 本卡 / 对卡卡号选路（每卡 8b `local_sid`） |
| `mac_rep_tab`（全局单例，`ADJ_FLAG_NUM=CHNL_NUM`） | 邻接表双卡合并；`adj_ses_raddr`/`macid` 双套查询口 |
| `link_status_switch[i]`（top_mem_map 出） | 每卡链路切换控制 |
| `r_bypass_en[× 卡][11/13]` 等 | NUMA 相关旁路位（见 §7） |

## 7. `r_bypass_en[i][31:0]` 位定义（置位位置全集）

| bit | 消费模块 | 说明 |
|---|---|---|
| [0] | Ingress / Egress（40G 用 `[0][0]`，10G 用 `[1][0]`） | 端口级旁路（交叉口 Egress 直通 `i^3'b001`） |
| [1] | `eth_ul_pkt_parsing`（ETH0..3 用 3b 组 `{r_bypass_en[1][2:1], r_bypass_en[0][1]}`） | 解析 bypass，命中即判「未知包」 |
| [2] | 同上（ETH4..7 用 `{r_bypass_en[1][4:3], r_bypass_en[0][2]}`） | 同左（注意两组解析都**横跨双卡**取位） |
| [5] | `session_t_sch`（`\|r_table_clear[i][0]`） | 会话查询旁路 / DDR 清表 |
| [8] | `eth_sta` ckes_bps | 校验和旁路 |
| [10] | `axis_rxq_demux` | DMA RXQ 旁路 |
| [11] | `crs_crd_numa`（卡 0/1 各自位） | NUMA 交叉旁路 |
| [12] | `crs_crd` | 路由 / OVC 旁路 |
| [13] | `up_numa`（`{r[1][13], r[0][13]}`） | 跨卡 UL 汇聚旁路 |
| [14] | `position_check` | 协议位置检测旁路 |
| [7] | `blacklist_proc` —— **源码 `1'b1` 硬编码**（原 `r_bypass_en[i][7]\|r_table_clear[i][1]` 已注释，top.sv:1428-1429） | 黑名单整链旁路当前常开 |

特征：位分配散落、且解析器三 bit 组跨越双卡寄存器取值，属历史演进（新功能顺手占用新位）；**无集中位定义文档**，改寄存器时须回 top.sv 全量核对本表。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)。