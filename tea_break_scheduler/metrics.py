"""Metric accumulator and output formatting for the tea-break scheduler.

The simulation engine updates raw counters during each time step. This module
converts those counters into the documented, report-ready metric dictionary.
All ratios with a zero denominator are returned as None (JSON null / blank CSV).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Metrics:
    total_tasks: int = 0
    completed_tasks: int = 0
    cancelled_tasks: int = 0
    urgent_tasks: int = 0
    urgent_missed: int = 0
    total_delay: int = 0
    total_response: int = 0
    on_time_tasks: int = 0
    conflicts: int = 0
    deadlocks: int = 0
    recoveries: int = 0
    preemptions: int = 0
    safety_rejections: int = 0
    rollback_count: int = 0
    rollback_work: int = 0
    redo_work: int = 0
    resource_busy_ticks: dict[str, int] = field(default_factory=dict)
    resource_held_ticks: dict[str, int] = field(default_factory=dict)
    resource_available_ticks: dict[str, int] = field(default_factory=dict)
    resource_outage_ticks: dict[str, int] = field(default_factory=dict)
    resource_outage_held_ticks: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        ratio = lambda a, b: round(a / b, 4) if b else None
        util = {name: ratio(self.resource_busy_ticks.get(name, 0), ticks)
                for name, ticks in self.resource_available_ticks.items()}
        occupancy = {name: ratio(self.resource_held_ticks.get(name, 0), ticks)
                     for name, ticks in self.resource_available_ticks.items()}
        defined = [value for value in util.values() if value is not None]
        return {
            "total_tasks": self.total_tasks, "completed_tasks": self.completed_tasks,
            "cancelled_tasks": self.cancelled_tasks,
            "unfinished_tasks": self.total_tasks - self.completed_tasks - self.cancelled_tasks,
            "completion_rate": ratio(self.completed_tasks, self.total_tasks),
            "on_time_completion_rate": ratio(self.on_time_tasks, self.total_tasks),
            "average_completion_delay": ratio(self.total_response, self.completed_tasks),
            "average_response_time": ratio(self.total_response, self.completed_tasks),
            "average_lateness": ratio(self.total_delay, self.completed_tasks),
            "resource_utilization": round(sum(defined) / len(defined), 4) if defined else None,
            "resource_utilization_by_resource": util,
            "resource_occupancy_by_resource": occupancy,
            "resource_busy_ticks": dict(self.resource_busy_ticks),
            "resource_held_ticks": dict(self.resource_held_ticks),
            "resource_available_ticks": dict(self.resource_available_ticks),
            "resource_outage_ticks": dict(self.resource_outage_ticks),
            "resource_outage_held_ticks": dict(self.resource_outage_held_ticks),
            "deadlock_count": self.deadlocks, "conflict_count": self.conflicts,
            "urgent_eligible_tasks": self.urgent_tasks, "urgent_missed_tasks": self.urgent_missed,
            "urgent_task_miss_rate": ratio(self.urgent_missed, self.urgent_tasks),
            "recoveries": self.recoveries, "preemptions": self.preemptions,
            "safety_rejection_count": self.safety_rejections,
            "rollback_count": self.rollback_count, "rollback_work": self.rollback_work,
            "redo_work": self.redo_work,
        }

