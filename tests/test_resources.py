# 资源模块局部测试：申请/释放语义、故障期间保留占用、归属查询与账目自检。
import json
import unittest
from pathlib import Path

from tea_break_scheduler.models import Resource, Task, TaskState
from tea_break_scheduler.resources import ResourceManager
from tea_break_scheduler.scenario_io import load_scenario

DEMOS = Path(__file__).resolve().parents[1] / "data" / "demos"


def task(task_id: str, **overrides) -> Task:
    fields = dict(task_id=task_id, name=task_id, priority=1, deadline=20, duration=2,
                  resources={"tea_table": 1}, max_claim={"tea_table": 1})
    fields.update(overrides)
    return Task(**fields)


def manager(banker: bool = False) -> ResourceManager:
    return ResourceManager({
        "tea_table": Resource(name="tea_table", capacity=1),
        "return_station": Resource(name="return_station", capacity=1),
        "request_board": Resource(name="request_board", capacity=1, shared=True),
    }, banker_enabled=banker)


class AcquireTests(unittest.TestCase):
    def test_grant_records_allocation(self):
        rm, a = manager(), task("A")
        result = rm.try_acquire(a, {"A": a}, 0, {"tea_table": 1})
        self.assertTrue(result.granted)
        self.assertEqual(result.reason, "granted")
        self.assertEqual(rm.allocation["A"], {"tea_table": 1})

    def test_occupied_reason_is_ownership_conflict(self):
        rm = manager()
        a, b = task("A"), task("B")
        rm.try_acquire(a, {"A": a, "B": b}, 0, {"tea_table": 1})
        result = rm.try_acquire(b, {"A": a, "B": b}, 1, {"tea_table": 1})
        self.assertFalse(result.granted)
        # 只有这个原因会建立 wait-for 边，调度器据此计数资源冲突。
        self.assertEqual(result.reason, "resource occupied")

    def test_shared_resource_does_not_consume_allocation(self):
        rm = manager()
        a = task("A", resources={"request_board": 1}, max_claim={"request_board": 1})
        result = rm.try_acquire(a, {"A": a}, 0, {"request_board": 1})
        self.assertTrue(result.granted)
        self.assertNotIn("A", rm.allocation)


class ReleaseTests(unittest.TestCase):
    def test_partial_release_keeps_other_resources(self):
        rm = manager()
        a = task("A", resources={"tea_table": 1, "return_station": 1},
                 max_claim={"tea_table": 1, "return_station": 1})
        rm.try_acquire(a, {"A": a}, 0, {"tea_table": 1, "return_station": 1})
        rm.release("A", ["return_station"])
        self.assertEqual(rm.held_by("A"), ("tea_table",))

    def test_full_release_clears_entry(self):
        rm, a = manager(), task("A")
        rm.try_acquire(a, {"A": a}, 0, {"tea_table": 1})
        rm.release("A")
        self.assertNotIn("A", rm.allocation)
        self.assertEqual(rm.holders("tea_table"), ())


class OutageTests(unittest.TestCase):
    def test_outage_rejects_new_request_without_touching_holder(self):
        rm = manager()
        a, b = task("A"), task("B")
        rm.try_acquire(a, {"A": a, "B": b}, 0, {"tea_table": 1})
        rm.resources["tea_table"].blocked_until = 5
        result = rm.try_acquire(b, {"A": a, "B": b}, 2, {"tea_table": 1})
        self.assertFalse(result.granted)
        self.assertEqual(result.reason, "resource outage")
        # 故障不改写物理容量，也不清空已持有者：暂停期间占用保留到恢复（第 8 节）。
        self.assertEqual(rm.holders("tea_table"), ("A",))
        self.assertEqual(rm.physical_available()["tea_table"], 0)
        self.assertEqual(rm.available(2)["tea_table"], 0)
        self.assertEqual(rm.available(5)["tea_table"], 0)

    def test_available_reflects_outage_only_after_capacity(self):
        rm, a = manager(), task("A")
        rm.try_acquire(a, {"A": a}, 0, {"tea_table": 1})
        self.assertEqual(rm.available(0)["tea_table"], 0)
        rm.resources["return_station"].blocked_until = 3
        self.assertEqual(rm.available(0)["return_station"], 0)
        self.assertEqual(rm.available(3)["return_station"], 1)


class QueryTests(unittest.TestCase):
    def test_holders_are_sorted_for_stable_output(self):
        rm = manager()
        for tid in ("C", "A", "B"):
            t = task(tid, resources={"return_station": 1}, max_claim={"return_station": 1})
            rm.try_acquire(t, {tid: t}, 0, {"return_station": 1})
        self.assertEqual(rm.holders("return_station"), ("C",))

    def test_held_by_lists_multiple_resources(self):
        rm = manager()
        a = task("A", resources={"tea_table": 1, "return_station": 1},
                 max_claim={"tea_table": 1, "return_station": 1})
        rm.try_acquire(a, {"A": a}, 0, {"tea_table": 1, "return_station": 1})
        self.assertEqual(rm.held_by("A"), ("return_station", "tea_table"))

    def test_unknown_resource_is_an_input_error(self):
        rm, a = manager(), task("A")
        with self.assertRaises(ValueError):
            rm.try_acquire(a, {"A": a}, 0, {"no_such_resource": 1})


class AuditTests(unittest.TestCase):
    def test_clean_ledger_after_normal_use(self):
        rm, a = manager(), task("A")
        rm.try_acquire(a, {"A": a}, 0, {"tea_table": 1})
        self.assertEqual(rm.audit(), [])
        rm.release("A")
        self.assertEqual(rm.audit(), [])

    def test_over_capacity_is_reported(self):
        rm = manager()
        rm.allocation["A"] = {"tea_table": 2}
        problems = rm.audit()
        self.assertEqual(len(problems), 1)
        self.assertIn("超过容量", problems[0])

    def test_unknown_resource_in_allocation_is_reported(self):
        rm = manager()
        rm.allocation["A"] = {"ghost": 1}
        self.assertTrue(any("未声明" in p for p in rm.audit()))

    def test_completed_task_holding_resource_is_reported(self):
        rm, a = manager(), task("A")
        rm.try_acquire(a, {"A": a}, 0, {"tea_table": 1})
        a.state = TaskState.COMPLETED
        # 资源账本自身没超容量，但与任务状态不一致，交叉核对必须报出。
        self.assertTrue(any("仍持有" in p for p in rm.audit([a])))


class DemoLedgerTests(unittest.TestCase):
    """每个演示场景跑完后账本必须自洽，这是 17 节"资源与任务账目一致"的可执行证据。"""

    def test_every_demo_ends_with_clean_ledger(self):
        for path in sorted(DEMOS.glob("*.json")):
            with self.subTest(demo=path.name):
                scheduler = load_scenario(path)
                result = scheduler.run()
                problems = scheduler.resource_manager.audit(scheduler.tasks)
                self.assertEqual(problems, [], f"{path.name} 账目不一致：{problems}")
                self.assertEqual(result["stop_reason"] in ("all tasks finished", "max_time"), True)

    def test_deadlock_controls_share_one_input(self):
        # 7.4 的三组受控对照必须同一输入，只允许两个开关不同，否则结论不成立。
        docs = {
            name: json.loads((DEMOS / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("deadlock_unresolved", "deadlock_recover", "avoid")
        }
        base = docs["deadlock_unresolved"]
        for name, doc in docs.items():
            self.assertEqual(doc["tasks"], base["tasks"], f"{name} 任务定义与对照组不一致")
            self.assertEqual(doc["resources"], base["resources"], f"{name} 资源定义与对照组不一致")
            self.assertEqual(doc["config"]["max_time"], base["config"]["max_time"], f"{name} 观察窗口不一致")
            diff = {k for k in doc["config"] if doc["config"][k] != base["config"][k]}
            self.assertTrue(diff <= {"banker_enabled", "deadlock_recovery"}, f"{name} 多改了 {diff}")


if __name__ == "__main__":
    unittest.main()
