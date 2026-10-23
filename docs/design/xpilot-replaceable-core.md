# xpilot：可替换的模型、DM、接管与安全兜底

任务：X-20261023-08 / V-C。状态：设计，未实现。代码基线固定为 `00f7924ca05272103dd7cd2063cd5c66d1767b87`，仓库 `onemiless/openpilot`；下文所有 `文件:行号` 均指这个提交，可用 `git show 00f7924ca05272103dd7cd2063cd5c66d1767b87:<文件>` 复核。“现状”是源码证据，“方案”和检查门槛是待实现要求；没有构建、设备或实车通过的含义。

## 1. 已决定的边界

- **用户 2026-10-23 决定**：`perception_model`、`driver_monitoring`、`engagement`、`safety_fallback` 都允许替换整个软件组件。现有 SP 实现成为默认插件和示例，第三方实现不用先运行 SP 算法再修正输出。
- **不动底线**：panda safety、`controls_allowed` 及 MADS 横向许可、速率/扭矩/转角限制、内置 safety headers、车端限制，以及 XPILOT 规则 3。FCW、刹车退出、原车 AEB 的保护不能被替换插件关掉。当前规则见 `XPILOT.md:16-22`；panda 横向许可与限幅见 `opendbc_repo/opendbc/safety/lateral.h:353-407`，刹车/再生制动退出见 `opendbc_repo/opendbc/safety/safety.h:349-379`。Tesla 的具体控制方式是转角，不能把通用扭矩限制误写成 Tesla 的扭矩控制（`opendbc_repo/opendbc/car/tesla/interface.py:26`）。
- **替换策略，保留宿主**：调度、契约校验、失效撤权、发送门控不是第五个可替换策略。软件兜底可以重写判断和交接流程，不能改写车端或固件来获得本来没有的权限。

## 2. 共用宿主

### 2.1 现有能力和缺口

四个类别已有定义，任意合法 `role:` 是独占资源，按 `(priority, id)` 裁决；但类别本身不会替换代码（`openpilot/tesla/manifest.py:31-62,144-155`）。`Plugin.processes()` 目前只声明附加进程；宿主检查 `process:<name>`，再给 `should_run` 加开关条件，没有撤销 SP 进程的机制（`openpilot/tesla/plugin.py:60-64`、`openpilot/tesla/plugins/__init__.py:175-186`）。发现时会导入插件 Python，钩子异常会记入 `XpilotPluginFaults`；同步调用没有超时隔离（`openpilot/tesla/plugins/__init__.py:46-84,107-116,194-219`）。额外 `SERVICES` 反而被排除在健康检查之外，不能用它承载必需的核心输入（`openpilot/tesla/plugins/__init__.py:189-191`；`openpilot/selfdrive/selfdrived/selfdrived.py:101-120`）。

### 2.2 方案：一次选择，失效先退出

- 每次行程锁定四个 role 的插件 id、版本、内容 SHA-256、进程集合和 DM 是否必需。开关、升级、卸载只在停车并重新建立会话后生效。启动时替换包缺失、导入失败或不兼容，选择内置默认；默认也不可用就禁止接管。
- 四个内置默认包用 `enable_param:null`，仅在相应 role 没有合格替换者时入选；UI 显示“Default”，不提供关闭默认的按钮。这是本设计对规则 6 的必需默认项特例，实施时同步规则；普通替换包仍用默认 `0` 的 BOOL。`null` 的现有含义见 `openpilot/tesla/manifest.py:9`、`openpilot/tesla/plugins/__init__.py:92-104`。
- 扩展 `processes(procs)`：在同一次裁决中屏蔽被替换的原进程族、验证声明、拒绝重名，再返回新增进程；原 manager 只看到一份确定的进程表。宿主把原描述供给默认包，其 `processes()` 返回原对象；最终按对象身份去重，默认入选时原位保留，替换入选时屏蔽原族。不复制模型或 DM 实现。当前集中接入点在 `openpilot/sunnypilot/system/fork_processes.py:21-31`、`openpilot/system/manager/process_config.py:164-165`。
- 增加不可卸载的 `openpilot/tesla/core_host.py` 宿主和独立 `core_guardd`，后者只读清单和消息，**不导入替换插件**。它验证进程、消息内容、来源会话、原始帧推进和时间；card 在 `CI.apply` 前再次核对许可、踏板和 panda 状态。许可丢失时清除 `enabled/latActive/longActive`，通过原 controller 发退出状态，停止附加控制发送；不能保持上一条有效控制。
- 健康侧带复用 `customReservedRawData0` 的 Data，JSON 契约为 `{api:1, session, seq, sampleMonoTime, roles, permitLat, permitLong, fault}`，由 `core_guardd` 唯一发布。已有槽位和服务见 `openpilot/cereal/log.capnp:2634`、`openpilot/cereal/services.py:113`。旧服务不新增 session 字段：guard 在切换后清队列，以激活时间和当前 camerad 帧号交叉核对来源；侧带 session 只标识本次宿主许可。其服务频率为 0，不能依赖 SubMaster 自动判活：宿主自行拒绝未来时间、倒退 seq、错误 session，初始门槛为许可超过 100 ms、接管周期超过 100 ms、模型/DM 原始帧超过 500 ms 即失效；还检查 valid、频率和下述结构。以上是待测上限，设备验收只能收紧。当前 SubMaster 用接收时刻和 `10/frequency` 判活，重新发送旧内容会刷新它（`openpilot/cereal/messaging/__init__.py:251-278`）。
- 行驶中崩溃、卡死、过期、非法值或目录被外部删除：锁存故障、两轴撤权、提示接管；不热启默认、不自动重新接管。停车后重启受影响进程，再选默认，清除旧队列和状态，需驾驶员重新接管。默认模型管理器仅在停车运行（`openpilot/system/manager/process_config.py:139`），它的下载故障不应单独撤销行驶中已健康的推理。
- UI 常驻宿主提示 role/id/原因和“Take control”；声音输出独立读取许可失效，包含 C3XL 蜂鸣器，不能只依赖卡住的 selfdrived。当前普通插件报警不会退出且优先级最高 MID（`openpilot/tesla/alerts.py:1-3,17-20`）；soundd 有 selfdrive 超时报警，而 C3XL 输出只在消息更新时处理报警（`openpilot/selfdrive/ui/soundd.py:156-165`、`openpilot/sunnypilot/system/alert_output.py:128-134,170-176`）。因此核心失效不能只发普通 `PluginAlert`。

## 3. 感知模型：`role:perception.model`

### 3.1 今天是什么

- `models_manager`、`modeld_warmup` 在停车运行；行驶时按 runner 选 Python `modeld` 或 native 入口 `modeld_tinygrad`（`openpilot/system/manager/process_config.py:102,139-141`）。模型管理读取 `deviceState.chestnutPresent`，发布 `modelManagerSP.selectedBundle/activeBundle/availableBundles`（`openpilot/sunnypilot/models/manager.py:294-305,369-393`）。下载完成写入分开的 qcom/chestnut active bundle；本地 SHA-256 和版本校验、runner 缓存见 `openpilot/sunnypilot/models/helpers.py:24-46,141-180`。
- stock 和 v2 都读 camerad 的道路 VisionIPC、`deviceState/carState/narrowRoadCameraState/extrinsicsCalibration/driverMonitoringState/carControl/controlsState/lateralDelay`，等待 `CarParams`，发布 `modelV2/drivingModelData/cameraOdometry/modelDataV2SP`，Chestnut 时另发 `chestnutGpuState`（`openpilot/selfdrive/modeld/modeld.py:249-260,308-333,445-474`；`openpilot/sunnypilot/modeld_v2/modeld.py:333-359,480-509`）。两种实现都已有大模型异常后转小模型的内部路径（`openpilot/selfdrive/modeld/modeld.py:424-439`；`openpilot/sunnypilot/modeld_v2/modeld.py:459-473`）。
- 参数：`ModelManager_ActiveBundle{,Chestnut}`、`ModelRunnerTypeCache`（`openpilot/sunnypilot/models/helpers.py:24-27,168-180`）；`ModelManager_DownloadRef/ClearCache`（`openpilot/sunnypilot/models/manager.py:140-148,389-391`）；`ModelManager_ModelsCache{,_Chestnut}/LastSyncTime{,_Chestnut}/ActiveJson`（`openpilot/sunnypilot/models/fetcher.py:79-83,118-134`）；`ChestnutLoading/Active/Retry/OnroadCycleRequested`（`openpilot/selfdrive/modeld/modeld.py:239-302`）；v2 另读 `PlanplusControl/CameraOffset`（`openpilot/sunnypilot/modeld_v2/modeld.py:410-411`）。warmup 读取 qcom bundle 准备缓存（`openpilot/sunnypilot/modeld_v2/warmup.py:20-38`）。

### 3.2 替换单位、契约和默认包

**进程族整体替换**：模型下载、选择、缓存、推理都归一个 role；不是只换权重，也不要求调用 SP runner。默认目录 `plugins/sp_perception/` 的 `processes()` 返回上述四个原进程描述，保留 stock/tinygrad 的互斥和原运行条件。模型源码改动为零。

替换者必须保持既有服务和字段语义：

| 输出 | 必需内容 |
|---|---|
| 20 Hz `modelV2` | 帧号、EOF、frameAge/drop、执行时间、big；33 点 position/velocity/acceleration/orientation/orientationRate；4 条 laneLines 和概率/标准差、2 条 roadEdges、3 个各 6 点的 leadsV3；action.desiredCurvature/desiredAcceleration/shouldStop；meta 的 desire、laneChange、disengagePredictions、hardBrakePredicted；confidence。 |
| 20 Hz `drivingModelData` | 同帧 action、帧号/drop/big/执行时间、path 多项式、laneLineMeta 和 laneChange meta。 |
| 20 Hz `cameraOdometry` | 同帧 EOF、trans/rot、wideFromDeviceEuler、roadTransformTrans 及各标准差；未完成标定不能谎报 valid。 |
| 20 Hz `modelDataV2SP` | laneTurnDirection、左右 laneChangeEdgeBlock；无变道功能时明确 off/none。 |
| 停车 1 Hz `modelManagerSP` | 可用、已选、实际激活 bundle 及下载状态；不能把 queued 当 active。Chestnut 时另发 GPU 温度、显存温度、功耗/上限、利用率、时钟、风扇及 valid。 |

字段依据：`openpilot/selfdrive/modeld/fill_model_msg.py:59-193`、`openpilot/selfdrive/modeld/constants.py:6-23,46-50`、`openpilot/cereal/custom.capnp:571-580`、`openpilot/cereal/services.py:63,74-75,88,97`；GPU 状态见 `openpilot/selfdrive/modeld/modeld.py:98-127`。替换管理器还必须响应原下载/取消、默认选择、刷新与清缓存动作，保持 Models 页不改（`openpilot/tesla/ui/pages/models.py:81-93,108-129,138-152`）。向量维度、单位、坐标系、时间索引必须适配基线，不能以空数组凑 valid；概率须在 [0,1]，数值有限、时间递增、同帧输出一致。`radard` 依赖 velocity/leads，`plannerd` 依赖模型驱动周期，`controlsd` 依赖 action，标定/定位依赖 odometry，全部保持不改（`openpilot/selfdrive/controls/radard.py:237-244,282`、`openpilot/selfdrive/controls/plannerd.py:35-52`、`openpilot/selfdrive/controls/controlsd.py:85-126`、`openpilot/selfdrive/locationd/calibrationd.py:266-285`、`openpilot/selfdrive/locationd/locationd.py:271-281`）。

**失败与检查**：先列进程退出/死锁、双 runner、旧帧换新时间、NaN/空轨迹、bundle 损坏、下载中断、驱动中卸载。主机 E2E 用固定录像同时喂默认与替换实现，串起 radard/plannerd/controlsd/card，逐项注入，证明唯一发布者、契约拒绝和两轴撤权；下载失败须保留原 active。设备检查覆盖每种目标硬件的推理时延、VIPC、Chestnut 内部降级、冷启动及缓存；封闭场地验证失效后控制停止与提示。底线仍是第 1 节：模型不能拿 CAN、改安全参数或让虚假轨迹越过限幅；结构合法不证明感知正确。默认内部大转小路径保留，但整包失效不等于可在行驶中安全切包。

## 4. 驾驶员监控：`role:driver.monitoring`

### 4.1 今天是什么

`dmonitoringmodeld` 从 cabin VisionIPC 和 `extrinsicsCalibration` 推理，20 Hz 发布 `driverStateV2` 的 frameId、执行时间、wheelOnRightProb、左右脸姿/位置/标准差、脸/眼/眨眼/墨镜/手机/睡眠概率（`openpilot/selfdrive/modeld/dmonitoringmodeld.py:84-108,111-151`）。`dmonitoringd` 以 driverStateV2 为时钟，另读标定、车况、接管、modelV2 和 carControl；valid 来自输入健康，发布 `driverMonitoringState`（`openpilot/selfdrive/monitoring/dmonitoringd.py:11-38`）。policy 包括 vision/wheeltouch、awareness、三级报警、lockout 和 noResponseForceDecel（`openpilot/selfdrive/monitoring/policy.py:27-44,314-429`）。

参数为 `AlwaysOnDM/IsRhdDetected/IsDriverViewEnabled`（`openpilot/selfdrive/monitoring/dmonitoringd.py:16,36-45`）、`DriverLockoutCount`（`openpilot/selfdrive/monitoring/policy.py:157-160,318-322`）；`DriverMonitoringEnabled/ActiveDriverMonitoringEnabled` 受硬件能力约束并按行程锁定（`openpilot/sunnypilot/hardware/driver_monitoring.py:7-31`）。DM 关闭时 selfdrived 忽略 cabin/DM 健康检查；开启时消费 lockout、alertLevel、activePolicy 和 uncertainty，并写 `DriverTooDistracted/Offroad_DriverMonitoringUncertain`（`openpilot/selfdrive/selfdrived/selfdrived.py:103-107,255-278`）。`noResponseForceDecel` 还进入 controlsState.forceDecel 和车端 escalation，规划器会把巡航目标置零（`openpilot/selfdrive/controls/controlsd.py:202-206`、`openpilot/selfdrive/controls/lib/longitudinal_planner.py:56-60`）。

### 4.2 替换单位、契约和默认包

**两进程整体替换**，role 同时拥有推理和 policy；可以不用 SP 的 DriverMonitoring 类。`plugins/sp_driver_monitoring/` 包装两个原进程，保留 driverview/硬件/开关条件（`openpilot/system/manager/process_config.py:19-20,103,116`、`openpilot/sunnypilot/system/fork_processes.py:23-24`），两份 DM 源码均零改动。

替换者必须发布 20 Hz `driverStateV2` 以及 **完整** `driverMonitoringState`：lockout/count/minutes、alert3Count/noResponseCount/noResponseForceDecel、alwaysOn/alwaysOnLockout、alertLevel、activePolicy、isRHD、rhdCalibration、visionPolicyState、wheeltouchPolicyState；结构以 `openpilot/cereal/log.capnp:2193-2263` 为准。不能清空原来已锁存的 lockout；没有视觉证据就用既有 wheeltouch 表示并明确 faceDetected=false，不能伪造“有脸”。UI、selfdrived、modeld、controlsd 的服务订阅保持不变（`openpilot/selfdrive/ui/ui_state.py:55-65`、`openpilot/selfdrive/selfdrived/selfdrived.py:113-118`、`openpilot/selfdrive/modeld/modeld.py:310-311`、`openpilot/selfdrive/controls/controlsd.py:44-48`）。

宿主按已锁定的 role 能力设置 `dm_required`：默认包沿用现有硬件开关；替换包用其他真实传感器时可整体替代视觉链，不能继续被默认包的 cabin gate 误关。selfdrived 的 dm_enabled 由核心入口适配，不改硬件 helper 的默认语义；需监控时任何缺失都算故障。主动关闭 DM 只允许停车生效，不用“健康空消息”掩盖关闭。

**失败与检查**：先列推理死/策略活、脸状态冻结、非法概率/枚举、重启清零 lockout、DM 总开关中途变化、包消失。主机 E2E 重放分心→报警→无人响应→减速→禁止接管，再注入上述故障，检查 policy、UI、纵向整条链；设备需分别验证有 cabin 与无 cabin 的配置、视角/遮挡/左右舵、声音；封闭场地验证减速和退出。需 DM 的会话故障立即撤权并提示，默认只在停车重启；当前明确关闭 DM 的会话不因不存在的相机新增故障。可替换监控算法和计时，不能替换 panda/车端许可；宿主不得因换插件丢失已发生的锁定状态。

## 5. 接管：`role:engagement.state`

### 5.1 今天是什么

selfdrived 100 Hz 采样 carState 和健康/模型/DM/规划/控制/panda 等服务，等待 CarParams/CarParamsSP；按“事件→普通状态机→MADS→报警→发布”执行（`openpilot/selfdrive/selfdrived/selfdrived.py:65-120,157-184,645-655`）。普通状态机支持 disabled/preEnabled/enabled/softDisabling/overriding，soft-disable 为 3 秒（`openpilot/selfdrive/selfdrived/state.py:7-97`）。MADS 有独立 enabled/active/paused 状态及事件改写（`openpilot/sunnypilot/mads/state.py:17-23,45-135`、`openpilot/sunnypilot/mads/mads.py:206-218`）。

输出是 `selfdriveState` 的 enabled/active/state/engageable/personality 和全部 alert 字段，`selfdriveStateSP.mads.{state,enabled,active,available}` 及按钮状态，`onroadEvents/onroadEventsSP` 每秒或变化即发（`openpilot/selfdrive/selfdrived/selfdrived.py:594-643`）。controlsd 在 MADS available 时使用 mads.active；pandad 独立读取普通 enabled 与 MADS enabled 作为心跳，两轴不能只关其中一个（`openpilot/sunnypilot/selfdrive/controls/controlsd_ext.py:42-51`、`openpilot/selfdrive/pandad/pandad.cc:34-36,402-409`）。参数有 `DisengageOnAccelerator/LongitudinalPersonality/IsMetric/IsLdwEnabled`（`openpilot/selfdrive/selfdrived/selfdrived.py:659-667`），`Mads/MadsMainCruiseAllowed/MadsSteeringMode/MadsUnifiedEngagementMode/TeslaMadsScreenButton`；部分 Tesla 配置会限制 MADS 模式并设置 alternativeExperience（`openpilot/sunnypilot/mads/mads.py:50-58`、`openpilot/sunnypilot/mads/helpers.py:23-65`）。

### 5.2 替换单位、契约和默认包

**进程内完整策略对象**，不另抢 selfdrived 的发布 socket。原因：事件、报警和 MADS 共用周期与状态；把 selfdrived 全进程交给接管插件会连带夺走独立的 safety_fallback。`plugins/sp_engagement/` 实现拟新增的 `engagement(...)` 工厂，默认对象直接调用原普通 `StateMachine.update` 和 `ModularAssistiveDrivingSystem.update`。替换者可以重写两套状态机和按钮接管语义，不必运行默认算法；guard 的底线 veto 在策略之后、发布之前再次执行，不能仅把停用事件交给自定义状态机自行决定。

同一 `plugins.run_core(s)` 入口接管 selfdrived 周期，默认保持原顺序。输入是只读 CS/上一帧、CP/CP_SP、Params 快照、事件与健康快照；`update(context)` 必须返回普通 state/enabled/active、MADS state/enabled/active/available、current_alert_types、soft_disable_timer、personality，以及 MADS 对策略事件的增删。宿主校验枚举、active/enabled 对应关系及时间，把结果映射到既有发布器所读的 state_machine、mads 和 personality 字段，负责按钮跟踪、报警和既有四服务发布；插件不能自己发布第二份状态。MADS 允许横向 active 而普通 enabled=false，不能用普通 active⇒enabled 的断言错误地合并两轴。controlsd/card/pandad/UI 不改其订阅和字段含义。

**失败与检查**：先列异常、无限循环、非法状态组合、MADS 残留激活、旧按钮重放、卸载后重新接管。主机 E2E 覆盖普通与 MADS 的接合/暂停/override/刹车/取消/3 秒退出，逐帧检查两个 enabled、两个 active、事件和声音；卡死时由独立 guard 撤销 card 许可，不能声称 try/except 能救死循环。设备检查 100 Hz 周期和硬件按钮；封闭场地逐项验证驾驶员退出与无自动重接管。故障锁存后先退出，停车才恢复默认。不可替换的是真实踏板与 panda 许可：纵向刹车退出、横向按已验证 MADS alternativeExperience 处理，不允许插件改安全模式或放大权限。

## 6. 安全兜底：`role:safety.fallback`

### 6.1 今天是什么

没有单独的 fallback 进程。selfdrived 的 `update_events` 混合处理 DM、车况、踏板、标定、热故障、panda mismatch、进程/通信故障、模型延迟与 FCW（`openpilot/selfdrive/selfdrived/selfdrived.py:255-355,387-503,513-520`）；事件表赋予 noEntry/softDisable/immediateDisable，状态机执行退出（`openpilot/selfdrive/selfdrived/events.py:740-766`、`openpilot/selfdrive/selfdrived/state.py:24-57`）。

FCW 同时来自模型 hardBrakePredicted 和纵向计划，MPC 的 crash_cnt 产生 planner FCW（`openpilot/selfdrive/selfdrived/selfdrived.py:498-503`；`openpilot/selfdrive/controls/lib/longitudinal_planner.py:84-98,140-142`）。原车 stockAeb/stockLkas 解析和事件仍在车端路径（`opendbc_repo/opendbc/car/tesla/carstate.py:107-111`、`openpilot/selfdrive/car/car_events.py:51-56`）。Tesla controller 对转角限速、加速度裁剪并能发送 cancel；panda 禁止伪造 AEB、stock AEB 时禁止 xpilot 纵向/cancel、按条件保留原车报文转发（`opendbc_repo/opendbc/car/tesla/carcontroller.py:38-62`、`opendbc_repo/opendbc/safety/modes/tesla.h:289-357`）。这些路径不提供“已确认 Autopilot 接管”的完整握手；退出 xpilot 不能据此标为交接成功。

现有看门狗也有不同边界：card 只按 carControl alive 决定是否 apply；pandad 丢弃超过 1 秒的 sendcan；固件按普通和 MADS 心跳退出许可并在心跳消失时进 SILENT，RX 迟滞也撤权（`openpilot/selfdrive/car/card.py:251-278`、`openpilot/selfdrive/pandad/pandad.cc:90-96`、`panda/board/main.c:191-225`、`opendbc_repo/opendbc/safety/sunnypilot/mads.h:136-144`、`opendbc_repo/opendbc/safety/safety.h:315-332`）。它们不能识别持续发送的错误感知。相关 Params 包括 `Offroad_ExcessiveActuation/ChestnutLoading/ChestnutActive/DriverTooDistracted/Offroad_DriverMonitoringUncertain`（`openpilot/selfdrive/selfdrived/selfdrived.py:83-87,200-215,255-278,348-355`），不是一个可随意关闭的“总安全开关”。

### 6.2 替换单位、契约和默认包

**进程内完整事件与兜底策略**，与接管共享 `run_core` 的采样，但先于状态转移。`plugins/sp_safety_fallback/` 的拟新增 `safety_fallback(...)` 默认对象直接调用原 `SelfdriveD.update_events`，保留原计数器与 Params 副作用；不复制那段逻辑。新实现整体接管软件事件生成、故障处置时机、报警和交接策略，返回完整 Events/EventsSP、`none/soft_disable/immediate_disable` 处置、报警请求、`handoff_requested/confirmed` 及证据时间、需持久化的既有故障状态。宿主统一提交结果，接管插件随后消费；两者均不能删掉宿主的底线事件。既有额外插件报警只合并一次：默认 update_events 已调用合并，替换路径由宿主补齐（`openpilot/selfdrive/selfdrived/selfdrived.py:281`）。

底线事件单独由宿主计算：真实刹车/取消和 car/panda 禁止、核心数据失效，及基线 model/planner FCW 与 stock AEB 保护；保留 SP MPC 的 FCW 计算和原车 AEB 转发，不把“整个兜底可替换”变成“允许关闭防撞”。新的风险判断可以独立实现；它不能输出绕过 planner/controller 的油门或制动 CAN。默认软退出仍通过现有 state.softDisabling→forceDecel 链减速；协议发送属于 actuation 类，新增地址仍需独立内置 safety header。当前按地址选 safety 插件、否则走原 safety tx，最终还有 relay 检查（`opendbc_repo/opendbc/safety/safety.h:230-247`）；headers 是固件边界，不能随商店包动态替换。

交接默认只是退出并要求驾驶员接管。替换策略可以请求原车交接，但只有插件自己的只读 CANParser 读到新鲜、明确的原车状态才可确认；不能把 cruiseState.enabled 或 stockLkas 单独当完整 Autopilot 确认。未确认、超时、矛盾即显示未交接、保持退出；严禁为了“无缝”保留旧控制或屏蔽 AEB。

**失败与检查**：先列兜底异常/卡死、健康数据过期、FCW 被删、AEB/cancel 竞争、误报 AP 成功、驱动中卸载。主机 E2E 注入每项并验证接管策略无法吞掉底线、card 撤权、报警和 handoff 未确认；设备需编译并运行既有 panda/safety 检查、记录限幅/RX/心跳拒绝和原车 AEB 转发，不能把回放当固件证据。封闭场地先证明退出与人工接管，再验证各 Tesla 硬件/固件组合的交接；未证明前只提供人工接管模式。故障时不信任同进程默认能救卡死，由独立宿主门控兜底，停车后才回默认。

## 7. 默认清单、实施顺序与验收

四个目录都在 `openpilot/tesla/plugins/`。共用清单骨架如下，后三个按表替换 id/category/entry/claims；不新增 manifest 格式：

```json
{
  "id": "sp_perception", "name": "SP Perception", "version": "1.0.0", "api": 1,
  "category": "perception_model", "entry": "plugin:SpPerception",
  "priority": 10000, "enable_param": null,
  "claims": ["role:perception.model", "process:models_manager", "process:modeld",
             "process:modeld_tinygrad", "process:modeld_warmup"],
  "params": {}, "settings": []
}
```

| 默认目录 / entry | category | 完整 claims |
|---|---|---|
| `sp_driver_monitoring` / `plugin:SpDriverMonitoring` | driver_monitoring | role:driver.monitoring, process:dmonitoringmodeld, process:dmonitoringd |
| `sp_engagement` / `plugin:SpEngagement` | engagement | role:engagement.state |
| `sp_safety_fallback` / `plugin:SpSafetyFallback` | safety_fallback | role:safety.fallback |

默认包无新 Params；复用上述 SP 参数。替换包的开关和自有设置放自己的 params/settings，按既有生成机制管理（`XPILOT.md:21`）。model/DM 替换包可声明不同进程名，宿主按 role 屏蔽整个默认族；不得占用其他 role 的服务。接管/兜底 hooks 不申领宿主的 selfdrived 或 core_guardd。

**预期 SP diff**：以下都是将来的改动，本提交只写本文；每个接入文件最多新增一行插件调用，逻辑放 xpilot 宿主/插件。

| 文件 | 预期改动 |
|---|---|
| `openpilot/system/manager/process_config.py` | 0，复用已有 apply_fork_processes。 |
| `openpilot/sunnypilot/system/fork_processes.py` | 将现有调用改成 `plugins.processes(procs)`，宿主同时完成原进程族 gate 和新进程登记。 |
| 两套 modeld、models/**、两份 DM、policy、state.py、mads/**、plannerd、controlsd | 0，默认包装原实现，保持消费者契约。 |
| `openpilot/selfdrive/selfdrived/selfdrived.py` | main 中把 `s.run()` 改成一行 `plugins.run_core(s)`；宿主维护原参数线程生命周期、按钮/报警/发布顺序和默认对象，新增策略不接收可写 SelfdriveD。 |
| `openpilot/selfdrive/car/card.py` | apply 前一行 `CC = self.plugins.guard_core(CS, CC)`；guard 不调用替换插件，现有 control_sends 宿主服从同一许可。 |
| `openpilot/selfdrive/ui/soundd.py`、`openpilot/sunnypilot/system/alert_output.py` | 各一行宿主失效报警调用；helper 内部订阅侧带，无额外手写订阅。 |
| Tesla car/controller/DBC、panda、全部 safety headers、cereal schema/services | 0；使用现有 RawData 槽，不重编号。 |

xpilot 自有 `plugin.py/plugins/__init__.py` 增加两个工厂、进程族选择和周期委托；`core_host.py` 实现只读上下文、结果校验和 guard；Tesla UI/Store 复用现有页面增加锁定/故障显示及停车约束。当前 store.uninstall 本身直接删目录，没有行驶检查，因此约束必须在宿主/API 也执行，不能只靠 UI（`openpilot/tesla/store.py:145-151`）。

**实施顺序**：① 先写失败场景和可复现 E2E 驱动，再做 role 选择、会话锁定、guard 和独立告警，未过门槛不启用任何核心替换；② 包装模型进程族并验证默认等价；③ 包装 DM、验证 lockout 和减速；④ 一次引入共用 run_core，先只启用默认接管/默认兜底；⑤ 再分别开放接管替换、最后开放兜底与交接。每步独立提交和可回滚，先证明默认路径等价，再证明替换路径，不编写事后单元测试。

**可重复产物**：拟新增 `tools/sp_tesla_e2e/core_contract_e2e.py`，命令约定 `python3 tools/sp_tesla_e2e/core_contract_e2e.py --scenario all --route <固定本地录像> --out <目录>`，目前不存在，也未执行。结束必须输出输入录像/Params/模型与插件 SHA-256、源码 commit、逐帧消息及发送 trace、故障注入时刻→撤权→声音/画面时间线、断言结果和结果文件 hashes。设备产物另含实际 active commit、硬件/车端/panda 固件身份、录像和 CAN 读回；不能用同名分支或上传目录证明激活。真实故障延迟须落在第 2 节门槛，任何超过都阻止放行。

**风险排序**：P0：合法但错误的感知或 DM 判定、绕过真实踏板/许可、MADS 单轴残留、误确认 AP 交接；panda 限幅不能证明路线安全。P1：进程内钩子挂死、默认与替换双发布、跨会话旧帧、DM 锁定被重置、告警进程同时失效；靠独立门控和整链注入验证。P2：模型缓存/编译 ABI、CPU 调度与守护额外延迟、UI 表示滞后；逐硬件测量。Python 插件已有同进程导入能力，claims 不是操作系统沙箱（`openpilot/tesla/plugins/__init__.py:67-80`）；本方案面向经审核代码，不宣称能隔离恶意代码。编译和道路验证仍是后续门槛。

**只留用户决定的问题**：第三方核心替换是否允许从商店直接安装，还是先限审核白名单？是否要求无 cabin 的设备也必须使用替代 DM（本方案默认保留现有开关）？是否要实现自动请求 Autopilot 交接，以及首批允许的 Tesla 硬件/固件组合？行驶中故障默认人工接管、停车后回默认；若要自动恢复控制，需要另行明确授权和专门验收，不作为本次设计默认。
