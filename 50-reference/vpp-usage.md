---
title: VPP 使用方法（CLI / 配置 / 运维）
tags: [vpp, networking, dpdk, reference, snippet, active]
created: 2026-07-29
summary: >-
    VPP 的日常使用速查：启动方式、startup.conf 关键配置、CLI 常用命令（接口/路由/邻居/插件）、抓包与调试、常见运维操作。与 [[20-protocols/vpp|VPP 知识]] 配合阅读。
category: reference
updated: 2026-07-29
sources: []
base_confidence: 0.8
lifecycle: reviewed
---

# VPP 使用方法（CLI / 配置 / 运维）

> 知识背景见 [[20-protocols/vpp|VPP 知识]]。本文是"怎么用"的操作手册。

## 1. 安装与启动

### 包安装（Ubuntu/Debian）

```bash
# 添加 FD.io 仓库（版本如 2402 / 2502，按需替换）
echo "deb [trusted=yes] https://packagecloud.io/fdio/2402/ubuntu/ $(lsb_release -sc) main" \
  | sudo tee /etc/apt/sources.list.d/99fdio.list
sudo apt update && sudo apt install vpp vpp-plugin-core vpp-plugin-dpdk
```

### 启动

```bash
# 前台调试启动（看日志）
sudo vpp unix { interactive cli-listen /run/vpp/cli.sock } 2>&1 | less

# 后台以 startup 配置启动（生产常用）
sudo systemctl start vpp
# 或
sudo vpp -c /etc/vpp/startup.conf
```

### 进入 CLI

```bash
# 方式一：交互式（startup 里配了 cli-listen 后）
sudo vppctl                # 等价于 vppctl -s /run/vpp/cli.sock
sudo vppctl "show interface"   # 直接执行单条命令
```

## 2. startup.conf 关键配置

位于 `/etc/vpp/startup.conf`，结构为嵌套大括号。最小可用示例：

```
unix {
  cli-listen /run/vpp/cli.sock   # 开启 CLI 套接字
  nodaemon                        # 前台运行；后台去掉此行
  log /tmp/vpp.log
  full-coredump
}

api-segment {
  gid vpp                         # 共享内存 API 段权限
}

cpu {
  main-core 1                     # main 线程绑核
  corelist-workers 2-3            # worker 线程绑核（多核转发）
  # 或用 workers 4 让 VPP 自动选 4 个核
}

dpdk {
  dev 0000:03:00.0 {              # 直通给 VPP 的 PCI 网卡
    name eth0                     # VPP 内接口名
  }
  dev 0000:03:00.1 {
    name eth1
  }
  uio-driver uio_pci_generic      # 或 vfio-pci
  no-multi-seg                    # 关闭 multi-segment（性能/兼容取舍）
}

plugins {
  plugin dpdk_plugin.so { enable }   # 显式启用/禁用插件
  plugin nat_plugin.so { enable }
  # plugin xxx_plugin.so { disable }
}
```

要点：
- **巨页**：DPDK 需要大页。启动前 `sudo sysctl -w vm.nr_hugepages=1024`，或在 `/etc/default/grub` 配 `default_hugepagesz=1GB hugepagesz=1GB hugepages=4`。
- **网卡绑定**：用 `sudo dpdk-devbind.py --bind=uio_pci_generic 0000:03:00.0` 把网卡从内核驱动解绑交给 DPDK。VPP 也可在 `dpdk { dev ... }` 里直接接管。
- **多核**：`cpu { workers N }` 是转发性能来源；worker 数量应匹配 NUMA 与网卡队列数（RSS）。

## 3. 常用 CLI 命令

### 接口（interface）

```bash
show interface                     # 列出接口、状态、计数
show interface address             # 显示接口 IP
set interface state eth0 up        # 启用接口
set interface ip address eth0 192.168.1.1/24   # 配 IP
set interface promiscuous on eth0 # 混杂模式
show hardware-interfaces          # 查看底层 PCI/驱动信息
show dpdk interface                # DPDK 接口统计（丢包、mbuf 不足等）
```

### 路由 / FIB

```bash
show ip fib                       # 查看 IPv4 FIB（转发信息库）
show ip fib 192.168.1.0/24
ip route add 10.0.0.0/8 via 192.168.1.254 eth0   # 加静态路由
ip route del 10.0.0.0/8
show ip neighbors                 # ARP / ND 邻居表
set ip neighbor eth0 192.168.1.254 00:11:22:33:44:55  # 静态 ARP
```

### 邻接表 / 隧道

```bash
show adj                          # adjacency（下一跳封装）表
create gre tunnel src 1.1.1.1 dst 2.2.2.2            # GRE 隧道
create vxlan tunnel src 1.1.1.1 dst 2.2.2.2 vni 100  # VXLAN 隧道
set interface ip address gre0 10.1.1.1/30
```

### 插件 / 节点图

```bash
show plugins                     # 已加载插件
show node                        # 列出所有 VLIB 节点（含类型、调用次数）
show node graph eth0-output      # 查看某节点的下游连接
show runtime                     # 节点调用计数、耗时（性能热点）
show threads                     # worker 线程与绑核情况
```

### 会话 / 特性（NAT、ACL 等插件的典型入口）

```bash
# NAT 示例（需 nat_plugin 启用）
nat44 add interface address eth0
nat44 enable sessions
show nat44 sessions

# ACL 示例（需 acl_plugin 启用）
acl-plugin add permit+reflect src 192.168.0.0/16 dst 0.0.0.0/0
```

### 抓包 / 调试

```bash
# VPP 内建 pkt trace（极有用，能看包走过哪些节点）
trace add dpdk-input 100        # 抓取 100 个包并跟踪节点路径
show trace                      # 查看跟踪结果（每个包经过的 node + 决策）
trace clear

# 数据包生成（测试用）
packet-generator new {
  name pg0
  interface eth0
  node ethernet
  ...
}
```

### 性能 / 计数器

```bash
show interface eth0             # 看 rx/tx 包数、丢包
show errors                     # 全局错误计数（丢包原因）
show buffers                    # buffer 池占用（巨页内存）
show memory                     # 内存分布
show cpu                        # 每 worker 的包处理速率（pps）
```

## 4. 常用运维操作

### 重启 VPP

```bash
sudo systemctl restart vpp
# 或进程内
vppctl ...  # 无直接 restart，kill 后 systemctl 拉起
```

### 配置持久化

- `vppctl` 的命令**默认不落盘**。要持久化，把命令写入 `/etc/vpp/startup.conf` 的 `exec` 段，或用 `exec /path/to/config.vpp` 在启动后批量执行：
  ```
  unix { ... exec /etc/vpp/setup.vpp }
  ```
  其中 `setup.vpp` 每行一条 CLI 命令。

### 从外部脚本调用

```bash
# 一行执行（适合 Ansible / 启动脚本）
sudo vppctl "set interface ip address eth0 192.168.1.1/24"
```

### 日志与排错

```bash
show log                        # 查看 VPP 运行日志
journalctl -u vpp -f            # systemd 日志
# DPDK 初始化失败多因巨页/驱动绑定，检查：
cat /proc/meminfo | grep Huge
dpdk-devbind.py --status
```

## 5. 最小可用示例（两段式）

1. **准备**：绑网卡 + 配大页（见 §2）。
2. **启动**：`sudo vpp -c /etc/vpp/startup.conf`。
3. **配置**：
   ```bash
   sudo vppctl "set interface state eth0 up"
   sudo vppctl "set interface state eth1 up"
   sudo vppctl "set interface ip address eth0 192.168.1.1/24"
   sudo vppctl "ip route add 0.0.0.0/0 via 192.168.1.254 eth0"
   ```
4. **验证**：`sudo vppctl "show interface"` 看计数增长，`trace add` 看包路径。

## 与本项目衔接

- 本项目 [[50-reference/npp-timer-mechanism|NPP]] 在 VPP 节点图里挂了 process node 做流表老化，调试时可用 `show node`、`show runtime` 看该节点调用情况。
- 写自定义插件时，参考 `VLIB_REGISTER_NODE` 宏与 `vlib_process_*` 系列 API（见 [[20-protocols/vpp|VPP 知识]] §核心概念）。
