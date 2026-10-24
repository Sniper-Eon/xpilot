# X-20261023-09 C3XL xpilot v6 设备验证记录

## 结论

- 总状态：**FAIL / NOT ALL PASS**。部署、设备 SCons、首次 manager 默认参数建立、最终恢复与最终服务运行均通过；`big_screen_e2e.py`、`ui_smoke.py`、2/8 个 `*_check.py`、生产 UI 插件加载以及 4/27 张尺寸截图失败。
- X-05 的两个具体显示问题**没有完全修复**：Clock 与 IP 的 `wide` 图正常，但 `small` 和 `medium` 图仍在右缘裁切。Clock 最后一位 `8` 被切；IP 的完整 state 是 `192.168.102.113`，画面只完整显示到 `192.168.102.11`，末尾 `3` 被切。
- 其余 23 张截图没有文字贴边裁切、文字互相重叠或小于可读下限。捕获到的最小字号是 30 px；IP small 是 34 px。没有截图出现 `...`。
- 设备：只操作 `comma@192.168.102.113`；每个写阶段前均确认 `hostname=comma-9c13c9f5`、`hardware_profile=c3xl`、`IsOffroad=1`、`IsEngaged=0`。没有访问或修改其它设备。
- 目标和设备最终活动提交均为 `bfca6fcec388f019e9b3046e9067f3a11e7d27ff`。任务开始时它就是刷新后的 `origin/xpilot`；验证期间远端又前进到 `784485f3792b5a90f583471602e9330825d45129`，本轮没有把后来的两个提交混入明确锁定的目标。
- 最终服务：`comma.service=active`；两层 `manager.py` 和生产 UI 进程均存在。
- 四项状态均已恢复到测试前的**存在性和逐字节内容**：`XpilotTileLayout`、`XpilotTileTheme=Graphite`、`XpilotBms=1`、Tesla Model Y HW4 `CarPlatformBundle`。

## 按任务顺序的通过/失败

| 项目 | 结果 | 证据摘要 |
|---:|---|---|
| 1. 部署、SCons、首次启动 manager、再停服 | **PASS** | 增量 bundle 两端校验；设备 `2bd5436… -> bfca6fc…` ff-only；SCons rc=0；首次启动后 Car/Map/Clock/IP 默认参数均为 `1`；随后服务停止 |
| 2a. `big_screen_e2e.py` | **FAIL，rc=1** | 唯一结果 error 是 drive 编辑页出现 8 个数据 tile，而脚本集合断言失败；另有 3 次 `overspeed_warning.ui` 缺模块 traceback |
| 2b. `ui_smoke.py` | **FAIL，rc=1** | zh-CHS 缺文件问题已消失；新失败为 C3XL 上窗口尺寸不满足脚本硬编码的 `(536,240)` |
| 3. 全部 `*_check.py` | **FAIL，6/8 PASS** | `manifest_check.py` 和 `plugin_host_check.py` 失败；其它 6 项 rc=0 |
| 4a. 正式服务 60 秒运行 | **FAIL（服务存活，但有 UI traceback）** | 服务、manager、UI PID 均持续存在；日志有 3 次相同的 `ModuleNotFoundError: openpilot.tesla.plugins.overspeed_warning` |
| 4b. 9 个 tile × 3 个尺寸截图 | **FAIL，23/27 目视 PASS** | Clock small/medium、IP small/medium 右缘裁切；其它图无裁切、重叠或过小文字 |
| 5. 恢复四项参数与布局 | **PASS** | 最终服务启动并稳定 10 秒后再次 `cmp`；4 个 SHA-256 与测试前相同 |

## 身份、部署与安全门

| 项目 | 结果 |
|---|---|
| 主机 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source` |
| 报告分支 | `task/X-20261023-09`，从明确目标 `bfca6fc…` 新建 |
| 目标提交 | `bfca6fcec388f019e9b3046e9067f3a11e7d27ff` |
| 设备 | `comma-9c13c9f5`，`c3xl`，`192.168.102.113` |
| 活动路径 | `/data/openpilot -> /data/xpilot-install-20261022/candidate` |
| 更新前设备 HEAD | `2bd5436a36410018c83baf65de4cdc4aa100a1c4` |
| 更新后/最终设备 HEAD | `bfca6fcec388f019e9b3046e9067f3a11e7d27ff` |
| 更新关系 | `2bd5436…` 是 `bfca6fc…` 的祖先；设备执行 `git merge --ff-only bfca6fc…` |
| bundle | `/data/xpilot-install-20261022/xpilot-20261023-v6.bundle` |
| bundle SHA-256 | `997f3c9e1f8b6b549e433d0efe2d9a7408d6a5df4b61f8cb4f0f8e89b4cb6c7b`，主机和设备一致 |
| bundle 内容 | requires `2bd5436…`；contains `bfca6fc… refs/remotes/origin/xpilot`；两端 `git bundle verify` 成功 |
| 最终安全态 | `IsOffroad=1`、`IsEngaged=0`、`comma.service=active` |

设备 checkout 更新前有 287 项既有工作树差异，主要是 LFS 实体文件和既有生成物。没有执行 `clean`、`reset` 或覆盖这些文件；ff-only 更新涉及的 12 个版本文件没有与既有差异冲突。

所有 SSH 都使用既有 known_hosts 和 `StrictHostKeyChecking=yes`。没有修改网络、SSH 设置、硬件参数、Panda 固件或车辆控制设置；没有上路、接合或发送验证 CAN。

## 项目 1：部署、重建和首次 manager 启动

设备停服后执行：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p \
  scons -C /data/xpilot-install-20261022/candidate -j4
```

结果：**PASS，rc=0**。完整日志见 `build.log`。

```text
scons: done building targets.
real 13.03
user 11.47
sys 1.59
```

随后只启动一次目标版本的 `comma.service`，等待正式 manager 和 UI PID 出现，再等待 8 秒。默认参数读回：

```text
XpilotCarTile=1
XpilotMapTile=1
XpilotClockTile=1
XpilotIpTile=1
```

确认后停止服务，再运行项目 2 和 3。这个顺序避免了 X-05 在首次 manager 写默认值之前执行 `big_screen_e2e.py` 的问题。

### Panda 边界

正式运行日志仍显示：

```text
Panda 1d002d000a51303436323838 connected, version: DEV-443dd964-DEBUG,
signature 89e7f6a96b68f6a0, expected 34f6597f7fe52f31
```

本轮没有显式 flash/reset/safety 设置，日志也没有证明刷写完成。因此不能声称 Panda 固件与本次构建匹配，或 safety 变更已在 Panda 上激活。

## 项目 2：`big_screen_e2e.py` 与 `ui_smoke.py`

两个命令都从 `/data/openpilot` 使用以下环境，且服务处于停止状态：

```bash
env -C /data/openpilot \
  PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo \
  python3 ...
```

### 2a. `big_screen_e2e.py`

命令：

```bash
python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v6
```

结果：**FAIL，rc=1**。布局和 Driver View 均被脚本恢复。`result.json` 的完整 errors 数组：

```text
drive edit tiles: ['speed_card', 'speed_limit_card', 'lead_card', 'car', 'map', 'clock', 'ip', 'bms']
```

最终 traceback：

```text
Traceback (most recent call last):
  File "/data/xpilot-install-20261022/candidate/tools/sp_tesla_e2e/big_screen_e2e.py", line 447, in <module>
    assert result['passed']
           ~~~~~~^^^^^^^^^^
AssertionError
```

此外，在创建 UI host 时出现 3 次相同的 `overspeed_warning.ui` 缺模块 traceback，全文模式见“UI traceback”一节和 `big-screen.log`。本轮没有改脚本、改参数或删外装插件来规避失败。

### 2b. `ui_smoke.py`

结果：**FAIL，rc=1**。X-05 的 `app_zh-CHS.po` 错误已不再出现；完整失败 traceback 为：

```text
Traceback (most recent call last):
  File "/data/xpilot-install-20261022/candidate/tools/sp_tesla_e2e/ui_smoke.py", line 28, in <module>
    assert (gui_app.width,gui_app.height)==(536,240)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
```

也就是说，此提交删除了脚本主动切换 zh-CHS 的旧失败，但在 C3XL 大屏环境中立即遇到硬编码 mici 尺寸断言，未进入后续 smoke 场景。

## 项目 3：全部 `tools/sp_tesla_e2e/*_check.py`

设备目录当时共有 8 个匹配脚本，逐个独立执行并保存完整日志：

| 脚本 | rc | 结果 |
|---|---:|---|
| `external_bridge_check.py` | 0 | PASS |
| `manifest_check.py` | 1 | **FAIL** |
| `offroad_pages_check.py` | 0 | PASS |
| `phase2_check.py` | 0 | PASS |
| `phase3_check.py` | 0 | PASS |
| `plugin_host_check.py` | 1 | **FAIL** |
| `store_check.py` | 0 | PASS |
| `tile_layout_check.py` | 0 | PASS |

`manifest_check.py` 的完整 error：

```text
{
 "plugins": [
  "auto_speed", "traffic_light", "bms", "external_compute", "overspeed_warning",
  "ambient_light", "blindspot_edges", "car_tile", "clock_tile", "lead_card",
  "map_tile", "speed_card", "speed_limit_card", "ip_tile"
 ],
 "errors": [
  "M8 13 manifests but 14 plugin classes"
 ]
}
```

`plugin_host_check.py` 的完整 errors：

```text
{
 "plugins": [
  "auto_speed", "traffic_light", "bms", "external_compute", "overspeed_warning",
  "ambient_light", "blindspot_edges", "car_tile", "clock_tile", "lead_card",
  "map_tile", "speed_card", "speed_limit_card", "ip_tile"
 ],
 "errors": [
  "P9 overspeed_warning ENABLE_PARAM ExtOverspeedWarning not a declared BOOL",
  "P9 overspeed_warning setting ExtOverspeedMargin not in params_keys.h"
 ]
}
```

两个失败和正式 UI traceback 指向同一设备插件状态：`overspeed_warning` 的 class/manifest/参数声明与 UI 模块位置不一致。本任务只报告，不安装、删除、移动或修复该插件。

## 项目 4：正式运行日志和尺寸截图

### 正式服务窗口

项目 3 后重新启动 `comma.service`，等待两个 manager 层和生产 UI，再采集 `comma:0.0` 约 60 秒到 `ui-runtime.log`。窗口结束时服务和三个 PID 仍存活，但有 3 次相同 traceback，因此本项不能判全通过。

完整 traceback 模式如下，每次仅重复这一段：

```text
ui module openpilot.tesla.plugins.overspeed_warning.ui failed to load
Traceback (most recent call last):
  File "/data/openpilot/openpilot/tesla/ui/plugin_ui.py", line 35, in _classes
    mod = importlib.import_module(module_name)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/importlib/__init__.py", line 90, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1310, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1324, in _find_and_load_unlocked
ModuleNotFoundError: No module named 'openpilot.tesla.plugins.overspeed_warning'
```

### 截图方法与边界

设备 DRM 只能由一个 UI 进程独占。正式服务窗口完成后停服，运行 `tile_size_e2e.py`：它使用生产 `BigScreenHost`、生产 tile 类、设备字体与真实 GPU；每个尺寸都通过 `BigScreenHost._on_gesture` 的 long-press、resize tap 和 Done 路径改变，不直接把目标尺寸写进布局 JSON。截图结束后脚本在 `finally` 恢复四项参数，随后又用权威备份做最终恢复并重新启动正式服务。

因此这些是**设备真实 GPU + 生产 UI 类/编辑回调**截图，不是正在运行的 `comma.service` framebuffer 抓取，也不是手指实体触摸证明。

第一次单进程计划抓 27 张，在累计 22 次全屏 GPU 读回后停在 Plugins small 之后不再推进；等待并确认 60 秒无新文件后用 SIGINT 让 Python 经过 `finally`。结构化结果为 `passed=false`、22 cases、四项均 restored。随后用同一个驱动的 `--tiles plugins` 和 `--tiles tesla` 各开一个新进程补齐，两次均 rc=0、`passed=true`、四项 restored。这个验证驱动问题没有被算成产品 traceback或产品通过。

### 27 张截图逐项结论

“过小”按任务的 24 px 下限和实际目视可读性判断。所有截图均为 2160×1080 RGBA 原图。

| Tile | 尺寸 | 截图 | 边缘裁切 | 重叠 | 过小 | 结论 |
|---|---|---|---|---|---|---|
| Clock | small | [tile-clock-small.png](tile-clock-small.png) | **是，右侧最后一个 `8` 被切** | 否 | 否，主值 89 px | **FAIL** |
| Clock | medium | [tile-clock-medium.png](tile-clock-medium.png) | **是，右侧最后一个 `8` 被切** | 否 | 否，主值 197 px | **FAIL** |
| Clock | wide | [tile-clock-wide.png](tile-clock-wide.png) | 否 | 否 | 否，主值 300 px | PASS |
| IP | small | [tile-ip-small.png](tile-ip-small.png) | **是，`192.168.102.113` 的末尾 `3` 被切** | 否 | 否，34 px | **FAIL** |
| IP | medium | [tile-ip-medium.png](tile-ip-medium.png) | **是，`192.168.102.113` 的末尾 `3` 被切** | 否 | 否，75 px | **FAIL** |
| IP | wide | [tile-ip-wide.png](tile-ip-wide.png) | 否，完整 `.113` | 否 | 否，80 px | PASS |
| Map | small | [tile-map-small.png](tile-map-small.png) | 否 | 否 | 否，内容 36 px | PASS |
| Map | medium | [tile-map-medium.png](tile-map-medium.png) | 否 | 否 | 否，内容 72 px | PASS |
| Map | wide | [tile-map-wide.png](tile-map-wide.png) | 否 | 否 | 否，内容 72 px | PASS |
| Car | small | [tile-car-small.png](tile-car-small.png) | 否 | 否 | 否，内容 40 px | PASS |
| Car | medium | [tile-car-medium.png](tile-car-medium.png) | 否 | 否 | 否，内容 80 px | PASS |
| Car | wide | [tile-car-wide.png](tile-car-wide.png) | 否 | 否 | 否，内容 80 px | PASS |
| Speed | small | [tile-speed_card-small.png](tile-speed_card-small.png) | 否 | 否 | 否，副行 36 px | PASS |
| Speed | medium | [tile-speed_card-medium.png](tile-speed_card-medium.png) | 否 | 否 | 否，副行 72 px | PASS |
| Speed | wide | [tile-speed_card-wide.png](tile-speed_card-wide.png) | 否 | 否 | 否，副行 72 px | PASS |
| Lead | small | [tile-lead_card-small.png](tile-lead_card-small.png) | 否 | 否 | 否，副行 36 px | PASS |
| Lead | medium | [tile-lead_card-medium.png](tile-lead_card-medium.png) | 否 | 否 | 否，副行 72 px | PASS |
| Lead | wide | [tile-lead_card-wide.png](tile-lead_card-wide.png) | 否 | 否 | 否，副行 72 px | PASS |
| Battery | small | [tile-bms-small.png](tile-bms-small.png) | 否 | 否 | 否，标题 30 px | PASS |
| Battery | medium | [tile-bms-medium.png](tile-bms-medium.png) | 否 | 否 | 否，标题 45 px | PASS |
| Battery | wide | [tile-bms-wide.png](tile-bms-wide.png) | 否 | 否 | 否，标题 45 px | PASS |
| Plugins | small | [tile-plugins-small.png](tile-plugins-small.png) | 否 | 否 | 否，标题 30 px | PASS |
| Plugins | medium | [tile-plugins-medium.png](tile-plugins-medium.png) | 否 | 否 | 否，内容 72 px | PASS |
| Plugins | wide | [tile-plugins-wide.png](tile-plugins-wide.png) | 否 | 否 | 否，内容 72 px | PASS |
| Tesla | small | [tile-tesla-small.png](tile-tesla-small.png) | 否 | 否 | 否，标题 30 px | PASS |
| Tesla | medium | [tile-tesla-medium.png](tile-tesla-medium.png) | 否 | 否 | 否，标题 45 px | PASS |
| Tesla | wide | [tile-tesla-wide.png](tile-tesla-wide.png) | 否 | 否 | 否，标题 45 px | PASS |

结构化绘制记录最初把四张裁切图误判为 `edge_cut=[]`，因为它使用 `measure_text_ex` 的宽度；真实光栅字形已经碰到 texture 最右列。逐像素复核最右列的 `YMAX`（Graphite 空白背景为 64）为：

| 图 | 最右列 YMAX |
|---|---:|
| Clock small | 235 |
| IP small | 120 |
| Clock medium | 235 |
| IP medium | 235 |
| Clock wide | 64 |
| IP wide | 64 |

其它 21 张的最右列 `YMAX` 都是 64。目视裁剪与这一像素证据一致，所以最终判断以原图/像素证据为准，不以验证驱动的宽度估计为准。

本次状态下没有任何字符串触发 `...`；除 Clock/IP 的实际光栅越界外，也没有需要因高度而丢弃的可见尾行。当前截图不能覆盖所有可能的未来长文本或更多行状态。

## 项目 5：参数恢复

测试前四项都存在。每轮验证驱动的 `finally` 均恢复原值；全部截图后又从只读前保存的权威备份复制回目标路径，启动正式服务，等待 manager/UI 稳定 10 秒，再逐项 `cmp` 和 SHA-256：

| 参数 | 测试前/最终值 | 测试前 SHA-256 | 最终 |
|---|---|---|---|
| `XpilotTileLayout` | 873 bytes | `7d2e2f182f08e9cf92ab14d444b42078cf45f96fafcc693cfa1519149b7f3d46` | 相同 |
| `XpilotTileTheme` | `Graphite` | `1d261a8554d2da69b2e13445a8ee2a94dd10912a2bf5a0f3d3fe0698e5540f84` | 相同 |
| `XpilotBms` | `1` | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` | 相同 |
| `CarPlatformBundle` | Tesla Model Y HW4 2023–25 JSON | `dfcc84df24862d499db2c9a7572af713b81f9592a740eb53b4f393f213722519` | 相同 |

最终读回：

```text
hostname=comma-9c13c9f5
profile=c3xl
offroad=1
engaged=0
service=active
head=bfca6fcec388f019e9b3046e9067f3a11e7d27ff
manager_layers=2
ui_process=present
```

## 证据文件

仓库证据目录：`docs/validation/xpilot-c3xl-20261023-v6/`。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本报告 |
| `build.log`、`build.exit` | 设备 SCons 完整日志和 rc |
| `big-screen-result.json`、`big-screen.log`、`big-screen.exit` | 项目 2a 结构化结果、完整输出和 rc |
| `ui-smoke.log`、`ui-smoke.exit` | 项目 2b 完整输出和 rc |
| `check-exit-codes.tsv`、`checks/*.log` | 项目 3 八项 rc 和逐项完整日志 |
| `ui-runtime.log` | 正式服务约 60 秒 tmux 原始日志 |
| `tile_size_e2e.py` | 可重复的生产 edit/resize/Done + 真实 GPU 截图驱动；仅报告证据，不是产品代码 |
| `tile-size-first.log/result/exit` | 首轮 22 张后停止推进的原始证据，结构化 `passed=false` |
| `tile-size-plugins.log/result/exit` | Plugins 三尺寸补跑，`passed=true` |
| `tile-size-tesla.log/result/exit` | Tesla 三尺寸补跑，`passed=true` |
| 27 张 `tile-*.png` | 9 个指定 tile × small/medium/wide，2160×1080 RGBA 原图；本目录 `.gitattributes` 禁用 PNG LFS filter |

设备原始证据路径：

- `/data/xpilot-install-20261022/xpilot-20261023-v6.bundle`
- `/data/xpilot-ui-check-v6-build.log`、`.exit`
- `/data/xpilot-ui-check-v6-e2e.log`、`.exit`、`/data/xpilot-ui-check-v6/`
- `/data/xpilot-ui-check-v6-ui-smoke.log`、`.exit`
- `/data/xpilot-ui-check-v6-checks.tsv`、`/data/xpilot-ui-check-v6-checks/`
- `/data/xpilot-ui-check-v6-ui-runtime.log`
- `/data/xpilot-ui-check-v6-tile-size-e2e.py`、对应三轮日志/退出码和三个截图目录
- `/data/xpilot-ui-check-v6-param-backup/`

## 未验证边界与风险

- 没有道路、真实 onroad 相机、车道线、告警、控制闭环、vehicle-bus、BMS CAN、实际盲区或 engagement 验证。
- 没有手指实体触摸屏验证；尺寸变更走生产 gesture handler，但由验证脚本调用。
- 截图不是正在运行的 `comma.service` framebuffer；正式服务和真实 GPU 截图分阶段独占 DRM。
- 没有 Panda SPI 独占读回、刷写或 safety 激活证明；正式日志明确存在 device/expected signature mismatch。
- 没有修复任何失败，也没有安装、删除或更改 `overspeed_warning`。本任务没有产品源码改动。
- 任务期间 `origin/xpilot` 后移两个提交；设备和报告有意保持用户指定的 `bfca6fc…`，后来的提交未经本报告验证。

```text
REPORT
task: X-20261023-09
status: FAIL
source_commit: bfca6fcec388f019e9b3046e9067f3a11e7d27ff
device_commit: bfca6fcec388f019e9b3046e9067f3a11e7d27ff
device: comma-9c13c9f5 c3xl 192.168.102.113
offroad: 1
engaged: 0
service: active
build: PASS rc=0
test_2_big_screen_e2e: FAIL rc=1
test_2_ui_smoke: FAIL rc=1
test_3_all_check_scripts: FAIL 6/8
test_4_ui_runtime: FAIL overspeed_warning_module_not_found_x3
test_4_tile_screenshots: FAIL 23/27
clock_small: FAIL right_edge_cut
clock_medium: FAIL right_edge_cut
clock_wide: PASS
ip_small: FAIL right_edge_cut_not_full_192.168.102.113
ip_medium: FAIL right_edge_cut_not_full_192.168.102.113
ip_wide: PASS full_192.168.102.113
other_tile_screenshots: PASS 21/21
params_restore: PASS exact_4_of_4
panda_signature: device_89e7f6a96b68f6a0 expected_34f6597f7fe52f31 mismatch
push: NOT_DONE
END REPORT
```

REPORT X-20261023-09
