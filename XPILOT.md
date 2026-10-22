# xpilot：规则与开发说明

所有人和所有 AI 动手改代码前必须先读这份文档。`AGENTS.md`（Codex 等）和 `CLAUDE.md`（Claude）都指向这里。

## 1. 项目是什么

- **定位**：sunnypilot（下称 SP）只适配 Tesla 的精简版，分支名 `xpilot`。
- **基线**：sunnypilot `922513f`，opendbc `5be750714`。只做这一次基准，之后不再整体合并上游，只手工挑修复（`tools/dev_sp_release/upstream_watch.py`）。
- **主体**：横向、纵向、模型都是 SP 原版，Tesla 车端代码是上游原版。
- **扩展**：xpilot 的功能全部以插件形式接入，不改 SP 主体逻辑。
- **已删除**：其他车型、comma 云、sunnylink、旧的大屏 UI、扭矩车用的横向控制、翻译（UI 只用英文）。
- **硬件**：C3、C3X、C3XL、C4。大屏设备上 mici UI 显示在一个窗口里，四周是插槽。

## 2. 硬规则

1. **不改 SP 主体逻辑。** SP 文件里最多只能加一行插件调用。功能逻辑全部写在 `openpilot/tesla/plugins/<功能名>/`。
2. **不改上游 Tesla 车端代码。** `opendbc_repo/opendbc/car/tesla/*`、`opendbc_repo/opendbc/sunnypilot/car/tesla/*`、`opendbc/dbc/tesla_model3_*.dbc`、`opendbc/safety/modes/tesla.h` 保持上游原样。需要车端数据，就在插件里用自己的 `CANParser` 读。
3. **插件只能收紧，不能放松。** 纵向只能更慢或停车，不能绕过 SP 和 panda 的任何检查。
4. **每个 CAN 发送地址都必须有 panda safety 插件**（`opendbc/safety/plugins/`），在插件里自己校验内容、频率、时效和 `controls_allowed`。没有 safety 插件，panda 会直接拦掉。
5. **插件出错不能拖垮进程**：输入过期就当周期什么都不发；异常要捕获。UI 插槽连续出错 3 次会被自动停用。
6. **Params**：新 key 先在 `openpilot/common/params_keys.h` 声明。新功能默认关闭。设置项写进 `openpilot/tesla/ui/settings_meta.py`。
7. **cereal**：只追加字段，不改已有字段的序号和类型。新消息用 `custom.capnp` 里的 `customReserved*` 槽位。
8. **验证**（沿用 `AGENTS.md`）：
   - 先列出失败模式，再写检查。
   - 优先做可重复的端到端检查。
   - 不准把静态检查说成编译、safety 测试或上车已通过。
   - 本地 commit 和设备上实际运行的 commit 分开报告。
9. **提交**：在 `xpilot` 分支上，一个连贯改动一个提交，只包含这次改动的文件。只有在用户要求时才推送。
10. **按插件拆分**：加功能就是加插件目录，删功能就是删目录、再从注册表里去掉那一行。

## 3. 目录

```
openpilot/tesla/
  plugin.py                 Python 插件接口（Plugin 基类，所有钩子都有默认空实现）
  plugins/__init__.py       插件注册表 PLUGINS，以及 card/plannerd/manager 用的调用宿主
  plugins/auto_speed/       自动设定速度
  plugins/traffic_light/    红绿灯停车
  plugins/ambient_light/    盲区氛围灯
  ui/screen.py ui/grid.py ui/slot.py ui/slots/   大屏宿主、插槽格式、插槽
  ui/settings_page.py ui/settings_meta.py        Tesla 设置页
opendbc_repo/opendbc/safety/plugins/
  plugin.h registry.h auto_speed.h ambient_light.h   panda safety 插件（见第 6 节，目前未接入）
```

## 4. Python 插件接口（`openpilot/tesla/plugin.py`）

| 钩子 | 调用方 / 时机 | 用途 |
|---|---|---|
| `__init__(CP, params)` | card，识别车型后调用一次 | 创建 CANParser，读取参数 |
| `setup(CP_SP)` | card，发布 CarParamsSP 之前 | 设置 flags；需要 panda 插件时置 `safetyParam` 位 |
| `observe_can(can_list, now_ns)` | card，每批 CAN | 只读解析；返回需要立即发送的帧（少用） |
| `publish_state(CS_SP)` | card，每个周期 | 填写 carStateSP 里本插件的字段；也可以从这里读 `CS_SP.speedLimit` |
| `control_sends(CS, CC, now_ns)` | card，每个控制周期 | 返回要追加发送的 `CanData` |
| `service_params(params)` | card，约 10 Hz | 重新读取实时设置 |
| `processes()`（类方法） | manager | 额外进程。manager 相关的 import 写在方法内部 |
| `plan_filter(CP, params)`（类方法） | plannerd | 返回带 `publisher(pm, sm)` 的对象，用来收紧纵向计划；不需要就返回 None |
| `PLAN_SERVICES` | plannerd | `plan_filter` 需要额外订阅的服务 |

SP 里的调用位置：`selfdrive/car/card.py`（`CarPlugins`）、`selfdrive/controls/plannerd.py`（`plan_services`、`plan_filters`、`plan_sink`）、`sunnypilot/system/fork_processes.py`（`processes`）。

## 5. 写一个新插件

1. 新建 `openpilot/tesla/plugins/<名字>/__init__.py`（空文件）和 `plugin.py`：

```python
from openpilot.tesla.plugin import Plugin

class MyFeature(Plugin):
  NAME = "my_feature"

  def __init__(self, CP, params):
    super().__init__(CP, params)
    self.enabled = params.get_bool("TeslaMyFeature")

  def control_sends(self, CS, CC, now_ns):
    return []   # 有 CAN 发送时，必须同时提供 panda safety 插件
```

2. 在 `plugins/__init__.py` 的 `PLUGINS` 里加上这个类。
3. 在 `params_keys.h` 声明参数（默认关闭），在 `settings_meta.py` 里加设置项。
4. 有 CAN 发送的：写 `opendbc/safety/plugins/<名字>.h` 并加进 `registry.h`。`safetyParam` 位要和 Python 侧一致（auto_speed 用的是 `0x4000`）。
5. 有 UI 的：插槽放在 `openpilot/tesla/ui/slots/`，格式见 `ui/grid.py`。
6. 先写失败模式和检查，再写实现；能在本机跑的就跑。

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

**当前状态：未接入。** 需要在 `safety.h` 里加 4 处调用：
1. include `opendbc/safety/plugins/registry.h`；
2. `safety_rx_hook` 里，`valid` 为真时调用 `safety_plugins_rx(msg)`；
3. `safety_tx_hook` 里，属于插件的报文交给 `plugin->tx(msg)` 校验；
4. `set_safety_hooks` 里调用 `safety_plugins_reset()`。

这次修改被 Claude Code 的权限分类器判定为"削弱安全"而拦下，需要用户在 `.claude/settings.json` 里授权（见本文末尾）。在接入之前，自动设定速度（0x3C2）和氛围灯（0x679）的发送会被 panda 拦掉。接入之后必须在 Mac 或设备上编译 panda 和 libsafety，并补上插件的 safety 测试。

## 7. 雷达接入接口

`opendbc_repo/opendbc/car/car_helpers.py` 里有 `RADAR_PLUGINS = {"tesla": "module:Class"}`，填上即可用一个 `RadarInterfaceBase` 子类替换车型自带的雷达，card 通过 `get_radar_interface()` 获取。目前为空，Tesla 用原车雷达。外接雷达如果需要发送报文，还要配一个 panda safety 插件。

## 8. 地图接口

- **数据**：任何数据源只发布 `liveMapDataSP`，包括限速、前方限速、路名、`targetVelocities`（弯道目标速度）、`source`。
- **选择**：用 `MapProvider` 参数选数据源，默认 `osm`；设置页有开关。
- **新增数据源**：继承 `sunnypilot/mapd/live_map_data/base_map_data.py`，并在 `process_config.py` 里按 `MapProvider` 的取值注册进程。
- **导航**：发布 `navInstruction`，再把 256×256 地图图像发到 VisionIPC 的 `mapsd` 流。

## 9. UI 插槽（大屏）

- **加插槽**：在 `openpilot/tesla/ui/slots/` 新建文件，继承 `Slot` 并写好 `SPEC = SlotSpec(id, title, cells, services, show, hz, order)`，会被自动发现，在 12×6 网格中自动排布。
- **只显示**：插槽不接收触摸。
- **视频窗口**：在窗口外按住 1 秒进入编辑，可拖动和缩放；位置保存在 `TeslaVideoWindow`。

## 10. 现有插件

| 插件 | 功能 | 参数 | panda |
|---|---|---|---|
| `auto_speed` | 按车辆限速（DAS_fusedSpeedLimit）加偏移，用右滚轮单格报文调整巡航设定速度；手动拨滚轮后暂停，反方向拨两下恢复 | `TeslaAutoSpeedLimit`、`TeslaAutoSpeedLimitOffset` | `auto_speed.h`（0x3C2，需要 vehicle bus 和 openpilot 纵向） |
| `traffic_light` | 读取 Tesla 自身的红绿灯感知（APP_trafficControl），由 trafficcontrold 和计划仲裁器在红灯前停车（只收紧） | `TeslaTrafficSignalControlEnabled`、`TeslaTrafficStopReference`、`TeslaTrafficControlMaxSpeed` | 无发送 |
| `ambient_light` | 盲区有车时把氛围灯点成红色；区分昼夜亮度 | `TeslaBlindspotAmbient*` | `ambient_light.h`（0x679） |

## 11. 本机可以跑的检查

```
python3 tools/sp_tesla_e2e/static_imports.py --baseline <基线 json>   # 有没有断掉的 import
python3 tools/sp_tesla_e2e/slot_layout_check.py                       # 插槽排布
python3 tools/dev_sp_release/upstream_watch.py                        # 列出值得 cherry-pick 的上游提交
```

编译、safety 测试、UI 渲染和上车验证只能在 Mac 或设备上做。

## 授权说明（给用户）

要让 AI 修改 panda safety 核心文件，在仓库的 `.claude/settings.json`（或 `~/.claude/settings.json`）里加：

```json
{ "permissions": { "allow": ["Edit(opendbc_repo/opendbc/safety/**)", "Write(opendbc_repo/opendbc/safety/**)"] } }
```

加完后重启会话。safety 的改动必须先编译并跑测试，再上车。
