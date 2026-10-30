#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统数据驾驶舱 · 实时数据服务
=============================
仅绑定本机回环地址 127.0.0.1，数据不出电脑，安全。
用法:
    pip install psutil          # 若未安装
    python3 live_data_server.py
然后浏览器打开:  http://127.0.0.1:8765/
    - 访问首页: 返回驾驶舱页面本身（推荐，同源无跨域问题）
    - 访问 /api/stats: 返回实时系统指标 JSON
"""
import json
import mimetypes
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psutil
except ImportError:
    print("[错误] 未安装 psutil，请先运行: pip install psutil")
    sys.exit(1)

# 默认仅本机(127.0.0.1)。需让局域网访问时：先设置环境变量 COCKPIT_HOST=0.0.0.0 再运行。
HOST = os.environ.get("COCKPIT_HOST", "127.0.0.1")
PORT = int(os.environ.get("COCKPIT_PORT", "8765"))
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "系统数据驾驶舱.html")

_last_net = None
_last_disk = None
_last_cpu = None
_last_percpu = None
_last_gpu = (0, None)
_boot_ts = time.time()
_collect_lock = threading.Lock()


def _collect():
    """采集一次系统快照，返回与前端约定结构的 dict。"""
    global _last_net, _last_disk, _last_cpu, _last_percpu
    now = time.time()

    # 自己维护 CPU 基线：psutil.cpu_percent 的内部基线在 ThreadingHTTPServer
    # 下每请求线程各自独立，会恒返回 0。改用 cpu_times() 差值计算，线程安全。
    ct = psutil.cpu_times()
    ct_total = sum(ct)
    ct_busy = ct_total - ct.idle
    cpu = 0.0
    if _last_cpu is not None:
        d_busy = ct_busy - _last_cpu[0]
        d_total = ct_total - _last_cpu[1]
        if d_total > 0:
            cpu = max(0.0, min(100.0, d_busy / d_total * 100.0))
    _last_cpu = (ct_busy, ct_total)

    per_ct = psutil.cpu_times(percpu=True)
    per_cpu = [0.0] * len(per_ct)
    if _last_percpu is not None and len(_last_percpu) == len(per_ct):
        for i, c in enumerate(per_ct):
            c_total = sum(c)
            c_busy = c_total - c.idle
            d_busy = c_busy - _last_percpu[i][0]
            d_total = c_total - _last_percpu[i][1]
            if d_total > 0:
                per_cpu[i] = max(0.0, min(100.0, d_busy / d_total * 100.0))
    _last_percpu = [(sum(c) - c.idle, sum(c)) for c in per_ct]

    mem = psutil.virtual_memory()

    net = psutil.net_io_counters()
    disk = psutil.disk_io_counters()

    # 速率换算（字节/秒 -> Mbit/s 与 MB/s）
    net_rx = net_tx = 0.0
    if net and _last_net:
        dt = now - _last_net[0]
        if dt > 0:
            net_rx = (net.bytes_recv - _last_net[1]) / dt * 8 / 1e6
            net_tx = (net.bytes_sent - _last_net[2]) / dt * 8 / 1e6
    _last_net = (now, net.bytes_recv if net else 0, net.bytes_sent if net else 0)

    disk_r = disk_w = 0.0
    if disk and _last_disk:
        dt = now - _last_disk[0]
        if dt > 0:
            disk_r = (disk.read_bytes - _last_disk[1]) / dt / 1e6
            disk_w = (disk.write_bytes - _last_disk[2]) / dt / 1e6
    _last_disk = (now, disk.read_bytes if disk else 0, disk.write_bytes if disk else 0)

    # 系统盘使用率（跨平台：取用户主目录所在分区，避免 Windows 下 "/" 语义歧义）
    disk_usage = 0.0
    try:
        disk_usage = psutil.disk_usage(os.path.expanduser("~")).percent
    except Exception:
        pass

    # CPU 温度（尽力而为，无传感器时回退为估算）
    temp_c = None
    try:
        temps = psutil.sensors_temperatures()
        for _k, lst in (temps or {}).items():
            if lst:
                temp_c = lst[0].current
                break
    except Exception:
        pass
    if temp_c is None:
        temp_c = 34 + cpu * 0.42

    # 占用最高的 5 个进程（排除系统伪进程：空闲/系统内核等，避免列表被占名额）
    _skip_proc = {"System Idle Process", "System", "Idle", "Registry"}
    top = []
    try:
        for p in sorted(psutil.process_iter(["name", "cpu_percent", "memory_info"]),
                        key=lambda x: x.info.get("cpu_percent") or 0, reverse=True):
            nm = p.info.get("name") or "?"
            if nm in _skip_proc:
                continue
            mi = p.info.get("memory_info")
            top.append({
                "name": nm[:24],
                "cpu": round(p.info.get("cpu_percent") or 0.0, 1),
                "memMb": round((mi.rss / 1048576) if mi else 0.0, 0),
            })
            if len(top) >= 5:
                break
    except Exception:
        pass

    mem_used_gb = round((mem.total - mem.available) / 1073741824, 1)
    mem_total_gb = round(mem.total / 1073741824, 1)

    return {
        "hostname": socket.gethostname() or "LOCAL-WORKSTATION",
        "uptime": int(now - psutil.boot_time()),
        "cores": psutil.cpu_count(logical=True) or 1,
        "load": round(_load_avg(cpu), 2),
        "cpu": round(cpu, 1),
        "mem": round(mem.percent, 1),
        "memUsedGb": mem_used_gb,
        "memTotalGb": mem_total_gb,
        "disk": round(disk_usage, 1),
        "diskR": round(disk_r, 1),
        "diskW": round(disk_w, 1),
        "netRx": round(net_rx, 1),
        "netTx": round(net_tx, 1),
        "temp": round(temp_c, 1),
        "procs": len(psutil.pids()),
        "perCpu": [round(v, 1) for v in per_cpu],
        "topProc": top,
        "gpu": _collect_gpu(),
    }


def _num(s, default=0.0):
    try:
        return float(s)
    except Exception:
        return default


def _load_avg(cpu):
    """系统负载均值；Unix 用 getloadavg，Windows 等无此接口时按 CPU 占用估算。"""
    try:
        return psutil.getloadavg()[0]
    except (AttributeError, NotImplementedError, OSError):
        return (cpu / 100.0) * (psutil.cpu_count(logical=True) or 1)


def _collect_gpu():
    """尽力采集 GPU 指标（通过 nvidia-smi，无 N 卡/无驱动时回退为 None）。"""
    global _last_gpu
    now = time.time()
    if now - _last_gpu[0] < 2.5:
        return _last_gpu[1]
    gpu = None
    try:
        import subprocess
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total,"
             "temperature.gpu,clocks.current.graphics,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3)
        lines = [ln for ln in out.stdout.strip().splitlines() if ln.strip()]
        if lines:
            p = [x.strip() for x in lines[0].split(",")]
            if len(p) >= 3:
                gpu = {
                    "name": p[0] or "GPU",
                    "util": round(_num(p[1]), 1),
                    "memUsedMb": round(_num(p[2] if len(p) > 2 else 0), 0),
                    "memTotalMb": round(_num(p[3] if len(p) > 3 else 0), 0),
                    "temp": round(_num(p[4] if len(p) > 4 else 0), 1),
                    "clockMHz": round(_num(p[5] if len(p) > 5 else 0), 0),
                    "powerW": round(_num(p[6] if len(p) > 6 else 0), 1),
                }
    except Exception:
        gpu = None
    _last_gpu = (now, gpu)
    return gpu


def collect():
    """对外接口：串行化采集，规避 psutil.cpu_percent 的线程安全问题。"""
    with _collect_lock:
        return _collect()


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")

    def do_GET(self):
        if self.path.startswith("/api/stats"):
            body = json.dumps(collect()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        # 静态资源：命中本地文件则按类型直接返回，否则回退到首页（SPA）
        base = os.path.dirname(os.path.abspath(__file__))
        rel = self.path.split("?")[0].lstrip("/")
        fpath = os.path.normpath(os.path.join(base, rel)) if rel else HTML_PATH
        if rel and os.path.isfile(fpath) and fpath.startswith(base):
            try:
                with open(fpath, "rb") as f:
                    data = f.read()
                ctype = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self._cors()
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                pass
        try:
            with open(HTML_PATH, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            msg = "<h1>未找到 系统数据驾驶舱.html，请与本脚本放在同一目录</h1>".encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def log_message(self, fmt, *args):  # 精简日志
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))


if __name__ == "__main__":
    print("=" * 52)
    print("  系统数据驾驶舱 · 实时数据服务")
    print("  绑定地址: http://%s:%s/" % (HOST, PORT))
    print("  说明: 仅本机可访问，数据不对外，按 Ctrl+C 停止")
    print("=" * 52)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务。")
#（注：内容由AI生成）
