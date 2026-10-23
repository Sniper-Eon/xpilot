# REPORT X-20261023-16

status: DONE
device_head: 9258ebcb48981b95c81ff73471efb2979cc63727
report_branch: task/X-20261023-13

已完成授权清理、目标提交的 ff-only 部署、原生构建、X-13 停车验证及 Alpha longitudinal 开关。失败模式 a–f 全部 PASS。最终 comma.service active，IsOffroad=1、IsEngaged=0、deviceState.started=false；AlphaLongitudinalEnabled 在 60.068 秒后仍为 true，原始文件为 b'1'。它在下一次车辆启动时生效，本轮没有启动控制或验证纵向接管。

本轮没有修改产品源码。报告替换前一轮 BLOCKED 记录，只在已有文档分支上追加提交；文档提交完整 SHA 由本分支和最终交付记录确定，与设备活动提交分开。验证过程中有两项已恢复的脚本错误、一个商店公网索引问题，详见编号问题。

## 身份、来源与操作范围

| 项目 | 当前证据 |
|---|---|
| 验证 checkout | /Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source |
| 主机初始分支 / HEAD | task/X-20261023-13 / ae281f454c32f4b11408b682d9bba144fbdb02b4，干净 |
| 主仓库 origin | ssh://git@ssh.github.com:443/onemiless/openpilot.git |
| git fetch 后 origin/xpilot | 9258ebcb48981b95c81ff73471efb2979cc63727 |
| 文档远端起点 | origin/task/X-20261023-13 = ae281f454c32f4b11408b682d9bba144fbdb02b4；本地 ff-only 对齐后原地追加 |
| 唯一设备 | comma@172.16.1.202；hostname comma-9c13c9f5；/data/hardware_profile=c3xl |
| SSH 约束 | StrictHostKeyChecking=yes、UpdateHostKeys=no、BatchMode=yes；未改连接配置，未访问其他设备 |
| 活动路径 | /data/openpilot -> /data/xpilot-install-20261022/candidate |
| 设备部署前 / 后 | f7af016516db4043bec0af24e6d3133fd864dfc9 -> 9258ebcb48981b95c81ff73471efb2979cc63727，分支 xpilot |
| 主机 / 设备本轮证据 | /private/tmp/X-20261023-16 / /data/xpilot-X-20261023-16-evidence |
| 插件仓库 origin/main | cb3f428b54aa3745df4c82acb1b7152b225bfbcb，onemiless/xpilot-plugins |
| 设备插件仓库副本 | /data/xpilot-X-20261023-16-evidence/xpilot-plugins；HEAD=origin/main，干净，36 个仓库内容文件与主机哈希相同 |
| Part C 后安全快照时间 | 2026-10-23T16:43:33Z；发布前再次通过 final-recheck.jsonl 只读门 |

已先读 AGENTS.md、XPILOT.md 4.3/4.4、core_host.py、phase4_check.py，以及 origin/task/X-20261023-11 的 v8 REPORT.md 和指定 diag-X-20261023-15/REPORT.md、candidates.tsv。采用 ponytail skill，复用 v8 的门禁、只读 Panda、bundle、ff-only、原生 SCons、原始字节快照/恢复、服务恢复及 GPU 截图方法。源文件、前轮报告、诊断清单的哈希在 source-identity.json。失败模式在执行隔离检查前写入 FAILURE-MODES.txt 和各验证脚本头部；未编写产品代码或补写单元测试。

所有设备写入均在重新读取 IsOffroad=1 后执行；还检查 hostname/profile、IsEngaged、deviceState 和 Panda 状态。停服后的构建及检查沿用保留的 IsOffroad，未写入 IsOffroad 或伪造点火状态。没有切换或修改 /Users/mile/Desktop/mo-op 主工程，也没有新建分支/工作树；本机初始 checkout 干净，设备既有 dirty 文件采用哈希保全及更新路径交集检查。

## Part A：/data 清理

A1 先记录 readlink -f /data/openpilot 的结果。13 个批准路径及其解析路径均不等于、也不包含活动 target；通过整组预检后才删除。A2 对每个路径单独执行 sudo lsof，stderr 按要求丢弃，确认 lsof rc=0 且筛选匹配数为 0。A3 仅执行以下 13 个 sudo rm -rf，逐条记录命令、du 已分配字节及删除前后 statvfs 可用字节变化；未使用通配符。没有跳过项。

| 路径 | 删除前 allocated B | 删除时 df/statvfs 增量 B | 结果 |
|---|---:|---:|---|
| `/data/sp-sync-experiment-20261017` | 7187009536 | 7186993152 | DELETED，lsof=0 |
| `/data/agnos-offline-20261013` | 1029005312 | 1029005312 | DELETED，lsof=0 |
| `/data/nav-reboot-baseline-20261013` | 827559936 | 827559936 | DELETED，lsof=0 |
| `/data/navassist-track-p0-offline` | 827129856 | 827129856 | DELETED，lsof=0 |
| `/data/c3xl194_bmv4_20min_20260917` | 787677184 | 787677184 | DELETED，lsof=0 |
| `/data/openpilot-before-offline-20261013` | 653418496 | 653418496 | DELETED，lsof=0 |
| `/data/prebuild-baseline-20261013` | 630657024 | 630657024 | DELETED，lsof=0 |
| `/data/dev-sp-nav-prebuild-offline` | 630644736 | 630644736 | DELETED，lsof=0 |
| `/data/c3xl-1344-build` | 524570624 | 524570624 | DELETED，lsof=0 |
| `/data/c3xl-resolution-20261010` | 441757696 | 441757696 | DELETED，lsof=0 |
| `/data/dev-sp-nav-prebuild.tar.gz` | 375062528 | 375062528 | DELETED，lsof=0 |
| `/data/c3xl-ctm-1344-20260923` | 269312000 | 269312000 | DELETED，lsof=0 |
| `/data/c3xl-1344-evidence` | 246476800 | 246472704 | DELETED，lsof=0 |

13 项 du 合计 14430281728 B。目录分配字节、单次可用空间增量和全程 df 增量采用不同采样边界；后台日志写入及文件系统元数据会产生少量差值，不把它们强行当成完全相同的量。

| df -B1 /data | total B | used B | available B | Use% |
|---|---:|---:|---:|---:|
| 删除前 | 31526391808 | 24585302016 | 5313699840 | 83% |
| 删除后 | 31526391808 | 10155053056 | 19743948800 | 34% |
| 部署、构建、验证后 | 31526391808 | 10245214208 | 19653787648 | 35% |

A4：19743948800 >= 8589934592 B，PASS。最终空间仍高于门槛。完整执行记录在 free-data.py、free-data.log；free-data.stderr 为空。保留了 /data/openpilot 及其 target、safe_staging、模型目录、scons_cache、realdata、params 和 xpilot-install-20261022，未删除其他设备路径。

## Part B1：部署、原生构建与生产窗口

bundle 两端验证通过；SHA-256 为 da5e03c53e90025a551dd9d0bf35b6c2c5c960e790432d4303d9ae9c4eb6aad5，要求 f7af016 为前置对象。设备 git fetch bundle 后，17 个更新路径与原有 287 个 dirty 文件无交集；保留 task-X-20261023-16-before 指向 f7af016，然后停服、git merge --ff-only。没有 reset、clean、stash 或覆盖既有差异。panda/opendbc_repo 的两个提交间差异为空。

原生命令及环境：

```bash
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
/usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

构建 rc=0，real 214.09 / user 671.93 / sys 38.67 秒；结尾 scons: done building targets.。device/build.log:65 明确执行 capnpc，输入含 custom.capnp，输出到 cereal/gen/cpp；第 681 行编译 custom.capnp.o，第 682–683 行生成 libcereal.a；同时重新编译 log.capnp.o、socketmaster 和多个 camerad/loggerd/pandad 等 C++ 消费者并成功链接。真实 cereal enum 的 xpilotPluginFault=29；selfdrived 和 card 模块在设备成功导入。

| Panda 只读项目 | 结果 |
|---|---|
| 方法 | PandaSpiHandle.get_info/controlRead；Panda.__new__，未调用 Panda.__init__/connect |
| serial / raw type | 1d002d000a51303436323838 / 09，应用态非 bootstub |
| 读回 / 本地预期版本 | DEV-087a2e7f-DEBUG，匹配 |
| 128-byte 完整签名 | 读回与固件预期完全相同，完整 hex 保留在 preflight/final JSONL 和 panda JSON |
| firmware SHA-256 | 7153811862ea8027d4ada5f5762f0e67abc15d02a893fa5ca4159ffc40ed093d，前后相同 |
| health | controls_allowed=false，faults=0，fault_status=0，ignition_line=false，ignition_can=false |

构建后通过 Panda 门才启动 comma.service，再经过 wait-stable.py 与完整 preflight。生产窗口 60.100033 秒，601 个 Panda 样本均无点火/控制/fault，120 个 managerState 样本中的 UI/pandad/hardwared 持续 running=true、exitCode=0，PID 固定为 104559 / 104563 / 104564。生产 startup/runtime/end 日志未发现 UI/manager traceback、插件 load/draw 错误或 lead_card 异常；LOAD_ERRORS={}，plugin faults 为空。完整输出在 device/production-*.log、device/ui-runtime.log、device/production-runtime.json。

## 失败模式 a–f

| 模式 | 结果 | 证据及边界 |
|---|---|---|
| a：原生构建或新 cereal enum/C++ 消费者损坏 | PASS | SCons rc=0；capnpc 重新生成，custom.capnp.o/libcereal.a 和消费者编译链接成功；真实 enum=29 |
| b：默认 owners 改变 selfdrived/card 路径 | PASS | 真实 Params/CarParams 下 owners 正确、install_core 保持对象身份、core_alive=true、_gate.sm=None；未实例化/启动 onroad SelfdriveD |
| c：真实环境 phase4_check.py 失败 | PASS | 设备原样脚本 rc=0、errors=[]；运行于真实 cereal/msgq/zmq/Params 环境 |
| d：其余检查或两个 E2E 回归 | PASS | 其余 8 个检查全 rc=0；big_screen passed=true；store_e2e errors=[] |
| e：Plugins 默认接管/兜底插件缺失或能被关闭 | PASS | 两个分类均列出正确标题；enable_param=null、toggle_state=true、toggle_enabled=false；无可操作开关 |
| f：60 秒生产日志有 UI/manager traceback 或插件错误 | PASS | 60.100 秒日志无匹配；生产 UI/pandad/hardwared PID 不变，LOAD_ERRORS={}、faults 为空，GPU tile failures=0 |

phase4_check.py 本身使用脚本内置的假事件、替换插件和假时钟覆盖 C1–C12，**不是道路或真实挂死测试**。本轮没有再注入主机侧 zmq/msgq/Params 模块 stub；脚本保留其原有隔离逻辑，B3 另用设备真实 Params/CarParams 补齐默认路径证据。

## Part B2：检查与 E2E

停止 comma.service 以独占 DRM 后逐项执行，原样产品检查脚本未修改。每项完整 stdout/stderr 在 device/checks/，退出码在 device/check-exit-codes.tsv。

| 脚本 | rc |
|---|---:|
| external_bridge_check.py | 0 |
| manifest_check.py | 0 |
| offroad_pages_check.py | 0 |
| phase2_check.py | 0 |
| phase3_check.py | 0 |
| phase4_check.py | 0 |
| plugin_host_check.py | 0 |
| store_check.py | 0 |
| tile_layout_check.py | 0 |
| big_screen_e2e.py | 0 |
| store_e2e.py | 0 |
| default-path.py（本轮验证驱动） | 0 |
| core-ui-e2e.py（v8 GPU 方法的本轮驱动） | 0 |

原样 E2E 命令：

```bash
python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v9
python3 tools/sp_tesla_e2e/store_e2e.py --repo /data/xpilot-X-20261023-16-evidence/xpilot-plugins
```

big_screen：passed=true、errors=[]，24 个 case 记录，21 张 GPU 截图。保留原脚本三个条件跳过：Small models 子页没有 qcom bundles；driver camera 和 regulatory 在此硬件隐藏。synthetic onroad 仅在独立 UI 进程中渲染布局，没有修改 IsOffroad、模拟点火或启动 onroad 控制进程。

store_e2e：errors=[]、installed=[op_models, overspeed_warning]，包括 E7。脚本在 import 前将 XPILOT_PLUGINS_DIR 设为自己的 xp-e2e 临时目录，使用 localhost 服务提供 copied origin/main 的索引和归档；没有向真实 /data/xpilot_plugins 安装、升级或卸载。临时 E7 仅计算 should_run 条件，不启动 op_modeld。真实 overspeed_warning 保持 1.0.0。

## Part B3：真实默认路径输出

完整 JSON 在 [device/default-path.json](device/default-path.json)。使用 CarParamsPersistent 解码出的 Tesla Model Y 参数构造 plugins.CarPlugins；未执行任何 observe_can/control_sends 钩子。用真实 CP/Params 和三个占位对象验证 install_core 提前返回，未实例化完整 SelfdriveD；成功导入真实 selfdrived/card 模块。

```json
{
  "brand": "tesla",
  "carFingerprint": "TESLA_MODEL_Y",
  "role:engagement.state": "sp_engagement",
  "role:safety.fallback": "sp_safety_fallback",
  "core_alive": true,
  "gate_sm_is_none": true,
  "install_core_noop": true,
  "xpilotPluginFault_enum": 29,
  "LOAD_ERRORS": {},
  "faults": null
}
```

真实模块位置：Params_module=openpilot.common.params；zmq=/usr/local/venv/lib/python3.12/site-packages/zmq/__init__.py；msgq=/data/openpilot/msgq/__init__.py。B3 的隔离占位对象只用于比较 default install 是否改写对象，不能证明 onroad 的时序或控制闭环。

## Part B4：截图、参数恢复与服务恢复

采用 v8 方法：停服独占 DRM，设备 GPU 上渲染生产 BigScreenHost 和 PluginsPage，通过 render texture 导出 2160×1080 图；没有操作真实服务 framebuffer 或实体触屏。使用原始布局，lead_card 也实际绘制成功。

| 分类 | 截图 | 结果 |
|---|---|---|
| Engagement | [SP Engagement](device/core-ui/sp_engagement.png) | 369924 B；始终开启、控件不可操作 |
| Safety Fallback & Autopilot Handoff | [SP Safety Fallback](device/core-ui/sp_safety_fallback.png) | 315657 B；始终开启、控件不可操作 |
| 原始停车磁贴 | [tiles](device/core-ui/tiles.png) | 313074 B；lead_card 无绘制错误 |

页面仍绘制开启状态的 toggle 图形；本轮验收明确为 **没有可操作开关**，并未宣称图形不存在。运行时断言 action.enabled=false、state=true、enable_param=None。24 张 PNG 全部 <400000 B，最大 370814 B；两张原图只无损重压 IDAT，解压扫描线哈希不变。设备保留原图，本目录 png-lossless-compression.json 记录原始/最终大小与哈希，verify-artifacts.py 独立重解码核验。

部署前已保存以下六项存在性、base64 原始字节和 SHA-256。测试后恢复一次，最终服务启动稳定后再恢复一次，以补回 manager 启动时清除的 IsDriverViewEnabled=b'0'；之后未再重启服务。下表是 **Part C 之前** 六项全部逐字节恢复的结果：

| 参数 | 原始存在性 | 恢复后 SHA-256 | 字节恢复 |
|---|---|---|---|
| XpilotTileLayout | 存在 | d73ea8f49dbf49e97680419e51ec608cd8af9d82028c6297dddf56088c277838 | PASS |
| XpilotTileTheme | 存在 | 1d261a8554d2da69b2e13445a8ee2a94dd10912a2bf5a0f3d3fe0698e5540f84 | PASS |
| XpilotBms | 存在 | 6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b | PASS |
| CarPlatformBundle | 存在 | dfcc84df24862d499db2c9a7572af713b81f9592a740eb53b4f393f213722519 | PASS |
| IsDriverViewEnabled | 存在 | 5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9 | PASS |
| AlphaLongitudinalEnabled | 不存在 | NA | PASS |

XpilotTileLayout/Theme 位于 /data/xpilot_plugins/.params，其余位于 /data/params/d。device/params-before.json、device/params-restored-after-final-start.json、device/final-before-alpha.jsonl 保留完整证明。Part C 后只有 Alpha 按用户要求由不存在改为 b'1'；其余五项仍逐字节一致。

最终 device/preservation.json：原有 dirty 287/287 内容哈希一致，商店全部 10/10 文件的集合与哈希一致（含原有缓存、ExtOverspeedWarning 及布局/主题），overspeed_warning=1.0.0。已安装插件未改动。最终服务 active，最新活动 HEAD 正确；最终 preflight 的 deviceState/pandaStates/managerState alive，停车、未接合、无点火、无控制许可、无 fault，固件签名再次一致。

## Part C：Alpha openpilot longitudinal

CarParamsPersistent 通过 capnp 的 car.CarParams 解码：TESLA_MODEL_Y，alphaLongitudinalAvailable=true，openpilotLongitudinalControl=false。没有修改 CarParams、能力字段或其他开关。初始 Alpha 参数不存在。第一次异步写入后最终落盘为 true；为获得可重复的确认，最终有效验证使用同一 Params.put_bool 的 block=True 等待落盘：

```python
Params().put_bool("AlphaLongitudinalEnabled", True, block=True)
```

| 读回点 | 参数值 | 状态 |
|---|---|---|
| 最终有效验证开始前 | true | 首次异步写入已落盘 |
| 同步写入后立即 | true | get_bool=true、typed get=true |
| 60.067572 秒后 | true | removed=false，服务 active，601 个安全样本通过 |
| 最终原始文件 | b'1' | SHA-256=6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b |

当时 CarParams 临时参数不存在、CarParamsPersistent 存在且 alphaLongitudinalAvailable=true；UI 从 persistent CP 读取能力，没有清除此开关。保留的 openpilotLongitudinalControl=false 是本次读取到的既存 CP 字段，不等同于参数未设置或下次启动车辆已应用。完整 before/immediate/after_60s 输出在 device/alpha-long.jsonl；最终服务和安全状态在 device/final.jsonl。

## 编号问题

1. **验证脚本错误，已恢复：异步写入后立即断言过早。** 第一次默认 put_bool(block=False) 后读取仍为空，alpha-long.py:25 的 assert p.get_bool(...) 抛出 AssertionError。该次后台写入随后已落盘。保留 device/alpha-long-attempt1.jsonl、device/alpha-long.py 和 final-run.log；最终改为 block=True，完成独立 60 秒观察。不是 UI 删除参数的证据。
2. **验证脚本错误，已恢复：将 typed Params 值当成 bytes。** 第二次尝试在写入前的日志输出抛 AttributeError: 'bool' object has no attribute 'hex'。Params.get 对 BOOL 返回 bool；该次尚未执行新写入。保留 device/alpha-long-persisted.py、空的 attempt2 输出及 final-run-persisted.log；最终驱动直接记录 bool，原始字节另由最终文件哈希证明。最终有效驱动为 device/alpha-long-final.py，rc=0。
3. **环境/显示问题，未修改：公网商店及模型索引连接被重置。** Safety Fallback 截图的 Refresh 错误文字挤出按钮区域。随后仅调用 fetch_index 只读复核，返回 entry_count=0、精确错误 `index: <urlopen error [Errno 104] Connection reset by peer>`，见 live-store-index.json。没有改网络或商店代码。使用设备本地副本/localhost 的 store_e2e 成功不证明公网索引可用；生产 models_manager 同时反复报告 `Request transport error while fetching models: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))` 和 `Failed to fetch fresh data. Using expired cache as fallback`；原文定位在 network-errors.txt。模型新索引/下载仍未证明可用。这些是已捕获的联网失败，没有 UI/manager traceback 或插件导入错误，不影响本次 a–f 的停车验收。

GPU 验证日志另外保留 raylib: COMMA: Failed to initialize color correction，以及 PWD symlink 提示；截图、页面断言和 E2E 成功，未将这些诊断写成色彩校准已通过。两次验证驱动异常发生在 Part C 的独立 shell 中，不在 60 秒生产日志窗口，未造成服务停止或产品源码改动。

## NOT RUN

- onroad engagement。
- 真实 selfdrived 挂死时的 card gate / 实际 CAN 发送停止时间。
- 实体 MADS 按钮和车辆输入操作。
- 全部封闭场地项目。
- 下一次车辆启动后的 Alpha 实际纵向控制效果、控制闭环和道路安全资格。
- Small models 下载/执行、此硬件隐藏的 driver camera/regulatory 子页、实体触摸和色彩校准。

没有进行驾驶、点火模拟、手工 CAN、Panda flash、数据 reset、网络/SSH 配置修改，未确认任何重启、关机、reset、卸载；未安装/更新/移除真实商店插件。

## 证据、复核与回退边界

| 路径 | 内容 |
|---|---|
| source-identity.json、plugins-copy-proof.json | 主机分支/目标、源文件/前轮记录哈希、插件副本 36 文件哈希 |
| free-data.py/.log/.stderr | 固定白名单、活动路径保护、逐路径 lsof/删除/字节记录和 df |
| device/deploy.sh、deploy.log、bundle-*.log、device/target.bundle | bundle、交集检查、保留 ref、ff-only 部署 |
| device/build.log/.exit、device/panda-*.json | 原生 cereal/C++ 构建及前后只读固件门 |
| device/preflight.py、device/wait-stable.py、device/*running.jsonl、device/final*.jsonl | 参数快照、持续安全门、服务与最终状态 |
| device/production.sh、device/production-runtime.json、device/*runtime.log、device/production-*.log | 60 秒生产窗口和连续安全/进程样本 |
| device/checks、device/check-exit-codes.tsv、device/big-screen、device/store-e2e.log | 九项检查、24 个 UI case、临时商店 E2E |
| device/default-path.py/.json/.exit、device/core-ui-e2e.py、device/core-ui | 真实默认路径、GPU 分类截图和不可操作控件断言 |
| device/restore-params.py、device/params-*.json、device/preservation.py/.json | 原始字节恢复与 dirty/store 文件保全 |
| device/alpha-long*.py、device/alpha-long*.jsonl、final-run*.log | 两次驱动错误和最终 60 秒 Alpha 结果 |
| live-store-index.json/.stderr | 公网索引的只读复核和精确错误 |
| png-lossless-compression.json、device-original-hashes.json、SHA256SUMS、verify-artifacts.py | 原图哈希、无损重压记录及离线复核 |

只读证据复核命令：

```bash
cd docs/validation/xpilot-c3xl-20261023-v9
shasum -a 256 -c SHA256SUMS
python3 verify-artifacts.py
```

设备原始证据仍在 /data/xpilot-X-20261023-16-evidence、/data/xpilot-ui-check-v9；插件 source 副本和 bundle 在前者中。脚本是本轮已执行的操作记录，包含本轮既有输出路径，不应直接重跑覆盖证据。设备保留 task-X-20261023-16-before=f7af016，可用于另行授权的恢复；本轮没有版本回退。撤销文档用 git revert <文档提交>，不会回退设备或清掉 Alpha 参数。

未推送 xpilot，未 force-push；只推送 task/X-20261023-13，提交范围严格限于本目录。下一次车辆启动和全部道路项目仍未验证。
