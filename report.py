# report.py

"""
HTML test report generator for DICOM performance tests.

Produces a self-contained HTML file with embedded Chart.js, dark theme,
interactive charts, and filterable results table.
"""

from __future__ import annotations

import html
import json
import math
import platform
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TestResult:
    """Per-test result data."""

    node_id: str
    outcome: str  # "passed", "failed", "skipped", "error"
    duration: float  # seconds
    perf_snapshot: Optional[Dict[str, Any]] = None
    perf_samples: Optional[List[Dict[str, Any]]] = None  # serialized Sample dicts
    thresholds: Optional[Dict[str, float]] = None
    markers: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class ReportData:
    """Session-level report data."""

    timestamp: str
    duration: float  # seconds
    platform_info: str
    test_results: List[TestResult]
    config_summary: Optional[Dict[str, Any]] = None


def _compute_latency_histogram(samples: List[Dict], bins: int = 30) -> Dict:
    """Pre-compute histogram bins for Chart.js bar chart."""
    latencies = [s["latency_ms"] for s in samples if s.get("success")]
    if not latencies:
        return {"labels": [], "values": []}

    lo, hi = min(latencies), max(latencies)
    if lo == hi:
        return {"labels": [f"{lo:.0f}"], "values": [len(latencies)]}

    bin_width = (hi - lo) / bins
    counts = [0] * bins
    for lat in latencies:
        idx = min(int((lat - lo) / bin_width), bins - 1)
        counts[idx] += 1

    labels = [f"{lo + i * bin_width:.0f}" for i in range(bins)]
    return {"labels": labels, "values": counts, "bin_width": bin_width}


def _compute_throughput_timeline(samples: List[Dict], bucket_seconds: float = 1.0) -> Dict:
    """Compute 1-second bucket throughput time series."""
    if not samples:
        return {"labels": [], "values": []}

    start = min(s["start_time"] for s in samples)
    end = max(s["end_time"] for s in samples)
    duration = end - start
    if duration <= 0:
        return {"labels": ["0"], "values": [len(samples)]}

    num_buckets = max(1, int(math.ceil(duration / bucket_seconds)))
    # Cap buckets to prevent huge arrays
    if num_buckets > 600:
        bucket_seconds = duration / 600
        num_buckets = 600

    counts = [0] * num_buckets
    for s in samples:
        idx = min(int((s["start_time"] - start) / bucket_seconds), num_buckets - 1)
        counts[idx] += 1

    # Convert counts to rate (per second)
    rates = [c / bucket_seconds for c in counts]
    labels = [f"{i * bucket_seconds:.1f}" for i in range(num_buckets)]
    return {"labels": labels, "values": rates}


def _compute_latency_scatter(samples: List[Dict], max_points: int = 5000) -> Dict:
    """Compute latency-over-time scatter data, downsampling if needed."""
    if not samples:
        return {"success": [], "failure": []}

    start = min(s["start_time"] for s in samples)

    success_pts = []
    failure_pts = []
    for s in samples:
        pt = {"x": round(s["start_time"] - start, 3), "y": round(s["latency_ms"], 2)}
        if s.get("success"):
            success_pts.append(pt)
        else:
            failure_pts.append(pt)

    # Downsample success points if too many (keep all failure points)
    if len(success_pts) > max_points:
        step = len(success_pts) / max_points
        success_pts = [success_pts[int(i * step)] for i in range(max_points)]

    return {"success": success_pts, "failure": failure_pts}


def _esc(text: str) -> str:
    """HTML-escape text."""
    return html.escape(str(text))


def _render_css() -> str:
    """Render the dark theme CSS."""
    return """
    <style>
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #1e2a45;
            --text-primary: #e0e0e0;
            --text-secondary: #a0a0b0;
            --accent-green: #00d4aa;
            --accent-red: #e94560;
            --accent-yellow: #ffc107;
            --accent-blue: #4fc3f7;
            --border-color: #2a3a5e;
            --radius: 8px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 24px;
        }

        .container { max-width: 1400px; margin: 0 auto; }

        h1 {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 4px;
        }

        h2 {
            font-size: 1.3rem;
            font-weight: 600;
            margin: 32px 0 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--border-color);
        }

        h3 {
            font-size: 1.1rem;
            font-weight: 600;
            margin: 24px 0 12px;
            color: var(--accent-blue);
        }

        .header {
            text-align: center;
            padding: 24px 0 16px;
            border-bottom: 2px solid var(--border-color);
            margin-bottom: 24px;
        }

        .header-meta {
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 8px;
        }

        .header-meta span { margin: 0 12px; }

        /* Summary cards */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 20px;
            text-align: center;
        }

        .stat-card .value {
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.2;
        }

        .stat-card .label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .stat-total .value { color: var(--accent-blue); }
        .stat-passed .value { color: var(--accent-green); }
        .stat-failed .value { color: var(--accent-red); }
        .stat-skipped .value { color: var(--accent-yellow); }

        /* Charts */
        .charts-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 24px;
        }

        .chart-container {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 16px;
        }

        .chart-container canvas {
            max-height: 300px;
        }

        /* Config table */
        .config-section {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 20px;
            margin-bottom: 24px;
        }

        .config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 16px;
        }

        .config-group h4 {
            font-size: 0.95rem;
            color: var(--accent-blue);
            margin-bottom: 8px;
        }

        .config-group table {
            width: 100%;
            border-collapse: collapse;
        }

        .config-group td {
            padding: 4px 8px;
            font-size: 0.85rem;
            border-bottom: 1px solid var(--border-color);
        }

        .config-group td:first-child {
            color: var(--text-secondary);
            width: 50%;
        }

        /* Filter buttons */
        .filter-bar {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }

        .filter-btn {
            padding: 6px 16px;
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            background: var(--bg-card);
            color: var(--text-primary);
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }

        .filter-btn:hover { border-color: var(--accent-blue); }
        .filter-btn.active {
            background: var(--accent-blue);
            color: #000;
            border-color: var(--accent-blue);
        }

        /* Results table */
        .results-table {
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-card);
            border-radius: var(--radius);
            overflow: hidden;
            margin-bottom: 24px;
        }

        .results-table th {
            background: var(--bg-secondary);
            padding: 12px 16px;
            text-align: left;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border-color);
        }

        .results-table td {
            padding: 10px 16px;
            font-size: 0.85rem;
            border-bottom: 1px solid var(--border-color);
        }

        .results-table tr:hover { background: rgba(79, 195, 247, 0.05); }

        .badge {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-passed { background: rgba(0, 212, 170, 0.15); color: var(--accent-green); }
        .badge-failed { background: rgba(233, 69, 96, 0.15); color: var(--accent-red); }
        .badge-skipped { background: rgba(255, 193, 7, 0.15); color: var(--accent-yellow); }
        .badge-error { background: rgba(233, 69, 96, 0.15); color: var(--accent-red); }

        .marker-tag {
            display: inline-block;
            padding: 1px 6px;
            border-radius: 4px;
            font-size: 0.7rem;
            background: rgba(79, 195, 247, 0.15);
            color: var(--accent-blue);
            margin-right: 4px;
        }

        /* Performance detail cards */
        .perf-section {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            padding: 20px;
            margin-bottom: 24px;
        }

        .gauge-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }

        .gauge-card {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 16px;
            text-align: center;
        }

        .gauge-card .gauge-value {
            font-size: 1.4rem;
            font-weight: 700;
        }

        .gauge-card .gauge-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        .gauge-card .gauge-threshold {
            font-size: 0.7rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .gauge-ok { color: var(--accent-green); }
        .gauge-warn { color: var(--accent-yellow); }
        .gauge-bad { color: var(--accent-red); }

        .perf-charts {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }

        .perf-chart-box {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 12px;
        }

        .perf-chart-box canvas { max-height: 250px; }

        /* Failure details */
        .failure-block {
            background: var(--bg-card);
            border: 1px solid var(--accent-red);
            border-radius: var(--radius);
            margin-bottom: 12px;
            overflow: hidden;
        }

        .failure-header {
            padding: 12px 16px;
            background: rgba(233, 69, 96, 0.1);
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .failure-header:hover { background: rgba(233, 69, 96, 0.15); }

        .failure-body {
            padding: 16px;
            display: none;
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
            font-size: 0.8rem;
            white-space: pre-wrap;
            word-break: break-word;
            color: var(--text-secondary);
            max-height: 400px;
            overflow-y: auto;
        }

        .failure-body.open { display: block; }

        .chevron { transition: transform 0.2s; }
        .chevron.open { transform: rotate(90deg); }

        /* Responsive */
        @media (max-width: 800px) {
            .charts-row, .perf-charts { grid-template-columns: 1fr; }
            .config-grid { grid-template-columns: 1fr; }
            body { padding: 12px; }
        }

        /* Full-width chart variant */
        .perf-charts-full {
            display: grid;
            grid-template-columns: 1fr;
            gap: 16px;
        }

        .perf-charts-full .perf-chart-box canvas { max-height: 300px; }
    </style>
    """


def _render_js(data: ReportData) -> str:
    """Render the JavaScript for Chart.js charts and interactivity."""
    # Pre-compute chart data for each test with perf samples
    perf_chart_data = {}
    for i, tr in enumerate(data.test_results):
        if tr.perf_samples:
            samples = tr.perf_samples
            perf_chart_data[i] = {
                "histogram": _compute_latency_histogram(samples),
                "throughput": _compute_throughput_timeline(samples),
                "scatter": _compute_latency_scatter(samples),
            }

    # Summary data
    total = len(data.test_results)
    passed = sum(1 for t in data.test_results if t.outcome == "passed")
    failed = sum(1 for t in data.test_results if t.outcome == "failed")
    skipped = sum(1 for t in data.test_results if t.outcome == "skipped")
    errored = sum(1 for t in data.test_results if t.outcome == "error")

    # Duration bar chart data
    test_names = []
    test_durations = []
    test_colors = []
    color_map = {
        "passed": "rgba(0, 212, 170, 0.7)",
        "failed": "rgba(233, 69, 96, 0.7)",
        "skipped": "rgba(255, 193, 7, 0.7)",
        "error": "rgba(233, 69, 96, 0.7)",
    }
    for tr in data.test_results:
        # Short name: just the function name
        parts = tr.node_id.split("::")
        name = parts[-1] if parts else tr.node_id
        test_names.append(name)
        test_durations.append(round(tr.duration, 3))
        test_colors.append(color_map.get(tr.outcome, "rgba(79, 195, 247, 0.7)"))

    chart_defaults = """
    Chart.defaults.color = '#a0a0b0';
    Chart.defaults.borderColor = 'rgba(42, 58, 94, 0.5)';
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    """

    return f"""
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        {chart_defaults}

        const perfChartData = {json.dumps(perf_chart_data)};
        const testNames = {json.dumps(test_names)};
        const testDurations = {json.dumps(test_durations)};
        const testColors = {json.dumps(test_colors)};

        // --- Summary donut chart ---
        const donutCtx = document.getElementById('summaryDonut');
        if (donutCtx) {{
            new Chart(donutCtx, {{
                type: 'doughnut',
                data: {{
                    labels: ['Passed', 'Failed', 'Skipped', 'Error'],
                    datasets: [{{
                        data: [{passed}, {failed}, {skipped}, {errored}],
                        backgroundColor: [
                            'rgba(0, 212, 170, 0.8)',
                            'rgba(233, 69, 96, 0.8)',
                            'rgba(255, 193, 7, 0.8)',
                            'rgba(233, 69, 96, 0.5)'
                        ],
                        borderWidth: 0
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ padding: 16 }} }}
                    }},
                    cutout: '60%'
                }}
            }});
        }}

        // --- Duration bar chart ---
        const durCtx = document.getElementById('durationBar');
        if (durCtx) {{
            new Chart(durCtx, {{
                type: 'bar',
                data: {{
                    labels: testNames,
                    datasets: [{{
                        label: 'Duration (s)',
                        data: testDurations,
                        backgroundColor: testColors,
                        borderRadius: 4
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    indexAxis: testNames.length > 10 ? 'y' : 'x',
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        x: {{ grid: {{ color: 'rgba(42, 58, 94, 0.3)' }} }},
                        y: {{ grid: {{ color: 'rgba(42, 58, 94, 0.3)' }} }}
                    }}
                }}
            }});
        }}

        // --- Performance charts per test ---
        for (const [idx, data] of Object.entries(perfChartData)) {{
            const thresholdEl = document.getElementById('perf-thresholds-' + idx);
            let thresholds = {{}};
            if (thresholdEl) {{
                thresholds = JSON.parse(thresholdEl.textContent);
            }}

            // Latency histogram
            const histCtx = document.getElementById('histChart-' + idx);
            if (histCtx && data.histogram.labels.length > 0) {{
                const histPlugins = [];
                if (thresholds.max_p95_latency_ms) {{
                    histPlugins.push({{
                        id: 'p95Line',
                        afterDraw(chart) {{
                            const xScale = chart.scales.x;
                            const yScale = chart.scales.y;
                            const ctx = chart.ctx;
                            const p95 = thresholds.max_p95_latency_ms;
                            // Find the bar index closest to p95
                            const labels = data.histogram.labels.map(Number);
                            let p95Pixel = null;
                            for (let i = 0; i < labels.length; i++) {{
                                if (labels[i] >= p95) {{
                                    p95Pixel = xScale.getPixelForValue(i);
                                    break;
                                }}
                            }}
                            if (p95Pixel === null && labels.length > 0) {{
                                p95Pixel = xScale.getPixelForValue(labels.length - 1);
                            }}
                            if (p95Pixel !== null) {{
                                ctx.save();
                                ctx.strokeStyle = 'rgba(233, 69, 96, 0.8)';
                                ctx.lineWidth = 2;
                                ctx.setLineDash([6, 4]);
                                ctx.beginPath();
                                ctx.moveTo(p95Pixel, yScale.top);
                                ctx.lineTo(p95Pixel, yScale.bottom);
                                ctx.stroke();
                                ctx.fillStyle = 'rgba(233, 69, 96, 0.8)';
                                ctx.font = '11px sans-serif';
                                ctx.fillText('P95 threshold: ' + p95 + 'ms', p95Pixel + 4, yScale.top + 14);
                                ctx.restore();
                            }}
                        }}
                    }});
                }}

                new Chart(histCtx, {{
                    type: 'bar',
                    data: {{
                        labels: data.histogram.labels,
                        datasets: [{{
                            label: 'Count',
                            data: data.histogram.values,
                            backgroundColor: 'rgba(79, 195, 247, 0.6)',
                            borderRadius: 2
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {{
                            legend: {{ display: false }},
                            title: {{ display: true, text: 'Latency Distribution (ms)', color: '#e0e0e0' }}
                        }},
                        scales: {{
                            x: {{
                                title: {{ display: true, text: 'Latency (ms)' }},
                                grid: {{ color: 'rgba(42, 58, 94, 0.3)' }},
                                ticks: {{ maxTicksLimit: 15 }}
                            }},
                            y: {{
                                title: {{ display: true, text: 'Count' }},
                                grid: {{ color: 'rgba(42, 58, 94, 0.3)' }}
                            }}
                        }}
                    }},
                    plugins: histPlugins
                }});
            }}

            // Throughput timeline
            const tpCtx = document.getElementById('tpChart-' + idx);
            if (tpCtx && data.throughput.labels.length > 0) {{
                const tpAnnotations = [];
                if (thresholds.target_rate) {{
                    tpAnnotations.push({{
                        id: 'targetLine',
                        afterDraw(chart) {{
                            const yScale = chart.scales.y;
                            const xScale = chart.scales.x;
                            const ctx = chart.ctx;
                            const yPixel = yScale.getPixelForValue(thresholds.target_rate);
                            ctx.save();
                            ctx.strokeStyle = 'rgba(0, 212, 170, 0.6)';
                            ctx.lineWidth = 2;
                            ctx.setLineDash([6, 4]);
                            ctx.beginPath();
                            ctx.moveTo(xScale.left, yPixel);
                            ctx.lineTo(xScale.right, yPixel);
                            ctx.stroke();
                            ctx.fillStyle = 'rgba(0, 212, 170, 0.8)';
                            ctx.font = '11px sans-serif';
                            ctx.fillText('Target: ' + thresholds.target_rate + ' img/s', xScale.left + 4, yPixel - 6);
                            ctx.restore();
                        }}
                    }});
                }}

                new Chart(tpCtx, {{
                    type: 'line',
                    data: {{
                        labels: data.throughput.labels,
                        datasets: [{{
                            label: 'Images/sec',
                            data: data.throughput.values,
                            borderColor: 'rgba(0, 212, 170, 0.8)',
                            backgroundColor: 'rgba(0, 212, 170, 0.1)',
                            fill: true,
                            tension: 0.3,
                            pointRadius: 0,
                            borderWidth: 2
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {{
                            legend: {{ display: false }},
                            title: {{ display: true, text: 'Throughput Over Time', color: '#e0e0e0' }}
                        }},
                        scales: {{
                            x: {{
                                title: {{ display: true, text: 'Time (s)' }},
                                grid: {{ color: 'rgba(42, 58, 94, 0.3)' }},
                                ticks: {{ maxTicksLimit: 15 }}
                            }},
                            y: {{
                                title: {{ display: true, text: 'Images/sec' }},
                                grid: {{ color: 'rgba(42, 58, 94, 0.3)' }},
                                beginAtZero: true
                            }}
                        }}
                    }},
                    plugins: tpAnnotations
                }});
            }}

            // Latency scatter
            const scCtx = document.getElementById('scatterChart-' + idx);
            if (scCtx && (data.scatter.success.length > 0 || data.scatter.failure.length > 0)) {{
                const scDatasets = [];
                if (data.scatter.success.length > 0) {{
                    scDatasets.push({{
                        label: 'Success',
                        data: data.scatter.success,
                        backgroundColor: 'rgba(0, 212, 170, 0.4)',
                        pointRadius: 2,
                        pointHoverRadius: 5
                    }});
                }}
                if (data.scatter.failure.length > 0) {{
                    scDatasets.push({{
                        label: 'Failure',
                        data: data.scatter.failure,
                        backgroundColor: 'rgba(233, 69, 96, 0.6)',
                        pointRadius: 3,
                        pointHoverRadius: 6
                    }});
                }}

                new Chart(scCtx, {{
                    type: 'scatter',
                    data: {{ datasets: scDatasets }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {{
                            legend: {{ position: 'bottom' }},
                            title: {{ display: true, text: 'Latency Over Time', color: '#e0e0e0' }}
                        }},
                        scales: {{
                            x: {{
                                title: {{ display: true, text: 'Time (s)' }},
                                grid: {{ color: 'rgba(42, 58, 94, 0.3)' }}
                            }},
                            y: {{
                                title: {{ display: true, text: 'Latency (ms)' }},
                                grid: {{ color: 'rgba(42, 58, 94, 0.3)' }},
                                beginAtZero: true
                            }}
                        }}
                    }}
                }});
            }}
        }}

        // --- Filter buttons ---
        document.querySelectorAll('.filter-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const filter = this.dataset.filter;
                document.querySelectorAll('.results-table tbody tr').forEach(row => {{
                    if (filter === 'all' || row.dataset.outcome === filter) {{
                        row.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                    }}
                }});
            }});
        }});

        // --- Collapsible failure details ---
        document.querySelectorAll('.failure-header').forEach(header => {{
            header.addEventListener('click', function() {{
                const body = this.nextElementSibling;
                const chevron = this.querySelector('.chevron');
                body.classList.toggle('open');
                chevron.classList.toggle('open');
            }});
        }});
    }});
    </script>
    """


def _render_header(data: ReportData) -> str:
    """Render the report header."""
    duration_fmt = f"{data.duration:.1f}s" if data.duration < 60 else f"{data.duration / 60:.1f}m"
    return f"""
    <div class="header">
        <h1>DICOM Test Report</h1>
        <div class="header-meta">
            <span>{_esc(data.timestamp)}</span>
            <span>|</span>
            <span>Duration: {duration_fmt}</span>
            <span>|</span>
            <span>{_esc(data.platform_info)}</span>
        </div>
    </div>
    """


def _render_summary(data: ReportData) -> str:
    """Render summary dashboard with stat cards."""
    total = len(data.test_results)
    passed = sum(1 for t in data.test_results if t.outcome == "passed")
    failed = sum(1 for t in data.test_results if t.outcome in ("failed", "error"))
    skipped = sum(1 for t in data.test_results if t.outcome == "skipped")

    return f"""
    <div class="summary-grid">
        <div class="stat-card stat-total">
            <div class="value">{total}</div>
            <div class="label">Total Tests</div>
        </div>
        <div class="stat-card stat-passed">
            <div class="value">{passed}</div>
            <div class="label">Passed</div>
        </div>
        <div class="stat-card stat-failed">
            <div class="value">{failed}</div>
            <div class="label">Failed</div>
        </div>
        <div class="stat-card stat-skipped">
            <div class="value">{skipped}</div>
            <div class="label">Skipped</div>
        </div>
    </div>
    <div class="charts-row">
        <div class="chart-container">
            <canvas id="summaryDonut"></canvas>
        </div>
        <div class="chart-container">
            <canvas id="durationBar"></canvas>
        </div>
    </div>
    """


def _render_config(data: ReportData) -> str:
    """Render configuration section."""
    if not data.config_summary:
        return ""

    cfg = data.config_summary
    sections = []

    if "endpoint" in cfg:
        ep = cfg["endpoint"]
        rows = "".join(f"<tr><td>{_esc(k)}</td><td>{_esc(str(v))}</td></tr>" for k, v in ep.items())
        sections.append(f"<div class='config-group'><h4>Endpoint</h4><table>{rows}</table></div>")

    if "load_profile" in cfg:
        lp = cfg["load_profile"]
        rows = "".join(f"<tr><td>{_esc(k)}</td><td>{_esc(str(v))}</td></tr>" for k, v in lp.items())
        sections.append(f"<div class='config-group'><h4>Load Profile</h4><table>{rows}</table></div>")

    if "thresholds" in cfg:
        th = cfg["thresholds"]
        rows = "".join(f"<tr><td>{_esc(k)}</td><td>{_esc(str(v))}</td></tr>" for k, v in th.items())
        sections.append(f"<div class='config-group'><h4>Thresholds</h4><table>{rows}</table></div>")

    if "dataset" in cfg:
        ds = cfg["dataset"]
        rows = "".join(f"<tr><td>{_esc(k)}</td><td>{_esc(str(v))}</td></tr>" for k, v in ds.items())
        sections.append(f"<div class='config-group'><h4>Dataset</h4><table>{rows}</table></div>")

    inner = "\n".join(sections)
    return f"""
    <h2>Configuration</h2>
    <div class="config-section">
        <div class="config-grid">{inner}</div>
    </div>
    """


def _render_results_table(data: ReportData) -> str:
    """Render the filterable results table."""
    rows = []
    for tr in data.test_results:
        # Short test name
        parts = tr.node_id.split("::")
        short_name = parts[-1] if parts else tr.node_id
        module = parts[0].replace("tests/", "") if len(parts) > 1 else ""

        markers_html = "".join(f"<span class='marker-tag'>{_esc(m)}</span>" for m in tr.markers)

        perf_info = ""
        if tr.perf_snapshot:
            snap = tr.perf_snapshot
            total_sent = snap.get("total", 0)
            err_rate = snap.get("error_rate", 0)
            p95 = snap.get("p95_latency_ms")
            p95_str = f"{p95:.0f}ms" if p95 is not None else "-"
            perf_info = f"{total_sent} sent | {err_rate:.1%} err | p95={p95_str}"

        duration_str = f"{tr.duration:.2f}s" if tr.duration < 60 else f"{tr.duration / 60:.1f}m"

        rows.append(f"""
            <tr data-outcome="{_esc(tr.outcome)}">
                <td><span class="badge badge-{_esc(tr.outcome)}">{_esc(tr.outcome.upper())}</span></td>
                <td>{_esc(module)}</td>
                <td>{_esc(short_name)} {markers_html}</td>
                <td>{duration_str}</td>
                <td>{perf_info}</td>
            </tr>
        """)

    rows_html = "\n".join(rows)

    return f"""
    <h2>Test Results</h2>
    <div class="filter-bar">
        <button class="filter-btn active" data-filter="all">All</button>
        <button class="filter-btn" data-filter="passed">Passed</button>
        <button class="filter-btn" data-filter="failed">Failed</button>
        <button class="filter-btn" data-filter="skipped">Skipped</button>
    </div>
    <table class="results-table">
        <thead>
            <tr>
                <th>Status</th>
                <th>Module</th>
                <th>Test</th>
                <th>Duration</th>
                <th>Performance</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """


def _render_perf_details(data: ReportData) -> str:
    """Render performance detail sections for tests with perf data."""
    sections = []
    for i, tr in enumerate(data.test_results):
        if not tr.perf_snapshot or not tr.perf_samples:
            continue

        snap = tr.perf_snapshot
        thresholds = tr.thresholds or {}

        parts = tr.node_id.split("::")
        short_name = parts[-1] if parts else tr.node_id

        # Gauge cards
        total_sent = snap.get("total", 0)
        err_rate = snap.get("error_rate", 0)
        p95 = snap.get("p95_latency_ms")
        avg = snap.get("avg_latency_ms")
        throughput = snap.get("throughput_per_second", 0)

        max_err = thresholds.get("max_error_rate")
        max_p95 = thresholds.get("max_p95_latency_ms")

        err_class = "gauge-ok"
        if max_err is not None:
            err_class = "gauge-ok" if err_rate <= max_err else "gauge-bad"

        p95_class = "gauge-ok"
        if p95 is not None and max_p95 is not None:
            p95_class = "gauge-ok" if p95 <= max_p95 else "gauge-bad"

        err_threshold_str = f"<div class='gauge-threshold'>threshold: {max_err:.1%}</div>" if max_err is not None else ""
        p95_threshold_str = f"<div class='gauge-threshold'>threshold: {max_p95:.0f}ms</div>" if max_p95 is not None else ""

        p95_str = f"{p95:.0f}" if p95 is not None else "-"
        avg_str = f"{avg:.0f}" if avg is not None else "-"

        # Serialize thresholds for JS
        js_thresholds = {}
        if max_p95 is not None:
            js_thresholds["max_p95_latency_ms"] = max_p95
        target_rate = thresholds.get("target_rate")
        if target_rate is not None:
            js_thresholds["target_rate"] = target_rate

        sections.append(f"""
        <div class="perf-section">
            <h3>{_esc(short_name)}</h3>
            <script type="application/json" id="perf-thresholds-{i}">{json.dumps(js_thresholds)}</script>
            <div class="gauge-grid">
                <div class="gauge-card">
                    <div class="gauge-value" style="color: var(--accent-blue);">{total_sent}</div>
                    <div class="gauge-label">Total Sent</div>
                </div>
                <div class="gauge-card">
                    <div class="gauge-value {err_class}">{err_rate:.2%}</div>
                    <div class="gauge-label">Error Rate</div>
                    {err_threshold_str}
                </div>
                <div class="gauge-card">
                    <div class="gauge-value {p95_class}">{p95_str}ms</div>
                    <div class="gauge-label">P95 Latency</div>
                    {p95_threshold_str}
                </div>
                <div class="gauge-card">
                    <div class="gauge-value" style="color: var(--accent-blue);">{avg_str}ms</div>
                    <div class="gauge-label">Avg Latency</div>
                </div>
                <div class="gauge-card">
                    <div class="gauge-value" style="color: var(--accent-green);">{throughput:.1f}</div>
                    <div class="gauge-label">Images/sec</div>
                </div>
            </div>
            <div class="perf-charts">
                <div class="perf-chart-box">
                    <canvas id="histChart-{i}"></canvas>
                </div>
                <div class="perf-chart-box">
                    <canvas id="tpChart-{i}"></canvas>
                </div>
            </div>
            <div class="perf-charts-full" style="margin-top: 16px;">
                <div class="perf-chart-box">
                    <canvas id="scatterChart-{i}"></canvas>
                </div>
            </div>
        </div>
        """)

    if not sections:
        return ""

    inner = "\n".join(sections)
    return f"""
    <h2>Performance Details</h2>
    {inner}
    """


def _render_failures(data: ReportData) -> str:
    """Render collapsible failure details."""
    failures = [tr for tr in data.test_results if tr.outcome in ("failed", "error") and tr.error_message]
    if not failures:
        return ""

    blocks = []
    for tr in failures:
        parts = tr.node_id.split("::")
        short_name = parts[-1] if parts else tr.node_id
        blocks.append(f"""
        <div class="failure-block">
            <div class="failure-header">
                <span>{_esc(short_name)}</span>
                <span class="chevron">&#9654;</span>
            </div>
            <div class="failure-body">{_esc(tr.error_message)}</div>
        </div>
        """)

    inner = "\n".join(blocks)
    return f"""
    <h2>Failure Details</h2>
    {inner}
    """


def generate_html_report(data: ReportData) -> str:
    """
    Generate a self-contained HTML report string.

    Args:
        data: ReportData with session and per-test results.

    Returns:
        Complete HTML string ready to write to a file.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DICOM Test Report - {_esc(data.timestamp)}</title>
    {_render_css()}
</head>
<body>
    <div class="container">
        {_render_header(data)}
        {_render_summary(data)}
        {_render_config(data)}
        {_render_results_table(data)}
        {_render_perf_details(data)}
        {_render_failures(data)}
    </div>
    {_render_js(data)}
</body>
</html>"""
