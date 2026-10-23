# X-20261023-02 C3XL xpilot UI v3 部署与停车验证记录

## 结论

- 状态：**BLOCKED**。设备已从 `891de5f5c7253bcb1682c3f4a75741f60c2876ab` fast-forward 到目标 `2f1cd51506716d70c21efee98b60959b82d216fc`，设备原生增量构建成功，Panda 版本与签名保持一致且未刷写。
- 阻断：生产 UI 与仓库原样 `big_screen_e2e.py` 都在导入 `openpilot/tesla/ui/screen.py:135` 时退出：`rl.Rectangle` 在 pyray 中是函数，表达式 `rl.Rectangle | None` 在运行时触发 `TypeError: unsupported operand type(s) for |: 'function' and 'NoneType'`。
- E2E 已真实尝试，退出码 1，但在创建输出目录之前失败；所以脚本没有生成自己的 `result.json`，也没有生成任何 PNG。本目录的 `result.json` 是操作记录，明确标记 `script_generated_result=false`，没有伪造截图或通过结果。
- 最终设备仍停放：`IsOffroad=1`、`deviceState.started=false`。最终 15 秒取得 151 个 Panda 样本，全部 `controlsAllowed=false`、`faultStatus=none`、`pandaType=tres`。
- 最终服务已恢复：`comma.service=active`，manager 两层进程存在，`pandad`、`hardwared` 均 `running=true`、`exitCode=0`；`ui` 为 `running=false`、`exitCode=1`。
- 没有修改源码、Params、网络配置或用户数据；没有进入 onroad、没有接管、没有刷 Panda、没有确认任何危险对话框。

## 版本身份与同步

| 项目 | 结果 |
|---|---|
| 来源 | `ssh://git@ssh.github.com:443/onemiless/openpilot.git`，分支 `xpilot` |
| `git fetch` 后 `origin/xpilot` | `2f1cd51506716d70c21efee98b60959b82d216fc`，满足要求的 `2f1cd51` 前缀 |
| 本地主机 checkout | `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/source`，`xpilot`，同步前 `9d675ebb2e5ca598c72d33e218eb79617cbe1f32`，同步后 `2f1cd515...` |
| 设备 | C3XL `comma-9c13c9f5`；历史地址 `172.16.1.202` 不可达，当前 mDNS 地址 `192.168.102.113` |
| 设备活动目录 | `/data/openpilot -> /data/xpilot-install-20261022/candidate` |
| 设备更新前 HEAD | `891de5f5c7253bcb1682c3f4a75741f60c2876ab` |
| 设备更新后/最终 HEAD | `2f1cd51506716d70c21efee98b60959b82d216fc` |
| 增量 bundle | `/data/xpilot-install-20261022/xpilot-20261023-v3.bundle` |
| bundle SHA-256 | `666e731885fffa1b9aa5ee9510ac5ca95c5ee9dbdb3300b51f0aaa669d8b09ec`，主机与设备一致 |
| bundle 范围 | prerequisite `891de5f5...`，head `2f1cd515... refs/remotes/origin/xpilot`；设备 `git bundle verify` 成功 |
| safety 差异 | `9d675ebb..2f1cd515` 对 `panda/` 与 `opendbc_repo/opendbc/safety/` 差异为空 |

主工作树 `/Users/mile/Desktop/mo-op` 位于其它分支且有大量用户改动，因此没有切换、清理或覆盖它；复用上一轮已经存在且干净的独立 `xpilot` checkout。设备工作树继续显示上一轮记录过的 LFS 实体状态和未跟踪 `prebuilt`；本轮目标文件不与这些路径重叠，没有清理它们。

用户说明设备已通过 ADB 接入，但本机实际观测为 `adb devices -l` 空、ADB mDNS 空，当前设备 `192.168.102.113:5555` 返回 `Connection refused`。通过上一轮记录的唯一设备名 `comma-9c13c9f5.local` 解析到 `192.168.102.113`，SSH hostname 回读为 `comma-9c13c9f5` 后，继续使用前两轮已验证的 SSH 链路。没有扫描或连接其它设备。

## 安全门

首次变更前与停服前检查均通过：

- `/data/params/d/IsOffroad` 为 `1`。
- `deviceState.started=false`。
- 15 秒实时 Panda 采样均为 `controlsAllowed=false`、`faultStatus=none`、`pandaType=tres`。
- 活动路径为 `/data/xpilot-install-20261022/candidate`，更新前 HEAD 为 `891de5f5...`。
- `comma.service` 更新前为 active；manager、ui、pandad、hardwared 均正常。

最终恢复后安全态仍为 `IsOffroad=1`、`started=false`；最终 151 个 Panda 样本仍全部未允许控制、无 fault。

## 设备同步与构建

设备先验证增量 bundle 的 prerequisite、head 和 SHA-256，再把 `origin/xpilot` 更新到 `2f1cd515...`，最后在 `xpilot` 上执行 `--ff-only`。同步后 HEAD 与远端目标完全一致。

停服后执行：

```bash
env PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/time -p scons -C /data/xpilot-install-20261022/candidate -j4
```

完整日志：`/data/xpilot-ui-check-v3-build.log`。

结果：退出码 0，日志末尾为：

```text
scons: done building targets.
real 15.05
user 12.21
sys 1.76
```

对完整 10,016 字节日志分别搜索 `warning` 和 `error`，均无匹配；因此本轮没有构建 warning/error 可逐字列出。

## Panda 禁止刷写门

服务保持停止时，使用低层 SPI read 只读取 identity、版本和签名，没有调用 flash、reset 或 safety 设置：

- SPI identity：`1d002d000a5130343632383809cc`；序列号仍为 `1d002d000a51303436323838`，类型字节 `09`，应用状态 `cc`。
- 构建固件版本：`DEV-443dd964-DEBUG`。
- 设备 Panda 版本：`DEV-443dd964-DEBUG`。
- 构建文件 SHA-256：`656cd6fa82c3c44509f97515f471daccb006f0160240c0154820d20a7a4b2a3c`。
- 设备签名 128 字节与构建文件末尾 128 字节逐字一致。

因此没有刷 Panda。

## 正常服务启动、60 秒日志与阻断

第一次启动 `comma.service` 后，manager 完整初始化约 40 秒。过早执行的第一次 15 秒 runtime check 得到总线服务尚未 alive；待 manager 进程出现后重复检查，确认实际阻断不是 manager，而是 UI 导入失败。

60 秒以上窗口内，tmux 生产日志包含以下完整核心 traceback：

```text
crash
Traceback (most recent call last):
  File "/data/openpilot/openpilot/system/manager/process.py", line 23, in launcher
    mod = importlib.import_module(proc)
  File "/data/openpilot/openpilot/selfdrive/ui/ui.py", line 11, in <module>
    from openpilot.tesla.ui.screen import BigScreenHost, is_big_screen
  File "/data/openpilot/openpilot/tesla/ui/screen.py", line 72, in <module>
    class BigScreenHost:
  File "/data/openpilot/openpilot/tesla/ui/screen.py", line 135, in BigScreenHost
    def viewport(self) -> rl.Rectangle | None:
                          ~~~~~~~~~~~~~^~~~~~
TypeError: unsupported operand type(s) for |: 'function' and 'NoneType'
```

完整捕获：`/data/xpilot-ui-check-v3-ui-60s.log`。同一日志还记录：

- `raylib: COMMA: Failed to initialize color correction`。
- 既有 Cursor/Windsurf 符号链接已存在。
- `No IRQs found for 'fts_ts'`。
- Panda `DEV-443dd964-DEBUG` 签名匹配，USB 尝试失败后成功经 SPI 连接。

最终恢复态：

| 项目 | 结果 |
|---|---|
| `comma.service` | `active` |
| manager | 两层 `python3 ./manager.py` 存在 |
| ui | `running=false`，`exitCode=1` |
| pandad | `running=true`，`exitCode=0` |
| hardwared | `running=true`，`exitCode=0` |
| 消息 | deviceState/pandaStates/managerState/peripheralState/uiDebug 均 alive、valid |
| 安全 | `started=false`；151 个 Panda 样本无 fault、未允许控制 |

## 大屏 E2E

服务停止后按要求执行仓库原样命令：

```bash
env -C /data/openpilot PATH=/usr/local/venv/bin:/usr/local/bin:/usr/bin:/bin PYTHONPATH=/data/openpilot:/data/openpilot/opendbc_repo:/data/openpilot/msgq_repo:/data/openpilot/tinygrad_repo:/data/openpilot/rednose_repo python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check-v3
```

退出码 1。完整日志：`/data/xpilot-ui-check-v3-e2e.log`。traceback 为：

```text
Traceback (most recent call last):
  File "/data/xpilot-install-20261022/candidate/tools/sp_tesla_e2e/big_screen_e2e.py", line 27, in <module>
    from openpilot.tesla.ui.screen import NATIVE, BigScreenHost, NAV_TOP, NAV_W, ROW_H
  File "/data/openpilot/openpilot/tesla/ui/screen.py", line 72, in <module>
    class BigScreenHost:
  File "/data/openpilot/openpilot/tesla/ui/screen.py", line 135, in BigScreenHost
    def viewport(self) -> rl.Rectangle | None:
                          ~~~~~~~~~~~~~^~~~~~
TypeError: unsupported operand type(s) for |: 'function' and 'NoneType'
```

导入发生在脚本创建输出目录之前，因此 `/data/xpilot-ui-check-v3` 不存在，脚本没有生成 `result.json` 或任何 PNG。仓库中的 `result.json` 是本轮操作记录，不是脚本输出；字段 `script_generated_result=false` 明确区分该边界。E2E 后已重新启动 comma 服务。

## PNG 目视与交互/性能边界

本轮没有 PNG 可交给图片查看器：`nav-0-home` 至 `nav-8-developer`、`plugins-store` 和 onroad 图片全部因导入失败而未生成。因此以下项目均不能声称已验证：

- 文本裁切、重叠、字号、行裁切、空页面、mici texture 显示规则、Back/breadcrumb 位置。
- Toggles 切换并恢复原值。
- Device > Reboot 打开 ConfirmDialog 后 Cancel（没有触发或确认 reboot）。
- Plugins > Plugin Store > Back 返回。
- UI 进程 30 秒 CPU 与 frame time；UI 没有存活进程和有效 30 秒帧样本，不能用 `0%` 或空样本冒充结果。

没有运行道路/onroad、没有接管、没有注入 CAN。E2E 原计划的模拟 onroad 阶段也没有到达。

## 编号问题表

| # | 分类 | 实际症状 | PNG/证据 |
|---:|---|---|---|
| 1 | 设备传输 | 用户说明 ADB 已接入，但本机 `adb devices -l` 与 ADB mDNS 均为空，确认设备当前地址后 `192.168.102.113:5555` 返回 `Connection refused`。历史地址 `172.16.1.202:22` 超时。 | 无 PNG；设备名 `comma-9c13c9f5.local` 精确解析及 SSH hostname 回读后，使用当前 `192.168.102.113:22` 完成后续步骤。 |
| 2 | 启动时序 | 服务 start 后约 40 秒才出现完整 manager 子进程；第一轮 15 秒检查过早，除旧 `uiDebug` 外其余总线均不 alive。 | 无 PNG；systemd/journal 和第一次 runtime check。等待初始化后再次检查，manager/pandad/hardwared 正常，故不是最终阻断。 |
| 3 | **UI 致命导入错误** | `openpilot/tesla/ui/screen.py:135` 执行 `rl.Rectangle | None`；pyray 的 `Rectangle` 是函数，运行时 `| None` 抛 TypeError。生产 ui `exitCode=1`，无画面。 | 所有预期 PNG 均未生成；`/data/xpilot-ui-check-v3-ui-60s.log`、最终 `/data/xpilot-install-20261022/runtime-check.json`。 |
| 4 | E2E 致命导入错误 | `big_screen_e2e.py:27` 导入 `BigScreenHost` 时命中同一 TypeError，退出码 1，输出目录未创建。 | `offroad.png`、`nav-0-home.png`…`nav-8-developer.png`、`plugins-store.png`、`onroad-blindspot.png` 全部缺失；`/data/xpilot-ui-check-v3-e2e.log`、本目录 `result.json`。 |
| 5 | 验收缺口 | 因 UI 无法启动，无法取得页面目视、三项交互、30 秒 UI CPU/frame time。 | 无 PNG、无有效帧样本；这是 #3 的直接后果，不是通过结果。 |

## 证据

仓库目录：`docs/validation/xpilot-c3xl-20261023-v3/`

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 本记录 |
| `result.json` | E2E 失败操作记录；明确不是脚本生成结果 |

设备证据：

- `/data/xpilot-install-20261022/xpilot-20261023-v3.bundle`
- `/data/xpilot-ui-check-v3-build.log`
- `/data/xpilot-ui-check-v3-ui-60s.log`
- `/data/xpilot-ui-check-v3-e2e.log`
- `/data/xpilot-install-20261022/runtime-check.json`

没有 PNG 文件可提交；原因和预期文件名已写入 `result.json` 与问题表。

## 回滚

更新前提交 `891de5f5c7253bcb1682c3f4a75741f60c2876ab` 仍是当前 `2f1cd515...` 的祖先，在同一 `/data/xpilot-install-20261022/candidate` 仓库中可直接定位；原目录、LFS 实体和启动入口均保留。恢复时应在停车停服后回到该提交、重新运行设备原生 SCons，再启动 comma。

更早的 `xpilot-rollback-20261022` 仍指向 `3d03575f...`；`/data/sp-sync-experiment-20261017/candidate` 也仍保留，但都不是本轮 `891de5f5` 的直接替代。Panda 不需要回退：更新前后构建版本与签名均为同一 `DEV-443dd964-DEBUG` / `656cd6fa...a3c`。

本轮没有执行回滚，因为任务要求设备更新到 `2f1cd51` 或记录精确阻断；当前保留目标 HEAD 供协调者修复。

## 未验证边界

- 没有任何 UI v3 页面渲染成功证据。
- 没有实体屏幕、人手触摸、网络页面、对话框、插件商店或 30 秒性能验证。
- 没有道路、摄像头 onroad、车辆控制闭环或真实盲区信号验证。
- 没有修复或变更源码；协调者需要修复 `screen.py:135` 后重新完整执行本任务。
