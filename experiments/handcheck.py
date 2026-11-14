"""王晶莹：人工核算的指标样例（先小后大，先手算后批量）。

三条任务的输入可以完全手算，用来确认引擎输出的 completion_rate、
average_completion_delay、conflict_count 与单资源利用率没有算错；
核对通过后再跑 20 个种子的正式实验。

手算（H = 10）：

    任务 资源        到达  时长  执行区间  完成  截止  是否按时  时延
    A    tea_table    0     2    0–2       2     5     是        2
    B    corridor     0     3    0–3       3     6     是        3
    C    tea_table    0     1    2–3       3    10     是        3

    完成率        = 3 / 3 = 1.0
    按时完成率    = 3 / 3 = 1.0
    平均完成时延  = (2 + 3 + 3) / 3 = 2.6667
    平均逾期      = 0
    冲突次数      = 1（C 在 t=0 申请 tea_table 被 A 占用，进入一次新等待）
    tea_table 利用率 = 忙碌 3 tick / 可用 10 tick = 0.3
    corridor  利用率 = 3 / 10 = 0.3

运行：python3 experiments/handcheck.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tea_break_scheduler.models import Resource, SchedulerConfig, Task   # noqa: E402
from tea_break_scheduler.scheduler import Scheduler                     # noqa: E402

HORIZON = 10
EXPECTED = {
    "total_tasks": 3,
    "completed_tasks": 3,
    "completion_rate": 1.0,
    "on_time_completion_rate": 1.0,
    "average_completion_delay": 2.6667,
    "average_lateness": 0.0,
    "conflict_count": 1,
    "deadlock_count": 0,
    "urgent_task_miss_rate": None,
}


def build() -> tuple[list[Task], dict[str, Resource]]:
    tasks = [Task("A", "整理台面", 1, 5, 2, resources={"tea_table": 1}),
             Task("B", "通道配送", 1, 6, 3, resources={"corridor": 1}),
             Task("C", "二次整理", 1, 10, 1, resources={"tea_table": 1})]
    resources = {name: Resource(name) for name in ("tea_table", "corridor", "cup_station",
                                                   "return_station")}
    return tasks, resources


def main() -> int:
    tasks, resources = build()
    result = Scheduler(tasks, resources, SchedulerConfig(max_time=HORIZON)).run()
    metrics = result["metrics"]

    print(f"{'指标':<26}{'手算':>10}{'引擎':>12}  结论")
    ok = True
    for name, expected in EXPECTED.items():
        actual = metrics.get(name)
        same = (actual is None and expected is None) or (
            isinstance(actual, (int, float)) and isinstance(expected, (int, float))
            and abs(actual - expected) <= 1e-4)
        ok = ok and same
        print(f"{name:<26}{str(expected):>10}{str(actual):>12}  {'通过' if same else '不一致'}")

    for resource, expected in (("tea_table", 0.3), ("corridor", 0.3)):
        actual = metrics["resource_utilization_by_resource"].get(resource)
        same = actual is not None and abs(actual - expected) <= 1e-4
        ok = ok and same
        print(f"{resource + ' 利用率':<24}{expected:>10}{str(actual):>12}  {'通过' if same else '不一致'}")

    print("\n" + ("人工核算样例通过：引擎指标与手算一致。" if ok
                  else "存在不一致，禁止用这批结果写报告。"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
