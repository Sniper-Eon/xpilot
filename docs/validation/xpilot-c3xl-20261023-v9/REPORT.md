# X-20261023-13 C3XL 可替换接管与安全兜底验证记录

## 结论

**BLOCKED：唯一授权设备 `comma@172.16.1.202:22` 不可达，四次 SSH 均 rc=255。未部署目标提交，未执行任何设备验证。** 连接失败发生在 hostname、安全态与 Panda 只读门之前，因此没有停止服务、上传文件、修改参数或操作商店插件。

本报告的失败模式 a–f 均记 **FAIL / NOT RUN**：表示验收尚未完成，不表示已观察到六个产品缺陷。没有使用主机 stub 结果、上一轮报告或源码阅读代替本轮真实设备证据。

## 身份与范围

| 项目 | 结果 |
|---|---|
| 验证 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source` |
| 主机初始分支 / HEAD | `task/X-20261023-11` / `e656a13f8d228fd61b144a59bf6145f10ac1c45d`，干净 |
| 目标仓库 | `github.com/onemiless/openpilot` |
| origin | `ssh://git@ssh.github.com:443/onemiless/openpilot.git` |
| fetch 后 origin/xpilot / 完整目标 SHA | `e60f99c0d9cb14e39711d2716b2ba694b28ce9d3` |
| 本轮文档分支 | `task/X-20261023-13`，从上述目标 SHA 创建 |
| 唯一设备 | `comma@172.16.1.202` |
| 必须匹配的 hostname / hardware_profile | `comma-9c13c9f5` / `c3xl`；本轮未能读回 |
| 用户给定及 v8 记录的设备起点 | `f7af016516db4043bec0af24e6d3133fd864dfc9`；本轮未核实 |
| 本轮设备活动 HEAD | **UNKNOWN**；SSH 未建立，不能声称仍为 f7af016 或已变为 e60f99c |
| 本轮源码改动 | 无；文档提交仅包含本目录 |

已完整读取 `AGENTS.md`、目标版本 `XPILOT.md` 4.3/4.4、`openpilot/tesla/core_host.py`、`tools/sp_tesla_e2e/phase4_check.py`，以及上一轮任务分支中的 [v8 报告](https://github.com/onemiless/openpilot/blob/e656a13f8d228fd61b144a59bf6145f10ac1c45d/docs/validation/xpilot-c3xl-20261023-v8/REPORT.md)。采用 ponytail 流程，范围限于部署、验证与记录；没有修改产品源码或补写单元测试。

已读取并准备复用 v8 的 preflight、Panda SPI get_info/controlRead、bundle + ff-only、原生 SCons、参数原始字节恢复、停服独占 DRM 截图、启动稳定门与最终安全检查方法。**这些设备操作本轮均未开始。** 用户明确授权本轮任务分支，因此没有在 xpilot 上提交，也没有创建其他工作树。未操作 `/Users/mile/Desktop/mo-op` 主工程 checkout。

## 连接失败与安全边界

全部尝试只指向 `172.16.1.202`，均使用 `BatchMode=yes` 和 `StrictHostKeyChecking=yes`。第 2–4 次另设 `ConnectTimeout=10`、`ConnectionAttempts=1`。没有改网络或 SSH 配置，也没有尝试其他设备、地址或端口。

| 次数 | UTC 起始时间 | rc | 精确 stderr 文本 |
|---|---|---:|---|
| 1 | 未单独采集 | 255 | `ssh: connect to host 172.16.1.202 port 22: Operation timed out` |
| 2 | 未单独采集 | 255 | `ssh: connect to host 172.16.1.202 port 22: Host is down` |
| 3 | 2026-10-23T14:19:12.570706+00:00 | 255 | `ssh: connect to host 172.16.1.202 port 22: Operation timed out` |
| 4 | 2026-10-23T14:20:08.792715+00:00 | 255 | `ssh: connect to host 172.16.1.202 port 22: Operation timed out` |

第 1–2 次错误从工具返回值转录至 `initial-ssh-errors.log`；第 3–4 次由 subprocess 直接记录完整命令、时间、rc、stdout 和 stderr 至 `ssh-attempt-3.json`、`ssh-attempt-4.json`。所有尝试的远端 stdout 均为空。连接错误无法确定设备本身、电源或网络的具体原因。

没有设备访问，故未读取 IsOffroad、IsEngaged、deviceState、pandaStates、managerState 或 Panda 固件/完整签名。不能确认本轮设备停放、安全态或服务状态。没有调用 Panda 构造/connect、手工 CAN、flash、点火模拟、onroad selfdrived，也没有确认重启、关机、reset 或卸载。

## 主机准备与构建状态

主机已执行 `git fetch origin`，使用 `git rev-parse e60f99c0d9` 获得完整 SHA。`changes.log` 与 `source.diffstat` 记录 f7af016 至目标的提交和 16 个变化路径；`panda-safety.diffstat` 为零字节，仅证明这两个提交间 panda/opendbc 路径无差异，不是运行时或固件验证。

主机已生成 `/private/tmp/xpilot-X-20261023-13.bundle`，包含目标 origin/xpilot，要求前置提交 f7af016。`git bundle verify` **rc=0**；完整 SHA-256 为 `9a3ba2573031cdd4045491c1689e4619aece2450a88c7dced737255fda24afd7`。大小、源文件哈希及 v8 报告哈希见 `source-identity.json`。bundle 尚未上传；没有设备 ff-only 合并。

| 构建验收 | 结果 |
|---|---|
| 设备原生 SCons | NOT RUN，rc=NA |
| `custom.capnp` 新增 `xpilotPluginFault @29` | 源码差异已读取；设备生成物未验证 |
| cereal 重新生成 | **未验证，不能声称已重新生成** |
| cereal/C++ 消费者编译与加载 | NOT RUN |
| 构建后服务启动与 60 秒生产日志 | NOT RUN |

## 失败模式 a–f

| 模式 | 验收 | 执行状态 / 缺少的证据 |
|---|---|---|
| a：构建失败或新 cereal enum 破坏 C++ 消费者 | **FAIL** | NOT RUN；无设备原生构建、cereal 生成与消费者证据 |
| b：默认 owners 改变 selfdrived/card 行为 | **FAIL** | NOT RUN；无真实 Params 下 install_core no-op、core_alive=True、CardGate.sm=None 输出 |
| c：真实环境 phase4_check.py 失败 | **FAIL** | NOT RUN；没有执行设备脚本 |
| d：其他 *_check.py、big_screen_e2e.py、store_e2e.py 回归 | **FAIL** | NOT RUN；全部设备检查和 E2E 均无结果 |
| e：Plugins 缺少默认插件或提供可操作开关 | **FAIL** | NOT RUN；无 Engagement / Safety Fallback 页面截图和控件验证 |
| f：60 秒生产日志有 UI/manager traceback 或插件加载错误 | **FAIL** | NOT RUN；未采集生产日志，无法判断 |

## 检查 rc 与 E2E

下表从目标树实际存在的九个 `tools/sp_tesla_e2e/*_check.py` 枚举生成。NA 表示未启动脚本；不是 rc=0 或已观察到的脚本失败。

| 脚本 | rc | 状态 |
|---|---:|---|
| external_bridge_check.py | NA | NOT RUN |
| manifest_check.py | NA | NOT RUN |
| offroad_pages_check.py | NA | NOT RUN |
| phase2_check.py | NA | NOT RUN |
| phase3_check.py | NA | NOT RUN |
| phase4_check.py | NA | NOT RUN |
| plugin_host_check.py | NA | NOT RUN |
| store_check.py | NA | NOT RUN |
| tile_layout_check.py | NA | NOT RUN |
| big_screen_e2e.py --output /data/xpilot-ui-check-v9 | NA | NOT RUN；passed 未知 |
| store_e2e.py --repo DEVICE_CHECKOUT | NA | NOT RUN；errors 未知，无脚本输出 |

没有在设备复制 xpilot-plugins origin/main，也没有进行真实商店插件的安装或移除。没有运行主机 stub 检查来替代本轮设备检查。

## 默认路径、截图与恢复

步骤 3 **NOT RUN**：没有设备真实环境 shell 输出。期望 `plugins.owner(Params(), 'role:engagement.state') == 'sp_engagement'`、`plugins.owner(Params(), 'role:safety.fallback') == 'sp_safety_fallback'`、`CarPlugins.core_alive() is True` 和 `_gate.sm is None`，这些值本轮均未观测；install_core 不改变对象也未获真实环境证明。

步骤 4 **NOT RUN**：没有 GPU 截图，不能核验 Plugins 页或小于 400 KB 的图片要求。没有生成替代示意图。

以下为 v8 同一参数清单，本轮均未快照、修改或恢复，也未声称最终字节一致：

| 参数 | 路径 |
|---|---|
| XpilotTileLayout | `/data/xpilot_plugins/.params/XpilotTileLayout` |
| XpilotTileTheme | `/data/xpilot_plugins/.params/XpilotTileTheme` |
| XpilotBms | `/data/params/d/XpilotBms` |
| CarPlatformBundle | `/data/params/d/CarPlatformBundle` |
| IsDriverViewEnabled | `/data/params/d/IsDriverViewEnabled` |

本任务没有执行远端修改命令，因此没有由本任务造成的参数或服务变更需要撤销。**最终安全检查未运行，服务 active 与设备原状态均未重新确认。**

## 编号问题

1. **阻塞：唯一指定设备 SSH 不可达。** 四次 rc=255，错误为 `Operation timed out` / `Host is down`。这阻止了身份、安全门、部署、原生构建、全部检查、默认路径证明、截图及最终读回。已提示用户恢复同一地址的可达性；没有以其他设备或配置变更绕过门。

## NOT RUN

- onroad engagement。
- 真实 selfdrived 卡死时的 card gate。
- 实体 MADS 按钮操作。
- 全部封闭场地项目。
- 本轮所有设备身份/安全/Panda 门、部署、cereal/native build、九项检查、两项 E2E、默认路径 shell、Plugins GPU 截图、60 秒生产日志、参数字节核验、服务恢复和最终安全检查。

## 证据与后续复现

| 文件 | 内容 |
|---|---|
| source-identity.json | 主机 checkout、提交、目标、bundle 与已读取文件哈希；设备 HEAD 为 null |
| initial-ssh-errors.log、ssh-attempt-3.json、ssh-attempt-4.json | 连接失败记录，直接采集与转录来源分开标识 |
| changes.log、source.diffstat、panda-safety.diffstat | 目标提交的源码变化范围 |
| bundle-verify.log、bundle-heads.log | 主机增量 bundle 校验；不证明上传或部署 |
| FAILURE-MODES.txt、check-exit-codes.tsv、result.json | 失败模式、全部未执行 rc、结构化 BLOCKED 结果 |
| artifact-verification.json、SHA256SUMS | 本地证据一致性验证与文件哈希 |
| retry-gate.sh | 同一地址、严格 host key 的只读连接重试命令 |

本地证据可重复校验：

```bash
cd docs/validation/xpilot-c3xl-20261023-v9
shasum -a 256 -c SHA256SUMS
```

可达性恢复后，先重新通过本轮要求的 hostname、hardware_profile、实际 HEAD、dirty 文件、停车/未接合/无点火和 Panda 只读门，再继续原任务步骤；不要直接使用未确认的历史设备状态。报告提交独立于设备部署，只推送 `task/X-20261023-13`，不推送 xpilot、不 force-push。文档提交 SHA 由分支及最终交付记录确定；撤销文档可用 `git revert <文档提交>`。

未验证设备或车辆行为；主要风险是目标版本在真实环境的构建、默认路径和安全兜底仍无本轮证据。
