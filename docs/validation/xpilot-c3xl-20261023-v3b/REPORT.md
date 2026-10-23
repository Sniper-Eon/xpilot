# X-20261023-03 C3XL xpilot UI v3 部署与停车验证记录（round 3）

## 结论

- 状态：**DONE**。设备从 `2f1cd51506716d70c21efee98b60959b82d216fc` fast-forward 到目标 `7ee2e996515f9648be81dc3ce12d5551ead7ba05`，完成设备原生构建、Panda 禁止刷写门、正常服务启动、60 秒 UI 日志、30 秒性能采样、真实 GPU 大屏 E2E、三项交互补证和最终服务恢复。
- 设备：C3XL `comma-9c13c9f5`。历史地址 `172.16.1.202` 本轮未使用；当前地址为 `192.168.102.113`。开始任何设备写入前，SSH `hostname` 精确回读 `comma-9c13c9f5`。
- 最终运行态：`comma.service=active`；两层 manager 存在；`ui`、`pandad`、`hardwared` 均 `running=true`、`exitCode=0`。
- 最终安全态：`IsOffroad=1`、`deviceState.started=false`。最终 15 秒取得 150 余个 Panda 样本，全部 `controlsAllowed=false`、`faultStatus=none`、`pandaType=tres`。
- 仓库原样 `big_screen_e2e.py`：`passed=true`、`errors=[]`。12 张 2160×1080 PNG 全部生成并逐张查看；每张严格小于 400,000 bytes。
- UI v3 规则成立：Home、Toggles、Plugins、Tesla、Network、Device、Software、Developer 和 Store 都是原生页面，`mici_draws=0`；只有 Models 使用声明的 mici fallback，`mici_draws=15`。Store 的 `Back` 真实触摸返回通过。
- 交互补证：`IsMetric` 真实触摸由 `true → false → true`，已恢复；Device 的 Reboot 生产回调打开 `ConfirmDialog`，真实触摸 Cancel 后 `DoReboot` 完全未改变；没有确认 reboot、power off、reset calibration、uninstall 或其它危险动作。
- Panda 构建版本和真实设备均为 `DEV-443dd964-DEBUG`；构建签名固件 SHA-256 仍为 `656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`。没有刷 Panda，也没有调用 reset/safety 设置。
- 本轮没有修改任何产品源码、Params 定义、网络配置或用户数据；Git 变更只在 `docs/validation/xpilot-c3xl-20261023-v3b/`。

## 版本身份与同步

| 项目 | 结果 |
|---|---|
| 来源 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git`，分支 `xpilot` |
| `git fetch` 后 `origin/xpilot` | `7ee2e996515f9648be81dc3ce12d5551ead7ba05`，满足要求的 `7ee2e99` 前缀 |
| 本地主机验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source`，`xpilot`；同步前 `3ad601ca2284e0b1ed39967b3d182a7304329b20`，同步后 `7ee2e996...` |
| 主工作树 | `/Users/mile/Desktop/mo-op` 在其它分支并有大量用户改动；本轮未切换、清理或覆盖 |
| 设备活动目录 | `/data/openpilot -> /data/xpilot-install-20261022/candidate` |
| 设备更新前 HEAD | `2f1cd51506716d70c21efee98b60959b82d216fc` |
| 设备更新后/最终 HEAD | `7ee2e996515f9648be81dc3ce12d5551ead7ba05` |
| 增量 bundle | `/data/xpilot-install-20261022/xpilot-20261023-v3b.bundle` |
| bundle SHA-256 | `e643d81dadbb46dd15789df54b705cdb67cb3b48a14937bc26821dce9b896a13`，主机与设备一致 |
| bundle 范围 | prerequisite `2f1cd515...`；head `7ee2e996... refs/remotes/origin/xpilot`；主机与设备 `git bundle verify` 均成功 |
| Panda/safety 差异 | `2f1cd515..7ee2e996` 对 `panda/` 和 `opendbc_repo/opendbc/safety/` 的差异为空 |

设备工作树保留上一轮已经记录的 LFS 实体文件状态和未跟踪 `prebuilt`；本轮没有清理或提交它们。同步过程只更新设备 `origin/xpilot`，再在 `xpilot` 上执行 `--ff-only`，设备提交身份与远端目标完全一致。

## 安全门

首次写入前、上传 bundle 后停服前、E2E 停服前和最终恢复后均做了安全检查：

- `hostname=comma-9c13c9f5`，`/data/hardware_profile=c3xl`。
- `/data/params/d/IsOffroad=1`。
- `deviceState.started=false`。
- 实时 Panda 为 Tres；`controlsAllowed=false`、`faultStatus=none`。
- 活动路径和更新前 HEAD 分别为 `/data/xpilot-install-20261022/candidate`、`2f1cd515...`。
- 全程没有进入 onroad、没有 engagement、没有发 CAN、没有清数据、没有连接或忘记 Wi-Fi。

## 构建与 Panda 禁止刷写门

服务停止后执行：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

完整日志：`/data/xpilot-ui-check-v3b-build.log`。退出码 0，结尾为：

```text
scons: done building targets.
real 6.75
user 5.77
sys 1.35
```

完整日志没有 `warning` 或 `error`，所以没有构建 warning/error 可逐字列出。

服务保持停止时通过 SPI 只读检查真实 Panda：

- 硬件档案：`c3xl`；SPI serial `1d002d000a51303436323838`；raw type `09`；应用态、非 bootstub。
- 构建固件版本：`DEV-443dd964-DEBUG`。
- 设备 Panda 版本：`DEV-443dd964-DEBUG`。
- 构建文件 SHA-256：`656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`。
- 设备 health：`controls_allowed=false`、`faults=0`、`fault_status=0`、`spi_error_count=0`。
- 正常服务日志还明确打印设备签名前缀和 expected 相同：`89e7f6a96b68f6a0`。

版本没有差异，因此按任务门禁停止在只读检查，没有进入任何刷写路径。

## 正常服务、60 秒 UI 日志与最终恢复

第一次启动后等待 manager 完整出现，再捕获 tmux 生产日志到 `/data/xpilot-ui-check-v3b-ui-60s.log`。窗口内没有 traceback，也没有 UI 退出；后续 runtime check 得到：

- `comma.service=active`。
- manager 两层进程存在。
- `ui`、`pandad`、`hardwared` 均 `running=true`、`exitCode=0`。
- `deviceState`、`pandaStates`、`managerState`、`peripheralState`、`uiDebug` 均 alive、valid。
- `started=false`，Panda 样本无 fault、未允许控制。

日志中的非致命问题逐字摘录如下；完整上下文保存在设备日志：

```text
ln: failed to create symbolic link '/home/comma/.cursor-server/vscode-server': File exists
ln: failed to create symbolic link '/home/comma/.windsurf-server/vscode-server': File exists
No IRQs found for 'fts_ts'
raylib: COMMA: Failed to initialize color correction
raylib: FONT: Requested codepoints glyphs found: [117/122]
raylib: FONT: Requested codepoints glyphs found: [107/122]
Request transport error while fetching models: HTTPSConnectionPool(host='raw.githubusercontent.com', port=443): Read timed out. (read timeout=10)
Failed to fetch fresh data. Using expired cache as fallback
No WiFi device found
FPS dropped below 60: 46
The authenticity of host '[ssh.github.com]:443 ([20.205.243.160]:443)' can't be established.
```

E2E 后重新启动 comma。最终 runtime check 再次通过：目标 HEAD 未变，关键进程全部运行，安全态未变。

## 30 秒 UI CPU 与帧时间

正常 comma 服务、停车 offroad 下采样 `/proc/<ui-pid>/stat` 和 `uiDebug`；结果保存在 `perf.json`，设备原始路径 `/data/xpilot-ui-check-v3b-perf.json`。

| 时长 | 帧样本 | UI 进程 CPU | frame time avg / median / p95 / p99 / max | frame CPU avg / p95 / max | >20 / >33.3 / >100 ms |
|---:|---:|---:|---|---|---|
| 30.0004 s | 1737 | 33.0662% | 17.2723 / 17.2721 / 17.2809 / 17.2908 / 17.3393 ms | 1.5428 / 1.9408 / 2.3606 ms | 0 / 0 / 0 |

该窗口没有持续掉帧或孤立长帧，但 60 秒生产日志和 E2E 初始化阶段仍分别出现问题表中的低 FPS 提示；不能用一个稳态窗口抹掉它们。

## 大屏 E2E 与交互补证

服务停止后执行仓库原样脚本：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v3b
```

完整日志：`/data/xpilot-ui-check-v3b-e2e.log`。`result.json` 为脚本原生输出：

- `passed=true`、`head=7ee2e996...`、`errors=[]`。
- 9 个顶层导航页面全部进入正确类，原生页 stack=1；Models fallback stack=2。
- Home、Toggles、Plugins、Tesla、Network、Device、Software、Developer 的 `mici_draws=0`；Models 的 `mici_draws=15`。
- Plugins → Store 打开 `StorePage`，标题带 Back 通过真实 press/release 返回，脚本最终确认 `_sub is None`。
- 模拟 onroad viewport 为 `(360,218,1440,644)`；5 张卡片都在声明 zone 内；blindspot overlay 已加载并绘制。
- E2E 日志另有 `FPS dropped below 60: 15`、`15`、`13`、`14`，以及色彩校正和缺 glyph 提示。

交互补证保存在 `interactions.json`，设备日志 `/data/xpilot-ui-check-v3b-interaction.log`：

- Toggles 首个 `IsMetric` 开关由真实触摸事件 `true → false → true`，最后值与原值一致。
- Device 的 Reboot 行使用生产 row callback 打开全屏 `ConfirmDialog`，再以真实触摸事件点击 Cancel；`DoReboot` 前后完全相同。
- 没有调用 confirm callback，没有设置 `DoReboot`，也没有触发任何其它危险动作。

## 截图逐张目视结论

- `offroad.png`、`nav-0-home.png`：原生 Home 清楚，版本/分支/提交完整；无 mici texture。首屏底部的 `Car` 行只显示上部，需要滚动。
- `nav-1-toggles.png`：标题、开关、行间距清楚；首屏底部下一行仅露出上部，需要滚动。交互补证证明第一项可切换并恢复。
- `nav-2-models.png`：按设计唯一使用 mici fallback，但 3× 内容仍严重横向裁切；`mountain dew model v3...` 右端消失，右侧 `SELECT` 按钮大部分越出画面。
- `nav-3-plugins.png`：原生行可读、无 mici texture；`Plugin Store ›` 中的箭头缺字显示为 `?`；`Auto Speed Limit: Speed Limit Offset` 的值显示成重叠/拼接的 `0 km/h|mph`；底部下一行部分可见。
- `plugins-store.png`：不是空页，初始状态明确显示 `Refresh: tap Refresh` 和 `REFRESH`。Back 与 breadcrumb 的区域位置正确、没有重叠，真实触摸返回通过；但 `‹ Back` 与 `Plugins › Store` 的两个箭头都缺字显示为 `? Back`、`Plugins ? Store`。
- `nav-4-tesla.png`：前几行清楚；`MADS Screen Activation` 的多选按钮横向超出内容区/屏幕，右侧 `5-...` 只剩一部分。
- `nav-5-network.png`：当前网络、Forget、锁和信号图标可读；没有 mici texture。E2E 没有连接/忘记任何网络。
- `nav-6-device.png`：设备信息和按钮清楚；首屏底部下一行部分可见，需要滚动。Reboot 的实际对话框和 Cancel 由交互 JSON 证明，本轮没有另外保存对话框 PNG。
- `nav-7-software.png`：版本、分支、更新、目标分支和卸载行均完整可读，没有明显重叠或裁切。
- `nav-8-developer.png`：ADB、SSH、SSH keys、Joystick 行清楚；首屏底部下一行只显示上部，需要滚动。
- `onroad-blindspot.png`：卡片位置符合 E2E zone，中央不再残留上一张 Developer 页面；强制左右盲区红色 overlay 覆盖两侧列，内容仍能辨认但对比度明显下降。它是脚本注入 `ui_state.started=True` 的真实 GPU 合成，不是实际相机或道路画面。

## 编号问题表

| # | 分类 | 实际症状 | PNG / 证据 |
|---:|---|---|---|
| 1 | 设备连接 | 第一次按 `root@192.168.102.113` SSH 返回 `Permission denied (publickey)`；改用上一轮实际账号 `comma` 后，hostname 精确回读 `comma-9c13c9f5`。 | 无 PNG；本轮连接记录。没有扫描或操作其它设备。 |
| 2 | 运行环境 | 生产启动仍打印 Cursor/Windsurf 符号链接已存在、`No IRQs found for 'fts_ts'`、raylib 色彩校正失败。 | `/data/xpilot-ui-check-v3b-ui-60s.log`。UI 本轮没有因此退出。 |
| 3 | 字体/导航 | 字体只找到 `[117/122]` 或 `[107/122]` glyph；`‹`、`›` 实际渲染成 `?`，导致 `Plugin Store ?`、`? Back`、`Plugins ? Store`。 | `nav-3-plugins.png`、`plugins-store.png`；生产/E2E 日志。Back 触摸功能仍通过。 |
| 4 | 模型目录网络 | `raw.githubusercontent.com` 多次 10 秒读超时，随后使用 expired cache；日志末尾还停在 GitHub SSH 首次 host authenticity 提示。 | `/data/xpilot-ui-check-v3b-ui-60s.log`。没有修改设备全局网络或 known_hosts。 |
| 5 | Network/Wi-Fi | 生产日志两次打印 `No WiFi device found`，但停服 E2E 的 NetworkUI 后续能列出当前和邻近 SSID；两个证据不一致，需协调者结合正常服务时序排查。 | `/data/xpilot-ui-check-v3b-ui-60s.log`、`nav-5-network.png`。本轮未连接/忘记网络。 |
| 6 | 帧率提示 | 生产日志出现 `FPS dropped below 60: 46`；E2E 出现 `15`、`15`、`13`、`14`。 | 生产/E2E 日志。另一方面 `perf.json` 的独立稳态 30 秒 1737 帧全部低于 20 ms；提示发生在不同窗口。 |
| 7 | Models 缩放/裁切 | mici fallback 仍明显过大：模型副标题被右边界裁掉，`SELECT` 按钮大部分越出屏幕。 | `nav-2-models.png`。Models 是唯一允许显示 mici texture 的页，因此不是 texture 泄漏，而是 fallback 布局问题。 |
| 8 | Tesla 横向溢出 | `MADS Screen Activation` 多选按钮超出右边界，最右选择只显示 `5-...` 的一部分。 | `nav-4-tesla.png`。 |
| 9 | Plugins 值文本 | `Auto Speed Limit: Speed Limit Offset` 右侧值显示为重叠/拼接的 `0 km/h|mph`。 | `nav-3-plugins.png`。 |
| 10 | 首屏行裁切 | Home、Toggles、Plugins、Device、Developer 的内容区底部都只露出下一行的一部分；列表可滚动，因此不是空页或数据丢失，但首屏视觉上是被裁开的行。 | `nav-0-home.png`、`nav-1-toggles.png`、`nav-3-plugins.png`、`nav-6-device.png`、`nav-8-developer.png`。 |
| 11 | 交互验证驱动 | 第一次补证用自动计算的滚动后 Reboot 坐标，未打开 ConfirmDialog，测试在 `interaction.py:78` 的 `assert isinstance(dialog, ConfirmDialog)` 停止。`finally` 恢复 toggle，`DoReboot` 未改变。第二次改为调用同一生产 Reboot row callback 打开弹窗，再真实触摸 Cancel，通过。 | `/data/xpilot-ui-check-v3b-interaction.log`（最终成功日志覆盖同路径）；失败 traceback 已在操作记录中保留于本报告。`interactions.json` 为最终通过结果。 |
| 12 | 验证命令环境 | 直接以文件路径运行 `c3xl_probe.py` 时，脚本目录中的 `hardware/panda.py` 遮蔽顶层 `panda`，报 `ImportError: cannot import name 'Panda' from partially initialized module 'panda'`；改用 `python3 -m openpilot.sunnypilot.hardware.c3xl_probe` 后只读 SPI 检查成功。另有未引用远端正则/`find -printf` 的 shell 命令被远端 shell 拆开，随后均改为单一安全命令重跑。 | 无 PNG；属于验证驱动/命令问题，不是产品 UI traceback。 |
| 13 | onroad 证据边界 | `onroad-blindspot.png` 是停服 E2E 注入 started 的合成图，不是实际相机、道路、车道、告警或车辆控制证据；红色 overlay 还降低两侧卡片对比度。 | `onroad-blindspot.png`、`result.json`。全程未上路、未 engagement。 |

## 证据

仓库目录：`docs/validation/xpilot-c3xl-20261023-v3b/`

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本记录 |
| `result.json` | 仓库原样 big-screen E2E 结果 |
| `perf.json` | 正常服务 30 秒 UI CPU/frame time |
| `interactions.json` | Toggle 恢复、Reboot ConfirmDialog/Cancel 结果 |
| `offroad.png`、`nav-0-home.png` | Home/offroad |
| `nav-1-toggles.png` ... `nav-8-developer.png` | 九个顶层导航页 |
| `plugins-store.png` | Store 子页、breadcrumb 与 Back |
| `onroad-blindspot.png` | 模拟 started、卡片和强制双侧盲区 overlay |
| `.gitattributes` | 仅本目录 PNG 使用普通 Git blob，避免 Hugging Face LFS 凭据阻断 |

所有 PNG 均为 2160×1080 RGBA，且严格小于 400,000 bytes。

设备证据：

- `/data/xpilot-install-20261022/xpilot-20261023-v3b.bundle`
- `/data/xpilot-ui-check-v3b-build.log`
- `/data/xpilot-ui-check-v3b-ui-60s.log`
- `/data/xpilot-ui-check-v3b-e2e.log`
- `/data/xpilot-ui-check-v3b/`（原始 `result.json` 和 12 张 PNG）
- `/data/xpilot-ui-check-v3b-perf.json`
- `/data/xpilot-ui-check-v3b-interaction.log`
- `/data/xpilot-ui-check-v3b-interactions.json`
- `/data/xpilot-install-20261022/runtime-check.json`（最终恢复状态）

## 回滚

更新前提交 `2f1cd51506716d70c21efee98b60959b82d216fc` 仍是当前 `7ee2e996...` 的直接祖先，并保留在同一 `/data/xpilot-install-20261022/candidate` 仓库中；上一轮 bundle `/data/xpilot-install-20261022/xpilot-20261023-v3.bundle` 和本轮增量 bundle 也都保留。停车停服后可把同一 `xpilot` checkout 回到 `2f1cd515...`，重新运行设备原生 SCons，再启动 comma。

更早的 `xpilot-rollback-20261022` 仍指向 `3d03575f...`，`/data/sp-sync-experiment-20261017/candidate` 也仍保留；它们不是本轮 `2f1cd515` 的直接替代。Panda 不需要回退：本轮前后构建版本和设备签名都未改变。

本轮没有执行回滚，因为目标提交成功运行、E2E 通过，且任务要求保留 `7ee2e99` 供协调者根据问题表继续修复。

## 未验证边界

- 没有道路、真实 onroad 相机、车道线、告警、车辆闭环控制、实际盲区信号或 engagement 验证。
- 没有人手触摸实体屏幕；触摸证据来自真实 GPU/生产 widget 的进程内映射事件。
- 没有 Refresh 插件商店、安装/更新/删除插件。
- 没有连接、忘记或修改任何 Wi-Fi/网络配置。
- 没有确认 reboot、power off、reset calibration 或 uninstall；只验证 Reboot 对话框出现后 Cancel。
- 没有修复问题表中的任何代码问题；按任务要求只部署、记录和提交证据。
