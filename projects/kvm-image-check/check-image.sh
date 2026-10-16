#!/usr/bin/env bash
# check-image.sh — 公有云镜像发布前自检（RHEL8 系）
#
# 用途：逐项检查上公有云 KVM 的硬性要求，输出 PASS / WARN / FAIL / SKIP 与退出码，
#       可直接做产线出图门禁。
#
# 用法：
#   bash check-image.sh                     # 在镜像内部运行（在线模式）
#   bash check-image.sh --strict            # 严格模式：WARN 也返回失败（CI 门禁推荐）
#   bash check-image.sh --root /mnt/imgroot # 离线模式：检查解包/挂载后的镜像树
#
# 在线 / 离线模式差异：
#   在线（默认）— 额外检查内核参数（/proc/cmdline）、分区布局（lsblk/parted）、
#                 系统服务（systemctl）；这些依赖运行环境。
#   离线（--root）— 只做文件级检查；环境依赖项输出 SKIP，不会误判为 FAIL。
#
# 参考：concepts/KVM 公有云 镜像 适配、entities/公有云镜像 制作 与 导入 实战
#
# 退出码：0 = 无 FAIL；1 = 存在 FAIL；严格模式下 2 = 存在 WARN

set -u

STRICT=0
ROOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1 ;;
    --root)   shift; ROOT="${1:-}"; ROOT="${ROOT%/}" ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) printf '未知参数：%s\n' "$1" >&2; exit 64 ;;
  esac
  shift
done

OFFLINE=0
[ -n "$ROOT" ] && OFFLINE=1

PASS=0; WARN=0; FAIL=0; SKIP=0
ok()      { printf '  [PASS] %s\n' "$*"; PASS=$((PASS+1)); }
warn()    { printf '  [WARN] %s\n' "$*"; WARN=$((WARN+1)); }
bad()     { printf '  [FAIL] %s\n' "$*"; FAIL=$((FAIL+1)); }
skip()    { printf '  [SKIP] %s\n' "$*"; SKIP=$((SKIP+1)); }
section() { printf '\n== %s ==\n' "$*"; }
indent()  { sed 's/^/         /'; }

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)  ESP_FALLBACK="BOOTX64.EFI" ;;
  aarch64) ESP_FALLBACK="BOOTAA64.EFI" ;;
  *)       ESP_FALLBACK="" ;;
esac

printf '公有云镜像自检 — 架构 %s，模式 %s\n' "$ARCH" "$([ "$OFFLINE" = 1 ] && printf '离线(%s)' "$ROOT" || printf '在线')"

########################################
section "1. fstab（设备寻址与阻塞挂载）"
########################################
if [ -r "$ROOT/etc/fstab" ]; then
  # 1.1 不得硬编码 /dev/ 设备路径
  hardcoded="$(awk '!/^[[:space:]]*#/ && NF>0 && $1 ~ /^\/dev\// {print $1" -> "$2}' "$ROOT/etc/fstab")"
  if [ -n "$hardcoded" ]; then
    bad "fstab 存在硬编码设备路径（云上设备名会变）："
    printf '%s\n' "$hardcoded" | indent
  else
    ok "fstab 无 /dev/ 硬编码"
  fi

  # 1.2 根分区必须用 UUID
  rootline="$(awk '!/^[[:space:]]*#/ && $2=="/" {print}' "$ROOT/etc/fstab")"
  case "$rootline" in
    UUID=*) ok "fstab 根分区使用 UUID" ;;
    "")     bad "fstab 未找到根分区条目" ;;
    *)      bad "fstab 根分区未用 UUID：$rootline" ;;
  esac

  # 1.3 非根真实挂载点必须带 nofail（排除伪文件系统与 bind 挂载）
  nofail_missing="$(awk '
      /^[[:space:]]*#/ || NF==0            { next }
      $2=="/" || $2=="none" || $2=="swap"   { next }
      $1=="none" || $1=="tmpfs" || $1=="devtmpfs" || $1=="proc" || $1=="sysfs" || $1=="devpts" { next }
      $3 ~ /^(proc|sysfs|devpts|tmpfs|devtmpfs|autofs|cgroup|cgroup2|debugfs|mqueue|hugetlbfs|pstore|binfmt_misc|securityfs|none|nullfs|swap)$/ { next }
      $4 ~ /bind/                          { next }
      $4 !~ /nofail/                       { print $2" ("$1" "$3")" }
    ' "$ROOT/etc/fstab")"
  if [ -n "$nofail_missing" ]; then
    warn "以下非根挂载点缺 nofail，云上缺盘会阻塞启动："
    printf '%s\n' "$nofail_missing" | indent
  else
    ok "非根真实挂载点均带 nofail（或无额外挂载）"
  fi

  # 1.4 规范禁止项：swap
  if awk '!/^[[:space:]]*#/ && $3=="swap" {found=1} END{exit !found}' "$ROOT/etc/fstab"; then
    warn "fstab 存在 swap 条目（阿里云镜像规范禁止 swap 分区）"
  else
    ok "无 swap 条目"
  fi
else
  bad "读不到 $ROOT/etc/fstab"
fi

########################################
section "2. 引导（UEFI fallback 与 root=UUID）"
########################################
# 2.1 ESP removable fallback（云上 NVRAM 为空，只认这个路径）
ESP_MNT="$ROOT/boot/efi"
if [ -n "$ESP_FALLBACK" ] && [ -f "$ESP_MNT/EFI/BOOT/$ESP_FALLBACK" ]; then
  ok "ESP fallback 存在：$ESP_MNT/EFI/BOOT/$ESP_FALLBACK"
elif [ -z "$ESP_FALLBACK" ]; then
  skip "未知架构 $ARCH，跳过 fallback 检查"
else
  bad "ESP 缺 removable fallback：$ESP_MNT/EFI/BOOT/$ESP_FALLBACK"
  printf '         修复：cp %s/EFI/redhat/shim*.efi %s/EFI/BOOT/%s\n' "$ESP_MNT" "$ESP_MNT" "$ESP_FALLBACK"
fi

# 2.2 内核参数 root= 必须 UUID
if [ "$OFFLINE" = 0 ] && [ -r /proc/cmdline ]; then
  cmdroot="$(tr ' ' '\n' < /proc/cmdline | grep -m1 '^root=')"
else
  cmdroot=""
fi
[ -z "$cmdroot" ] && cmdroot="$(grep -m1 -ohE 'root=[^ ]+' "$ROOT/boot/grub2/grub.cfg" 2>/dev/null | head -1)"
case "${cmdroot:-}" in
  root=UUID=*) ok "root= 使用 UUID（$cmdroot）" ;;
  "")          [ "$OFFLINE" = 1 ] && skip "离线模式且无 grub.cfg，无法校验 root=" || bad "未能从 cmdline/grub.cfg 解析出 root=" ;;
  *)           bad "root= 非 UUID：$cmdroot" ;;
esac

# 2.3 内核参数：网卡命名与串口日志
if [ "$OFFLINE" = 0 ] && [ -r /proc/cmdline ]; then
  cmdline="$(cat /proc/cmdline)"
elif [ -r "$ROOT/etc/default/grub" ]; then
  cmdline="$(grep -E '^GRUB_CMDLINE_LINUX=' "$ROOT/etc/default/grub" 2>/dev/null | head -1)"
else
  cmdline=""
fi
if [ -z "$cmdline" ]; then
  skip "取不到内核参数（离线且无 /etc/default/grub），跳过 net.ifnames / console 检查"
else
  printf '%s' "$cmdline" | grep -q 'net.ifnames=0' \
    && ok "内核参数含 net.ifnames=0" \
    || warn "内核参数缺 net.ifnames=0（网卡可能被重命名导致配置失配）"
  printf '%s' "$cmdline" | grep -q 'console=ttyS0' \
    && ok "内核参数含 console=ttyS0" \
    || warn "内核参数缺 console=ttyS0（云上串口看不到早期引导日志）"
fi

########################################
section "3. initramfs 驱动（三种挂载形态）"
########################################
# 解析后端优先级：lsinitrd(dracut) → cpio → python(内置 cpio newc 解析)
# 目的：让本项检查在没有 dracut 的环境（含离线镜像树）也能跑，而不是一律 SKIP
list_initramfs() {   # $1 = initramfs 文件；输出内含文件路径清单
  local img="$1"
  if [ "$LIST_BACKEND" = "lsinitrd" ]; then
    lsinitrd "$img" 2>/dev/null
  elif [ "$LIST_BACKEND" = "cpio" ]; then
    { gzip -dc "$img" 2>/dev/null || xz -dc "$img" 2>/dev/null || cat "$img"; } | cpio -t 2>/dev/null
  else
    "$LIST_PY" - "$img" <<'PYEOF'
import sys, gzip, lzma
path = sys.argv[1]
try:
    data = open(path, 'rb').read()
except OSError:
    sys.exit(1)

def rec_len(namesize, filesize):
    body = 110 + namesize
    body += (4 - body % 4) % 4
    body += filesize
    body += (4 - body % 4) % 4
    return body

def entries(data):
    """逐段解析 cpio：段首可能是 gzip/xz 流（dracut 的 early_cpio+压缩主段拼接格式）"""
    names = []
    while data:
        if data[:2] == b'\x1f\x8b':
            try:
                data = gzip.decompress(data)
            except Exception:
                return names
        elif data[:6] == b'\xfd7zXZ\x00':
            try:
                data = lzma.decompress(data)
            except Exception:
                return names
        off, size, trailer_end = 0, len(data), None
        while off + 110 <= size:
            if data[off:off+6] not in (b'070701', b'070702'):
                nxt = data.find(b'070701', off + 1)
                if nxt < 0:
                    break
                off = nxt
                continue
            hdr = data[off:off+110]
            try:
                filesize = int(hdr[54:62], 16)
                namesize = int(hdr[94:102], 16)
            except ValueError:
                break
            if namesize <= 0 or namesize > 4096:
                break
            name = data[off+110:off+110+namesize-1].decode('utf-8', 'replace')
            body = rec_len(namesize, filesize)
            if name == 'TRAILER!!!':
                trailer_end = off + body
                break
            names.append(name)
            off += body
        if trailer_end is None or trailer_end >= size:
            return names
        data = data[trailer_end:]
    return names

sys.stdout.write('\n'.join(entries(data)))
PYEOF
  fi
}

LIST_BACKEND=""
if command -v lsinitrd >/dev/null 2>&1; then
  LIST_BACKEND="lsinitrd"
elif command -v cpio >/dev/null 2>&1; then
  LIST_BACKEND="cpio"
elif LIST_PY="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)" && [ -n "$LIST_PY" ]; then
  LIST_BACKEND="python"
fi

if [ -z "$LIST_BACKEND" ]; then
  skip "无 lsinitrd / cpio / python，跳过 initramfs 驱动检查"
else
  found_img=0
  for img in "$ROOT"/boot/initramfs-*.img; do
    [ -e "$img" ] || continue
    found_img=1
    listing="$(list_initramfs "$img")"
    if [ -z "$listing" ]; then
      warn "$(basename "$img") 无法解析（不支持的压缩格式？），驱动需人工确认"
      continue
    fi
    missing=""
    for drv in virtio_blk virtio_scsi nvme; do
      printf '%s' "$listing" | grep -q "$drv" || missing="$missing $drv"
    done
    if [ -z "$missing" ]; then
      ok "$(basename "$img") 含 virtio_blk / virtio_scsi / nvme（后端 $LIST_BACKEND）"
    else
      bad "$(basename "$img") 缺驱动：$missing"
    fi
  done
  [ "$found_img" = 0 ] && skip "未找到 $ROOT/boot/initramfs-*.img"
fi
if [ -r "$ROOT/etc/dracut.conf.d/virtio.conf" ] && grep -q 'virtio_blk' "$ROOT/etc/dracut.conf.d/virtio.conf"; then
  ok "dracut 持久化配置存在（/etc/dracut.conf.d/virtio.conf）"
else
  warn "缺 /etc/dracut.conf.d/virtio.conf，内核升级后驱动可能丢失"
fi

########################################
section "4. 内核能力"
########################################
KCONF="$(ls "$ROOT"/boot/config-* 2>/dev/null | grep -v '\-debug$' | head -1)"
if [ -r "${KCONF:-}" ]; then
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
  skip "找不到 $ROOT/boot/config-*，跳过内核配置检查"
fi

########################################
section "5. 云初始化与 agent"
########################################
if [ "$OFFLINE" = 1 ]; then
  if [ -x "$ROOT/usr/bin/cloud-init" ] || [ -x "$ROOT/bin/cloud-init" ]; then
    ok "cloud-init 已安装"
  else
    bad "未安装 cloud-init（密码/公钥/网络注入全部失效）"
  fi
else
  command -v cloud-init >/dev/null 2>&1 \
    && ok "cloud-init 已安装（$(cloud-init --version 2>/dev/null | head -1)）" \
    || bad "未安装 cloud-init（密码/公钥/网络注入全部失效）"
fi

if [ -d "$ROOT/var/lib/cloud/instances" ] && [ -n "$(ls -A "$ROOT/var/lib/cloud/instances" 2>/dev/null)" ]; then
  warn "cloud-init 状态未清理（/var/lib/cloud/instances 非空），克隆实例可能不重新初始化"
else
  ok "cloud-init 状态已清理"
fi

if [ "$OFFLINE" = 1 ]; then
  if ls "$ROOT/usr/lib/systemd/system/" 2>/dev/null | grep -q '^qemu-guest-agent'; then
    ok "qemu-guest-agent 已安装"
  else
    warn "未安装 qemu-guest-agent（建议安装）"
  fi
  if ls "$ROOT/usr/lib/systemd/system/" 2>/dev/null | grep -qE 'aliyun|cloudmonitor|CloudResetPwd|OpsAgent'; then
    ok "检测到云平台 agent 服务"
  else
    warn "未检测到云平台 agent（阿里云助手必装；华为云需 CloudResetPwdAgent）"
  fi
else
  if command -v qemu-ga >/dev/null 2>&1 || systemctl list-unit-files 2>/dev/null | grep -q 'qemu-guest-agent'; then
    ok "qemu-guest-agent 已安装"
  else
    warn "未安装 qemu-guest-agent（建议安装）"
  fi
  if systemctl list-unit-files 2>/dev/null | grep -qE 'aliyun|cloudmonitor|CloudResetPwd|OpsAgent'; then
    ok "检测到云平台 agent 服务"
  else
    warn "未检测到云平台 agent（阿里云助手必装；华为云需 CloudResetPwdAgent）"
  fi
fi

########################################
section "6. 机器身份与敏感残留"
########################################
if [ -s "$ROOT/etc/machine-id" ]; then
  bad "/etc/machine-id 非空（批量实例身份重复）"
  printf '         修复：truncate -s 0 /etc/machine-id\n'
elif [ -e "$ROOT/etc/machine-id" ]; then
  ok "/etc/machine-id 已清空"
else
  warn "无 /etc/machine-id（systemd 首次启动会生成，确认符合预期）"
fi

if ls "$ROOT"/etc/ssh/ssh_host_* >/dev/null 2>&1; then
  warn "存在 SSH 主机密钥（建议删除，由首次启动重建）"
else
  ok "SSH 主机密钥已清理"
fi

if [ -s "$ROOT/root/.ssh/authorized_keys" ] || ls "$ROOT"/home/*/.ssh/authorized_keys >/dev/null 2>&1; then
  warn "存在 authorized_keys，确认不是调试用公钥"
else
  ok "无 authorized_keys 残留"
fi

if [ -s "$ROOT/root/.bash_history" ]; then
  warn "/root/.bash_history 非空"
else
  ok "无 bash_history 残留"
fi

########################################
section "7. 网络与 udev 痕迹"
########################################
if grep -rqs 'mac-address=' "$ROOT/etc/NetworkManager/system-connections/" 2>/dev/null; then
  bad "NetworkManager keyfile 中写死了 MAC 地址"
else
  ok "NM keyfile 无写死 MAC"
fi

if [ -f "$ROOT/etc/udev/rules.d/70-persistent-net.rules" ]; then
  bad "存在 70-persistent-net.rules（旧式网卡持久命名）"
else
  ok "无 70-persistent-net.rules"
fi

if grep -rqs '^HWADDR=' "$ROOT/etc/sysconfig/network-scripts/" 2>/dev/null; then
  warn "ifcfg 中存在 HWADDR（建议删除该行）"
else
  ok "ifcfg 无 HWADDR"
fi

########################################
section "8. 磁盘布局与扩容能力"
########################################
have_growpart=0
[ -x "$ROOT/usr/bin/growpart" ] && have_growpart=1
if [ "$OFFLINE" = 0 ] && command -v growpart >/dev/null 2>&1; then have_growpart=1; fi
if [ "$have_growpart" = 1 ]; then
  ok "growpart 已安装（cloud-init 自动扩容依赖）"
else
  warn "未安装 cloud-utils-growpart，云盘在线扩容不可用"
fi

# 以下检查依赖真实块设备，离线模式跳过
if [ "$OFFLINE" = 1 ]; then
  skip "离线模式：LVM / swap 分区 / 根分区位置 / 分区表 检查需真实块设备"
else
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

  ROOTDEV="$(findmnt -n -o SOURCE / 2>/dev/null)"
  if [ -n "${ROOTDEV:-}" ]; then
    PKNAME="$(lsblk -no PKNAME "$ROOTDEV" 2>/dev/null | head -1)"
    PARTN="$(lsblk -no PARTN "$ROOTDEV" 2>/dev/null | head -1)"
    if [ -n "${PKNAME:-}" ] && [ -n "${PARTN:-}" ]; then
      MAXN="$(lsblk -no PARTN "/dev/$PKNAME" 2>/dev/null | sort -n | tail -1)"
      if [ "$PARTN" = "$MAXN" ]; then
        ok "根分区是最后一个分区（扩容链路可用）"
      else
        warn "根分区不是最后一个分区（扩出的空间无法并给根，需调整布局）"
      fi
      if command -v parted >/dev/null 2>&1; then
        ptype="$(parted -s "/dev/$PKNAME" print 2>/dev/null | awk -F': ' '/Partition Table/{print $2}')"
        case "$ptype" in
          gpt)   ok "分区表为 GPT（UEFI 必要）" ;;
          msdos) warn "分区表为 MBR（若做 UEFI 引导需 GPT）" ;;
        esac
      fi
    fi
  fi
fi

########################################
printf '\n================ 汇总 ================\n'
printf 'PASS=%d  WARN=%d  FAIL=%d  SKIP=%d\n' "$PASS" "$WARN" "$FAIL" "$SKIP"
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
