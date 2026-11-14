"""王晶莹：指标汇总与静态图表。

读取 experiments/results/metrics.csv，按 (负载, 策略) 计算样本数、均值与样本
标准差，输出 summary.csv / summary.json，并在 experiments/figures/ 生成 SVG 图。
只用 Python 标准库，不依赖 numpy / matplotlib。
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SUMMARY_FIELDS = ("completion_rate", "on_time_completion_rate", "average_completion_delay",
                  "average_lateness", "urgent_task_miss_rate", "conflict_count",
                  "deadlock_count", "safety_rejection_count", "preemptions",
                  "unfinished_tasks", "rollback_work", "redo_work", "resource_utilization")
CHART_FIELDS = (("completion_rate", "完成率", "completion_rate.svg"),
                ("average_completion_delay", "平均完成时延", "average_delay.svg"),
                ("urgent_task_miss_rate", "紧急任务错失率", "urgent_miss_rate.svg"),
                ("conflict_count", "资源冲突次数", "conflict_count.svg"))

COLORS = ("#2f6f9f", "#e08b3a", "#6aa84f", "#a2599b", "#c0504d")
KIND_TITLES = {"normal": "普通负载", "crowded": "台面拥堵",
               "urgent": "紧急密集", "fault": "故障强度"}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value):
    if value in ("", None):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["workload"], row["policy"])].append(row)
    summary = []
    for (kind, policy), items in sorted(groups.items()):
        entry = {"workload": kind, "policy": policy, "n": len(items)}
        for field in SUMMARY_FIELDS:
            values = [number(item.get(field)) for item in items]
            values = [value for value in values if value is not None]
            entry[f"{field}_mean"] = round(statistics.mean(values), 4) if values else None
            entry[f"{field}_std"] = round(statistics.stdev(values), 4) if len(values) > 1 else (
                0.0 if values else None)
            entry[f"{field}_n"] = len(values)
        summary.append(entry)
    return summary


def write_chart(path: Path, field: str, label: str, policies, kinds, summary):
    width, height = 880, 380
    left, right, top, bottom = 70, 30, 60, 70
    plot_w, plot_h = width - left - right, height - top - bottom
    values = {}
    for kind in kinds:
        for policy in policies:
            for entry in summary:
                if entry["workload"] == kind and entry["policy"] == policy:
                    values[(kind, policy)] = entry.get(f"{field}_mean")
    known = [v for v in values.values() if v is not None]
    top_value = max(known) if known else 1.0
    scale_max = top_value * 1.15 if top_value > 0 else 1.0

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="Noto Sans CJK SC, Microsoft YaHei, sans-serif">',
             f'<rect width="{width}" height="{height}" fill="#fbfaf7"/>',
             f'<text x="{width / 2}" y="26" text-anchor="middle" font-size="17" fill="#22303c">{label}（按负载分组，均值）</text>',
             f'<text x="{width / 2}" y="46" text-anchor="middle" font-size="11" fill="#6b7b8a">横轴：四类实验负载　纵轴：{label}　柱：五种策略</text>',
             f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#c9d2da"/>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#c9d2da"/>']
    for tick in range(5):
        value = scale_max * tick / 4
        y = top + plot_h - plot_h * tick / 4
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#e6ebef"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="#6b7b8a">{value:.2f}</text>')
    group_w = plot_w / len(kinds)
    bar_w = group_w / (len(policies) + 1)
    for gi, kind in enumerate(kinds):
        base_x = left + gi * group_w + bar_w * 0.5
        for pi, policy in enumerate(policies):
            value = values.get((kind, policy)) or 0.0
            h = plot_h * value / scale_max if scale_max else 0
            x = base_x + pi * bar_w
            y = top + plot_h - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w * 0.86:.1f}" height="{h:.1f}" '
                         f'fill="{COLORS[pi % len(COLORS)]}" rx="2"/>')
            if value:
                parts.append(f'<text x="{x + bar_w * 0.43:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
                             f'font-size="9" fill="#41505c">{value:.2f}</text>')
        parts.append(f'<text x="{left + gi * group_w + group_w / 2:.1f}" y="{top + plot_h + 20}" '
                     f'text-anchor="middle" font-size="12" fill="#22303c">{KIND_TITLES.get(kind, kind)}</text>')
    for pi, policy in enumerate(policies):
        x = left + pi * 150
        parts.append(f'<rect x="{x}" y="{height - 28}" width="12" height="12" fill="{COLORS[pi % len(COLORS)]}"/>')
        parts.append(f'<text x="{x + 18}" y="{height - 18}" font-size="11" fill="#41505c">{policy}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="汇总实验指标并生成 SVG 图")
    parser.add_argument("--results", default=str(ROOT / "experiments" / "results"))
    parser.add_argument("--figures", default=str(ROOT / "experiments" / "figures"))
    args = parser.parse_args(argv)

    results = Path(args.results)
    figures = Path(args.figures)
    figures.mkdir(parents=True, exist_ok=True)
    rows = read_rows(results / "metrics.csv")
    summary = summarize(rows)
    policies = sorted({row["policy"] for row in rows},
                      key=lambda name: ["baseline", "fcfs", "no_dynamic",
                                        "non_preemptive", "no_deadlock"].index(name)
                      if name in ("baseline", "fcfs", "no_dynamic", "non_preemptive", "no_deadlock")
                      else 99)
    kinds = [kind for kind in ("normal", "crowded", "urgent", "fault")
             if any(row["workload"] == kind for row in rows)]

    keys = ["workload", "policy", "n"] + [f"{field}_{suffix}" for field in SUMMARY_FIELDS
                                          for suffix in ("mean", "std", "n")]
    with (results / "summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary)
    (results / "summary.json").write_text(
        json.dumps({"policies": policies, "kinds": kinds, "rows": summary},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    for field, label, name in CHART_FIELDS:
        write_chart(figures / name, field, label, policies, kinds, summary)

    print(f"样本 {len(rows)} 行，汇总 {len(summary)} 组；图见 {figures}")
    for entry in summary:
        if entry["policy"] == "baseline":
            print(f"{entry['workload']:8s} baseline 完成率={entry['completion_rate_mean']} "
                  f"时延={entry['average_completion_delay_mean']} "
                  f"紧急错失={entry['urgent_task_miss_rate_mean']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
