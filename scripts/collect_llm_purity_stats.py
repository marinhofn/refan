#!/usr/bin/env python3
"""
Collect LLM purity statistics from csv/llm_analysis_csv and write aggregated outputs.

Outputs:
 - csv/llm_analysis_aggregated.csv : per-model aggregated metrics (one row per model)
 - output/llm_purity_aggregated.json : detailed per-model breakdown and confusion matrices

This script is idempotent: run it anytime and it will update the outputs.
"""
import csv
import json
import os
from collections import defaultdict, Counter
from pathlib import Path
import argparse


def normalize_label(l):
    if l is None:
        return None
    s = str(l).strip().upper()
    if s in ("TRUE", "T", "1", "PURE"):
        return "TRUE"
    if s in ("FALSE", "F", "0", "FLOSS"):
        return "FALSE"
    if s in ("NONE", "", "NA", "NAN"):
        return None
    # fallback: if contains PURE or TRUE
    if "PURE" in s:
        return "TRUE"
    if "FLOSS" in s or "FALSE" in s:
        return "FALSE"
    return s


def read_csv_file(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def analyze_folder(folder):
    folder = Path(folder)
    results = {}
    for p in sorted(folder.glob("*.csv")):
        name = p.stem
        # use file stem as model id (may include dataset name)
        rows = read_csv_file(p)
        total = 0
        analyzed = 0
        purity_counts = Counter()
        llm_counts = Counter()
        # confusion: purity_tool x llm_label
        confusion = defaultdict(Counter)

        for r in rows:
            total += 1
            purity_raw = r.get("purity_analysis") or r.get("purity") or r.get("purity_tool")
            llm_raw = r.get("llm_analysis") or r.get("model_label") or r.get("llm")
            purity = normalize_label(purity_raw)
            llm = normalize_label(llm_raw)

            if llm is not None:
                analyzed += 1
                llm_counts[llm] += 1
            if purity is not None:
                purity_counts[purity] += 1

            # record confusion only when at least one of labels present
            confusion[purity][llm] += 1

        # compute agreement metrics: for TRUE and FALSE, compare counts
        agreement = {}
        for truth in ("TRUE", "FALSE"):
            truth_total = purity_counts.get(truth, 0)
            if truth_total == 0:
                agreement[truth] = {"total": 0, "agree": 0, "disagree": 0}
                continue
            agree = confusion[truth].get(truth, 0)
            # disagree counts are all other llm labels (including None)
            disagree = truth_total - agree
            agreement[truth] = {"total": truth_total, "agree": agree, "disagree": disagree}

        results[name] = {
            "file": str(p),
            "total_commits_in_file": total,
            "analyzed_by_model": analyzed,
            "purity_counts": dict(purity_counts),
            "llm_counts": dict(llm_counts),
            "confusion": {k if k is not None else "NONE": dict(v) for k, v in confusion.items()},
            "agreement": agreement,
        }

    return results


def write_aggregated_csv(results, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model",
        "file",
        "total_commits_in_file",
        "analyzed_by_model",
        "purity_true",
        "purity_false",
        "llm_true",
        "llm_false",
        "agreement_true_total",
        "agreement_true_agree",
        "agreement_true_disagree",
        "agreement_false_total",
        "agreement_false_agree",
        "agreement_false_disagree",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for model, data in sorted(results.items()):
            row = {
                "model": model,
                "file": data["file"],
                "total_commits_in_file": data["total_commits_in_file"],
                "analyzed_by_model": data["analyzed_by_model"],
                "purity_true": data["purity_counts"].get("TRUE", 0),
                "purity_false": data["purity_counts"].get("FALSE", 0),
                "llm_true": data["llm_counts"].get("TRUE", 0),
                "llm_false": data["llm_counts"].get("FALSE", 0),
                "agreement_true_total": data["agreement"]["TRUE"]["total"],
                "agreement_true_agree": data["agreement"]["TRUE"]["agree"],
                "agreement_true_disagree": data["agreement"]["TRUE"]["disagree"],
                "agreement_false_total": data["agreement"]["FALSE"]["total"],
                "agreement_false_agree": data["agreement"]["FALSE"]["agree"],
                "agreement_false_disagree": data["agreement"]["FALSE"]["disagree"],
            }
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Collect LLM purity stats from csv/llm_analysis_csv")
    parser.add_argument("--input-dir", default="csv/llm_analysis_csv", help="Folder with per-model CSVs")
    parser.add_argument("--out-csv", default="csv/llm_analysis_aggregated.csv", help="Aggregated CSV output")
    parser.add_argument("--out-json", default="output/llm_purity_aggregated.json", help="Aggregated JSON output")
    args = parser.parse_args()

    results = analyze_folder(args.input_dir)

    # write JSON
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    write_aggregated_csv(results, args.out_csv)

    print(f"Wrote aggregated CSV: {args.out_csv}")
    print(f"Wrote aggregated JSON: {args.out_json}")


if __name__ == "__main__":
    main()
