# X-20261023-05 C3XL xpilot UI v4 部署与停车验证记录

## 结论

- 状态：**DONE**。收到协调者 `DEPLOY 3e0b8ba896e876166b86639881f7ead288c846dd` 后，设备由 `7ee2e996515f9648be81dc3ce12d5551ead7ba05` fast-forward 到指定提交，完成原生构建、Panda 只读门、60 秒生产日志、30 秒性能采样、仓库原样 E2E 和服务恢复。
- 设备：C3XL `comma-9c13c9f5`，本次通过 `comma@192.168.102.113` 连接。首次写入前已精确回读 hostname、硬件档案、活动目录和实时安全状态。
- 最终活动提交仍为 **`3e0b8ba896e876166b86639881f7ead288c846dd`**；`comma.service=active`，两层 manager 存在，`ui`、`pandad`、`hardwared` 全部 `running=true, exitCode=0`。文档提交不代表设备随后运行了文档提交。
- 最终 `IsOffroad=1`、`IsEngaged=0`、`deviceState.started=false`；15 秒内取得 **151** 个 Panda 样本，全部 `controlsAllowed=false`、`faultStatus=none`、类型 Tres。
- 仓库原样 E2E：**`passed=true, errors=[]`**；22 张原始 2160×1080 PNG 已保留并逐张查看。Small models 子页因没有 qcom bundles 按脚本规则 skipped，因此没有该子页 PNG。
- 60 帧空闲磁贴屏重画次数为 **0**。全部设置详情页、Models、Store 和 Device 四个子页都使用原生页面，offroad 的 mici 绘制计数为 0。真实映射触摸验证了 Back、长按、改尺寸、Add tiles、Drive、Done 和 20 次 move 的拖动。
- 正常生产 UI 的 30 秒窗口：**23.2266% CPU，frame avg/p95 = 17.1649 / 17.1926 ms**；v3b 为 33.0662%、17.2723 / 17.2809 ms。比较条件和按需消息的限制见性能节。
- Panda 构建和设备版本均为 `DEV-443dd964-DEBUG`，签名匹配，固件 SHA-256 未变。没有刷写 Panda，没有调用 reset、safety 设置或验证用 CAN 发送接口。
- 本轮没有修改产品源码。Git 变更只在本目录。原有 **287** 个 dirty 文件的内容哈希完全未变，`prebuilt` 未清理，受保护参数前后相同。
- **布局并发说明**：部署前 `XpilotTileLayout` 不存在，最终存在。用户在本轮确认“我触摸了几次”。E2E 自身恢复到编辑步骤前的文件字节和两套内存布局均通过，但不能把整轮外部文件变化归因于 E2E。确认手动交互后，保留用户当前布局，不再覆盖。完整时序见下文。

## 版本身份与同步

| 项目 | 结果 |
|---|---|
| 远端 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git`，`xpilot` |
| 协调者批准及 fetch 核对的目标 | `3e0b8ba896e876166b86639881f7ead288c846dd` |
| 主机验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source`，`xpilot`；本轮从 `343b4d0f80741aa6afd56f2f042a01e21001e2b2` ff 到部署目标 |
| phase A 任务分支 | `task/X-20261023-05`；fix 2 已发布 `1cde386b4050586e397d025dcbc13c862dccb3e3`，本轮未把该分支当作部署身份 |
| 设备路径 | `/data/openpilot -> /data/xpilot-install-20261022/candidate` |
| 更新前 / 最终设备 HEAD | `7ee2e996515f9648be81dc3ce12d5551ead7ba05` / `3e0b8ba896e876166b86639881f7ead288c846dd` |
| 增量 bundle | `/data/xpilot-install-20261022/xpilot-20261023-v4.bundle` |
| bundle SHA-256 | `09c2d40265b43b11427b2898c5c8caab1cafc967bc14483bd60bf7c630b3b4de`，主机、设备相同 |
| bundle 范围 | prerequisite `7ee2e996...`，head `3e0b8ba896... refs/remotes/origin/xpilot`；两端 `git bundle verify` 通过 |
| 设备更新方式 | 只从 bundle 更新设备 `origin/xpilot`，再 `merge --ff-only` 到指定目标；未强制推送 |
| Panda / safety 差异 | `git diff --stat 7ee2e99..3e0b8ba896 -- panda/ opendbc_repo/opendbc/safety/` 输出为空；证据 `panda-safety.diffstat` 为 0 bytes |
| E2E 脚本 SHA-256 | `e5075a49325a550a5544694f6e1c210baa1097bfc50d5016d261028b4b74136d`，主机、设备一致 |
| 回退引用 | 设备 `xpilot-ui-v4-before-20261023` 指向更新前 `7ee2e996...` |

主工作树 `/Users/mile/Desktop/mo-op` 没有切换、清理或覆盖。本轮更新的产品文件与设备原有 dirty 文件没有交集，更新前逐文件记录内容哈希，最终 287 个文件全部相同。

## 安全门与数据保留

写入前、停服更新前、E2E 停服前、E2E 后和最终恢复后都核对停车安全状态。初始实时采样取得 51 个 Panda 样本，最终 151 个样本均无 fault、未允许控制。底层 SPI 读取还确认 `ignition_line=false, ignition_can=false, safety_mode=0`。

`before.json`、`after-e2e.json` 和 `final-preservation.json` 记录了以下参数的存在性和 SHA-256：`DoReboot`、`DoShutdown`、`DoUninstall`、`HasAcceptedTerms`、`HasAcceptedTermsSP`、`CompletedTrainingVersion`、`IsDriverViewEnabled`、`CalibrationParams`、`LiveTorqueParameters`、`LiveParametersV2`、`LiveDelay`。最终全部与初始值相同：

- `DoReboot`、`DoShutdown`、`DoUninstall` 始终不存在；没有自动化确认 reboot、power off、reset 或 uninstall 对话框。E2E 每帧还检查没有意外 modal。
- Terms / training 版本分别为 `2`、`1.0`、`0.2.0`，没有接受条款或完成训练的写入。
- Driver camera Back 后 `IsDriverViewEnabled=false`，最终仍为原值 `0`。
- 上述四项校准/车辆参数原本不存在，最终仍不存在。

全程没有实际进入 onroad、没有 engagement、没有清除车辆/插件数据，也没有连接、忘记或修改 Wi-Fi/网络。E2E 的 `ui_state.started=True` 只在独立 UI 进程内用于合成检查，没有改写 `IsOffroad` 或车辆状态。

### 布局文件与用户触屏时序

| 时点 | 文件状态 / 处理 |
|---|---|
| 首次外部快照 | `/data/xpilot_plugins/.params/XpilotTileLayout` 不存在 |
| E2E 内部 | 编辑前备份文件字节及两套布局；结果 `file_matches=true, layouts_match=true` |
| E2E 后外部快照 | 文件存在，732 bytes，SHA-256 `11a4122b191393b0fe21fa981560838f49b500886c23a55d4977c9ea1caf790e`；Developer 为 medium；完整内容保留为 `XpilotTileLayout.after-e2e` |
| 尚未得知用户触屏时 | 按原始恢复指令，先保存文件，停车停服后仅删除该布局文件以恢复原先的不存在状态，再启动服务；过程见 `layout-restoration.json` |
| 再次检查 | 文件再次出现，Status/Toggles 尺寸发生变化；因此没有把第一次删除当作最终恢复完成 |
| 用户澄清 | 用户明确回答“我触摸了几次”；这一并发交互会改变生产宿主的布局，无法用外部前后快照单独归因给脚本 |
| 最终保留 | 保留用户当前布局，729 bytes，SHA-256 `bbfa8eb72310ee2e77e8322de689f69e969fbdb599f69695ce6600b0c3749034`；副本为 `XpilotTileLayout.user-final` |

因此本轮只确认 **E2E 编辑范围内**的恢复通过，以及其它受保护参数没有变化；不声称整轮布局文件保持不变，也不把用户手动调整撤销到部署前。屏幕触摸发生的完整时序没有记录，不能进一步区分每次文件写入的来源。

## 构建与 Panda 禁止刷写门

设备停服后执行原生构建：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

退出码 0，完整日志为 `build.log`，设备原件 `/data/xpilot-ui-check-v4-build.log`。结尾：

```text
scons: done building targets.
real 12.76
user 11.07
sys 1.76
```

构建日志没有 warning/error。

本次没有直接实例化普通 `Panda()`：源码检查表明其 `connect()` 会设置心跳、power save、CAN-FD、CAN 速率，并 reset communications，不符合本轮严格只读门。实际通过 `PandaSpiHandle.get_info()` 和 `controlRead` 读取，跳过 `Panda.__init__/connect`，仅复用已有版本、签名和 health 解码方法。构建前、构建后都读取了真实 Panda：

| 项目 | 结果 |
|---|---|
| serial / raw type | `1d002d000a51303436323838` / `09`，Tres，应用态、非 bootstub |
| 构建 / 设备版本 | 均为 `DEV-443dd964-DEBUG` |
| 签名 | 设备与构建完全相同，前缀 `89e7f6a96b68f6a0`；完整签名见 `panda-pre.json` |
| 固件 SHA-256 | `656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`，与 v3b 相同 |
| health | `controls_allowed=false, faults=0, fault_status=0, spi_error_count=0` |

版本和签名一致，因此没有进入任何刷写路径。生产日志随后也打印设备签名与 expected 相同，并成功通过 SPI 连接。

## 正常服务、60 秒 UI 日志与最终恢复

`tmux pipe-pane` 捕获了 **60.000946 秒**生产日志，原件 `/data/xpilot-ui-check-v4-ui-60s.log`，副本 `ui-60s.log`。另外保留 `production-startup.log`。该窗口没有 traceback、UI 退出或低 FPS 提示。默认停车交互超时为 30 秒，因此这个 60 秒日志窗口包含息屏阶段，不作为 60 秒持续渲染证明。

以下环境/启动信息按实际日志保留，本轮没有为消除它们而改配置：

```text
tee: /sys/devices/system/cpu/cpufreq/policy4/scaling_max_freq: Invalid argument
ln: failed to create symbolic link '/home/comma/.cursor-server/vscode-server': File exists
ln: failed to create symbolic link '/home/comma/.windsurf-server/vscode-server': File exists
/data/openpilot has been modified, skipping overlay update installation
No IRQs found for 'fts_ts'
raylib: COMMA: Failed to initialize color correction
raylib: FONT: Requested codepoints glyphs found: [117/122]
raylib: FONT: Requested codepoints glyphs found: [107/122]
openpilot/selfdrive/pandad/usb.cc: failed to connect to panda over USB: Success
openpilot/selfdrive/pandad/panda.cc: connected to 1d002d000a51303436323838 over SPI
```

USB 尝试失败之后确实通过 SPI 连上，并非 Panda 未连接。本轮 60 秒窗口没有复现 v3b 的模型网络超时、`No WiFi device found` 或 GitHub host authenticity 提示，不能据此判断它们已永久修复。

E2E 使用退出清理确保失败也恢复服务。最终 runtime check 记录 `ui` PID 161246、`pandad` PID 161262、`hardwared` PID 161266，三者均运行且退出码为 0；设备 HEAD 和活动路径正确。最终 JSON 的 alive/valid 均为 true，但 `uiDebug` 是 0 Hz 按需服务，不能只用其 alive/valid 代替实际帧计数。

## 30 秒 UI CPU 与帧时间

方法沿用 v3b：正常 comma 服务、停车时，对 manager 报告的 UI PID 读取 `/proc/<pid>/stat` 的 utime+stime，以 `SC_CLK_TCK=100` 和单调时钟计算一个逻辑核基准的进程 CPU；同时采集 `uiDebug.frameTimeMillis/cpuTimeMillis`。采样期间持续检查未 started、未 engaged、Panda 未允许控制且无 fault，并检查 UI PID / 启动标识不变。

| 指标 | v3b | 本轮 v4 |
|---|---:|---:|
| 时长 | 30.000381 s | 30.008655 s |
| 帧样本 | 1737 | 1745 |
| UI 进程 CPU | 33.0662% | **23.2266%** |
| frame avg / median | 17.2723 / 17.2721 ms | **17.1649 / 17.1616 ms** |
| frame p95 / p99 / max | 17.2809 / 17.2908 / 17.3393 ms | **17.1926 / 17.2131 / 17.2294 ms** |
| frame CPU avg / p95 / max | 1.5428 / 1.9408 / 2.3606 ms | 1.5217 / 1.8777 / 5.1765 ms |
| >20 / >33.3 / >100 ms | 0 / 0 / 0 | 0 / 0 / 0 |

本窗口 CPU 比 v3b 少 9.8396 个百分点（相对少 29.76%），frame avg 少 0.10735 ms。frame CPU max 由 2.36 升到 5.18 ms，但整帧最大仍为 17.23 ms。进程 CPU 和 uiDebug 的 CPU 段定义不同，不混为同一指标。

首次采样在默认停车息屏之后运行，没有产生有效帧结果，停在 `perf.py:47` 的断言。随后 5 秒只读诊断观测到 uiDebug 更新数为 0；`py-spy` 显示主线程在 `application.py:652` 的不渲染休眠分支，而非崩溃。失败日志、当时方法和栈分别保留为 `perf-attempt1.log`、`perf-attempt1-method.txt`、`ui-asleep-stack.txt`。

有效窗口通过现有 Samsung Touchscreen 的短 press/release 维持亮屏：原始坐标 `(10,10)`，每次 50 ms，相对采样起点为 -0.549、10.058、20.059 秒。读取并核对过触摸设备范围，未改 Params、超时、网络或 CPU 配置；之后只读检查 10 个 MT slot 均为 -1、BTN_TOUCH=false。用户也确认本轮有手动触屏，完整触屏时序未记录，所以这里是**两个观测窗口的比较，不能当作无人干预的受控 A/B 因果结果**。

原始 1745 行样本在 `perf-samples.json`，CPU ticks 增量 697，Panda 样本 301。`uiDebug_valid_samples=0`：实际收到的消息 valid 标志为 false，数值按与 v3b 相同字段计算，未把这个标志改为 true。按需服务的默认 alive/valid 和实际收到的消息标志须分别理解。

复现方法保留在 `perf-method.txt`，设备可执行副本为 `/data/xpilot-ui-check-v4-evidence/perf.py`，在相同停车安全门后运行：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 /data/xpilot-ui-check-v4-evidence/perf.py
```

## 大屏 E2E

服务停止后执行目标提交中的原样脚本：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v4
```

退出码 0。`result.json` 原样保留：`passed=true, head=3e0b8ba896..., errors=[]`。

- offroad 九个设置磁贴全部放置；首屏和所有原生详情页都不画 mici，60 帧空闲的 tile face 重画计数为 0。
- 九个详情页 title / PAGE 类型正确；应用导航栈深度为 1。Store 子页深度 2，真实 Back 返回同一个 Plugins 页面。
- Models 是 `ModelsPage`，不再使用 fallback。qcom bundles 为空，Small models 分支记录 `skipped=true, reason="no qcom bundles available"`，没有调用会弹提示的 `_choose`。
- Device 通过真实 row callback 打开 `TrainingGuidePage`、`DriverCameraPage`、`TermsPage`、`RegulatoryPage`；子栈为 2，Back 返回 Device 为 1。训练只看第一步，不按 next/finish；camera Back 清掉 driver view。
- onboarding 只新建独立 `OnboardingPage(on_done=lambda: None)`，清空输入后绘制一次；没有推入实际 onboarding window，也没有点击条款按钮。
- Toggles 长按进入编辑，medium → small；真实点击 resize / + / Back / Drive / Done；点选中磁贴和非 add 空格只取消选中，Done 退出并返回 park。
- 默认 drive 顺序为 speed_card、speed_limit_card、lead_card、car、map，对应 `(0,0),(7,0),(0,1),(7,1),(0,2)`。speed_card 经 20 次 move 拖至 `(7,3)`，保存的 fixed 位置及模拟 onroad 的放置位置一致。
- 模拟 onroad viewport 为 `(300,59,1560,699)`；五张数据磁贴齐全，没有设置磁贴，没有磁贴压到 VIEW / blocked cells。强制左右盲区 overlay 成功绘制两次，无异常。

E2E 日志没有 traceback，但打印了 `FPS dropped below 60: 6, 6, 8, 5, 9, 9, 9`。截图、页面创建等发生在独立 E2E 窗口，不能与前面的正常生产稳态性能窗口混用。

## 截图逐张目视结论

全部 22 张均已查看。原始图保留在设备和主机外部证据目录；只有 Regulatory 的仓库副本缩为 1600×800，其余仍为 2160×1080。仓库全部 PNG 严格小于 400,000 bytes；原件/副本尺寸、大小及 SHA-256 逐张列于 `artifacts.json`。

| PNG | 目视结论 |
|---|---|
| `start.png` | 磁贴间距、标题、图标清楚，九个设置磁贴和五个数据磁贴可见。small Map 的 `No map data`、small Car 的 `0 km/h` / `U --` 当前都没有横向裁切；没有真实地图长路名/较长车辆数据，不能推广到这些内容。Developer 此时为 medium，因此不是全新默认布局的截图。 |
| `edit.png` | Toggles 被选中放大、其它磁贴变暗、两个角钮和 + 可见。底部 Park/Drive/Done 覆盖第 3 行的部分磁贴标题，见问题 1。 |
| `edit-resized.png` | Toggles 已变 small，角钮仍在磁贴内；其它磁贴重新排布。编辑栏仍压在第 3 行内容/标题之上。 |
| `add-tiles.png` | WP 标题、XPILOT 上级名、线画 Back 清楚，内容为 `No tiles to add`，不是未渲染的空页。 |
| `edit-drive.png` | 只有五张数据磁贴，左右交替；中间灰色 `Driving view` 占位完整居中，边界与 drive VIEW 一致。 |
| `edit-drive-moved.png` | Speed 在右下 `(7,3)`，其它数据磁贴自动补位；灰色占位无磁贴覆盖。当前编辑栏在中间空处，但将来在中间底行放磁贴仍有遮挡风险。 |
| `onroad-blindspot.png` | 五张磁贴位于两侧，强制红色渐变覆盖两边，字仍能辨认但对比度下降。中央是保留的 mici Home / 版本纹理，并非相机或实际道路画面。 |
| `onboarding.png` | terms of service、正文、二维码和两个按钮完整，没有明显溢出；仅无输入渲染。红色 `decline & uninstall` 是按钮文字，没有执行该动作或打开实际卸载流程。 |
| `page-status.png` | WP 页头、版本、分支、提交和 Network 行清楚；停服 E2E 的数据为 Network none，不代表设备网络被修改。 |
| `page-toggles.png` | 标题、开关、行间距清楚，无明显横向溢出。没有在此切换设置。 |
| `page-plugins.png` | Store OPEN、插件开关和 Speed Limit Offset 可读，值为单一 `0 km/h`，v3b 的 `km/h\|mph` 拼接问题本图未复现。 |
| `page-plugins-store.png` | 上级 PLUGINS / 标题 store 清楚，Refresh 行可读，Back 无缺字；未执行 Refresh 或安装动作。 |
| `page-tesla.png` | Off、3-Finger、4-Finger、5-Finger 横向均可见，未复现 v3b 的右侧横向溢出；MADS 所在行在内容区底边被纵向裁开，需要滚动。 |
| `page-models.png` | 原生模型名和 SELECT / REFRESH 按钮位于内容区内，不再有 3 倍 fallback 的横向裁切。Small models 的列表子页本轮 skipped，没有对应图片。 |
| `page-network.png` | 当前 SSID、连接勾号、Wi-Fi 图标、Forget、Advanced 都可见；未连接、忘记或修改网络。 |
| `page-device.png` | 设备 ID、Serial 和 Review / Preview / Terms 行清楚，WP 页头无重叠。 |
| `page-device-training-guide.png` | DEVICE / training guide、首步四条责任说明及 next 按钮完整；标题里的 `?` 是原文问号，不是缺 glyph 替代。没有点击 next。 |
| `page-device-driver-camera.png` | DEVICE / driver camera 页头正确，主体只显示 `camera starting`，没有实际摄像头图像；只证明页面及返回生命周期。 |
| `page-device-terms.png` | DEVICE / terms、网址和二维码完整，无接受/拒绝按钮，符合 review 页面。 |
| `page-device-regulatory.png` | FCC 标识与文字可读，长文底部进入滚动范围。正文明确显示 `HVIN: comma four`，与本次 C3XL 身份不同。仓库缩图后也已目视复核。 |
| `page-software.png` | 版本、分支、目标分支、检查更新及卸载行完整可读；没有执行按钮。 |
| `page-developer.png` | ADB、SSH、SSH keys、Joystick 和下方行清楚，无横向文字溢出；没有修改。 |

各 WP 详情页的 Back 都是线画圆钮/箭头，父级名与小写标题分层清楚，没有 v3b 的 `? Back` / `Plugins ? Store`。字体仍报告缺少部分 codepoints，但本轮截图未见由缺字替换产生的 `?`。

## 编号问题表

下表包含实际 UI 问题、环境信息和验证边界；不把它们全部当作 v4 新回归。本轮按任务只记录，不修源码。

| # | 分类 | 实际症状 / 影响 | 证据与状态 |
|---:|---|---|---|
| 1 | 编辑栏遮挡 | Park/Drive/Done 位于 y=988..1064，网格第 3 行到 y=1058；编辑栏盖住该行部分磁贴内容/标题。 | `edit.png`、`edit-resized.png`；功能点击通过，视觉遮挡未修复。 |
| 2 | 列表首屏裁行 | Tesla 的 MADS Screen Activation 行在屏幕底部被纵向裁开，需要滚动；横向四个选项本轮都可见。 | `page-tesla.png`；与 v3b 横向溢出分开记录。 |
| 3 | Regulatory 硬件文案 | C3XL 上显示 `HVIN: comma four` 及对应 FCC 文案。 | `page-device-regulatory.png`；原生渲染成功，硬件文案未适配。 |
| 4 | 相机覆盖边界 | Driver camera 主体只有 `camera starting`，没有图像。 | `page-device-driver-camera.png`；Back 清 driver view 通过，实际预览未证明。 |
| 5 | 模型列表覆盖边界 | Small models 因 `no qcom bundles available` skipped，未生成子页 PNG。 | `result.json`；符合约定跳过条件，不宣称列表已验证。 |
| 6 | E2E 长帧提示 | 独立截图运行出现 FPS 6、6、8、5、9、9、9。 | `e2e.log`；正常生产 30 秒窗口无 >20 ms 样本，两窗口不混用。 |
| 7 | 运行环境 | 生产启动有 scaling_max_freq Invalid argument、现存符号链接、fts_ts IRQ、色彩校正和缺 glyph 提示；USB 尝试失败后 SPI 成功。 | `ui-60s.log`、`production-startup.log`；没有因此修改系统/网络/固件配置。 |
| 8 | 按需遥测标志 | 有效性能窗口 1745 条 uiDebug 的 valid 均为 false；最终 runtime 的该服务 alive/valid 又可默认为 true。 | `perf.json`、`perf-samples.json`、`final-runtime.json`；实际样本数和消息标志单独报告。 |
| 9 | 并发触屏与布局归因 | 外部布局由不存在变为存在、随后尺寸再变化；用户确认曾手动触屏。脚本恢复通过不能证明整轮外部字节不变。 | `before.json`、`after-e2e.json`、`layout-restoration.json`、`XpilotTileLayout.user-final`；确认后保留当前用户布局，不再撤销。 |
| 10 | 首次性能驱动 | 首轮在停车息屏后运行，`perf.py:47` 的样本/PID 断言失败，没有 perf.json。只读栈确认休眠，随后维持亮屏重测成功。 | `perf-attempt1.log`、`ui-asleep-stack.txt`、`perf-method.txt`；失败证据保留，成功窗口条件已披露。 |

外围检查也曾遇到 `systemctl is-active` 对 inactive 返回退出码 3、受保护目录的 find Permission denied，以及主机默认 Python 无 PIL；分别改用保留退出状态的读取、已知证据路径和 macOS AppKit / sips。它们没有触发产品修复、依赖安装或硬件设置变更。

## 证据

仓库目录：`docs/validation/xpilot-c3xl-20261023-v4/`。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本记录 |
| `result.json`、`e2e.log`、`e2e-exit-code.txt` | 原样 E2E 结果、完整日志及退出码 |
| 22 张 PNG、`artifacts.json` | 每张截图及原件/仓库副本的大小、尺寸、SHA-256；最大仓库 PNG 为 315,901 bytes |
| `perf.json`、`perf-samples.json`、`perf-method.txt`、`perf.log` | 有效 30 秒结果、原始样本、复现方法及输出 |
| `perf-attempt1.log`、`perf-attempt1-method.txt`、`ui-asleep-stack.txt` | 首次采样失败及只读诊断 |
| `build.log`、`ui-60s.log`、`production-startup.log`、`log-start.json`、`log-end.json` | 构建和生产日志 / 时间窗 |
| `panda-pre.json`、`panda-post-build.json`、`panda-safety.diffstat` | 只读 Panda 版本/签名/health 与空源码差异 |
| `production-runtime.json`、`final-runtime.json`、`final-preservation.json` | 生产和最终状态、安全样本、原有文件与参数保留检查 |
| `before.json`、`after-e2e.json`、`layout-restoration.json`、两个 `XpilotTileLayout.*` | 初始快照、编辑后差异、首次恢复动作及最终用户布局副本 |
| `.gitattributes` | 本目录 PNG 作为普通 Git blob 保存 |

主机完整原始证据：`/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/validation-X-20261023-05-phase-B/`。其中 `xpilot-ui-check-v4/` 保存 22 张未经缩小的原始 PNG；Regulatory 原件为 474,956 bytes，仓库副本为 307,633 bytes，1600×800。

设备原始证据：

- `/data/xpilot-install-20261022/xpilot-20261023-v4.bundle`
- `/data/xpilot-ui-check-v4-build.log`
- `/data/xpilot-ui-check-v4-ui-60s.log`
- `/data/xpilot-ui-check-v4-perf.json`、`/data/xpilot-ui-check-v4-perf.log`
- `/data/xpilot-ui-check-v4-e2e.log`
- `/data/xpilot-ui-check-v4/`
- `/data/xpilot-ui-check-v4-evidence/`
- `/data/xpilot-install-20261022/runtime-check.json`

## 回滚

更新前的 `7ee2e996515f9648be81dc3ce12d5551ead7ba05` 仍在同一个 candidate 仓库内，设备回退引用 `xpilot-ui-v4-before-20261023` 精确指向它。v3b、v4 bundle 均保留，原有 287 个 dirty 文件及 `prebuilt` 没有清理。

如需回滚，重新通过 hostname / 硬件档案 / 停车 / 未接合 / Panda 门后停服，在同一 candidate 切回该已保留引用，重新原生 SCons 构建，再启动并复核服务。保留当前 xpilot 引用和 v4 bundle 可用于前滚；不要清理 LFS 实体或覆盖用户当前布局。Panda 版本、签名和固件内容未变，本轮没有需要回退的固件。

本轮没有执行代码回滚：指定目标正常运行、E2E 通过，问题和证据交由协调者处理。

## 未验证边界

- 没有道路、真实 onroad 相机/车道/告警、车辆闭环控制、实际盲区信号或 engagement 验证。
- 模拟 onroad 中央是 mici Home 纹理，不能替代真实 driving view；红色 overlay 为强制注入。
- Driver camera 只验证原生页、返回和参数清理，没有证明实际摄像头图像。
- Small models 子页 skipped；没有模型选择、刷新、清缓存、下载取消或训练后续步骤验证。
- onboarding 只做独立无输入绘制，未跑首次开机接受/拒绝流程。
- 没有插件商店 Refresh、安装/升级/删除，没有 Wi-Fi/网络配置操作，没有确认危险动作。
- 用户手动触屏的完整时间序列未知，布局和性能都不能当作完全隔离的无人干预实验。
- 没有修复上述产品或环境问题，提交只包含验证文档和证据。
