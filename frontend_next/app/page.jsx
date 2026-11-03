'use client';

import React, { useState, useEffect } from 'react';

export default function ForecastDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [apiUrl, setApiUrl] = useState(
    process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/forecast/latest/'
  );

  const fastApiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL;

  async function loadStaticFallback() {
    try {
      const staticRes = await fetch('/forecast_static.json');
      if (staticRes.ok) {
        const staticPoints = await staticRes.json();
        setData({
          run_id: null,
          created_at: null,
          origin: '2025-09',
          model_version: 'SARIMA(1,1,1)(1,0,0)[12]',
          stale: true,
          source: 'static_snapshot',
          points: staticPoints,
        });
        setError(null);
      } else {
        throw new Error('Static fallback could not be loaded');
      }
    } catch (fallbackErr) {
      console.error('Static fallback error:', fallbackErr);
      setError('Failed to reach backend and static fallback is unavailable.');
    }
  }

  async function fetchForecast(force = false) {
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    try {
      const url = new URL(apiUrl);
      if (force) url.searchParams.set('force_refresh', 'true');
      const res = await fetch(url.toString(), {
        cache: 'no-store',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`API returned HTTP ${res.status}: ${res.statusText}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err) {
      clearTimeout(timeoutId);
      console.warn('Backend fetch failed or timed out (8s limit), loading static snapshot:', err);
      await loadStaticFallback();
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchForecast();
  }, [apiUrl]);

  const points = data?.points || [];
  const isStaticSnapshot = data?.source === 'static_snapshot';

  // SVG Fan Chart Calculations
  const chartWidth = 800;
  const chartHeight = 360;
  const padding = { top: 30, right: 40, bottom: 50, left: 70 };

  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  let allValues = [];
  points.forEach(p => {
    allValues.push(p.point, p.lower_80, p.upper_80, p.lower_95, p.upper_95);
  });

  const minVal = allValues.length ? Math.floor(Math.min(...allValues) / 1000) * 1000 : 10000;
  const maxVal = allValues.length ? Math.ceil(Math.max(...allValues) / 1000) * 1000 : 25000;
  const valRange = maxVal - minVal || 1;

  function getX(index) {
    if (points.length <= 1) return padding.left + innerWidth / 2;
    return padding.left + (index / (points.length - 1)) * innerWidth;
  }

  function getY(val) {
    return padding.top + innerHeight - ((val - minVal) / valRange) * innerHeight;
  }

  // Create SVG path strings for fan chart bands
  const area95Path = points.length > 0 ? (
    points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.upper_95)}`).join(' ') +
    ' ' +
    points.slice().reverse().map((p, i) => `L ${getX(points.length - 1 - i)} ${getY(p.lower_95)}`).join(' ') +
    ' Z'
  ) : '';

  const area80Path = points.length > 0 ? (
    points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.upper_80)}`).join(' ') +
    ' ' +
    points.slice().reverse().map((p, i) => `L ${getX(points.length - 1 - i)} ${getY(p.lower_80)}`).join(' ') +
    ' Z'
  ) : '';

  const pointLinePath = points.length > 0 ? (
    points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.point)}`).join(' ')
  ) : '';

  const yTicks = [minVal, minVal + valRange * 0.25, minVal + valRange * 0.5, minVal + valRange * 0.75, maxVal];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 20px', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {/* Header */}
      <header style={{ marginBottom: 28, borderBottom: '1px solid #e2e8f0', paddingBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 700, margin: '0 0 6px 0', color: '#0f172a' }}>
              Monthly Commodity Price Forecast & Decision Support
            </h1>
            <p style={{ margin: 0, color: '#64748b', fontSize: 14 }}>
              Next.js Real-Time Forecast Client &bull; Connected to Django Gateway & FastAPI
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <a
              href="/report.html"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#4338ca',
                textDecoration: 'none',
                fontWeight: 600,
                fontSize: 14,
                padding: '8px 14px',
                borderRadius: 6,
                backgroundColor: '#eef2ff',
                border: '1px solid #c7d2fe',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              Full analysis (Questions 1-9)
            </a>

            {fastApiUrl && (
              <a
                href={`${fastApiUrl.replace(/\/+$/, '')}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: '#0f766e',
                  textDecoration: 'none',
                  fontWeight: 600,
                  fontSize: 14,
                  padding: '8px 14px',
                  borderRadius: 6,
                  backgroundColor: '#f0fdfa',
                  border: '1px solid #99f6e4',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                API docs
              </a>
            )}

            <button
              onClick={() => fetchForecast(true)}
              disabled={loading}
              style={{
                backgroundColor: '#2563eb',
                color: '#fff',
                border: 'none',
                padding: '8px 16px',
                borderRadius: 6,
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading ? 'Refreshing...' : 'Refresh Forecast'}
            </button>
          </div>
        </div>
      </header>

      {/* Static Snapshot Waking Up Banner */}
      {isStaticSnapshot && (
        <div
          data-testid="static-snapshot-banner"
          style={{
            backgroundColor: '#eff6ff',
            border: '1px solid #bfdbfe',
            color: '#1e40af',
            padding: '12px 18px',
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 600,
            marginBottom: 20,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>⏳</span>
            <span>Live backend is waking up (free hosting). Showing the saved forecast.</span>
          </div>
          <button
            onClick={() => fetchForecast(true)}
            disabled={loading}
            style={{
              backgroundColor: '#1d4ed8',
              color: '#ffffff',
              border: 'none',
              padding: '6px 14px',
              borderRadius: 6,
              fontWeight: 600,
              fontSize: 13,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Retrying...' : 'Retry live'}
          </button>
        </div>
      )}

      {/* Status & Banner Alerts */}
      {data && !isStaticSnapshot && (
        <div style={{ marginBottom: 24, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {data.stale ? (
            <div style={{
              backgroundColor: '#fffbeb',
              border: '1px solid #fef3c7',
              color: '#b45309',
              padding: '10px 16px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
            }}>
              <span style={{ fontSize: 18 }}>⚠️</span>
              <span>STALE FORECAST (FALLBACK): Serving cached or stored forecast run from database because upstream live inference is degraded.</span>
            </div>
          ) : (
            <div style={{
              backgroundColor: '#f0fdf4',
              border: '1px solid #dcfce7',
              color: '#15803d',
              padding: '10px 16px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
            }}>
              <span style={{ fontSize: 18 }}>✅</span>
              <span>LIVE FORECAST: Connected to active backend. Model provenance verified with zero stale lag.</span>
            </div>
          )}
        </div>
      )}

      {/* Metadata Cards */}
      {data && (
        <div style={{ marginBottom: 24, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, width: '100%' }}>
          <div style={{ backgroundColor: '#fff', padding: 16, borderRadius: 8, border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Model Specification</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4, color: '#0f172a' }}>{data.model_version || 'SARIMA(1,1,1)(1,0,0)[12]'}</div>
          </div>
          <div style={{ backgroundColor: '#fff', padding: 16, borderRadius: 8, border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Forecast Origin</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4, color: '#0f172a' }}>{data.origin || '2025-09'}</div>
          </div>
          <div style={{ backgroundColor: '#fff', padding: 16, borderRadius: 8, border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Serving Tier</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4, color: '#0f172a' }}>{data.source || 'django_gateway'}</div>
          </div>
          <div style={{ backgroundColor: '#fff', padding: 16, borderRadius: 8, border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Horizon Mean</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4, color: '#0f172a' }}>
              {points.length ? (points.reduce((acc, p) => acc + p.point, 0) / points.length).toFixed(1) : 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* Error View */}
      {error && (
        <div style={{
          backgroundColor: '#fef2f2',
          border: '1px solid #fee2e2',
          color: '#991b1b',
          padding: 16,
          borderRadius: 8,
          marginBottom: 24,
        }}>
          <strong>Connection Error:</strong> {error}
          <div style={{ marginTop: 8, fontSize: 13 }}>
            Make sure the backend is running (`python manage.py runserver 8080` or `docker compose up`).
          </div>
        </div>
      )}

      {/* Loading View */}
      {loading && !data && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b' }}>
          <div style={{ fontSize: 18, fontWeight: 600 }}>Loading forecast model and intervals...</div>
        </div>
      )}

      {/* Fan Chart Visualizer */}
      {points.length > 0 && (
        <div style={{ backgroundColor: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', padding: 24, marginBottom: 28, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 16px 0', color: '#0f172a' }}>
            12-Month Price Projection & Uncertainty Fan Chart
          </h2>
          <div style={{ overflowX: 'auto' }}>
            <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} style={{ width: '100%', height: 'auto', minWidth: 600 }}>
              {/* Grid lines and Y-axis labels */}
              {yTicks.map((tick, idx) => (
                <g key={idx}>
                  <line
                    x1={padding.left}
                    y1={getY(tick)}
                    x2={chartWidth - padding.right}
                    y2={getY(tick)}
                    stroke="#f1f5f9"
                    strokeWidth="1"
                  />
                  <text
                    x={padding.left - 10}
                    y={getY(tick) + 4}
                    textAnchor="end"
                    fontSize="11"
                    fill="#94a3b8"
                    fontFamily="monospace"
                  >
                    {Math.round(tick).toLocaleString()}
                  </text>
                </g>
              ))}

              {/* 95% Confidence Fan Area */}
              <path d={area95Path} fill="#e0e7ff" opacity="0.6" />

              {/* 80% Confidence Fan Area */}
              <path d={area80Path} fill="#c7d2fe" opacity="0.8" />

              {/* Central Point Forecast Line */}
              <path d={pointLinePath} fill="none" stroke="#4f46e5" strokeWidth="2.5" />

              {/* Points & X-axis labels */}
              {points.map((p, i) => (
                <g key={i}>
                  <circle cx={getX(i)} cy={getY(p.point)} r="4" fill="#4f46e5" stroke="#fff" strokeWidth="1.5" />
                  <text
                    x={getX(i)}
                    y={chartHeight - padding.bottom + 20}
                    textAnchor="middle"
                    fontSize="11"
                    fill="#64748b"
                    fontFamily="monospace"
                    transform={`rotate(-25, ${getX(i)}, ${chartHeight - padding.bottom + 20})`}
                  >
                    {p.month.substring(0, 7)}
                  </text>
                </g>
              ))}
            </svg>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 16, fontSize: 13, color: '#475569' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 14, height: 3, backgroundColor: '#4f46e5', display: 'inline-block' }}></span>
              <span>Point Forecast</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 14, height: 14, backgroundColor: '#c7d2fe', display: 'inline-block', borderRadius: 2 }}></span>
              <span>80% Prediction Interval</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 14, height: 14, backgroundColor: '#e0e7ff', display: 'inline-block', borderRadius: 2 }}></span>
              <span>95% Prediction Interval</span>
            </div>
          </div>
        </div>
      )}

      {/* Monthly Forecast Table */}
      {points.length > 0 && (
        <div style={{ backgroundColor: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid #e2e8f0' }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#0f172a' }}>Operational Numerical Horizon Table</h3>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 14 }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                  <th style={{ padding: '12px 16px' }}>Target Month</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Point Forecast</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>80% Lower</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>80% Upper</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>95% Lower</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>95% Upper</th>
                </tr>
              </thead>
              <tbody>
                {points.map((p, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px 16px', fontWeight: 600, color: '#0f172a' }}>{p.month}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700, color: '#2563eb' }}>
                      {typeof p.point === 'number' ? p.point.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : p.point}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', color: '#64748b' }}>
                      {typeof p.lower_80 === 'number' ? p.lower_80.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : p.lower_80}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', color: '#64748b' }}>
                      {typeof p.upper_80 === 'number' ? p.upper_80.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : p.upper_80}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', color: '#94a3b8' }}>
                      {typeof p.lower_95 === 'number' ? p.lower_95.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : p.lower_95}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', color: '#94a3b8' }}>
                      {typeof p.upper_95 === 'number' ? p.upper_95.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : p.upper_95}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
