# CRC 簇与内建发包器（common/parse-hash-demux）– part2

> 承接 [part1](parse-hash-demux_part1.md)（position_check/axis_rxq_demux/sdip_hash_gen）。本页覆盖 rtl/common/ 的 CRC 原语簇 `crc16_d64`/`crc_adjust`/`crc16_pipeline`/`hash_32b_gen` 以及可综合发包器 `eth_pkt_gen`。

## 1. CRC 簇实现细节

| 模块 | 位宽 | 多项式/初值 | 复位语义 | 说明 |
|---|---|---|---|---|
| crc16_d64.sv（模块名 **CRC16_D64**） | 64b 入/16b 出，**首串行位 D[63]** | `x^16+x^15+x^2+x^0`（0x8005，MSB 先，非反射） | `crc_out<=0`（!data_en） | 单级 64b 并行 CRC，XOR 簇预展开；无独立 init，靠 data_en 门控 |
| crc_adjust.sv | 16b×2 入/16b 出 | 同 0x8005 | `clear` 清零 | 把两个 CRC 各 64b 块合并（`crc_out = f(crc_in0(新块), crc_in1(累计))` 组合展开），用于接力累积 |
| crc16_pipeline.sv | 256b 入/1 周期 | 初值 `restart_d[4]?16'hffff` | `clear_d[4]` | 4× CRC16_D64 级联 + crc_adjust 收尾，din/vld/restart/clear 各 6 级移位；可从任意字节重启（restart） |
| hash_32b_gen.sv | 64b 入/32b 出 | `crc = 1+x^1+…+x^32`，rst→`c=32'hffffffff` | **rst 兼 init**（新包/新键起始） | 32b CRC（0x04C11DB7）并行 LFSR，`crc_en` 门控 |

**crc16_pipeline 级联细节**（供复刻）：
```systemverilog
// 4 级 CRC16_D64：每一级把上一级结果作为 crc_in
crc_din_crc[0] = 0;   crc_din_crc[i] = crc_dout_data[i-1];   // i=1..3
crc_din_data[i] = 从 din_d1..d4 各取 64b（错开 1 拍）
crc_adjust: crc_in1 = restart_d[4] ? 16'hffff : crc_out    // 初值/接力选择
```
- 架构意义：256b 长字拆 4×64b 并行 CRC、再两级（D64→调整）合并，1 拍吞吐；`restart` 允许 CRC 窗口起点不在字边界，契合 position_check 的行内偏移窗口。
- 注意 `hash_32b_gen` 的 `rst` 是「**重新初始化**」（置全 1）而非清除：sdip_hash_gen rst=ip_vld_ff1、payload_hash_gen rst=din_d[3].sop、blacklist/t_hash_gen/cfg_ip_parsing 同理。每个 64b 键块只喂一次 `rst+crc_en`。
- `crc16_d64` 与 `crc_adjust` 无 rst 端口——有效窗口由外围 `data_en/clear` 描述，属纯组合 XOR 网络存寄存器。

## 2. eth_pkt_gen —— 可综合内建发包器（RTL 版）

- 位于 rtl/common，**可综合**（纯 always_ff 寄存器电路，无仿真原语），输出 `BUS#(256,2)::C`。
- 控制字 `eth_pkt_ctrl[31:0]`：bit0=使能 `pkt_send_en`、[15:4]=包长 `pkt_send_len`、[31:16]=包间隙 `pkt_send_gap`。
- 内容固化：sop 拍四字 `{12345678abcd2234, 0000003308004500, 0032000100004006, 14183234abcd3234}`（以太+IPv4 头雏形），其余拍重复 `{…5002 27108db2…}`；`ch = {6'h0,2'd3}`（eth_id=3）。
- 状态由 `pkt_length/pkt_gap_cnt/pkt_send_en[2:0]` 计数刻画：length==0 空闲、==1 发 sop、1<len<send_len 发中间、==send_len 发 eop，随后 gap 计数。
- 实际用途：top.sv `inst_eth_pkt_gen` 出 `eth_pkt_gen_out`，仅在 TLV 源 `if(0)` 分支里作为 `tlv_din` 候选源——**当前 if(1) 分支（cfg_axis 直连）生效，该模块输出空挂**（综合可能被优化掉），属调试注入预留件。仿真侧同名 task `eth_pkt_gen()`（testcase_inc.svh）是另一物，勿混。
- 结论：可综合发包器成立（带回环口径、支持定长定隙），仅未接入当前数据路径。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)