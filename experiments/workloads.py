"""王晶莹：四类实验负载（普通 / 台面拥堵 / 紧急密集 / 故障强度）。

每个 (kind, seed) 生成一份固定输入：任务、资源与事件。相同种子下四类负载
各自独立，五种策略复用同一份输入（input 文档与 workload_sha256 相同），
从而把差异归因到策略而不是负载。
"""
from __future__ import annotations

import random

from tea_break_scheduler.models import Interrupt, InterruptType, Resource, Task, TaskStage

KINDS = ("normal", "crowded", "urgent", "fault")
HORIZON = 200

KIND_TITLES = {
    "normal": "普通负载",
    "crowded": "台面拥堵",
    "urgent": "紧急密集",
    "fault": "故障强度",
}


def resources() -> dict[str, Resource]:
    """与固定演示一致的资源集合；公告板为共享只读资源，不参与互斥。"""
    return {name: Resource(name, shared=name == "request_board") for name in
            ("tea_table", "cup_station", "return_station", "corridor", "request_board")}


def _delivery(tid: str, at: int, rng: random.Random, urgent: bool = False) -> Task:
    first, second = 1, rng.randint(2, 3)
    duration = first + second
    slack = rng.randint(1, 3) if urgent else rng.randint(10, 25)
    return Task(tid, "紧急送水杯" if urgent else "递送水杯",
                3 if urgent else rng.choice((1, 2, 2, 3)),
                at + duration + slack, duration, submitted_at=at, urgent=urgent,
                task_type="delivery",
                stages=[TaskStage("取杯", first, {"cup_station": 1}, ["cup_station"]),
                        TaskStage("通道配送", second, {"corridor": 1}, ["corridor"])])


def _maintenance(tid: str, at: int, rng: random.Random, long: bool = False) -> Task:
    duration = rng.randint(6, 9) if long else rng.randint(4, 6)
    return Task(tid, "整理茶歇台", rng.choice((1, 2)), at + duration + rng.randint(8, 18),
                duration, submitted_at=at, resources={"tea_table": 1}, task_type="maintenance")


def _recycle(tid: str, at: int, rng: random.Random) -> Task:
    return Task(tid, "回收空杯", 1, at + 18, 4, submitted_at=at, task_type="recycle",
                stages=[TaskStage("前往台面", 1, {"corridor": 1}, ["corridor"]),
                        TaskStage("台面收集", 2, {"tea_table": 1}, preemptible=False),
                        TaskStage("原子转移至回收区", 1, {"tea_table": 1, "return_station": 1},
                                  ["tea_table", "return_station"], preemptible=False)])


def _build_normal(rng: random.Random):
    tasks = []
    for i in range(10):
        at = rng.randint(0, 110)
        tasks.append(_delivery(f"T{i + 1:02d}", at, rng, urgent=rng.random() < 0.15))
    for i in range(5):
        tasks.append(_maintenance(f"M{i + 1:02d}", rng.randint(0, 100), rng))
    for i in range(3):
        tasks.append(_recycle(f"R{i + 1:02d}", rng.randint(0, 90), rng))
    return tasks, []


def _build_crowded(rng: random.Random):
    tasks = []
    for i in range(30):
        tasks.append(_maintenance(f"M{i + 1:02d}", rng.randint(0, 100), rng, long=True))
    for i in range(10):
        tasks.append(_delivery(f"T{i + 1:02d}", rng.randint(0, 120), rng, urgent=rng.random() < 0.1))
    for i in range(8):
        tasks.append(_recycle(f"R{i + 1:02d}", rng.randint(0, 110), rng))
    return tasks, []


def _build_urgent(rng: random.Random):
    tasks = []
    for i in range(8):
        tasks.append(_delivery(f"U{i + 1:02d}", rng.randint(0, 120), rng, urgent=True))
    for i in range(6):
        tasks.append(_delivery(f"T{i + 1:02d}", rng.randint(0, 120), rng))
    for i in range(4):
        tasks.append(_maintenance(f"M{i + 1:02d}", rng.randint(0, 100), rng))
    for i in range(2):
        tasks.append(_recycle(f"R{i + 1:02d}", rng.randint(0, 90), rng))
    at1, at2 = rng.randint(20, 110), rng.randint(40, 130)
    events = [Interrupt(at1, InterruptType.URGENT, "临时加急送水",
                        task=_delivery("UX1", at1, rng, urgent=True)),
              Interrupt(at2, InterruptType.URGENT, "临时加急续杯",
                        task=_delivery("UX2", at2, rng, urgent=True))]
    return tasks, events


def _build_fault(rng: random.Random):
    tasks, _ = _build_normal(rng)
    events = []
    for i in range(6):
        at = rng.randint(10, 140)
        target = rng.choice(("tea_table", "corridor", "cup_station"))
        kind = InterruptType.FAULT if i % 2 == 0 else InterruptType.ENVIRONMENT
        events.append(Interrupt(at, kind, f"{target} 临时不可用", resource=target,
                                duration=rng.randint(6, 14)))
    return tasks, events


_BUILDERS = {"normal": _build_normal, "crowded": _build_crowded,
             "urgent": _build_urgent, "fault": _build_fault}


def build(kind: str, seed: int):
    """返回 (tasks, events)；同一 (kind, seed) 始终得到同一份输入。"""
    if kind not in _BUILDERS:
        raise ValueError(f"unknown workload kind: {kind}")
    rng = random.Random(seed * 1009 + KINDS.index(kind))
    tasks, events = _BUILDERS[kind](rng)
    return tasks, events


def describe(kind: str, seed: int) -> dict:
    tasks, events = build(kind, seed)
    return {"kind": kind, "seed": seed, "tasks": len(tasks), "events": len(events),
            "urgent": sum(1 for t in tasks if t.urgent) + sum(1 for e in events if e.kind is InterruptType.URGENT),
            "static_work": sum(t.duration for t in tasks)}
