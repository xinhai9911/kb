#!/usr/bin/env bash
# run-tests.sh — check-image.sh 的 fixture 测试
#
# 不依赖真实镜像或 Linux 容器：构造三个受控的"解包镜像树"，用离线模式（--root）验证
#   - BAD   fixture：所有检查项都应为 FAIL / WARN（真阳性）
#   - GOOD  fixture：所有检查项都应为 PASS（真阴性，含伪文件系统不误报）
#   - WARN  fixture：无 FAIL 但有 WARN，用于验证 --strict 退出码
#
# 用法：bash tests/run-tests.sh
# 退出码：0 = 全部通过；1 = 有用例失败

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../check-image.sh"

if [ ! -f "$SCRIPT" ]; then
  printf '找不到 %s\n' "$SCRIPT" >&2
  exit 1
fi

TPASS=0; TFAIL=0
t_ok()   { printf '    [ok]   %s\n' "$*"; TPASS=$((TPASS+1)); }
t_bad()  { printf '    [FAIL] %s\n' "$*"; TFAIL=$((TFAIL+1)); }

assert_grep() {   # 文件 期望子串 说明
  if grep -qF -- "$2" "$1"; then t_ok "$3"; else
    t_bad "$3 —— 输出中缺少：$2"
  fi
}
assert_not_grep() {   # 文件 不应出现的子串 说明
  if grep -qF -- "$2" "$1"; then
    t_bad "$3 —— 输出中出现不应有的：$2"
  else
    t_ok "$3"
  fi
}
assert_exit() {   # 实际码 期望码 说明
  if [ "$1" = "$2" ]; then t_ok "$3（exit=$1）"; else
    t_bad "$3 —— 期望 exit=$2，实际 exit=$1"
  fi
}

# 生成合成 initramfs（gzip 压缩的 cpio newc）。$1 = 输出文件，其余参数 = 内含文件路径
make_initramfs() {
  local out="$1"; shift
  local py
  py="$(command -v python3 2>/dev/null || command -v python)"
  "$py" - "$out" "$@" <<'PYEOF'
import sys, gzip, os
out, names = sys.argv[1], sys.argv[2:]
def rec(name, data=b''):
    namesize = len(name) + 1
    hdr = (b'070701'
           + b'%08X' % 0          # ino
           + b'%08X' % 0o100644   # mode
           + b'%08X' % 0          # uid
           + b'%08X' % 0          # gid
           + b'%08X' % 1          # nlink
           + b'%08X' % 0          # mtime
           + b'%08X' % len(data)  # filesize
           + b'%08X' % 0 + b'%08X' % 0 + b'%08X' % 0 + b'%08X' % 0
           + b'%08X' % namesize   # namesize
           + b'%08X' % 0)         # check
    body = hdr + name.encode() + b'\0'
    body += b'\0' * ((4 - len(body) % 4) % 4)
    body += data
    body += b'\0' * ((4 - len(body) % 4) % 4)
    return body
main = b''.join(rec(n, b'module-bytes') for n in names) + rec('TRAILER!!!')
blob = gzip.compress(main)
if os.environ.get('EARLY') == '1':
    # 模拟 dracut：未压缩 early_cpio（微码段） + 压缩主段
    early = rec('early/microcode.bin', b'\x00' * 16) + rec('TRAILER!!!')
    blob = early + blob
open(out, 'wb').write(blob)
PYEOF
}

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

FILE_MODE=0
printf 'fixture 测试 — 脚本：%s\n' "$SCRIPT"

################################################################
printf '\n## 1. BAD fixture（真阳性：应报 FAIL/WARN）\n'
################################################################
ROOT_BAD="$TMPROOT/bad"
mkdir -p "$ROOT_BAD"/{etc/default,etc/ssh,etc/udev/rules.d,etc/sysconfig/network-scripts,etc/NetworkManager/system-connections,boot/grub2,var/lib/cloud/instances/i-123,root/.ssh}

cat > "$ROOT_BAD/etc/fstab" <<'EOF'
# test fixture
/dev/sda3   /       xfs   defaults       0 0
/dev/sda1   /boot   xfs   defaults       0 0
UUID=aaaa-bbbb   /data  xfs  defaults   0 0
UUID=cccc-dddd   none   swap  sw        0 0
EOF

cat > "$ROOT_BAD/boot/grub2/grub.cfg" <<'EOF'
menuentry 'Test' {
	linux16 /vmlinuz-4.18.0-test root=/dev/sda3 ro
}
EOF

printf 'GRUB_CMDLINE_LINUX="crashkernel=auto rhgb quiet"\n' > "$ROOT_BAD/etc/default/grub"

cat > "$ROOT_BAD/boot/config-4.18.0-test" <<'EOF'
# CONFIG_FW_CFG_SYSFS is not set
# CONFIG_BLK_DEV_NVME is not set
# CONFIG_VIRTIO_BLK is not set
EOF

printf 'machine-id-content\n'            > "$ROOT_BAD/etc/machine-id"
printf 'FAKEKEY\n'                        > "$ROOT_BAD/etc/ssh/ssh_host_rsa_key"
printf 'ssh-rsa FAKE debug key\n'         > "$ROOT_BAD/root/.ssh/authorized_keys"
printf 'rm -rf /\n'                       > "$ROOT_BAD/root/.bash_history"
printf 'rules\n'                          > "$ROOT_BAD/etc/udev/rules.d/70-persistent-net.rules"
printf 'HWADDR=52:54:00:aa:bb:cc\nBOOTPROTO=dhcp\n' > "$ROOT_BAD/etc/sysconfig/network-scripts/ifcfg-eth0"
printf 'mac-address=52:54:00:aa:bb:cc\n'  > "$ROOT_BAD/etc/NetworkManager/system-connections/eth0.nmconnection"
printf 'inst\n'                           > "$ROOT_BAD/var/lib/cloud/instances/i-123/instance-id"

# BAD initramfs：只有 virtio_blk，缺 virtio_scsi 与 nvme
make_initramfs "$ROOT_BAD/boot/initramfs-4.18.0-test.img" \
  "usr/lib/modules/4.18.0-test/kernel/drivers/block/virtio_blk.ko.xz"

OUT_BAD="$TMPROOT/bad.out"
bash "$SCRIPT" --root "$ROOT_BAD" > "$OUT_BAD" 2>&1
assert_exit "$?" 1 "BAD fixture 退出码为 1"

assert_grep  "$OUT_BAD" "fstab 存在硬编码设备路径" "检出 fstab 硬编码设备路径"
assert_grep  "$OUT_BAD" "fstab 根分区未用 UUID"    "检出根分区非 UUID"
assert_grep  "$OUT_BAD" "缺 nofail"                "检出非根挂载缺 nofail"
assert_grep  "$OUT_BAD" "存在 swap 条目"           "检出 fstab swap 条目"
assert_grep  "$OUT_BAD" "ESP 缺 removable fallback" "检出 ESP 缺 fallback"
assert_grep  "$OUT_BAD" "root= 非 UUID"            "检出 root= 非 UUID"
assert_grep  "$OUT_BAD" "缺 net.ifnames=0"         "检出缺 net.ifnames=0"
assert_grep  "$OUT_BAD" "缺 console=ttyS0"         "检出缺 console=ttyS0"
assert_grep  "$OUT_BAD" "缺 /etc/dracut.conf.d/virtio.conf" "检出缺 dracut 持久化配置"
assert_grep  "$OUT_BAD" "缺 CONFIG_FW_CFG_SYSFS"   "检出内核缺 FW_CFG_SYSFS"
assert_grep  "$OUT_BAD" "缺 CONFIG_BLK_DEV_NVME"   "检出内核缺 NVMe 驱动"
assert_grep  "$OUT_BAD" "缺 CONFIG_VIRTIO_BLK"     "检出内核缺 virtio-blk"
assert_grep  "$OUT_BAD" "未安装 cloud-init"        "检出未安装 cloud-init"
assert_grep  "$OUT_BAD" "cloud-init 状态未清理"    "检出 cloud-init 状态未清理"
assert_grep  "$OUT_BAD" "/etc/machine-id 非空"     "检出 machine-id 未清空"
assert_grep  "$OUT_BAD" "存在 SSH 主机密钥"        "检出 SSH 主机密钥残留"
assert_grep  "$OUT_BAD" "存在 authorized_keys"     "检出 authorized_keys 残留"
assert_grep  "$OUT_BAD" "/root/.bash_history 非空" "检出 bash_history 残留"
assert_grep  "$OUT_BAD" "写死了 MAC 地址"          "检出 NM keyfile 写死 MAC"
assert_grep  "$OUT_BAD" "70-persistent-net.rules"  "检出旧式网卡命名规则"
assert_grep  "$OUT_BAD" "ifcfg 中存在 HWADDR"      "检出 ifcfg HWADDR"
assert_grep  "$OUT_BAD" "未安装 cloud-utils-growpart" "检出缺 growpart"
assert_grep  "$OUT_BAD" "缺驱动： virtio_scsi nvme"    "检出 initramfs 缺驱动（合成 gzip+cpio 归档）"

################################################################
printf '\n## 2. GOOD fixture（真阴性：应全 PASS，WARN=0）\n'
################################################################
ROOT_OK="$TMPROOT/good"
mkdir -p "$ROOT_OK"/{etc/default,etc/ssh,etc/sysconfig/network-scripts,etc/NetworkManager/system-connections,etc/dracut.conf.d,boot/grub2,boot/efi/EFI/BOOT,var/lib/cloud/instances,usr/bin,usr/lib/systemd/system,root/.ssh}

cat > "$ROOT_OK/etc/fstab" <<'EOF'
UUID=1111-2222  /       xfs   defaults                                    0 0
UUID=3333-4444  /data   xfs   defaults,nofail,x-systemd.device-timeout=0   0 0
tmpfs           /tmp    tmpfs defaults                                    0 0
none            /proc   proc  defaults                                    0 0
devtmpfs        /dev    devtmpfs defaults                                 0 0
EOF

printf 'shim\n' > "$ROOT_OK/boot/efi/EFI/BOOT/BOOTX64.EFI"
cat > "$ROOT_OK/boot/grub2/grub.cfg" <<'EOF'
menuentry 'Test' {
	linux16 /vmlinuz-4.18.0-good root=UUID=1111-2222 ro
}
EOF
printf 'GRUB_CMDLINE_LINUX="net.ifnames=0 console=tty0 console=ttyS0,115200n8"\n' > "$ROOT_OK/etc/default/grub"
printf 'add_drivers+=" virtio_blk virtio_scsi virtio_net virtio_console nvme"\n'  > "$ROOT_OK/etc/dracut.conf.d/virtio.conf"

cat > "$ROOT_OK/boot/config-4.18.0-good" <<'EOF'
CONFIG_FW_CFG_SYSFS=y
CONFIG_BLK_DEV_NVME=m
CONFIG_VIRTIO_BLK=m
EOF

printf '#!/bin/sh\n' > "$ROOT_OK/usr/bin/cloud-init"
chmod +x "$ROOT_OK/usr/bin/cloud-init" 2>/dev/null || true
: > "$ROOT_OK/etc/machine-id"                       # 空文件 = 已清空
mkdir -p "$ROOT_OK/var/lib/cloud/instances"          # 存在但为空 = 已清理
printf '#!/bin/sh\n' > "$ROOT_OK/usr/bin/growpart"
chmod +x "$ROOT_OK/usr/bin/growpart" 2>/dev/null || true
printf '' > "$ROOT_OK/usr/lib/systemd/system/qemu-guest-agent.service"
printf '' > "$ROOT_OK/usr/lib/systemd/system/aliyun.service"

# GOOD initramfs：三种挂载形态驱动齐全
make_initramfs "$ROOT_OK/boot/initramfs-4.18.0-good.img" \
  "usr/lib/modules/4.18.0-good/kernel/drivers/block/virtio_blk.ko.xz" \
  "usr/lib/modules/4.18.0-good/kernel/drivers/scsi/virtio_scsi.ko.xz" \
  "usr/lib/modules/4.18.0-good/kernel/drivers/nvme/host/nvme.ko.xz"

# 真实 dracut 布局：未压缩 early_cpio（微码段）+ 压缩主段 拼接
export EARLY=1
make_initramfs "$ROOT_OK/boot/initramfs-4.18.0-good-early.img" \
  "usr/lib/modules/4.18.0-good/kernel/drivers/block/virtio_blk.ko.xz" \
  "usr/lib/modules/4.18.0-good/kernel/drivers/scsi/virtio_scsi.ko.xz" \
  "usr/lib/modules/4.18.0-good/kernel/drivers/nvme/host/nvme.ko.xz"
unset EARLY

OUT_OK="$TMPROOT/good.out"
bash "$SCRIPT" --root "$ROOT_OK" > "$OUT_OK" 2>&1
assert_exit "$?" 0 "GOOD fixture 退出码为 0"

assert_grep     "$OUT_OK" "fstab 无 /dev/ 硬编码"            "正确判定 fstab 无硬编码"
assert_grep     "$OUT_OK" "fstab 根分区使用 UUID"             "正确判定根分区 UUID"
assert_grep     "$OUT_OK" "非根真实挂载点均带 nofail"          "正确判定 nofail"
assert_not_grep "$OUT_OK" "/tmp (tmpfs"                       "伪文件系统未被误报（tmpfs 行不触发 nofail 告警）"
assert_not_grep "$OUT_OK" "/proc (none"                       "伪文件系统未被误报（proc/none 行不触发）"
assert_not_grep "$OUT_OK" "存在 swap 条目"                    "如实判定无 swap"
assert_grep     "$OUT_OK" "ESP fallback 存在"                "正确判定 ESP fallback"
assert_grep     "$OUT_OK" "root= 使用 UUID"                  "正确判定 root= UUID"
assert_grep     "$OUT_OK" "内核参数含 net.ifnames=0"          "正确判定 net.ifnames=0"
assert_grep     "$OUT_OK" "内核参数含 console=ttyS0"          "正确判定 console=ttyS0"
assert_grep     "$OUT_OK" "dracut 持久化配置存在"             "正确判定 dracut 配置"
assert_grep     "$OUT_OK" "CONFIG_FW_CFG_SYSFS=y"            "正确判定内核 FW_CFG_SYSFS"
assert_grep     "$OUT_OK" "内核提供 NVMe 驱动"                "正确判定内核 NVMe"
assert_grep     "$OUT_OK" "内核提供 virtio-blk 驱动"          "正确判定内核 virtio-blk"
assert_grep     "$OUT_OK" "cloud-init 已安装"                 "正确判定 cloud-init"
assert_grep     "$OUT_OK" "cloud-init 状态已清理"             "正确判定 cloud-init 状态"
assert_grep     "$OUT_OK" "qemu-guest-agent 已安装"           "正确判定 qemu-guest-agent"
assert_grep     "$OUT_OK" "检测到云平台 agent 服务"           "正确判定云平台 agent"
assert_grep     "$OUT_OK" "/etc/machine-id 已清空"            "正确判定 machine-id"
assert_grep     "$OUT_OK" "SSH 主机密钥已清理"                "正确判定 SSH 主机密钥"
assert_grep     "$OUT_OK" "NM keyfile 无写死 MAC"             "正确判定 MAC 绑定"
assert_grep     "$OUT_OK" "growpart 已安装"                   "正确判定 growpart"
assert_grep     "$OUT_OK" "含 virtio_blk / virtio_scsi / nvme" "正确判定 initramfs 驱动齐全（后端 python）"
assert_grep     "$OUT_OK" "initramfs-4.18.0-good-early.img 含 virtio_blk" "正确解析 early_cpio+压缩主段拼接布局（dracut 真实格式）"
assert_grep     "$OUT_OK" "PASS="                             "输出汇总行"

# GOOD 的 WARN 应为 0（保证"全绿"这个断言本身可信）
if grep -qE 'WARN=0' "$OUT_OK"; then t_ok "GOOD fixture WARN=0（全绿）"; else
  t_bad "GOOD fixture 存在非预期 WARN：$(grep -E 'WARN=' "$OUT_OK")"
fi

################################################################
printf '\n## 3. WARN-only fixture（验证 --strict 退出码）\n'
################################################################
ROOT_WARN="$TMPROOT/warn"
cp -r "$ROOT_OK" "$ROOT_WARN"
rm -f "$ROOT_WARN/usr/bin/growpart"                          # 制造 WARN：缺 growpart
rm -f "$ROOT_WARN/usr/lib/systemd/system/qemu-guest-agent.service"  # 制造 WARN：缺 agent

OUT_WARN="$TMPROOT/warn.out"
bash "$SCRIPT" --root "$ROOT_WARN" > "$OUT_WARN" 2>&1
assert_exit "$?" 0 "WARN-only：常规模式退出码 0"

OUT_WARN_S="$TMPROOT/warn-strict.out"
bash "$SCRIPT" --strict --root "$ROOT_WARN" > "$OUT_WARN_S" 2>&1
assert_exit "$?" 2 "WARN-only：严格模式退出码 2"

################################################################
printf '\n## 4. 离线模式约定\n'
################################################################
OUT_SKIP="$TMPROOT/good.out"
assert_grep "$OUT_SKIP" "[SKIP]" "离线模式下环境依赖项输出 SKIP（不误判为 FAIL）"

################################################################
printf '\n================ 测试汇总 ================\n'
printf '通过 %d 项，失败 %d 项\n' "$TPASS" "$TFAIL"
if [ "$TFAIL" -gt 0 ]; then
  printf '结论：测试未通过。\n'
  exit 1
fi
printf '结论：全部通过。\n'
exit 0
