# X-20261023-10 C3XL xpilot v7 设备验证记录

## 结论

- 总状态：**DONE；项目 1–6 全部 PASS**。完成增量 bundle、ff-only、设备原生 SCons、首次 manager 启动、60 秒生产 UI 日志、8 项检查、原样大屏 E2E、27 张磁贴尺寸截图、Plugins 来源补图和最终恢复。
- 本地主机验证基线与设备最终活动提交均为 **`cc129b8829c8fd6d170ef75d9857840cb25ed726`**。报告提交在 `task/X-20261023-10`，其父提交是该目标；报告提交与设备活动提交分别记录，报告分支不会部署到设备。
- v6 的 4 张裁切图在本轮对应尺寸均不再碰到右缘；**27/27 张最右列 YMAX 都为背景值 64**。Clock 显示完整 `12:23`，IP 显示完整 `172.16.1.202`。无文字重叠、过小或省略号。
- 60.054 秒生产窗口中没有 `ModuleNotFoundError`、`overspeed_warning` UI 加载错误或 UI traceback；601 个 Panda 样本均 `controlsAllowed=false`、无 fault。最终再取 51 个安全样本，服务 active。
- 五项参数的存在性和原始字节均已恢复；287 个设备既有 dirty 文件、`overspeed_warning` 全部 7 个文件（含既有缓存）的路径集合与 SHA-256 均未变。
- 共记录 **3 个环境/验证编排问题**，见“编号问题”。没有修改产品源码，没有修复产品问题，没有安装、移除或移动 store 插件。

## 按任务项目的通过/失败

| 项目 | 结果 | 证据摘要 |
|---:|---|---|
| 1. `5b979e2ba8` 实际像素字号 / Clock、IP / 27 张截图 | **PASS** | v6 驱动仅改 TARGET、任务号与 v7 标签；九个独立进程各抓三尺寸，全部 rc=0；像素门 27/27 YMAX=64；最小字号 34 px |
| 2. `b3130009d9` store UI 从 `xpilot_ext` 加载 | **PASS** | 60 秒生产日志无指定缺模块错误；store 文件逐字节未变；原样 E2E、九次磁贴驱动和来源补图均无该异常 |
| 3. `333bd99575` M8 / `6a1c129690` P9 和全部检查 | **PASS** | 8/8 `*_check.py` rc=0；manifest/host 输出包含仍安装的 `overspeed_warning`，errors 为空 |
| 4. `f41c90828e` big_screen_e2e 从 host 推导 drive tiles | **PASS** | 原样脚本 rc=0，`passed=true`，`errors=[]`；24 个 case，drive edit/onroad 合成布局均含八个实际启用的数据 tile |
| 5. `cc129b8829` 删除 ui_smoke.py | **PASS** | 目标树与设备均确认文件不存在，本轮从未执行该脚本 |
| 6. `784485f379` Plugins built-in/store 来源 | **PASS** | Auto Speed Limit 的 Source 为 `built-in (switch off only)`；Overspeed Warning 的 Source 为 `store (removable)`；有真实 GPU 截图 |

## 身份、部署与安全门

| 项目 | 结果 |
|---|---|
| 验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source` |
| 主机初始状态 | 干净，已在同名任务分支 `task/X-20261023-10`，HEAD `b3130009d9bd3a61e143bf1e34dd48cc9ef6834f`；没有切换其它工作树 |
| 主机准备 | `git fetch origin` 后 `origin/xpilot=cc129b8829…`；任务分支以 ff-only 到目标，再新增本目录的报告提交 |
| v6 参考 | `origin/task/X-20261023-09` = `b88c71e480236cc554581d970b6079b1d4f037ff`；已完整读取 REPORT 和 tile_size_e2e.py |
| 设备地址 | 初始 `192.168.102.113` SSH 超时；用户后续改为 **`172.16.1.202`**，之后所有设备操作只用新地址 |
| 设备身份 | `comma-9c13c9f5`，`hardware_profile=c3xl` |
| 活动路径 | `/data/openpilot -> /data/xpilot-install-20261022/candidate` |
| 设备实测起点 | `b3130009d9bd3a61e143bf1e34dd48cc9ef6834f`，分支 `xpilot`；与任务描述的 v6 `bfca6fc…` 不同，未假装从 v6 部署 |
| 设备最终 HEAD | `cc129b8829c8fd6d170ef75d9857840cb25ed726` |
| 增量关系 | `b313000… -> cc129b8…`，4 个提交；`git merge --ff-only` 成功 |
| bundle | `/data/xpilot-install-20261022/xpilot-20261023-v7.bundle`，3192 bytes |
| bundle SHA-256 | `f797990c260c631cfece6810666966699a69208fc3b97d6d5ff1b098c66d420d`，设备读回与主机一致，两端 verify 成功 |
| 最终安全态 | `IsOffroad=1`，`IsEngaged=0`，`deviceState.started=false`，服务 active |
| 最终进程 | UI PID 172379，pandad PID 172385，hardwared PID 172391；均 running=true、exitCode=0 |

设备原有 287 个 dirty 文件主要是 LFS 实体和 `prebuilt`。更新前对其逐文件哈希，确认与四个更新路径无重叠；最终 287/287 内容未变，见 `dirty-before.json` 与 `preservation.json`。未 reset、clean、覆盖这些差异，也未操作主工程 `/Users/mile/Desktop/mo-op`。

所有 SSH/SCP 使用 `BatchMode=yes`、`StrictHostKeyChecking=yes` 和既有 known_hosts。没有修改网络或 SSH 配置；旧地址路由诊断只读。

### Panda 只读门

沿用仓库 v4c 已有的 `PandaSpiHandle.get_info/controlRead` 方法，绕开会写入配置的 `Panda.__init__/connect`。部署前、构建后、测试前、服务恢复前及最终运行态均核对。**各次版本/签名一致，所以没有进入“版本不一致即停止”的分支，也没有 flash。**

| 项目 | 读回 |
|---|---|
| serial / raw type | `1d002d000a51303436323838` / `09`（Tres），应用态、非 bootstub |
| 设备 / 预期版本 | 两者均 `DEV-087a2e7f-DEBUG` |
| 设备 / 预期签名 | 完整 128 bytes 相同；前缀 `34f6597f7fe52f31`，全文见各 Panda JSON |
| firmware SHA-256 | `7153811862ea8027d4ada5f5762f0e67abc15d02a893fa5ca4159ffc40ed093d`，前后相同 |
| 只读 health | controls_allowed=false；faults=0、fault_status=0；ignition_line=false、ignition_can=false |
| 连续样本 | 初始 51；生产 601；最终 51；均无控制许可、无 fault |

指定范围差异记录在 0 bytes 的 `panda-safety.diffstat`，命令如下：

```bash
git diff --stat bfca6fcec388f019e9b3046e9067f3a11e7d27ff..cc129b8829c8fd6d170ef75d9857840cb25ed726 -- panda/ opendbc_repo/opendbc/safety/
```

## 项目 1：部署、原生构建与生产启动

`bfca6fc..cc129b8` 的完整变更清单和统计分别保存在 `changes.log`、`source.diffstat`。除任务列出的七个修复提交，还包括 `9b58afa` 的 Tiles/Driving Overlays 分类拆分。设备已含前四个提交，因此 bundle 以实测 `b313000…` 为 prerequisite；没有重复覆盖早已存在的改动。

停服后执行原生构建：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

**PASS，rc=0**。完整日志为 `build.log`；结果：

```text
scons: done building targets.
real 14.06
user 11.81
sys 1.68
```

构建后先通过 Panda 版本/完整签名门，再启动一次目标 manager，随后采集生产窗口；未用启动 manager 绕过或自动修复固件门。

## 项目 2：60 秒生产 UI 日志

`production.sh` 检查既有 tmux pane 没有其它 pipe 使用后才启用日志，持续 **60.053747 秒**，结束后关闭本轮 pipe。日志在 `ui-runtime.log`，连续进程与安全样本在 `production-runtime.json`。

**PASS（指定 store UI 加载问题）**：未出现 `ModuleNotFoundError`、`openpilot.tesla.plugins.overspeed_warning` 缺模块或任何 UI traceback。生产日志同时明确设备 signature 和 expected 一致。模型列表联网失败仍出现，单列为问题 1，未修改网络来掩盖。

## 项目 3：全部 tools/sp_tesla_e2e/*_check.py

在设备服务停止且原生库已构建后逐个执行，保留每个完整日志。`store_check.py` 自己把安装目录切到临时目录，所做的模拟安装/删除没有接触设备的 `/data/xpilot_plugins/overspeed_warning`。

| 脚本 | rc | 结果 |
|---|---:|---|
| `external_bridge_check.py` | 0 | PASS |
| `manifest_check.py` | 0 | PASS |
| `offroad_pages_check.py` | 0 | PASS |
| `phase2_check.py` | 0 | PASS |
| `phase3_check.py` | 0 | PASS |
| `plugin_host_check.py` | 0 | PASS |
| `store_check.py` | 0 | PASS |
| `tile_layout_check.py` | 0 | PASS |

`manifest_check.py`、`plugin_host_check.py` 仍发现原装 `overspeed_warning`，两者的 `errors=[]`；没有通过删除或移动插件来取得通过。

## 项目 4：原样 big_screen_e2e.py

使用设备生产环境，服务停服以独占 DRM：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo PYTHONDONTWRITEBYTECODE=1 python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v7
```

结果：**PASS，rc=0，passed=true，errors=[]**。24 个 case；drive tile 集合为 speed_card、speed_limit_card、lead_card、car、map、clock、ip、bms。保存布局、BACK、driver view 恢复等断言通过。证据为 `big-screen.log`、`big-screen.exit`、`big-screen/result.json` 和该目录全部页面 PNG。

脚本的 onroad 只是在独立 UI 进程内临时合成布局；没有写 IsOffroad，没有真实 onroad、车辆启动、接合或 CAN 验证。被删除的 `ui_smoke.py` 没有执行。

## 项目 5：27 张尺寸截图与像素裁切判定

复用 v6 `tile_size_e2e.py`，只替换 TARGET、任务号和 v7 标签，行为保持不变，原始驱动哈希与来源见 `tile-driver-origin.json`。每个 tile 用独立进程跑 small/medium/wide，避免 v6 累计读回的长进程停滞。九次 rc 均为 0、passed 均为 true；每次通过生产 long-press、resize tap、Done 回调改变尺寸并在 finally 恢复参数。

截图是**真实设备 GPU、生产 BigScreenHost、生产 tile、设备字体和编辑回调**的 2160×1080 RGBA 图；不是正在运行的 comma.service framebuffer，也不是手指实体触摸证据。

像素检查使用与 v6 数值一致的 `FFmpeg format=yuv444p -> crop 最右一列 -> signalstats.YMAX`。先重新读取 v6 六张 Clock/IP 原图作为校准，得到 235/235/64 与 120/235/64，完全复现 v6 报告；然后检查本轮 27 张。Graphite 空白列为 64，前景进入右缘才会高于 64。没有把 measure_text_ex 的宽度当作最终裁切证据。

```bash
python3 docs/validation/xpilot-c3xl-20261023-v7/pixel-check.py
ffmpeg -hide_banner -nostdin -i docs/validation/xpilot-c3xl-20261023-v7/tile-clock-small.png -vf format=yuv444p,crop=1:250:287:22,signalstats,metadata=print -frames:v 1 -f null -
```

| Tile | 尺寸 | 截图 | 右列 YMAX | 边缘裁切 | 重叠 | 最小字号 | 结论 |
|---|---|---|---:|---|---|---|---|
| Clock | small | [tile-clock-small.png](tile-clock-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Clock | medium | [tile-clock-medium.png](tile-clock-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Clock | wide | [tile-clock-wide.png](tile-clock-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| IP | small | [tile-ip-small.png](tile-ip-small.png) | 64 | 否 | 否 | 34 px | PASS |
| IP | medium | [tile-ip-medium.png](tile-ip-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| IP | wide | [tile-ip-wide.png](tile-ip-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| Map | small | [tile-map-small.png](tile-map-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Map | medium | [tile-map-medium.png](tile-map-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Map | wide | [tile-map-wide.png](tile-map-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| Car | small | [tile-car-small.png](tile-car-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Car | medium | [tile-car-medium.png](tile-car-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Car | wide | [tile-car-wide.png](tile-car-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| Speed | small | [tile-speed_card-small.png](tile-speed_card-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Speed | medium | [tile-speed_card-medium.png](tile-speed_card-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Speed | wide | [tile-speed_card-wide.png](tile-speed_card-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| Lead | small | [tile-lead_card-small.png](tile-lead_card-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Lead | medium | [tile-lead_card-medium.png](tile-lead_card-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Lead | wide | [tile-lead_card-wide.png](tile-lead_card-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| Battery | small | [tile-bms-small.png](tile-bms-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Battery | medium | [tile-bms-medium.png](tile-bms-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Battery | wide | [tile-bms-wide.png](tile-bms-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| Plugins | small | [tile-plugins-small.png](tile-plugins-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Plugins | medium | [tile-plugins-medium.png](tile-plugins-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Plugins | wide | [tile-plugins-wide.png](tile-plugins-wide.png) | 64 | 否 | 否 | 51 px | PASS |
| Tesla | small | [tile-tesla-small.png](tile-tesla-small.png) | 64 | 否 | 否 | 34 px | PASS |
| Tesla | medium | [tile-tesla-medium.png](tile-tesla-medium.png) | 64 | 否 | 否 | 51 px | PASS |
| Tesla | wide | [tile-tesla-wide.png](tile-tesla-wide.png) | 64 | 否 | 否 | 51 px | PASS |

Clock 主值字号分别 97/215/317 px，最后一个 `3` 完整；IP 主值 40/80/80 px，完整显示 `172.16.1.202`。全图最小文字 34 px，高于 24 px 下限；没有 `...`。已逐图目视核对原图/不缩放磁贴裁剪，没有碰边、重叠或过小文字。

**输入边界**：用户更换了地址，本轮 IP 字符串比 v6 的 `192.168.102.113` 短；本轮截图直接证明当前实际 IP 的渲染。没有改网络、伪造当前 IP 或宣称覆盖所有未来长文本。v6 的旧长字符串只用于像素判定方法的回归校准。

## 项目 6：Plugins 来源截图

- [Auto Speed Limit](big-screen/page-plugins-plugin.png)：Source 清楚显示 **built-in (switch off only)**，Version v1.0.0。
- [Overspeed Warning](plugin-source/page-plugins-store-source.png)：Source 清楚显示 **store (removable)**，Version v1.0.0；原有开关仍为 off，Margin 仍为 5 km/h。

第二张由 `plugin-source-e2e.py` 打开生产 PluginsPage/PluginPage 后真实 GPU 导出，rc=0、passed=true；仅打开页面，没有点开关、Install、Update 或 Remove。对应输出在 `plugin-source/`，日志在 `plugin-source.log`。截图证明来源提示；未测试卸载动作。

## 五项参数恢复与文件保全

首次任何产品检查/UI 测试前，已记录五项存在性、SHA-256 和原始字节（base64），保存在 `params-before.json`，设备也保留同名权威备份。各驱动有 finally 恢复，所有 UI 完成后又执行权威恢复。

`IsDriverViewEnabled` 和 `IsOffroad` 的类型带 `CLEAR_ON_MANAGER_START`。因此最终恢复顺序必须包含“服务稳定后再恢复 driver view 原始文件”；本轮已经这样做，且此后没有再重启服务。`params-restored-after-start.json` 记录唯一需要补写的是原本存在的 `IsDriverViewEnabled=b'0'`。

| 参数 | 测试前存在性 / 大小 | 测试前与最终 SHA-256 | 最终 |
|---|---|---|---|
| `XpilotTileLayout` | 是 / 873 bytes | `7d2e2f182f08e9cf92ab14d444b42078cf45f96fafcc693cfa1519149b7f3d46` | 是；逐字节相同 |
| `XpilotTileTheme` | 是 / 8 bytes | `1d261a8554d2da69b2e13445a8ee2a94dd10912a2bf5a0f3d3fe0698e5540f84` | 是；逐字节相同 |
| `XpilotBms` | 是 / 1 bytes | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` | 是；逐字节相同 |
| `CarPlatformBundle` | 是 / 191 bytes | `dfcc84df24862d499db2c9a7572af713b81f9592a740eb53b4f393f213722519` | 是；逐字节相同 |
| `IsDriverViewEnabled` | 是 / 1 bytes | `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9` | 是；逐字节相同 |

`final-verified.jsonl` 在最终恢复后重新读取五项 base64、存在性和哈希，与初始完全相同；`preservation.json` 又独立比较原始 bytes，五项全 true。相同证据还证明原有 287 个 dirty 文件和 7 个 store 插件文件均未变。

最终运行态（UTC `2026-10-23T12:37:14Z`）：

```text
hostname=comma-9c13c9f5
hardware_profile=c3xl
head=cc129b8829c8fd6d170ef75d9857840cb25ed726
IsOffroad=1
IsEngaged=0
started=false
comma.service=active
Panda_samples=51
controlsAllowed=false
faultStatus=none
params_exact=5/5
store_files_exact=7/7
existing_dirty_files_exact=287/287
```

## 编号问题

1. **环境：生产模型索引下载失败，仍未修复。** 60 秒日志出现 `Failed to establish a new connection: [Errno 101] Network is unreachable`，目标为 raw.githubusercontent.com 的 driving_models_v25.json，并回退到过期缓存。UI/manager 仍存活；这不影响本轮指定 store 模块加载门，但不能据此声称模型联网/更新成功。`ui-runtime.log` 保留原文。生产启动还包含既有 symlink 和 USB 尝试提示；随后 SPI 成功及连续 Panda 样本已证实，未将它们当作 Panda 不可用。
2. **验证编排：首次最终门执行过早。** `run-tests.sh` 在启动服务后立即跑 preflight，manager 清掉并重建 IsOffroad 的窗口触发 `preflight.py:44 AssertionError`；整段编排 rc=1，原文保留在 `test-run.log`、`test-run.exit`，空的首轮最终输出保留为 `final-attempt1.jsonl`。大屏 E2E 本身 rc=0/errors=[]，九次截图也都 rc=0；未将该编排失败改写为一次全成功运行。稳定后的只读门和最终门均通过，没有在失败窗口继续产品测试。
3. **验证编排：只在重启前恢复 driver view 不足以保留存在性。** manager 启动会删除测试前存在的 `IsDriverViewEnabled=0`；补图后的最终快照实际发现了这个差异。现已在服务稳定后从原始备份补回，最终 51 个安全样本和两份字节比较均通过。没有通过改 Params 类型或产品代码来规避。

旧地址 SSH 超时和实际起点已前进到 b313000 是已解决的身份/传输差异，列于身份表，不重复计作产品缺陷。

## 证据、哈希与复现

仓库目录：`docs/validation/xpilot-c3xl-20261023-v7/`。`SHA256SUMS` 覆盖本目录所有其它文件；PNG 共 49 张，每张均小于 400000 bytes。`.gitattributes` 与 v6 相同，所有层级 PNG 的 filter/diff/merge/text 均 unset，实际 PNG 进入 Git。

只有一张原始页面图超过限制：`big-screen/page-plugins-category.png` 从 493588 bytes 以 zlib level 9 无损重压为 376487 bytes；解压扫描线字节完全相同，源/目标 SHA-256 与扫描线哈希见 `png-lossless-compression.json`。27 张 tile PNG 未重编码。设备保留原始图。

| 文件/目录 | 内容 |
|---|---|
| `REPORT.md`、`result.json`、`SHA256SUMS` | 中文报告、机器摘要、全部证据哈希 |
| `source.diffstat`、`changes.log`、`panda-safety.diffstat` | v6→v7 变化与 safety 零差异 |
| `bundle.json`、`bundle-verify.log`、`bundle-heads.log`、`deploy.log` | bundle 身份、两端校验和 ff-only |
| `build.log`、`build.exit` | 原生 SCons 完整日志和 rc |
| `preflight.py`、`panda-read.py`、各 gate JSON/JSONL | 可重复的只读身份、Panda 版本/签名、运行态、安全样本 |
| `production.sh`、`production-runtime.json`、`ui-runtime.log` | 60 秒生产窗口和 601 个连续安全样本 |
| `check-exit-codes.tsv`、`checks/` | 八项 rc 和完整输出 |
| `big-screen/`、`big-screen.log`、`big-screen.exit` | 原样 E2E result.json 与 21 张页面/布局截图 |
| `tile_size_e2e.py`、`tile-driver-origin.json`、`tile-results/`、`tile-size-*.log`、`tile-exit-codes.tsv` | v6 驱动来源、九次运行结构化结果和日志 |
| 根目录 27 张 `tile-*.png` | 9 tiles × small/medium/wide 原图 |
| `pixel-check.py`、`pixel-results.json`、`pixel-ffmpeg.json` | v6 校准、v7 像素判定、每次 ffmpeg 完整命令/输出 |
| `plugin-source/`、`plugin-source*.py/.sh/.log/.exit` | store Source 行补图和生产页面验证 |
| `params-before.json`、`restore-params.py`、各恢复 JSON、`final-verified.jsonl`、`preservation.json` | 五项原始字节、最终还原和文件内容保全 |
| `test-run.log/.exit`、`final-attempt1.jsonl` | 原始首次最终门失败，未覆盖 |

设备原始路径：

- `/data/xpilot-install-20261022/xpilot-20261023-v7.bundle`
- `/data/xpilot-ui-check-v7-evidence/`
- `/data/xpilot-ui-check-v7/`
- `/data/xpilot-ui-check-v7-tiles/`
- `/data/xpilot-ui-check-v7-plugin-source/`

运行方法保存在 `deploy.sh`、`production.sh`、`run-tests.sh`、`plugin-source.sh`；它们是**本轮操作记录**，路径含已存在的证据目录，不能不经身份/安全门就在同名路径盲目重跑。复现应保留已有证据，用新输出目录，沿用相同源提交、环境和命令。最终验真：

```bash
cd docs/validation/xpilot-c3xl-20261023-v7
shasum -a 256 -c SHA256SUMS
```

## 回退与未验证边界

- 本轮没有执行回退。设备保留 `task-X-20261023-10-before` 指向实际起点 `b3130009d9bd3a61e143bf1e34dd48cc9ef6834f`，同时保留增量 bundle、构建物和五项原始字节。需要回退时须在新任务重新满足身份/离线/未接合/Panda 版本与签名门，使用隔离 candidate 和原生构建；不得 reset/clean 当前工作树或触发 flash。
- 本报告的 Git 提交仅包含本目录；撤销报告可对该文档提交使用 `git revert`，不会改变设备部署。完整文档提交 SHA 由最终交付和远端任务分支确定。
- 没有真实道路、onroad 相机、控制闭环、车辆 CAN、BMS 数据或 engagement 验证；没有验证卸载/安装、重启、关机、reset 等危险确认动作。只有原样 E2E 的合成布局。
- 没有测试未来任意长文本或旧 IP 在新版本上的合成输入；当前无地图/前车/BMS 数据时的占位显示不等于这些车端功能已经验证。
- 没有改变产品源码、依赖、网络、SSH 或 store 插件，Panda 固件本轮未写入。主机报告提交与设备运行提交严格分开。

REPORT X-20261023-10
