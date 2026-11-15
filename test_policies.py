"""policies.py 的单元测试（维护人：李铭昊）。

运行（仓库根目录）：
    python3 -m unittest tests.test_policies -v
    python3 -m unittest discover -s tests -v

覆盖项目说明 13.3 要求的三类验证案例（到达先后、不同优先级、同优先级并列），
外加两个边界与若干接口约束。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tea_break_scheduler.models import Task, task_from_dict
from tea_break_scheduler.policies import (
    FCFS,
    PRIORITY,
    explain,
    format_ranking,
    order_tasks,
    rank_tasks,
    selection_reason,
)

CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "demos" / "policies_cases.json"


def make(task_id: str, priority: int = 1, deadline: int = 20, submitted: int = 0, urgent: bool = False) -> Task:
    # duration 固定为 1：本文件只验证排序，不关心工作量。
    return Task(task_id, task_id, priority, deadline, 1, submitted_at=submitted, urgent=urgent)


class ArrivalOrderTests(unittest.TestCase):
    """C1：FCFS 只看到达时刻，看不到达的高优先级任务不得插队。"""

    def test_order_by_arrival(self) -> None:
        tasks = [make("T3", submitted=4), make("T1", submitted=0), make("T2", submitted=2)]
        self.assertEqual(["T1", "T2", "T3"], [t.task_id for t in order_tasks(tasks, FCFS)])

    def test_late_urgent_task_does_not_jump_queue(self) -> None:
        tasks = [make("low", priority=1, submitted=0), make("urgent", priority=3, submitted=1, urgent=True)]
        self.assertEqual(["low", "urgent"], [t.task_id for t in order_tasks(tasks, FCFS)])

    def test_same_arrival_breaks_by_task_id(self) -> None:
        tasks = [make("T10", submitted=0), make("T9", submitted=0), make("T2", submitted=0)]
        self.assertEqual(["T10", "T2", "T9"], [t.task_id for t in order_tasks(tasks, FCFS)])


class PriorityOrderTests(unittest.TestCase):
    """C2：优先级数值大者先执行，与到达时刻无关。"""

    def test_priority_desc(self) -> None:
        tasks = [make("biz", priority=2), make("maint", priority=1), make("urgent", priority=3, submitted=5)]
        self.assertEqual(["urgent", "biz", "maint"], [t.task_id for t in order_tasks(tasks, PRIORITY)])


class TieBreakTests(unittest.TestCase):
    """C3/C4：优先级相同后，依次比截止时间、到达时刻、任务编号。"""

    def test_deadline_then_arrival_then_id(self) -> None:
        tasks = [
            make("no-tie", priority=2, deadline=50, submitted=1),
            make("early-deadline", priority=2, deadline=20, submitted=9),
            make("late-arrive", priority=2, deadline=30, submitted=5),
            make("early-arrive", priority=2, deadline=30, submitted=3),
            make("id-b", priority=2, deadline=40, submitted=30),
            make("id-a", priority=2, deadline=40, submitted=30),
        ]
        expected = ["early-deadline", "early-arrive", "late-arrive", "id-a", "id-b", "no-tie"]
        self.assertEqual(expected, [t.task_id for t in order_tasks(tasks, PRIORITY)])

    def test_all_tied_falls_back_to_task_id(self) -> None:
        tasks = [make("t3"), make("t1"), make("t2")]
        self.assertEqual(["t1", "t2", "t3"], [t.task_id for t in order_tasks(tasks, PRIORITY)])


class InterfaceTests(unittest.TestCase):
    def test_empty_candidate_list(self) -> None:
        self.assertEqual([], order_tasks([], PRIORITY))
        self.assertEqual([], rank_tasks([], PRIORITY))
        self.assertEqual("", format_ranking([], PRIORITY))

    def test_order_tasks_does_not_mutate_input(self) -> None:
        tasks = [make("T2", submitted=2), make("T1", submitted=1)]
        snapshot = [t.task_id for t in tasks]
        order_tasks(tasks, FCFS)
        self.assertEqual(snapshot, [t.task_id for t in tasks])

    def test_rank_matches_order_and_covers_every_task(self) -> None:
        tasks = [make("T1", priority=2), make("T2", priority=3), make("T3", priority=1)]
        ranked = rank_tasks(tasks, PRIORITY)
        self.assertEqual([t.task_id for t in order_tasks(tasks, PRIORITY)], [t.task_id for t, _ in ranked])
        self.assertEqual(len(tasks), len(ranked))

    def test_reason_explains_urgent_and_tie_break(self) -> None:
        tasks = [make("a", priority=2, deadline=10), make("b", priority=3, deadline=10, urgent=True)]
        ranked = rank_tasks(tasks, PRIORITY)
        self.assertEqual("b", ranked[0][0].task_id)
        self.assertIn("紧急任务优先", ranked[0][1])
        self.assertIn("优先级更高", ranked[0][1])

    def test_reason_for_tied_priority_mentions_deadline(self) -> None:
        earlier = make("early", priority=1, deadline=20)
        later = make("late", priority=1, deadline=30)
        self.assertIn("截止时间更早", explain(earlier, later, PRIORITY))

    def test_unknown_policy_raises(self) -> None:
        with self.assertRaises(ValueError):
            order_tasks([], "sjf")
        with self.assertRaises(ValueError):
            rank_tasks([], "sjf")
        with self.assertRaises(ValueError):
            selection_reason("sjf")

    def test_selection_reason_known_policies(self) -> None:
        self.assertIn("FCFS", selection_reason(FCFS))
        self.assertIn("priority", selection_reason(PRIORITY))

    def test_deterministic_repeated_calls(self) -> None:
        tasks = [make("T%d" % i, priority=(i % 2) + 1, deadline=10, submitted=i % 3) for i in range(1, 8)]
        first = [t.task_id for t in order_tasks(tasks, PRIORITY)]
        for _ in range(5):
            self.assertEqual(first, [t.task_id for t in order_tasks(tasks, PRIORITY)])


class CaseFileTests(unittest.TestCase):
    """data/demos/policies_cases.json 里预先登记的预期顺序必须与程序输出一致。"""

    def test_all_cases(self) -> None:
        with CASES_PATH.open("r", encoding="utf-8") as handle:
            cases = json.load(handle)["cases"]
        self.assertGreaterEqual(len(cases), 3)
        for case in cases:
            with self.subTest(case=case["case_id"]):
                tasks = [task_from_dict(item) for item in case["tasks"]]
                actual = [t.task_id for t in order_tasks(tasks, case["policy"])]
                self.assertEqual(case["expected"], actual)


if __name__ == "__main__":
    unittest.main(verbosity=2)
