#!/usr/bin/env python3
"""
Generate an HTML report comparing three models (deepseek, mistral, gemma)
using the aggregated CSV and per-commit CSVs available in the workspace.
Saves output to output/analysis_three_models/report.html

Dependencies: pandas, plotly

Run: python3 scripts/generate_three_model_report.py
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
CSV_AGG = ROOT / 'csv' / 'llm_analysis_aggregated.csv'
JSON_AGG = ROOT / 'output' / 'llm_purity_aggregated.json'
OUT_DIR = ROOT / 'output' / 'analysis_three_models'
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_HTML = OUT_DIR / 'report.html'

# model keys / filenames mapping (expecting these exist)
MODEL_FILES = {
    'deepseek': {
        'agg_key': 'deepseek-r1_8b_floss_hashes_no_rpt_purity_with_analysis',
        'csv': ROOT / 'csv' / 'llm_analysis_csv' / 'deepseek-r1_8b_floss_hashes_no_rpt_purity_with_analysis.csv'
    },
    'mistral': {
        'agg_key': 'mistral_latest_floss_hashes_no_rpt_purity_with_analysis',
        'csv': ROOT / 'csv' / 'llm_analysis_csv' / 'mistral_latest_floss_hashes_no_rpt_purity_with_analysis.csv'
    },
    'gemma': {
        'agg_key': 'gemma2_2b_floss_hashes_no_rpt_purity_with_analysis',
        'csv': ROOT / 'csv' / 'llm_analysis_csv' / 'gemma2_2b_floss_hashes_no_rpt_purity_with_analysis.csv'
    }
}

# load aggregated CSV
agg = pd.read_csv(CSV_AGG)

# load aggregated JSON for confusion details if available
json_data = {}
if JSON_AGG.exists():
    with open(JSON_AGG, 'r') as f:
        json_data = json.load(f)

# helper: extract agg row for a model key
def get_agg_row_for_key(key):
    row = agg[agg['model'].str.contains(key.split('_floss')[0], regex=False)]
    if len(row) == 0:
        # fallback: match full key
        row = agg[agg['model'] == key]
    return row.iloc[0] if len(row)>0 else None

# Build a summary table for the three models
summary_rows = []
per_commit_dfs = {}
for short, info in MODEL_FILES.items():
    agg_key = info['agg_key']
    row = get_agg_row_for_key(agg_key)
    analyzed = int(row['analyzed_by_model']) if row is not None else 0
    total = int(row['total_commits_in_file']) if row is not None else 0
    purity_true = int(row['purity_true']) if row is not None else 0
    purity_false = int(row['purity_false']) if row is not None else 0
    llm_true = int(row['llm_true']) if row is not None else 0
    llm_false = int(row['llm_false']) if row is not None else 0
    agreement_true_total = int(row['agreement_true_total']) if row is not None else 0
    agreement_true_agree = int(row['agreement_true_agree']) if row is not None else 0
    agreement_false_total = int(row['agreement_false_total']) if row is not None else 0
    agreement_false_agree = int(row['agreement_false_agree']) if row is not None else 0

    # read per-commit CSV if exists
    per_csv = info['csv']
    if per_csv.exists():
        df = pd.read_csv(per_csv)
        per_commit_dfs[short] = df
    else:
        per_commit_dfs[short] = None

    missing = total - analyzed

    summary_rows.append({
        'model': short,
        'agg_key': agg_key,
        'analyzed': analyzed,
        'total': total,
        'missing': missing,
        'purity_true': purity_true,
        'purity_false': purity_false,
        'llm_true': llm_true,
        'llm_false': llm_false,
        'agreement_true_total': agreement_true_total,
        'agreement_true_agree': agreement_true_agree,
        'agreement_false_total': agreement_false_total,
        'agreement_false_agree': agreement_false_agree
    })

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(OUT_DIR / 'summary_three_models.csv', index=False)

# For commits statuses (FLOSS/PURE/FAILED/NONE/etc) compute breakdowns from per-commit CSVs
status_breakdown = {}
for short, df in per_commit_dfs.items():
    if df is None:
        status_breakdown[short] = None
        continue
    # df expected columns: hash,purity_analysis,llm_analysis
    # normalize llm_analysis strings and fill NaN with 'NONE'
    s = df['llm_analysis'].fillna('NONE').astype(str)
    counts = s.value_counts().to_dict()
    # also record how many of the failed/none rows are labeled by purity_analysis
    failed_mask = s == 'FAILED'
    none_mask = s == 'NONE'
    failed_by_purity = df.loc[failed_mask, 'purity_analysis'].fillna('UNKNOWN').value_counts().to_dict()
    none_by_purity = df.loc[none_mask, 'purity_analysis'].fillna('UNKNOWN').value_counts().to_dict()
    status_breakdown[short] = {
        'counts': {k: int(v) for k,v in counts.items()},
        'failed_by_purity': failed_by_purity,
        'none_by_purity': none_by_purity,
        'total_rows': len(df)
    }

# Create plots with Plotly and assemble into HTML
figs = []

# 1) Coverage bar
fig_cov = go.Figure()
fig_cov.add_trace(go.Bar(x=summary_df['model'], y=summary_df['analyzed'], name='analyzed'))
fig_cov.add_trace(go.Bar(x=summary_df['model'], y=summary_df['missing'], name='missing'))
fig_cov.update_layout(title='Coverage (analyzed vs missing) by model', barmode='stack')
figs.append(fig_cov)

# 2) LLM predictions distribution (llm_true vs llm_false)
fig_dist = go.Figure()
fig_dist.add_trace(go.Bar(x=summary_df['model'], y=summary_df['llm_true'], name='llm_true'))
fig_dist.add_trace(go.Bar(x=summary_df['model'], y=summary_df['llm_false'], name='llm_false'))
fig_dist.update_layout(title='LLM predictions (TRUE vs FALSE) by model', barmode='group')
figs.append(fig_dist)

# 3) Purity counts (from agg)
fig_purity = go.Figure()
fig_purity.add_trace(go.Bar(x=summary_df['model'], y=summary_df['purity_true'], name='purity_true'))
fig_purity.add_trace(go.Bar(x=summary_df['model'], y=summary_df['purity_false'], name='purity_false'))
fig_purity.update_layout(title='Dataset purity counts (TRUE vs FALSE) by model-key (dataset-level)', barmode='group')
figs.append(fig_purity)

# 4) For each model plot confusion matrix if available in json_data
for short, info in MODEL_FILES.items():
    key = info['agg_key']
    entry = json_data.get(key)
    if not entry:
        continue
    confusion = entry.get('confusion', {})
    # Build a simple confusion matrix table for TRUE/FALSE vs TRUE/FALSE
    # Some entries use keys as 'TRUE'/'FALSE' and nested counts
    labels = ['TRUE','FALSE']
    matrix = [[0,0],[0,0]]
    for i, gt in enumerate(labels):
        row = confusion.get(gt, {})
        for j, pred in enumerate(labels):
            matrix[i][j] = int(row.get(pred, 0))
    cm_fig = go.Figure(data=go.Heatmap(z=matrix, x=labels, y=labels, colorscale='Blues', text=matrix, texttemplate='%{text}'))
    cm_fig.update_layout(title=f'Confusion matrix for {short} (ground truth rows)')
    figs.append(cm_fig)

# (old missing_breakdown logic removed; status_breakdown will be used below)

# assemble HTML
html_parts = [f"<h1>Three-model analysis report</h1>", f"<p>Generated by scripts/generate_three_model_report.py</p>"]
html_parts.append('<h2>Summary</h2>')
html_parts.append(summary_df.to_html(index=False))

html_parts.append('<h2>Coverage & Predictions</h2>')
# embed plots
for i, fig in enumerate(figs):
    div = fig.to_html(full_html=False, include_plotlyjs=(i==0))
    html_parts.append(div)

html_parts.append('<h2>LLM analysis status breakdown (FLOSS / PURE / FAILED / NONE)</h2>')
for short, info in status_breakdown.items():
    if info is None:
        html_parts.append(f"<h4>{short}</h4><p>No per-commit CSV available.</p>")
        continue
    counts = info['counts']
    rows = ''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in counts.items())
    html_parts.append(f"<h4>{short} — total rows: {info['total_rows']}</h4><table border=1><tr><th>llm_analysis</th><th>count</th></tr>{rows}</table>")
    # failed_by_purity
    fb = info.get('failed_by_purity', {})
    if fb:
        rows2 = ''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in fb.items())
        html_parts.append(f"<h5>{short} — FAILED rows by purity_analysis</h5><table border=1><tr><th>purity_analysis</th><th>count</th></tr>{rows2}</table>")
    nb = info.get('none_by_purity', {})
    if nb:
        rows3 = ''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in nb.items())
        html_parts.append(f"<h5>{short} — NONE rows by purity_analysis</h5><table border=1><tr><th>purity_analysis</th><th>count</th></tr>{rows3}</table>")

# Save HTML
# Versioning: if report exists, move it to a timestamped backup before writing
if OUT_HTML.exists():
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup = OUT_DIR / f'report.{ts}.html'
    shutil.move(str(OUT_HTML), str(backup))
    print('Existing report moved to', backup)

with open(OUT_HTML, 'w') as f:
    f.write('\n'.join(html_parts))

print('Report written to', OUT_HTML)
print('Summary CSV written to', OUT_DIR / 'summary_three_models.csv')
print('Done')
