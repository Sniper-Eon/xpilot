# X-20261023-11 C3XL 可替换模型栈验证记录

## 结论

**DONE；失败模式 a–d 全部 PASS。** 已在唯一指定设备部署 `f7af016516db4043bec0af24e6d3133fd864dfc9`，完成原生 SCons、默认 SP 栈、8 项检查、原样大屏 E2E、包含 E7 的商店 E2E，以及真实商店目录中的 op_models 安装、启用、关闭和卸载。没有修改产品源码。

最终服务 active，恢复默认 `sp_models`。五项指定参数的存在性和原始字节全部恢复；`ExtOpModels` 与 `/data/xpilot_plugins/op_models` 均不存在；原有 287 个 dirty 文件、商店原有全部 9 个文件的路径集合和 SHA-256 完全一致，其中 overspeed_warning 的 7 个文件（含既有缓存）未变。

**op_modeld 的真实 onroad 推理：NOT RUN。** 全程停车、未接合，没有模拟 onroad 启动该进程。商店 E7 只计算进程启动条件；大屏 E2E 自带的 synthetic onroad 只渲染独立 UI 布局，未改变设备行驶状态。

## 身份、规则与部署

已完整读取 `AGENTS.md`、`XPILOT.md`，并核对目标版本新增的规则 6、4.3 `role:perception.model` 和第 10 节 `sp_models`。完整读取并复用 [v7 报告](https://github.com/onemiless/openpilot/blob/695b2843691c5f26ef0abedf9b496fed1dc863ae/docs/validation/xpilot-c3xl-20261023-v7/REPORT.md) 的只读门、bundle、ff-only、原生构建、GPU 截图与参数恢复方法。v7 报告哈希见 `source-identity.json`。按用户明确指定的例外创建文档任务分支；没有创建另一个工作树，也没有修改主工程 checkout。

| 项目 | 实测值 |
|---|---|
| 验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source` |
| 主机初始分支 / HEAD | `task/X-20261023-10` / `695b2843691c5f26ef0abedf9b496fed1dc863ae`，干净 |
| 本轮文档分支 | `task/X-20261023-11`，从目标 `f7af016516db4043bec0af24e6d3133fd864dfc9` 创建 |
| 主仓库远端 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git` |
| 唯一设备传输 | `comma@172.16.1.202`，全部 SSH/SCP 使用 `BatchMode=yes`、`StrictHostKeyChecking=yes` |
| hostname / hardware_profile | `comma-9c13c9f5` / `c3xl` |
| 活动路径 | `/data/openpilot -> /data/xpilot-install-20261022/candidate` |
| 设备实际起点 | 分支 `xpilot`，`cc129b8829c8fd6d170ef75d9857840cb25ed726` |
| 设备最终活动提交 | **`f7af016516db4043bec0af24e6d3133fd864dfc9`** |
| 插件仓库 | `onemiless/xpilot-plugins`，main `edab6ec127a40c6e4d56e08409d9d9f53435c075`，主机和设备 checkout 均干净 |
| 设备插件仓库副本 | `/data/xpilot-install-20261022/xpilot-X-20261023-11-plugins` |
| bundle | `/data/xpilot-install-20261022/xpilot-X-20261023-11.bundle`，6786 bytes |
| bundle SHA-256 | `427bc2ce36b40bbeec3ebffa347598d05734d99d835f280f80eaf04df4f71a7f` |
| op_models 发布包 SHA-256 | `6f160751d990e1ba11e42b6d42f94eb5b9c4ce10175b87f5aabc3fcaf095a4a1` |

`changes.log` 仅有 `7095968`、`e2ec0d0`、`f7af016` 三个提交；`source.diffstat` 记录全部 11 个变化路径。`panda-safety.diffstat` 为 0 bytes。部署前逐文件哈希设备 dirty 文件，并确认与本轮更新路径无交集；没有 reset、clean 或覆盖既有差异。bundle 两端校验通过，设备 `git merge --ff-only` 成功，保留 `task-X-20261023-11-before` 指向实际起点。

本地报告提交与设备活动提交分开：报告提交只新增本目录，不部署到设备；完整文档提交 SHA 由任务分支和最终交付记录确定。只推送 `task/X-20261023-11`，不推送 xpilot，不 force-push。

## 安全与构建

沿用 v7 `PandaSpiHandle.get_info/controlRead` 读取方法，未调用 `Panda.__init__/connect`，没有 flash 或手工 CAN 操作。部署前、构建后、每次服务恢复前、截图前与最终门均检查固件版本/完整签名和 health。

| 检查 | 结果 |
|---|---|
| serial / raw type | `1d002d000a51303436323838` / `09`，Tres，应用态非 bootstub |
| 读回 / 本地预期版本 | 均 `DEV-087a2e7f-DEBUG` |
| 完整 128-byte 签名 | 读回和预期完全相等，全文在各 Panda JSON/JSONL |
| firmware SHA-256 | `7153811862ea8027d4ada5f5762f0e67abc15d02a893fa5ca4159ffc40ed093d`，前后相同 |
| health | controls_allowed=false，faults=0，fault_status=0，ignition_line=false，ignition_can=false |
| 默认生产窗口 | 60.019 秒，600 个连续 Panda 样本，无控制许可、无 fault；UI/pandad/hardwared 持续存活 |
| 各状态连续门 | 默认 51、启用 51、关闭 51、卸载 50、最终 50 个 Panda 样本，均停车、未接合、无点火、无控制许可 |
| 原生构建 | **rc=0**，`real 13.00 / user 11.63 / sys 1.42` 秒 |

原生构建命令：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

`build.log` 结尾为 `scons: done building targets.`，`build.exit=0`。先通过构建后 Panda 门，再启动目标 manager。最终只读复核在 `final-verified.stdout`，其中最后一行 `active` 是独立的 systemctl 输出；机器可读安全快照为 `final.jsonl`。

## 失败模式 a–d

| 模式 | 结果 | 实测证据 |
|---|---|---|
| a：默认 SP 进程停掉或 Models 磁贴消失 | **PASS** | owner=sp_models；models_manager、modeld_warmup running=true；`default-ui/result.json` 中 models 已放置，截图可见 |
| b：启用后 SP 停车进程仍运行、原 Models 未隐藏或 op_models 缺失 | **PASS** | SP 四个模型进程全部 running=false；op_modeld 停车时也不运行；owner=op_models，conflicts={sp_models: op_models}；页面显示 SP Model Manager [conflict]、openpilot Model 开关开启；placed 含 op_models、不含 models |
| c：关闭或卸载后 SP 栈 / Models 未恢复 | **PASS** | 关闭和卸载分别重启验证；两次 owner=sp_models，两进程 running=true，models 可见、op_models 不可见；卸载后只剩原 overspeed_warning |
| d：UI traceback / 插件加载错误 | **PASS** | 默认 60 秒生产日志、四种状态启动日志与 GPU 驱动、大屏 E2E 均无 UI traceback 或插件导入/构造/绘制异常；各状态 LOAD_ERRORS={}，插件 fault 为空 |

启用状态的替换磁贴 **id 为 `op_models`，显示标题仍为 `Models`**，内容是 `openpilot / bundled model`。验收按实际 tile id 和所属插件判断，没有把这个标题误判为旧 SP 磁贴仍存在。

## 各状态 manager 进程与角色

表中 PID=0 表示 manager 明确报告 running=false；“未注册”表示该进程不在该次 managerState 中。全部行的 modeld 和 modeld_tinygrad 均 running=false / PID=0；没有运行 onroad 推理。

| 状态（UTC） | owner | models_manager | modeld_warmup | op_modeld | UI / pandad / hardwared PID |
|---|---|---|---|---|---|
| 默认 13:24:14 | sp_models | 202260，running | 202267，running | 未注册 | 202231 / 202242 / 202245 |
| 启用 13:27:01 | op_models | 0，stopped | 0，stopped | 0，stopped | 205700 / 205703 / 205710 |
| 关闭 13:27:35 | sp_models | 206621，running | 206624，running | 0，stopped | 206611 / 206613 / 206616 |
| 卸载 13:28:09 | sp_models | 207590，running | 207591，running | 未注册 | 207575 / 207579 / 207581 |
| 最终 13:28:44 | sp_models | 208459，running | 208460，running | 未注册 | 208449 / 208451 / 208452 |

以上进程的 exitCode 均为 0。完整 managerState 列表在 `*-running.jsonl` 和 `final.jsonl`；启用、关闭、卸载还各有 `*-processes.json` 与完整 `*-ps.txt`，启用态 ps 中没有残留 SP 模型进程。

## 检查与 E2E

服务停止、原生库已构建后，逐个执行设备目标树的所有 `tools/sp_tesla_e2e/*_check.py`，未修改脚本或移走 overspeed_warning。

| 脚本 | rc |
|---|---:|
| external_bridge_check.py | 0 |
| manifest_check.py | 0 |
| offroad_pages_check.py | 0 |
| phase2_check.py | 0 |
| phase3_check.py | 0 |
| plugin_host_check.py | 0 |
| store_check.py | 0 |
| tile_layout_check.py | 0 |

| E2E / 附加验证 | 结果 |
|---|---|
| 原样 big_screen_e2e.py | **rc=0，passed=true，errors=[]**，24 个 case 记录 |
| 原样 store_e2e.py | **rc=0，errors=[]**，installed=[op_models, overspeed_warning]；目标 f7af016 的 E7 已包含并执行 |
| 默认/启用/关闭/卸载 GPU 页面驱动 | 四次 passed=true；启用、关闭、卸载各 rc=0，默认驱动成功后才继续检查 |
| 插件仓库 tools/build_index.py --check | rc=0；tn_long 未构建原生部分，按该脚本原有规则跳过，与本次 op_models 无关 |
| 最终 preservation.py | rc=0，passed=true；参数/dirty/store 文件全部一致 |

大屏 E2E 的三个原有条件跳过如实保留：Small models 子页 `no qcom bundles available`，driver camera 和 regulatory 两行 `row hidden on this hardware`。Models 主页面本身已通过。没有把跳过项写成已验证模型下载或真实相机。

使用的设备环境和原样命令：

```bash
cd /data/openpilot
export PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo
export PYTHONDONTWRITEBYTECODE=1
python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v8
python3 tools/sp_tesla_e2e/store_e2e.py --repo /data/xpilot-install-20261022/xpilot-X-20261023-11-plugins
```

这些静态/逻辑检查、GPU UI E2E、生产进程证据分别记录，均不代替道路、模型推理或车辆安全验证。

## 真实商店切换与截图

真实安装使用 `openpilot.tesla.store.fetch_index/install`，安装目录断言为 `/data/xpilot_plugins`。将 edab6ec 原索引的 URL 改为设备副本中的 `file://` 发布包，另存 `local-index.json`；包内容与原索引 SHA-256 未改，设备无需互联网。仅安装 op_models；`store_e2e.py` 的安装则在其自有临时目录，二者没有混淆。

安装成功后通过 `plugin_params.ParamsView.put_bool('ExtOpModels', True)` 启用，再启动服务取运行态证据。随后停服，用同一 ParamsView 写 False，重启验证关闭态。再次停服，先 `ParamsView.remove('ExtOpModels')`，再 `store.uninstall('op_models')`，重启验证卸载态。原接口卸载保留参数，所以显式清理本轮参数；没有删除其他插件或参数。

截图沿用 v7 方法：停止 comma.service 以独占 DRM，在设备 GPU 上运行生产 `BigScreenHost`、实际插件 tile 与 PluginsPage，通过 render texture 导出 2160×1080 图。使用保存的原始布局；没有为了让磁贴出现而改变布局。截图对应真实商店目录和开关状态；它们是生产组件在独立验证进程中的渲染，未声称抓取正在运行的服务 framebuffer，也未声称实体手指触摸。

| 状态 | tile 屏幕 | Plugins 页面 |
|---|---|---|
| 默认 | [models 可见](default-ui/tiles.png) | [SP 默认启用](default-ui/plugins.png) |
| 启用 | [op_models 可见、models 隐藏](enabled-ui/tiles.png) | [SP conflict、openpilot Model 开启](enabled-ui/plugins.png) |
| 关闭 | [models 恢复](disabled-ui/tiles.png) | [openpilot Model 关闭、SP 恢复](disabled-ui/plugins.png) |
| 卸载 | [models 仍正常](removed-ui/tiles.png) | [仅 SP 默认模型](removed-ui/plugins.png) |

29 张 PNG 全部小于 400000 bytes。三张超过限制的原图只重压 PNG IDAT 的 zlib 数据，解压扫描线逐字节相同；最终最大图为 365482 bytes。原始/最终哈希、大小和扫描线哈希记录在 `png-lossless-compression.json`；设备保留原图。

## 参数恢复、保全与最终安全态

第一次部署前保存五项存在性、大小、base64 原始字节与 SHA-256，见 `params-before.json`。各轮结束恢复后，**最后一次服务启动稳定后再恢复一次**，补回 manager 启动时清除的 `IsDriverViewEnabled=b'0'`；此后没有再重启服务。`params-restored-after-final-start.json` 明确只有该项需要补写。

| 参数 | 原始大小 | 最终相同的 SHA-256 | 字节恢复 |
|---|---:|---|---|
| XpilotTileLayout | 873 | `7d2e2f182f08e9cf92ab14d444b42078cf45f96fafcc693cfa1519149b7f3d46` | PASS |
| XpilotTileTheme | 8 | `1d261a8554d2da69b2e13445a8ee2a94dd10912a2bf5a0f3d3fe0698e5540f84` | PASS |
| XpilotBms | 1 | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` | PASS |
| CarPlatformBundle | 191 | `dfcc84df24862d499db2c9a7572af713b81f9592a740eb53b4f393f213722519` | PASS |
| IsDriverViewEnabled | 1 | `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9` | PASS |

五项原本都存在，最终也全部存在。`preservation.json` 独立读取文件字节与初始备份比较，并检查原有文件集合：dirty 287/287、store 9/9 完全相同；其中 store 包括布局/主题两文件与 overspeed_warning 七文件。`ExtOpModels` 在商店参数目录和 core Params 目录均不存在，op_models 目录不存在。

最终门：hostname 正确、c3xl、目标 HEAD、comma.service active、IsOffroad=true、IsEngaged=false、deviceState.started=false；Panda controlsAllowed=false、faultStatus=none、faults=[]、两路 ignition=false。最终 SP 两进程、UI、pandad、hardwared 均 running=true、exitCode=0。安全状态由连续消息与只读固件门共同证明。

## 编号问题

1. **环境：SP 模型索引联网仍失败。** 生产日志原文有 `ConnectionResetError(104, 'Connection reset by peer')`，以及 raw.githubusercontent.com 的 `Failed to establish a new connection: [Errno 101] Network is unreachable`，随后 `Failed to fetch fresh data. Using expired cache as fallback`。没有修改网络来规避；本轮只证明 SP 管理进程及替换机制，模型索引更新/下载未通过。大屏 Small models 子页因没有 qcom bundle 按原脚本跳过，和此环境限制一并保留。
2. **验证编排：首次启动后的只读门执行过早，已恢复。** 首次 `preflight.py:44` 在 IsOffroad 重建窗口触发 `AssertionError`，错误原文从工具输出保存在 `default-first-gate.stderr`。没有在该门失败时进行产品测试；稳定后重新通过完整门才继续。后续启用、关闭、卸载、最终恢复均先执行 `wait-stable.py`，再运行完整 preflight，全部成功。没有修改产品代码或写入 IsOffroad 来绕过门。

原日志中的 PWD symlink 提示和 `raylib: COMMA: Failed to initialize color correction` 也保留；截图导出、页面断言均成功，未观察到 UI traceback、插件加载错误或绘制 fault。这些诊断不等于模型联网或色彩校准已经验证。

## 证据、复现与回退

| 路径 | 内容 |
|---|---|
| REPORT.md、result.json、SHA256SUMS | 中文报告、结构化结果、全部证据哈希 |
| source-identity.json、changes.log、source.diffstat、panda-safety.diffstat | 两仓提交、包/索引哈希、变化范围、安全路径零差异 |
| bundle-verify.log、bundle-heads.log、deploy.sh、deploy.log、build.log、build.exit | 主机校验、设备校验/ff-only、原生构建 |
| preflight.py、panda-read.py、preflight.jsonl、pre-stop.jsonl、panda-*.json | v7 只读门及部署/切换前后的检查 |
| production.sh、production-runtime.json、ui-runtime.log、production-*.log | 默认栈 60 秒生产窗口和 600 个连续安全样本 |
| check-exit-codes.tsv、checks/ | 全部八项检查 rc 和完整输出 |
| big-screen/、big-screen.log、big-screen.exit | 原样大屏 E2E 结果与 21 张截图 |
| store-e2e.log、store-e2e.exit、plugin-index-check.log | 包含 E7 的商店 E2E、发布包重建一致性检查 |
| store-action.py、local-index.json、install-enable.json、disable.json、uninstall.json | 真实商店安装、开关与卸载结果 |
| model-ui-e2e.py、default-ui/、enabled-ui/、disabled-ui/、removed-ui/ | 四状态生产组件 GPU 截图、角色/冲突/磁贴断言 |
| swap.sh、swap.log、swap-ui-exit-codes.tsv、*-running.jsonl、*-processes.json、*-ps.txt | 实际服务重启与进程列表 |
| *-startup.log、*-ui.log、big-screen.log | 各状态生产和验证 UI 异常检查原始日志 |
| params-before.json、restore-params.py、params-restored-*.json、store-before.json、dirty-before.json、preservation.py/.json | 原始字节、恢复、文件内容保全 |
| final.jsonl、final-verified.stdout、final-stable.log | 最终和再次只读复核的服务、提交、安全态 |
| default-first-gate.stderr、startup-inspect.log、wait-stable.py | 首次启动窗口失败及后续稳定门 |
| recover.sh | 出错时清理本轮插件/参数并恢复服务的恢复路径；本次 swap 成功，未触发 |
| png-lossless-compression.json、verify-artifacts.py、artifact-verification.json | 图像无损重压记录、可重复的证据自检 |

设备原始证据仍在：

- `/data/xpilot-ui-check-v8-evidence/`
- `/data/xpilot-ui-check-v8/`
- `/data/xpilot-install-20261022/xpilot-X-20261023-11.bundle`
- `/data/xpilot-install-20261022/xpilot-X-20261023-11-plugins/`

本目录脚本是本次操作记录，包含已存在输出路径；复现时先重新满足身份、安全和独占 DRM 门，并用新的证据路径，勿盲目覆盖本轮产物。无需设备即可重新验证本轮证据：

```bash
cd docs/validation/xpilot-c3xl-20261023-v8
shasum -a 256 -c SHA256SUMS
python3 verify-artifacts.py
```

本次没有回退设备。保留的 `task-X-20261023-11-before` 指向 `cc129b8829c8fd6d170ef75d9857840cb25ed726`，增量 bundle 与原始参数备份均在。若另行请求版本回退，须重新通过设备/停车/Panda 门，在隔离 candidate 中原生构建并切换；不得 reset/clean 当前含既有差异的工作树。撤销本报告可用 `git revert <文档提交>`，不会改变设备部署。

未进行真实道路、onroad 模型推理、模型消息语义/时序、控制闭环、车辆 CAN、Panda flash、数据 reset、网络或 SSH 配置修改；未确认任何重启、关机、reset 或 openpilot 卸载操作。只安装/移除了本任务授权的 op_models。

REPORT X-20261023-11
