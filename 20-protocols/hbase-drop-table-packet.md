---
title: HBase Protobuf dropTable 报文解析
tags: [protocol, hbase, pcap, active]
created: 2026-06-10
updated: 2026-06-10
status: active
source: Q:\AI\hbase_step_01_table_drop_cleanup_report.md
---


# HBase Protobuf `dropTable` 报文解析

源抓包文件：
`Q:\AI\output\hbase-workflow\pcap\protobuf_v18_20260518_152833\steps\step_01_table_drop_cleanup\step.pcapng`

辅助结果文件：
- `Q:\AI\output\hbase-workflow\pcap\protobuf_v18_20260518_152833\steps\step_01_table_drop_cleanup\step_report.txt`
- `Q:\AI\output\hbase-workflow\pcap\protobuf_v18_20260518_152833\steps\step_01_table_drop_cleanup\output.txt`
- `Q:\AI\output\hbase-workflow\pcap\protobuf_v18_20260518_152833\steps\step_01_table_drop_cleanup\tpr_fields.json`

## 1. 概览

该抓包对应一次 Phoenix/HBase 的表删除清理动作，业务方法为 `dropTable`。

从结果文件可确认：

```json
{
  "success": true,
  "method": "dropTable",
  "table": "test_flush_v18"
}
```

本次抓包文件总大小仅 `1036` 字节，包含 `3` 个数据帧，完整流程为：

1. 客户端向 HBase RegionServer 发起 `dropTable` 请求
2. 服务端返回成功响应
3. 客户端发送 ACK 确认

## 2. 抓包环境与目标

根据 `pcapng` 文件头中的抓包信息，可以提取出以下环境信息：

- 抓包工具：`Dumpcap (Wireshark) 4.6.5`
- 操作系统：`64-bit Windows 11 (24H2), build 26100`
- 网卡：`Intel(R) Ethernet Connection (17) I219-LM`
- 抓包过滤条件：`host 10.245.25.63 and tcp port 16020`

需要特别说明：

- `step_report.txt` 中标记的目标是 `10.245.25.63:2181`
- 但该抓包实际捕获的是 `10.245.25.63:16020`

因此，这份包反映的是 HBase RegionServer 的 protobuf/RPC 交互，而不是 ZooKeeper `2181` 端口流量。

## 3. 三次报文交互

### 3.1 请求报文

五元组：

- 源地址：`10.66.30.52:51793`
- 目的地址：`10.245.25.63:16020`
- 传输层：`TCP`
- TCP 标志位：`PSH, ACK`

从 IP 头可见：

- `Total Length = 0x00E9 = 233`
- `TTL = 128`

TCP 负载起始可见：

```text
00 00 00 BD
18 08 1B 1A 0B 45 78 65 63 53 65 72 76 69 63 65
20 01 30 D0 0F 38 E0 D4 03 A2 01 0A 43 ...
```

其中：

- 前 4 字节 `00 00 00 BD` 表示后续应用层消息长度为 `0xBD = 189` 字节
- 后续 protobuf/RPC 明文可识别出服务名和业务字段

请求报文中可直接识别出的关键字符串包括：

- `ExecService`
- `SYSTEM.CATALOG,,1778846578384.65f9f985b78e989d777875a675a13bed.`
- `test_flush_v18`
- `MetaDataService`
- `dropTable`

对应的关键片段如下：

```text
... ExecService ...
... SYSTEM.CATALOG,,1778846578384.65f9f985b78e989d777875a675a13bed. ...
... test_flush_v18 ...
... MetaDataService ...
... dropTable ...
```

这说明客户端并不是直接发送“SQL 文本”，而是在 Phoenix 侧通过 HBase 的 `ExecService` 调用协处理器服务：

- 协处理器服务：`MetaDataService`
- 调用方法：`dropTable`

同时，请求实际命中的元数据对象位于：

- 系统表：`SYSTEM.CATALOG`

并且结合 `tpr_fields.json` 可知其关键行键为：

- `rowKey = "\u0000\u0000test_flush_v18"`

这意味着本次删除动作在线上协议层体现为：

`Mutate(SYSTEM.CATALOG, \x00\x00test_flush_v18)`

也就是对 Phoenix 元数据表 `SYSTEM.CATALOG` 中与 `test_flush_v18` 对应的元数据记录进行删除/清理。

### 3.2 响应报文

五元组反向：

- 源地址：`10.245.25.63:16020`
- 目的地址：`10.66.30.52:51793`
- 传输层：`TCP`
- TCP 标志位：`PSH, ACK`

从 IP 头可见：

- `Total Length = 0x00CD = 205`
- `TTL = 62`

TCP 负载前部：

```text
00 00 00 A1
02 08 1B 9C 01 0A 43 08 01 12 3F 53 59 53 54 45 ...
```

其中：

- 前 4 字节 `00 00 00 A1` 表示响应体长度为 `0xA1 = 161` 字节

响应中可直接识别出的关键字符串包括：

- `SYSTEM.CATALOG,,1778846578384.65f9f985b78e989d777875a675a13bed.`
- `org.apache.phoenix.coprocessor.generated.MetaDataProtos$MetaDataResponse`

这说明服务端返回的是 Phoenix 协处理器的 `MetaDataResponse`。

从抓包可见响应中没有明显错误字符串，结合目录中的自动提取结果：

- `success = true`
- `method = dropTable`
- `table = test_flush_v18`

可判断本次 `dropTable` 已执行成功。

### 3.3 ACK 报文

第三帧为客户端确认报文：

- 源地址：`10.66.30.52:51793`
- 目的地址：`10.245.25.63:16020`
- TCP 标志位：`ACK`
- IP `Total Length = 0x0028 = 40`
- 无应用层负载

该帧仅用于确认服务端响应已被客户端接收。

## 4. 关键字段提取

结合原始报文和自动提取结果，可整理出以下业务字段：

- 客户端 IP：`10.66.30.52`
- 服务端 IP：`10.245.25.63`
- 服务端端口：`16020`
- 协议类型：`HBase Protobuf RPC`
- 工具标识：`HBase-Protobuf`
- 业务动作：`dropTable`
- 元数据表：`SYSTEM.CATALOG`
- 目标表名：`test_flush_v18`
- 行键：`\x00\x00test_flush_v18`
- 协议表现形式：`Mutate(SYSTEM.CATALOG, \x00\x00test_flush_v18)`
- 执行结果：成功

## 5. 结论

这份 `step.pcapng` 记录的是一次 Phoenix 删除表时的元数据清理请求，协议层并非表现为 SQL 文本，而是：

1. 客户端通过 HBase `ExecService` 发起 RPC
2. 调用 Phoenix 协处理器 `MetaDataService.dropTable`
3. 对 `SYSTEM.CATALOG` 中与 `test_flush_v18` 相关的元数据行执行删除/变更
4. 服务端返回 `MetaDataResponse`
5. 结果成功

因此，从协议识别角度看，这一步的核心特征不是 `DROP TABLE xxx` 字符串，而是以下组合特征：

- `ExecService`
- `MetaDataService`
- `dropTable`
- `SYSTEM.CATALOG`
- `\x00\x00test_flush_v18`

## 6. 补充说明

本次分析主要依据：

- `pcapng` 原始十六进制内容
- step 目录下已有的自动提取结果

当前环境中未找到可直接执行的 `tshark`，因此没有使用 Wireshark/tshark 的协议树自动解码，而是基于包内可见明文字段和块结构完成解析。
