#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# sim.sh — iverilog 仿真入口
#
# 用法: bash scripts/sim.sh
# 期望: [PASS] led toggled N times in 100us  +  [EXIT 0] PASS
# -----------------------------------------------------------------------------
set -u

# iverilog 路径探测: 1) PATH  2) Windows 默认安装位置
IVERILOG=$(command -v iverilog 2>/dev/null || true)
VVP=$(command -v vvp 2>/dev/null || true)

if [ -z "$IVERILOG" ] && [ -x "/d/iverilog/bin/iverilog.exe" ]; then
  IVERILOG="/d/iverilog/bin/iverilog.exe"
  VVP="/d/iverilog/bin/vvp.exe"
fi

if [ -z "$IVERILOG" ]; then
  echo "ERROR: iverilog not found."
  echo "  安装: http://iverilog.icarus.com/"
  echo "  或:   export PATH=\$PATH:/d/iverilog/bin"
  exit 1
fi

cd "$(dirname "$0")/.."      # 切到工程根
mkdir -p sim/wave

echo "[iverilog] compile ..."
"$IVERILOG" -g2012 -o sim/wave/tb_chip_top.vvp \
  sim/tb/tb_chip_top.v \
  rtl/top/chip_top.v \
  rtl/core/ctrl/led_blink.v \
  rtl/infra/clk_rst/clk_rst.v \
  || { echo "[FAIL] compile error"; exit 2; }

echo "[vvp] run 100us ..."
SIM_OUT=$("$VVP" sim/wave/tb_chip_top.vvp 2>&1)
RC=$?
echo "$SIM_OUT"

# 双重判定：exit code + stdout 里的 [FAIL] 标记
if echo "$SIM_OUT" | grep -q '\[FAIL\]'; then
  RC=3
fi

if [ $RC -eq 0 ]; then
  echo "[EXIT 0] PASS"
  echo "波形: sim/wave/tb_chip_top.vcd  (gtkwave sim/wave/tb_chip_top.vcd)"
else
  echo "[EXIT $RC] FAIL"
fi

exit $RC
