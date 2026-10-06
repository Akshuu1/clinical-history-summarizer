#!/usr/bin/env python3
"""
Evaluation script — compares pipeline output against hand-written gold summaries.

Usage:
  python scripts/evaluate.py

For each case in data/synthetic_notes/:
  1. Reads the raw note
  2. Calls the extraction pipeline directly (no HTTP — imports the service)
  3. Compares output to data/gold_summaries/case_N.json
  4. Computes precision/recall/F1 for allergies and current_medications (primary metrics)
  5. Checks for hallucination (any cited field not traceable to source)
  6. Writes reports/evaluation_report.json

This is the actual evaluation described in the project goals — not estimated numbers.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

from app.services.extractor import extract_summary_raw
from app.services.validator import validate_summary

console = Console()

NOTES_DIR = Path(__file__).parent.parent / "data" / "synthetic_notes"
GOLD_DIR = Path(__file__).parent.parent / "data" / "gold_summaries"
REPORT_PATH = Path(__file__).parent.parent / "reports" / "evaluation_report.json"


def normalise_name(name: str) -> str:
    """Lowercase, strip whitespace — for loose but consistent matching."""
    return name.lower().strip()


def compute_set_metrics(predicted: list[str], gold: list[str]) -> dict:
    """
    Compute precision, recall, F1 for a list-type field.
    Uses exact normalised string matching.
    """
    pred_set = {normalise_name(x) for x in predicted}
    gold_set = {normalise_name(x) for x in gold}

    if not gold_set and not pred_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}

    tp = len(pred_set & gold_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def run_case(case_file: Path) -> dict:
    """Run extraction on one case and evaluate against gold standard."""
    case_name = case_file.stem
    case_data = json.loads(case_file.read_text())
    
    raw_notes = case_data.get("raw_notes", "")
    gold = case_data.get("gold_summary", {})

    start = time.time()
    raw_summary, normalised_lines = extract_summary_raw(
        patient_id=case_name,
        raw_notes=raw_notes,
    )
    verified = validate_summary(raw_summary, normalised_lines)
    elapsed = time.time() - start

    # Extract predicted values (Updated schema fields)
    pred_allergies = [a.allergen for a in verified.allergies]
    pred_meds = [m.drug for m in verified.current_medications]

    # Extract gold values (Updated schema fields)
    gold_allergies = [a.get("allergen", "") for a in gold.get("allergies", [])]
    gold_meds = [m.get("drug", "") for m in gold.get("current_medications", [])]

    allergy_metrics = compute_set_metrics(pred_allergies, gold_allergies)
    med_metrics = compute_set_metrics(pred_meds, gold_meds)

    # Hallucination check
    has_unverified = bool(verified.unverified_fields)

    return {
        "case": case_name,
        "elapsed_seconds": round(elapsed, 2),
        "allergy_metrics": allergy_metrics,
        "medication_metrics": med_metrics,
        "unverified_fields": verified.unverified_fields,
        "has_unverified_fields": has_unverified,
        "predicted_allergies": pred_allergies,
        "gold_allergies": gold_allergies,
        "predicted_medications": pred_meds,
        "gold_medications": gold_meds,
    }


def aggregate(results: list[dict], field: str) -> dict:
    """Macro-average a metric field across all cases."""
    values = [r[field] for r in results]
    avg_precision = sum(v["precision"] for v in values) / len(values)
    avg_recall = sum(v["recall"] for v in values) / len(values)
    avg_f1 = sum(v["f1"] for v in values) / len(values)
    return {
        "macro_precision": round(avg_precision, 4),
        "macro_recall": round(avg_recall, 4),
        "macro_f1": round(avg_f1, 4),
    }


def main():
    console.print("\n[bold cyan]Clinical History Summarizer — Evaluation[/bold cyan]\n")

    TEST_DIR = Path(__file__).parent.parent / "data" / "test_cases"

    # Check gold files exist
    if not TEST_DIR.exists() or not any(TEST_DIR.iterdir()):
        console.print(
            "[red]ERROR: No generated test cases found in data/test_cases/[/red]\n"
            "You must generate them first with `make generate-cases`."
        )
        sys.exit(1)

    cases = sorted(TEST_DIR.glob("case_*.json"))
    if not cases:
        console.print("[red]ERROR: No case files found in data/test_cases/[/red]")
        sys.exit(1)

    results = []
    errors = []

    for case_file in cases:
        console.print(f"  Running [cyan]{case_file.stem}[/cyan]...", end=" ")
        try:
            result = run_case(case_file)
            results.append(result)
            uv = "⚠ " if result["has_unverified_fields"] else "✓ "
            console.print(
                f"{uv}allergy F1={result['allergy_metrics']['f1']:.2f} "
                f"med F1={result['medication_metrics']['f1']:.2f} "
                f"({result['elapsed_seconds']}s)"
            )
        except Exception as exc:
            errors.append({"case": case_file.stem, "error": str(exc)})
            console.print(f"[red]ERROR: {exc}[/red]")

    if not results:
        console.print("[red]No cases evaluated.[/red]")
        sys.exit(1)

    # Aggregate
    allergy_agg = aggregate(results, "allergy_metrics")
    med_agg = aggregate(results, "medication_metrics")

    # Print summary table
    table = Table(title="\nEvaluation Results (Macro-Average)", show_header=True)
    table.add_column("Field", style="bold")
    table.add_column("Precision", justify="right")
    table.add_column("Recall", justify="right")
    table.add_column("F1", justify="right")
    table.add_row(
        "Allergies",
        f"{allergy_agg['macro_precision']:.2%}",
        f"{allergy_agg['macro_recall']:.2%}",
        f"{allergy_agg['macro_f1']:.2%}",
    )
    table.add_row(
        "Current Medications",
        f"{med_agg['macro_precision']:.2%}",
        f"{med_agg['macro_recall']:.2%}",
        f"{med_agg['macro_f1']:.2%}",
    )
    console.print(table)

    # Unverified field rate
    unverified_count = sum(1 for r in results if r["has_unverified_fields"])
    console.print(
        f"\nCases with unverified fields: {unverified_count}/{len(results)} "
        f"({unverified_count/len(results):.0%})"
    )

    # Save report
    report = {
        "total_cases": len(results),
        "errored_cases": len(errors),
        "allergy_aggregate": allergy_agg,
        "medication_aggregate": med_agg,
        "unverified_field_rate": {
            "count": unverified_count,
            "total": len(results),
            "rate": round(unverified_count / len(results), 4),
        },
        "per_case_results": results,
        "errors": errors,
    }

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    console.print(f"\n[green]Report saved to:[/green] {REPORT_PATH}\n")


if __name__ == "__main__":
    main()
