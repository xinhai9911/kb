# 构建与仿真体系深度分析（build_lib / sim/nic_top 编译流程）

> 定点：`build_lib/*.tcl`、`sim/nic_top/Makefile + *.tcl + nic_sim.sh`、生成物 `run_synth.tcl`。综述 §5.3 已概览，本文补流程细节与版本串格式。

## 0. 目录事实修正（与综述差异）

顶层**不存在 `build/` 目录**（只有 `build_lib/`）；仓库实际 Makefile 为 **`sim/nic_top/Makefile`**。综述所述 `build/Makefile` 的 `BOARD=nsfocus_ku060_golden` 变体在仓库源码中不存在（待核实是否只在发布机）。golden 变体由 `set_version_golden.tcl + pin_golden.xdc` 手工切换。Makefile 仅支持 `BOARD=nsfocus_ku060_switch`（交换转卡）。

## 1. sim/nic_top/Makefile

```make
DEFS = NSFOCUS_KU060
BOARD ?=            GRAPH ?= on      PROJECT ?= ec_8x10_nf_v1
CURRENT_REV ?= 2023_0905             DEVICE = xcku060-ffva1156-2-e
ifeq ($(BOARD),nsfocus_ku060_switch)
    XDC_FILES_REL = ../../constraint/pin_nsfocus_ku060_switch.xdc
    DEFS += NSFOCUS_KU060_SWITCH      CURRENT_VER ?= 0D02_0301
else
    XDC_FILES_REL = ../../constraint/pin.xdc      CURRENT_VER ?= 0D02_0001
endif
```

- 目标链：`fpga`（默认）→ `sim`：写 `run_synth.tcl`（open_project ../../build/$(PROJECT).xpr、set part、`add_files` 对应 pin.xdc、`remove_files` system_management_wiz_0/xadc .xci）→ `vivado -mode batch -source run_synth.tcl`。`GRAPH=on` 不产生差异（两分支都调 sim）。
- 完整 build 走 `gui_off`：`reset_run synth_1 → launch_runs synth_1 -jobs 16`（run_synth.tcl）→ impl（run_impl.tcl）→ `run_gen_bit.tcl`：`set_property STEPS.WRITE_BITSTREAM.TCL.POST [pwd]/../../build_lib/bin_gen.tcl` 注入 **write_bitstream 后置 hook** 生成发布固件，`launch_runs impl_1 -to_step write_bitstream -jobs 16`。
- `copy_file`：`cp build_lib/set_version_switch.tcl → build_lib/set_version.tcl`（switch 变体换版本脚本）。
- `CURRENT_VER`/`CURRENT_REV` 为宏版本，与 set_version 版本串是两套。

## 2. build.tcl 与 run_synth.tcl

`build.tcl`（模拟 IP 环境初始化）：open_project → `add_files ip/axi_vip_s0/axi_vip_s0.xci` → 递归 `find_ip`（.xci/.bd，跳过 common 目录）：`reset_target + export_ip_user_files + generate_target`（覆盖 ddr4_0_dns、axi_vip_s0、tcam_64p、bd/design_1）→ `export_simulation -simulator questa` 到 `../../sim` → `launch_runs synth_1 -jobs 10`。

`run_synth.tcl` 为 Makefile `sim` 目标**逐行 echo 生成**的短脚本（4 行，见 §1），非手工维护文件。

## 3. 版本宏注入（build_lib/set_version.tcl / golden）

两脚本骨架相同，差异在 GOLDEN 宏与计数器。

| 项目 | set_version.tcl | set_version_golden.tcl |
|---|---|---|
| 写入 `rtl/def/ver_define.svh` | `define NSFOCUS_KU060 / PCIE_DUAL / DEF_NIC_{DATE,TIME,REV,VER}` | 同上 + **`define GOLDEN`** |
| cur_rev | `01_02_06_04`；rev0d=`03_0D_0014` | 同左；rev0d=`03_0D_0000` |
| manifest | 生成 0d + 0f（golden+app+timers）两条 bin_gen 行 | 仅生成 0d 单镜像行（无 0f/NIC__gld 多引导） |
| 副作用 | **原地改写 `ip/bd/design_1/design_1.bd`**：正则把 AXI VIP 属性 `OUTSTANDING "value":"2"` 替换为 `"1"`（突发深 2→1，仿真/生成收敛需要） | 同左 |

版本串格式（以 0d 为例）：`01_02_06_04_03_0D_260605_0011_0326_0014`
= `cur_rev(01_02_06_04)` + `cur_rev_0d_cut(03_0D)` + `date_cut(260605=YYMDD)` + `time(0011_0326 = 00HH_MMSS)` + `rev_cnt(0014)`。
字段编码（文件头注释）：vendor `01=xilinx/02=intel`；chip `02=ku060`（03=ku15p）；port `06`（本工程口数）；nic `04=40+10G(sw/rack/pcie)`；product `03`＝IDPS（01=NF/02=ADS/04=UTS）；sp flag `0D=普通/0F=` 带 golden+app+timers 的多引导、`1D/1F=secondary`。

## 4. bin_gen.tcl（由 set_version 生成，2026-06-05 快照）

```tcl
# 0D：单镜像（top.bit 在 0x0）
write_cfgmem -format bin -size 64 -interface SPIx8 \
  -loadbit {up 0x00000000 "../../../build/ec_8x10_nf_v1.runs/impl_1/top.bit"} \
  -checksum -force -file "../../../release/…_0D_….bin"
# 0F：多引导（golden 0x0 + app 0x01F00000 + timer1 0x01EFFC00 + timer2 0x03E00000）
write_cfgmem -format bin -size 64 -interface SPIx8 \
  -loadbit {up 0x00000000 "../../../build_lib/NIC__gld.bit" up 0x01F00000 "../../../build/…/top.bit"} \
  -loaddata {up 0x01EFFC00 "…/timer1.bin" up 0x03E00000 "…/timer2.bin"} \
  -checksum -force -file "../../../release/…_0F_….bin"
exec sh -c {cp …/top.bit …_0D….bit}
exec sh -c {mv …_0D…_primary.bin …_0D….bin}   ;# primary→0D/0F
exec sh -c {mv …_0D…_secondary.bin …_1D….bin} ;# secondary→1D/1F
exec sh -c {mv …_0F…_primary.bin …_0F….bin}
exec sh -c {mv …_0F…_secondary.bin …_1F….bin}
exec sh -c {rm -rf ../../../release/*.prm}
```

布局语义（64MB flash）：主镜像 0x0 = top.bit（Pro）；多引导 0x0 = `NIC__gld.bit`（golden，静态发布位流）、0x01F00000 = top.bit（app）、timer1.bin 0x01EFFC00（=app−1KB）、timer2.bin 0x03E00000。`_primary/_secondary` 文件后缀来自 write_cfgmem 的 CONFIGFALLBACK/多镜像输出，重命名归入 0D/0F 与 1D/1F 版本号。

## 5. multiboot_address_table.tcl（XAPP1246/1247 工具）

`tclsh` 即可跑（`#!/usr/bin/env tclsh`）。交互/批处理计算 golden、timer1、multiboot、timer2 的 flash 地址：

- 假设：256kB 扇区对齐；DCI_WAIT 4ms(UltraScale)/PLL lock 200µs；timer 图 1kB；位流尾留 `wait_cycles×width/8` 字节缓冲。
- 关键 proc：`NextBitstreamAddress`（+缓冲→扇区上取整）、`FirstTimerAddress=mb−1024`、`WbstarAddress=mb−512`。
- `CreateTimers`：timer1.bin = 242 字哑头 + `000000BB`(总线宽探测) + `11220044`(宽模式) + `AA995566`(同步) + `30022001`(timer 写) + `0x40000000|0x4000`；timer2.bin = 1 哑字头 + 计数 1。SPIx1/2/4/8 与 BPIx8/16（BPI 位/字节交换）。输出 write_cfgmem 与 WBSTAR。仓库 `build_lib/timer1.bin/timer2.bin` 即其产物。

## 6. sim/nic_top 的 Questa 编译体系

`msim_setup.tcl`：
- `dev_com`：映射 `/opt/xilinx/dev_lib` 预编译库（unisim、unisims_ver、simprims_ver、xpm、**xilinx_vip**、unimacro_ver、secureip）。
- `com = do com_ddr_0.tcl`（**com_ddr_1 已注释**）＋ com_dma ＋ com_ip ＋ com_vlog。
- `elab`：编译 `tb_top/top_for_sim.sv` → `vopt +acc=npr -o top_opt`；`elab_debug`：编译 `tb_nic_top.sv` → `vsim -voptargs=+acc -warning 7061`（glbl+.tc+.tb_nic_top）+ `log -r /*` + `do wave.do`。
- 主循环：检测 `build/*.gen` 存在→只 `do com_vlog.tcl`（增量），否则 `dev_com; com`。默认 `set tc_list {tc1}`；逐用例 `vlog tc → elab_debug → run 1ns → run 30us`（**当前文件硬编码 30us，无 tc_timeout**；CLAUDE.md 所述超时机制为更新版，以本快照为准），结果入 `tc_summary.log`。

`nic_sim.sh`：`rm -rf vivado* transcript` → 若无 `build/*.gen` 则 `make` + `vivado -mode tcl -source build.tcl -notrace` + `rm -rf ../questa` → `vsim -do msim_setup.tcl`。

| com_*.tcl | 内容 |
|---|---|
| com_ddr_0/1（两文件字节相同） | 建 xpm/microblaze_v11_0_9/lib_cdc/proc_sys_reset/lmb*/blk_mem_gen_v8_4_5/iomodule 库；编译 `ddr4_0_dns` 的 `bd_3686` MicroBlaze MCS 层次（VHD）+ DDR4 phy/control/cal 全 RTL + `tb_model/ddr` 行为模型 + glbl.v |
| com_dma（最大） | 38 个库；xilinx_vip 全集、`design_1_axi_vip_0_0`、xpm cdc/fifo/memory、fifo_generator、`design_1.v` bd 网表；`ipshared` 通用 hdl（排除 xdma/gtwizard/vip）、tcam_64p `cam_v2_3_0`；**末尾 `cp tb_model/dma/axi_master_new.v ../../rtl/dma/` 覆盖自研 RTL**；RAM_QPI_WR/RD netlist 注释 |
| com_ip | vmap xil_defaultlib；clk_100m clk_wiz、ip/i_e_gress；遍历 `.gen/sources_1/ip` 各模块的 sim/synth/hdl 目录；**VHDL 优先其 `_sim_netlist.v`**，无网表才 vcom |
| com_vlog | 按目录序 vlog 全部 RTL（def/common/eth/pkt_replay/blacklist/dma/bd/table/tlv/forward/i_e_gress/mtu/share_ram/pkt_tracing/**updata**/port_group/ddr_ctrl/payload_hash/top）+ tb_model；`rtl/dma/*.v` 加 `-define TIMR_DW=9 -mfcu`；table/顶 加 `-define SIM` |

`wave.do` 为调试波形（`virtual function` 合并总线 + add wave），`modelsim.ini` 为库映射。路径硬编码 `/home/xilinx/Vivado/2022.1`、`/opt/xilinx/dev_lib`（Linux，Windows checkout 需改）。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)