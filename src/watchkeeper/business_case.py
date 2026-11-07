"""Business case for one retrofitted pump, built from our MEASURED benchmark metrics and clearly labelled assumptions.

  python -m watchkeeper.business_case          # writes docs/business_case.md

The arithmetic follows the organizers' worked example (`examples/business_case.py`, MIT). Measured inputs come from
eval/results/WK_causal_learned/metrics.json (leave-one-asset-out on synthetic data). Every money input is an assumption, so the
result is a worked example of the logic, not a promise of saving at any real site.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
METRICS = ROOT / "eval" / "results" / "WK_causal_learned" / "metrics.json"
PER_EVENT = ROOT / "eval" / "results" / "WK_causal_learned" / "per_event_loo.csv"
OUT = ROOT / "docs" / "business_case.md"

# Assumptions (same values as the organizers' example unless noted). Sources: RETROFIT_FEASIBILITY.md sections 2 and 5.
ASSUME = {
    "events_per_year": (0.6, "1/yr", "developing faults per duty pump that would otherwise end in an unplanned stop"),
    "unplanned_stop_h": (10.0, "h", "detection by failure, diagnosis, parts, repair"),
    "planned_stop_h": (3.0, "h", "the same work prepared and done in a planned window"),
    "downtime_cost_eur_h": (1500.0, "EUR/h", "production loss of a mid-size line with no redundant pump"),
    "repair_unplanned_eur": (9000.0, "EUR", "within a typical EUR 3-15 k pump overhaul range (itself an estimate)"),
    "repair_planned_eur": (4000.0, "EUR", "damage limited when caught early"),
    "false_alert_cost_eur": (120.0, "EUR", "about 1.5 h of technician time to check one false alert"),
    "repeat_alert_cost_eur": (30.0, "EUR", "a repeat on a problem already known is a glance, not a check (our assumption)"),
    "capex_eur": (4500.0, "EUR", "BOM option B about EUR 2.1-2.4 k from list prices plus cabling, enclosure and installation"),
    "opex_eur_yr": (700.0, "EUR/yr", "connectivity, software maintenance, battery and sensor replacement"),
}
LEVELS = {  # installed cost per retrofit level, EUR (assumptions built from list prices in RETROFIT_FEASIBILITY.md)
    "Level 0: existing signals only (edge box + read-only integration)": 2000.0,
    "Level 1: + suction pressure transmitter + wireless vibration point": 3500.0,
    "Level 2: wired vibration, power and flow metering (option A/B)": 4500.0,
}
SITES = [("Ship seawater pump with a healthy standby", 0.0, 0.3), ("Cooling-tower circulation pump", 400.0, 0.6),
         ("Hot process-water transfer pump", 600.0, 0.6), ("Process pump with no redundancy (organizers' example)", 1500.0, 0.6)]


def evaluate(p: dict) -> dict:
    """`caught` is the share of developing faults found early enough to be planned. Alerts split into false episodes and repeats."""
    caught = p["events_per_year"] * p["caught"]
    benefit = caught * ((p["unplanned_stop_h"] - p["planned_stop_h"]) * p["downtime_cost_eur_h"] + p["repair_unplanned_eur"] - p["repair_planned_eur"])
    nuisance = 365 * (p["false_per_day"] * p["false_alert_cost_eur"] + p["repeat_per_day"] * p["repeat_alert_cost_eur"])
    net = benefit - nuisance - p["opex_eur_yr"]
    return {"benefit": benefit, "nuisance": nuisance, "net": net, "payback_yr": p["capex_eur"] / net if net > 0 else float("inf")}


def _fmt_yr(x: float) -> str:
    return "never" if x == float("inf") else f"{x:.1f} yr"


def _bisect(fn, lo: float, hi: float, target: float) -> float:
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fn(mid) < target else (lo, mid)
    return hi


def build(metrics_path: Path = METRICS, per_event_path: Path = PER_EVENT, assets_path: Path | None = None, source: str = "leave-one-asset-out on the public pumps") -> str:
    m = json.loads(metrics_path.read_text(encoding="utf-8"))["leave_one_asset_out"]
    pe = pd.read_csv(per_event_path)
    days = m["asset_days"]
    n_false, n_rep = m["false_alert_episodes"], m["excess_repeat_episodes"]
    early = m["early_warning_rate"]
    dl = pe[pe.lead_time_to_deadline_h.notna()]
    leads = sorted(dl[dl.lead_time_to_deadline_h > 0].lead_time_to_deadline_h)
    n_dead, n_early = len(dl), len(leads)
    base = {k: v[0] for k, v in ASSUME.items()}
    base.update(caught=early, false_per_day=n_false / days, repeat_per_day=n_rep / days)
    org = dict(base, false_per_day=m["false_alerts_per_asset_day"], repeat_per_day=0.0, false_alert_cost_eur=120.0)      # organizers' convention
    r, r_org = evaluate(base), evaluate(org)

    L = ["# Business case for one retrofitted pump (synthetic scenario)", "",
         f"Every money figure is an assumption. The detection figures are measured on the synthetic benchmark ({source}). "
         "This shows how the numbers combine, not a saving at any real site.", "",
         "## Measured inputs", "",
         "| Measure | Value | Meaning |", "|---|---|---|",
         f"| Event recall | {m['event_recall']:.2f} | share of the {m['events_scored']} scored events that received an alert in their window |",
         f"| Found before the conventional alarm limit | **{early:.2f}** | of the events that ever reach a limit ({n_dead} of {len(pe)}), {n_early} were caught before it |",
         f"| False-alert episodes per pump-day | {n_false / days:.3f} | {n_false} episodes over {days:.0f} pump-days |",
         f"| Repeat alerts beyond the free reminder per pump-day | {n_rep / days:.3f} | {n_rep} repeats on problems already flagged |",
         "", f"Lead time for the {n_early} events caught early: {', '.join(f'{x:.1f} h' for x in leads)}. Slow mechanical faults (bearing wear, imbalance, "
         "strainer clogging) give hours to days of warning. Fast hydraulic episodes such as cavitation give almost none: the alert comes minutes after the "
         "limit, so there the value is the diagnosis, not the lead time.", "",
         "## Assumptions", "", "| Input | Value | Unit | Basis |", "|---|---|---|---|"]
    L += [f"| {k.replace('_', ' ')} | {v[0]:g} | {v[1]} | {v[2]} |" for k, v in ASSUME.items()]
    L += ["", "## Base case (no redundant pump, downtime EUR 1,500 per hour)", "",
          "| | Organizers' convention (all alerts cost EUR 120) | Refined (repeats cost EUR 30) |", "|---|---|---|",
          f"| Avoided downtime and repair per year | EUR {r_org['benefit']:,.0f} | EUR {r['benefit']:,.0f} |",
          f"| Alert handling per year | EUR {r_org['nuisance']:,.0f} | EUR {r['nuisance']:,.0f} |",
          f"| Operating cost per year | EUR {base['opex_eur_yr']:,.0f} | EUR {base['opex_eur_yr']:,.0f} |",
          f"| **Net per year** | **EUR {r_org['net']:,.0f}** | **EUR {r['net']:,.0f}** |",
          f"| Payback on EUR {base['capex_eur']:,.0f} | {_fmt_yr(r_org['payback_yr'])} | {_fmt_yr(r['payback_yr'])} |", ""]
    if r_org["net"] <= 0:
        L += ["**Reading.** At the current alert rate the base case is not positive under the organizers' convention. The cost of checking alerts "
              f"(EUR {r_org['nuisance']:,.0f} per year) is larger than the avoided cost (EUR {r_org['benefit']:,.0f}). Fewer false alerts and a higher share found before "
              "the limit are what turn it positive, and the sections below show how far each one has to move.", ""]
    L += ["## By type of site", "", "| Site | Downtime EUR/h | Faults/yr | Net EUR/yr (refined) | Payback |", "|---|---|---|---|---|"]
    for name, dt, ev in SITES:
        x = evaluate(dict(base, downtime_cost_eur_h=dt, events_per_year=ev))
        L.append(f"| {name} | {dt:,.0f} | {ev:g} | {x['net']:,.0f} | {_fmt_yr(x['payback_yr'])} |")
    L += ["", "A standby pump takes the downtime term to zero, so the case there rests on avoided repair cost, crew time and energy, and does not pay back "
          "on monitoring alone.", ""]

    # break-even
    be_dt = _bisect(lambda v: evaluate(dict(base, downtime_cost_eur_h=v))["net"], 0, 100000, base["capex_eur"] / 5)
    be_fa = _bisect(lambda v: -evaluate(dict(base, false_per_day=v))["net"], 0, 2.0, -base["capex_eur"] / 5)
    be_caught = _bisect(lambda v: evaluate(dict(base, caught=v))["net"], 0, 1.0, base["capex_eur"] / 5)
    L += ["## What has to move for a 5-year payback (refined convention, one input at a time)", "",
          f"- Downtime cost: about EUR {be_dt:,.0f} per hour (now {base['downtime_cost_eur_h']:,.0f}).",
          f"- False-alert episodes per pump-day: below {be_fa:.3f} (now {n_false / days:.3f}).",
          f"- Share found before the limit: {be_caught:.2f} (now {early:.2f}).", ""]

    # sensitivity
    L += ["## Sensitivity (refined convention)", "", "| Input | Low | High | Net EUR/yr low | Net EUR/yr high |", "|---|---|---|---|---|"]
    for key, lo, hi in (("events_per_year", 0.2, 1.2), ("caught", 0.3, 0.95), ("false_per_day", 0.0, 0.3), ("downtime_cost_eur_h", 0.0, 5000.0),
                        ("repair_unplanned_eur", 5000.0, 15000.0), ("capex_eur", 2000.0, 12000.0)):
        L.append(f"| {key.replace('_', ' ')} | {lo:g} | {hi:g} | {evaluate(dict(base, **{key: lo}))['net']:,.0f} | {evaluate(dict(base, **{key: hi}))['net']:,.0f} |")

    # retrofit levels with measured recall per instrumentation tier
    assets = pd.read_csv(assets_path or ROOT / "data" / "assets.csv")
    tier = dict(zip(assets.asset_id, assets.instrumentation_tier))
    pe["tier"] = pe.asset_id.map(tier)
    by = pe.groupby("tier").agg(events=("event_id", "count"), detected=("detected", "sum"), type_ok=("type_correct", "sum"))
    L += ["", "## What each retrofit level sees (measured on the same fleets)", "",
          "| Instrumentation | Installed cost (assumption) | Events | Detected | Right type |", "|---|---|---|---|---|"]
    for (name, capex), t in zip(LEVELS.items(), ("T0_LEGACY", "T1_RETROFIT", "T2_FULL")):
        row = by.loc[t] if t in by.index else None
        L.append(f"| {name} | EUR {capex:,.0f} | {int(row.events) if row is not None else 0} | {int(row.detected) if row is not None else 0} | {int(row.type_ok) if row is not None else 0} |")
    L += ["", "The levels see different mixes of faults on only 5 to 10 pumps each, so these counts show a direction and do not rank the levels; they do not show that more sensors detect less.", "",
          "## Honest limits", "",
          "- Synthetic data and assumed costs. Faults per year, downtime cost and repair cost drive the result more than the detector does.",
          f"- Only {n_dead} of the {len(pe)} events reach a conventional limit, so \"found before the limit\" rests on {n_dead} events ({n_early} caught).",
          "- The alert rate is the weakest number. Lowering false alerts is worth more than raising recall at this point.",
          "- No claim of certified safety, class approval or proven savings.", ""]
    return "\n".join(L)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = build()
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())


def summary(metrics_path: Path, per_event_path: Path) -> dict:
    """The same numbers as `build`, as data for the interface: measured inputs, base case under two conventions, and the four site types."""
    m = json.loads(metrics_path.read_text(encoding="utf-8"))["leave_one_asset_out"]
    pe = pd.read_csv(per_event_path)
    days, n_false, n_rep, early = m["asset_days"], m["false_alert_episodes"], m["excess_repeat_episodes"], m["early_warning_rate"]
    dl = pe[pe.lead_time_to_deadline_h.notna()]
    leads = sorted(float(x) for x in dl[dl.lead_time_to_deadline_h > 0].lead_time_to_deadline_h)
    base = {k: v[0] for k, v in ASSUME.items()}
    base.update(caught=early, false_per_day=n_false / days, repeat_per_day=n_rep / days)
    org = dict(base, false_per_day=m["false_alerts_per_asset_day"], repeat_per_day=0.0, false_alert_cost_eur=120.0)
    clean = lambda r: {k: (None if v == float("inf") else round(float(v), 1)) for k, v in r.items()}
    return {"measured": {"events": int(m["events_scored"]), "recall": round(float(m["event_recall"]), 3), "events_with_limit": int(len(dl)), "caught_before_limit": len(leads),
                         "lead_hours": [round(x, 1) for x in leads], "false_per_pump_day": round(n_false / days, 4), "repeat_per_pump_day": round(n_rep / days, 4),
                         "pump_days": round(float(days), 0)},
            "assumptions": {k: {"value": v[0], "unit": v[1], "basis": v[2]} for k, v in ASSUME.items()},
            "base": {"organizers_convention": clean(evaluate(org)), "refined": clean(evaluate(base))},
            "sites": [{"name": n, "downtime_eur_h": dt, "faults_per_year": ev, **clean(evaluate(dict(base, downtime_cost_eur_h=dt, events_per_year=ev)))} for n, dt, ev in SITES]}
