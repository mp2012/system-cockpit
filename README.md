# 系统数据驾驶舱 · System Cockpit

![License](https://img.shields.io/badge/license-MIT-blue)
![Offline](https://img.shields.io/badge/works-offline-brightgreen)
![ECharts](https://img.shields.io/badge/charts-Apache%20ECharts-5470c6)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

一个**纯前端 + 轻量本地服务**的 PC 实时性能监控面板。单屏总览 + 五个详情页签（CPU / 内存 / 磁盘 / 网络 / 显卡），数据可视化基于 ECharts。

- **完全离线 / 内网可用**：所有依赖（ECharts、字体）已本地化，不依赖任何外网。
- **数据不出本机**：后端仅绑定回环地址 `127.0.0.1`，不对外暴露。
- **跨平台**：Windows / Linux / macOS 均可运行。

## 界面预览

![系统数据驾驶舱 - 显卡详情](assets/screenshot.png)

---

## 功能特性

| 区域 | 内容 |
|------|------|
| 总览单屏 | CPU / 内存 / 磁盘 / 网络 四大仪表盘 + 负载趋势 + 系统负载雷达 + 核心占用 + TOP 进程 |
| CPU 详情 | 各核心占用率、历史趋势、各核心负载热力图、进程 CPU Top5 |
| 内存详情 | 占用趋势、已用/空闲环形图、进程内存 Top5、内存明细 |
| 磁盘详情 | 使用率仪表、读写速率趋势、当前读写柱状图、磁盘明细 |
| 网络详情 | 吞吐趋势、流量分布、当前速率、网络明细 |
| 显卡详情 | GPU 利用率仪表、显存占用环形图、利用率/温度趋势、GPU 明细 |

- **两种数据模式**
  - **实时模式**：由 `live_data_server.py` 提供真实系统指标（每 2 秒刷新）。
  - **演示模式**：未启动服务时自动使用合成数据，页面照常可看。
- **显卡（GPU）**：服务端通过 `nvidia-smi` 尽力采集（N 卡 + 驱动可用时显示真实数据）；无 N 卡 / 无驱动时前端自动回退到合成演示数据，页面不空白。
- **TOP 进程**已过滤 `System Idle Process`、`System`、`Idle` 等系统伪进程，列表更干净。

---

## 目录结构

```
系统数据驾驶舱/
├── 系统数据驾驶舱.html   # 前端主页面（双击即可用演示模式打开）
├── live_data_server.py   # 本地实时数据服务（psutil 采集 + 静态托管）
├── start.bat             # Windows 一键启动脚本
├── start.sh              # Linux / macOS 一键启动脚本
├── echarts.min.js        # 本地 ECharts 引擎（已离线化）
├── fonts/                # 本地字体（Orbitron，数字字体）
│   └── orbitron-latin-*.woff2
├── server.log            # 运行时日志（启动服务后生成）
└── README.md
```

---

## 快速开始

### 方式一：直接看演示（无需任何安装）
双击 `系统数据驾驶舱.html`，浏览器会以**演示模式**加载（合成数据），无需启动服务、无需联网。

### 方式二：实时数据（推荐）
1. 安装依赖（仅首次，需联网）：
   ```bash
   pip install psutil
   ```
2. 启动服务：
   ```bash
   python live_data_server.py
   ```
3. 浏览器打开 `http://127.0.0.1:8765/`，顶部数据源切到「实时」。

### 方式三：一键启动脚本
- **Windows**：双击 `start.bat`（自动装依赖 → 启动服务 → 打开浏览器）。
- **Linux / macOS**：
  ```bash
  chmod +x start.sh && ./start.sh
  ```
> 停止服务：关闭 Windows 弹出的「系统数据驾驶舱」窗口；或在 Linux/macOS 执行脚本输出的 `kill <PID>`。

---

## 数据源与实时模式

`live_data_server.py` 通过 `psutil` 采集系统指标，并在 `/api/stats` 返回 JSON，前端每 2 秒轮询一次。采集项包括：

- 主机名、运行时长、逻辑核心数、系统负载
- CPU 总占用率 + 每核心占用率
- 内存使用率、已用/总 GB
- 磁盘使用率、读写速率（MB/s）
- 网络下行/上行（Mbit/s）
- CPU 温度、进程数、CPU 占用 Top5 进程
- `gpu`：经 `nvidia-smi` 采集显卡利用率 / 显存 / 温度 / 频率 / 功耗（无 N 卡时返回 `null`）

> 实现细节：CPU 占用由 `cpu_times()` 差值自算基线（避免 `cpu_percent()` 在多线程服务下恒为 0）。

---

## 跨平台说明

| 组件 | 平台支持 | 备注 |
|------|----------|------|
| 前端 HTML | 任意现代浏览器 | 已本地化 ECharts 与字体，离线可用 |
| 后端服务 | Windows / Linux / macOS | 基于 `psutil`，已加固：`getloadavg` 在 Windows 不存在时按 CPU 估算；`net_io`/`disk_io` 在 macOS 可能返回 `None` 已保护；磁盘使用率取主目录所在分区 |
| GPU 真实数据 | 仅 NVIDIA（需 `nvidia-smi`） | 其它显卡自动回退演示数据 |

---

## 局域网访问（可选）

默认仅本机可访问。若需同网段其他电脑访问：

- **临时**：启动时设置环境变量
  ```bash
  # Windows (PowerShell)
  $env:COCKPIT_HOST="0.0.0.0"; python live_data_server.py
  # Linux / macOS
  COCKPIT_HOST=0.0.0.0 ./start.sh
  ```
- **持久**：编辑 `start.bat` 或 `start.sh`，取消 `COCKPIT_HOST=0.0.0.0` 那行的注释。

其他电脑用宿主机的**内网 IP** 访问：`http://<内网IP>:8765/`。

> ⚠️ 安全提示：开放到局域网后，网内任何人都能读取本机指标。本服务**只读**、不执行写操作，建议仅在可信网络使用、用完即停。

---

## 故障排查

| 现象 | 原因 / 处理 |
|------|------|
| 图表全空、仪表停在 0%，但顶部信息和 TOP 进程正常 | ECharts 未加载。多半是**旧版服务端进程仍在运行**（不托管本地 JS）。重启 `live_data_server.py` 后 `Ctrl+F5` 强刷。已内置 CDN 回退：联网时会自动恢复。 |
| 提示「图表引擎加载失败」 | `echarts.min.js` 与页面不在同目录，或静态服务未生效。确认文件齐全并重启服务。 |
| `import psutil` 报错 | 未安装依赖：`pip install psutil`。 |
| 显卡页显示合成数据 | 非 N 卡或未安装 `nvidia-smi`，属正常回退行为。 |
| TOP 进程里出现 `System Idle Process` | 不会——前端已过滤系统伪进程；若出现请检查服务端是否为最新版本并重启。 |

---

## 技术栈

- 前端：原生 HTML / CSS / JavaScript + [Apache ECharts 5](https://echarts.apache.org/)（本地引入）
- 后端：Python 3 + `psutil`（采集）、标准库 `http.server`（服务）
- 字体：Orbitron（数字显示，本地 woff2）

---

## 许可证

采用 [MIT 许可证](LICENSE)，可自由使用、修改与分发。
