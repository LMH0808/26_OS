# 基础资源管理与竞争/死锁案例验证

> 负责人：卞苏阳。对应《项目说明》4.2、5.1、5.2、7.4、9、10、13.2、13.3、17。
> 本文只写**案例与验证记录**；银行家安全性检查、资源分配图与回滚策略的说明由韩臻浩核对，不在本文展开。
> 文中所有数字均为 `run_demo.py` 实际输出，命令附在每节，可直接复现。

---

## 1 交付件

| 文件 | 类型 | 说明 |
|---|---|---|
| `tea_break_scheduler/resources.py` | 修改 | 仅**追加** `holders()`、`held_by()`、`audit()` 三个只读方法，未改动 `try_acquire()` / `release()` 任何一行 |
| `data/demos/acquire_release.json` | 新增 | 正常申请释放，两任务并发持有不同资源 |
| `data/demos/conflict.json` | 新增 | 资源冲突：申请被拒 → 等待 → 释放后获准 |
| `data/demos/stage_release.json` | 新增 | 跨阶段保留占用（收集后不释放台面） |
| `data/demos/queue_wait.json` | 新增 | 普通等待：四人排队，死锁 0 |
| `data/demos/deadlock_unresolved.json` | 新增 | 死锁形成且不解除，到 H 正常导出 |
| `data/demos/deadlock_recover.json` | 新增 | 同一输入，回滚解除死锁 |
| `data/demos/avoid.json` | 新增 | 同一输入，安全性检查提前拒绝，环未形成 |
| `data/demos/fault_hold.json` | 新增 | 故障期间保留占用 |
| `tests/test_resources.py` | 新增 | 16 项：申请/释放/故障/查询/自检/场景账目/对照一致性 |
| `data/demos/README.md` | 新增 | 场景清单与字段模板（13.3「统一模板」） |

`data/demos/basic.json`、`deadlock.json`、`baseline.json` 由韩臻浩提供，本文引用但不修改。

---

## 2 13.3 六项交付对照

| # | 要求 | 对应文件 | 实测结论 | 状态 |
|---|---|---|---|---|
| 1 | 正常申请释放 | `acquire_release.json` | N1 与 N2 并发持有不同资源，均在 t=4 完成，冲突 0 | 完成 |
| 2 | 资源冲突 | `conflict.json` | C2 于 t=1 被拒，t=3 获准，t=5 完成；冲突 1 | 完成 |
| 3 | 普通等待 | `queue_wait.json` | Q1→Q4 依次完成，冲突 3，死锁 **0** | 完成 |
| 4 | 死锁形成 | `deadlock_unresolved.json` | 环形成，死锁 1，到 H=40 正常退出，退出码 0 | 完成 |
| 5 | 死锁解除 | `deadlock_recover.json` | 同一输入，回滚 B，死锁 1 → 解除，A@3 B@5 | 完成 |
| 6 | 目标环境运行记录 | `docs/run_ubuntu22.md` | 模板已在仓库中，本机为 Ubuntu 24.04 容器，**不能代替 22.04 现场** | **未完成** |

每项材料均按「配置、操作步骤、结果」三节记录，见本文第 6 节。

---

## 3 7.4 四项专项验证

### 3.1 三组受控对照：同一输入，只翻两个开关

`deadlock_unresolved.json`、`deadlock_recover.json`、`avoid.json` 的 `tasks` 与 `resources` **逐字节相同**，
`max_time` 同为 40，仅 `banker_enabled` / `deadlock_recovery` 不同。`tests/test_resources.py` 里有测试固定这一约束，
防止以后改了一个忘了另一个。

| 对照组 | banker | recovery | 死锁次数 | 安全拒绝 | 回滚 | 结局 |
|---|---|---|---|---|---|---|
| `deadlock_unresolved` 无保护 | 关 | 关 | **1** | 0 | 0 | A、B 均未完成，`max_time` 停止 |
| `deadlock_recover` 检测后破解 | 关 | 开 | **1** | 0 | **1** | A@3、B@5 全部完成 |
| `avoid` 提前避免 | **开** | 关 | **0** | **1** | 0 | A@2、B@4 全部完成 |

`avoid` 的轨迹显示拒绝发生在申请当场：

```
t=0  start: A
t=0  资源等待: B Banker safety check rejected request
t=1  stage_complete: A
t=2  任务完成: A
t=2  start: B
```

B 的危险申请被拒时**尚未获得回收区**，因此环从未形成——这正是 7.1「检查通过后提交分配，否则撤销试分配并置为等待」的效果，
也说明 7.4「提前避免」与「检测后破解」是两条不同路径，不能用一个场景代替另一个。

### 3.2 与引擎内置对照的交叉验证

`python3 run_demo.py --scenario deadlock` 是韩臻浩在 `scenarios.py` 里内置的同题对照，与本文三个 JSON 相互独立：

| 内置方案 | 完成率 | 死锁 | 回滚 | 对应本文文件 | 结论是否一致 |
|---|---|---|---|---|---|
| `avoidance` | 1.0 | 0 | 0 | `avoid.json` | 一致 |
| `detection_only` | 0.0 | 1 | 0 | `deadlock_unresolved.json` | 一致 |
| `detection_and_recovery` | 1.0 | 1 | 1 | `deadlock_recover.json` | 一致 |

两条路径（代码内置场景 / JSON 场景文件）得到同一组开关结论，说明案例文件没有写错开关。

### 3.3 7.4 四项对应关系

| 7.4 场景 | 配置 | 文件 | 实测 |
|---|---|---|---|
| 正常排队 | 默认 | `queue_wait.json` | 等待后恢复，死锁 0，无错误报警 |
| 无保护死锁 | 关避免、关破解、留检测 | `deadlock_unresolved.json` | 检测到环，A/B 未完成 |
| 检测后破解 | 关避免、开检测与回滚 | `deadlock_recover.json` | 发现环 → 释放 → 继续执行 |
| 提前避免 | 开安全性检查 | `avoid.json` | 危险申请被延后，环未形成 |

四个场景均通过正常步骤与资源接口建立循环等待（先各持一资源，再申请对方持有的资源），
没有绕过接口改写 `allocation`（4.3 条明令禁止）。

---

## 4 资源对象与一次申请的四道关

| 资源 | 类型 | 说明 |
|---|---|---|
| `tea_table` | 互斥单实例 | 茶歇台 |
| `cup_station` | 互斥单实例 | 取杯区 |
| `return_station` | 互斥单实例 | 回收操作位，不模拟堆积容量 |
| `corridor` | 互斥单实例 | 单条窄通道 |
| `request_board` | 共享只读 | 不写入 `allocation`，不参与互斥排队，不进 wait-for 图 |

`ResourceManager.try_acquire()` 的判定顺序固定，四种结果互斥：

| 步骤 | 判定 | `reason` | 计入资源冲突 | 建立 wait-for 边 |
|---|---|---|---|---|
| 1 | 声明非法 / Max 超容量 | 抛 `ValueError` | 否（输入错误） | 否 |
| 2 | 资源故障或关闭 | `resource outage` | **否** | 否 |
| 3 | 物理容量不足 | `resource occupied` | **是，且只在此处计数** | 是 |
| 4 | Banker 试分配不安全 | `Banker safety check rejected request` | 否（单列安全拒绝） | 否 |

第 3 步才写 `waiting_requests`，所以故障与安全拒绝不会伪造出资源死锁——这是 7.2「故障、通道关闭、前置依赖和普通排队分别记录等待原因」的落地方式。
故障不改写物理容量，只由 `blocked_until` 表达，已持有者账目保持不动（第 8 节「保留通道占用直至恢复」）。

---

## 5 归属查询与账目自检

本轮在 `release()` 之后追加三个只读方法，不改既有签名，不影响引擎行为：

| 方法 | 用途 |
|---|---|
| `holders(name)` | 某资源当前占用者，按 task_id 排序 |
| `held_by(task_id)` | 某任务当前持有的资源，按名称排序 |
| `audit(tasks=None)` | 账目一致性自检：超容量、占用未声明资源、零值残留、**已完成/已撤销/未到达任务仍持有资源** |

`audit()` 交叉核对任务侧状态，直接对应 17 节「资源不会违规重复分配，资源与任务账目一致」。
八个场景跑完后 `audit()` 全部返回空列表，测试里固化为 `test_every_demo_ends_with_clean_ledger`。

> 说明：`audit()` 目前只在测试与人工核查中调用，引擎输出（`--view json`）还没有 `audit` 字段。
> 若要写进每次运行结果，需要韩臻浩在集成层加一行调用，属公共接口改动，我不擅自修改。

---

## 6 逐案例记录

统一命令：`python3 run_demo.py --input data/demos/<file> --view trace`

### 6.1 `acquire_release.json` — 正常申请释放

**配置**：`banker_enabled=true`、检测与回滚开启（不触发）、非抢占、H=20。
资源 `tea_table` / `cup_station` / `corridor` 各 1。N1 整理台面 4 步占台面；N2 取杯 2 步占取杯区，配送 2 步占通道。

**操作步骤**：执行上述命令，`--view trace` 逐事件核对。

**结果**：

| 项 | 实测 |
|---|---|
| 完成 | N1 t=4、N2 t=4，`all tasks finished` |
| 冲突 / 死锁 / 安全拒绝 | 0 / 0 / 0 |
| 逐资源利用率 | tea_table 0.2、cup_station 0.1、corridor 0.1 |
| 账目自检 | 空 |

判据：两个任务同时持有不同资源并并发推进，说明空闲检查不会把无关资源误锁；
N2 在 t=2 释放取杯区并当步申请通道，说明步骤边界的释放与再申请都生效。

### 6.2 `conflict.json` — 资源冲突

**配置**：`banker_enabled=true`、非抢占、H=20，单资源 `tea_table`。
C1 优先级 2、t=0 到达、占台面 3 步；C2 优先级 1、t=1 到达、需台面 2 步。

**操作步骤**：同上命令。

**结果**：

| 项 | 实测 |
|---|---|
| 冲突次数 | **1**（C2 于 t=1 被拒，只计一次） |
| 完成 | C1 t=3、C2 t=5 |
| 死锁 / 安全拒绝 | 0 / 0 |
| 账目自检 | 空 |

```
t=1  资源等待: C2 resource occupied
t=3  任务完成: C1
t=3  start: C2
t=5  任务完成: C2
```

判据：被拒原因是 `resource occupied`（而非 outage 或安全拒绝），且同一段连续等待只计 1 次，符合第 10 节口径。
C2 的等待 4 步后自然解除，没有进入死锁检测分支。

### 6.3 `stage_release.json` — 跨阶段保留

**配置**：`banker_enabled=true`、非抢占、H=30。
R1 三阶段回收：通道到达（释放通道）→ 占台收集（**不释放台面**）→ 申请回收区完成转移（释放回收区与台面）。
T1 递送、M1 整理台面同时在队列。

**操作步骤**：同上命令。

**结果**：

| 项 | 实测 |
|---|---|
| 完成 | R1 t=6、T1 t=5、M1 t=8 |
| 冲突 / 死锁 | 1 / 0 |
| 逐资源利用率 | tea_table 0.1667、cup_station 0.0333、return_station 0.0667、corridor 0.1333 |

关键轨迹（时间步级别）：

```
t=1  stage_start: R1      # 取得 tea_table，release_resources 为空
t=2  资源等待: M1 resource occupied
t=4  stage_complete: R1   # 阶段结束仍不释放
t=6  任务完成: R1         # 到任务完成才连同 return_station 一起释放
t=6  start: M1
```

判据：`basic.json` 是单阶段任务，证明不了「未列入释放清单的占用跨阶段保留」；本案例能。

### 6.4 `queue_wait.json` — 普通等待

**配置**：`banker_enabled=true`、非抢占、H=40，单资源 `tea_table`。四个同优先级整理任务依次到达，仅靠截止时间定序。

**操作步骤**：同上命令。

**结果**：

| 项 | 实测 |
|---|---|
| 完成顺序 | Q1 t=4 → Q2 t=8 → Q3 t=11 → Q4 t=13 |
| 冲突 / 死锁 | 3 / **0** |
| 茶歇台利用率 | 0.325 |

判据：三次等待全部可自然恢复，`deadlock_count = 0`。若此处报警，说明检测器把普通排队误判为循环等待。
每个等待者只计 1 次冲突，与第 10 节「同一次连续等待不每步重复计数」一致。

### 6.5 `deadlock_unresolved.json` — 死锁形成且不解除

**配置**：`banker_enabled=false`、`deadlock_detection=true`、`deadlock_recovery=false`、非抢占、H=40。
A 先占台面再申请回收区，B 以相反顺序申请，两者 `rollback_allowed=true`（虚拟预留步骤）。

**操作步骤**：同上命令，另用 `--view json` 核对停止原因与退出码。

**结果**：

| 项 | 实测 |
|---|---|
| 停止原因 | `max_time`（H=40），**退出码 0，不挂起** |
| 死锁次数 | 1（未解除期间不重复累计） |
| 冲突次数 | 2 |
| 结局 | A、B 均未完成，等待原因 `resource occupied` |
| 账目自检 | 空（等待中的任务持有资源属正常） |

```
t=1  资源等待: A resource occupied
t=1  资源等待: B resource occupied
t=1  检测到死锁:
t=40 stop: max_time
```

判据：17 节「即使死锁未解除也能到 H 正常导出结果」的直接证据。`deadlock.json` 开了恢复，覆盖不到这一分支。

### 6.6 `deadlock_recover.json` — 死锁解除

**配置**：与 6.5 同一份 `tasks` / `resources` / `max_time`，仅 `deadlock_recovery=true`。

**操作步骤**：同上命令。

**结果**：

| 项 | 实测 |
|---|---|
| 完成 | A t=3、B t=5，`all tasks finished` |
| 死锁次数 | 1（检测到并解除） |
| 回滚次数 / 丢失工作量 / 实际重做 | 1 / 1 / 1 |
| 冲突 | 3 |

```
t=1  检测到死锁:
t=1  回滚恢复: B lowest priority, least checkpoint redo cost, task id
t=3  任务完成: A
t=5  任务完成: B
```

判据：受害者选择符合 7.3「优先选环中优先级最低的可回滚任务，相同时按较少重做成本、任务编号」；
回滚后 B 未立即重建同一环（A 已持有台面），说明按统一资源顺序重试起了作用。

### 6.7 `avoid.json` — 提前避免

**配置**：与 6.5 同一份输入，仅 `banker_enabled=true`。

**操作步骤**：同上命令。

**结果**：

| 项 | 实测 |
|---|---|
| 完成 | A t=2、B t=4 |
| 死锁次数 | **0** |
| 安全性拒绝 | **1** |
| 回滚 | 0 |

判据见 3.1：拒绝发生在 B 申请回收区当场，环未形成。**避免组死锁为 0 不能单独证明检测存在**，
检测能力由 6.5 证明；三者必须一起看。

### 6.8 `fault_hold.json` — 故障期间保留占用

**配置**：`banker_enabled=true`、非抢占、H=30、单资源 `tea_table`。
F1 占台面做 6 步长任务；t=2 台面故障 3 步；F2 自 t=1 起排队。

**操作步骤**：同上命令。

**结果**：

| 项 | 实测 |
|---|---|
| 完成 | F1 t=9、F2 t=10 |
| `resource_outage_ticks` | tea_table = 3 |
| `resource_outage_held_ticks` | tea_table = **3** |
| 死锁 | 0 |

```
t=1  资源等待: F2 resource occupied
t=2  资源关闭:
t=2  中断暂停: F1 environment interruption
t=2  资源等待: F2 resource outage      # 原因从占用变为故障
t=5  资源恢复:
t=5  任务恢复: F1
t=9  任务完成: F1
```

判据：`resource_outage_held_ticks = 3` 说明故障三拍里台面始终由 F1 持有，账目没有被故障清空，
对应第 8 节「保留占用直至恢复」与第 10 节「故障期间持有资源的记录仍保留，但有效工作为零」。

---

## 7 待确认的三个问题

以下均为**实测与口径不一致**，不是文字表述问题。判定前不写进论文结论。

### 7.1 一次连续等待被故障打断后，冲突被计两次

- 输入：`data/demos/fault_hold.json`
- 命令：`python3 run_demo.py --input data/demos/fault_hold.json --view json`
- 预期：`conflict_count = 1`（F2 从 t=1 到 t=9 从未拿到台面，属同一次连续等待）
- 实际：`conflict_count = 2`
- 原因：`scheduler.py` 的去重键是 `(reason, request)`；t=2 原因由 `resource occupied` 变成 `resource outage`，键变后 t=5 恢复时再计一次
- 建议：去重键只取 `request`，或把 outage 视为同一等待段的延续；若确认按现状统计，需在指标定义里写明「故障会切断等待段」

### 7.2 到 H 停止时未完成任务的 `state` 是 `ready` 而非 `blocked`

- 输入：`data/demos/deadlock_unresolved.json`
- 命令：`python3 run_demo.py --input data/demos/deadlock_unresolved.json --view json`
- 预期：按 4.3 与 17 节，未完成任务应保留 WAITING/BLOCKED 并记录原因
- 实际：`A/B.state = "ready"`，但 `waiting_reason = "resource occupied"`；摘要表据此显示「就绪」
- 推测：`_update_ready()` 在 `max_time` 停止前把 BLOCKED 改回 READY，而 `_start_tasks()` 未再执行
- 影响：`unfinished` 块的原因正确，只有 `state` 字段与摘要表不一致；论文引用状态分布时需注意

### 7.3 释放与获准发生在同一时刻

- 输入：`data/demos/conflict.json`
- 预期：按第 9 节「同一步结束后，等待任务从下一时间步重试」，C2 应在 t=4 获准
- 实际：C1 于 t=3 完成并释放，C2 在同一时刻 t=3 获准，执行区间 [3,5)
- 影响：两个任务执行区间不重叠，不违反互斥；只影响「授权时刻」与平均时延的标注。若王晶莹按「下一时间步」预期核对，会差 1 步
- 建议：在 `docs/interfaces.md` 写明重试发生在释放同一时刻的分配阶段，避免统计口径分歧

---

## 8 与验收条款的对应

| 条款 | 证据 |
|---|---|
| 17 节「互斥资源不会违规重复分配，账目一致」 | `audit(tasks)` 在八个场景跑完后均为空；`test_every_demo_ends_with_clean_ledger` |
| 17 节「冲突、危险申请、死锁、故障等待正确区分」 | 四种 `reason` 互斥（第 4 节）；`fault_hold` 与 `queue_wait` 的对照 |
| 17 节「死锁未解除也能到 H 正常导出」 | 6.5，`max_time` + 退出码 0 |
| 7.4 四项专项验证 | 3.3 表，四个场景全部实跑 |
| 考核标准「死锁避免/检测/破解三项都有可运行场景」 | `avoid` / `deadlock_unresolved` / `deadlock_recover` 同源三组 |
| 考核标准「竞争环境：申请被拒、等待、重排、恢复的日志」 | `--view trace` 逐事件；6.2、6.4 引用了原始行 |
| 考核标准「资源建模：容量定义、占用记录、冲突日志」 | `resources.py` 账本 + `trace` + `audit()` |

---

## 9 未完成与依赖

| 项 | 状态 | 阻塞原因 | 解除条件 |
|---|---|---|---|
| Ubuntu 22.04 现场运行记录 | 未完成 | 本机为 Ubuntu 24.04 容器，Python 3.11 | 教师目标机上按 `docs/run_ubuntu22.md` 末尾模板执行并填写 |
| `run_demo.py` 与 `python3 -m src.main --scenario` 的路径映射 | 未记录 | 仓库结构为 `tea_break_scheduler/`，与第 14 节目录不同（第 14 节允许等效路径） | 韩臻浩在 `docs/interfaces.md` 建立对应关系 |
| 任务字段 `held_resources` / `waiting_request` | 未实现 | `models.py` 有 `waiting_reason`，无这两个字段；`audit()` 因此无法与任务侧持有清单逐项对账 | 韩臻浩补充字段后，`audit()` 增加一项交叉核对 |
| 引擎输出 `audit` 字段 | 未接入 | 属集成层改动 | 韩臻浩在 `run_demo` 输出中追加一行 |

---

## 10 反馈格式

给韩臻浩提问题按五项写，缺一不可：

```
输入文件：data/demos/fault_hold.json
执行命令：python3 run_demo.py --input data/demos/fault_hold.json --view json
预期结果：conflict_count = 1
实际结果：conflict_count = 2
运行日志：t=1 occupied → t=2 outage → t=5 occupied（附 trace）
```
