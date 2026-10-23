# X-20261023-U3 C3XL xpilot UI v4 第三轮部署与停车验证记录

## 结论

- 状态：**DONE**。设备从 `00f7924ca05272103dd7cd2063cd5c66d1767b87` fast-forward 到指定目标 **`25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191`**，完成增量 bundle、原生 SCons 构建、构建前后 Panda 只读门、60 秒生产日志、完整 30 秒亮屏性能、原样大屏 E2E、训练 next 补充 E2E 和服务恢复。
- 设备为 C3XL **`comma-9c13c9f5`**；连接 `comma@192.168.102.113`，活动路径 `/data/openpilot -> /data/xpilot-install-20261022/candidate`。最终 `comma.service=active`，设备活动 HEAD 仍为上述产品目标；本目录文档提交不代表设备运行了该文档提交。
- 最终 `IsOffroad=1`、`IsEngaged=0`、`deviceState.started=false`；15 秒 runtime check 得到 **151 个 Panda 样本**，全部 `controlsAllowed=false`、`faultStatus=none`、类型 Tres。UI、pandad、hardwared 均 `running=true, exitCode=0`。
- 原样仓库 E2E **`passed=true, errors=[]`，退出码 0**；Driver camera 和 Regulatory 均记录 `skipped=true, reason="row hidden on this hardware"`，符合 C3XL。Small models 因无 qcom bundles skipped。
- 补充真实 GPU E2E **`passed=true, errors=[]`**：从 Device 打开训练首步，通过真实映射 press/release 点击 next，直接回到 Device，没有进入 DM 或相机上传步骤。`CompletedTrainingVersion`、`RecordFront`、`IsDriverViewEnabled` 和布局字节不变。
- 30 秒生产性能：**CPU 23.2961%，frame avg/p95 17.2003 / 17.2292 ms**，1742 条帧样本，收到的样本没有 >20 ms 帧。三次 `(10,10)`、50 ms 空白角落触点维持亮屏；完整时间和遥测限制见性能节。
- 20 张原样 E2E PNG 加 2 张训练 next 证据，共 **22 张 2160×1080 原图**；全部逐张目视检查，最大 **314,500 bytes**，严格小于 400,000 bytes。设备、主机、仓库副本字节相同，无缩放或重编码。
- 用户布局前后为 729 bytes，SHA-256 **`bbfa8eb72310ee2e77e8322de689f69e969fbdb599f69695ce6600b0c3749034`**；driver view 前后均为原字节 `0`，SHA-256 **`5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9`**。本轮不需要额外恢复写入。
- 设备原有 **287 个 dirty 文件（含 prebuilt）内容全部未变**。本轮没有产品源码修改；Git 提交仅归档本目录。没有 CAN 验证命令、Panda flash、数据重置、网络配置更改或危险动作确认。
- 最终门首次 5 秒采样在 `gate.py:24` 的 `assert rows and all(sm.alive.values())` 失败；原始日志及空输出保留。同一脚本重跑和随后 15 秒 runtime 均通过。首次没有输出各通道明细，不能确定是哪个条件未就绪，也不声称已定位根因。

## 版本身份与同步

| 项目 | 结果 |
|---|---|
| 远端 / 分支 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git` / `xpilot` |
| 目标解析 | `git fetch origin xpilot` 后，`git rev-parse 25e9eeb296` 得到 `25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191` |
| 主机验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source`，开始为干净 `xpilot@6b11af1cdfae303c130afc333256bd6b53ea1767`，直接 ff 到目标；未切换分支、reset 或 clean |
| 更新前 / 最终设备 HEAD | `00f7924ca05272103dd7cd2063cd5c66d1767b87` / `25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191` |
| 增量 bundle | `/data/xpilot-install-20261022/xpilot-20261023-v4c.bundle` |
| bundle SHA-256 | `32981ac6c0b80c50b453757b0c91c5d86d8b92e76a78b26a0bf3eeb467075bbd`，主机与设备一致 |
| bundle 范围 | prerequisite `00f7924ca0...`，head `25e9eeb296... refs/remotes/origin/xpilot`；两端 `git bundle verify` 通过 |
| 设备更新 | 从 bundle 更新设备 `origin/xpilot`，再 `git merge --ff-only 25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191` |
| 产品差异 | 排除已有验证文档后，仅 `device.py`、`training.py`：2 files changed, 11 insertions(+), 4 deletions(-)，见 `product.diffstat` |
| 完整差异 | 包含第二轮报告目录，见 `source.diffstat`；不能把文档行数当产品改动规模 |
| Panda / safety 差异 | 下列 diffstat 为空，`panda-safety.diffstat` 为 **0 bytes**；两目录均未改动 |
| E2E 脚本 SHA-256 | `5dfba7d29b294ae2a7e215522329187bc4d0e77063adc51bd1dba01a4aca4156`，主机与设备一致，原样执行 |
| 回退引用 | 设备 `xpilot-ui-v4c-before-20261023` 指向更新前 `00f7924ca05272103dd7cd2063cd5c66d1767b87` |
| 文档发布身份 | 本目录 scoped commit 见 Git 历史；最终 commit 与远端回读另存主机 `publication.json`，与设备产品 HEAD 分开记录 |

```bash
git diff --stat 00f7924ca0..25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191 -- panda/ opendbc_repo/opendbc/safety/
```

未对主工作树 `/Users/mile/Desktop/mo-op` 执行 Git 切换、清理或覆盖。验证 checkout 本轮无其他 dirty 工作，因此没有另建 worktree。设备变更路径与原有 dirty 路径的交集为空，见 `deployment-overlap.json`；最终所有原有内容哈希相同。

## 安全门与数据保留

写入前、停服部署前、生产运行、性能前、E2E 前、服务恢复后均采样核对 hostname、C3XL 档案、活动目录、IsOffroad、IsEngaged、deviceState 和 Panda。初始 51 个、性能窗口 300 个、最终 151 个 Panda 样本均无 fault、未允许控制。构建前后 SPI health 还确认 ignition_line、ignition_can 为 false。

受保护参数逐项记录存在性、大小与 SHA-256：`DoReboot`、`DoShutdown`、`DoUninstall`、`HasAcceptedTerms`、`HasAcceptedTermsSP`、`CompletedTrainingVersion`、`IsDriverViewEnabled`、`CalibrationParams`、`LiveTorqueParameters`、`LiveParametersV2`、`LiveDelay`、`InteractivityTimeout`、`RecordFront`。最终全部与初始一致：

- 三项危险动作参数一直不存在；四项校准/车辆参数原本不存在，最终仍不存在。
- Terms / training 版本没有变化。补充验证只完成 **Review training guide 的返回流程**，没有改首次开机训练完成版本，也没有接受或拒绝条款。
- `InteractivityTimeout` 保持原字节 `0`；本轮没有采用第二轮的临时超时参数方法。
- `IsDriverViewEnabled` 始终逻辑 false，最终文件仍为原字节 `0`。`driver-view-preservation.json` 实际记录 `restored=false, matches_initial=true`；不能把预备的恢复分支说成已执行写入。

| 阶段 | XpilotTileLayout | IsDriverViewEnabled |
|---|---|---|
| 部署前 | 729 bytes，`bbfa8eb7...` | 1 byte，`0`，`5feceb66...` |
| 原样 E2E 内部 | `file_matches=true, layouts_match=true` | before=false，after=false |
| 训练 next 补充 E2E | 前后 SHA-256 相同 | 前后 SHA-256 相同 |
| 最终外部快照 | 729 bytes，同一完整 SHA-256 | 1 byte，同一完整 SHA-256 |

除原样与补充 E2E 的映射输入、性能窗口空白角落短触点外，没有额外触屏操作。没有实际进入 onroad、驾驶、engagement、CAN 验证、Panda flash、数据 reset、网络变更；从未确认 reboot、power off、reset 或 uninstall。原样 E2E 的 `ui_state.started=True` 只用于独立进程的合成布局检查，没有改车辆/IsOffroad 状态。

## 构建与 Panda 禁止刷写门

停服前通过实时门，退出清理保证失败也启动服务。原生构建命令与前两轮相同：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

退出码 0，`build.log` 无 warning/error：

```text
scons: done building targets.
real 12.90
user 11.42
sys 1.51
```

沿用上一轮修正后的严格只读方法：`PandaSpiHandle.get_info/controlRead`；跳过 `Panda.__init__/connect`，仅复用版本、签名及 health 解码。不调用 flash、reset communications、safety 设置或 CAN 接口。

| 项目 | 构建前 / 后结果 |
|---|---|
| serial / 类型 | `1d002d000a51303436323838` / raw `09`，Tres |
| 应用态 | info `1d002d000a5130343632383809cc`，`0xCC` 应用态、非 bootstub |
| 设备 / 构建版本 | 均为 `DEV-443dd964-DEBUG` |
| 签名 | 两次与构建完整匹配，前缀 `89e7f6a96b68f6a0`；完整值见两份 Panda JSON |
| 固件 SHA-256 | `656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`，与前两轮相同 |
| health | controls_allowed=false，faults=0，fault_status=0，spi_error_count=0，ignition_line=false，ignition_can=false |
| safety_mode | 构建前 19，构建后 0；检查脚本没有设置 safety mode |

版本、签名一致，无需且没有刷写。生产启动随后也打印设备 signature 与 expected 相同，USB 尝试失败后通过 SPI 成功连接。

## 正常服务、60 秒 UI 日志与最终恢复

`tmux pipe-pane` 捕获 **60.001409288 秒**生产日志，UTC `2026-10-23 04:45:25.765522` 至 `04:46:25.767095`，即台北时间 12:45:25 至 12:46:25。设备原件 `/data/xpilot-ui-check-v4c-ui-60s.log`，起止记录为 `log-start.json` / `log-end.json`。该窗口保留默认停车息屏行为，包含息屏阶段；不作为 60 秒连续渲染证明。

60 秒窗口没有 Python traceback、UI 退出或低 FPS 提示。实际有模型列表 HTTPS read timeout、expired cache，以及后台 GitHub SSH host authenticity 提示；没有回答该提示或修改 known_hosts/网络。启动日志另有以下既有环境信息：

```text
tee: /sys/devices/system/cpu/cpufreq/policy4/scaling_max_freq: Invalid argument
ln: failed to create symbolic link ...vscode-server...
ln: failed to create symbolic link ...windsurf-server...
No IRQs found for 'fts_ts'
raylib: COMMA: Failed to initialize color correction
raylib: FONT: Requested codepoints glyphs found: [117/122]
raylib: FONT: Requested codepoints glyphs found: [107/122]
openpilot/selfdrive/pandad/usb.cc: failed to connect to panda over USB: Success
```

后续 SPI 连接成功，不能把 USB 尝试失败说成 Panda 未连接。没有为消除提示而改变系统、频率、IRQ、字体、网络或固件。

原样及补充 E2E 后由 EXIT trap 恢复 `comma.service`。最终 UI PID **193461**、pandad PID **193469**、hardwared PID **193474** 均运行且退出码为 0；两层 manager 存在，活动路径及 HEAD 正确。首次最终门失败的原始日志为 `final-check-attempt1.log`，空 JSON 为 `after-e2e-initial-attempt1.json`；重跑相同门和 15 秒 runtime 成功，见 `final-check.log`、`final-runtime.json`、`final-preservation.json`。没有因这个采样失败额外重启或改源码。

`production-env.json` 记录最终 UI cmdline `openpilot.selfdrive.ui.ui` 与 cwd `/data/xpilot-install-20261022/candidate/openpilot/system/manager`。限域 `/proc/<pid>/environ` 读取没有返回所查 PATH/PYTHONPATH 等键，因此不声称已确认其完整环境；下列采样/E2E 使用明确指定、与前两轮相同的环境。

## 30 秒 UI CPU 与帧时间

沿用 v3b / v4 第一轮算法：从 manager 获取 UI PID，读取 `/proc/<pid>/stat` 的 utime+stime，以 `SC_CLK_TCK=100` 和单调时钟计算单逻辑核基准 CPU；同时订阅 `uiDebug.frameTimeMillis/cpuTimeMillis`。持续核对未 started/engaged、Panda 无控制许可/无 fault、UI PID 及启动标识不变。

| 指标 | v3b | v4 第一轮 | v4b 第二轮 | 本轮 v4c |
|---|---:|---:|---:|---:|
| 完整窗口 | 30.000381 s | 30.008655 s | 未完成 | **30.005063 s** |
| 帧样本 | 1737 | 1745 | 1215 条部分帧 | **1742** |
| UI 进程 CPU | 33.0662% | 23.2266% | N/A | **23.2961%** |
| frame avg / median | 17.2723 / 17.2721 ms | 17.1649 / 17.1616 ms | N/A | **17.2003 / 17.1971 ms** |
| frame p95 / p99 / max | 17.2809 / 17.2908 / 17.3393 ms | 17.1926 / 17.2131 / 17.2294 ms | N/A | **17.2292 / 17.2493 / 17.2705 ms** |
| frame CPU avg / p95 / max | 1.5428 / 1.9408 / 2.3606 ms | 1.5217 / 1.8777 / 5.1765 ms | N/A | **1.5138 / 1.8869 / 3.1630 ms** |
| 收到样本 >20 / >33.3 / >100 ms | 0 / 0 / 0 | 0 / 0 / 0 | N/A | **0 / 0 / 0** |

本轮 CPU 比 v3b 少 **9.7701 个百分点，约 29.55%**，比 v4 第一轮多 **0.0695 个百分点**；frame avg 比 v4 第一轮多 **0.03536 ms**。这是不同提交、不同时点的观测窗口比较；v4 第一轮还有用户手动触屏，不当作严格受控 A/B 或源码改动的因果效果。

本轮明确允许第一轮的 keep-awake 方法。触摸设备先核对为 Samsung Touchscreen，原始 MT x/y 范围分别为 0..1080、0..2160；仅向原始 **`(10,10)`** 注入 50 ms press/release，位于屏幕角落、网格外，不进入任何磁贴。以下时间为 **release 完成后**相对正式采样起点的单调时钟时间，按同一方法与第一轮比较：

| 次数 | 相对采样起点 | 坐标与时长 |
|---:|---:|---|
| 1 | -0.231142 s | raw (10,10)，50 ms |
| 2 | 10.058437 s | raw (10,10)，50 ms |
| 3 | 20.064788 s | raw (10,10)，50 ms |

首帧 **0.008867 s**，末帧 **30.005039 s**；本轮增加完整窗口断言，首帧 <0.5 s、末帧 >29.5 s、相邻采样间隔 <0.5 s，全部通过。最大采样间隔 **66.569 ms**，包含采样脚本自身执行 50 ms 短触点的阻塞；不能把“收到的 1742 条没有长帧”扩大成所有渲染帧全覆盖。结束后只读 ioctl 确认 10 个 MT tracking ID 均为 -1、BTN_TOUCH=false，见 `touch-released.json`。

CPU ticks 增量 **699**，Panda 样本 **300**。`uiDebug_valid_samples=0`，1742 条实际收到的消息 valid 标志全部为 false，沿用历史字段算法，没有改标志。`uiDebug` 为 0 Hz 按需服务，runtime 的默认 alive/valid 不能代替帧计数；进程 CPU 与帧内 cpuTimeMillis 也不混为同一指标。

完整原始帧、汇总和复现方法分别为 `perf-samples.json`、`perf.json`、`perf-method.txt`；保持亮屏的脚本即设备外部证据 `/data/xpilot-ui-check-v4c-evidence/perf.py`：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 /data/xpilot-ui-check-v4c-evidence/perf.py
```

## 大屏 E2E

实时停车门通过后停服，运行目标提交中的原样脚本：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v4c
```

`result.json` 原样为 **`passed=true, head=25e9eeb296..., errors=[]`**，退出码 **0**：

- 九个 offroad 设置磁贴齐全；60 帧空闲 tile face 重画数 **0**；详情页均原生、mici 绘制次数为 0，应用导航栈为 1。
- Store 子页栈深 2，真实 Back 返回同一个 Plugins 页面。Models 为原生页；Small models 因 `no qcom bundles available` skipped。
- Device 的 TrainingGuidePage、TermsPage 打开和 Back 正确。Driver camera、Regulatory 行都因硬件隐藏而 skipped，**没有这两张 PNG 是预期**，不再把不存在的 cabin camera 预览当故障或待验证相机。
- 原样脚本只检查训练第一步并 Back，不点击 next；首步结束的动态证明由下述补充 E2E 提供。
- onboarding 独立无输入渲染；没有点击接受/拒绝或推入真实首次开机窗口。
- Toggles 当前 small，通过长按、resize 变 wide；Add tiles、Back、取消选中、Drive、Done、20 次 move 拖动均通过。
- 默认 drive 五张数据磁贴左右交替；speed_card 拖至 `(7,3)` 的保存位置与合成 onroad 一致。viewport `(300,59,1560,699)`，无磁贴覆盖 VIEW / blocked cells，无设置磁贴，强制盲区 overlay 绘制 2 次。
- `file_matches=true, layouts_match=true`；driver view before/after 均 false，外部最终字节也一致。

原样 E2E 日志的低 FPS 提示为 **9、6、8、5、9、6、9**，没有 traceback。这些发生在独立截图/页面创建测试中，不与生产稳态性能窗口混用。

### 训练 next 补充 E2E

仅使用外部证据脚本，不修改或替换仓库 E2E，也不改产品源码。失败模式先列在 `FAILURE-MODES.txt` 与脚本首部。使用生产 BigScreenHost、DevicePage、TrainingGuidePage、真实 GPU 和相同 `host.to_logical` 输入映射：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 /data/xpilot-ui-check-v4c-evidence/training-next-e2e.py
```

首先真实点 Device 磁贴中心 **(949,147)**，核对 camera / regulatory 两行不可见，沿用原样 E2E 的真实 Review row callback 打开训练；渲染首步后，按实际按钮矩形中心 **(1650,945)** 注入 press/release。next 后栈为原 Device 一层、`host._shown` 为原 Device、训练 inactive 且 `_step` 仍为 0；全过程 driver view 为 false，没有 DM 步骤或 modal。保留 `training-next-before.png`、`training-next-after.png`、`training-next-result.json`，结果 **passed=true, errors=[]**，四项受保护字节 SHA-256 前后相同。

这证明 **C3XL 的训练 review 在 attention 后直接结束并返回**。没有首次开机训练版本写入或有 cabin camera 硬件上的流程验证。

## 截图逐张目视结论

20 张原样截图和 2 张补充截图全部已逐张查看；Device、训练首步及 next 前后另以完整原图复核。全部 2160×1080、未变换；`artifacts.json` 记录逐张设备路径、主机路径、仓库路径、大小、尺寸与 SHA-256，并与 `device-manifest.json` 比对。

| PNG | 目视结论 |
|---|---|
| `start.png` | 九个设置和五个数据磁贴齐全；当前用户 Status/Toggles/Developer 为 small、Plugins/Tesla 为 medium。small Car 的 `0 km/h` / `U --`、Map 的 `No map data` 无横向裁切。未覆盖真实长路名/长车辆文本。 |
| `edit.png` | Toggles small 选中，两个角钮清楚；Park/Drive/Done 在最后空格 `(7,3)` 竖排，未盖磁贴。按钮 x=1872、y=808/894/980、宽250、高76，均在该空格内。 |
| `edit-resized.png` | Toggles 变 wide，图标、标题和角钮完整；`+` 在 `(6,3)`，竖排工具栏仍在 `(7,3)`，没有覆盖磁贴或与加号混叠。 |
| `add-tiles.png` | 线画 Back、XPILOT / add tiles 和 `No tiles to add` 清楚，没有缺字或意外空白。 |
| `edit-drive.png` | Driving view 占位完整居中；Park/Drive/Done 横排在占位内部下沿 y=658..734，高于占位底758、低于标题，无磁贴遮挡。 |
| `edit-drive-moved.png` | Speed 位于右下 `(7,3)`，编辑按钮仍在占位内部，未覆盖左右或右下磁贴。 |
| `onroad-blindspot.png` | 两侧/右下五张数据磁贴和红色强制渐变可见，字可辨但对比度下降。中央是 mici Home / `25e9eeb` 纹理，非实际道路相机。 |
| `onboarding.png` | terms of service、正文、二维码及两按钮完整；decline & uninstall 只是无输入渲染的文字，没有执行条款或卸载动作。 |
| `page-status.png` | 版本、xpilot、`25e9eeb2`、Network none 清楚；停服测试的 none 不是网络修改。 |
| `page-toggles.png` | 标题、开关、文字清楚，无横向裁切；仍显示 Record & upload cabin camera 通用开关，本轮未改或切换，不能与 Device 的 preview 行混淆。 |
| `page-plugins.png` | Store OPEN、插件行、单一 `0 km/h` 值完整，无 `km/h\|mph` 拼接；最底下一行进入滚动范围。 |
| `page-plugins-store.png` | PLUGINS / store、Refresh 和 Back 清楚；没有 Refresh、安装或删除。 |
| `page-tesla.png` | Off、3-Finger、4-Finger、5-Finger 横向均可见；首屏底边 MADS Screen Activation 的行/按钮仍被纵向裁开，需滚动。 |
| `page-models.png` | 原生模型名、SELECT / REFRESH 均在内容区内，未见横向裁切；Small models 子页 skipped。 |
| `page-network.png` | SSID、勾号、Wi-Fi 图标、Forget、Advanced 清楚；没有连接、忘记或修改网络。 |
| `page-device.png` | **没有 Driver camera preview，也没有 Regulatory info 行**；Review 下直接是 Terms，再到 Reset calibration。ID、Serial、按钮均清楚，没有 camera starting 占位或错误 comma four 标签，符合 C3XL。未触碰 RESET。 |
| `page-device-training-guide.png` | DEVICE / training guide、四条 attention 责任说明和 next 完整，未见裁切。`what is sunnypilot?` 的 `?` 是原文正常标点，非缺 glyph 替代；原样脚本此处只 Back。 |
| `page-device-terms.png` | DEVICE / terms、网址和二维码完整，无接受/拒绝按钮，符合 review 页。 |
| `page-software.png` | 版本、`xpilot (25e9eeb)`、目标分支、检查与卸载行清楚，未执行按钮。 |
| `page-developer.png` | ADB、SSH、SSH keys、Joystick、Longitudinal maneuver 行可读，无明显横向文字裁切；没有修改。 |
| `training-next-before.png` | 补充 E2E 的实际首步，四条说明、正常问号和 next 均完整，与原样训练截图一致。 |
| `training-next-after.png` | 点击 next 后确实回到 Device；camera/regulatory 仍无行，没有 DM、相机检查或上传选择页。 |

所有详情页 Back 均是线画箭头，没有看到缺 glyph 替代的 `? Back`、`Plugins ? Store` 或意外 `?`。日志仍报告字体 codepoints 不全，结论只限截图可见范围。当前布局及 resize/drive 场景编辑栏均无遮挡；没有覆盖停车空格不足时的 fallback 布局，不推广到所有可能布局。

## 编号问题表

共 **6 项**，包括仍可见问题、验证边界、环境信息及已通过重跑的检查问题，不全部视为本轮新回归。本轮只记录，不修改产品源码。

| # | 分类 | 实际症状 / 影响 | 证据与状态 |
|---:|---|---|---|
| 1 | 列表首屏裁行 | Tesla 底部 MADS Screen Activation 行/按钮纵向裁开，横向四选项可见。 | `page-tesla.png`；仍存在，需滚动。 |
| 2 | 模型子页未覆盖 | Small models 无 qcom bundles，按脚本规则 skipped。 | `result.json`；未宣称子页通过。 |
| 3 | E2E 长帧提示 | 独立截图 E2E 出现 FPS 9、6、8、5、9、6、9。 | `e2e.log`；生产收到的样本无 >20 ms，不混用两窗口。 |
| 4 | 运行环境/网络提示 | HTTPS 超时/expired cache、GitHub authenticity、频率/链接/IRQ/色彩校正/glyph 信息；USB 后 SPI 成功。 | `ui-60s.log`、`production-startup.log`；未改配置或确认提示。 |
| 5 | 遥测采样边界 | 1742 条 uiDebug valid 均 false；短触点期间采样最大间隔 66.569 ms，非逐渲染帧完整捕获。 | `perf.json`、`perf-samples.json`；完整 30 秒跨度通过，保留标志及采样限制。 |
| 6 | 最终检查首次未就绪 | 5 秒 gate 的 rows/alive 综合断言首次失败，缺少失败时各通道快照，具体条件未定位。 | `final-check-attempt1.log`、空 `after-e2e-initial-attempt1.json`；同一门重跑及 15 秒 runtime 通过，无额外服务重启。 |

上一轮的性能息屏阻塞已由完整触点保持亮屏窗口消除；相机行按 C3XL 能力隐藏，不再把不存在的 cabin camera 记为预览失败。编辑栏无遮挡、Regulatory 隐藏、训练 next 直接结束均有本轮证据。

## 证据

仓库目录：`docs/validation/xpilot-c3xl-20261023-v4c/`。目录 scoped commit 只归档证据；本轮产品/设备 HEAD 固定为 `25e9eeb2969a24fc2bb7b6c2ae4d571ea257f191`。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本报告，结构沿用前两轮 |
| `result.json`、`e2e.log`、`e2e-exit-code.txt` | 原样 E2E 结果、完整日志、退出码 |
| 22 张 PNG、`artifacts.json`、`device-manifest.json` | 全部原图及跨设备/主机/仓库尺寸、大小和哈希验证，无重编码 |
| `training-next-result.json`、`training-next-e2e.log`、`training-next-e2e-method.txt` | 首步 next 真实 GPU/映射触摸、返回和参数字节证据及可重复方法 |
| `build.log`、`deploy.log`、`source.diffstat`、`product.diffstat`、`panda-safety.diffstat` | ff-only、原生构建、完整/产品范围与 Panda/safety 零差异 |
| `panda-pre.json`、`panda-post-build.json`、`panda-read-method.txt` | 只读版本、签名、health 与方法 |
| `ui-60s.log`、`production-startup.log`、`log-start.json`、`log-end.json`、`production-method.txt` | 60 秒生产日志及时间窗 |
| `perf.json`、`perf-samples.json`、`perf.log`、`perf-method.txt` | 成功性能汇总、原始样本、触点时间、计算与完整窗口断言 |
| `touch-released.json`、`touch-released-method.txt` | 10 个 MT slot / BTN_TOUCH 只读释放检查 |
| `before.json`、各 `*-gate.json`、`after-e2e*.json`、`deployment-overlap.json` | 身份、安全、dirty 哈希、参数及变更无交集证据 |
| `production-runtime.json`、`final-runtime.json`、`final-preservation.json`、`final-check*.log` | 运行、安全及最终字节保留；首次失败和重跑成功日志均保留 |
| `XpilotTileLayout.before`、`XpilotTileLayout.user-final`、`IsDriverViewEnabled.before`、`driver-view-preservation.json` | 用户当前布局、driver view 原字节和无额外恢复写入记录 |
| 其它 `*-method.txt`、`FAILURE-MODES.txt` | 本轮外部证据脚本/实际命令和预先失败模式；不是产品源码或单元测试 |
| `production-env.json`、`restored-startup.log`、`.gitattributes`、`SHA256SUMS` | 限域运行环境、恢复日志、普通 PNG blobs 和全目录内容哈希 |

主机完整原始证据：`/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/validation-X-20261023-U3/`，其中 `xpilot-ui-check-v4c/` 为原样 E2E 输出，`xpilot-ui-check-v4c-evidence/` 为设备外部证据副本。主机还保存原始 bundle、执行 shell 输出、审图 contact sheets；最终 `publication.json` 单独记录文档发布 commit 和远端回读。

设备原始证据：

- `/data/xpilot-install-20261022/xpilot-20261023-v4c.bundle`
- `/data/xpilot-ui-check-v4c-build.log`
- `/data/xpilot-ui-check-v4c-ui-60s.log`
- `/data/xpilot-ui-check-v4c-perf.json`、`/data/xpilot-ui-check-v4c-perf.log`
- `/data/xpilot-ui-check-v4c-e2e.log`
- `/data/xpilot-ui-check-v4c/`
- `/data/xpilot-ui-check-v4c-evidence/`

## 回滚

设备回退引用 **`xpilot-ui-v4c-before-20261023`** 指向本轮更新前 **`00f7924ca05272103dd7cd2063cd5c66d1767b87`**。之前各轮与本轮 bundle、原有 287 个 dirty 文件及 prebuilt 均保留。

如需回滚，重新通过 hostname / C3XL / 停车 / 未接合 / Panda 版本和签名门后停服，在同一 candidate 使用已保留的回退引用，重新原生 SCons 构建，再启动并核对活动 HEAD、进程和 Panda。保留当前引用和本轮 bundle 可用于前滚；不要清理 LFS 实体、prebuilt、用户布局或 driver view 原值。固件没有变化，无固件回退需要。

本轮没有执行产品回滚：目标部署、构建、生产性能、原样及补充 E2E、最终安全门全部完成。文档归档提交若需撤销，用 `git revert <docs commit>`，不改写历史，不 force-push。

## 未验证边界

- 没有真实道路、onroad 相机/车道/告警、车辆闭环、盲区信号或 engagement 验证；合成 onroad 中央是 Home 纹理，红色 overlay 是强制注入。
- C3XL 无 cabin camera，preview 行预期跳过；没有相机硬件出流或有 cabin camera 设备的训练路径验证。
- Small models 子页 skipped；没有模型选择、刷新、下载、缓存清理、商店变更或网络设置操作。
- onboarding 只独立无输入渲染；训练补充验证是 review 返回，不是首次开机接受条款/完成训练写入流程。
- 编辑栏只覆盖当前用户布局、resize 和 drive 场景，未覆盖停车空格不足时的 fallback。
- 性能只有一个 30 秒亮屏窗口，uiDebug valid 标志为 false，触点存在采样间隔；不等于长期热稳态或严格受控 A/B，也不证明全部渲染帧无长帧。
- 没有定位首次最终 gate 未就绪的具体通道，也没有修复已记录产品/环境问题；提交只有本目录报告及证据。
