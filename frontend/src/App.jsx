import React, { useState, useEffect, useMemo } from 'react';

const API_BASE = '';

export default function App() {
  const [health, setHealth] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [metricsData, setMetricsData] = useState(null);
  const [modelData, setModelData] = useState(null);
  const [dataQuality, setDataQuality] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [driftData, setDriftData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [runMessage, setRunMessage] = useState(null);
  const [chartView, setChartView] = useState('recent'); // 'recent' or 'full'
  const [show80, setShow80] = useState(true);
  const [show95, setShow95] = useState(true);
  const [showNaive, setShowNaive] = useState(true);

  // Fetch all endpoints
  const fetchAllData = async () => {
    setLoading(true);
    try {
      const [hRes, fcRes, mRes, modRes, dqRes, histRes, drRes] = await Promise.all([
        fetch(`${API_BASE}/health`).then((r) => r.json()),
        fetch(`${API_BASE}/api/v1/forecast`).then((r) => r.json()),
        fetch(`${API_BASE}/api/v1/metrics`).then((r) => r.json()),
        fetch(`${API_BASE}/api/v1/model`).then((r) => r.json()),
        fetch(`${API_BASE}/api/v1/data-quality`).then((r) => r.json()),
        fetch(`${API_BASE}/api/v1/history`).then((r) => r.json()),
        fetch(`${API_BASE}/api/v1/monitoring/drift`).then((r) => r.json()),
      ]);

      setHealth(hRes);
      setForecastData(fcRes);
      setMetricsData(mRes);
      setModelData(modRes);
      setDataQuality(dqRes);
      setHistoryData(histRes.history || []);
      setDriftData(drRes);
    } catch (err) {
      console.error('Failed to fetch data from API:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  // Trigger Forecast Pipeline Run
  const handleRunPipeline = async () => {
    setRunningPipeline(true);
    setRunMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/forecast/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version_tag: 'dashboard_manual_trigger' }),
      });
      const data = await res.json();
      if (res.ok) {
        setRunMessage(`Success: Pipeline run ${data.run_id} completed in ${data.duration_ms}ms (Parity verified: ${data.parity_verified})`);
        await fetchAllData();
      } else {
        setRunMessage(`Run failed: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      setRunMessage(`Error triggering pipeline: ${err.message}`);
    } finally {
      setRunningPipeline(false);
    }
  };

  // Monthly descriptions
  const monthlyDynamics = {
    '2025-10-01': 'Initial baseline near current price level',
    '2025-11-01': 'Slight seasonal softening into winter',
    '2025-12-01': 'Year-end consolidation',
    '2026-01-01': 'Winter seasonal low',
    '2026-02-01': 'Projected annual trough (~14,720)',
    '2026-03-01': 'Early spring price firming',
    '2026-04-01': 'Spring stabilization plateau',
    '2026-05-01': 'Pre-summer plateau (~15,535)',
    '2026-06-01': 'Mid-summer price firming',
    '2026-07-01': 'Projected annual peak (~15,960)',
    '2026-08-01': 'Late summer moderating',
    '2026-09-01': 'Horizon close firming (~15,894)',
  };

  // SVG Chart Calculations
  const chartPoints = useMemo(() => {
    if (!historyData.length || !forecastData?.forecast?.length) return null;

    // Filter by view
    let hist = historyData;
    if (chartView === 'recent') {
      hist = historyData.filter((d) => d.date >= '2023-01-01');
    }

    const forecast = forecastData.forecast;
    const allPrices = [
      ...hist.filter((d) => d.price !== null).map((d) => d.price),
      ...forecast.map((f) => f.upper_95),
      ...forecast.map((f) => f.lower_95),
    ];

    const minPrice = Math.floor(Math.min(...allPrices) / 1000) * 1000;
    const maxPrice = Math.ceil(Math.max(...allPrices) / 1000) * 1000;

    // Total width & height
    const width = 1000;
    const height = 340;
    const padding = { top: 20, right: 30, bottom: 40, left: 60 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const totalSteps = hist.length + forecast.length;
    const getX = (idx) => padding.left + (idx / (totalSteps - 1)) * chartW;
    const getY = (price) => padding.top + chartH - ((price - minPrice) / (maxPrice - minPrice)) * chartH;

    // Map history points
    const mappedHist = hist.map((d, i) => ({
      ...d,
      x: getX(i),
      y: d.price !== null ? getY(d.price) : null,
    }));

    // Map forecast points
    const mappedForecast = forecast.map((f, i) => ({
      ...f,
      x: getX(hist.length + i),
      y: getY(f.point_forecast),
      yL80: getY(f.lower_80),
      yU80: getY(f.upper_80),
      yL95: getY(f.lower_95),
      yU95: getY(f.upper_95),
      yNaive: getY(15750.0), // Naive last value
    }));

    return {
      width,
      height,
      padding,
      chartW,
      chartH,
      minPrice,
      maxPrice,
      mappedHist,
      mappedForecast,
      histCutoffX: mappedHist.length ? mappedHist[mappedHist.length - 1].x : 0,
    };
  }, [historyData, forecastData, chartView]);

  return (
    <div className="dashboard-container">
      {/* Header Bar */}
      <header className="header-bar">
        <div className="header-title">
          <h1>Commodity Price Forecasting & Decision Support Platform</h1>
          <div className="header-subtitle">
            Model: <strong>{forecastData?.model_name || 'SARIMA(1,1,1)(1,0,0)[12]'}</strong> (Rolling 120, Log) | Origin: <strong>{forecastData?.forecast_origin || 'September 2025'}</strong> | Horizon: <strong>{forecastData?.forecast_horizon || 'Oct 2025 – Sep 2026'}</strong>
          </div>
        </div>
        <div className="header-actions">
          <span className={`status-pill ${health?.status === 'HEALTHY' ? 'healthy' : 'degraded'}`}>
            ● {health?.status || 'CHECKING...'}
          </span>
          <button className="btn-secondary" onClick={fetchAllData} disabled={loading}>
            Refresh
          </button>
          <button className="btn-primary" onClick={handleRunPipeline} disabled={runningPipeline}>
            {runningPipeline ? 'Running...' : '▶ Run Pipeline'}
          </button>
        </div>
      </header>

      {/* Execution Feedback Notification */}
      {runMessage && (
        <div className={`alert-banner ${runMessage.includes('Success') ? 'info' : 'warning'}`}>
          <strong>{runMessage}</strong>
        </div>
      )}

      {/* Top KPI Cards */}
      <section className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">12-Month Mean Forecast</div>
          <div className="kpi-value">{forecastData?.mean_point_forecast ? forecastData.mean_point_forecast.toLocaleString() : '15,429.8'}</div>
          <div className="kpi-subtext">Trading Range: 14,721 – 15,961</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Latest Price (Sep 2025)</div>
          <div className="kpi-value">{forecastData?.origin_price ? forecastData.origin_price.toLocaleString() : '15,750'}</div>
          <div className="kpi-subtext">Post-Gap Regime (~14,500 – 16,000)</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Sep 2026 Target Price</div>
          <div className="kpi-value">{forecastData?.forecast ? forecastData.forecast[11].point_forecast.toLocaleString() : '15,894.5'}</div>
          <div className="kpi-subtext">80% Interval: [12,562, 20,111]</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Holdout Out-of-Sample MAE</div>
          <div className="kpi-value">{metricsData?.primary_model_metrics?.mae || '1,139.48'}</div>
          <div className="kpi-subtext highlight-green">
            +{metricsData?.relative_mae_improvement_pct || '1.80'}% advantage vs Naive ({metricsData?.benchmark_metrics?.mae || '1,160.33'})
          </div>
        </div>
      </section>

      {/* Interactive Time-Series Chart */}
      <section className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Commodity Price Trajectory & 12-Month Operational Forecast</div>
            <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Historical monthly observations, 30-month unobserved gap representation, and model-based 80% & 95% uncertainty bands
            </div>
          </div>
          <div className="chart-controls">
            <button
              className={`toggle-btn ${chartView === 'recent' ? 'active' : ''}`}
              onClick={() => setChartView('recent')}
            >
              Recent Regime (2023–2026)
            </button>
            <button
              className={`toggle-btn ${chartView === 'full' ? 'active' : ''}`}
              onClick={() => setChartView('full')}
            >
              Full Series (2005–2026)
            </button>
            <button
              className={`toggle-btn ${show80 ? 'active' : ''}`}
              onClick={() => setShow80(!show80)}
            >
              80% Band
            </button>
            <button
              className={`toggle-btn ${show95 ? 'active' : ''}`}
              onClick={() => setShow95(!show95)}
            >
              95% Band
            </button>
            <button
              className={`toggle-btn ${showNaive ? 'active' : ''}`}
              onClick={() => setShowNaive(!showNaive)}
            >
              Naive Baseline
            </button>
          </div>
        </div>

        {/* SVG Visualization */}
        <div className="chart-svg-container">
          {chartPoints ? (
            <svg viewBox={`0 0 ${chartPoints.width} ${chartPoints.height}`} style={{ width: '100%', height: '100%' }}>
              <defs>
                <linearGradient id="forecastBand80" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity="0.22" />
                  <stop offset="100%" stopColor="#2563eb" stopOpacity="0.08" />
                </linearGradient>
                <linearGradient id="forecastBand95" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity="0.10" />
                  <stop offset="100%" stopColor="#2563eb" stopOpacity="0.03" />
                </linearGradient>
              </defs>

              {/* Grid Lines & Y-axis labels */}
              {[chartPoints.minPrice, (chartPoints.minPrice + chartPoints.maxPrice) / 2, chartPoints.maxPrice].map((p, i) => {
                const y = chartPoints.padding.top + chartPoints.chartH - ((p - chartPoints.minPrice) / (chartPoints.maxPrice - chartPoints.minPrice)) * chartPoints.chartH;
                return (
                  <g key={i}>
                    <line x1={chartPoints.padding.left} y1={y} x2={chartPoints.width - chartPoints.padding.right} y2={y} stroke="#e2e8f0" strokeDasharray="3 3" />
                    <text x={chartPoints.padding.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#94a3b8" fontFamily="monospace">
                      {Math.round(p).toLocaleString()}
                    </text>
                  </g>
                );
              })}

              {/* Forecast Shaded Bands (95% and 80%) */}
              {show95 && (
                <polygon
                  points={[
                    ...chartPoints.mappedForecast.map((f) => `${f.x},${f.yU95}`),
                    ...[...chartPoints.mappedForecast].reverse().map((f) => `${f.x},${f.yL95}`),
                  ].join(' ')}
                  fill="url(#forecastBand95)"
                />
              )}
              {show80 && (
                <polygon
                  points={[
                    ...chartPoints.mappedForecast.map((f) => `${f.x},${f.yU80}`),
                    ...[...chartPoints.mappedForecast].reverse().map((f) => `${f.x},${f.yL80}`),
                  ].join(' ')}
                  fill="url(#forecastBand80)"
                />
              )}

              {/* Historical Line */}
              {chartPoints.mappedHist.map((pt, idx, arr) => {
                if (idx === 0 || pt.y === null || arr[idx - 1].y === null) return null;
                const prev = arr[idx - 1];
                return (
                  <line
                    key={`hist-${idx}`}
                    x1={prev.x}
                    y1={prev.y}
                    x2={pt.x}
                    y2={pt.y}
                    stroke={pt.segment === 'segment_2' ? '#1e3a8a' : '#0284c7'}
                    strokeWidth="2.2"
                  />
                );
              })}

              {/* Origin Divider Line */}
              <line
                x1={chartPoints.histCutoffX}
                y1={chartPoints.padding.top}
                x2={chartPoints.histCutoffX}
                y2={chartPoints.height - chartPoints.padding.bottom}
                stroke="#64748b"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
              <text x={chartPoints.histCutoffX + 6} y={chartPoints.padding.top + 14} fontSize="11" fontWeight="600" fill="#2563eb">
                Forecast Origin (Sep 2025) →
              </text>

              {/* Naive Baseline Line */}
              {showNaive && (
                <line
                  x1={chartPoints.histCutoffX}
                  y1={chartPoints.mappedForecast[0].yNaive}
                  x2={chartPoints.mappedForecast[chartPoints.mappedForecast.length - 1].x}
                  y2={chartPoints.mappedForecast[0].yNaive}
                  stroke="#dc2626"
                  strokeWidth="1.6"
                  strokeDasharray="3 3"
                />
              )}

              {/* Forecast Trajectory Line */}
              {chartPoints.mappedForecast.map((pt, idx, arr) => {
                if (idx === 0) {
                  const lastHist = chartPoints.mappedHist[chartPoints.mappedHist.length - 1];
                  return (
                    <g key="fc-start">
                      <line x1={lastHist.x} y1={lastHist.y} x2={pt.x} y2={pt.y} stroke="#2563eb" strokeWidth="2.6" />
                      <circle cx={pt.x} cy={pt.y} r="3.5" fill="#2563eb" />
                    </g>
                  );
                }
                const prev = arr[idx - 1];
                return (
                  <g key={`fc-${idx}`}>
                    <line x1={prev.x} y1={prev.y} x2={pt.x} y2={pt.y} stroke="#2563eb" strokeWidth="2.6" />
                    <circle cx={pt.x} cy={pt.y} r="3.5" fill="#2563eb" />
                  </g>
                );
              })}

              {/* Legend */}
              <g transform={`translate(${chartPoints.padding.left + 10}, ${chartPoints.height - 12})`} fontSize="11" fill="#475569">
                <rect x="0" y="-8" width="12" height="3" fill="#1e3a8a" />
                <text x="18" y="-5">Historical Price</text>

                <rect x="130" y="-8" width="12" height="3" fill="#2563eb" />
                <circle cx="136" cy="-6" r="3" fill="#2563eb" />
                <text x="148" y="-5">SARIMA Forecast</text>

                <rect x="270" y="-8" width="12" height="3" fill="#dc2626" />
                <text x="288" y="-5">Naive Baseline (15,750)</text>

                <rect x="440" y="-8" width="14" height="8" fill="rgba(37,99,235,0.2)" />
                <text x="460" y="-1">80% & 95% Intervals</text>
              </g>
            </svg>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>Loading chart data...</div>
          )}
        </div>
      </section>

      {/* Monthly Forecast Table */}
      <section className="card">
        <div className="card-header">
          <div className="card-title">12-Month Operational Forecast Table (October 2025 to September 2026)</div>
          <span className="card-badge">SARIMA Rolling 120 Log</span>
        </div>
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Forecast Month</th>
                <th className="numeric">Point Forecast</th>
                <th className="numeric">80% Lower Bound</th>
                <th className="numeric">80% Upper Bound</th>
                <th className="numeric">95% Lower Bound</th>
                <th className="numeric">95% Upper Bound</th>
                <th>Expected Market Dynamics</th>
              </tr>
            </thead>
            <tbody>
              {forecastData?.forecast?.map((row) => (
                <tr key={row.month}>
                  <td style={{ fontWeight: 600 }}>{row.month}</td>
                  <td className="numeric" style={{ fontWeight: 700, color: '#2563eb' }}>
                    {row.point_forecast.toLocaleString(undefined, { minimumFractionDigits: 1 })}
                  </td>
                  <td className="numeric">{row.lower_80.toLocaleString(undefined, { minimumFractionDigits: 1 })}</td>
                  <td className="numeric">{row.upper_80.toLocaleString(undefined, { minimumFractionDigits: 1 })}</td>
                  <td className="numeric" style={{ color: '#64748b' }}>{row.lower_95.toLocaleString(undefined, { minimumFractionDigits: 1 })}</td>
                  <td className="numeric" style={{ color: '#64748b' }}>{row.upper_95.toLocaleString(undefined, { minimumFractionDigits: 1 })}</td>
                  <td>{monthlyDynamics[row.month] || 'Stabilization plateau'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Two-Column Grid: Holdout Performance & Data Quality */}
      <div className="two-col-grid">
        {/* Left: Holdout Performance */}
        <section className="card">
          <div className="card-header">
            <div className="card-title">Out-of-Sample Holdout Audit (Oct 2024 – Sep 2025)</div>
            <span className="card-badge">Strict Pre-Holdout Training</span>
          </div>
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th className="numeric">MAE</th>
                  <th className="numeric">RMSE</th>
                  <th className="numeric">sMAPE</th>
                  <th className="numeric">MASE</th>
                  <th className="numeric">Signed Bias</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ background: '#eff6ff', fontWeight: 600 }}>
                  <td>{metricsData?.primary_model_metrics?.model || 'SARIMA(1,1,1)(1,0,0)[12]'}</td>
                  <td className="numeric" style={{ color: '#2563eb' }}>{metricsData?.primary_model_metrics?.mae}</td>
                  <td className="numeric">{metricsData?.primary_model_metrics?.rmse}</td>
                  <td className="numeric">{metricsData?.primary_model_metrics?.smape}%</td>
                  <td className="numeric">{metricsData?.primary_model_metrics?.mase}</td>
                  <td className="numeric">+{metricsData?.primary_model_metrics?.bias || '495.8'}</td>
                </tr>
                <tr>
                  <td>{metricsData?.benchmark_metrics?.model || 'Naive Benchmark'}</td>
                  <td className="numeric">{metricsData?.benchmark_metrics?.mae}</td>
                  <td className="numeric">{metricsData?.benchmark_metrics?.rmse}</td>
                  <td className="numeric">{metricsData?.benchmark_metrics?.smape}%</td>
                  <td className="numeric">{metricsData?.benchmark_metrics?.mase}</td>
                  <td className="numeric">+{metricsData?.benchmark_metrics?.bias || '546.0'}</td>
                </tr>
                {metricsData?.comparison_metrics && (
                  <tr>
                    <td>{metricsData?.comparison_metrics?.model}</td>
                    <td className="numeric">{metricsData?.comparison_metrics?.mae}</td>
                    <td className="numeric">{metricsData?.comparison_metrics?.rmse}</td>
                    <td className="numeric">{metricsData?.comparison_metrics?.smape}%</td>
                    <td className="numeric">{metricsData?.comparison_metrics?.mase}</td>
                    <td className="numeric">+{metricsData?.comparison_metrics?.bias || '766.9'}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 14, lineHeight: 1.5 }}>
            {metricsData?.interpretation || 'SARIMA modestly outperforms the Naive benchmark by 1.80% on holdout MAE.'}
          </div>
        </section>

        {/* Right: Data Quality & Governance */}
        <section className="card">
          <div className="card-header">
            <div className="card-title">Data Quality & Governance Audit</div>
            <span className="card-badge">Variant B Primary</span>
          </div>
          <div style={{ fontSize: '0.825rem', color: '#334155' }}>
            <div style={{ marginBottom: 12 }}>
              <strong>Total Monthly Observations:</strong> {dataQuality?.total_months || 249} months (Jan 2005 – Sep 2025)
              <br />
              <strong>Valid Observed Points:</strong> {dataQuality?.valid_observations || 219} months
              <br />
              <strong>Missing Copied Block:</strong> {dataQuality?.missing_data_block?.months_count || 30} months (Jun 2021 – Nov 2023)
            </div>
            <div className="alert-banner warning" style={{ marginBottom: 12, padding: '10px 14px' }}>
              <strong>Zero-Interpolation Policy:</strong> The duplicated 30-month block is represented as unobserved NaNs. Observations before and after are strictly never treated as contiguous.
            </div>
            <div className="alert-banner info" style={{ padding: '10px 14px' }}>
              <strong>Drift & Retraining Status:</strong> {driftData?.status || 'OPERATIONAL'} (Distribution: {driftData?.forecast_drift?.status || 'STABLE'}). Retraining triggers require ≥12 newly observed contiguous months.
            </div>
          </div>
        </section>
      </div>

      {/* Limitations and Disclaimer Footer */}
      <footer className="footer-disclaimer">
        <strong>Explicit Technical & Business Limitations:</strong> State-space Kalman filtering over the 30-month gap handles missing data without artificial bias, but cannot reconstruct true unobserved market volatility. Segment 2 contains 22 months post-2023, providing fewer than 2 annual cycles in the current price regime. The primary model improves over the Naive baseline by a modest 1.8%; budget allocations should treat the Naive carry-forward scenario as an equally viable baseline. No post-September 2025 prices are observed or fabricated.
      </footer>
    </div>
  );
}
