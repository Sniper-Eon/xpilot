# X-20261023-01 C3XL xpilot UI v2 部署与停车验证记录

## 结论

- 状态：DONE。设备已经从 `3d03575f90802e457db07bb99ba36c002e19c1b8` fast-forward 到目标 `891de5f5c7253bcb1682c3f4a75741f60c2876ab`，完成设备原生构建、正常服务启动、30 秒性能采样、真实 GPU 大屏 E2E、Plugin Store 刷新补证和服务恢复。
- 设备：用户指定的 C3XL `172.16.1.202`；`/data/openpilot -> /data/xpilot-install-20261022/candidate`。
- 最终运行态：`comma.service` active；manager 存在；`ui`、`pandad`、`hardwared` 均为 `running=true`、`exitCode=0`。
- 最终安全态：`IsOffroad=1`、`deviceState.started=false`；最终 5 秒取得 51 个 Panda 样本，全部 `controlsAllowed=false`、`faultStatus=none`、`pandaType=tres`。全程未进入 onroad、未接管、未清数据、未修改 Panda safety 参数。
- `Offroad_TiciSupport` 已不存在；最终 `/data/params/d` 没有任何 `Offroad_*` 文件。停车 Home 截图也未出现 unsupported hardware 告警。
- 仓库原样 `big_screen_e2e.py`：`passed=true`、`errors=[]`。9 个顶层导航入口、offroad/onroad viewport、三张新卡、核心 Car/Map 卡和强制双侧盲区 overlay 均通过脚本断言。
- Panda 构建版本仍为 `DEV-443dd964-DEBUG`，设备读回同版本且 `up_to_date=true`；H7 签名固件 SHA-256 仍为 `656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`。没有刷 Panda。
- 本轮没有修改任何源码；仓库变更只在 `docs/validation/xpilot-c3xl-20261023/`。

## 版本身份与同步

| 项目 | 结果 |
|---|---|
| 来源 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git`，分支 `xpilot` |
| 远端目标 | `refs/heads/xpilot = 891de5f5c7253bcb1682c3f4a75741f60c2876ab` |
| 设备更新前 HEAD | `3d03575f90802e457db07bb99ba36c002e19c1b8` |
| 设备更新后/最终 HEAD | `891de5f5c7253bcb1682c3f4a75741f60c2876ab` |
| 本地主机验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source`，`xpilot`，同步后 HEAD `891de5f5...` |
| 设备活动目录 | `/data/xpilot-install-20261022/candidate` |
| 增量 bundle | `/data/xpilot-install-20261022/xpilot-20261023.bundle` |
| bundle SHA-256 | `766e54371275b18aea3353dfd909fb24ea028ba4fab5e809677526350d464275`，主机与设备一致 |
| 子模块 | `msgq e7396e76...`、neural data `03cac2d3...`、rednose `28d4a7f6...`、tinygrad `92b742f7...`；本次 gitlink 无变化 |
| safety 差异 | `443dd964..891de5f5` 对 `panda/` 和 `opendbc_repo/opendbc/safety/` 的差异为空 |

同步使用包含 `3d03575f...891de5f5` 的 incremental bundle；设备先验证 bundle，再更新 `origin/xpilot`，最后在 `xpilot` 上执行 `--ff-only`。设备提交身份与远端目标完全一致，没有用补丁重建提交。

设备工作树继续显示上一轮已经记录的 LFS 实体文件状态和未跟踪 `prebuilt`；目标范围内的 31 个更新文件均不与这些 LFS 路径重叠，没有清理、覆盖或提交这些状态。

## 安全门

变更前只读检查结果：

- `/data/params/d/IsOffroad` 为 `1`。
- 连续 5 秒取得 50 个实时 Panda 样本；每个样本均为 `deviceState.started=false`、`controlsAllowed=[false]`、`faultStatus=[none]`。
- 活动链接是 `/data/xpilot-install-20261022/candidate`，HEAD 是 `3d03575f...`。
- bundle 上传后、停服前再次确认 `IsOffroad=1`、`started=false`。每次后续停服前也重新确认 offroad/未接管。

## 构建

设备停服后执行原生 SCons：

```bash
env PATH=/usr/local/venv/bin:$PATH /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

完整日志：`/data/xpilot-ui-check-v2-build.log`。

结果：

```text
scons: done building targets.
real 72.32
user 74.28
sys 11.30
```

唯一匹配 `warning|error` 的构建文本如下，原样保留：

```text
Warning: Please note that the following versions of CasADi  are officially supported: 3.5.6 or 3.5.5 or 3.5.4 or 3.5.3 or 3.5.2 or 3.5.1 or 3.4.5 or 3.4.0.
 If there is an incompatibility with the CasADi generated code, please consider changing your CasADi version.
Version 3.6.7 currently in use.
```

构建没有 error，退出码为 0。`openpilot/common/plugin_params.inc` 触发的 Params 原生库已经随正常构建重新生成。

## Panda 禁止刷写门

构建后、comma 仍停止时直接读真实 SPI Panda：

- 构建产物版本：`DEV-443dd964-DEBUG`。
- 设备 Panda：序列号 `1d002d000a51303436323838`，类型 `09`/H7，版本 `DEV-443dd964-DEBUG`。
- `Panda.up_to_date()`：`true`。
- 构建签名文件 SHA-256：`656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`。

版本和签名匹配，因此没有进入刷写路径，也没有调用 flash/reset safety 设置。

## 正常服务启动与告警

构建完成后启动 comma，15 秒消息总线检查和进程检查得到：

- `comma.service=active`。
- manager 两层父/子进程存在。
- `ui`、`pandad`、`hardwared` 均运行且 `exitCode=0`。
- `deviceState.started=false`；Panda `controlsAllowed=false`、`faultStatus=none`。
- `/data/params/d/Offroad_TiciSupport` 不存在，且没有其它 `Offroad_*` 文件。

E2E 后已再次启动 comma。最终复查仍是同一目标 HEAD，服务和三个关键进程正常，51 个最终 Panda 样本无故障且未允许控制。

## 30 秒 UI 帧时间与 CPU

两个独立窗口都在正常 comma 服务、停车 offroad 状态下，从 `uiDebug` 采样并用 `/proc/<ui-pid>/stat` 计算 UI 进程平均 CPU。原始结果为 `perf-initial.json` 和 `perf-steady.json`。

| 窗口 | 时长 | 帧样本 | UI 进程 CPU | frame time avg / median / p95 / p99 / max | frame CPU avg / p95 / max |
|---|---:|---:|---:|---|---|
| initial | 30.0068 s | 1437 | 26.4940% | 90.321 / 未记录 / 17.323 / 未记录 / **104882.500 ms** | 2.610 / 3.768 / 11.340 ms |
| steady | 30.0059 s | 1656 | 21.1625% | 18.122 / 17.302 / 17.313 / 17.325 / **1356.687 ms** | 1.510 / 1.949 / 16.505 ms |

稳态窗口有 2 帧超过 20 ms，2 帧超过 33.3 ms，其中 1 帧超过 100 ms。持续分位数约 17.3 ms，但两次窗口都出现孤立的大停顿；首窗口的 104.8825 秒异常值很像首帧/屏幕恢复计时，但本轮没有足够证据确定原因，不能删掉或当成正常值。

## 大屏 E2E

comma 停止后执行仓库原样脚本：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:$PATH PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v2
```

结果：`result.json` 中 `passed=true`、`head=891de5f5...`、`errors=[]`。

- offroad mici viewport：`(456, 180, 1608, 720)`。
- Home stack=1；Toggles、Models、Plugins、Tesla、Network、Device、Software、Developer 均进入正确类且 stack=2。
- onroad mici viewport：`(360, 218, 1440, 644)`。
- 卡片布局：`speed_card` 左侧，`speed_limit_card` 和 `lead_card` 右侧，`car` 与 `map` 底部；脚本确认都在声明 zone 内且不压入 viewport。
- `blindspot_edges` 已加载，强制左右盲区时 overlay 绘制没有异常。
- E2E 只注入 UI 进程内触摸事件，不改设置、不发 CAN、不建立驾驶控制。

E2E 完整 stdout/stderr：`/data/xpilot-ui-check-v2-e2e.log`。

## Plugin Store 补证

仓库原样 E2E 已验证 Plugins 顶层页面，但没有进入 Plugin Store。补证使用现有生产 `Plugin Store` 与 `Refresh` 按钮回调、同一真实 GPU 合成方式，只经临时 `ssh -R 17897:127.0.0.1:7897` 代理读取索引；没有安装、更新、删除插件，也没有写 Params。临时反向代理完成后已经关闭，设备没有全局网络改动。

`plugin-store.json` 结果：

- `passed=true`，页面为 `StorePage`。
- Refresh 后状态为 `1 plugins`。
- 索引项：`overspeed_warning` / `Overspeed Warning` / `1.0.0` / `installable=true`。
- 截图：`plugin-store-after-refresh.png`。

第一次补证驱动错误地按 items[0] 取按钮，实际取到隐藏 Back，得到 `expected StorePage, got MiciMainLayout`；这是临时验证驱动的索引错误，不是产品错误。随后改为按按钮文本 `Plugin Store` 选择同一生产回调并通过，没有修改仓库文件。

## 编号问题表

| # | 分类 | 实际症状 | 证据与边界 |
|---:|---|---|---|
| 1 | 构建环境 | SCons 成功，但 CasADi 3.6.7 不在生成器列出的官方支持版本中。 | 上方逐字 warning；`/data/xpilot-ui-check-v2-build.log`。没有在本轮证明生成的 MPC 与 3.6.7 完全兼容。 |
| 2 | 验证命令环境 | 仓库原样 E2E 开头打印 `kj/filesystem-disk-unix.c++:1734: warning: PWD environment variable doesn't match current directory; pwd = /home/comma`。 | 由本轮 `env -C` 启动但保留旧 `PWD` 引起；脚本仍退出 0。后续补证改用真实 candidate 路径，不再出现。不是产品 UI 失败。 |
| 3 | GPU/字体 | E2E 打印 `raylib: COMMA: Failed to initialize color correction`；字体多次只找到 `[117/122]` 或 `[107/122]` glyph。 | `/data/xpilot-ui-check-v2-e2e.log`。截图能生成，但色彩校正失败及缺 glyph 没有被本轮修复。 |
| 4 | Network/eSIM | Network 页面阶段两次打印 `No WiFi device found`；eSIM worker 打印 `Failed to poll eSIM profiles`，最终异常为 `openpilot.common.serial.SerialException: [Errno 2] could not open port /dev/modem_at0: [Errno 2] No such file or directory: '/dev/modem_at0'`。 | 完整 traceback 在 `/data/xpilot-ui-check-v2-e2e.log`。上一轮启动环境包含 `BLOCK=modem`；本轮不改设备网络或 modem 配置。 |
| 5 | 帧停顿 | E2E 打印 `FPS dropped below 60: 16`、`15`、`15`、`9`。正常服务 30 秒稳态窗口另有单帧 `1356.687 ms`；首窗口还有 `104882.500 ms` 异常值。 | `perf-initial.json`、`perf-steady.json`、E2E 日志。稳态 p95 约 17.31 ms，说明不是持续低帧率；孤立停顿原因未确定。 |
| 6 | 页面缩放/裁切 | 3× offroad viewport 下多个页面内容过大或裁切：Models 的 `mountain dew model v3...` 越出卡片；Network 的 `AX1800_Pr...` 被 WiFi 图标/边界截断；Software 的版本日期只显示到 `2026.003.000 (Oct 2...`；Device 及 Tesla/Plugins 等页面只露出下一张卡的部分文字。 | `nav-2-models.png`、`nav-5-network.png`、`nav-7-software.png`、`nav-6-device.png`、`nav-4-tesla.png`、`nav-3-plugins.png`。顶层 nav 本身清晰，触摸映射断言通过；问题是复用 mici 卡片在放大 viewport 内的首屏可读性。 |
| 7 | Plugin Store 布局 | 刷新成功后页面标题仍是顶层 `Plugins`；巨大 `Back` 卡占据首屏大部分，`Refresh`/`1 plugins` 只在右侧露出一部分，插件条目首屏不可见。 | `plugin-store-after-refresh.png`、`plugin-store.json`。功能刷新成功，但视觉层级和首屏可用性较差。 |
| 8 | onroad 截图边界 | `onroad-blindspot.png` 的中央 viewport 仍是前一页 Developer 的 ADB/SSH 内容；脚本在同一帧把 `ui_state.started=True` 后立即截图，没有等待真实 onroad 主页面切换。 | 外围卡片坐标和盲区 overlay 已证明；这张图不能证明真实相机/onroad 中心 UI、告警、车道或实际驾驶画面。未上路、未注入控制。 |
| 9 | 正常服务截图缺口 | 正常 comma 服务下尝试通过 raylib 已编译的 F12 screenshot 路径取 live offroad 图；临时只含 F12 的 uinput 设备成功发出事件，但没有生成 `screenshot*.png`。临时设备随后销毁，服务恢复。 | 没有安装截图工具或 attach 正常 UI 进程，避免扩大设备改动。仓库保存的是停服真实 GPU/生产 widget 合成图，而不是 live 服务进程的原生屏幕抓取。 |
| 10 | 文档 push / LFS | 首次普通 push 停在直连 Git LFS；仅为该进程使用现有本机代理后，pre-push 明确失败：`fatal: could not read Username for 'https://huggingface.co': Device not configured`、`Git credentials for https://huggingface.co/sunnypilot/sunnypilot-lfs.git/info/lfs not found.` | 根 `.gitattributes` 把所有 PNG 送到 Hugging Face LFS，但本机只有读取能力。只在本报告目录增加局部 `.gitattributes`，把 12 张小于 400 KB 的证据图作为普通 Git blob；未改全局 LFS、凭据或网络配置。 |

## 截图目视结论

- Home：xpilot 左栏、Home 标题、中心 sunnypilot 首页和底部 build description 均可见；未见 unsupported hardware 告警。
- 顶层导航：选中高亮和左侧蓝条一致；脚本确认九个入口触摸映射正确，没有累积导航栈，也没有顶层冗余 Back 卡。
- Plugins：`Plugin Store` 按钮可见，右侧下一分类卡只显示部分内容。
- Tesla、Device：首张卡标题/值基本可读，但横向下一卡只露出部分文字。
- Models、Network、Software：存在问题表 #6 的明显文本裁切。
- Plugin Store：刷新数据成功，但问题表 #7 的首屏布局明显不理想。
- onroad：三张新插件卡与 Car/Map 卡位置符合 v2 zone；强制双侧红色渐变覆盖左右列，文字仍可辨但对比度降低。中央内容不是有效 onroad 画面，按问题 #8 限定结论。
- 本轮没有观察实体屏幕视频，因此不能凭静态 PNG 排除真实面板闪烁；30 秒性能采样也不能把单次停顿解释为已解决。

## 证据

仓库目录：`docs/validation/xpilot-c3xl-20261023/`

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本记录 |
| `result.json` | 仓库原样 big-screen E2E 结果 |
| `plugin-store.json` | Plugin Store Refresh 补证 |
| `perf-initial.json` | 第一个正常服务 30 秒窗口 |
| `perf-steady.json` | 第二个正常服务 30 秒窗口 |
| `offroad.png` / `nav-0-home.png` | Home/offroad |
| `nav-1-toggles.png` ... `nav-8-developer.png` | 九个顶层导航页面 |
| `plugin-store-after-refresh.png` | 商店刷新后页面 |
| `onroad-blindspot.png` | 一帧模拟 started、卡片和强制双侧盲区 overlay |

设备原始 2160×1080 PNG 和 JSON：`/data/xpilot-ui-check-v2/`。仓库 PNG 已缩小；除 `nav-8-developer.png` 为 1800×900 外，其余为 1920×960，全部严格小于 400,000 bytes。

设备其它日志：

- `/data/xpilot-ui-check-v2-build.log`
- `/data/xpilot-ui-check-v2-e2e.log`
- `/data/xpilot-ui-check-v2-perf.json`
- `/data/xpilot-ui-check-v2-perf-steady.json`

## 回滚

设备已增加只读回滚定位分支 `xpilot-rollback-20261022`，固定到更新前 `3d03575f90802e457db07bb99ba36c002e19c1b8`。当前活动分支仍是 `xpilot`，没有执行回滚。

源码回滚位置是同一 candidate 仓库中的该分支/提交；恢复它后必须重新运行设备原生 SCons，再启动 comma。Panda 不需要回退：`3d03575f` 与 `891de5f5` 的构建版本都指向相同 `DEV-443dd964-DEBUG`，当前签名匹配。更早的 dev-sp 目录 `/data/sp-sync-experiment-20261017/candidate` 仍保留，但它不是本轮 xpilot 3d03575 的直接替代品。

## 未验证边界

- 没有道路、onroad 摄像头、车道线、真实告警、车辆控制闭环或实际盲区信号验证。
- 没有人手触摸验收；顶层导航是 E2E 映射触摸，Plugin Store 补证调用生产按钮回调。
- 没有安装商店插件。
- 没有修复或进一步诊断问题表中的代码问题；按任务要求仅记录，交由协调者处理。
- 没有取得正常服务进程的原生 live screenshot；仓库图片是停服后真实 GPU、生产 widget 的离屏合成证据。
