# X-20261023-08 C3XL xpilot UI v4 第二轮部署与停车验证记录

## 结论

- 状态：**BLOCKED（30 秒完整亮屏性能门未完成）**。指定产品提交已部署、原生构建成功、60 秒生产日志完成、原样 E2E 通过、服务已恢复，报告和证据已整理。不能把这些结果写成全部验收完成。
- 设备由 `3e0b8ba896e876166b86639881f7ead288c846dd` fast-forward 到 **`00f7924ca05272103dd7cd2063cd5c66d1767b87`**；最终活动路径仍为 `/data/openpilot -> /data/xpilot-install-20261022/candidate`，`comma.service=active`。
- 最终 `IsOffroad=1`、`IsEngaged=0`、`deviceState.started=false`。15 秒 runtime check 得到 **151 个 Panda 样本**，全部 `controlsAllowed=false`、`faultStatus=none`，类型 Tres；`ui`、`pandad`、`hardwared` 均运行且 `exitCode=0`。
- E2E：**`passed=true, errors=[]`，退出码 0**。21 张原始 2160×1080 PNG 全部保留、逐张目视检查；仓库副本与原件字节相同，最大 **310,631 bytes**，全部小于 400,000 bytes。
- `edit.png`、`edit-resized.png` 的 Park/Drive/Done 在最后空格内竖排；`edit-drive.png`、`edit-drive-moved.png` 的按钮在 Driving view 占位区内部，四张截图均未遮住磁贴。Regulatory 在 C3XL 上按硬件条件 skipped，未再显示 comma four 标签。
- Driver camera 按新脚本等待 360 帧后仍显示 **`camera starting`，没有摄像头图像**。页面及 Back 生命周期通过不代表实际预览通过。
- 本轮没有取得可用的完整 30 秒生产 UI CPU / 帧时间结果。为遵守“E2E 之外不触屏”，没有复用上一轮角落触点；临时使用现有 `InteractivityTimeout=120`，但 UI 仍在采样后约 20.90 秒停止出帧，完整亮屏断言失败。原参数已恢复为 `0`，失败日志和 1215 个部分帧样本保留。
- 用户当前 `XpilotTileLayout` 前后均为 729 bytes，SHA-256 均为 **`bbfa8eb72310ee2e77e8322de689f69e969fbdb599f69695ce6600b0c3749034`**。E2E 内部文件及两套内存布局恢复也通过；没有重置、替换或删除用户布局。
- 构建前后 Panda 版本、签名、固件 SHA-256 均匹配；没有刷写、调用验证用 CAN 接口或改变 safety 设置。原有 **287 个 dirty 文件（含 prebuilt）内容全部不变**。
- 本轮产品源码零修改。Git 提交仅包含本目录；本地文档提交与设备活动产品提交分开记录，设备没有升级到后续文档提交。

## 版本身份与同步

| 项目 | 结果 |
|---|---|
| 远端 / 分支 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git` / `xpilot` |
| 用户指定、fetch 核对的产品目标 | `00f7924ca05272103dd7cd2063cd5c66d1767b87` |
| 主机验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source`；开始为干净的 `xpilot@aef591f0c01d89983f66030ca6314d435eb4a3e5`，fetch 后 ff 到目标 |
| 设备连接 | `ssh -o BatchMode=yes comma@192.168.102.113`；写入前精确回读 `comma-9c13c9f5`、`hardware_profile=c3xl`、活动路径和 HEAD |
| 更新前 / 最终设备 HEAD | `3e0b8ba896e876166b86639881f7ead288c846dd` / `00f7924ca05272103dd7cd2063cd5c66d1767b87` |
| 增量 bundle | `/data/xpilot-install-20261022/xpilot-20261023-v4b.bundle` |
| bundle SHA-256 | `160bc2613f263fe69a774996485cc852d1ba35b58cb744630ac5583e50e2c65a`；主机、设备相同 |
| bundle 范围 | prerequisite `3e0b8ba896...`，head `00f7924ca0... refs/remotes/origin/xpilot`；两端 `git bundle verify` 通过 |
| 设备更新方式 | 从 bundle 更新设备 `origin/xpilot`，`git merge --ff-only 00f7924ca05272103dd7cd2063cd5c66d1767b87` |
| 产品差异 | 排除上一轮验证目录后，6 files changed, 70 insertions(+), 30 deletions(-)：XPILOT、Device 页、编辑栏和既有检查脚本；完整范围见 `source.diffstat` |
| Panda / safety 差异 | 以下命令输出为空，`panda-safety.diffstat` 为 0 bytes |
| E2E 脚本 SHA-256 | `5dfba7d29b294ae2a7e215522329187bc4d0e77063adc51bd1dba01a4aca4156`；主机、设备相同 |
| 回退引用 | 设备 `xpilot-ui-v4b-before-20261023` 指向 `3e0b8ba896e876166b86639881f7ead288c846dd` |

```bash
git diff --stat 3e0b8ba896..00f7924ca05272103dd7cd2063cd5c66d1767b87 -- panda/ opendbc_repo/opendbc/safety/
```

没有对 `/Users/mile/Desktop/mo-op` 主工作树执行切换、清理或覆盖。只在用户指定的验证 checkout 操作 Git。设备更新文件与原有 dirty 文件没有交集，更新前逐文件记录哈希，最终逐项相同。

## 安全门与数据保留

首次只读预检及落盘的 `before.json` 均取得 51 个安全 Panda 样本。停服部署前、性能采样前、E2E 前、恢复后再次检查 hostname、C3XL 档案、IsOffroad、IsEngaged、deviceState 和 Panda。最终 151 个样本全部无 fault、未允许控制；runtime 的核心服务 alive/valid 均为 true。

底层 SPI 只读 health 的构建前 / 后均为 `ignition_line=false, ignition_can=false, controls_allowed=false, faults=0, fault_status=0, spi_error_count=0`。构建前 safety_mode 为 19，构建后为 0；本轮检查脚本没有调用任何设置 safety mode 的方法。

以下参数记录存在性、长度和 SHA-256：`DoReboot`、`DoShutdown`、`DoUninstall`、`HasAcceptedTerms`、`HasAcceptedTermsSP`、`CompletedTrainingVersion`、`IsDriverViewEnabled`、`CalibrationParams`、`LiveTorqueParameters`、`LiveParametersV2`、`LiveDelay`、`InteractivityTimeout`。最终全部与初始相同。

- 危险动作参数始终不存在；没有确认 reboot、power off、reset、uninstall。
- Terms / training 版本未变；训练只渲染第一步，没有 next/finish。
- 四项校准/车辆参数原本不存在，最终仍不存在；没有数据重置。
- `InteractivityTimeout` 仅在性能尝试前临时从 `0` 改为 `120`，退出清理恢复原字节 `0`，前后 SHA-256 为 `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9`；过程见 `timeout.log`。
- E2E 内部 `IsDriverViewEnabled=false -> false` 恢复通过。随后 manager 启动按 `CLEAR_ON_MANAGER_START` 清理该文件，首次外部快照为“不存在”，逻辑值仍为 false，触发保留断言。恢复原来的 false 字节 `0` 后重做最终检查通过；原始失败保留在 `after-e2e-initial.json`、`final-preservation-attempt1.json`。`driver-view-restoration.json` 是主机根据快照和执行动作整理的记录，设备独立恢复日志在收集时不存在，不把该主机记录当作原始设备日志。

布局记录如下，没有额外恢复或重置操作：

| 阶段 | 结果 |
|---|---|
| 部署前 | 729 bytes；SHA-256 `bbfa8eb72310ee2e77e8322de689f69e969fbdb599f69695ce6600b0c3749034` |
| E2E 内部 | `file_matches=true, layouts_match=true` |
| E2E / 服务恢复后 | 729 bytes；同一 SHA-256 |
| 最终保留 | `layout_unchanged=true`；字节副本 `XpilotTileLayout.user-final` |

没有真实进入 onroad、engagement、驾驶或控制；没有验证用 CAN 发送或接收命令、网络配置变更、Panda flash。E2E 只在独立 UI 进程内模拟 onroad 布局。除 E2E 自身的映射触摸事件，本轮没有物理或注入式触屏。

## 构建与 Panda 禁止刷写门

停服后原生构建，退出码 0：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

```text
scons: done building targets.
real 12.89
user 11.34
sys 1.59
```

`build.log` 无 warning/error，设备原件 `/data/xpilot-ui-check-v4b-build.log`。

沿用上一轮的严格只读方法：`PandaSpiHandle.get_info/controlRead`，跳过 `Panda.__init__/connect`，仅复用版本、签名、health 解码。不使用普通 `Panda()` 的连接设置、reset communications 或刷写路径。

| 项目 | 构建前 / 后结果 |
|---|---|
| serial / raw type | `1d002d000a51303436323838` / `09`，Tres |
| 应用态标记 | `0xCC`，非 `0xEE` bootstub；原始 info 为 `1d002d000a5130343632383809cc` |
| 设备 / 构建版本 | 均为 `DEV-443dd964-DEBUG` |
| 完整签名 | 两次均与构建完全相同；前缀 `89e7f6a96b68f6a0`，完整内容见两个 Panda JSON |
| 固件 SHA-256 | `656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`，与 v3b / v4 第一轮相同 |
| health | controls_allowed=false、faults=0、fault_status=0、spi_error_count=0 |

首次证据脚本错误地用 `not info[13]` 判断应用态，因合法 `0xCC` 触发断言。退出清理立即恢复服务，当时设备仍为 `3e0b8ba896`。按仓库 `Panda.spi_connect` 的解码改为要求 `0xCC` 后重做版本/签名门并通过。此错误只在外部证据脚本中，没有产品源码修改，也不是版本不一致；简明原始错误记录为 `panda-attempt1-error.txt`。

## 正常服务、60 秒 UI 日志与最终恢复

按上一轮用 `tmux pipe-pane` 捕获 **60.000177804 秒**正常生产输出，设备原件 `/data/xpilot-ui-check-v4b-ui-60s.log`，仓库副本 `ui-60s.log`；起止时钟见 `log-start.json`、`log-end.json`。同时保留启动日志和 15 秒生产 runtime 采样。此时停车默认超时仍为 30 秒，窗口包含息屏阶段，不作为 60 秒持续渲染证明。

本窗口没有 Python traceback、UI 退出或低 FPS 提示。实际出现模型列表请求超时并使用 expired cache，以及设备后台 GitHub SSH host authenticity 提示；没有回答该提示、更新 known_hosts 或修改网络。启动日志还保留以下环境信息：

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

USB 尝试失败之后 SPI 成功，生产日志中的设备签名与 expected 一致。没有为消除这些信息而改频率、IRQ、字体、网络或系统配置。

部署、性能尝试和 E2E 都使用退出清理恢复 `comma.service`。最终 `ui` PID 180706、`pandad` PID 180714、`hardwared` PID 180718，三者均 `running=true, exitCode=0`。最终 runtime 151 个 Panda 样本全部安全，活动 HEAD 仍为指定产品提交。`uiDebug` 为 0 Hz 按需服务，其默认 alive/valid 不能替代实际帧样本。

`production-env.json` 保存最终 UI PID、cmdline、cwd 和限域环境读取；该进程 `/proc/<pid>/environ` 未读出 PATH/PYTHONPATH 等所列键，因此不据此声称已确认生产进程的完整环境。以下构建、采样、E2E 命令的显式 PATH/PYTHONPATH 与上一轮相同。

## 30 秒 UI CPU 与帧时间

CPU 和帧算法沿用上一轮：manager 的 UI PID，`/proc/<pid>/stat` 的 utime+stime，`SC_CLK_TCK` 和单调时钟，配合 `uiDebug.frameTimeMillis/cpuTimeMillis`；持续检查未 started、未 engaged、Panda 未允许控制且无 fault、PID/启动标识未变。

本轮有一项明确流程差异：上一轮有效窗口在采样前及第 10、20 秒注入 `(10,10)` 短触点。此次“E2E 外不触屏”约束下没有注入触点；改用现有 `InteractivityTimeout=120` 后重启服务，但 UI 仍按启动时已建立的息屏计时结束渲染。源码中 `Device._reset_interactive_timeout()` 在初始/交互时建立截止时间，参数刷新本身不重设该截止时间；这与观察一致，未对运行进程或源码打补丁。

| 指标 | v3b | v4 第一轮 | 本轮 v4b |
|---|---:|---:|---:|
| 完整有效窗口 | 30.000381 s | 30.008655 s | **未完成** |
| UI 进程 CPU | 33.0662% | 23.2266% | **N/A** |
| frame avg / median | 17.2723 / 17.2721 ms | 17.1649 / 17.1616 ms | **N/A** |
| frame p95 / p99 / max | 17.2809 / 17.2908 / 17.3393 ms | 17.1926 / 17.2131 / 17.2294 ms | **N/A** |
| 有效窗口帧样本 | 1737 | 1745 | **无有效完整窗口** |
| frame CPU avg / p95 / max | 1.5428 / 1.9408 / 2.3606 ms | 1.5217 / 1.8777 / 5.1765 ms | **N/A** |
| >20 / >33.3 / >100 ms | 0 / 0 / 0 | 0 / 0 / 0 | **N/A** |

失败现场：`perf.py:49` 的完整窗口断言失败，最后帧时间只有采样起点后 **20.896271211 s**，没有达到 `>29.5 s`。原始样本 1215 条，第一条为 0.007784857 s，消息 valid 全部为 false。仅这段部分帧的 frame avg/p95 为 **17.1951366 / 17.2045698 ms**，max 17.2883911 ms；这些诊断值不作为 30 秒通过结果，不与历史完整窗口计算改善率。脚本在断言后才生成 CPU 汇总，因此没有本轮有效 CPU 数值，不能用历史 23.23% 填补。

`perf-failure.json` 明确 `passed=false, process_cpu_percent=null`；原始日志、样本和方法分别为 `perf-attempt1.log`、`perf-attempt1-samples.json`、`perf-method.txt`。退出清理将 `InteractivityTimeout` 恢复原值并读回哈希。没有为了补齐数字而触屏、篡改 valid、缩短窗口或拼接两次运行。

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 /data/xpilot-ui-check-v4b-evidence/perf.py
```

该命令及 `perf-run-method.txt` 重现的是本轮**失败尝试**；在“不额外触屏、无源码修改”约束下，本轮没有建立成功的 30 秒保持亮屏方法，因此整体状态保留 BLOCKED。

## 大屏 E2E

停车安全门通过、服务停止后执行目标提交中的原样脚本：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v4b
```

退出码 **0**，原样 `result.json` 为 **`passed=true, head=00f7924ca0..., errors=[]`**，没有 E2E 错误。退出后服务恢复。

- 九个 offroad 设置磁贴全部放置，所有原生详情页 mici 绘制计数为 0；60 帧空闲磁贴正面重画次数为 **0**。
- 九个详情页 title / PAGE 正确，应用 nav stack 为 1；Plugins Store 子页真实 Back 返回同一个 Plugins 页面。
- Models 为原生 `ModelsPage`；Small models 因 `no qcom bundles available` skipped，未执行模型选择或刷新。
- Device 的 TrainingGuidePage、DriverCameraPage、TermsPage 正确并返回 Device；Regulatory 为 `skipped=true, reason="row hidden on this hardware"`，没有 Regulatory PNG，符合 C3XL 预期。
- Driver camera 分支等待 **360 帧**（60 FPS 下名义约 6 秒；没有独立墙钟计时），截图仍为 `camera starting`。Back 后 driver view 为 false。该脚本不检查图像像素或保证相机出流，因此 passed 不代表实际相机图像通过。
- onboarding 只做独立、无输入的原生页绘制，没有推入真实 onboarding window 或点击接受/拒绝。
- 用户布局中的 Toggles 初始为 **small**，本轮真实 resize 后为 **wide**；不是上一轮 medium -> small。长按、resize、取消选中、Add tiles、Back、Drive、Done 和 20 次 move 拖动均通过。
- drive 默认左右交替的五张数据磁贴位置正确；speed_card 被拖到 `(7,3)`，固定位置、模拟 onroad 位置一致。模拟 viewport `(300,59,1560,699)`，没有设置磁贴或 VIEW/blocked cells 重叠，强制盲区 overlay 绘制 2 次。
- `file_matches=true, layouts_match=true`，driver view before/after 均 false；外部最终布局哈希也一致。

E2E 日志打印 `FPS dropped below 60: 9, 6, 8, 16, 53, 6, 9, 9`。这些来自独立截图测试，不代替生产性能窗口；没有 traceback。

## 截图逐张目视结论

21 张全部已查看。全部原件和仓库副本均为 2160×1080，未缩放、未重编码，字节相同；每张大小、SHA-256、设备/主机原件路径列在 `artifacts.json`。当前用户布局与上一轮首屏不同，不把布局差异当作默认布局变更。

| PNG | 目视结论 |
|---|---|
| `start.png` | 用户当前 Status/Toggles/Developer 等为 small，Plugins/Tesla 为 medium；九个设置和五个数据磁贴齐全。small Map 的 `No map data`、Car 的 `0 km/h` / `U --` 无横向裁切；没有真实长路名或动态车辆长文本覆盖。 |
| `edit.png` | Toggles small 被选中，角钮清楚；Park/Drive/Done 在最后空格 `(7,3)` 竖排。按目标代码矩形 x=1872、y=808/894/980、宽250、高76，均在该空格内；目视没有盖住任何磁贴内容或标题，上一轮底栏遮挡未复现。 |
| `edit-resized.png` | Toggles 为 wide，其他磁贴重排；`+` 在 `(6,3)`，竖排工具栏仍在 `(7,3)`，两者分开。工具栏无磁贴覆盖，选中 wide 磁贴的图标、标题、角钮没有明显裁切。 |
| `add-tiles.png` | 线画 Back、XPILOT / add tiles 页头和 `No tiles to add` 清楚，没有缺字或意外空白页。 |
| `edit-drive.png` | 灰色 Driving view 完整居中，按钮横排在占位区下沿内部，y=658..734，低于文字且高于占位区底758；左右五张数据磁贴均未被按钮遮挡。 |
| `edit-drive-moved.png` | Speed 在右下 `(7,3)`；编辑栏位置仍在灰色占位内部，未盖住右下 Speed、左右数据磁贴或底部可放磁贴区域。 |
| `onroad-blindspot.png` | 五张磁贴在两侧/右下，红色渐变强制覆盖左右，文字可辨但对比度下降。中央仍是 mici Home / `00f7924` 纹理，不是真实道路相机或驾驶画面。 |
| `onboarding.png` | terms of service、正文、二维码及两按钮完整；未见横向溢出。decline & uninstall 仅为文字，没有执行卸载或条款动作。 |
| `page-status.png` | 版本、xpilot、`00f7924c` 和 Network none 清楚；停服测试中的 none 不代表修改网络。 |
| `page-toggles.png` | 标题、开关、行间距清楚，没有明显横向裁切；没有切换设置。 |
| `page-plugins.png` | Store OPEN、插件行、单一 `0 km/h` 偏移值可读，无 `km/h\|mph` 拼接；底部下一行进入滚动区域。 |
| `page-plugins-store.png` | PLUGINS / store、Refresh 行与 Back 清楚；没有 Refresh、安装或删除动作。 |
| `page-tesla.png` | Off、3-Finger、4-Finger、5-Finger 横向均可见；首屏最底 MADS Screen Activation 行/按钮仍被内容区纵向裁开，需要滚动。 |
| `page-models.png` | 原生模型名和 SELECT / REFRESH 均在内容区内；未见上一代 fallback 的横向裁切。Small models 子页 skipped，无对应子页 PNG。 |
| `page-network.png` | SSID、连接勾号、Wi-Fi 图标、Forget、Advanced 清楚；没有连接、忘记或修改网络。 |
| `page-device.png` | Dongle ID、Serial、Review/Preview/Terms 行清楚；E2E 记录 Regulatory 隐藏，未显示不匹配的 comma four 标签。 |
| `page-device-training-guide.png` | DEVICE / training guide、首步四条责任说明及 next 完整。`what is sunnypilot?` 的问号是正常原文标点，不是缺 glyph 替代。未点击 next。 |
| `page-device-driver-camera.png` | DEVICE / driver camera 页头完整；等待后仍只有 `camera starting`，**没有任何实际摄像头图像**。本图不能证明相机预览成功，也不足以单独归因为摄像头硬件故障。 |
| `page-device-terms.png` | DEVICE / terms、网址和二维码完整，无接受/拒绝按钮，符合 review 页面。 |
| `page-software.png` | 版本、分支 `xpilot (00f7924)`、目标分支和检查/卸载行清楚；未执行按钮。 |
| `page-developer.png` | ADB、SSH、SSH keys、Joystick、Longitudinal maneuver 行可读，无明显横向溢出；没有修改。 |

所有详情页 Back 为线画箭头，没有看到缺 glyph 替代的 `? Back` 或 `Plugins ? Store`；训练页的正常问号单独区分。日志仍有字体 codepoints 不全提示，因此这里只下截图可见范围的结论。Regulatory 没有 PNG 是预期硬件 skip，不是丢失证据。

## 编号问题表

共 **9 项**，包含产品视觉问题、未覆盖项目、环境信息和已处理的验证问题；不把它们全部当作本轮新回归。按任务只记录，没有修产品源码。

| # | 分类 | 实际症状 / 影响 | 证据与状态 |
|---:|---|---|---|
| 1 | 性能门阻塞 | 无额外触点时，超时参数没有延长初始息屏计时，最后帧在20.896秒；未取得30秒有效CPU/帧汇总。 | `perf-attempt1.log`、`perf-attempt1-samples.json`、`perf-failure.json`、`timeout.log`；**未完成，整体BLOCKED**。 |
| 2 | 相机图像未证明 | 等待360帧后仍是 camera starting，无实际图像；页面/Back通过不能替代图像通过。 | `page-device-driver-camera.png`、`result.json`；仍未证明。 |
| 3 | 列表首屏裁行 | Tesla 的 MADS Screen Activation 行/按钮在内容区底边纵向裁开。 | `page-tesla.png`；横向选项可见，纵向需滚动。 |
| 4 | 模型列表覆盖边界 | Small models 因无 qcom bundles skipped。 | `result.json`；符合脚本规则，子页未覆盖。 |
| 5 | E2E 长帧提示 | 独立截图运行打印 FPS 9、6、8、16、53、6、9、9。 | `e2e.log`；不与生产稳态混用。 |
| 6 | 运行环境/网络 | 模型列表 HTTPS 超时/expired cache，GitHub host authenticity 提示，以及启动频率、链接、IRQ、色彩校正、glyph 提示；USB失败后SPI成功。 | `ui-60s.log`、`production-startup.log`；未确认提示或改配置。 |
| 7 | 按需遥测标志 | 1215 条部分帧的 uiDebug valid 全为false；最终按需alive/valid不能代替实际帧计数。 | `perf-failure.json`、原始样本、`final-runtime.json`；限制保留。 |
| 8 | 只读检查脚本错误 | 首次把合法应用态0xCC按布尔判断，触发断言；服务自动恢复，源码尚未更新。 | `panda-attempt1-error.txt`、`panda-read-method.txt`、两份Panda JSON；已修正外部脚本并重做通过，无flash。 |
| 9 | 启动参数文件清理 | manager清理原值0的IsDriverViewEnabled文件，首次字节保留检查失败，逻辑仍false。 | `after-e2e-initial.json`、`final-preservation-attempt1.json`、`driver-view-restoration.json`、`final-preservation.json`；已恢复原字节并复核通过。 |

上一轮编辑栏遮挡和 C3XL 显示 comma four Regulatory 标签在本轮指定截图/硬件条件下已消除，不列为仍存在的问题。停车布局空格不足时的源码 fallback 并未由本轮截图覆盖，不能推广为所有布局绝无遮挡。

## 证据

仓库目录：`docs/validation/xpilot-c3xl-20261023-v4b/`。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本记录；目录后续的 scoped docs commit 只归档证据，不代表设备激活该文档提交 |
| `result.json`、`e2e.log`、`e2e-exit-code.txt` | 原样E2E结果、日志、退出码 |
| 21张PNG、`artifacts.json` | 逐张原始尺寸/大小/SHA-256及路径；无缩放，全部<400,000 bytes |
| `build.log`、`deploy.log`、`source.diffstat`、`panda-safety.diffstat` | 构建、ff-only更新及源码差异证据 |
| `panda-pre.json`、`panda-post-build.json`、`panda-attempt1-error.txt` | 只读固件门和首次脚本错误记录 |
| `ui-60s.log`、`production-startup.log`、`log-start.json`、`log-end.json` | 60秒生产日志及计时 |
| `perf-failure.json`、`perf-attempt1.log`、`perf-attempt1-samples.json`、`timeout.log` | 性能失败、部分原始帧、临时超时及原值恢复；没有成功perf.json |
| `before.json`、各`*-gate.json`、`after-e2e*.json` | 身份、安全、dirty内容与参数快照 |
| `production-runtime.json`、`final-runtime.json`、`final-preservation*.json` | 生产/最终采样及原始失败、最终保留结果 |
| `driver-view-restoration.json`、`XpilotTileLayout.user-final`、`InteractivityTimeout.before` | 参数恢复记录、未变布局字节和原始超时字节 |
| 各`*-method.txt` | 本轮实际使用的外部证据脚本与命令，不是产品代码或单元测试 |
| `production-env.json`、`restored-startup.log`、`SHA256SUMS` | 限域进程读取、恢复启动日志、报告和证据内容哈希 |
| `.gitattributes` | PNG作为普通Git blob归档 |

主机完整原始证据：`/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/validation-X-20261023-08/`，其中 `xpilot-ui-check-v4b/` 为原始PNG及result，`xpilot-ui-check-v4b-evidence/` 为设备证据副本。

设备证据：

- `/data/xpilot-install-20261022/xpilot-20261023-v4b.bundle`
- `/data/xpilot-ui-check-v4b-build.log`
- `/data/xpilot-ui-check-v4b-ui-60s.log`
- `/data/xpilot-ui-check-v4b-perf.log`
- `/data/xpilot-ui-check-v4b-e2e.log`
- `/data/xpilot-ui-check-v4b/`
- `/data/xpilot-ui-check-v4b-evidence/`

主机目录还保留部署/性能/E2E/最终检查的shell输出，包括最初参数保留断言失败与后续通过输出。外围读取有一次按旧名称查找不存在的 `params_pyx.pyx`、一次按Python命令名查PID失败，随后使用实际 `params.py` 和manager报告PID；未因此改产品或安装依赖。

## 回滚

设备回退引用 `xpilot-ui-v4b-before-20261023` 精确指向本轮更新前的 **`3e0b8ba896e876166b86639881f7ead288c846dd`**。上一轮和本轮bundle、原287个dirty文件及prebuilt均保留。

如需回滚，先重新通过 hostname / C3XL / 停车 / 未接合 / Panda 版本和签名门，停服，在同一candidate切回已保留的该引用，重新原生SCons构建，再启动并复核活动HEAD、进程与Panda。不要清理LFS实体、prebuilt或覆盖用户布局；不需要固件回退，因为本轮固件未变。

本轮没有执行代码回滚：指定产品目标正常运行，E2E通过；未完成的性能门和可见问题保留为报告结论。报告归档提交如需撤销，使用 `git revert <docs commit>`，不重写历史。

## 未验证边界

- 没有完整30秒亮屏生产性能结果；不能声称达到或优于v3b/第一轮23.23%的CPU。
- 没有真实道路、onroad相机/车道/告警、车辆闭环、实际盲区信号、驾驶或engagement验证。
- Driver camera实际图像仍未证明；模拟onroad中央为mici Home纹理，强制红色overlay不代表真实车辆信号。
- Small models skipped；没有模型选择、刷新、下载、缓存清理、插件商店变更或网络配置操作。
- onboarding只做独立无输入渲染，没有接受、拒绝、卸载、训练后续步骤或危险确认。
- 编辑栏仅验证当前布局及E2E resize/drive场景；没有覆盖停车网格只剩不到两个空格的fallback。
- 没有修复产品或运行环境问题；提交只有本轮验证文档及证据。
