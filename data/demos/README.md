# data/demos 场景索引

本目录存放可直接喂给 `run_demo.py` 的版本化 JSON 场景。本文件索引卞苏阳提交的 8 个验证场景；
目录中另有 `basic.json`、`deadlock.json`、`baseline.json`（由韩臻浩提供），不在本索引范围内。
以下字段与取值均以目录内现有 JSON 及 `tea_break_scheduler/scenario_io.py` 的解析规则为准。

## 运行方式

在仓库根目录执行（`--input` 接收场景文件；`--view` 可选 `summary` / `trace` / `json`，默认 `summary`）：

```bash
python3 run_demo.py --input data/demos/acquire_release.json
python3 run_demo.py --input data/demos/conflict.json
python3 run_demo.py --input data/demos/stage_release.json
python3 run_demo.py --input data/demos/queue_wait.json
python3 run_demo.py --input data/demos/deadlock_unresolved.json
python3 run_demo.py --input data/demos/deadlock_recover.json
python3 run_demo.py --input data/demos/avoid.json
python3 run_demo.py --input data/demos/fault_hold.json
```

逐事件轨迹加 `--view trace`，完整结果导出加 `--view json`（例如 `--output result.json`）。
账目自检由 `tests/test_resources.py` 的 `test_every_demo_ends_with_clean_ledger` 覆盖：

```bash
python3 -m unittest discover -s tests
```

## 场景索引

| # | 文件 | 验证点 | banker / recovery / H | 资源 | 任务 | 事件 |
|---|---|---|---|---|---|---|
| 1 | `acquire_release.json` | 正常申请与释放，两个任务并发持有不同资源 | true / true / 20 | `tea_table`、`cup_station`、`corridor` 各 1 | N1 整理茶歇台（单阶段，占台面后释放）；N2 递送水杯（两阶段，取杯区 → 通道） | 无 |
| 2 | `conflict.json` | 同一互斥资源竞争：申请被拒 → 等待 → 释放后获准 | true / true / 20 | `tea_table` 1 | C1（优先级 2，t=0，3 步）、C2（优先级 1，t=1，2 步）均申请 `tea_table` | 无 |
| 3 | `stage_release.json` | 跨阶段保留占用：未列入 `release_resources` 的资源继续持有 | true / true / 30 | `tea_table`、`cup_station`、`return_station`、`corridor` 各 1 | R1 三阶段回收（「占台收集」不释放台面）；T1 两阶段递送；M1 单资源整理 | 无 |
| 4 | `queue_wait.json` | 普通排队等待，应与死锁区分 | true / true / 40 | `tea_table` 1 | Q1–Q4 同优先级、依次 t=0..3 到达，仅截止时间不同 | 无 |
| 5 | `deadlock_unresolved.json` | 关闭避免与破解、保留检测，形成环且不解除 | false / false / 40 | `tea_table`、`return_station` 各 1 | A 先占台面再申请回收区，B 顺序相反；两者 `rollback_allowed=true` | 无 |
| 6 | `deadlock_recover.json` | 与第 5 项同一输入，开启回滚破解 | false / true / 40 | 同第 5 项 | 同第 5 项 | 无 |
| 7 | `avoid.json` | 与第 5 项同一输入，开启安全性检查提前避免 | true / false / 40 | 同第 5 项 | 同第 5 项 | 无 |
| 8 | `fault_hold.json` | 资源故障期间保留占用 | true / true / 30 | `tea_table` 1 | F1（6 步，t=0）、F2（1 步，t=1） | t=2 的 `environment` 事件：`tea_table` 暂停 3 个时间单位 |

第 5–7 项是一组受控对照：`tasks`、`resources`、`config.max_time` 完全相同，仅 `banker_enabled`
与 `deadlock_recovery` 两个开关不同；`tests/test_resources.py` 的
`test_deadlock_controls_share_one_input` 固定了这一约束。

8 个文件使用的资源名：`tea_table` 茶歇台、`cup_station` 取杯区、`return_station` 回收区、
`corridor` 通道，均为单实例互斥资源（`capacity=1`、`shared=false`）。

## 字段说明（统一模板）

### 顶层

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | int | 固定为 1（`scenario_from_dict` 只接受 1）；8 个文件均为 1 |
| `seed` | int / null | 随机种子；8 个文件均为 null |
| `config` | object | 调度与算法开关，见下表 |
| `resources` | object | 资源名 → 资源定义，见下表 |
| `tasks` | array | 任务对象数组，见下表 |
| `events` | array | 中断/事件对象数组；除 `fault_hold.json` 外 7 个文件均为空数组 |

### `config`（对应 `models.SchedulerConfig`）

| 字段 | 说明 | 8 个文件中的取值 |
|---|---|---|
| `workers` | 服务员人数上限，null 表示不设人数约束 | 均为 null |
| `dynamic_rescheduling` | 是否在事件后重排 | 均为 true |
| `preemptive` | 是否允许抢占 | 均为 false |
| `banker_enabled` | 银行家安全性检查（死锁避免） | 见场景索引 |
| `deadlock_detection` | 资源分配图环检测 | 均为 true |
| `deadlock_recovery` | 检测后是否回滚破解 | 见场景索引 |
| `max_time` | 观察上限 H | 20 / 30 / 40，见场景索引 |
| `detection_period` | 死锁检测周期 | 均为 1 |
| `policy` | 排序策略，`priority` 或 `fcfs` | 均为 `priority` |

### `resources.<资源名>`（对应 `models.Resource`）

| 字段 | 说明 |
|---|---|
| `capacity` | 容量；互斥资源必须为 1 |
| `shared` | 是否共享只读；共享资源不写入互斥占用账本 |
| `blocked_until` | 故障/关闭截止时刻；8 个文件的资源定义均为 0（`fault_hold.json` 由 `events` 在运行时触发） |

### `tasks[]`（对应 `models.task_from_dict` / `TASK_INPUT_FIELDS`）

| 字段 | 说明 |
|---|---|
| `task_id` | 任务编号，须唯一 |
| `name` | 任务名称 |
| `priority` | 优先级，数值越大优先程度越高 |
| `deadline` | 软截止时刻，超时不直接取消 |
| `duration` | 执行时长；使用 `stages` 时必须等于各阶段 `duration` 之和 |
| `dependencies` | 前置任务 id 列表；8 个文件均为空 |
| `resources` | 单阶段任务的资源申请；与 `stages` 二选一，不能同时给出 |
| `preemptible` | 是否允许被调度抢占 |
| `urgent` | 是否紧急任务 |
| `submitted_at` | 到达时刻 |
| `stages` | 阶段列表；与 `resources` 二选一，见下表 |
| `max_claim` | 全程最大资源需求上界，须覆盖每个阶段的申请 |
| `rollback_allowed` | 是否允许作为死锁回滚受害者 |
| `max_retries` | 最大回滚重试次数；8 个文件均为 3 |
| `task_type` | 类别标签：`maintenance` / `delivery` / `recycle` |

### `stages[]`（对应 `models.TaskStage`）

| 字段 | 说明 |
|---|---|
| `name` | 阶段名称 |
| `duration` | 阶段时长 |
| `resources` | 本阶段申请的资源名 → 数量 |
| `release_resources` | 本阶段结束时释放的资源名列表；**空数组表示跨阶段保留占用**（见 `stage_release.json` 的「占台收集」） |
| `preemptible` | 本阶段是否允许抢占 |

### `events[]`（对应 `models.Interrupt`）

现有 8 个文件中仅 `fault_hold.json` 使用事件，出现的字段如下：

| 字段 | 说明 |
|---|---|
| `at` | 事件发生时刻 |
| `kind` | 事件类型；该文件为 `environment` |
| `description` | 说明文字 |
| `resource` | 受影响的资源名 |
| `duration` | 持续时长 |

`fault_hold.json` 中的唯一事件：

```json
{
  "at": 2,
  "kind": "environment",
  "description": "茶歇台临时清洁，暂停 3 个时间单位",
  "resource": "tea_table",
  "duration": 3
}
```
