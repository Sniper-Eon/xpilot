# xpilot 扩展接口说明

xpilot = sunnypilot（基线 `922513f`）+ 只适配 Tesla。横向、纵向主体用 SP 原版；Tesla 相关功能都是扩展，代码在 `openpilot/tesla/` 下：

```
openpilot/tesla/
  car/      车辆收发扩展：card 适配器、控制权交接、BMS、氛围灯、SCC-V
  long/     纵向扩展：规划后端（Experimental、TN）、legacy MPC、DEC、调参
  traffic/  红绿灯控制：观测进程和最终计划仲裁
  ui/       大屏宿主、插槽、Tesla 设置页
```

通用规则：
- SP 主体文件里只放一行调用，逻辑写在本目录。
- 扩展只能收紧 SP 的约束（少加速、早减速）。唯一例外是纵向后端：由用户自己选，并且一次行程内锁定。
- 输入过期或出异常时，当周期回到 SP 原路径，不能让进程崩溃。
- 新增 Params key 要在 `openpilot/common/params_keys.h` 里声明，否则读写时会报错。

---

## 1. UI 插槽（大屏 C3/C3X/C3XL）

屏幕按 12×6 的网格切，每格 180 px。插槽自动排在视频窗口周围，C4 上没有插槽。

**怎么加一个插槽**：在 `openpilot/tesla/ui/slots/` 新建一个 `.py` 文件即可，不需要在别处注册。

```python
from openpilot.tesla.ui.grid import SlotSpec
from openpilot.tesla.ui.slot import Slot

class SpeedSlot(Slot):
  SPEC = SlotSpec(
    id="speed",            # 唯一
    title="Speed",
    cells=(2, 1),          # 占几格：(列, 行)
    services=(),           # update() 要读的 cereal 服务；为空表示读 ui_state.sm
    show="always",         # 可选 "always" / "onroad" / "offroad"
    hz=5,                  # 最高重绘频率，其余帧复用缓存
    order=100,             # 排布优先级，数字小的先放
  )

  def update(self, sm):    # 取数据，不要在这里画
    self.v = sm['carState'].vEgo

  def _render(self, rect): # 画图；坐标从插槽自己的左上角 (0, 0) 开始
    self.draw_lines(rect, [f"{self.v * 3.6:.0f} km/h"])
```

**规则**：
- 读到的每个服务都要写进 `services`。如果什么都不写，拿到的 `sm` 是 `ui_state.sm`。
- 插槽只负责显示，不接收触摸。
- 插槽连续出错 3 次会被停用并记日志，不会影响 UI。
- 网格放不下的插槽会被隐藏，按 `order` 决定谁先放。

**现成的例子**：`slots/car.py`（读 carState）、`slots/map.py`（读地图接口）、`slots/bms.py`（自己订阅 `can`）。

**视频窗口**：在窗口外按住 1 秒进入编辑；拖窗口可以移动，拖右下角可以缩放；点窗口外保存。位置存在 Params `TeslaVideoWindow`，格式是 `{"x", "y", "scale"}`。

**检查排布**：`python3 tools/sp_tesla_e2e/slot_layout_check.py`，不需要 pyray，在 PC 上就能跑。

---

## 2. 地图接口

所有地图数据都通过一条消息 `liveMapDataSP` 传递，字段定义在 `cereal/custom.capnp`：

| 字段 | 含义 |
|---|---|
| `speedLimitValid` / `speedLimit` | 当前限速（m/s） |
| `speedLimitAheadValid` / `speedLimitAhead` / `speedLimitAheadDistance` | 前方限速，以及到那里的距离（m） |
| `roadName` | 路名 |
| `targetVelocities[]` | 前方弯道目标速度，每项是 `{latitude, longitude, velocity(m/s)}` |
| `source` | 数据来源名，例如 `"osm"` |

**谁在用**：SLA（限速辅助）、SCC-M（弯道减速）、UI 的地图插槽。只要停止发布，SCC-M 就不再使用这些数据。

**接一个新的数据源**（手机、其他设备、别的地图）：
1. 继承 `openpilot/sunnypilot/mapd/live_map_data/base_map_data.py` 里的 `BaseMapData`。设置 `SOURCE = "xxx"`，实现限速、路名接口，按需实现 `get_target_velocities()`。也可以不继承，直接发布这条消息。
2. 在 `system/manager/process_config.py` 里加一个进程，条件写 `params.get("MapProvider") == "xxx"`。
3. 同一时间只有一个数据源：Params `MapProvider` 默认是 `osm`，设置页里有 "OSM Map Data" 开关。

**导航**：发布官方消息 `navInstruction`，再把 256×256 的灰度地图图像发到 VisionIPC 的 `mapsd` / `VISION_STREAM_MAP`，mici 的导航面板就会显示。目前还没有导航数据源。

---

## 3. 纵向后端（替换整个纵向规划）

后端注册在 `long/registry.py`：

```python
MY_BACKEND = BackendSpec(
  id=BackendId.MY,                 # 先在 BackendId 枚举里加一项
  slug="my", label="My",
  provider="openpilot.tesla.long.my.planner:LongitudinalPlanner",
  capabilities=frozenset({...}),
  stopping_policy="openpilot.tesla.long.my.policy:MyStoppingPolicy",  # 可选
)
# 再把它加进 BACKENDS
```

- **provider 类**：接口和 SP 的 `LongitudinalPlanner` 一致，构造参数是 `(CP, CP_SP)`，需要有 `update(sm)`、`publish(sm, pm)` 和属性 `sla`。
- **stopping_policy 类**：需要实现 `update_state(stopping: bool)` 和 `stopping_decel_rate(CS, a_target, last_output_accel) -> float`，作用是改写停车时的减速斜率。
- **怎么选**：Params `LongitudinalPlannerMode` 填 BackendId 的数值，上路时锁定，一次行程内不变。只有 Tesla 车会用到，其他情况一律走 Official。
- **调用位置**：`plannerd.py` 里的 `create_longitudinal_planner(...)`，`controlsd.py` 里的 `create_long_control(...)`。

---

## 4. 最终计划仲裁（红绿灯停车）

`traffic/final_plan_arbitrator.py`：在 plannerd 发布计划之前，对 `longitudinalPlan` 做最后一次修正。只能让车减速或停车；红绿灯功能（Params `TeslaTrafficSignalControlEnabled`）关闭时，走原来的发布路径。

目前它是红绿灯专用的，还不是通用的"约束接口"。如果有新功能也要限制纵向（比如前方盲区刹车），需要先在这里抽出一个通用约束入口。

---

## 5. 车辆收发扩展（card）

`car/card_adapter.py` 里的 `TeslaCardAdapter`，card 在每个周期调用它：

| 方法 | 时机 | 用途 |
|---|---|---|
| `observe_can(can_list)` | 收到 CAN 后 | 解析附加报文，返回需要立即发送的帧 |
| `publish_state(CS_SP)` | 生成 carStateSP 时 | 往 `carStateSP` 里填 Tesla 状态 |
| `update_context()` | 每个周期 | 把规划和控制的上下文传给 opendbc 里的 Tesla 状态机 |
| `control_sends(CS, CC, now)` | 发送控制指令时 | 追加附件报文（氛围灯、自动限速滚轮） |
| `service_params(params)` | 低频 | 读取参数 |

所有新增的 CAN 发送报文都必须在 `opendbc_repo/opendbc/safety/modes/tesla.h` 的白名单里，并配好 safety 测试，否则 panda 会拦掉。

`car/control_runtime.py` 里的 `TeslaControlRuntime` 由 selfdrived 调用，负责在控制权交接期间过滤原车巡航事件。

---

## 6. 只读 CAN 感知（推荐新功能用这种方式）

写一个独立进程，订阅 `can`，用 `opendbc.can.CANParser` 和 `opendbc/dbc/` 里的 Tesla DBC 解析需要的报文，再发布自己的消息。不需要改 card，也不碰 safety。

进程在 `openpilot/sunnypilot/system/fork_processes.py` 里注册：

```python
PythonProcess("myperceptiond", "openpilot.tesla.xxx.myperceptiond", only_onroad)
```

---

## 7. 设置项

Tesla 设置页是 `ui/settings_page.py`，元数据在 `ui/settings_meta.py`：

- `LABELS` / `TITLES`：显示名称
- `BOOL_KEYS`：开关
- `RANGES`：数值，格式是 `(最小, 最大, 步长, 单位, 除数)`
- `CHOICES`：枚举

加一个设置的步骤：在 `params_keys.h` 里声明 key，在上面对应的表里加一行。设置页按这些表自动生成控件。

---

## 尚未提供 / 限制

- **横向目标接口**（让外部数据源提供目标曲率）还没做。不要直接用 `lateralManeuverPlan` 代替：controlsd 只检查 valid，不检查数据是否过期，发布方一挂就会一直沿用最后一帧曲率。
- **opendbc 里的 Tesla 改动**仍然是原地修改，还没有拆成扩展钩子。改 safety 前必须在 Mac 或设备上编译 libsafety 并跑 safety 测试。
- **外挂算力**：有线方案用上游已经支持的 chestnut（USB 外接 GPU，由 modeld 自动使用）；网络外挂盒子还没做网关。

## 本机可跑的检查

```
python3 tools/sp_tesla_e2e/static_imports.py --baseline <基线 json>   # 删改代码后检查有没有断掉的 import
python3 tools/sp_tesla_e2e/slot_layout_check.py                       # 插槽排布
python3 tools/dev_sp_release/upstream_watch.py                        # 列出值得 cherry-pick 的上游提交
```
