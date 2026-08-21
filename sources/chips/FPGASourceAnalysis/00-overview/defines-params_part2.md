# def/ 总线族与宏定义深度解析（part 2：pci_bus_def）

> 源码位置：`Q:\AI\fpga_work\ips_test_2025_add_mpls_6que\rtl\def\pci_bus_def.sv`（8 千字节级包，含 TLP/事务类型常量、`tlp#` 与 `bus_pci#` 两套虚拟类、tag 结构）。`ver_define`/`user_bus_def` 见 part 1。

## 4. pci_bus_def 包

### 4.1 TLP 格式化与类型常量

| 常量 | 值 | 说明 |
|---|---|---|
| `DATA_CHL` | `2'b01` | DMA 数据通道标识 |
| `DW3_NO_DATA`/`DW4_NO_DATA` | `3'b000/001` | fmt：3/4 DW 无数据 TLP |
| `DW3_DATA`/`DW4_DATA` | `3'b010/011` | fmt：3/4 DW 带数据 |
| `TLP_PREFIX` | `3'b100` | fmt：TLP 前缀 |
| `MRD`/`MRDLK` | `5'b0_0000/0_0001` | 内存读 / 锁存读 |
| `MWR` | `5'b0_0000` | 内存写（type 编码与 MRD 同低 4 位，靠 fmt 区分） |
| `IORD`/`IOWR` | `5'b0_0010` | IO 读 / IO 写 |
| `CFGRD0`/`CFGWR0` | `5'b0_0100` | Type0 配置读 / 写 |
| `CFGRD1`/`CFGWR1` | `5'b0_0101` | Type1 配置读 / 写 |
| `TCFGRD`/`TCFGWR` | `5'b1_1011` | 带前缀配置读 / 写 |
| `MSG`/`MSGD` | `5'b1_0xxx` | 消息（前缀带 dont-care 位） |
| `CPL`/`CPLD` | `5'b0_1010` | 完成 / 完成带数据 |
| `CPLLK` | `5'b0_1011` | 锁存完成 |
| `FETCHADD`/`SWAP`/`CAS` | `0_1100/0_1101/0_1110` | 原子加 / 交换 / 比较交换 |
| `LPRFX`/`EPRFX` | `0_xxxx/1_xxxx` | 本地 / 端到端 TLP 前缀 |

Xilinx 事务类型（4-bit，`MEM_READ_REQ=0`…… `VENDOR_DEF_MSG=13`/`ATS_MSG=14`/`RES=15`）提供 AXI→PCIe 的 RQ/CQ 侧枚举（详见 pci/ 内 axi2pci、mreq）。

### 4.2 `tlp#(DW,CH)` 与 `bus_pci#(DW,CH)` 的 `avl_ch`

| typedef | 字段 | 说明 |
|---|---|---|
| `tlp#(DW,CH)::avl` | `vld,sop,eop,left[$clog2(DW/8)-1:0],data[DW-1:0]` | 无 ch 的 TLP 流 |
| `tlp#(DW,CH)::avl_ch` | avl 之上加 `ch[CH-1:0]` | 带通道号的 TLP 流（默认 DW=256, CH=8） |
| `tlp#(DW,CH)::tlp_mm` | `f_p, length[10:0], ttype[4:0], fmt[2:0], fbe[3:0], lbe[3:0], tag[7:0], address[CH-1:0]` | MM 事务描述（首包标志、长度、类型/格式、首尾字节使能、tag、地址） |
| `bus_pci#(DW,CH)::avl` / `avl_ch` | 同上 | 默认 DW=256, CH=32（32 路队列通道） |
| `bus_pci::avl_ptr` | `sop,eop,vld,left[0:0],data` | 指针流（left 仅 1bit） |
| `bus_pci::tlp_comp` | `fir_frag, sop_gap[4:0], req_cpld, length[10:0], compl_status[2:0], byte_count[11:0], requester_id[15:0], tag[7:0], lower_addr[11:0]` | Completion 描述：首分片/首包间隙/是否请求完成、完成状态、剩余字节数、请求者 ID、tag、低地址 |
| `avl_tlp_mm`/`avl_tlp_comp`/`avl_tlp_comp_ptr` | 流 + 描述复合 | AXIS 包络与 TLP 元数据捆绑 |
| `avl_tlp_mmi` | `tlp#(DW,CH)::avl` + `tlp_mm` | 复用 tlp 类的内部复合 |

### 4.3 `ST_TAG_INFO` 与 arid 编码

- `ST_TAG_INFO`（tag 管理状态，每 DMA 通道一组）：`vld, cur_id[5:0]（当前 tag）, rd_done, f_id[5:0]（首 tag）, p_num[5:0]（包序号）, f_p/l_p（首/尾包）, p_len[13:0]（MRD 包字节长）, user[9:0], sop_latch/eop_latch, rd_addr[9:0]（读指针，单位 32B）, cur_addr[9:0]`——MRD 拆包与 completion 对齐用。
- **s_axib_arid[8:0] 编码**（文件头注释原文，PCIe AXI 读数/写数识别用）：

```systemverilog
// s_axib_arid[8:0]:
// -- 9'hxx0: dl descriptor request       // 下行（主机→卡）描述符读
// -- 9'hxx1: dl data read request        // 下行数据读
// -- 9'hxx2: ul descriptor request       // 上行（卡→主机）描述符读
// -- 9'hxx3: dl configuration request    // 下行配置读
```

低 2 位区分请求类别；高 7 位（`xx`）编码队列/通道归属（具体分配见 pci/tag_manger）/DMA 通道，用于把不同类别请求分发到不同 tag 空间。

> 返回：[`skill.md`](../skill.md) | [`faq.md`](../faq.md)。