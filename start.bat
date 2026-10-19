@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem ===== 可选：局域网访问 =====
rem 默认仅本机可访问(127.0.0.1)。如需让同网段其他电脑访问，取消下一行注释
rem （注意：开放后网内任何人都能读取本机指标，建议在可信局域网、用完即停）。
rem set COCKPIT_HOST=0.0.0.0

echo [1/3] 检查依赖 psutil ...
python -c "import psutil" 2>nul
if errorlevel 1 (
    echo     未检测到 psutil，正在安装（需要联网一次）...
    python -m pip install --user --quiet psutil
    if errorlevel 1 (
        echo     安装失败，请手动执行: python -m pip install psutil
        pause
        exit /b 1
    )
)

echo [2/3] 启动系统数据驾驶舱服务 (http://127.0.0.1:8765/) ...
start "系统数据驾驶舱" python live_data_server.py
if errorlevel 1 (
    echo     启动失败：请确认 python 已加入 PATH。
    pause
    exit /b 1
)

echo [3/3] 等待服务就绪并打开浏览器 ...
timeout /t 2 >nul
start "" http://127.0.0.1:8765/

echo.
echo 服务已启动。关闭下方弹出的「系统数据驾驶舱」窗口即可停止。
echo （按任意键关闭本窗口，不影响已启动的服务）
pause >nul
