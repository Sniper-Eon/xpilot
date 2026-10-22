# C3XL 安装及大屏 UI 调整记录 — 2026-10-22

## 停止点与版本身份

用户要求停止继续改动代码、保留已经完成的修改，并推送相关修改。本记录只增加文档和已有验收结果，不继续修复代码。

- 来源：`onemiless/openpilot`，`xpilot`，初始远程 SHA `8b8bc63f414c9777b2f1567c56bf8c875113ea1f`。
- 当前代码提交：`3d03575f90802e457db07bb99ba36c002e19c1b8`。设备当前也运行该提交；本记录的文档提交会在其后，不代表设备又更新了一次。
- 设备：用户指定的 `172.16.1.202` C3XL，AGNOS 19.7，`/data/hardware_profile=c3xl`。
- `/data/openpilot -> /data/xpilot-install-20261022/candidate`。
- Panda 应用固件：`DEV-443dd964-DEBUG`，H7；新分支读回签名匹配，真实 SPI 发现通过。
- 用户已明确确认设备停稳、未参与驾驶控制、可独占操作，并允许清空数据；实际未清空数据。
- 停止修改时只读确认：`comma.service` active，manager、UI、Python pandad 和原生 pandad 均存在。

## 保留的五个代码提交

| 提交 | 原因与已完成改动 |
|---|---|
| `54280a6148cd5204a79a921246964e97ea16143c` | 删除引用已移除 legacy MPC 目录的 SConscript 残留行，使构建能够继续。 |
| `443dd964e03fbcdb07a8944023e5c5ac45a045a6` | F4 的调试 HardFault_Handler 与公共处理函数重复定义；删除 F4 重复调试实现，保留公共 cookie 和复位逻辑。 |
| `73c29355a852b3e22d08bacabb90ee8cfc22f426` | 大屏宿主先于字体初始化创建告警组件，UI KeyError 退出；改成窗口、字体初始化后实例化宿主。 |
| `8345c275e6b3102af0c27266822afa1e866f9848` | 将中心从 536×240 放大到 1608×720；停车时侧边分类导航直达 mici 具体页面；停车时不渲染行车告警，保留行驶时告警；增加真实 GPU/触摸 E2E。 |
| `3d03575f90802e457db07bb99ba36c002e19c1b8` | 去掉侧边分类首页的冗余 Back 卡片，避免中间第一屏只显示巨大返回按钮；保留子页面返回；分类标签统一首字母大写。 |

没有修改 Tesla 车辆控制或 safety 核心规则，没有通过修改 Params 绕过硬件支持或安全检查。原本的窗口拖动/缩放入口已被固定居中布局取代，旧 TeslaVideoWindow 参数不再决定宿主尺寸。

## 安装过程中遇到的问题

| 编号 | 实际现象 | 处理和结果 |
|---|---|---|
| 1 | 主工作区在 dev-sp-egpu，存在大量其它任务的未提交内容，根目录无 AGENTS.md。 | 保存 HEAD、状态和 binary diff；遵守本轮用户规则。未切换、清理或覆盖主工作区；独立克隆 xpilot，在其已有分支工作。 |
| 2 | 默认沙箱下 DNS 失败、Git/SSH Operation not permitted。 | 使用审批后的网络执行权限，SSH 恢复。 |
| 3 | origin=mmoo758/openpilot 的 HTTPS 连接约 75 秒超时。 | 经 SSH 443 确认 onemiless/openpilot 有 xpilot，且设备原仓库也是此来源；使用它拉取。 |
| 4 | 原仓库部分克隆读取对象时尝试访问不可达的 sunnypilot 历史来源。 | 改用独立浅克隆；避免依赖原仓库不完整的 promisor 对象。 |
| 5 | 完整历史 bundle 因 promisor 缺少 f698277… 对象失败。 | 改用成功完成的独立浅克隆；未用失败包安装。 |
| 6 | 第一份源码 archive 触发 LFS smudge，尝试写入受保护 .git 被拒绝。 | 废弃失败归档；GIT_LFS_SKIP_SMUDGE=1 重新导出，上传后核对 SHA-256。 |
| 7 | 浅 bundle 导入设备报 Failed to traverse parents，缺少 shallow 边界。 | 改为传输成功浅克隆的 .git 元数据；后续小提交用 incremental bundle 同步。 |
| 8 | 设备 IsOnroad 文件不存在，IsOffroad=1。 | 另获用户明确停车独占确认；未将缺少参数等同于控制状态已被证明。 |
| 9 | tinygrad 目标版本不同，原始 HTTPS 下载持续慢速。 | 按分支 gitlink 获取 92b742f…；确认原 fetch 存活时不删锁，后来终止此次 fetch/index-pack，经临时代理重新拉取成功。 |
| 10 | tinygrad 并行重试遇 shallow.lock。 | 确认原进程仍在工作；未删除活动锁。 |
| 11 | 设备直连 Hugging Face 报 Network is unreachable。 | 使用本机已经启用的 127.0.0.1:7897 代理，经 SSH 反向转发完成下载；不修改设备全局网络。 |
| 12 | 候选目录模型与二进制最初仍是 LFS 指针。 | 复用旧目录/缓存中大小和 SHA-256 均匹配的文件，其余用标准 LFS batch 接口下载；日志记录 286 次 VERIFIED，包含子模块文件。 |
| 13 | LFS 临时文件替换使 updater 权限从 100755 变成 100644。 | 按 Git 记录恢复可执行权限。 |
| 14 | git lfs install 遇已有 pre-push hook。 | 用 --skip-repo 注册过滤器，保留原 hook。 |
| 15 | git status 列出大量 LFS 状态标记以及未跟踪 prebuilt。 | 安装阶段额外执行 git diff 和 cached diff，均退出 0、内容为空；不将状态标记误称为额外源码变更。之后 UI 改动均有独立提交。 |
| 16 | 第一轮 SCons 引用不存在的 tesla/long/legacy_mpc/SConscript 而停止。 | 全分支搜索后删除唯一残留引用，提交 54280a6。 |
| 17 | 第二轮 SCons 的 F4 bootstub 编译遇 HardFault_Handler 重复定义。 | 保留公共故障复位处理，删除重复 F4 调试处理，提交 443dd96；第三轮全量原生构建通过。 |
| 18 | git am 得到内容相同、committer 时间不同的设备 SHA。 | incremental bundle 同步本地原提交身份，避免仅凭补丁相同声称提交一致。 |
| 19 | 设备没有 pytest。 | 使用已有 unittest 入口；Tesla safety 共 381 项，OK，43 skipped，27.835 秒。未补写单元测试。 |
| 20 | 新库 SPI 发现为空，标准 reset 后仍为空，USB 也没有 Panda。 | 保存两次失败 JSON；旧库同机可枚举，比较 spi.py 后发现新旧 SPI 协议不兼容，不能判成硬件缺失。 |
| 21 | 新 SPI 协议要求匹配固件。 | 用旧库写入已编译 H7 应用固件，不用旧库重连；再用新库验证 DEV-443dd964-DEBUG、签名匹配、faults=0、controls_allowed=false，SPI 发现 E2E passed=true。 |
| 22 | 重启后首次 SSH 超时。 | 等待网络启动后恢复，核对真实路径、HEAD 和进程。 |
| 23 | 在线模型目录 raw.githubusercontent.com DNS/连接失败，使用缓存。 | 保留现状和日志，没有修改全局网络；网络刷新能力仍未解决。 |
| 24 | 第一次启动验收 UI exitCode=1，其它消息正常。 | 直接运行生产 UI 复现 FontWeight.BOLD KeyError；修复宿主/字体初始化顺序，提交 73c2935。 |
| 25 | 启动有旧 Cursor/Windsurf 符号链接已存在、fts_ts IRQ 未找到、raylib 色彩校正失败及部分字体 glyph 缺失提示。 | 记录，不扩展为额外系统修改。UI 渲染心跳通过，但并不证明这些提示已消除。 |
| 26 | pandad 先尝试 USB 失败，再成功走 SPI。 | 确认设备实际用 SPI；保留原发现流程，不把初次 USB 尝试失败误报成 Panda 最终连接失败。 |

## 用户报告的大屏问题与这轮结果

1. **顶部一直闪烁。** 代码中顶部 AlertRenderer 在停车时也无条件运行，会读取已经停止发布的行车状态。修改前真实 GPU E2E 在停车前 19 帧观测到 19 次行车告警绘制调用；改动后同场景为 0。行驶分支保留，并用本地 UI 注入告警生成 GPU 截图。**这证明停车误绘制路径被移除，不等同于用户已现场确认一切闪烁消失。**
2. **中间太小。** 修改前中心 `(812,420,536,240)`，修改后 `(276,180,1608,720)`；中心宽高均为原来的三倍，面积约占全屏一半。
3. **设置导航太麻烦。** 左侧 Home/Toggles/Models/Plugins/Tesla，右侧 Network/Device/Software/Developer。复用原 mici 设置内容和回调，从侧边直接进入具体页面，分类切换先退出旧页面，不累积导航栈；分类首页冗余 Back 卡片移除，子页面返回保留。
4. **初版调整仍有巨大的 Back 卡片。** E2E 截图中发现，随后完成 3d03575 的小修正；用户要求停止后不再修改它。
5. **设备原生截图受面板旋转影响。** 原截图为 1080×2160，不适合直接判定逻辑布局。E2E 使用真实 GPU 绘制、生产窗口纹理和宿主，在 2160×1080 离屏目标合成并保存 PNG。该截图是 GPU 合成证据，不是相机拍摄的实体屏幕。
6. **截图出现 unsupported hardware 提示。** hardwared.py 仍有 tici 和分支频道组合限制，xpilot 不在现有 dev-sp 例外中；本次没有绕过或修改该限制。它是仍需独立处理的问题，不能将本次安装或 UI 验收解释为已经允许上路控制。
7. **自动化触摸范围。** 验证了映射坐标的 press/release 和九个顶层入口；不是人手触摸验收，没有点击改变设置值、连接网络或切换插件。没有穷举全部子页面。

## 验证证据与边界

- `ui-before.json`：旧 UI 验收失败，列出小窗口、停车行车告警误绘制、缺少侧菜单。
- `ui-after.json`：3d03575，真实 GPU 和生产组件 E2E passed=true，九个入口均进入相应页面，停车 banner_calls=0，行驶告警绘制保留。
- `install-runtime.json`：73c2935 时的安装验收；15 秒、150 条 tres Panda 样本，faultStatus=none、controlsAllowed=false；deviceState/pandaStates/managerState/peripheralState/uiDebug 全部 alive/valid。**这是前一阶段证据，不冒充 3d03575 的重复采样。**
- 3d03575 停止修改时只读检查：服务 active，manager/UI/pandad 存在；没有在停止要求后再改源码或做新一轮行车验收。
- 其它已完成检查：七项插件检查、原生 session_acceptance、Tesla safety、完整原生 SCons、固件签名和真实 SPI 发现。
- 原生模型、摄像头 onroad、车辆闭环控制、实车道路验证均未做。本次 UI 注入的行车告警不是实际驾驶验证。

完整过程日志和截图在执行主机 `/Users/mile/Desktop/mo-op/artifacts/xpilot-install-20261022/`，设备记录在 `/data/xpilot-install-20261022/`。仓库只保存问题记录、关键 JSON 和可重复 E2E，不上传大体积源码归档、模型、参数快照或全部设备日志。

## 复验入口（后续需要时，由操作者停车停服后执行）

```bash
cd /data/openpilot
export PATH=/usr/local/venv/bin:$PATH
export PYTHONPATH=$PWD:$PWD/opendbc_repo:$PWD/msgq_repo:$PWD/tinygrad_repo:$PWD/rednose_repo
python3 tools/sp_tesla_e2e/big_screen_e2e.py --output /data/xpilot-ui-check
```

它会打开真实 GPU 窗口、注入本进程的触摸事件、保存 PNG 和 result.json，失败时断言退出。运行期间不可再有其它 UI 占用 GPU；测试退出后需要恢复正常服务。

## 回滚边界

原源码 `/data/sp-sync-experiment-20261017/candidate` 保留；原启动入口和参数快照在设备安装记录目录。由于已经更换 Panda SPI 应用协议，恢复旧源码还需要匹配旧固件，不能只切换软链接。用户要求停止后没有执行回滚或清理。
