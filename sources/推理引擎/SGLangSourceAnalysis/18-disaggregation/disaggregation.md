## PD 分离（srt/disaggregation）· 架构、抽象与传输后端

本文覆盖 `srt/disaggregation/`（29 文件）及触达的 `srt/managers/disagg_service.py`、`srt/arg_groups/pd_disaggregation_hook.py`、`srt/server_args.py`。KV 传输细节与 scheduler 衔接见 [disaggregation_part2.md](disaggregation_part2.md)。

### 模块职责

| 文件/目录 | 职责 |
|---|---|
| `base/conn.py` | 传输抽象基类：`BaseKVManager`/`BaseKVSender`/`BaseKVReceiver`/`BaseKVBootstrapServer`、`KVArgs`、`KVPoll` 状态机、`StateType` |
| `common/` | 跨后端共享实现（`CommonKV*`）；staging 缓冲与散射 |
| `mooncake/` | 默认后端：Mooncake RDMA/TCP 传输、零拷贝自定义内存池 |
| `nixl/` | NVIDIA NIXL 后端（支持 DCP relayout、mem kind 显式建模） |
| `mori/` | 腾讯 Mori 后端（自有元数据线格式） |
| `ascend/` | 昇腾后端：继承 Mooncake 类 + `memfabric_hybrid` config store、NPU D2D |
| `fake/` | 假后端：不做真实传输，仅合成 decode 基准测试 |
| `prefill.py` | prefill 侧调度衔接：`PrefillBootstrapQueue` + `SchedulerDisaggregationPrefillMixin`（chunk 发送） |
| `decode.py` | decode 侧调度衔接：`DecodePreallocQueue`（预分配）+ `DecodeTransferQueue`（传输收敛） |
| `kv_events.py` | KV 缓存事件发布（ZMQ PUB/ROUTER + replay），供 HiCache 等消费 |
| `decode_hicache_mixin.py` / `decode_kvcache_offload_manager.py` | decode 侧 HiCache 前缀恢复与 KV 异步 offload |
| `encode_*.py`（3 文件） | **编码器分离**（VLM encoder-only 服务，独立于 PD 分离） |
| `srt/managers/disagg_service.py` | prefill 端启动 bootstrap 服务（`start_disagg_service`） |
| `srt/arg_groups/pd_disaggregation_hook.py` | `handle_pd_disaggregation`：PD 参数校验/归一化 |

### PD 分离架构

prefill 与 decode 是**两组独立进程/节点**，各自 `--disaggregation-mode prefill|decode`。同一请求的 prefill 计算（含整段 prefix 的 KV 生成）发生在 prefill 端，随后 KV 页**直接从 prefill 的 GPU KV 池 RDMA 写入 decode 端的 GPU KV 池**，decode 端拿到已就位的 KV 后只做增量 decode。

```
客户端 ──> Router/TokenizeManager（decode 侧或独立 router）
            │  (1) /generate（含 bootstrap_host/bootstrap_room 路由信息）
            ▼
 decode server（--disaggregation-mode decode）
   ├─ DecodePreallocQueue：先为请求预分配 KV 槽位
   ├─ 控制面：HTTP 查 prefill bootstrap /route → 得到 prefill 目标 rank
   └─ DecodeTransferQueue：轮询接收状态，Success 后提交 decode
            ▲ KV 数据面（RDMA/TCP，零拷贝直写 decode KV 池）
            │ 控制面（HTTP /route + zmq/TCP 元数据）
 prefill server（--disaggregation-mode prefill）
   ├─ 每个 TP rank 启动 KV bootstrap server（aiohttp，默认端口 8998）
   ├─ PrefillBootstrapQueue：prefill 完成 → 创建 sender → chunk 发送 KV
   └─ 末 chunk 附带首 token 元数据（MetadataBuffers）
```

**数据面**：KV 页与首 token 元数据经后端 RDMA 直传（mooncake/nixl/ascend），`mooncake_tcp` 退化为 TCP。**不使用 torch.distributed allreduce 传数据**；allreduce 只用于把各 TP/CP rank 的**轮询状态收敛**（见 part2 的 `poll_and_all_reduce`）。

### 核心抽象（base/conn.py）

`KVPoll`（base/conn.py:89）是贯穿全链路的请求级传输状态机：

| 值 | 状态 | 含义 |
|---|---|---|
| 0 | `Failed` | 传输失败（不可恢复） |
| 1 | `Bootstrapping` | decode 侧注册/握手中 |
| 2 | `WaitingForInput` | 已就绪，等 prefill 发起传输 |
| 3 | `Transferring` | KV 传输进行中 |
| 4 | `Success` | 传输完成，可提交解码 |

`StateType`（base/conn.py:17）枚举状态负载：`MAMBA`/`SWA`/`DSA`/`MINIMAX_INDEX_K`/`SWA_RING`/`C128_STATE`（MLA 压缩状态，如 DeepSeek-V4 unified_kv）。

`KVArgs`（base/conn.py:38）描述一次传输的全部内存几何：`kv_data_ptrs/lens`（分层 KV 指针）、`aux_*`、`state_*`（MLA/Mamba 状态）、`kv_head_num`/`page_size`、PP 相关 `prefill_start/end_layer`、`mla_compression_ratios` 等。

四个基类抽象（`BaseKVSender` 有 `init/send/poll/failure_exception/clear/abort`，`BaseKVReceiver` 增 `send_metadata`）：

| 基类 | 角色 |
|---|---|
| `BaseKVManager`（:97） | 传输状态登记、rank 表、kv 区域注册（`register_to_bootstrap`） |
| `BaseKVSender`（:115） | prefill 侧发起者 |
| `BaseKVReceiver`（:184） | decode 侧接收者 |
| `BaseKVBootstrapServer`（:243） | prefill 侧控制面注册表 |

### 传输后端矩阵

`utils.py:592 TransferBackend` 与 `utils.py:600 KVClassType`；工厂 `get_kv_class(backend, class_type)`（utils.py:630）按需 import 后端类。CLI choices（server_args.py:236）：`mooncake`、`nixl`、`ascend`、`fake`、`mori`、`mooncake_tcp`。

| 后端 | Manager/Sender/Receiver/Bootstrap | 传输介质 |
|---|---|---|
| mooncake（默认） | `MooncakeKVManager`（mooncake/conn.py:195）等 | RDMA（`MC_FORCE_TCP=1` 时 TCP）；`SGLANG_MOONCAKE_CUSTOM_MEM_POOL=INTRA_NODE_NVLINK` 零拷贝 |
| mooncake_tcp | 同 mooncake，hook:21 改写为 mooncake + 强制 TCP | TCP，免 RDMA HCA |
| nixl | `NixlKVManager`（nixl/conn.py:393） | NVIDIA NIXL；支持 DCP relayout、mem kind 序列化 |
| mori | `MoriKVManager`（mori/conn.py:302） | Tencent Mori；自有 `TransferInfo` 线格式 |
| ascend | `AscendKVManager(MooncakeKVManager)`（ascend/conn.py:32） | memfabric D2D；需 `ASCEND_MF_STORE_URL` config store |
| fake | `FakeKVManager`（fake/conn.py:22） | 无传输，合成 benchmark；**仅 decode 端** |

### 配置与部署形态

核心参数（server_args.py:3131-3210，`NS("disagg")` 命名空间）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--disaggregation-mode` | `null` | `prefill`/`decode`/`null`（统一模式） |
| `--disaggregation-transfer-backend` | `mooncake` | 见后端矩阵 |
| `--disaggregation-bootstrap-port` | `8998` | prefill 端 bootstrap HTTP 端口 |
| `--disaggregation-ib-device` | `None` | InfiniBand 设备（单设备/逗号列表/按 GPU JSON 映射），None 自动探测 |
| `--disaggregation-decode-enable-radix-cache` | `False` | decode 端启用 radix cache，缓存已传 KV 前缀 |
| `--disaggregation-decode-enable-offload-kvcache` | `False` | decode 端异步 KV offload（HiCache） |
| `--disaggregation-decode-extra-slots` | `None` | 为在传请求预留的额外 req_to_token 槽位 |
| `--disaggregation-decode-polling-interval` | `1` | decode 轮询周期 |
| `--num-reserved-decode-tokens` | `512` | 请求入 running batch 时预留的 decode token 数 |
| `--optimistic-prefill-attempts` | `0` | 乐观 prefill 前向次数（跳过 bootstrap 等待） |

`handle_pd_disaggregation`（pd_disaggregation_hook.py:16）强制规则：

- decode 端默认 `disable_radix_cache=True`（强制 chunk cache），除非显式开启 radix cache（与 `--enable-hisparse`、speculative、fake 后端互斥）。
- decode + DCP（`dcp_size>1`）仅允许 mooncake/nixl/fake 后端（需 DCP relayout），且要求 chunk cache。
- prefill 端不允许 fake 后端。
- `SGLANG_RUST_SERVER=1` 时 bootstrap 注册表由 rust api listener 服务（端口别名到 api 端口，hook:126）。
- `SGLANG_DISAGG_STAGING_BUFFER` 仅支持 mooncake/nixl。

### 控制面：bootstrap server

`CommonKVBootstrapServer`（common/conn.py:1612）是 aiohttp 应用，`_setup_routes` 提供：

| 路由 | 作用 |
|---|---|
| `PUT /route` | prefill 各 rank 登记 `(rank_ip, rank_port)`，建 dp/cp/tp/pp 维度 `prefill_port_table` |
| `GET /route` | decode 查询目标 prefill rank 传输端点（`?dp&cp&tp&pp` 参数） |
| `POST /register_dp_rank` / `POST /query_dp_ranks` | DP 模式 prefill dp_rank 登记/查询 |
| `GET /health` | 健康检查（decode 心跳，失败触发重算） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
