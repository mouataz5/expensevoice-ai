"""Evaluate the voice-purchase decision layer.

Each case has a transcript, a model output and the route a careful reviewer would
expect. Two modes:

  replay (default)  feed each case's recorded_model_output through the real parser,
                    grounding check and quality gate. Deterministic, no API key,
                    runs in CI. The outputs are hand-written to reproduce failure
                    modes seen with LLM extraction (invented numbers, swapped
                    digits, schema violations, wrong categories, prose around JSON).
  --live            call the configured provider (LLM_PROVIDER + its API key) for
                    each transcript instead, to measure the model and the gate together.

Two systems are compared on the same cases:

  baseline  trust the model: a parsed answer is "ready" when its self-reported
            confidence is >= 0.7 (what the pipeline effectively did before the gate)
  gate      app.agent.quality_gate.evaluate_extraction

Metrics:
  route_accuracy      share of cases routed as expected
  unsafe_pass_rate    of the cases that need a human look, the share routed "ready"
                      (primary safety metric: a wrong number reaches the books unflagged)
  false_alarm_rate    of the cases expected "ready", the share flagged anyway (review cost)

Usage:
  python -m evals.voice_purchase.run_eval              # from backend/
  python -m evals.voice_purchase.run_eval --live
  python -m evals.voice_purchase.run_eval --write-report
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from app.agent.output_parsing import ExtractionOutputError, parse_extraction
from app.agent.quality_gate import MIN_MODEL_CONFIDENCE, evaluate_extraction
from app.schemas.extraction import ExtractedPurchase

HERE = Path(__file__).parent
CASES_PATH = HERE / "cases.jsonl"
REPORT_PATH = HERE / "RESULTS.md"

# Matches the default categories policy (app/core/policy_defaults.py).
ALLOWED = [
    "vente_poussins",
    "vente_nourriture",
    "charge_fixe_location",
    "charge_fixe_salaires",
    "charge_fixe_abonnement",
    "charge_variable_eau",
    "charge_variable_electricite",
    "charge_variable_medicaments",
    "charge_variable_transport",
    "charge_variable_autre",
]
MAX_PER_PURCHASE = 500.0


@dataclass
class CaseResult:
    id: str
    expected: str
    baseline: str
    gate: str
    gate_reasons: list[str]
    note: str


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _parse(raw: str) -> tuple[ExtractedPurchase | None, str | None]:
    try:
        return parse_extraction(raw, ALLOWED), None
    except ExtractionOutputError as e:
        return None, e.reason


def baseline_route(transcript: str, extracted: ExtractedPurchase | None) -> str:
    if not transcript.strip() or extracted is None:
        return "manual_entry"
    return "ready" if extracted.confidence >= MIN_MODEL_CONFIDENCE else "needs_attention"


def evaluate_case(case: dict, extracted: ExtractedPurchase | None, error: str | None) -> CaseResult:
    decision = evaluate_extraction(
        transcript=case["transcript"],
        extracted=extracted,
        stt_confidence=case.get("stt_confidence"),
        extraction_error=error,
        max_per_purchase=MAX_PER_PURCHASE,
    )
    return CaseResult(
        id=case["id"],
        expected=case["expected_route"],
        baseline=baseline_route(case["transcript"], extracted),
        gate=decision.route,
        gate_reasons=decision.reasons,
        note=case.get("note", ""),
    )


async def _live_extract(case: dict) -> tuple[ExtractedPurchase | None, str | None]:
    from app.services.extraction import extract_purchase_fields

    if not case["transcript"].strip():
        return None, "empty_transcript"
    try:
        return await extract_purchase_fields(case["transcript"], "buy", ALLOWED), None
    except ExtractionOutputError as e:
        return None, e.reason
    except Exception as e:  # provider errors are part of what a live run measures
        return None, f"provider_error:{type(e).__name__}"


def run(live: bool = False, cases: list[dict] | None = None) -> list[CaseResult]:
    results = []
    for case in cases or load_cases():
        if live:
            extracted, error = asyncio.run(_live_extract(case))
        else:
            extracted, error = _parse(case["recorded_model_output"])
        results.append(evaluate_case(case, extracted, error))
    return results


def metrics(results: list[CaseResult], system: str) -> dict[str, float]:
    def route(r: CaseResult) -> str:
        return getattr(r, system)

    needs_human = [r for r in results if r.expected != "ready"]
    expected_ready = [r for r in results if r.expected == "ready"]
    return {
        "route_accuracy": sum(route(r) == r.expected for r in results) / len(results),
        "unsafe_pass_rate": (
            sum(route(r) == "ready" for r in needs_human) / len(needs_human) if needs_human else 0.0
        ),
        "false_alarm_rate": (
            sum(route(r) != "ready" for r in expected_ready) / len(expected_ready) if expected_ready else 0.0
        ),
    }


def render_report(results: list[CaseResult], mode: str) -> str:
    base, gate = metrics(results, "baseline"), metrics(results, "gate")
    lines = [
        "# Voice purchase eval results",
        "",
        f"Mode: **{mode}** · {len(results)} cases · generated by `python -m evals.voice_purchase.run_eval --write-report`",
        "",
        "| Metric | Baseline (trust model confidence) | Quality gate |",
        "|---|---|---|",
    ]
    for key in ("route_accuracy", "unsafe_pass_rate", "false_alarm_rate"):
        lines.append(f"| {key} | {base[key]:.0%} | {gate[key]:.0%} |")
    lines += ["", "| Case | Expected | Baseline | Gate | Gate reasons | What it tests |", "|---|---|---|---|---|---|"]
    for r in results:
        mark = "" if r.gate == r.expected else " ❌"
        lines.append(
            f"| `{r.id}` | {r.expected} | {r.baseline} | {r.gate}{mark} | {', '.join(r.gate_reasons)} | {r.note} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="call the configured LLM provider")
    parser.add_argument("--write-report", action="store_true", help=f"write {REPORT_PATH.name}")
    args = parser.parse_args(argv)

    mode = "live" if args.live else "replay"
    results = run(live=args.live)
    report = render_report(results, mode)
    print(report)
    if args.write_report:
        REPORT_PATH.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
