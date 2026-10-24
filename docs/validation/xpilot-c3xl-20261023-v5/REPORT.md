# X-20261023-05 C3XL xpilot v5 设备验证记录

## 结论

- 总状态：**PARTIAL / NOT ALL PASS**。目标提交已部署、原生重建并恢复正常服务；测试 3、4 和手动 A–C 通过。测试 1、2 失败；手动 D 的数据状态与 Battery 子项通过，但 Clock/IP 最小 tile 的实屏文字裁切，因此 D 按失败报告。
- 设备：只操作了 `comma@192.168.102.113`；每个写阶段前都要求 `hostname=comma-9c13c9f5`，硬件档案为 `c3xl`，`IsOffroad=1`。没有访问或修改其它设备。
- 设备最终活动提交：`2bd5436a36410018c83baf65de4cdc4aa100a1c4`；`/data/openpilot -> /data/xpilot-install-20261022/candidate`；`comma.service=active`；UI 和两层 manager 均存在。
- 参数最终恢复：`/data/xpilot_plugins/.params/XpilotTileTheme` 缺失；`CarPlatformBundle` 恢复到原始 Tesla Model Y HW4 JSON，SHA-256 `dfcc84df24862d499db2c9a7572af713b81f9592a740eb53b4f393f213722519`；`XpilotBms` 缺失。手动脚本另将布局恢复到运行前 SHA-256 `9cd134605badc8d1e5a5f401b101a86eb336eac7d8b7a0b6fa40bfe29efce30b`。
- 发布状态：**BLOCKED，尚未推送**。本地和远端已经存在同名 `task/X-20261023-05`，HEAD `1cde386b4050586e397d025dcbc13c862dccb3e3`，含 6 个与本报告无关的 UI/E2E 提交；相对当前 `origin/xpilot` 为 6 ahead / 19 behind。不能按要求“从 `origin/xpilot` 建同名分支”而不重写或合并无关历史，因此证据暂存在指定路径的 detached worktree，等待分支名或历史处理指示。

## 版本身份与部署

| 项目 | 结果 |
|---|---|
| 源仓库 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git` |
| `git fetch origin` 后目标 | `origin/xpilot = 2bd5436a36410018c83baf65de4cdc4aa100a1c4`，满足 `2bd5436` |
| 主 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source`，`xpilot@59c1b95a...`；未切换、reset 或 clean |
| 证据 worktree | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/wt/X-20261023-05`，detached `2bd5436a...`，因为请求的分支名已被占用 |
| 设备活动路径 | `/data/openpilot -> /data/xpilot-install-20261022/candidate` |
| 设备更新前 HEAD | `25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191` |
| 设备更新后/最终 HEAD | `2bd5436a36410018c83baf65de4cdc4aa100a1c4` |
| 更新关系 | `25e9eeb...` 是 `2bd5436...` 的祖先；设备执行 `git merge --ff-only 2bd5436...` |
| bundle | `/data/xpilot-install-20261022/xpilot-20261023-v5.bundle` |
| bundle SHA-256 | `29e033fb10c287095487e8d183fc96f8c21232ca205f6d2fb7358c92901f97c5`，主机和设备相同 |
| bundle 内容 | requires `25e9eeb...`；contains `2bd5436... refs/remotes/origin/xpilot`；两端 `git bundle verify` 成功 |

设备 checkout 原有大量 LFS 实体文件显示为 modified，且有未跟踪 `prebuilt`；本轮未 clean、reset、覆盖或提交它们。部署只更新远端跟踪引用并 fast-forward 当前 `xpilot`。

## 安全门与最终运行态

首次上传前、停服/更新前、每轮停服 UI 验证前及最终恢复后均重新读取：

- `hostname=comma-9c13c9f5`；`/data/hardware_profile=c3xl`。
- `/data/params/d/IsOffroad=1`；任何一次若不是 1 都会停止，本轮没有触发停止门。
- 设备活动路径和 HEAD 均与本报告目标一致。
- UI 验证期间 `comma.service=inactive`；验证结束最终为 `active`。
- 没有修改网络、known_hosts 或其它全局设置；SSH 始终使用现有 known_hosts 和 `StrictHostKeyChecking=yes`。
- 没有上路、接合或发送验证 CAN；手动脚本只调用生产 UI 回调。

最终只读检查：

```text
hostname=comma-9c13c9f5
offroad=1
service=active
head=2bd5436a36410018c83baf65de4cdc4aa100a1c4
bms=absent
```

## 重建

服务停止后执行：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p \
  scons -C /data/xpilot-install-20261022/candidate -j4
```

退出码 0，完整日志为设备 `/data/xpilot-ui-check-v5-build.log` 和本目录 `build.log`：

```text
scons: done building targets.
real 208.76
user 719.11
sys 43.70
```

构建确实重新生成 cereal/native 依赖并编译 Panda 目标。唯一真正的 warning 是 CasADi 3.6.7 不在脚本列出的官方支持版本列表；包含 `-Werror` 的编译命令不是错误输出。

### Panda 证据边界

60 秒生产日志和最终 tmux 回读均显示：

```text
Panda 1d002d000a51303436323838 connected, version: DEV-443dd964-DEBUG,
signature 89e7f6a96b68f6a0, expected 34f6597f7fe52f31
```

日志没有 `flashing` 行，本轮也没有显式调用 flash/reset/safety 设置。但设备签名前缀与本次构建 expected **不一致**；因此不能声称 Panda 固件匹配、已刷新或 safety 变更已在 Panda 上激活。任务是 UI 设备验证，本轮没有扩大到停用 pandad 后的 SPI 独占读回或固件刷写。

## 测试 1–4

所有 Python 命令均从 `/data/openpilot` 使用 v3b 第 117 行环境：

```bash
env -C /data/openpilot \
  PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo \
  python3 ...
```

| # | 命令 / 检查 | 退出码 | 结论 |
|---:|---|---:|---|
| 1 | `big_screen_e2e.py --output /data/xpilot-ui-check-v5`，comma 停止 | 1 | **FAIL**：drive 默认/模拟 onroad 缺 `car`、`map` |
| 2 | `ui_smoke.py` | 1 | **FAIL**：缺少已裁掉的 `app_zh-CHS.po` |
| 3 | 8 个 `*_check.py`，严格逐个执行 | 全部 0 | **PASS** |
| 4 | 启动 comma，pipe tmux 60 秒到 `/data/xpilot-ui-check-v5-ui-60s.log` | 0 | **PASS（无 traceback）**；有模型目录网络错误和其它非致命环境提示 |

测试 3 的逐项退出码：

| 脚本 | 退出码 |
|---|---:|
| `external_bridge_check.py` | 0 |
| `manifest_check.py` | 0 |
| `offroad_pages_check.py` | 0 |
| `phase2_check.py` | 0 |
| `phase3_check.py` | 0 |
| `plugin_host_check.py` | 0 |
| `store_check.py` | 0 |
| `tile_layout_check.py` | 0 |

### 测试 1 完整失败信息

`big-screen-result.json` 的五条原始 errors：

```text
drive edit tiles: ['speed_card', 'speed_limit_card', 'lead_card']
default drive tile car: None, expected (7, 1)
default drive tile map: None, expected (0, 2)
onroad data tile car not placed
onroad data tile map not placed
```

完整 traceback：

```text
Traceback (most recent call last):
  File "/data/xpilot-install-20261022/candidate/tools/sp_tesla_e2e/big_screen_e2e.py", line 447, in <module>
    assert result['passed']
           ~~~~~~^^^^^^^^^^
AssertionError
```

这个运行发生在新提交首次启动 manager 之前。随后首次生产启动按 manifest 默认值建立了 `XpilotCarTile=1`、`XpilotMapTile=1`、`XpilotClockTile=1`、`XpilotIpTile=1`；因此本结果准确描述任务规定顺序下的首次停服运行，不能用后来的默认写入倒推成通过。未修改或重跑仓库原样脚本来掩盖失败。

### 测试 2 完整 traceback

```text
Traceback (most recent call last):
  File "/data/xpilot-install-20261022/candidate/tools/sp_tesla_e2e/ui_smoke.py", line 30, in <module>
    gui_app.init_window('Tesla migration mici E2E',fps=30)
  File "/data/openpilot/openpilot/system/ui/lib/application.py", line 363, in init_window
    self._load_fonts()
  File "/data/openpilot/openpilot/system/ui/lib/application.py", line 774, in _load_fonts
    self.fallback_font()
  File "/data/openpilot/openpilot/system/ui/lib/application.py", line 735, in fallback_font
    chars.update(TRANSLATIONS_DIR.joinpath(f"app_{language}.po").read_text(encoding="utf-8"))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/pathlib.py", line 1029, in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/pathlib.py", line 1015, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/data/openpilot/openpilot/selfdrive/ui/translations/app_zh-CHS.po'
```

### 测试 4 日志

`ui-60s.log` 共 92 行，没有 `Traceback`、进程退出或 fatal。非致命问题包括：

- Cursor/Windsurf 符号链接已存在；`No IRQs found for 'fts_ts'`；raylib 色彩校正失败和字体 codepoint 数不足。
- `raw.githubusercontent.com` 一次 10 秒超时、一次 `Network is unreachable`，随后使用 expired cache。
- 上述 Panda signature/expected 不一致。

## 手动 A–D

`manual_e2e.py` 是设备外部、真实 GPU 的验证驱动；调用生产 page/switch/model/ADD callbacks，不修改产品源码，不发送 CAN。最终运行退出 0，`manual-result.json` 为 `passed=true`、`errors=[]`，并逐字节证明 theme、layout、CarPlatformBundle、XpilotBms 全部恢复。

| 项目 | 结论 | 证据 |
|---|---|---|
| A Plugin market | **PASS** | 5 个实际有内容的 manifest 类别各有左栏按钮，底部 Refresh 控件存在；13 个已加载插件行均为 `vX - author - description` 且带 switch；Battery 行生产回调进入详情页；Version/Author/Category 及滚动后的 Claims/Priority 可见；BACK 返回相同第 2 类别 |
| B Tile color | **PASS** | 生产 callback 选 Crimson；Toggles 滚动图显示选中；返回磁贴页后 16 个已放置 tile 全部为 RGB `(162,0,37)`；原 theme 缺失已恢复 |
| C Car model | **PASS** | 列表精确为 Auto + 6 个 Tesla 型号；选择 `Tesla Model 3 (with HW2.5) 2019` 后 JSON `name` 相同、自动返回且 row 显示；选 Auto 后参数删除；最后恢复原 Model Y HW4 JSON |
| D Clock/IP/Battery | **FAIL（Battery 子项 PASS）** | Clock state=`08:35`, `Fri 23 Oct`；IP state=`192.168.102.113`, `none`；Battery 默认关闭、开关打开、用 ADD callback 加入且 offroad state=None、画面 `--`。但小尺寸实图中 Clock 右缘被裁，IP 只显示 `192.168.102.`，没有完整满足可视显示要求 |

插件页没有显示“需要重启”提示，因此没有为开关单独重启 UI；停服验证进程重新创建 host 后 Battery 已出现。最终 `XpilotBms` 恢复为缺失。首次最终启动期间 manager 一次将其按默认值重建为 `0`；待 manager 稳定后再次删除，8 秒复核仍缺失。

### 手动验证驱动失败尝试及完整 tracebacks

为保留验证驱动自身问题，不把它们误归为产品 traceback：

1. 首次 manager 启动前和首次启动后的满布局尝试都在 Clock/IP 放置断言停止；两次 finally 均证明四处状态恢复。完整 traceback 相同：

```text
Traceback (most recent call last):
  File "/data/xpilot-ui-check-v5-manual-e2e.py", line 236, in <module>
    for _ in gui_app.render():
  File "/data/openpilot/openpilot/system/ui/lib/application.py", line 697, in render
    self._host.render()
  File "/data/xpilot-ui-check-v5-manual-e2e.py", line 231, in render
    next_step = frame + next(scenario)
                        ^^^^^^^^^^^^^^
  File "/data/xpilot-ui-check-v5-manual-e2e.py", line 104, in steps
    assert "clock" in placed and "ip" in placed
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
```

根因分别是首次启动前新默认 param 尚未建立，以及当前布局中 Clock=medium、IP=wide 加固定位置后不能落位。最终驱动使用产品 `BigScreenHost._pin`（ADD 按钮实际 callback）把它们临时以 small 加入，并在结束时恢复完整布局 SHA。

2. 第一次 ADD 驱动直接读 IP state 时传错 SubMaster；这是验证驱动错误，生产 `_face` 对该 tile 使用 `ui_state.sm`。完整 traceback：

```text
Traceback (most recent call last):
  File "/data/xpilot-ui-check-v5-manual-e2e.py", line 240, in <module>
    for _ in gui_app.render():
  File "/data/openpilot/openpilot/system/ui/lib/application.py", line 697, in render
    self._host.render()
  File "/data/xpilot-ui-check-v5-manual-e2e.py", line 235, in render
    next_step = frame + next(scenario)
                        ^^^^^^^^^^^^^^
  File "/data/xpilot-ui-check-v5-manual-e2e.py", line 109, in steps
    ip_state = host._entries["ip"].tile.state(host._sm)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/data/openpilot/openpilot/tesla/plugins/ip_tile/ui.py", line 22, in state
    return ip_address(), str(sm["deviceState"].networkType).replace("NetworkType.", "")
                             ~~^^^^^^^^^^^^^^^
  File "/data/openpilot/openpilot/cereal/messaging/__init__.py", line 230, in __getitem__
    return self.data[s]
           ~~~~~~~~~^^^
KeyError: 'deviceState'
```

修正验证驱动后最终运行通过。以上失败均发生在 comma 停止、offroad 状态，没有产品服务 traceback；每次 finally 都恢复参数和布局。

## 截图逐张目视结论

| 文件 | 目视结论 |
|---|---|
| `plugins-market.png` | 左栏 5 类和底部 Refresh 控件位置存在；抓图时后台首次 fetch 正处于 `working...`。右栏开关和版本/作者/描述清楚 |
| `plugins-category.png` | 第 2 类 Data Sources & External Compute 被选中；Battery 与 External Compute 行均有 switch 和摘要 |
| `plugins-plugin-page.png` | Battery 详情页顶部、switch、描述、Version、Author、Category 可见 |
| `plugins-plugin-page-details.png` | 同一详情页滚动后 Claims=`none`、Priority=`100` 可见 |
| `plugins-back-same-category.png` | BACK 后仍停在第 2 类；与进入前类别图像 SHA 相同 |
| `tile-color-selected.png` | Toggles 底部 Tile color 行中 Crimson 绿色选中 |
| `tile-color-all-tiles.png` | 返回后屏上所有 tile 都使用 Crimson，没有混色 |
| `car-model-list.png` | Auto 和列表上半部；按钮均在内容区内 |
| `car-model-list-bottom.png` | 列表下半部补齐 Model X、两款 Model Y；原 Model Y HW4 显示 SELECTED |
| `car-model-selected.png` | 返回 Tesla 页后 Car model 行显示选择的 Model 3 HW2.5 2019 |
| `car-model-auto.png` | Auto 后 Car model 行显示 Auto |
| `new-tiles-clock-ip.png` | Clock/IP 已通过 ADD callback 落位；Clock 和完整 IP 的内部 state 正确，但 small tile 文本右侧裁切 |
| `battery-plugin-enabled.png` | Battery 插件页 switch 为开；页面未显示 restart 提示 |
| `new-tiles-battery.png` | Battery tile 明确显示 `--`；Clock/IP 同图仍有上述裁切 |

所有截图均为 2160×1080 RGBA 原图，无重编码。截图仅是停服真实 GPU 合成，不是道路/相机/车辆闭环证据。

## 证据文件与设备路径

仓库证据目录：`docs/validation/xpilot-c3xl-20261023-v5/`。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本报告 |
| `big-screen-result.json`、`big-screen.log` | 测试 1 原生结果和完整日志 |
| `ui-smoke.log` | 测试 2 完整输出和 traceback |
| `check-exit-codes.tsv`、`checks/*.log` | 测试 3 八项退出码和逐项日志 |
| `ui-60s.log` | 测试 4 的 60 秒 tmux UI 日志 |
| `build.log` | 设备原生 SCons 完整日志 |
| `manual_e2e.py`、`manual-result.json`、`manual-e2e.log` | 可重复手动 A–D 驱动、结构化结果和最终日志 |
| 14 张 PNG | A–D 原始截图；`.gitattributes` 禁用该目录 PNG 的 LFS filter |

设备原始证据：

- `/data/xpilot-install-20261022/xpilot-20261023-v5.bundle`
- `/data/xpilot-ui-check-v5-build.log`
- `/data/xpilot-ui-check-v5-e2e.log`、`/data/xpilot-ui-check-v5-e2e.exit`
- `/data/xpilot-ui-check-v5/`
- `/data/xpilot-ui-check-v5-ui-smoke.log`、`/data/xpilot-ui-check-v5-ui-smoke.exit`
- `/data/xpilot-ui-check-v5-checks.tsv`、`/data/xpilot-ui-check-v5-checks/`
- `/data/xpilot-ui-check-v5-ui-60s.log`
- `/data/xpilot-ui-check-v5-manual-e2e.py`、`.log`、`.exit`
- `/data/xpilot-ui-check-v5-manual/`

## 回滚

更新前提交 `25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191` 是当前目标祖先，仍保留在同一仓库及增量 bundle 的 prerequisite 中。若回滚，必须重新通过 hostname/C3XL/offroad 门、停服，在同一 candidate 回到该提交，重新运行 SCons，再启动并验证活动 HEAD 和运行态。当前没有执行回滚，因为目标服务能启动且任务要求保留 `2bd5436` 供后续修复测试失败和 UI 裁切。

Panda signature 与 expected 不一致，不应把仅回退 openpilot checkout 当作固件一致性证明；在任何固件动作前需另做独占、安全、版本和回读门。

## 未验证边界

- 没有道路、真实 onroad 相机、车道线、告警、控制闭环、实际盲区或 engagement 验证。
- 没有手指触摸实体屏幕；使用真实 GPU 与生产 callbacks/scroll state。没有 Refresh 商店、安装、更新、删除或网络设置动作。
- 没有真实 BMS CAN 数据和 vehicle-bus 线束验证；Battery 只验证 offroad 无数据时的 `--`。
- 没有 Panda SPI 独占读回、刷写或 safety 激活证明；当前运行日志明确存在 signature mismatch。
- 测试 1、2 没有修复或改写；D 的 Clock/IP 裁切也只记录不修复。
- 请求的报告分支名冲突，未 force-push、未重置或合并无关历史；远端尚未收到本报告。

```text
REPORT
task: X-20261023-05
status: PARTIAL
source_commit: 2bd5436a36410018c83baf65de4cdc4aa100a1c4
device_commit: 2bd5436a36410018c83baf65de4cdc4aa100a1c4
device: comma-9c13c9f5 c3xl 192.168.102.113
offroad: 1
service: active
build: PASS rc=0
test_1_big_screen_e2e: FAIL rc=1
test_2_ui_smoke: FAIL rc=1
test_3_all_check_scripts: PASS 8/8 rc=0
test_4_ui_60s: PASS no_traceback
manual_A_plugins_market: PASS
manual_B_tile_color: PASS restored_absent
manual_C_car_model: PASS restored_original_json
manual_D_new_tiles: FAIL clock_ip_text_clipped battery_pass restored_bms_absent
panda_signature: device_89e7f6a96b68f6a0 expected_34f6597f7fe52f31 mismatch
docs_branch: BLOCKED existing_unrelated_task/X-20261023-05
push: NOT_DONE
END REPORT
```
