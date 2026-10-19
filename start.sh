#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# ===== 可选：局域网访问 =====
# 默认仅本机可访问(127.0.0.1)。如需让同网段其他电脑访问，取消下一行注释
# （注意：开放后网内任何人都能读取本机指标，建议在可信局域网、用完即停）。
# export COCKPIT_HOST=0.0.0.0

# 优先 python3，回退 python
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "未找到 python3/python，请先安装 Python 3。"
  exit 1
fi

echo "[1/3] 检查依赖 psutil ..."
if ! "$PY" -c "import psutil" 2>/dev/null; then
  echo "    未检测到 psutil，正在安装（需要联网一次）..."
  "$PY" -m pip install --user psutil || pip3 install psutil
fi

echo "[2/3] 启动系统数据驾驶舱服务 (http://127.0.0.1:8765/) ..."
nohup "$PY" live_data_server.py > server.log 2>&1 &
PID=$!
echo "    服务 PID: $PID（日志见 server.log）"

echo "[3/3] 等待服务就绪并打开浏览器 ..."
sleep 2
URL="http://127.0.0.1:8765/"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"          # Linux
elif command -v open >/dev/null 2>&1; then
  open "$URL"              # macOS
else
  echo "    无法自动打开浏览器，请手动访问: $URL"
fi

echo
echo "服务已在后台启动。停止服务请执行: kill $PID"
echo "（脚本退出不影响后台服务；如需停止见上方命令）"
