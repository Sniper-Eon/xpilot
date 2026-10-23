# xpilot：规则与开发说明

所有人和所有 AI 动手改代码前必须先读这份文档。`AGENTS.md`（Codex 等）和 `CLAUDE.md`（Claude）都指向这里。

## 1. 项目是什么

- **定位**：sunnypilot（下称 SP）只适配 Tesla 的精简版，分支名 `xpilot`。
- **基线**：sunnypilot `922513f`，opendbc `5be750714`。只做这一次基准，之后不再整体合并上游，只手工挑修复（`tools/dev_sp_release/upstream_watch.py`）。
- **主体**：横向、纵向、模型都是 SP 原版，Tesla 车端代码是上游原版。
- **扩展**：xpilot 的功能全部以插件形式接入，不改 SP 主体逻辑。
- **已删除**：其他车型、comma 云、sunnylink、旧的大屏 UI、扭矩车用的横向控制、翻译（UI 只用英文）。
- **硬件**：C3、C3X、C3XL、C4。大屏设备上整屏是磁贴，行驶时 mici 画面固定在中间、磁贴排在四周（见第 9 节）。

## 1b. 核心理念

1. **一切功能皆插件。** SP 是不改的主干；xpilot 的每个功能都是 `openpilot/tesla/plugins/<id>/` 下的一个目录，加功能就是加目录，删功能就是删目录。
2. **宿主定规则，插件只填内容。** 合并、裁决、限幅、出错隔离都写在宿主（`openpilot/tesla/`）里，插件改不了；插件只实现钩子。
3. **安全底线不可越过。** 车端检查、SP 的限幅和 panda safety 永远最后生效；插件再高的优先级也只能在这个范围内工作。
4. **出错只影响自己。** 一个插件坏了，只有它被停用，SP 和其他插件照常运行。
5. **先声明再使用。** 插件要用的 CAN 地址、进程、数据源和可替换环节都写进 `claims`；冲突由宿主按 `priority` 裁决，用户在插件市场里看得到。
6. **够用就好。** 钩子、参数、抽象只在真有插件需要时才加；UI 低频刷新、只在内容变化时重画。
7. **证据说话。** 先写失败模式和检查；本机检查、编译、safety 测试、设备实测分开报告，不能互相顶替。

## 2. 硬规则

1. **不改 SP 主体逻辑。** SP 文件里每个钩子点只加一行插件调用（循环、出错隔离等逻辑放在 `openpilot/tesla/` 里）。功能逻辑全部写在 `openpilot/tesla/plugins/<功能名>/`。
2. **不改上游 Tesla 车端代码。** `opendbc_repo/opendbc/car/tesla/*`、`opendbc_repo/opendbc/sunnypilot/car/tesla/*`、`opendbc/dbc/tesla_model3_*.dbc`、`opendbc/safety/modes/tesla.h` 保持上游原样。需要车端数据，就在插件里用自己的 `CANParser` 读。
3. **插件不能绕过车端和 panda 的检查。** 纵向：`long_target` 加速只能替换驾驶员设定车速（条件见第 4 节）；`plan_filter` 只能收紧；`role:long.planner` 可以整体替换纵向计划、包括跟车（用户 2026-10-22 决定），但加速度限制、FCW、踩刹车退出、原车 AEB 和 panda 限制不变。横向：`role:lateral.controller` 的输出不额外限制，靠车端转角速率限制和 panda 兜底。外接算力的数据只做建议。
4. **每个 CAN 发送地址都必须有 panda safety 插件**（`opendbc/safety/plugins/`），在插件里自己校验内容、频率、时效和 `controls_allowed`。没有 safety 插件，panda 会直接拦掉。
5. **插件出错不能拖垮进程**：输入过期就当周期什么都不发。宿主兜底：插件在任何钩子里抛异常，就被记进 `XpilotPluginFaults`、本次进程内停用，其他插件和 SP 照常运行；plan filter 出错时计划照常发布。UI 磁贴和叠加层连续出错 3 次会停止绘制。
6. **Params**：插件的 key 写在自己 `plugin.json` 的 `params` 里，然后运行 `python3 openpilot/tesla/plugins/gen_params.py` 生成 `common/plugin_params.inc` 并一起提交；不属于插件的 key 才写进 `params_keys.h`。每个插件有一个 BOOL 总开关 `enable_param`，默认关闭；例外：只做显示、`claims` 为空的 `ui` 类插件（如 `speed_card`）可以默认开启。设置项写在 `plugin.json` 的 `settings` 里。
7. **cereal**：只追加字段，不改已有字段的序号和类型。新消息用 `custom.capnp` 里的 `customReserved*` 槽位。
8. **验证**（沿用 `AGENTS.md`）：
   - 先列出失败模式，再写检查。
   - 优先做可重复的端到端检查。
   - 不准把静态检查说成编译、safety 测试或上车已通过。
   - 本地 commit 和设备上实际运行的 commit 分开报告。
9. **提交**：在 `xpilot` 分支上，一个连贯改动一个提交，只包含这次改动的文件。只有在用户要求时才推送。
10. **按插件拆分**：加功能就是加一个带 `plugin.json` 的插件目录，删功能就是删目录（然后重新运行 `gen_params.py`）。插件自动被发现，没有手写的注册表。
11. **只用声明过的资源**：插件只能使用 `plugin.json` 里 `claims` 声明过的资源；宿主会拒绝未声明的 CAN 发送、钩子和进程。
12. **车端数据只读、只经插件**：插件在 card 里用 `observe_can` 自己解析，再写进 `carStateSP` 里自己的字段（cereal 规则见第 7 条）；UI 和其他进程只读这些消息，不直接读 CAN。
13. **UI**：文字只用英文和 ASCII（设备字体没有 `‹ › · —` 等字）；磁贴只读消息、不写参数（设置写在详情页）；`hz` 按需要取最低值。
14. **不加新依赖**：只用标准库和仓库里已有的库。商店插件需要编译的部分以预编译二进制发布（见 8c）。

## 3. 目录

```
openpilot/tesla/
  plugin.py                 Python 插件接口（Plugin 基类，所有钩子都有默认空实现）
  manifest.py               插件清单格式、类别、资源声明、冲突裁决（只用标准库）
  plugins/__init__.py       自动发现插件（PLUGINS），以及 card/plannerd/manager 用的调用宿主（总开关、冲突、资源检查、出错隔离）
  plugins/<id>/plugin.json  插件清单；plugins/<id>/plugin.py 插件代码；plugins/<id>/ui.py 可选，放磁贴和叠加层
  plugins/gen_params.py     把各插件清单里的 params 生成到 common/plugin_params.inc
  plugins/auto_speed/       自动设定速度
  plugins/traffic_light/    红绿灯停车
  plugins/ambient_light/    盲区氛围灯
  plugins/external_compute/ 外接算力桥接
  plugins/speed_card/ lead_card/ speed_limit_card/ car_tile/ map_tile/ clock_tile/ ip_tile/ blindspot_edges/   大屏磁贴和盲区边框（只显示）
  plugins/bms/              电池数据（card 解析）和 Battery 磁贴
  ui/screen.py ui/tile.py ui/tiles.py ui/slots/   大屏磁贴宿主、磁贴基类、布局模型（无 pyray）、内置磁贴（slots/settings.py 设置页磁贴）
  ui/plugin_ui.py           UI 侧插件加载：找到 Tile、HudOverlay 和 ScreenOverlay，插件关闭时隐藏
  ui/plugins_page.py ui/store_page.py   mici 设置里的"Plugins"页和商店页（小屏用）
  ui/offroad.py ui/pages/   大屏停车时的详情页（见第 9 节）
  ui/settings_page.py ui/settings_meta.py        Tesla 设置页（上游 Tesla 选项、DM、地图）
opendbc_repo/opendbc/safety/plugins/
  plugin.h registry.h auto_speed.h ambient_light.h   panda safety 插件（见第 6 节）
```

## 4. Python 插件接口（`openpilot/tesla/plugin.py`）

### 4.1 插件清单 `plugin.json`

```json
{
  "id": "my_feature", "name": "My Feature", "version": "1.0.0", "api": 1,
  "category": "longitudinal_planning", "entry": "plugin:MyFeature",
  "author": "someone", "description": "What it does and what it needs.",
  "priority": 100, "enable_param": "XpMyFeature",
  "claims": ["long.target", "can.tx:0x3C2:1"],
  "settings": [{"key": "XpMyFeatureLevel", "label": "Level", "range": [0, 10, 1, "", 1]}],
  "params": {"XpMyFeature": {"type": "BOOL", "default": "0"}, "XpMyFeatureLevel": {"type": "INT", "default": "5"}}
}
```

| 字段 | 含义 |
|---|---|
| `id` | 必须和目录名一致 |
| `api` | 插件面向的宿主接口版本，必须等于 `manifest.API_VERSION`（现在是 1），否则不加载 |
| `category` | 类别，见下表 |
| `entry` | 插件包内的 `模块:类名` |
| `priority` | 数字越小越优先：争同一个独占资源时它赢；同类插件的执行顺序也按它，数字相同按 id |
| `enable_param` | BOOL 总开关；`null` 表示一直开启。关闭时 card 不创建插件、进程不启动、plan filter/目标车速不加载、UI 不显示。车端下一次行程生效，UI 1 秒内生效 |
| `claims` | 要用的资源，见下表；没声明的一律被拒绝 |
| `settings` | 设置项：只有 key 和 label 是开关；带 `range: [最小, 最大, 步长, 单位, 除数]` 或 `choices: [[标签, 值], ...]` 是选择项 |
| `params` | 参数声明，格式见 `gen_params.py`；改完运行 `python3 openpilot/tesla/plugins/gen_params.py` |

清单有错（id 不对、类别未知、api 不匹配、资源格式错、JSON 坏了）或代码导入失败的插件会被跳过，在 Plugins 页顶部显示 "Failed: <id>"，不影响其他插件。

### 4.2 类别（`manifest.CATEGORIES`，按控制链路顺序）

控制链路：`perception_model` 感知模型、`object_fusion` 前车和目标融合、`vehicle_params` 标定和车辆参数、`engagement` 接管状态机、`driver_monitoring` 驾驶员监控、`lateral_planning` 横向规划、`longitudinal_planning` 纵向规划、`lane_change` 变道、`navigation` 导航驾驶、`controller` 控制器、`actuation` 执行和车端报文、`safety_fallback` 安全兜底和 Autopilot 交接。

暂无钩子的类别：`perception_model`、`object_fusion`、`vehicle_params`、`engagement`、`driver_monitoring`、`lateral_planning`、`navigation`、`safety_fallback`。这些类别现在只用于分组显示；插件可以用通用钩子（`processes`、`alert_source` 等），但还不能替换 SP 的对应环节。真有插件需要时再加钩子，不预先加。

有插件要做时，按下面的顺序考虑加钩子（越靠前越可能先用到、风险越低）：

| 顺序 | 类别 | 可能的钩子 | 理由 |
|---|---|---|---|
| 1 | `navigation` | 不需要新钩子：`source:map` + `processes()` 发布 `liveMapDataSP` / `navInstruction`（第 8 节） | 现有接口已够用，先写插件 |
| 2 | `vehicle_params` | 只读的参数修正（例如转向比、质量），在 card 发布 CarParams 前调用 | 影响小、可在本机验证 |
| 3 | `driver_monitoring` | 替换或补充 DM 的提醒策略（只能更严格） | Tesla 页已有 DM 选项，需求明确 |
| 4 | `object_fusion` | 在 radard 之后修正前车（`radarState`），只能让前车更近 | `radar_interface` 只覆盖原始雷达 |
| 5 | `lateral_planning` | 修正或替换模型给的路径 | 已有 `lat_correction` 和 `lat_controller`，多数需求可以先用它们 |
| 6 | `engagement` | 接管条件（只能更严格） | 涉及 selfdrived 状态机，风险高 |
| 7 | `perception_model` | 替换模型 | 需要模型管线和算力，变更最大 |
| 8 | `safety_fallback` | 退出和 Autopilot 交接策略 | 安全相关，必须先有 panda 侧方案 |

其他：`data_source` 数据源和外接算力、`alerts` 报警、`body_comfort` 车身和舒适、`ui` 界面、`tools` 工具和诊断。

### 4.3 资源声明（claims）和冲突

| 资源 | 含义 | 独占 |
|---|---|---|
| `can.tx:0x<地址>:<总线>` | 发送这个 CAN 地址（还需要 panda safety 插件） | 是 |
| `process:<名字>` | 运行这个 manager 进程 | 是 |
| `source:<数据>` | 提供某类数据，如 `source:radar`、`source:lanes` | 是 |
| `role:<环节>` | 占用一个可替换的环节，如 `role:lateral.controller` | 是 |
| `long.target` | 使用 `long_target` 钩子 | 否，宿主按固定规则合并 |
| `plan.filter` | 使用 `plan_filter` 钩子 | 否，按优先级串联 |
| `alert` | 使用 `alert_source` 钩子 | 否，每个级别取优先级最高插件的第一条 |
| `lat.correction` | 使用 `lat_correction` 钩子 | 否，按优先级串联，总改动有上限 |
| `external.provider` | 使用 `external_provider` 钩子 | 否，所有 provider 一起运行 |
| `role:lane_change.policy` | 使用 `lane_change_policy` 钩子 | 是 |
| `role:lateral.controller` | 替换横向控制器（`lat_controller`） | 是 |
| `role:long.planner` | 替换纵向规划（`long_planner`），可以自带跟车逻辑 | 是 |

- **冲突裁决**：两个已开启的插件声明了同一个独占资源时，`priority` 小的生效（相同则按 id），另一个整体不生效，Plugins 页显示 "conflict"。在 Plugins 页打开一个插件，会自动关掉和它冲突的插件。
- **合并规则由宿主固定**：插件改不了。目标车速的规则见下面 `long_target`。
- **底线**：不管优先级多高，都越不过 SP 的限制和 panda safety。

### 4.4 钩子

| 钩子 | 调用方 / 时机 | 用途 |
|---|---|---|
| `__init__(CP, params)` | card，识别车型后调用一次 | 创建 CANParser，读取参数 |
| `setup(CP_SP)` | card，发布 CarParamsSP 之前 | 设置 flags；需要 panda 插件时置 `safetyParam` 位 |
| `observe_can(can_list, now_ns)` | card，每批 CAN | 只读解析；返回需要立即发送的帧（少用） |
| `publish_state(CS_SP)` | card，每个周期 | 填写 carStateSP 里本插件的字段；也可以从这里读 `CS_SP.speedLimit` |
| `control_sends(CS, CC, now_ns)` | card，每个控制周期 | 返回要追加发送的 `CanData` |
| `service_params(params)` | card，约 10 Hz | 重新读取实时设置 |
| `processes()`（类方法） | manager | 额外进程。manager 相关的 import 写在方法内部 |
| `long_target(CP, params)`（类方法） | plannerd，每个计划周期 | 返回带 `update(sm, v_ego, v_cruise)` 的对象，给出目标车速（m/s）或 None。低于巡航车速：和 SP 自己的限速一样取最小；高于巡航车速：只替换驾驶员设定车速，且只在已接管、没踩油门/刹车、没 override 时生效，多个插件取最低，上限 `V_CRUISE_MAX`。MPC 跟车、模型和 SP 的限速功能仍然取最小，所以加速不会越过它们 |
| `alert_source(CP, params)`（类方法） | selfdrived，每周期（100 Hz） | 返回带 `update(sm) -> list[PluginAlert]` 的对象。`PluginAlert(severity, title, body)`，severity 为 `info`（无声）、`warning`（提示音）、`critical`（警告音）。插件报警在任何状态都显示，不会让系统退出，优先级最高到 MID，SP 自己的退出和严重报警永远优先。标题最多 60 字符，正文 80 |
| `lane_change_policy(params)`（类方法） | modeld 的 DesireHelper | 返回带 `allow(carstate, direction, default) -> bool` 的对象，只替换 SP 的"不用推方向盘就开始变道"这一个判断（`default` 是 SP 原来的结果）。打转向灯、最低车速、盲区和路沿检查仍然强制生效 |
| `lat_correction(CP, params)`（类方法） | controlsd，横向生效时每个控制周期 | 返回带 `update(sm, v_ego, curvature) -> 曲率或 None` 的对象。多个修正按优先级串联；总改动不超过 0.5 m/s² 横向加速度对应的曲率（低于 5 m/s 按 5 m/s 算），NaN/inf 被忽略；之后 SP 的 `clip_curvature`（ISO 加加速度和加速度限制）照常生效 |
| `lat_controller(CP, CP_SP, CI, params)`（类方法） | controlsd | 返回和 `LatControl` 接口一致的对象（`update(...) -> (steer, 转角, lac_log)`、`reset()`），替换 SP 的横向控制器。输出不和 SP 比较、不额外限制，只靠车端转角速率限制和 panda 兜底。SP 的控制器一直并行运行；插件出错或输出 NaN/inf 时，本次运行剩下的时间都改用 SP 的输出 |
| `long_planner(CP, CP_SP, params)`（类方法） | plannerd，SP 算完之后 | 返回带 `update(sm, sp) -> plan 或 None` 的对象。`sp` 是 SP 的结果（`speeds`、`accels`、`jerks` 各 17 个点，`a_target`、`should_stop`）；返回同样字段的 plan 就替换 SP 的计划，**包括跟车**。`a_target` 限制在 ACCEL_MIN/MAX；长度不对、NaN/inf 或 None 时保留 SP 的计划；出错的规划器被停用。SP 的 MPC 仍然运行，FCW 仍由它决定 |
| `plan_filter(CP, params)`（类方法） | plannerd | 返回带 `publisher(pm, sm)` 的对象，用来收紧纵向计划；不需要就返回 None |
| `radar_interface(CP, CP_SP, params)`（类方法） | card，启动时 | 需要 `source:radar`。返回和 `RadarInterfaceBase` 接口一致的对象（`update(can_list) -> RadarData 或 None`），替换车型自带的雷达。原车雷达一直并行运行；插件出错后本次运行剩下的时间回到原车雷达 |
| `external_provider(params)`（类方法） | externald，启动时 | 需要 `external.provider`。返回一个 provider（`poll`、`send`、`close`），见 8b |
| `SERVICES` | plannerd、selfdrived、controlsd | 钩子需要额外订阅的服务；这些服务不参与存活和有效性检查，不会影响接管 |

SP 里的调用位置：`selfdrive/car/card.py`（`CarPlugins`、`radar_interface`）、`selfdrive/controls/plannerd.py`（`services`、`plan_filters`、`plan_sink`、`long_targets`）、`sunnypilot/selfdrive/controls/lib/longitudinal_planner.py`（`apply_long_targets`）、`selfdrive/selfdrived/selfdrived.py`（`alert_sources`、`update_alerts`）、`sunnypilot/selfdrive/selfdrived/events.py`（插件报警定义，见 `openpilot/tesla/alerts.py`）、`selfdrive/controls/lib/desire_helper.py`（`lane_change_policies`、`lane_change_allowed`）、`selfdrive/controls/controlsd.py`（`lat_corrections`、`apply_lat_corrections`、`lateral_controller`）、`selfdrive/controls/lib/longitudinal_planner.py`（`apply_long_planner`）、`sunnypilot/system/fork_processes.py`（`processes`，以及 `holds(params, "source:map")` 关掉 SP 的地图进程）。

## 5. 写一个新插件

### 5.1 步骤

1. **先想清楚类型**，选最小的一种：
   - 只显示：一个 `ui.py` 磁贴或叠加层，读已有的消息。`claims` 为空，可以默认开启。
   - 读车端数据再显示：card 钩子 `observe_can` 解析 + `publish_state` 写到 `carStateSP` 的新字段，`ui.py` 磁贴订阅 `carStateSP`。参考 `plugins/bms/`。
   - 影响驾驶：用第 4.4 节的规划/控制钩子，声明对应 claim；能"只收紧"的就不要"替换"。
   - 发 CAN：`control_sends` + `can.tx` claim + panda safety 插件（第 6 节）。参考 `plugins/auto_speed/`、`plugins/ambient_light/`。
   - 独立进程：`processes()` + `process:<名字>` claim。参考 `plugins/traffic_light/`、`plugins/external_compute/`。
2. **写失败模式**（在检查脚本或模块 docstring 里列出），再写检查：纯逻辑放进 `tools/sp_tesla_e2e/` 里已有的 `*_check.py`（或插件自己的 `tests/`），渲染和触摸只能在设备上用 `big_screen_e2e.py` 确认。
3. **建目录** `openpilot/tesla/plugins/<id>/`：空的 `__init__.py`、`plugin.json`（4.1）、`plugin.py`、可选的 `ui.py`：

```python
# plugin.py
from openpilot.tesla.plugin import Plugin

class MyFeature(Plugin):   # 名字、开关、设置都来自 plugin.json，代码里不要写
  def observe_can(self, can_list, now_ns):
    for mono_time, frames in can_list:
      for address, data, bus in frames:
        ...                # 只读解析，记下最新一帧和时间
    return []

  def publish_state(self, CS_SP):
    CS_SP.myFeature.available = ...   # 过期就标成不可用，不要发旧值

# ui.py
from openpilot.tesla.ui.tile import Tile
from openpilot.tesla.ui.tiles import TileSpec

class MyTile(Tile):
  SPEC = TileSpec("my_feature", "My Feature", sizes=("small", "medium"), services=("carStateSP",), hz=2)

  def state(self, sm):              # 返回可比较的值；变了才重画
    v = sm["carStateSP"].myFeature
    return f"{v.value:.0f}" if v.available else None

  def draw(self, rect, size, state):
    self.draw_value(rect, state or "--", "unit")
```

4. **新消息字段**：加在 `cereal/custom.capnp`（只追加，见规则 7），设备上要重新编译（scons）。
5. **参数**：写进 `plugin.json` 的 `params` 和 `settings`，运行 `python3 openpilot/tesla/plugins/gen_params.py`，把 `common/plugin_params.inc` 一起提交。
6. **跑本机检查**（第 11 节），全部通过后按功能拆分提交；有 C 代码的再编译 panda、跑 safety 测试和 MISRA；最后上设备实测，报告设备上的 commit。
7. **不用注册**：插件自动被发现，插件市场按类别显示它的开关、版本、作者、简介和设置。也可以放进插件商店仓库发布（8c）。

### 5.2 API 一览

**清单和元数据**（`openpilot/tesla/manifest.py`）：`plugin.json` 字段见 4.1；`CATEGORIES`（类别和显示名）；`API_VERSION`（现在 1）；claims 格式见 4.3。宿主从清单填好 `Plugin` 的类属性：`NAME`、`TITLE`、`DESCRIPTION`、`CATEGORY`、`PRIORITY`、`ENABLE_PARAM`、`CLAIMS`、`SETTINGS`、`MANIFEST`（含 `version`、`author`），插件只读。插件自己可以设 `SERVICES`（钩子要额外订阅的服务）。

**Python 钩子**（`openpilot/tesla/plugin.py` 的 `Plugin`，全部有空的默认实现，详细规则见 4.4）：

| 进程 | 钩子 | 需要的 claim |
|---|---|---|
| card | `__init__(CP, params)`、`setup(CP_SP)`、`observe_can(can_list, now_ns)`、`publish_state(CS_SP)`、`service_params(params)` | 无 |
| card | `control_sends(CS, CC, now_ns) -> [CanData]` | `can.tx:...` |
| card | `radar_interface(CP, CP_SP, params)` | `source:radar` |
| manager | `processes() -> [ManagerProcess]` | `process:<名字>` |
| plannerd | `long_target(CP, params)` | `long.target` |
| plannerd | `plan_filter(CP, params)` | `plan.filter` |
| plannerd | `long_planner(CP, CP_SP, params)` | `role:long.planner` |
| controlsd | `lat_correction(CP, params)` | `lat.correction` |
| controlsd | `lat_controller(CP, CP_SP, CI, params)` | `role:lateral.controller` |
| modeld | `lane_change_policy(params)` | `role:lane_change.policy` |
| selfdrived | `alert_source(CP, params)`，返回 `PluginAlert(severity, title, body)` | `alert` |
| externald | `external_provider(params)`，返回 `Provider`（`poll`、`send`、`close`） | `external.provider` |

`can_list` 每一项是 `(mono_time_ns, [(address, data, bus), ...])`；总线编号用 `opendbc.car.tesla.values.CANBUS`（`party`、`vehicle`、`autopilot_party`）。解析可以用位运算，也可以用 `opendbc.can.CANParser` 读 `opendbc/dbc/` 里的 DBC。

**参数**：钩子拿到的 `params` 是 `openpilot.tesla.plugin_params.ParamsView`：`get(key)`、`get_bool(key)`、`put(key, value)`、`put_bool(key, value)`、`remove(key)`，内置和商店插件用法一样。

**宿主工具**（`openpilot/tesla/plugins/__init__.py`，给宿主和页面用，插件一般不需要）：`PLUGINS`、`is_enabled(cls, params)`、`active(params)`、`resolve(params) -> (生效的插件, 冲突)`、`holds(params, claim)`、`FAULTS_PARAM`（`XpilotPluginFaults`）、`LOAD_ERRORS`。

**UI**（插件的 `ui.py`，无参构造，插件关闭时自动隐藏，连续出错 3 次停止绘制）：

| 类 | 接口 | 用途 |
|---|---|---|
| `ui.tile.Tile` | `SPEC`、`state(sm)`、`draw(rect, size, state)`；画图用 `face(rect)`、`draw_value(rect, value, unit, sub)`、`draw_lines(rect, lines, size)`，以及模块函数 `text(...)`、`text_w(...)` 和颜色 `DIM`；颜色只用 `Tile.COLOR` | 大屏磁贴 |
| `ui.tiles.TileSpec` | `id, title, sizes, services, show, hz, order`（见第 9 节） | 磁贴声明 |
| `ui.plugin_ui.ScreenOverlay` | `update(sm)`、`draw(zones)` | 大屏行驶时的整屏叠加层 |
| `ui.plugin_ui.HudOverlay` | Widget：`update()`、`render(rect)`；读 `ui_state.sm` | mici 行驶画面叠加层 |

**消息**（插件可以读或发布）：`carStateSP` 里插件自己的字段（例 `teslaBattery`）、`liveMapDataSP` 和 `navInstruction`（地图和导航，第 8 节）、`externalIn` / `externalOut`（外接算力，8b），以及 SP 的所有服务（`carState`、`radarState`、`longitudinalPlan`、`deviceState` 等）。

**panda safety**（C，内置插件才可以）：`safety_plugin` 结构（`msg`、`active`、`rx`、`tx`、`reset`），见第 6 节。

**商店**（8c）：插件包和内置插件同样格式；代码按 `xpilot_ext.<id>` 导入、内部用相对导入；参数存在 `.params` 文件里；二进制要在清单写 `platform`。

## 6. panda safety 插件接口（`opendbc/safety/plugins/`）

```c
typedef struct {
  CanMsg msg;                          // 本插件唯一负责的发送报文（地址、总线、长度）
  bool (*active)(void);                // 按 safety 模式和参数决定是否生效
  void (*rx)(const CANPacket_t *msg);  // 每条有效的接收报文都会调用（用来记录模板、状态）
  bool (*tx)(const CANPacket_t *msg);  // 校验一次发送；返回 true 才放行
  void (*reset)(void);                 // safety 模式切换时调用
} safety_plugin;
```

规则：一个插件只负责一个报文，原有 safety 模式的白名单和检查一律不改；校验内容至少包括报文模板、新鲜度、频率限制、`controls_allowed`、只在 Tesla 模式下生效，以及会话上限。

**当前状态：libsafety 在 Mac（Apple clang 16）和 Linux 主机上编译；`test_tesla.py` 和 `test_xpilot_plugins.py` 通过；MISRA（cppcheck）在 Linux 主机上 0 条报告。** 只保留 Tesla 后，lateral.h/longitudinal.h/safety.h 里给其他车型用的共用函数没人调用，在 `tests/misra/main.c` 里用 `SAFETY_UNUSED` 标出，stock 头文件不改。会话上限：auto_speed 每次最多 50 格、空闲 3 秒算新会话；ambient_light 每次最多 150 帧/15 秒、空闲 1 秒算新会话。 `safety.h` 里有 4 处调用：
1. include `opendbc/safety/plugins/registry.h`；
2. `safety_rx_hook` 里，`valid` 为真时调用 `safety_plugins_rx(msg)`；
3. `safety_tx_hook` 里，属于插件的报文交给 `plugin->tx(msg)` 校验，其余报文仍走原模式；
4. `set_safety_hooks` 里调用 `safety_plugins_reset()`。

上车前必须在 Mac 或设备上编译 panda 和 libsafety，跑 safety 测试，并补上插件的 safety 测试。

## 7. 雷达接入接口

写一个声明 `source:radar` 的插件，实现 `radar_interface` 钩子（见 4.4）。插件关闭、没有声明或出错时用原车雷达。外接雷达如果需要发送报文，还要声明 `can.tx` 并配一个 panda safety 插件。

`opendbc_repo/opendbc/car/car_helpers.py` 里的 `RADAR_PLUGINS` 是旧接口，已不用，保持为空（opendbc 不改）。

## 8. 地图接口

- **数据**：任何数据源只发布 `liveMapDataSP`，包括限速、前方限速、路名、`targetVelocities`（弯道目标速度）、`source`。
- **默认数据源**：SP 的 OSM（`mapd`、`mapd_manager`、`map_osm` 进程）。
- **新增数据源**：写一个插件，声明 `source:map` 和 `process:<名字>`，用 `processes()` 启动自己的进程发布 `liveMapDataSP`（可以继承 `sunnypilot/mapd/live_map_data/base_map_data.py`）。这个插件开启时，SP 的三个地图进程自动不启动；关掉插件就回到 OSM。
- **已知问题**：地图插件开启时，Tesla 页的 "OSM Map Data" 开关仍显示原值，但不起作用。
- **导航**：发布 `navInstruction`，再把 256×256 地图图像发到 VisionIPC 的 `mapsd` 流。

## 8b. 外接算力接口（`plugins/external_compute/`）

- **消息**：`externalIn`（外部 → 设备）和 `externalOut`（设备 → 外部），类型 `ExternalData`：`source`、`kind`（如 `llm.reply`、`vision.lanes`）、`seq`、`payload`（JSON 文本）、`validForMs`（0 表示不过期）。
- **只做建议**：外部数据不能直接控制车辆。要用它的插件订阅 `externalIn`，用 `provider.is_fresh()` 检查时效，再通过自己的钩子（如 `long_target`）和限制生效。
- **桥接进程** `externald`：插件开启时运行，把所有 provider 收到的消息发到 `externalIn`，把 `externalOut` 转给 provider。
- **provider 接口**（`provider.py`）：`poll(timeout)`、`send(msg)`、`close()`。现有 `tcp.py`：外部设备通过网线、USB 网卡或 WiFi 连到设备端口（默认 8770），按行发 JSON，第一行必须是 `{"hello": "<令牌>", "name": "..."}`。令牌在设备的 `/data/params/d/XpilotExternalToken`，首次启动自动生成。明文 TCP，只在可信网络上用。
- **新增 provider**（例如调用大模型 HTTP API）：写一个插件，声明 `external.provider`，在 `external_provider(params)` 钩子里返回一个 `Provider` 子类的实例。`external_compute` 自己就用这个钩子提供 TCP provider。`externald` 只在 `external_compute` 开启时运行。

## 8c. 插件商店（`openpilot/tesla/store.py`）

- **仓库**：`github.com/onemiless/xpilot-plugins`。`plugins/<id>/` 是源码，`tools/build_index.py` 生成可复现的 `dist/<id>-<版本>.tar.gz` 和 `index.json`（每个插件的 url 和 sha256）。第三方提 PR，维护者审核后合并。**暂不签名**：sha256 只防下载损坏或被替换，可信度来自审核过的仓库。
- **设备端**：Plugins 磁贴就是插件市场（见第 9 节），左下角 Refresh 拉取索引（第一次打开时自动拉一次）。只能停车时安装、更新、删除，重启后生效。
- **安装位置**：`/data/xpilot_plugins/<id>/`（可用环境变量 `XPILOT_PLUGINS_DIR` 改），系统更新不会动它。安装过程：限制大小下载 → 校验 sha256 → 只解出普通文件（拒绝 `../`、绝对路径、链接）→ 校验清单（id、api、入口模块、不能和内置插件同 id、参数名不能重复）→ 用改名的方式整体替换。任何一步失败，原来装的版本保持不变。
- **下载插件的代码**：作为包 `xpilot_ext.<id>` 导入，插件内部要用相对导入（`from .controller import X`）。
- **下载插件的参数**：不编译进 Params，而是存在 `/data/xpilot_plugins/.params/<key>`，支持 BOOL、INT、FLOAT、STRING、JSON。宿主把交给插件、开关判断和设置页的 params 都包了一层（`plugin_params.ParamsView`），插件照常用 `params.get/get_bool/put`。删除插件时参数值保留，重装后设置还在。
- **带二进制的插件**：需要编译的代码（例如 acados 求解器）以预编译二进制发布，清单里写 `"platform": {"machine", "python"}`（由插件自己的 `build_native.py` 在目标设备上生成）。设备只显示、安装和加载平台一致的版本；升级 Python 等导致不一致时，插件被跳过并显示 "Failed"。panda safety 插件只能内置。

## 9. UI（大屏，2160×1080，UI v4：磁贴）

整个大屏是 Windows Phone / Win 8 风格的磁贴（tile）。不画图的布局逻辑在 `openpilot/tesla/ui/tiles.py`（`tile_layout_check.py` 在本机测），宿主在 `ui/screen.py`，磁贴基类在 `ui/tile.py`。

- **网格**：8 列 × 4 行，格子 250 px，间隙 12 px（步距 262），整体居中，原点 `ORIGIN=(38,22)`。磁贴尺寸（列×行）：`small` 1×1、`medium` 2×2、`wide` 4×2、`large` 4×4。
- **两套布局**：停车布局（`show` 为 `always`/`offroad` 的磁贴，整屏 32 格）和行驶布局（`show` 为 `always`/`onroad` 的磁贴，绕开 mici 画面的 14 格），各自保存顺序、尺寸、位置和隐藏列表，都在停车时编辑。
- **排布**：先放固定了位置的磁贴（列表顺序；位置放不下、越界或压到 mici 画面就当作没固定），再把其余磁贴按列表顺序放进第一个放得下的位置。扫描顺序：停车时按列（第 0 列从上到下，再第 1 列……，Win 8 横屏）；行驶时按行、每行从两边往中间（第 0 列、第 7 列、第 1 列、第 6 列……），所以左右两边交替填充。前面留下的空洞会被后面的小磁贴填上；放不下的磁贴不显示（编辑模式里可以从"添加"重新放）。
- **行驶时**：mici 画面固定在 `VIEW=(300,59,1560,699)`（第 1–6 列 × 第 0–2 行这块区域里按 536:240 居中，缩放约 2.91），这 18 格不放磁贴；磁贴绕着它排：第 0 列、第 7 列和第 3 行的第 1–6 列，共 14 格。没固定位置的磁贴在自己支持的尺寸里从保存的尺寸往小试，放得下就用。行驶时磁贴不接收触摸，报警只由 mici 在画面内显示一次。
- **停车时**：显示停车布局。点一下磁贴打开它的详情页（有 `PAGE` 的）；长按（0.6 s）磁贴或空格进入编辑模式。
- **编辑模式**（只在停车时）：三个按钮 `Park | Drive | Done`（`tiles.bar_buttons(placed, started)`）：编辑停车布局时竖排放进最后一个空格（第一个空格是"+"），只剩不到两个空格时才横排压在底部居中；编辑行驶布局时横排在 mici 画面占位的底部：Park/Drive 切换正在编辑的布局（编辑行驶布局时 mici 画面的位置画成一块灰色占位），Done 退出。其他磁贴变暗，选中的磁贴右上角是"取消固定"圆钮、右下角是"改尺寸"圆钮（图形用线画，不用字符）。点改尺寸按 `sizes` 的顺序循环；点取消固定把它移到隐藏列表；按住拖动磁贴，松手处的格子成为它的固定位置（磁贴左上角落在这格，超出网格就往回挪；压到 mici 画面则不动），和它重叠的其他固定磁贴变回不固定；点别的磁贴改选它；第一个空格显示"+"，点它打开"Add tiles"页，列出隐藏和放不下的磁贴，点一个就以它最小的尺寸固定到最后（不固定位置）；点其他空格或再点一次选中的磁贴取消选中。
- **保存**：布局存在 `XpilotTileLayout`（JSON `{"park": {"tiles": [[id, 尺寸, 列, 行], ...], "hidden": [id, ...]}, "drive": {...}}`，列/行为 `null` 表示不固定；旧格式 `{"tiles": [[id, 尺寸]], "hidden": [...]}` 读作停车布局），不进 `params_keys.h`，由 `plugin_params.ParamsView` 存成文件 `/data/xpilot_plugins/.params/XpilotTileLayout`。读取时丢掉不认识的 id、不属于这套布局的磁贴和不支持的尺寸；新出现的磁贴按 (`order`, `id`) 用默认尺寸排到最后；插件关闭时它的磁贴不显示但位置保留。
- **加磁贴**：插件的写在 `plugins/<名字>/ui.py`；不属于插件的放 `openpilot/tesla/ui/slots/`。继承 `Tile`，写 `SPEC = TileSpec(id, title, sizes, services, show, hz, order)`，会被自动发现。磁贴没有自己的颜色：都画成 `Tile.COLOR`。
  - `sizes`：支持的尺寸，第一个是默认；要在行驶时显示必须包含 `small`。
  - `state(sm)`：读数据，返回这块磁贴要显示的内容（可比较的值）。最多每秒调用 `hz` 次；**只有返回值变了（或尺寸变了）才重画**，其余帧画缓存的纹理。`draw(rect, size, state)` 画磁贴正面。
  - 外观用 `Tile.face(rect, ...)`（底色、左下角标题）、`draw_value`（大数字、单位、灰色副行）或 `draw_lines`，保持统一。文字只用 ASCII（设备字体缺 `‹ › · —` 等字，会显示成 `?`；`tile_layout_check.py` 检查）。
  - 连续出错 3 次停止绘制，不影响其他磁贴。
- **配色**：`tiles.THEMES`（Cobalt、Teal、Emerald、Crimson、Violet、Graphite），在 Toggles 页的"Tile color"里选，存在 `XpilotTileTheme`（STRING，和布局一样存成 `.params` 文件，不进 `params_keys.h`）。宿主启动时和每次回到磁贴屏时读取，设置 `Tile.COLOR` 并让所有磁贴重画；编辑栏的选中按钮也用这个颜色。
- **插件市场**（Plugins 磁贴，`pages/plugins.py`）：左边一列是 `manifest.CATEGORIES` 里有插件的分类（加载失败时最前面多一个 "Failed"），左下角是商店的 Refresh；右边是选中分类的列表：每个插件一行开关，标题下是版本、作者和简介，后面是商店里有、这次没加载的插件（Install）。点插件行（开关以外）打开插件页：开关、设置项、Version/Author/Category/Claims/Priority，商店下载的插件还有 Update/Remove。分类和行由 `offroad.market_sections` 生成（`offroad_pages_check.py` O12），分类未知的商店插件归到 tools。原来单独的 Store 子页已删除。
- **Tesla 页**（`pages/tesla.py`）：Vehicle 组第一行是 "Car model"，打开子页选 Auto 或 sunnypilot 车型列表（`car_list.json`）里的某一款 Tesla。选车型写 `CarPlatformBundle`（`{**car_list[名字], "name": 名字}`，和 params_migration 一样），card 下次启动时把 `platform` 当作固定指纹；Auto 删除这个参数，恢复自动识别。只在停车时可用。列表由 `offroad.tesla_models` 生成（O13 检查平台都在 opendbc 里）。
- **设置磁贴（内置）**：Status（原 Home）、Toggles、Models、Plugins、Tesla、Network、Device、Software、Developer，放在 `ui/slots/settings.py`，`show="offroad"`。`PAGE` 是 `ui/pages/` 里对应的原生页面（Models 是 `pages/models.py` 的 `ModelsPage`：当前模型和下载状态、小模型/大模型列表子页（默认模型，再按文件夹分组，收藏在前，按钮 CURRENT/QUEUED/SELECT）、取消下载、刷新列表、清除缓存；选择、刷新、清缓存只在停车时可用）。设置磁贴不再打开 mici 页面（`offroad_pages_check.py` O1 不允许 `MICI`）。
- **详情页（WP 风格）**：整屏。左上角是返回圆钮（线画的箭头，点击区 `BACK=(0,0,140,230)`），右边小号大写的上级名（`XPILOT` 或父页面名），下面是大号小写标题；内容区 `CONTENT=(140,230,1920,850)`，由宿主按屏幕像素直接画 `ui/pages/` 里的原生列表页（tici 的 `list_view`/`scroller_tici` 控件）。页面打开的子页（如 Plugins 的插件页、Tesla 的 Car model）压栈，返回一层层退回，退到底回到磁贴屏。
  - 每页一个模块：`openpilot/tesla/ui/pages/<页>.py`，带 `show_event` 的 Widget（`show_event` 时从 params 重新读状态）。共用部分在 `pages/base.py`。不画图的逻辑在 `ui/offroad.py`（视口模式、触摸映射、插件行、商店任务 `StoreJobs`、停车提示），`offroad_pages_check.py` 在本机测。
  - 页面内容和 mici 一致（同样的参数、动作和可用条件，行驶中或接合时不能改）。重置校准、重启、关机、卸载用 `ConfirmDialog`；这些 tici 弹窗压在导航栈上，在 mici 那一遍里隐藏，由宿主全屏画（弹窗打开时页面不接收触摸）。
  - Device 的子页都是原生页面（`pages/training.py`、`terms.py`、`regulatory.py`、`driver_camera.py`），用 `ListPage.open()` 打开；法规信息（`mici_fcc.html` 是 comma four 的标签）只在 mici 硬件上显示；训练指南和车内摄像头只在停车时可用，在 `hide_event` 和息屏超时时清掉 `IsDriverViewEnabled`（息屏后不再渲染；这个参数开着时 hardwared 不会进入 onroad）。`pages.base.back()` 调宿主的 `back()` 关闭当前页。
  - 宿主里已经没有 3 倍的 mici 页面；`FALLBACK_VIEW=(296,295,1608,720)` 只留给意外压到 main 之上的 mici 控件。
  - 页面调用 `self.open(None, None)` 表示返回上一层。
  - 开机引导：mici 的 `OnboardingWindow` 在栈里时，宿主不画 mici 纹理，改为全屏画原生 `pages/onboarding.py` 的 `OnboardingPage`（同样的参数：`HasAcceptedTerms`、`HasAcceptedTermsSP`、`CompletedTrainingVersion`、`DoUninstall`；拒绝前在页内再确认一次），完成后宿主 `pop_widgets_to(main)`，和 mici 的回调一样。
- **不画 mici 纹理**靠 `system/ui/lib/application.py` 里一行钩子：`host.viewport()` 返回 `None` 时跳过 `draw_texture_pro`。此时 `to_logical` 把所有触摸映射到 mici 屏幕很远之外，下面继续运行的 mici 控件不会响应。这是对 SP 文件唯一的改动。
- **整屏叠加层**：`ScreenOverlay`（`update(sm)`、`draw(zones)`），行驶时在磁贴之后绘制；`zones` 是 `VIEW` 四周的 left/right/top/bottom 和 view 本身的屏幕矩形。出错隔离同上，插件关闭时隐藏。例：`blindspot_edges`。
- 已知：`NetworkUI` 自己建一个 `WifiManager`，mici 的 `NetworkLayoutMici` 只在 mici 设置里构造（大屏不构造），所以大屏进程里只有 Network 页那一个。
- 主机检查只验证逻辑和静态结构，**没有渲染过**；字号、间距、弹窗位置要在设备上用 `big_screen_e2e.py` 截图确认。
- 检查：`tools/sp_tesla_e2e/tile_layout_check.py`（网格、排布、行驶避让、编辑操作、手势、保存格式、ASCII）、`offroad_pages_check.py`（本机）；渲染和触摸：`tools/sp_tesla_e2e/big_screen_e2e.py`（只能在设备上跑，截图磁贴屏、编辑模式、每个设置详情页、插件市场的分类和插件页，检查停车时除 Models 外不画 mici 纹理）。

## 10. 现有插件

| 插件 | 功能 | 参数 | panda |
|---|---|---|---|
| `auto_speed` | 按车辆限速（DAS_fusedSpeedLimit）加偏移，用右滚轮单格报文调整巡航设定速度；手动拨滚轮后暂停，反方向拨两下恢复 | `TeslaAutoSpeedLimit`、`TeslaAutoSpeedLimitOffset` | `auto_speed.h`（0x3C2，需要 vehicle bus 和 openpilot 纵向） |
| `traffic_light` | 读取 Tesla 自身的红绿灯感知（APP_trafficControl），由 trafficcontrold 和计划仲裁器在红灯前停车（只收紧） | `TeslaTrafficSignalControlEnabled`、`TeslaTrafficStopReference`、`TeslaTrafficControlMaxSpeed` | 无发送 |
| `ambient_light` | 盲区有车时把氛围灯点成红色；区分昼夜亮度 | `TeslaBlindspotAmbient*` | `ambient_light.h`（0x679，`safetyParam` 位 `0x2000`，需要 vehicle bus） |
| `external_compute` | 外接算力桥接（见 8b），本身不控制车辆 | `XpilotExternal*` | 无发送 |
| `speed_card` | 大屏磁贴：车速（仪表车速）和 SET 设定车速；默认开启 | `XpilotSpeedCard` | 无发送 |
| `lead_card` | 大屏磁贴：前车距离和相对速度（radarState.leadOne）；默认开启 | `XpilotLeadCard` | 无发送 |
| `speed_limit_card` | 大屏磁贴：SP 解析出的限速（longitudinalPlanSP）；默认开启 | `XpilotSpeedLimitCard` | 无发送 |
| `car_tile` | 大屏磁贴：仪表车速、挡位、转向灯、盲区；默认开启 | `XpilotCarTile` | 无发送 |
| `map_tile` | 大屏磁贴：限速、路名、下一个转弯（liveMapDataSP、navInstruction，任何地图或导航来源）；默认开启 | `XpilotMapTile` | 无发送 |
| `blindspot_edges` | 大屏：盲区有车时画面左/右侧显示红色渐变边框（ScreenOverlay）；默认开启 | `XpilotBlindspotEdges` | 无发送 |
| `clock_tile` | 大屏磁贴：本地时间和日期（设备时区）；默认开启 | `XpilotClockTile` | 无发送 |
| `ip_tile` | 大屏磁贴：设备 IP（默认路由的源地址）和网络类型；默认开启 | `XpilotIpTile` | 无发送 |
| `bms` | 电池：card 从 vehicle bus 解 0x132（电压、电流）和 0x292（SOC），写到 `carStateSP.teslaBattery`；Battery 磁贴显示电量、电压、电流、功率。信号定义来自社区 Model 3/Y DBC，还没在车上核对；默认关闭（需要 vehicle bus 线束） | `XpilotBms` | 无发送 |

## 11. 本机可以跑的检查

```
python3 tools/sp_tesla_e2e/static_imports.py --baseline <基线 json>   # 有没有断掉的 import
python3 tools/sp_tesla_e2e/tile_layout_check.py                       # 大屏磁贴：网格、排布、行驶避让、编辑操作、手势、重画判断、ASCII 文字
python3 tools/sp_tesla_e2e/plugin_host_check.py                       # 插件宿主：出错隔离、总开关、元数据、参数、目标车速、雷达/地图/外接 provider
python3 tools/sp_tesla_e2e/external_bridge_check.py                   # 外接算力 TCP 桥接（本机真实 socket）
python3 tools/sp_tesla_e2e/manifest_check.py                          # 插件清单、资源声明、冲突裁决
python3 tools/sp_tesla_e2e/phase2_check.py                            # 插件报警、变道策略、横向修正
python3 tools/sp_tesla_e2e/phase3_check.py                            # 可替换的横向控制器和纵向规划
python3 tools/sp_tesla_e2e/store_check.py                             # 插件商店：下载、校验、安装、参数（本机 HTTP 服务）
python3 tools/sp_tesla_e2e/offroad_pages_check.py                     # 大屏停车页面：页面模块、参数名、插件行、商店行、视口、触摸映射
python3 tools/sp_tesla_e2e/store_e2e.py --repo ~/xpilot-plugins       # 插件仓库端到端：索引 → 安装 → 发现 → 钩子生效
python3 tools/dev_sp_release/upstream_watch.py                        # 列出值得 cherry-pick 的上游提交
```

编译、safety 测试、UI 渲染和上车验证只能在 Mac 或设备上做。

## 授权说明（给用户）

要让 AI 修改 panda safety 核心文件，在仓库的 `.claude/settings.json`（或 `~/.claude/settings.json`）里加：

```json
{ "permissions": { "allow": ["Edit(opendbc_repo/opendbc/safety/**)", "Write(opendbc_repo/opendbc/safety/**)"] } }
```

加完后重启会话。safety 的改动必须先编译并跑测试，再上车。
