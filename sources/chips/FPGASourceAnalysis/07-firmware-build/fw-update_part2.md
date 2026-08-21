# 固件升级链路深度分析 · Part2：ICAP 重加载与 AXI-Lite→LBS 桥（updata/）

> 续 Part1（SPI 通道 + QSPI 栈）。本文覆盖 `reload.sv` / `Reload_program.sv` 的 IPROG 序列与 `SAXI_LITE2LBS.sv` 桥的全部 CDC/握手细节。

## 1. reload.sv / Reload_program.sv（ICAP→CSIB IPROG，多引导）

两个模块**逻辑完全相同**，仅复位风格不同：
`reload`：posedge clk / posedge rst（由 update.sv 用）；`Reload_program`：posedge sys_clk / negedge rst_n 异步复位（由 Qspi_top.sv 用）。

**触发与波形**：`reload_set` 上升沿（`reload_set & ~reload_set_1dly`）→ `Reloading=1`，`cnt` 0..0xF。`CSIB`：cnt0 拉低（使能 ICAPE3 写端口）、**cnt9 拉高**（关断）。

I 总线逐拍（每拍 32-bit，先经 `BIT_SWP()` 按**字节内 7..0 位反转**，符合 ICAP I 总线的位序要求）：

| cnt | I 内容 | 作用（UG470 IPROG 序列） |
|---|---|---|
| 1 | `FFFF_FFFF` DUMMY_WORD | 哑字 |
| 2 | `AA99_5566` SYNC_WORD | 同步字 |
| 3 | `2000_0000` T1_NOOP1 | NOP |
| 4 | `3002_0001` T1W1_WORD2WBSTAR | Type-1 写 WBSTAR 寄存器 |
| 5 | `0000_0000` WBSTAR | **起点写 0**（回 flash 首地址） |
| 6 | `3000_8001` T1W1_WORD2CMD | Type-1 写 CMD 寄存器 |
| 7 | `0000_000F` IPROG_CMD | 内部重新 PROGRAM（重启配置） |
| 8 | `2000_0000` T1_NOOP2 | NOP |

cnt0/cnt9 时 I=0。`ICAPE3` 参数：`DEVICE_ID=32'h0362_8093`、`ICAP_AUTO_SWITCH="DISABLE"`、`RDWRB=0`（仅写、不读回），AVAIL/PRDONE/PRERROR 悬空不采。

> 注释：WBSTAR 固定 0 → IPROG 后从 flash 0x0 重启（回到首镜像）。golden→app 的跳转依赖 golden 位流通属性 `NEXT_CONFIG_ADDR`（见 08-constraint 文档）先经 **timer 链**（WBSTAR→timer1.bin→app）迁移；本模块不写 WBSTAR 值，故不会覆盖属性初始化。

## 2. SAXI_LITE2LBS.sv（AXI-Lite → LBS 桥，跨时钟）

参数 `S_AXI_AW=32 / S_AXI_DW=32`。职责：把 PCIe/AXI-Lite 域单拍读写搬到 LBS 时钟域。

**写通道**

| 步骤 | 机制 |
|---|---|
| 握手 | `awready`/`wready` 于 `awvalid&wvalid& ^busy`（`wrcyc` 空闲）**同拍拉高**，同拍捕获 `awaddr/wdata/wstrb` 至 `Lbs_*_axi_clk` 寄存器 |
| 跨域 | `xpm_cdc_handshake#(WIDTH=68=32+32+4)`：src=s_axi_aclk，dest=Lbs_clk；`dest_req=Lbs_wren`，`dest_out={Lbs_waddr,Lbs_wd,Lbs_wstrb}` |
| 完成 | `src_rcv`（dest 已收）回程清 `Lbs_wren_axi_clk` 并断言 `s_axi_bvalid`（`bresp=00`），`wrcyc` 复位 |

**读通道**

| 步骤 | 机制 |
|---|---|
| 请求 | `arready` 拉高捕获 `araddr`，`rdcyc` 锁定 |
| 跨域 | `xpm_cdc_handshake#(WIDTH=32)`：src=axi→dest=lbs，`dest_req=Lbs_rden`，`dest_out=Lbs_raddr` |
| 读返回 | Lbs_clk 侧收到 `Lbs_rdv` 置 `bcyc`，`Lbs_rsend` 发起反向 handshake（WIDTH=32，src=lbs→dest=axi）；`dest_req=Lbs_rdv_axi_clk` → `s_axi_rvalid/s_axi_rdata`（`rresp=00`） |

三只 CDC 全为 `xpm_cdc_handshake` **内部握手**（`DEST_EXT_HSK=0`，`dest_ack` 接 0 示意由本宏管理），`SRC_SYNC_FF=4`、`DEST_SYNC_FF=4`、`INIT_SYNC_FF=1`、`SIM_ASSERT_CHK=1`（模拟断言开）。

**已知局限（源码事实）**
- **不支持突发**：单笔单拍、逐笔握手，无 outstanding 流水；
- AW/W 必须同拍到达（无独立等待/重试）；
- `Lbs_wstrb` 原样透传，但下游 LBS 寄存器（Qspi_lbs / update 等）均按**整 32-bit 写**，字节使能不参与地址译码，跨到对应低位外无多字节合并处理。

## 3. 与多引导地址表的衔接（见 build-system / 08-constraint 文档）

- 固件烧写布局：`bin_gen.tcl` 主镜像 0x0（golden/app），app 0x01F00000，timer1.bin 0x01EFFC00，timer2.bin 0x03E00000；
- `pin.xdc`：Pro 版 `NEXT_CONFIG_ADDR=0x0` + `CONFIGFALLBACK ENABLE` + `TIMER_CFG=0x1DCD650`（看门狗）；
- `pin_golden.xdc`：golden 版 `NEXT_CONFIG_ADDR=0x00F7FE00`（=timer1.bin 地址>>1，SPIx8）+ `NEXT_CONFIG_REBOOT ENABLE`。

重加载的完整闭环＝「UART/PCIe 写入固件 → QSPI ping-pong 页擦编程 → host 写 reload 魔数 → ICAP IPROG → WBSTAR(属性) → 失败 salvaged 由对端 timer 看门狗回退」，两条 H2F 路径（SPI 从卡级联、本卡 QSPI）互备。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)