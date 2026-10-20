# Handoff: System Cockpit Cross-Platform App

## User goal

Package the current System Cockpit dashboard as a cross-platform desktop app. The user is open to a complete rewrite and asked for an objective recommendation. The recommended direction was Electron, keeping the existing HTML UI initially while replacing the Python/local-HTTP runtime with a native desktop shell and IPC-based metrics access.

## Current status

- Electron implementation is present. Node.js 24.20.0 was installed after the user authorized continuing; in the current PowerShell the executable may need to be added from `%LOCALAPPDATA%\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3bbwe\node-v24.20.0-win-x64` because its PATH was not refreshed.
- `npm install` created `package-lock.json`. The Electron runtime initially timed out via GitHub, then installed successfully using `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`.
- Electron uses a context-isolated preload bridge (`window.systemCockpit.getStats()`) and `systeminformation` in the main process. Python and a local HTTP port are not needed by the packaged app. Browser mode remains compatible with the old API/demo fallback.
- Windows NSIS installer and ZIP built successfully under `release/`: `System Cockpit Setup 1.0.0.exe` and `System Cockpit-1.0.0-win.zip`. Dev-mode `npm run test:smoke` returned the expected local metrics object; packaged `System Cockpit.exe --smoke-test` exited with code 0 after the final build.
- Visual QA fixed UI issues: clipped nav/status at narrow widths, unsolicited auto-fullscreen requests, and the CPU gauge omitting the temperature value. Layout checks passed at 390, 600, 601, 768, 980, 1053, 1300, and 1440 px with no chip-text or nav overflow. All six tabs, pause/resume, and user-triggered fullscreen were exercised. Live mode was confirmed using the Python server, then the temporary server was stopped and the Windows package rebuilt.
- The dashboard keeps one invariant landscape grid at every screen size: four gauges across the top, trend panels on the left, and information panels on the right. Smaller landscape displays compress spacing, charts, and text without hiding or stacking regions. No document scrolling, nav scrolling, or detail-list clipping was observed at 600x400, 667x375, 768x600, 844x390, 1024x600, and 1366x768 across all six tabs. The final Windows installer was rebuilt and smoke-tested after this change.
- Header and panel corner accents now share the same 8px, 1px-line, 0.35-opacity style at desktop and small widths. Browser computed-style checks confirmed they match; the final Windows installer/ZIP was rebuilt and the packaged app smoke test passed.
- Current `systeminformation` in this Windows environment returns `null` for disk I/O counters, so disk read/write rates safely report 0 here. GPU reports `null` unless NVIDIA `nvidia-smi` is available; live mode now shows an explicit unavailable state and never synthesizes GPU data, while demo mode still has simulated GPU values. The Windows package was rebuilt and smoke-tested after this behavior change. `npm audit --omit=dev` reported zero vulnerabilities; the full initial install audit reported 8 moderate findings in the development dependency tree.
- A GitHub Actions matrix has been added for native Windows/macOS/Linux builds. The macOS and Linux builds have not been run locally; confirm them in CI. Linux smoke test uses `xvfb-run`.
- The Python service used for live UI verification was stopped afterward; port 8765 was confirmed closed.

## Confirmed code paths

- `系统数据驾驶舱.html` is the existing single-page UI. It loads local `echarts.min.js` and has bundled demo data.
- Around line 327, the page selects `./api/stats` when served over HTTP, otherwise `http://127.0.0.1:8765/api/stats`.
- Around line 381, `tryLive()` fetches that endpoint; successful responses switch the UI into live mode, failures fall back to demo data.
- `live_data_server.py` exposes `collect()` returning the metrics dictionary and serves it from `/api/stats`. Its fields include `hostname`, `uptime`, `cores`, `load`, `cpu`, `mem`, `memUsedGb`, `memTotalGb`, `disk`, `diskR`, `diskW`, `netRx`, `netTx`, `temp`, `procs`, `perCpu`, `topProc`, and `gpu`.
- The Python server uses `psutil`; GPU metrics are best-effort via `nvidia-smi` and return `null` when unavailable.

## Implemented architecture

- Electron main process collects local metrics with `systeminformation`; the sandboxed preload exposes only `getStats()` over IPC. The packaged app does not require Python or a local HTTP service.
- The existing HTML UI uses the IPC bridge in Electron and keeps its HTTP/demo modes for browser use.
- Live GPU is considered available only when a real GPU object with utilization is returned. `gpu: null` now yields an explicit unavailable message; synthetic GPU data is generated only in demo mode.
- Cross-platform `electron-builder` scripts and a native-runner GitHub Actions matrix are configured. macOS/Linux artifacts still require CI execution for verification.

## Trade-offs already discussed

- Electron: best ecosystem and consistent runtime, but larger package and higher memory use; recommended for this app.
- Tauri: smaller output, but more Rust and platform integration work, especially for system metrics.
- PyWebView + PyInstaller: least rewrite, but Python runtime and platform packaging remain product dependencies; not the preferred long-term direction.

## Remaining work / limitations

- macOS/Linux package jobs are configured in `.github/workflows/build-desktop.yml` but have not been executed from this Windows environment. Trigger the workflow manually or push a `v*` tag to validate and download those artifacts.
- The Windows app uses Electron's default icon. Add a project icon if branded installers are desired.
- Review the 8 moderate development-tree audit findings before changing build dependencies; runtime-only audit reported zero vulnerabilities.
- Re-run `npm run test:smoke` and the relevant `npm run dist:<platform>` after subsequent code changes.
