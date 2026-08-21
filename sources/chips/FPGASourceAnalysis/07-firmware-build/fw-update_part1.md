# 固件升级链路深度分析 · Part1：SPI 通道与 QSPI 栈（updata/）

> 定点：`rtl/updata/*.sv`。综述 §4.9/5.3 已给一句概览，本文补寄存器偏移、命令码、状态机、双 RAM ping-pong 细节。Part2 讲 ICAP 重加载与 SAXI 桥。

## 0. 模块层级与通道

| 通道 | 链路 | LBS 窗 |
|---|---|---|
| SPI 主/从级联 | `update(mst/slv)` → `spi_ctrl`（STARTUPE3 / 外接 pin） | **0x08_3000**（mst）、0x08_3800（slv），`MASTER` 参数 |
| QSPI 固件升级 | `Qspi_top` → `Qspi_lbs`（寄存器）＋`Qspi_upgrade`（数据流）→`Qspi_cmd`（命令）→`Qspi_dri`（位时序，STARTUPE3） | **0x001_000**（`QSPI_BADDR=12'h1`） |
| 重加载 | `reload` / `Reload_program`（ICAPE3 IPROG，Part2） | 失效保护 |

`MASTER="true"`：出 STARTUPE3 引脚 + 挂 reload；`"false"`：透出 `spi_ext_csn/o`、读 `spi_ext_i`，时序参数取自同级输入（主从级联）。

## 1. update.sv 寄存器窗（BASE_ADDR=24'h08_3000）

地址译码 `host_addr = address & 24'hff_f800 == BASE_ADDR`（0x08_0000 起 8KB 窗）；读延迟 2 拍（`tmp_rdv`）。

| 偏移 | 读写 | 字段 | 说明 |
|---|---|---|---|
| 0x00 | RW | spi_dnum[7:0] | SPI 每 bit 分频计数（默认 **4**），写同拍发 `spi_drst`；仅 MASTER |
| 0x10 | RW | cmd_en[3:0] | 4 相命令使能 |
| 0x14 | RW | cmd_io[3:0] | 每相方向：0=输出/写，1=输入/读 |
| 0x18 | RW | cmd_size[1:0] | phase0/1 字节数（各 16b） |
| 0x1c | RW | cmd_size[3:2] | phase2/3；**写此寄存器即拉 cmd_req 并清 mem_spi_rdy** |
| 0x20 | RO | cmd_done | 完成标志 |
| 0x30/0x34 | RW/RO | i_raddr / i_rd | 聚焦读（SPI 读回 RAM 的 32-bit 口） |
| 0x40/0x44/0x48 | RW | reload_reg0/1/2 | 魔数齐 → `reload_set` |
| 0x100…窗内 | WO | o_waddr/o_wd/o_wren | 固件写窗；`o_waddr = addr[9:2] - 0x40`（0x100→字 0），8-bit 掩 256 字 |

`mem_spi_rdy` = SPI 引擎空闲可接新命令。

## 2. spi_ctrl.sv：位级 SPI 引擎

- 时钟：`num = spi_dnum==0?2:dnum`；计数 0..num-1 翻转 `spi_clk` → SCK 周期 = 2×num×clk（默认 clk/8）。
- FSM：`IDLE → RDV(等 wr_ram o_rdv) → WAIT(首个 dn_edge 拉低 csn) → CMD → DONE`。最多 **4 相**，`cmd_num=Σcmd_en`；`cmdt_size_cnt` 累计到 cmd1/2/3/4_size 边界切相并换 `current_io`（输入/输出方向切换点）。
- 写路径：host 灌 `wr_ram`（256×32→1024×8，block RAM）→ 引擎在 `~current_io` 下 `o_rden` 取 `tmp_rd`，`spi_o[0]` **MSB 先**于 `cnt==0 & ~spi_clk` 逐位送出。
- 读路径：`current_io=1` 时 `i_wd={i_wd[6:0],spi_i[1]}` 每 up_edge 收 1 bit，字节边界 `i_wren` 写入 `rd_ram`（1024×8→256×32）；host 置 i_raddr 后 i_rden → i_rdv/i_rd。
- MASTER=true → `STARTUPE3`（USRCCLKO=spi_clk，FCSBO=spi_csn，DO=spi_o，DTS=`4'b1110` 仅驱动 D0，DI=spi_i，FCSBTS=0，KEYCLEARB/PACK/USRDONE=1）；false → 外部三线。

## 3. QSPI 四层栈

### 3.1 Qspi_lbs：寄存器地图（读 2 拍回）

| 偏移 | 名 | 说明 |
|---|---|---|
| 0x000 | TEST_REG | 回读为 `~test_reg` |
| 0x004/0x008 | Manufacturer_id / Device_id | rdid 结果（8b/16b） |
| 0x00C/0x010/0x014 | cmd_state / dri_state / upg_state | 三级 FSM 状态 |
| 0x018 | FORCE_EXIT | 写1强退；`force_exit_done` 自清零 |
| 0x01C | VERSION=0x1 | 0x020/0x024=CGE_TIMEH/L=`2022_0607/0016_0730` |
| 0x028/0x02C/0x030 | RELOAD_REG0/1/2 | 魔数→`Reload_set` |
| 0x100… | FILE_RD rdy/req/size/saddr | 读固件命令 |
| 0x200… | RAM1/2：wrok/raddr/rden/rd；num/cnt/cyc_ram | 读回通道（0x210/0x21C 32-bit 数据口） |
| 0x300… | FILE_WR rdy/req/size/saddr | 写固件命令 |
| 0x400… | RAM1/2：wrok/waddr/wren/wd；num/cnt/cyc_ram | 写入通道（0x410/0x41C 数据口） |

`local_addr[23:12]==QSPI_BADDR` 才响应；`err_flg` 记录“ram_wrok 写 0”异常；读应答再打拍。

### 3.2 双 RAM ping-pong（CHEL=2）

两对 TDP RAM（Vivado `RAM_QPI_WR`/`RAM_QPI_RD` IP；com_dma.tcl 中其 `_sim_netlist` 编译被注释）：

| RAM | Port A | Port B | 能力 |
|---|---|---|---|
| RAM_QPI_WR | host 写 9-bit×32（512字） | QSPI 读 11-bit×8（2048B） | 2KB 写缓冲 |
| RAM_QPI_RD | QSPI 写 11-bit×8（2048B） | host 读 9-bit×32（512字） | 2KB 读缓冲 |

host 逐字访问；QSPI 按字节。`File_*_cyc_ram`（=cnt[0]）选 0/1 通道乒乓。

### 3.3 Qspi_upgrade：数据流 FSM

状态：`IDLE → QSPI_ES_BEGIN(start) → QSPI_ES_RDY → QSPI_ES(扇区擦除) → FILE_WR_WAIT/FILE_WR/FILE_WR_DONE → QSPI_WR_END`；读路 `QSPI_RD_BEGIN → FILE_RD_WAIT/FILE_RD/FILE_RD_DONE → QSPI_RD_END`。收尾都经 `Qspi_end_req`（Qspi_cmd DEVICE_RESET 回 1x）。

- 写：先擦 `es_len=(size[11:0]==0)?size:(size[25:12]+1,12'b0)`（4KB 取整）；`File_wr_num=ceil(size/256)`；每块等 `ram1/2_wrok & Qspi_wr_rdy` 发 `Qspi_wr_req`（len 固定 256，saddr+=256），`Qspi_wr_rden` 逐字节喂 page program；完成后回 ram_rddone 释放。
- 读：`File_rd_num=ceil(size/256)`；等 `ram1/2_wrok==0` 空闲读入 RAM，置各级 `wrok=1` 通知 host，host 回 rddone。
- `Qspi_force_exit` 可在各 WAIT 态强退。

### 3.4 Qspi_cmd：命令 FSM

状态：`INITIAL → CFG_AD4(区分改 4B 地址) → CFG_4X(切 QPI) → IDRD(rdid) → IDLE → DAT_RD / DAT_WR_COP→DAT_WR_ENABLE→DAT_WR_CKE_ENABLE→DAT_WR(→DAT_WR_STU) / DAT_ES_COP→…→DAT_ES(→DAT_ES_STU) → RESET → INITIAL`。`Qspi_cmd_state=c_state`。

| 操作 | 命令码 | 说明 |
|---|---|---|
| RDID 1x / 4x | 0x9F / 0xAF | start 流程 |
| EN4B（1x）| 0xB7 | 4 字节地址模式 |
| 1x→4x 切 QPI | 0x35 | |
| 读状态 | 0x05 | bit1=WEL，bit0=WIP |
| 读数据 | 0xEB | DAT_RD，len 按 256B 对齐/最小 256 |
| 写使能 | 0x06 | 每 wr/es 前 |
| 扇区擦除 | 0x20 | 地址 saddr[24:12]（4KB 对齐） |
| 页编程 | 0x02 | 地址 saddr[24:8]，固定 256B |
| 复位 | 0x66/0x99 | end 流程 |

`wr_num=ceil(wr_len/256)`；`es_num` 按 `es_len[25:12]` 计扇区。每轮写：WREN→验 WEL→PP→验 WIP。

### 3.5 Qspi_dri：位级时序（目标 MX25U256 256Mb=32MB）

时钟 `dev_cnt 0..1` 翻转 → SCK=lbs_clk/2；`Dout` 装载发送字节：1x `{Dout[6:0],1'b0}`（MSB 先 D0），4x `{Dout[3:0],4'b0}`（高 nibble 先）。`Qsio_t` 1x 单线、4x 发/收切换；各态 cnt0 拉低 csn、末值拉高。

| 状态 | 命令 | 总 cnt（半周期） | 说明 |
|---|---|---|---|
| ID_RD_1X | 0x9F | 32 | 1x 逐位读 ID（mfr 9..16、dev 17..32） |
| REG_RD/WR_1X | — / 写 | 8 | 1x 单字节 |
| CFG_AD4 / CFG_4X | 0xB7 / 0x35 | 8 | 前回 1x、后进 4x |
| REG_STU_CFG_1X | 0x01 | 24 | 0x01+状态+配置 两字节（cnt7/15 装载） |
| ID_RD | 0xAF | 8 | 4x 拼 8+16bit ID（cnt3..8） |
| STU_RD | 0x05 | 4 | 状态字节 |
| DAT_RD | 0xEB | rdlen×2+16 | 16=cmd2+addr6+mode2+哑元6 |
| WR_ENABLE | 0x06 | 2 | |
| SECTOR_EASER | 0x20 | 10 | cmd+4B 地址（cnt1/3/5/7 nibble 装载） |
| PAGE_PROGRAM | 0x02 | 512+10 | 数据 256B；`Qspi_program_rden` 奇数 cnt 7..517 |
| DEVICE_RESET | 0x66→0x99 | 6（csn 两脉冲） | →RESET_WAIT |
| RESET_WAIT | — | 24'b 计数 0xFFFFFF | 回 IDLE_1X |

读回：`Qspi_rdwd` 在 cnt>16、clk 低沿按奇偶拼字节，`Qspi_rdwren` 整字节写 RAM。SCK 走 STARTUPE3 USRCCLKO；`Qspi_dri_state=c_state`。

> 继续：[fw-update_part2.md](fw-update_part2.md) | [`skill.md`](../skill.md) | [`faq.md`](../faq.md)
> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)