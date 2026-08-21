# 29 个测试用例语义（端口配置流式特性与判定）

> 源路径 `sim/nic_top/testcase/tc*.sv` ?? `readme.txt`；判定/寄存器回读数据来自各 tc 尾部 `initial` 的 `axi_rd32` 与 `log2file`。`tc_summary.log` 现状仅 `[2026-07-15 11:44:42] tc1 test pass`（msim_setup.tcl 第 180 行 `set tc_list {tc1}` 只跑 tc1）。
> 端口含义：A=axis_eth_40g(2 口,256b)、B=axis_eth_10g(4 口,64b)；「4×10G-only」=tc24/25（旧统一 axis）；「6 口新式」=tc32/33/34（A0-1+B2-5）。

## 判定谓词速查表

| tc | 端口 | 主配置 | 期望判定（谓词） |
|----|------|--------|------------------|
| 0 | A0+B2+B3 | 无会话表（bypass 统计出 | `tc_status[4:0]==~5'd0`；含 `axi_rd32(0,'h8_0028)==~0`；pkt_cnt 每口==20 |
| 1 | A0+B2+B3 | 虚拟线(map)(2tcp+2udp)+DMA+port_map `'h0405_0001` | `tc_status[3:0]==~4'd0`；每口收发各==20（唯一 pass） |
| 2 | A0+B2+B3 | 会话表 swap(3)+交换表 +loopback | `tc_status[3:0]==~4'h0`；out 15/in 5 不等量 |
| 3 | A0+B2+B3 | 路由 route(3)+NATPORT | `tc_status[7:0]==~8'h0`；校验改写 ip/dMAC/sMAC/port 值（`'h8_4160==dada_dadd`、`'h8_4190==ffff`） |
| 4 | A0+B2+B3 | route(1tcp+2udp, VLAN12) | `tc_status[9:0]==~10'h0`；ip/port/mac + 采样计数 3/15 |
| 5 | A0+B2+B3 | route(3)+采样配置 | `tc_status[6:0]==~7'h0`；采样字节 len `(89+4)*(16*3+4)`、vlan 双 tag=12 |
| 6 | A0+B2+B3 | route(3)+DDR 清空 | `tc_status[3:0]==4'b1111`；`'h8_7004==60` 且 `==(pkt 三计数和)`；DDR 写后清→读 0 |
| 7 | A0+B2+B3 | 无会话表+VLAN12+MAC adj | `tc_status[3:0]==~4'h0`；每口 in4/out4 |
| 8 | A1+B4+B5 | 会话表 route(3)，SYN flag | `tc_status[4:0]==~5'h0`；dev1 `'h8_6024==12`；SYN→ch[95]=1 bypass |
| 9 | A0+B2+B3 | route(3)+ICMP/IPinIP | `tc_status[4:0]==~5'h0`；`'h8_6024==12`（首包队列） |
| 10 | A0+B2+B3 | ICMP/v6 + MAC adj 4 轮 | `tc_status[5:0]==~6'h0`；`'h8_600c==3`、`'h8_6024==9` |
| 11 | A0+B2+B3 | ARP 4 轮 + MAC adj | `tc_status[5:0]==~6'h0`；`'h8_600c/6024==0`（ARP 丢弃不入队） |
| 12 | A0+B2+B3 | block(1tcp+2udp) VLAN12（tc12 自带 block ft_monitor 分支，TLV beat1 头用 `16'd171,8'd41` 而非 161/64） | `tc_status[5:0]==~6'h0`；`'h8_6004==18`；6 包全入队无转发 |
| 13 | A0+B2+B3 | 4 表项 map×80 轮 | `tc_status[4:0]==~5'd0`；`'h8_601c==240`（收发各 80） |
| 14 | A0+B2+B3 | 无会话表首包上送 + MAC adj | `tc_status[4:0]==~5'h0`；`'h8_600c==12` |
| 15 | A0+B2+B3 | swap(2)+交换表 `'h8_8000~c=1` | `tc_status[4:0]==~5'h0`；`'h8_601c==12` |
| 16 | 4×10G 统一 axis（旧） | Blacklist DDR 清空 | `tc_status[2:0]==3'b111`；`'h8_7004==80`、`'h8_7014==0`；DMA 写→清→读 0 |
| 17 | 4×10G 统一 axis（旧） | MAC adj+IP黑板+首包上送 | `tc_status[7:0]==~8'd0`；`'h8_6004==88`、`'h8_600c==80`、`'h8_601c==0`、`'h8_6024==8` |
| 18 | A0+B2+B3 | map(2) 混合包长 96~1504B | `tc_status[3:0]==~4'd0`；每口==10 |
| 19 | A0+B2+B3 | MPLS(0x8847) 64~1984B | `tc_status[5:0]=='b11_1111`；采样字节 `57+4+(1977+4)*3`、`'h8_2000==4` |
| 20 | 4×10G 统一 axis（旧） | 上行解析完整性 49×4 | `tc_status[8:0]==~9'h0`；`'h8_7078/6078==7`(DB/会话表 empty)；in==out 校验 |
| 21 | A0+B2+B3 | map(2) 1504B 跨卡 | `tc_status[3:0]==~4'd0`；port_map `'h0706_0001`，每口==20 |
| 22 | A0+B2+B3 | 随机 MPLS+TCP hash 检测 | `tc_status[5:0]==~6'h0`；`'h8_a000==50`、hash 匹配+不匹配和==50 |
| 23 | A1+B4+B5 | route(3)+双卡 DMA +采样 | `tc_status[6:0]==~7'h0`；采样 IP/dMAC/SMAC/port 回读 + `'h8_2108` 字节 len |
| 24 | 4×10G 统一 axis（旧） | 带流控路由（tc_en） | `tc_status[8:0]==~9'h0`；`defparam RAM_INIT='h35e`；`gbl_timeout` force 序列；流控 RAM 值 `'h8_e13c~e444` 逐格 =='h17/'h18/…/'ha0 |
| 25 | 4×10G 统一 axis（旧） | 带流控路由（dev1） | `tc_status[8:0]==~9'h0`；`RAM_INIT='h15e`；dev1 RAM 值 `'h8_e13c~e404` 相似并含 'h10/'h5f |

## 六口新式用例（tc32/33/34）

| tc | 端口 | 主配置 | 期望判定 |
|----|------|--------|---------|
| 32 | 6 口（A0-1+B2-5） | 超限转发；每口 16 包 IPv6 TCP ack，40G `eth_tx_clk[i]`/10G `eth_tx_clk[i+4]`；RSS cfg `'h8_60f4{addr,data}` | `tc_status[11:0]==~12'h0`；dev0/1 `'h8_5000..` 相等、`'h8_600c==48`；双卡收发相等 |
| 33 | 6 口 | RSS 散列检测；`'h8_60f4{16'h0,i[3:0],8'h0,i[3:0]}` | `tc_status[5:0]==~6'h0`；`'h8_6004/600c==48` |
| 34 | 6 口 | 超限转发 + RSS + `'h8_01b0 PORT_CFG` | `tc_status[11:0]==~12'h0`；同 tc32 |

## readme.txt 说明（tc0~tc4）

```
tc0 光口0~3上行发少量ipv4 tcp包，逻辑报文统计出口bypass
tc1 光口0 上行发少量ipv4 tcp包，会话表配置为虚拟线模式，所有包全部走转发流程
tc2 光口0 上行发少量ipv4 tcp包，会话表配置为虚拟线模式
tc3 光口0 上行发少量ipv4 tcp包，会话表配置为交换模式
tc4 光口0 上行发少量ipv4 tcp包，会话表配置为路由模式
```
（readme 仅覆盖 0~4，且 tc2 描述文案与头部 Description「交换转发」不一致——头部为准。）

## 现状与运行方式

- `tc_summary.log` 当前仅 tc1 pass；`msim_setup.tcl` 的 `set tc_list {tc1}` 决定跑哪些，可用 `cat ./tc_summary.log` 收尾。
- 运行：`nic_sim.sh` → 若无 `build/*.gen` 先 `make`+vivado 生成仿真产物，否则 `vsim -do msim_setup.tcl`；编译经 `com_ddr_0/com_dma/com_ip/com_vlog.tcl`。
- 判定机制：`tc_status` 逐位为子目标真值，`log2file(tc, 谓词, tc_status)` 写 `tc_summary.log`；谓词多为 `tc_status[X:0]==~0` 所有位为 1。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)
