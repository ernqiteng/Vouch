"""Measure extract_claims() against the hand-labelled eval set.

Run from backend/ (one Gemini call per case):
    python -m evals.run_claims_eval
    python -m evals.run_claims_eval --delay 5 --limit 10
    python -m evals.run_claims_eval --only peg_synonym,wav_bio
    python -m evals.run_claims_eval --price-in 0.30 --price-out 2.50   # $ per 1M tokens

A prediction counts as correct when its (competency, source) pair is in the
case's expected list. Snippets aren't scored: extract_claims() already drops
any claim whose snippet isn't really in the text. Cases where every model
failed are reported separately and left out of precision/recall, so a busy
API doesn't look like bad extraction.
"""
import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from llm import extract_claims
from seed_competencies import COMPETENCIES

HERE = Path(__file__).parent


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def f1(precision: float | None, recall: float | None) -> float | None:
    if not precision or not recall:
        return 0.0 if precision is not None and recall is not None else None
    return round(2 * precision * recall / (precision + recall), 3)


def percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


def run(
    delay: float,
    limit: int | None,
    only: list[str] | None,
    price_in: float | None,
    price_out: float | None,
) -> dict:
    cases = json.loads((HERE / "claims_eval.json").read_text(encoding="utf-8"))["cases"]
    if only:
        unknown = set(only) - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"Unknown case ids: {sorted(unknown)}")
        cases = [c for c in cases if c["id"] in only]
    if limit:
        cases = cases[:limit]
    competencies = dict(COMPETENCIES)

    per_case, failed = [], []
    tp = fp = fn = 0
    by_competency: dict[str, Counter] = defaultdict(Counter)
    latencies, prompt_tokens, output_tokens, models = [], [], [], Counter()

    for i, case in enumerate(cases, 1):
        if i > 1 and delay:
            time.sleep(delay)  # stay under the free tier's requests-per-minute limit
        claims, ok, stats = extract_claims(case["bio"], case["document"], competencies)
        if stats.attempts:
            latencies.append(stats.latency_ms)
        if not ok:
            failed.append(case["id"])
            print(f"[{i:>2}/{len(cases)}] {case['id']}: FAILED (every model errored)")
            continue

        models[stats.model] += 1
        if stats.prompt_tokens is not None:
            prompt_tokens.append(stats.prompt_tokens)
            output_tokens.append(stats.output_tokens or 0)

        expected = {tuple(pair) for pair in case["expected"]}
        predicted = {(c.competency, c.source.value) for c in claims}
        hits, extra, missed = expected & predicted, predicted - expected, expected - predicted
        tp, fp, fn = tp + len(hits), fp + len(extra), fn + len(missed)
        for code, _ in hits:
            by_competency[code]["tp"] += 1
        for code, _ in extra:
            by_competency[code]["fp"] += 1
        for code, _ in missed:
            by_competency[code]["fn"] += 1

        mark = "ok  " if not extra and not missed else "MISS"
        print(f"[{i:>2}/{len(cases)}] {mark} {case['id']}"
              + (f"  extra={sorted(extra)}" if extra else "")
              + (f"  missed={sorted(missed)}" if missed else ""))
        per_case.append({
            "id": case["id"], "tests": case["tests"], "model": stats.model,
            "latency_ms": stats.latency_ms, "expected": sorted(expected),
            "predicted": sorted(predicted), "false_positives": sorted(extra),
            "false_negatives": sorted(missed),
            "snippets": [c.model_dump(mode="json") for c in claims],
        })

    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    summary = {
        "cases_total": len(cases),
        "cases_scored": len(per_case),
        "cases_failed": failed,
        "cases_perfect": sum(1 for c in per_case if not c["false_positives"] and not c["false_negatives"]),
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": precision, "recall": recall, "f1": f1(precision, recall),
        "latency_ms": {
            "mean": round(statistics.mean(latencies)) if latencies else None,
            "p50": percentile(latencies, 50), "p95": percentile(latencies, 95),
            "max": max(latencies) if latencies else None,
        },
        "tokens_per_call": {
            "prompt_mean": round(statistics.mean(prompt_tokens)) if prompt_tokens else None,
            "output_mean": round(statistics.mean(output_tokens)) if output_tokens else None,
        },
        "models_used": dict(models),
    }
    if price_in is not None and price_out is not None and prompt_tokens:
        summary["estimated_cost_per_verification_usd"] = round(
            statistics.mean(prompt_tokens) / 1e6 * price_in
            + statistics.mean(output_tokens) / 1e6 * price_out, 6)

    competency_scores = {}
    for code, c in sorted(by_competency.items()):
        p, r = ratio(c["tp"], c["tp"] + c["fp"]), ratio(c["tp"], c["tp"] + c["fn"])
        competency_scores[code] = {"tp": c["tp"], "fp": c["fp"], "fn": c["fn"], "precision": p, "recall": r}

    return {"run_at": datetime.now().isoformat(timespec="seconds"), "summary": summary,
            "by_competency": competency_scores, "cases": per_case}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--delay", type=float, default=4.0, help="seconds between calls (default 4)")
    parser.add_argument("--limit", type=int, help="only run the first N cases")
    parser.add_argument("--only", help="comma-separated case ids to run, e.g. to retry failures")
    parser.add_argument("--price-in", type=float, help="$ per 1M input tokens, for a cost estimate")
    parser.add_argument("--price-out", type=float, help="$ per 1M output tokens, for a cost estimate")
    args = parser.parse_args()

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    result = run(args.delay, args.limit, only, args.price_in, args.price_out)
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"claims-{datetime.now():%Y%m%d-%H%M%S}.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

    s = result["summary"]
    print("\n=== Claim extraction eval ===")
    print(f"Cases: {s['cases_scored']} scored, {len(s['cases_failed'])} failed, "
          f"{s['cases_perfect']} perfect")
    print(f"Precision {s['precision']}  Recall {s['recall']}  F1 {s['f1']}  "
          f"(TP {s['true_positives']}, FP {s['false_positives']}, FN {s['false_negatives']})")
    print(f"Latency ms: mean {s['latency_ms']['mean']}, p50 {s['latency_ms']['p50']}, "
          f"p95 {s['latency_ms']['p95']}, max {s['latency_ms']['max']}")
    print(f"Tokens per call: {s['tokens_per_call']['prompt_mean']} in, "
          f"{s['tokens_per_call']['output_mean']} out")
    if "estimated_cost_per_verification_usd" in s:
        print(f"Estimated cost per verification: ${s['estimated_cost_per_verification_usd']}")
    print(f"Models used: {s['models_used']}")
    print(f"Saved to {out_file}")


if __name__ == "__main__":
    main()
