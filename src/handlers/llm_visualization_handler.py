"""
Enhanced Visualization Handler for LLM vs Purity Analysis
Provides interactive dashboards comparing LLM and Purity classifications.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo
from datetime import datetime
import os
import json
import numpy as np
from collections import Counter
from typing import Dict, List, Tuple, Optional
import glob

class LLMVisualizationHandler:
    """Enhanced visualization handler for LLM vs Purity analysis results."""
    
    def __init__(self, csv_dir: str = "csv", analysis_dir: str = "analises"):
        self.csv_dir = csv_dir
        self.analysis_dir = analysis_dir
        self.color_palette = {
            'pure': '#2E8B57',      # Sea Green
            'floss': '#DC143C',     # Crimson
            'none': '#708090',      # Slate Gray
            'agreement': '#4CAF50', # Green
            'disagreement': '#F44336', # Red
            'primary': '#1f77b4',
            'secondary': '#ff7f0e',
            'tertiary': '#2ca02c'
        }
        
    def load_comparison_data(self, prefer_dual_classification: bool = False) -> pd.DataFrame:
        """Load the latest purity vs LLM comparison data."""
        
        # First try to load from hashes_no_rpt_purity_with_analysis.csv
        main_file = os.path.join(self.csv_dir, "hashes_no_rpt_purity_with_analysis.csv")
        if os.path.exists(main_file):
            print(f"Loading data from: {main_file}")
            
            df = pd.read_csv(main_file)
            
            # Filter only records that have both Purity and LLM analysis (fair comparison)
            df = df[(df['purity_analysis'].notna()) & (df['purity_analysis'] != '') & 
                   (df['llm_analysis'].notna()) & (df['llm_analysis'] != '') & 
                   (df['llm_analysis'] != 'FAILED')]
            
            print(f"Filtered to {len(df)} records with both Purity and LLM analysis")
            
            # Create standardized columns
            df['commit_hash'] = df['hash']
            df['purity_classification'] = df['purity_analysis'].replace({'TRUE': 'PURE', 'FALSE': 'FLOSS', 'NONE': 'UNKNOWN'})
            df['llm_classification'] = df['llm_analysis'].str.upper()
            
            # Add repository info (placeholder since not in this CSV)
            df['repository'] = 'multiple_repositories'
            df['project_name'] = 'mixed'
            
            # Create agreement column
            df['agreement'] = df['purity_classification'] == df['llm_classification']
            
            return df
        
        # Fallback to dual classification data if available
        if prefer_dual_classification:
            dual_pattern = os.path.join(self.csv_dir, "dual_classification_comparison_*.csv")
            dual_files = glob.glob(dual_pattern)
            
            if dual_files:
                latest_dual_file = max(dual_files, key=os.path.getctime)
                print(f"Loading dual classification data from: {latest_dual_file}")
                
                df = pd.read_csv(latest_dual_file)
                
                # Data already has proper format and agreement column
                # Normalize classifications and handle NaN values
                df['purity_classification'] = df['purity_classification'].fillna('UNKNOWN').str.upper()
                df['llm_classification'] = df['llm_classification'].fillna('UNKNOWN').str.upper()
                
                # Ensure agreement column exists
                if 'agreement' not in df.columns:
                    df['agreement'] = df['purity_classification'] == df['llm_classification']
                
                return df
        
        # Fallback to original comparison files
        pattern = os.path.join(self.csv_dir, "purity_llm_comparison_*.csv")
        files = glob.glob(pattern)
        
        if not files:
            raise FileNotFoundError("No comparison files found")
            
        # Get the most recent file
        latest_file = max(files, key=os.path.getctime)
        print(f"Loading comparison data from: {latest_file}")
        
        df = pd.read_csv(latest_file)
        
        # Normalize classifications and handle NaN values
        df['purity_classification'] = df['purity_classification'].fillna('UNKNOWN').str.upper()
        df['llm_classification'] = df['llm_classification'].fillna('UNKNOWN').str.upper()
        
        # Create agreement column
        df['agreement'] = df['purity_classification'] == df['llm_classification']
        
        return df
    
    def load_analysis_sessions(self) -> List[Dict]:
        """Load analysis session data for progress tracking."""
        pattern = os.path.join(self.analysis_dir, "llm_purity_analysis_*.json")
        files = glob.glob(pattern)
        
        sessions = []
        for file in files:
            try:
                with open(file, 'r') as f:
                    session_data = json.load(f)
                    sessions.append(session_data)
            except Exception as e:
                print(f"Error loading {file}: {e}")
                
        return sessions
    
    def create_agreement_overview(self, df: pd.DataFrame) -> go.Figure:
        """Create overview of agreement between Purity and LLM classifications."""
        
        # Calculate agreement statistics
        total = len(df)
        agreements = df['agreement'].sum()
        disagreements = total - agreements
        agreement_rate = (agreements / total * 100) if total > 0 else 0
        
        # Create pie chart
        fig = go.Figure(data=[
            go.Pie(
                labels=['Agreement', 'Disagreement'],
                values=[agreements, disagreements],
                hole=0.4,
                marker_colors=[self.color_palette['agreement'], self.color_palette['disagreement']],
                textinfo='label+percent+value',
                textfont_size=14
            )
        ])
        
        fig.update_layout(
            title=f"Purity vs LLM Classification Agreement<br>Total: {total} commits | Agreement Rate: {agreement_rate:.1f}%",
            font=dict(size=12),
            showlegend=True,
            height=500
        )
        
        return fig
    
    def create_confusion_matrix(self, df: pd.DataFrame) -> go.Figure:
        """Create confusion matrix showing classification patterns."""
        
        # Create confusion matrix data
        confusion_data = pd.crosstab(df['purity_classification'], df['llm_classification'])
        
        # Convert to percentages
        confusion_pct = confusion_data.div(confusion_data.sum(axis=1), axis=0) * 100
        
        # Create annotations
        annotations = []
        for i, row in enumerate(confusion_data.index):
            for j, col in enumerate(confusion_data.columns):
                value = confusion_data.iloc[i, j]
                pct = confusion_pct.iloc[i, j]
                annotations.append(
                    dict(
                        x=col, y=row,
                        text=f"{value}<br>({pct:.1f}%)",
                        showarrow=False,
                        font=dict(color="white" if value > confusion_data.max().max()/2 else "black")
                    )
                )
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=confusion_data.values,
            x=confusion_data.columns,
            y=confusion_data.index,
            colorscale='RdYlBu_r',
            showscale=True,
            colorbar=dict(title="Count")
        ))
        
        fig.update_layout(
            title="Classification Confusion Matrix<br>Purity (rows) vs LLM (columns)",
            xaxis_title="LLM Classification",
            yaxis_title="Purity Classification",
            annotations=annotations,
            height=500
        )
        
        return fig
    
    def create_repository_analysis(self, df: pd.DataFrame) -> go.Figure:
        """Create repository-wise analysis of classifications."""
        
        # Extract repository name from URL
        df['repo_name'] = df['repository'].str.extract(r'/([^/]+)$')[0].fillna('unknown')
        
        # Calculate statistics by repository
        repo_stats = df.groupby('repo_name').agg({
            'agreement': ['count', 'sum', 'mean'],
            'purity_classification': lambda x: (x == 'PURE').sum(),
            'llm_classification': lambda x: (x == 'PURE').sum()
        }).round(3)
        
        # Flatten column names
        repo_stats.columns = ['total', 'agreements', 'agreement_rate', 'purity_pure', 'llm_pure']
        repo_stats = repo_stats.reset_index()
        
        # Create subplot
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Agreement Rate by Repository', 'Total Commits by Repository',
                          'Purity vs LLM Pure Classifications', 'Repository Agreement Details'),
            specs=[[{"type": "bar"}, {"type": "bar"}],
                   [{"type": "scatter"}, {"type": "table"}]]
        )
        
        # Agreement rate by repository
        fig.add_trace(
            go.Bar(x=repo_stats['repo_name'], y=repo_stats['agreement_rate'],
                   name='Agreement Rate', marker_color=self.color_palette['agreement']),
            row=1, col=1
        )
        
        # Total commits by repository
        fig.add_trace(
            go.Bar(x=repo_stats['repo_name'], y=repo_stats['total'],
                   name='Total Commits', marker_color=self.color_palette['primary']),
            row=1, col=2
        )
        
        # Scatter plot: Purity vs LLM pure classifications
        fig.add_trace(
            go.Scatter(x=repo_stats['purity_pure'], y=repo_stats['llm_pure'],
                      mode='markers+text', text=repo_stats['repo_name'],
                      textposition='top center', name='Repositories',
                      marker=dict(size=repo_stats['total']*2, opacity=0.7)),
            row=2, col=1
        )
        
        # Table with detailed statistics
        fig.add_trace(
            go.Table(
                header=dict(values=['Repository', 'Total', 'Agreements', 'Rate %', 'Purity Pure', 'LLM Pure']),
                cells=dict(values=[repo_stats['repo_name'], repo_stats['total'],
                                 repo_stats['agreements'], 
                                 (repo_stats['agreement_rate']*100).round(1),
                                 repo_stats['purity_pure'], repo_stats['llm_pure']])
            ),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=False,
                         title_text="Repository-wise Analysis")
        
        return fig
    
    def create_classification_distribution(self, df: pd.DataFrame) -> go.Figure:
        """Create distribution analysis of classifications."""
        
        # Count classifications
        purity_counts = df['purity_classification'].value_counts()
        llm_counts = df['llm_classification'].value_counts()
        
        # Create subplot
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Purity Classifications', 'LLM Classifications'),
            specs=[[{"type": "pie"}, {"type": "pie"}]]
        )
        
        # Purity pie chart
        fig.add_trace(
            go.Pie(labels=purity_counts.index, values=purity_counts.values,
                   name="Purity", hole=0.3),
            row=1, col=1
        )
        
        # LLM pie chart
        fig.add_trace(
            go.Pie(labels=llm_counts.index, values=llm_counts.values,
                   name="LLM", hole=0.3),
            row=1, col=2
        )
        
        fig.update_layout(
            title_text="Classification Distribution Comparison",
            height=500
        )
        
        return fig
    
    def create_timeline_analysis(self, sessions: List[Dict]) -> go.Figure:
        """Create timeline analysis of analysis sessions."""
        
        if not sessions:
            return go.Figure().add_annotation(
                text="No session data available", 
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        # Extract session information
        session_data = []
        for session in sessions:
            info = session.get('session_info', {})
            session_data.append({
                'start_time': pd.to_datetime(info.get('start_time')),
                'end_time': pd.to_datetime(info.get('end_time')),
                'total_processed': info.get('total_processed', 0),
                'successful_analyses': info.get('successful_analyses', 0),
                'failed_analyses': info.get('failed_analyses', 0),
                'duration_minutes': (pd.to_datetime(info.get('end_time')) - 
                                   pd.to_datetime(info.get('start_time'))).total_seconds() / 60
            })
        
        df_sessions = pd.DataFrame(session_data)
        
        # Create timeline plot
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Analysis Sessions Timeline', 'Success Rate by Session',
                          'Processing Speed', 'Cumulative Progress'),
            specs=[[{"type": "scatter"}, {"type": "bar"}],
                   [{"type": "scatter"}, {"type": "scatter"}]]
        )
        
        # Timeline
        fig.add_trace(
            go.Scatter(x=df_sessions['start_time'], y=df_sessions['total_processed'],
                      mode='lines+markers', name='Processed'),
            row=1, col=1
        )
        
        # Success rate
        success_rate = (df_sessions['successful_analyses'] / df_sessions['total_processed'] * 100).fillna(0)
        fig.add_trace(
            go.Bar(x=list(range(len(df_sessions))), y=success_rate,
                   name='Success Rate %'),
            row=1, col=2
        )
        
        # Processing speed (commits per minute)
        speed = (df_sessions['total_processed'] / df_sessions['duration_minutes']).fillna(0)
        fig.add_trace(
            go.Scatter(x=df_sessions['start_time'], y=speed,
                      mode='lines+markers', name='Commits/min'),
            row=2, col=1
        )
        
        # Cumulative progress
        cumulative = df_sessions['total_processed'].cumsum()
        fig.add_trace(
            go.Scatter(x=df_sessions['start_time'], y=cumulative,
                      mode='lines+markers', name='Cumulative'),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=False,
                         title_text="Analysis Progress Timeline")
        
        return fig
    
    def create_progress_dashboard(self, total_commits: int = None) -> go.Figure:
        """Create progress dashboard showing analysis completion status."""
        
        # Load session data to calculate progress
        sessions = self.load_analysis_sessions()
        
        if not sessions:
            analyzed_count = 0
        else:
            # Sum all successful analyses across sessions
            analyzed_count = sum(session.get('session_info', {}).get('successful_analyses', 0) 
                               for session in sessions)
        
        # If total_commits not provided, try to estimate from CSV
        if total_commits is None:
            try:
                main_csv = os.path.join(self.csv_dir, "commits_with_refactoring.csv")
                if os.path.exists(main_csv):
                    df_main = pd.read_csv(main_csv)
                    total_commits = len(df_main)
                else:
                    total_commits = 10000  # Default estimate
            except:
                total_commits = 10000
        
        progress_pct = (analyzed_count / total_commits * 100) if total_commits > 0 else 0
        remaining = total_commits - analyzed_count
        
        # Create progress visualization
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Overall Progress', 'Analysis Status',
                          'Recent Session Performance', 'Estimated Completion'),
            specs=[[{"type": "indicator"}, {"type": "pie"}],
                   [{"type": "bar"}, {"type": "table"}]]
        )
        
        # Progress indicator
        fig.add_trace(
            go.Indicator(
                mode="gauge+number+delta",
                value=progress_pct,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Analysis Progress (%)"},
                delta={'reference': 100},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': self.color_palette['primary']},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 80], 'color': "yellow"},
                        {'range': [80, 100], 'color': "lightgreen"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ),
            row=1, col=1
        )
        
        # Status pie chart
        fig.add_trace(
            go.Pie(
                labels=['Analyzed', 'Remaining'],
                values=[analyzed_count, remaining],
                hole=0.4,
                marker_colors=[self.color_palette['agreement'], self.color_palette['disagreement']]
            ),
            row=1, col=2
        )
        
        # Recent session performance
        if sessions:
            recent_sessions = sessions[-5:]  # Last 5 sessions
            session_names = [f"Session {i+1}" for i in range(len(recent_sessions))]
            session_counts = [s.get('session_info', {}).get('successful_analyses', 0) 
                            for s in recent_sessions]
            
            fig.add_trace(
                go.Bar(x=session_names, y=session_counts,
                       marker_color=self.color_palette['secondary']),
                row=2, col=1
            )
        
        # Completion estimate table
        if sessions and len(sessions) > 0:
            # Calculate average processing rate
            total_time = 0
            total_processed = 0
            
            for session in sessions:
                info = session.get('session_info', {})
                if info.get('start_time') and info.get('end_time'):
                    start = pd.to_datetime(info['start_time'])
                    end = pd.to_datetime(info['end_time'])
                    duration = (end - start).total_seconds() / 3600  # hours
                    total_time += duration
                    total_processed += info.get('successful_analyses', 0)
            
            if total_processed > 0:
                avg_rate = total_processed / total_time  # commits per hour
                remaining_time = remaining / avg_rate if avg_rate > 0 else 0
                
                fig.add_trace(
                    go.Table(
                        header=dict(values=['Metric', 'Value']),
                        cells=dict(values=[
                            ['Total Commits', 'Analyzed', 'Remaining', 'Progress %', 
                             'Avg Rate (commits/hour)', 'Est. Remaining Time (hours)'],
                            [f"{total_commits:,}", f"{analyzed_count:,}", f"{remaining:,}",
                             f"{progress_pct:.1f}%", f"{avg_rate:.1f}", f"{remaining_time:.1f}"]
                        ])
                    ),
                    row=2, col=2
                )
        
        fig.update_layout(
            height=800,
            title_text=f"LLM Analysis Progress Dashboard - {analyzed_count:,}/{total_commits:,} commits ({progress_pct:.1f}%)"
        )
        
        return fig
    
    def create_comprehensive_dashboard(self, export_path: str = None) -> str:
        """Create comprehensive interactive dashboard with filters."""
        
        try:
            # Load data
            df = self.load_comparison_data()
            sessions = self.load_analysis_sessions()
            
            print(f"Loaded {len(df)} comparison records and {len(sessions)} analysis sessions")
            
            # Create all visualizations
            agreement_fig = self.create_agreement_overview(df)
            confusion_fig = self.create_confusion_matrix(df)
            distribution_fig = self.create_classification_distribution(df)
            timeline_fig = self.create_timeline_analysis(sessions)
            progress_fig = self.create_progress_dashboard()
            
            # Extract repository names for filter options
            df['repo_name'] = df['repository'].str.extract(r'/([^/]+)$')[0].fillna('unknown')
            repositories = sorted(df['repo_name'].unique())
            
            # Combine into comprehensive dashboard with interactivity
            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>LLM vs Purity Analysis Dashboard</title>
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <style>
                    * {{
                        font-family: 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    }}
                    body {{ 
                        margin: 0; 
                        padding: 20px; 
                        background-color: #f5f7fa;
                        -webkit-font-feature-settings: "liga";
                        font-feature-settings: "liga";
                        text-rendering: optimizeLegibility;
                    }}
                    .header {{ text-align: center; margin-bottom: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                    .filters {{ background-color: white; padding: 20px; border-radius: 10px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .filter-group {{ display: inline-block; margin: 10px; }}
                    .filter-group label {{ display: block; margin-bottom: 5px; font-weight: bold; color: #333; }}
                    .filter-group select, .filter-group input {{ padding: 8px; border: 1px solid #ddd; border-radius: 5px; }}
                    .filter-buttons {{ text-align: center; margin: 15px 0; }}
                    .filter-btn {{ 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        margin: 5px;
                        border-radius: 5px;
                        cursor: pointer;
                        font-weight: bold;
                    }}
                    .filter-btn:hover {{ opacity: 0.8; }}
                    .chart-container {{ margin: 30px 0; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .stats-summary {{ 
                        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                        color: white;
                        padding: 20px; 
                        border-radius: 10px; 
                        margin: 20px 0;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }}
                    .stat-item {{ background-color: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center; }}
                    .stat-value {{ font-size: 2em; font-weight: bold; }}
                    .stat-label {{ font-size: 0.9em; opacity: 0.9; }}
                    h2 {{ color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
                    h3 {{ color: #555; }}
                    .export-buttons {{ text-align: center; margin: 20px 0; }}
                    .export-btn {{ 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        margin: 5px;
                        border-radius: 5px;
                        cursor: pointer;
                        font-weight: bold;
                    }}
                    .export-btn:hover {{ opacity: 0.8; }}
                    .emoji {{ font-size: 1.2em; margin-right: 8px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1><span class="emoji">🔍</span>LLM vs Purity Classification Analysis Dashboard</h1>
                    <p>Interactive Analysis of Refactoring Classification Agreement</p>
                    <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p><strong>Data Source:</strong> hashes_no_rpt_purity_with_analysis.csv (Fair Comparison - Both analyses present)</p>
                </div>
                
                <div class="filters">
                    <h3><span class="emoji">🎛️</span>Interactive Filters</h3>
                    <div class="filter-group">
                        <label for="agreementFilter">Agreement:</label>
                        <select id="agreementFilter">
                            <option value="all">All</option>
                            <option value="true">Agreement Only</option>
                            <option value="false">Disagreement Only</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="purityFilter">Purity Classification:</label>
                        <select id="purityFilter">
                            <option value="all">All</option>
                            <option value="PURE">PURE</option>
                            <option value="FLOSS">FLOSS</option>
                            <option value="UNKNOWN">UNKNOWN</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="llmFilter">LLM Classification:</label>
                        <select id="llmFilter">
                            <option value="all">All</option>
                            <option value="PURE">PURE</option>
                            <option value="FLOSS">FLOSS</option>
                            <option value="UNKNOWN">UNKNOWN</option>
                        </select>
                    </div>
                    <div class="filter-buttons">
                        <button onclick="applyFilters()" class="filter-btn">Apply Filters</button>
                        <button onclick="resetFilters()" class="filter-btn">Reset Filters</button>
                        <button onclick="exportCurrentView()" class="filter-btn">Export Current View</button>
                    </div>
                </div>
                
                <div class="stats-summary">
                    <h2><span class="emoji">📊</span>Summary Statistics (Fair Comparison)</h2>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-value" id="totalComparisons">{len(df):,}</div>
                            <div class="stat-label">Total Valid Comparisons</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="agreementRate">{(df['agreement'].mean() * 100):.1f}%</div>
                            <div class="stat-label">Agreement Rate</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{(df['purity_classification'] == 'PURE').sum()}</div>
                            <div class="stat-label">Purity PURE</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{(df['llm_classification'] == 'PURE').sum()}</div>
                            <div class="stat-label">LLM PURE</div>
                        </div>
                    </div>
                </div>
                
                <div class="chart-container">
                    <h2><span class="emoji">📈</span>Progress Overview</h2>
                    <div id="progress-chart"></div>
                </div>
                
                <div class="chart-container">
                    <h2><span class="emoji">🎯</span>Agreement Analysis</h2>
                    <div id="agreement-chart"></div>
                </div>
                
                <div class="chart-container">
                    <h2><span class="emoji">🔄</span>Classification Confusion Matrix</h2>
                    <div id="confusion-chart"></div>
                </div>
                
                <div class="chart-container">
                    <h2><span class="emoji">📊</span>Classification Distribution</h2>
                    <div id="distribution-chart"></div>
                </div>
                
                <div class="chart-container">
                    <h2><span class="emoji">⏱️</span>Timeline Analysis</h2>
                    <div id="timeline-chart"></div>
                </div>
                
                <div class="export-buttons">
                    <button onclick="exportChartAsPNG('agreement-chart', 'agreement_chart')" class="export-btn"><span class="emoji">📥</span>Export Agreement Chart</button>
                    <button onclick="exportChartAsPNG('confusion-chart', 'confusion_matrix')" class="export-btn"><span class="emoji">📥</span>Export Confusion Matrix</button>
                    <button onclick="exportAllCharts()" class="export-btn"><span class="emoji">📦</span>Export All Charts</button>
                </div>
                
                <script>
                    // Store original data for filtering
                    const originalData = {df.to_json(orient='records')};
                    let currentData = [...originalData];
                    
                    // Initialize charts
                    function initializeCharts() {{
                        Plotly.newPlot('progress-chart', {progress_fig.to_json()});
                        Plotly.newPlot('agreement-chart', {agreement_fig.to_json()});
                        Plotly.newPlot('confusion-chart', {confusion_fig.to_json()});
                        Plotly.newPlot('distribution-chart', {distribution_fig.to_json()});
                        Plotly.newPlot('timeline-chart', {timeline_fig.to_json()});
                    }}
                    
                    // Apply filters
                    function applyFilters() {{
                        const agreementFilter = document.getElementById('agreementFilter').value;
                        const purityFilter = document.getElementById('purityFilter').value;
                        const llmFilter = document.getElementById('llmFilter').value;
                        
                        currentData = originalData.filter(row => {{
                            if (agreementFilter !== 'all' && row.agreement.toString() !== agreementFilter) return false;
                            if (purityFilter !== 'all' && row.purity_classification !== purityFilter) return false;
                            if (llmFilter !== 'all' && row.llm_classification !== llmFilter) return false;
                            
                            return true;
                        }});
                        
                        updateStatistics();
                        updateCharts();
                    }}
                    
                    // Reset filters
                    function resetFilters() {{
                        document.getElementById('agreementFilter').value = 'all';
                        document.getElementById('purityFilter').value = 'all';
                        document.getElementById('llmFilter').value = 'all';
                        
                        currentData = [...originalData];
                        updateStatistics();
                        updateCharts();
                    }}
                    
                    // Update statistics
                    function updateStatistics() {{
                        const total = currentData.length;
                        const agreements = currentData.filter(row => row.agreement).length;
                        const agreementRate = total > 0 ? (agreements / total * 100).toFixed(1) : 0;
                        
                        document.getElementById('totalComparisons').textContent = total.toLocaleString();
                        document.getElementById('agreementRate').textContent = agreementRate + '%';
                    }}
                    
                    // Update charts with filtered data
                    function updateCharts() {{
                        // This would require more complex chart updating logic
                        // For now, we'll show a notification
                        if (currentData.length !== originalData.length) {{
                            console.log(`Filters applied: ${{currentData.length}} of ${{originalData.length}} records shown`);
                        }}
                    }}
                    
                    // Export functions
                    function exportChartAsPNG(chartId, filename) {{
                        Plotly.downloadImage(chartId, {{
                            format: 'png',
                            width: 1200,
                            height: 800,
                            filename: filename
                        }});
                    }}
                    
                    function exportAllCharts() {{
                        const charts = ['agreement-chart', 'confusion-chart', 'distribution-chart', 'repository-chart'];
                        const names = ['agreement_analysis', 'confusion_matrix', 'distribution_analysis', 'repository_analysis'];
                        
                        charts.forEach((chartId, index) => {{
                            setTimeout(() => {{
                                exportChartAsPNG(chartId, names[index]);
                            }}, index * 1000);
                        }});
                    }}
                    
                    function exportCurrentView() {{
                        const blob = new Blob([JSON.stringify(currentData, null, 2)], {{type: 'application/json'}});
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'filtered_analysis_data.json';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                    }}
                    
                    // Initialize on load
                    document.addEventListener('DOMContentLoaded', initializeCharts);
                </script>
            </body>
            </html>
            """
            
            # Save dashboard
            if export_path is None:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                export_path = f"llm_analysis_dashboard_{timestamp}.html"
            
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(dashboard_html)
            
            print(f"Dashboard saved to: {export_path}")
            return export_path
            
        except Exception as e:
            print(f"Error creating dashboard: {e}")
            return None
    
    def export_analysis_data(self, format_type: str = "all") -> Dict[str, str]:
        """Export analysis data in multiple formats."""
        
        try:
            df = self.load_comparison_data()
            sessions = self.load_analysis_sessions()
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            exported_files = {}
            
            if format_type in ["all", "csv"]:
                # Enhanced CSV export
                csv_path = f"llm_analysis_export_{timestamp}.csv"
                df.to_csv(csv_path, index=False)
                exported_files['csv'] = csv_path
            
            if format_type in ["all", "json"]:
                # JSON export with sessions
                json_path = f"llm_analysis_export_{timestamp}.json"
                export_data = {
                    'comparison_data': df.to_dict('records'),
                    'analysis_sessions': sessions,
                    'export_timestamp': datetime.now().isoformat(),
                    'statistics': {
                        'total_comparisons': len(df),
                        'agreement_rate': float(df['agreement'].mean()),
                        'purity_pure_count': int((df['purity_classification'] == 'PURE').sum()),
                        'llm_pure_count': int((df['llm_classification'] == 'PURE').sum()),
                        'repositories': df['repository'].unique().tolist()
                    }
                }
                
                with open(json_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
                exported_files['json'] = json_path
            
            if format_type in ["all", "html"]:
                # HTML dashboard
                html_path = self.create_comprehensive_dashboard(f"llm_dashboard_export_{timestamp}.html")
                if html_path:
                    exported_files['html'] = html_path
            
            if format_type in ["all", "excel"]:
                # Excel export with multiple sheets
                excel_path = f"llm_analysis_export_{timestamp}.xlsx"
                
                with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                    # Main comparison data
                    df.to_excel(writer, sheet_name='Comparison_Data', index=False)
                    
                    # Statistics summary
                    stats_data = {
                        'Metric': ['Total Comparisons', 'Agreement Rate (%)', 'Purity PURE Count', 
                                 'LLM PURE Count', 'Repositories Count'],
                        'Value': [len(df), f"{df['agreement'].mean() * 100:.1f}",
                                (df['purity_classification'] == 'PURE').sum(),
                                (df['llm_classification'] == 'PURE').sum(),
                                df['repository'].nunique()]
                    }
                    pd.DataFrame(stats_data).to_excel(writer, sheet_name='Summary_Stats', index=False)
                    
                    # Repository breakdown
                    df_copy = df.copy()
                    df_copy['repo_name'] = df_copy['repository'].str.extract(r'/([^/]+)$')[0].fillna('unknown')
                    repo_stats = df_copy.groupby('repo_name').agg({
                        'agreement': ['count', 'sum', 'mean'],
                        'purity_classification': lambda x: (x == 'PURE').sum(),
                        'llm_classification': lambda x: (x == 'PURE').sum()
                    }).round(3)
                    repo_stats.columns = ['total', 'agreements', 'agreement_rate', 'purity_pure', 'llm_pure']
                    repo_stats.to_excel(writer, sheet_name='Repository_Stats')
                
                exported_files['excel'] = excel_path
            
            if format_type in ["all", "png"]:
                # PNG exports of key charts
                try:
                    import plotly.io as pio
                    pio.kaleido.scope.mathjax = None  # Avoid MathJax issues
                    
                    # Agreement overview
                    agreement_fig = self.create_agreement_overview(df)
                    agreement_png = f"agreement_chart_{timestamp}.png"
                    agreement_fig.write_image(agreement_png, width=800, height=600)
                    
                    # Confusion matrix
                    confusion_fig = self.create_confusion_matrix(df)
                    confusion_png = f"confusion_matrix_{timestamp}.png"
                    confusion_fig.write_image(confusion_png, width=800, height=600)
                    
                    exported_files['png'] = {
                        'agreement': agreement_png,
                        'confusion': confusion_png
                    }
                    
                except Exception as e:
                    print(f"Warning: PNG export failed: {e}")
                    print("Install kaleido for PNG export: pip install kaleido")
            
            print(f"Exported files: {list(exported_files.keys())}")
            return exported_files
            
        except Exception as e:
            print(f"Error exporting data: {e}")
            return {}
    
    def create_export_package(self, package_name: str = None) -> str:
        """Create a complete export package with all visualizations and data."""
        
        if package_name is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            package_name = f"llm_analysis_package_{timestamp}"
        
        # Create package directory
        os.makedirs(package_name, exist_ok=True)
        
        try:
            df = self.load_comparison_data()
            sessions = self.load_analysis_sessions()
            
            print(f"Creating export package in: {package_name}/")
            
            # Export all data formats
            exported = self.export_analysis_data("all")
            
            # Move files to package directory
            moved_files = {}
            for format_type, file_path in exported.items():
                if isinstance(file_path, dict):  # Handle PNG dictionary
                    moved_files[format_type] = {}
                    for chart_type, png_path in file_path.items():
                        new_path = os.path.join(package_name, os.path.basename(png_path))
                        os.rename(png_path, new_path)
                        moved_files[format_type][chart_type] = new_path
                else:
                    new_path = os.path.join(package_name, os.path.basename(file_path))
                    os.rename(file_path, new_path)
                    moved_files[format_type] = new_path
            
            # Create individual chart HTML files
            charts_dir = os.path.join(package_name, "charts")
            os.makedirs(charts_dir, exist_ok=True)
            
            chart_files = []
            
            # Individual charts
            charts = [
                ("agreement_overview", self.create_agreement_overview(df)),
                ("confusion_matrix", self.create_confusion_matrix(df)),
                ("repository_analysis", self.create_repository_analysis(df)),
                ("classification_distribution", self.create_classification_distribution(df)),
                ("timeline_analysis", self.create_timeline_analysis(sessions)),
                ("progress_dashboard", self.create_progress_dashboard())
            ]
            
            for chart_name, fig in charts:
                chart_path = os.path.join(charts_dir, f"{chart_name}.html")
                fig.write_html(chart_path)
                chart_files.append(chart_path)
            
            # Create README for the package
            readme_content = f"""
# LLM Analysis Export Package

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Contents

### Data Files
- **CSV**: Raw comparison data in spreadsheet format
- **JSON**: Complete data with analysis sessions and metadata
- **Excel**: Multi-sheet workbook with data and statistics
- **HTML**: Interactive dashboard with all visualizations

### Visualizations (charts/ directory)
- `agreement_overview.html`: Agreement between Purity and LLM classifications
- `confusion_matrix.html`: Classification confusion matrix
- `repository_analysis.html`: Repository-wise analysis breakdown
- `classification_distribution.html`: Distribution of classifications
- `timeline_analysis.html`: Analysis session timeline
- `progress_dashboard.html`: Progress tracking dashboard

### Summary Statistics
- Total comparisons: {len(df):,}
- Agreement rate: {(df['agreement'].mean() * 100):.1f}%
- Repositories analyzed: {df['repository'].nunique()}
- Analysis sessions: {len(sessions)}

## Usage
1. Open the main HTML dashboard for interactive exploration
2. Use CSV/Excel files for further analysis in other tools
3. Individual chart HTML files can be shared independently
4. JSON file contains complete raw data for programmatic access

## Software
Generated using LLM Visualization Handler for Refactoring Analysis
"""
            
            readme_path = os.path.join(package_name, "README.md")
            with open(readme_path, 'w') as f:
                f.write(readme_content)
            
            print(f"✅ Export package created successfully!")
            print(f"📁 Package location: {package_name}/")
            print(f"📄 Files included: {len(moved_files)} data formats + {len(chart_files)} charts + README")
            
            return package_name
            
        except Exception as e:
            print(f"Error creating export package: {e}")
            return None


def main():
    """Main function to demonstrate the visualization capabilities."""
    
    # Initialize handler
    handler = LLMVisualizationHandler()
    
    try:
        # Create comprehensive dashboard
        print("Creating comprehensive LLM analysis dashboard...")
        dashboard_path = handler.create_comprehensive_dashboard()
        
        if dashboard_path:
            print(f"✅ Dashboard created successfully: {dashboard_path}")
        
        # Export data in multiple formats
        print("\nExporting analysis data...")
        exported = handler.export_analysis_data()
        
        if exported:
            print("✅ Export completed:")
            for format_type, path in exported.items():
                print(f"   {format_type.upper()}: {path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
