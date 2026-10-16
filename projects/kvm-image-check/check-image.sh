#!/usr/bin/env bash
# check-image.sh — 公有云镜像发布前自检（RHEL8 系）
#
# 用途：在待发布的镜像内部运行（或 chroot 进镜像运行），逐项检查上公有云 KVM
#       的硬性要求。输出 PASS / WARN / FAIL 与退出码，可直接做产线出图门禁。
#
# 用法：
#   bash check-image.sh            # 常规检查，WARN 不失败
#   bash check-image.sh --strict   # 严格模式，WARN 也返回失败（CI 门禁推荐）
#
# 参考：concepts/KVM 公有云 镜像 适配、entities/公有云镜像 制作 与 导入 实战
#
# 退出码：0 = 无 FAIL；1 = 存在 FAIL；严格模式下 2 = 存在 WARN

set -u

STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1

PASS=0; WARN=0; FAIL=0
ok()      { printf '  [PASS] %s\n' "$*"; PASS=$((PASS+1)); }
warn()    { printf '  [WARN] %s\n' "$*"; WARN=$((WARN+1)); }
bad()     { printf '  [FAIL] %s\n' "$*"; FAIL=$((FAIL+1)); }
section() { printf '\n== %s ==\n' "$*"; }

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)  ESP_FALLBACK="BOOTX64.EFI" ;;
  aarch64) ESP_FALLBACK="BOOTAA64.EFI" ;;
  *)       ESP_FALLBACK="" ;;
esac

printf '公有云镜像自检 — 架构 %s\n' "$ARCH"

########################################
section "1. fstab（设备寻址与阻塞挂载）"
########################################
if [ -r /etc/fstab ]; then
  # 1.1 不得硬编码 /dev/ 设备路径
  hardcoded="$(awk '!/^[[:space:]]*#/ && NF>0 && $1 ~ /^\/dev\// {print $1" -> "$2}' /etc/fstab)"
  if [ -n "$hardcoded" ]; then
    bad "fstab 存在硬编码设备路径（云上设备名会变）："
    printf '%s\n' "$hardcoded" | sed 's/^/         /'
  else
    ok "fstab 无 /dev/ 硬编码"
  fi

  # 1.2 根分区必须用 UUID
  rootline="$(awk '!/^[[:space:]]*#/ && $2=="/" {print}' /etc/fstab)"
  case "$rootline" in
    UUID=*) ok "fstab 根分区使用 UUID" ;;
    "")     bad "fstab 未找到根分区条目" ;;
    *)      bad "fstab 根分区未用 UUID：$rootline" ;;
  esac

  # 1.3 非根挂载点必须带 nofail（云上数据盘可能不存在）
  nofail_missing="$(awk '!/^[[:space:]]*#/ && NF>0 && $2!="/" && $2!="none" && $4 !~ /nofail/ {print $2" ("$1")"}' /etc/fstab)"
  if [ -n "$nofail_missing" ]; then
    warn "以下非根挂载点缺 nofail，云上缺盘会阻塞启动："
    printf '%s\n' "$nofail_missing" | sed 's/^/         /'
  else
    ok "非根挂载点均带 nofail（或无额外挂载）"
  fi

  # 1.4 规范禁止项：swap
  if awk '!/^[[:space:]]*#/ && $3=="swap" {found=1} END{exit !found}' /etc/fstab; then
    warn "fstab 存在 swap 条目（阿里云镜像规范禁止 swap 分区）"
  else
    ok "无 swap 条目"
  fi
else
  bad "读不到 /etc/fstab"
fi

########################################
section "2. 引导（UEFI fallback 与 root=UUID）"
########################################
# 2.1 ESP removable fallback（云上 NVRAM 为空，只认这个路径）
ESP_MNT="$(findmnt -n -o TARGET -t vfat 2>/dev/null | head -1)"
[ -z "${ESP_MNT:-}" ] && ESP_MNT="/boot/efi"
if [ -n "$ESP_FALLBACK" ] && [ -f "$ESP_MNT/EFI/BOOT/$ESP_FALLBACK" ]; then
  ok "ESP fallback 存在：$ESP_MNT/EFI/BOOT/$ESP_FALLBACK"
elif [ -z "$ESP_FALLBACK" ]; then
  warn "未知架构 $ARCH，跳过 fallback 检查"
else
  bad "ESP 缺 removable fallback：$ESP_MNT/EFI/BOOT/$ESP_FALLBACK"
  printf '         修复：cp %s/EFI/redhat/shim*.efi %s/EFI/BOOT/%s\n' "$ESP_MNT" "$ESP_MNT" "$ESP_FALLBACK"
fi

# 2.2 内核参数 root= 必须 UUID
if grep -qE 'root=UUID=' /proc/cmdline 2>/dev/null; then
  ok "/proc/cmdline 的 root= 使用 UUID"
else
  grubroot="$(grep -m1 -oE 'root=[^ ]+' /boot/grub2/grub.cfg 2>/dev/null | head -1)"
  case "${grubroot:-}" in
    root=UUID=*) ok "grub.cfg 的 root= 使用 UUID" ;;
    "")          bad "未能从 cmdline/grub.cfg 解析出 root=" ;;
    *)           bad "grub.cfg 的 root= 非 UUID：$grubroot" ;;
  esac
fi

# 2.3 内核参数：网卡命名与串口日志
cmdline="$(cat /proc/cmdline 2>/dev/null)"
printf '%s' "$cmdline" | grep -q 'net.ifnames=0' \
  && ok "内核参数含 net.ifnames=0" \
  || warn "内核参数缺 net.ifnames=0（网卡可能被重命名导致配置失配）"
printf '%s' "$cmdline" | grep -q 'console=ttyS0' \
  && ok "内核参数含 console=ttyS0" \
  || warn "内核参数缺 console=ttyS0（云上串口看不到早期引导日志）"

########################################
section "3. initramfs 驱动（三种挂载形态）"
########################################
for img in /boot/initramfs-*.img; do
  [ -e "$img" ] || continue
  missing=""
  for drv in virtio_blk virtio_scsi nvme; do
    lsinitrd "$img" 2>/dev/null | grep -q "$drv" || missing="$missing $drv"
  done
  if [ -z "$missing" ]; then
    ok "$(basename "$img") 含 virtio_blk / virtio_scsi / nvme"
  else
    bad "$(basename "$img") 缺驱动：$missing"
  fi
done
# dracut 持久化配置（防内核升级丢失）
if [ -r /etc/dracut.conf.d/virtio.conf ] && grep -q 'virtio_blk' /etc/dracut.conf.d/virtio.conf; then
  ok "dracut 持久化配置存在（/etc/dracut.conf.d/virtio.conf）"
else
  warn "缺 /etc/dracut.conf.d/virtio.conf，内核升级后驱动可能丢失"
fi

########################################
section "4. 内核能力"
########################################
KVER="$(uname -r)"
KCONF="/boot/config-$KVER"
if [ -r "$KCONF" ]; then
  grep -q '^CONFIG_FW_CFG_SYSFS=y' "$KCONF" \
    && ok "内核 CONFIG_FW_CFG_SYSFS=y（云上改密码依赖）" \
    || bad "内核缺 CONFIG_FW_CFG_SYSFS=y，控制台改密码会失效"
  grep -qE '^CONFIG_BLK_DEV_NVME=(y|m)' "$KCONF" \
    && ok "内核提供 NVMe 驱动" \
    || bad "内核缺 CONFIG_BLK_DEV_NVME（阿里新规格 NVMe 云盘起不来）"
  grep -qE '^CONFIG_VIRTIO_BLK=(y|m)' "$KCONF" \
    && ok "内核提供 virtio-blk 驱动" \
    || bad "内核缺 CONFIG_VIRTIO_BLK"
else
  warn "找不到 $KCONF，跳过内核配置检查"
fi

########################################
section "5. 云初始化与 agent"
########################################
command -v cloud-init >/dev/null 2>&1 \
  && ok "cloud-init 已安装（$(cloud-init --version 2>/dev/null | head -1)）" \
  || bad "未安装 cloud-init（密码/公钥/网络注入全部失效）"

if [ -d /var/lib/cloud/instances ] && [ -n "$(ls -A /var/lib/cloud/instances 2>/dev/null)" ]; then
  warn "cloud-init 状态未清理（/var/lib/cloud/instances 非空），克隆实例可能不重新初始化"
else
  ok "cloud-init 状态已清理"
fi

if command -v qemu-ga >/dev/null 2>&1 || systemctl list-unit-files 2>/dev/null | grep -q 'qemu-guest-agent'; then
  ok "qemu-guest-agent 已安装" \
  ; else
  warn "未安装 qemu-guest-agent（建议安装）"
fi

systemctl list-unit-files 2>/dev/null | grep -qE 'aliyun|cloudmonitor|CloudResetPwd|OpsAgent' \
  && ok "检测到云平台 agent 服务" \
  || warn "未检测到云平台 agent（阿里云助手必装；华为云需 CloudResetPwdAgent）"

########################################
section "6. 机器身份与敏感残留"
########################################
if [ -s /etc/machine-id ]; then
  bad "/etc/machine-id 非空（批量实例身份重复）"
  printf '         修复：truncate -s 0 /etc/machine-id\n'
else
  ok "/etc/machine-id 已清空"
fi

if ls /etc/ssh/ssh_host_* >/dev/null 2>&1; then
  warn "存在 SSH 主机密钥（建议删除，由首次启动重建）"
else
  ok "SSH 主机密钥已清理"
fi

if [ -s /root/.ssh/authorized_keys ] || ls /home/*/.ssh/authorized_keys >/dev/null 2>&1; then
  warn "存在 authorized_keys，确认不是调试用公钥"
else
  ok "无 authorized_keys 残留"
fi

if [ -s /root/.bash_history ]; then
  warn "/root/.bash_history 非空"
else
  ok "无 bash_history 残留"
fi

########################################
section "7. 网络与 udev 痕迹"
########################################
if grep -rqs 'mac-address=' /etc/NetworkManager/system-connections/ 2>/dev/null; then
  bad "NetworkManager keyfile 中写死了 MAC 地址"
else
  ok "NM keyfile 无写死 MAC"
fi

[ -f /etc/udev/rules.d/70-persistent-net.rules ] \
  && bad "存在 70-persistent-net.rules（旧式网卡持久命名）" \
  || ok "无 70-persistent-net.rules"

if grep -rqs '^HWADDR=' /etc/sysconfig/network-scripts/ 2>/dev/null; then
  warn "ifcfg 中存在 HWADDR（建议删除该行）"
else
  ok "ifcfg 无 HWADDR"
fi

########################################
section "8. 磁盘布局与扩容能力"
########################################
# 8.1 growpart 能力
if command -v growpart >/dev/null 2>&1; then
  ok "growpart 已安装（cloud-init 自动扩容依赖）"
else
  warn "未安装 cloud-utils-growpart，云盘在线扩容不可用"
fi

# 8.2 LVM / swap 分区（阿里云规范不建议）
if lsblk -o TYPE 2>/dev/null | grep -q '^lvm'; then
  warn "检测到 LVM 卷（阿里云镜像规范明文禁止，且不利于 growpart 扩容）"
else
  ok "无 LVM 卷"
fi
if lsblk -o FSTYPE 2>/dev/null | grep -qw 'swap'; then
  warn "检测到 swap 分区（规范禁止）"
else
  ok "无 swap 分区"
fi

# 8.3 根分区应位于最后一个分区（否则云盘扩容无效）
ROOTDEV="$(findmnt -n -o SOURCE / 2>/dev/null)"
if [ -n "${ROOTDEV:-}" ]; then
  # 解析父设备与分区号（支持 nvme0n1p3 / vda3 两种命名）
  PKNAME="$(lsblk -no PKNAME "$ROOTDEV" 2>/dev/null | head -1)"
  PARTN="$(lsblk -no PARTN "$ROOTDEV" 2>/dev/null | head -1)"
  if [ -n "${PKNAME:-}" ] && [ -n "${PARTN:-}" ]; then
    MAXN="$(lsblk -no PARTN "/dev/$PKNAME" 2>/dev/null | sort -n | tail -1)"
    if [ "$PARTN" = "$MAXN" ]; then
      ok "根分区是最后一个分区（扩容链路可用）"
    else
      warn "根分区不是最后一个分区（扩出的空间无法并给根，需调整布局）"
    fi
    # 分区表类型
    if command -v parted >/dev/null 2>&1; then
      ptype="$(parted -s "/dev/$PKNAME" print 2>/dev/null | awk -F': ' '/Partition Table/{print $2}')"
      case "$ptype" in
        gpt) ok "分区表为 GPT（UEFI 必要）" ;;
        msdos) warn "分区表为 MBR（若做 UEFI 引导需 GPT）" ;;
      esac
    fi
  fi
fi

########################################
printf '\n================ 汇总 ================\n'
printf 'PASS=%d  WARN=%d  FAIL=%d\n' "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf '结论：存在 %d 项必修问题，禁止发布。\n' "$FAIL"
  exit 1
fi
if [ "$STRICT" -eq 1 ] && [ "$WARN" -gt 0 ]; then
  printf '结论：严格模式，%d 项告警视为不通过。\n' "$WARN"
  exit 2
fi
printf '结论：可发布。\n'
exit 0
