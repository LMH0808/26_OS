"""王晶莹：正式实验批量入口。

用法（仓库根目录）：

    python3 experiments/run_experiments.py --seeds 20

对四类负载（普通 / 台面拥堵 / 紧急密集 / 故障强度）× 20 个种子 × 5 种策略
各跑一次，输出：

    experiments/results/inputs/<kind>_<seed>.json   实际输入（可再次 --input 运行）
    experiments/results/raw/<kind>.json             每份结果的指标与溯源字段
    experiments/results/metrics.csv                 逐样本明细（Excel 可直接打开）

指标口径见 docs/experiments.md；结果中的 workload_sha256 用于核对同种子对照
是否共用同一份负载。
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tea_break_scheduler.models import SchedulerConfig          # noqa: E402
from tea_break_scheduler.scenario_io import scenario_document   # noqa: E402
from tea_break_scheduler.scheduler import Scheduler             # noqa: E402

from experiments import workloads                                # noqa: E402

POLICIES = ("baseline", "fcfs", "no_dynamic", "non_preemptive", "no_deadlock")
POLICY_CHANGES = {
    "baseline": {},
    "fcfs": {"policy": "fcfs"},
    "no_dynamic": {"dynamic_rescheduling": False},
    "non_preemptive": {"preemptive": False},
    "no_deadlock": {"banker_enabled": False, "deadlock_recovery": False},
}

SCALAR_METRICS = ("total_tasks", "completed_tasks", "unfinished_tasks", "completion_rate",
                  "on_time_completion_rate", "average_completion_delay", "average_lateness",
                  "urgent_eligible_tasks", "urgent_missed_tasks", "urgent_task_miss_rate",
                  "conflict_count", "deadlock_count", "safety_rejection_count",
                  "preemptions", "recoveries", "rollback_count", "rollback_work", "redo_work",
                  "resource_utilization")


def config_for(policy: str, horizon: int) -> SchedulerConfig:
    if policy not in POLICY_CHANGES:
        raise ValueError(f"unknown policy: {policy}")
    return replace(SchedulerConfig(max_time=horizon), **POLICY_CHANGES[policy])


def run_one(kind: str, seed: int, policy: str, tasks, events, horizon: int) -> dict:
    scheduler = Scheduler(copy.deepcopy(tasks), workloads.resources(),
                          config_for(policy, horizon), copy.deepcopy(events))
    result = scheduler.run()
    metrics = result["metrics"]
    row = {"workload": kind, "seed": seed, "policy": policy}
    for name in SCALAR_METRICS:
        row[name] = metrics.get(name)
    row["stop_reason"] = result["stop_reason"]
    row["elapsed_time"] = result["elapsed_time"]
    row["source_sha256"] = result["metadata"]["source_sha256"]
    row["input_sha256"] = result["metadata"]["input_sha256"]
    row["workload_sha256"] = result["metadata"]["workload_sha256"]
    row["unfinished"] = result["unfinished"]
    row["resource_utilization_by_resource"] = metrics["resource_utilization_by_resource"]
    return row


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="运行四类负载 × 种子 × 策略的正式实验")
    parser.add_argument("--seeds", type=int, default=20, help="独立种子数，默认 20")
    parser.add_argument("--kinds", default=",".join(workloads.KINDS),
                        help="逗号分隔，默认四类全跑")
    parser.add_argument("--policies", default=",".join(POLICIES),
                        help="逗号分隔，默认五种策略全跑")
    parser.add_argument("--horizon", type=int, default=workloads.HORIZON,
                        help="统一观察窗口 H，默认 200")
    parser.add_argument("--out", default=str(ROOT / "experiments" / "results"),
                        help="结果目录")
    args = parser.parse_args(argv)

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    out = Path(args.out)
    (out / "inputs").mkdir(parents=True, exist_ok=True)
    (out / "raw").mkdir(parents=True, exist_ok=True)

    rows, summary = [], {}
    for kind in kinds:
        records = []
        for seed in range(1, args.seeds + 1):
            tasks, events = workloads.build(kind, seed)
            document = scenario_document(tasks, workloads.resources(),
                                         config_for("baseline", args.horizon), events, seed=seed)
            (out / "inputs" / f"{kind}_{seed:02d}.json").write_text(
                json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
            for policy in policies:
                row = run_one(kind, seed, policy, tasks, events, args.horizon)
                rows.append(row)
                records.append({key: value for key, value in row.items() if key != "workload"})
                print(f"{kind:8s} seed={seed:02d} {policy:16s} "
                      f"完成率={row['completion_rate']} 时延={row['average_completion_delay']} "
                      f"冲突={row['conflict_count']} 未完成={row['unfinished_tasks']}")
        (out / "raw" / f"{kind}.json").write_text(
            json.dumps({"workload": kind, "horizon": args.horizon,
                        "policies": policies, "runs": records},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        summary[kind] = len(records)

    columns = ["workload", "seed", "policy"] + list(SCALAR_METRICS) + [
        "stop_reason", "elapsed_time", "source_sha256", "input_sha256", "workload_sha256"]
    with (out / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    (out / "index.json").write_text(json.dumps(
        {"schema": 1, "horizon": args.horizon, "seeds": args.seeds,
         "kinds": kinds, "policies": policies, "runs": len(rows),
         "files": {"metrics": "metrics.csv", "raw": "raw/", "inputs": "inputs/"}},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n共 {len(rows)} 次运行；明细见 {out / 'metrics.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
