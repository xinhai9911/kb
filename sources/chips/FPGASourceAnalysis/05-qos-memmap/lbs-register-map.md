# LBS 内存映射体系寄存器地图（top_mem_map 与各 *_mem_map）

> 源路径：`rtl/common/top_mem_map.sv`、`rtl/table/st_sch_mem_map.sv`、`rtl/blacklist/tcam_mem_map.sv`、`rtl/eth/pkt_parsing_mem_map.sv`、`rtl/payload_hash/payload_hash_mem_map.sv`、`rtl/pkt_tracing/pkt_tracing_mem_map.sv`。本文把综述 §3.1 槽位表与各 *_mem_map 补成逐寄存器地图；只列源码事实。

## 1. 总线与译码方式

- 每通道 1 条 `MEM#(32)::IN mem_in`（address[23:0]/wr_vld/wr_data/rd_req，def/user_bus_def.sv 定义）由 top.sv 广播到同通道全部 16 个 `mem_out[16]` 槽。
- 各 *_mem_map 用 `case({mem_in.address[23:2],2'd0})`（4B 对齐字地址）命中自家 localparam；未命中 `rd_data=0`。
- `rd_vld` 由 rd_req 打 1 拍统一输出；top.sv 将 16 槽 `rd_data` 逐位 OR 合成 `reg_axi_rdata[i]`。地址位宽 24bit 字节地址，槽内步长 4B，窗口约 256B。

## 2. mem_out 槽位表（按 top.sv 实例核实，修正综述 §3.1）

| 槽 | 模块（_mem_map 实例位置） | LBS 基址 |
|---|---|---|
| [0] | top_mem_map | 0x08_0000 |
| [1]~[4] | eth_ul_pkt_parsing ×4（pkt_parsing_mem_map，ETH_ID=0~3） | 0x08_5000 + ETH_ID*0x100 |
| [5] | eth_sta（local_out） | — |
| [6] | session_t_sch（st_sch_mem_map） | 0x08_6000 |
| [7] | blacklist_proc（st_sch_mem_map 0x08_7000 + tcam_mem_map 0x08_9000，OR 合出） | 0x08_7000/0x08_9000 |
| [8] | Forward_top（FORWARD_BADDR=12'h084） | 0x08_4000 |
| [9]/[10] | update SPI 主/从 | 0x08_3000 / 0x08_3800 |
| [11] | axis_rxq_demux（内含 payload_hash_gen→payload_hash_mem_map） | 0x08_a000 |
| [12] | qos_block（top.sv **注释未接**） | 0x08_8000 |
| [13] | pkt_tracing_mem_map（**注释未实例化**） | 0x08_f000 |

## 3. top_mem_map（BASE 0x08_0000，槽[0]）

| 偏移 | 寄存器 | 读写 | 说明 |
|---|---|---|---|
| 0x00~0x0c | NIC_DATE/TIME/REV/VER | RO | 编译日期、时间、发布/版本；NIC_VER=DEF_NIC_VER+DEV_ID*0x100000 |
| 0x10 | TABLE_CLEAR | RW | 表清除控制（bit 分发到会话/黑名单等） |
| 0x14 | BYPASS_EN | RW | 上电 0x61（dl/ul checksum bypass、pkt_sta loopback）；看门狗超时强制置 bit0 |
| 0x18 | ETH_PORT_MAP | RW | 端口映射 |
| 0x1c | ETH_LOOPBACK | RW | 环回 |
| 0x20 | CORE_RST | RW | 写反相（~data[3:0]） |
| 0x24 | CORE_RX_EN | RW | 收使能[3:0] |
| 0x28 | CARD_STATUS | RO | 板卡状态 |
| 0x2c | ST_TIMEOUT | RW | st(0xff000000)/udp[27:16]/tcp[15:0]，默认 0x01e001e |
| 0x30 | USER_RST | WO | 写触发 user_rst[0]；读返回 0 |
| 0x34/38/3c | DDR_RD_DB0/1/2 | RO | pps 异步计数器/DDD RD 调试快照 |
| 0x100 | LOCAL_ID_NUM | RW | local_sid，上电=DEV_ID*4 |
| 0x104/108 | LINK_STATUS_L/H | RW | 64-bit 链路状态开关 |
| 0x10c~0x11c | HASH_SIP/DIP/RES/PORT/D | RO | 恶魔哈希调试（hash_gen_*） |
| 0x120 | XADC_TEMP | RO | 温度寄存器透传 |
| 0x130 | DMA_FULL_BYPASS | RW | 默认 1 |
| 0x154/0x180 | DMA_FULL_DROP_CNT / POSITION_MATCH | RO | 统计 |
| 0x1b0/0x1b4 | PORT_CFG_RAM_WR/RD | RW | 4b×7 分布式 RAM（RSS 配置，同 st_sch 的 RSS 结构），wr[15:12] 数据 / [11:0] 地址 |
| 0x1f0 | PCIE_CHANNEL | RW | pcie_channel_id，写后置 en 一拍 |
| 0x1fc | BUS_CHECK | RW | 总线自检字 |
| 0xe0~0xec | WATCH_DOG_NUM/CNT/CLR/EN | RW/RO | 1s 计数 CNT==NUM→置 BYPASS_EN[0]；CLR 清零（EN[0]） |
| 0xf0~0xfc | DDR_CFG_CNT0~3 | RO | |
| 0x124~0x12c | DDR_CFG_CNT4~6 | RO | |

DDR 调试口（详见 §10）：0x40~0x8c DDR_DB_WR_A3/A2/A1/A0+D15~D0；0x9c DDR_DB_RD_A0；0xa0~0xdc DDR_DB_RD_D15~D0。

## 4. st_sch_mem_map（0x08_6000 槽[6] session_t_sch；0x08_7000 槽[7] blacklist_filter，同一模块两实例）

（偏移相对各 BASE）

| 偏移 | 寄存器 | 读写 | 说明 |
|---|---|---|---|
| 0x00~0x24 | DIN0/DOUT0/1/2/3_SOP_H/L | RO | 6×48-bit SOF（会话 4 路+输入+流）计数 |
| 0x28 | A_RD_REQ | RO | |
| 0x2c~0x38 | P0/P1_DROP_CNT_H/L | RO | 48-bit 丢弃计数 |
| 0x3c~0x4c | DDR_DIFF/DDR_REQ_CNT/DDR_RES_CNT/DIFF_MAX/BUF_AFULL_CNT | RO | DDR 读写差、req/res、峰值、缓冲达到 |
| 0x50 | T_S_RATE | RW | 出速率配置 o_t_s_rate |
| 0x54 | DMA_FEILD_DB | RO | DMA 字段（dma_feild_db 快照） |
| 0x58 | RD_TIME_LIMIT | RW | 读超时限 |
| 0x5c | GBL_TIMEOUT | RO | 全局会话超时（i_gbl_timeout） |
| 0x60~0x6c | BYTE_CNT0/1_H/L | RO | 48-bit 字节计数 |
| 0x70 | DB_FWD_CFG | RW | 查表转发配置 o_db_fwd_cfg |
| 0x74 | DB_FWD_CHECK | RO | 查表转发校验回读 |
| 0x78 | EMPTY_STATUS | RO | 空状态 |
| 0x7c | FWD_ACT | RW | 转发动作字 o_fwd_act |
| 0x80 | AGING_CFG_ST | RW | 老化启动（bit31 为写脉冲） |
| 0x84/0x88 | AGING_CFG_TIME/NUM | RO | 老化时间/数量（只读回显） |
| 0x98 | FT_RD_DB_INFO | RO | FT 回读信息 |
| 0x9c | FT_DB_RD_A0 | WO | DDR ft_info_db 读地址触发 |
| 0xa0~0xdc | FT_DB_RD_D15~D0 | RO | 512-bit DDR 读回 |
| 0xe0~0xf0 | RSS_CFG_CNT0~4 | RO | 5×RSS 命中计数 |
| 0xf4/0xf8 | RSS_CFG_RAM_WR/RD | RW | 4bit×12 block RAM 写/读，wr[15:12] 数据 [11:0] 地址 |
| 0xfc | BUS_CHECK | RW | |

注：0x08_7000 实例（blacklist_filter）中 gbl_timeout/aging 输入接 0、rss_* 未连，仅 session_t_sch 实例启用 RSS/AGING。

## 5. tcam_mem_map（0x08_9000 槽[7]，blacklist_tcam 内 `generate if(0)` 未生成）

| 偏移 | 寄存器 | 读写 | 说明 |
|---|---|---|---|
| 0x00/0x04/0x08/0x0c | DIN0/DOUT0/1/2_SOP | RO | SOF 计数 |
| 0x10~0x1c | TCAM_INFO_0~3 | RO | TCAM 信息（4×32） |
| 0xfc | BUS_CHECK | RW | |

当前构建 `if(0)` 被综合掉（mem_out_pre[1]=0）。

## 6. pkt_parsing_mem_map（0x08_5000+ETH_ID*0x100，槽[1]~[4]）

| 偏移 | 寄存器 | 读写 | 说明 |
|---|---|---|---|
| 0x00~0x08 | DIN0/DOUT0/DOUT1_SOP | RO | SOF 计数 |
| 0x0c~0x38 | DMAC_H/L、SMAC_H/L、ETH_TYPE、FRAG_TTL、P_ID、DIP_32B、SIP_32B、DPORT、SPORT、TCP_FLAG | RO | ETH_FIELD 报文解析快照（DPORT/SPORT 拼 vlan；TCP_FLAG=l4_h_len+tcp_flag） |
| 0x3c | PKT_DB_INFO | RO | 报文查库信息 |
| 0x3c→0x40~0x7c | DMAC_CFG_H/L0~7 | RW | 8×48-bit DMAC 白名单表 |
| 0x80 | DMAC_CHECK | RW | 使能 DMAC 匹配（bit0） |
| 0x90 | RSS_PORT_EN | RW | RSS 端口使能（bit0） |
| 0xa0 | SEOP_CHECK | RO | SEOP 校验计数 |
| 0xfc | BUS_CHECK | RW | |

## 7. payload_hash_mem_map（0x08_a000，槽[11] axis_rxq_demux 内 payload_hash_gen）

| 偏移 | 寄存器 | 读写 | 说明 |
|---|---|---|---|
| 0x00~0x10 | DIN0/DOUT0/1/2/3_SOP | RO | SOF 计数 |
| 0x14~0x28 | HASH_INFO_0~5 | RO | 哈希查询信息（6×32） |
| 0x2c | HASH_CAL_CFG | RW | [20:16] sop_offset、[4:0] eop_offset |
| 0x30 | HASH_QUE_CFG | RW | 队列拼装掩码：bit0 p_id、bit1 dport/sport、bit2/3 sip/dip 置零 |
| 0x34 | HASH_ADD_CFG | RW | bit[15:0] 哈希加常量 |
| 0xfc | BUS_CHECK | RW | |

## 8. pkt_tracing_mem_map（0x08_f000，top.sv 注释未实例化；模块存在）

| 偏移 | 寄存器 | 读写 | 说明 |
|---|---|---|---|
| 0x00 | SESSION_HASH | WR→cfg[17] | 读回 cfg[17] |
| 0x04~0x68 | PKT_PARSING_DB0~3→db[0..3]；ETH_STA_DB0/1→db[4..5]；SESSION_SCH_DB0~2→db[6..8]；QOS_BLK_SB0→db[9]；BLACKLIST_DB0/1→db[10..11]；RXQ_DEMUX_DB0/1→db[12..13]；DMA_RX/CRS_CRD/REP_MAC/REP_IP/REP_PORT_DB0→db[14..18]；MTU_TX_DB0/1、CRS_BOARD_DB0、ETH_TX_DB0~3→db[19..25] | RO | 26×32 回读（i_pkt_tracing_db） |
| 0xfc | BUS_CHECK | RW | |
| 0x100~0x11c | DATA_SEL0~7 | WR | →cfg[16..9] |
| 0x120~0x13c | DATA_MASK0~7 | WR | →cfg[8..1] |
| 0x140 | DATA_OFFSET | WR | →cfg[0] |

cfg 输出 `o_pkt_tracing_cfg[17:0]` 供各子系统抓包检测（filter/window 选择）。

## 9. 其它非 *_mem_map 窗口（仅登记基址，展开待核实）

- update（QSPI/SPI flash 更新）：主 0x08_3000（槽[9]）/ 从 0x08_3800（槽[10]），寄存器未展开（不在本次范围）。
- Forward_top：FORWARD_BADDR=12'h084（槽[8]，基址 0x08_4000）；综述 §3.1“QSPI 0x001_000”在本次 6 文件无对应声明。

## 10. DDR 调试口（top_mem_map）

- 写：DDR_DB_WR_A3~A0（0x40~0x4c 拼 128-bit 地址）+ D15~D0（0x50~0x8c 拼 512-bit 数据）→ 逐周期发 ddr_db_wr。
- 读：写 DDR_DB_RD_A0（0x9c）下发地址（bit28=类型、bit0 关联 rd_res_demux）并置 req.vld；0xa0~0xdc 回读 512-bit；0x34/38/3c 为 pps 快照。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)