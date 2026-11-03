import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  Dimensions,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';

const SCREEN_WIDTH = Dimensions.get('window').width;

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Default to Android emulator loopback (10.0.2.2) or local IP via env
  const API_URL =
    process.env.EXPO_PUBLIC_API_URL ||
    'http://10.0.2.2:8080/api/forecast/latest/';

  const fetchForecast = async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const url = forceRefresh ? `${API_URL}?force_refresh=true` : API_URL;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.warn('Fetch error:', err.message);
      // Secondary attempt for iOS simulator or localhost
      if (API_URL.includes('10.0.2.2')) {
        try {
          const fallbackUrl = 'http://localhost:8080/api/forecast/latest/';
          const res = await fetch(fallbackUrl);
          if (res.ok) {
            const json = await res.json();
            setData(json);
            setError(null);
            return;
          }
        } catch (_) {}
      }
      setError(err.message || 'Failed to connect to forecast gateway.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast();
  }, []);

  const points = data?.points || [];

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Commodity Price Forecast</Text>
          <Text style={styles.subtitle}>Way2Agribusiness Decision Support</Text>
        </View>
        <TouchableOpacity
          style={styles.refreshButton}
          onPress={() => fetchForecast(true)}
          disabled={loading}
        >
          <Text style={styles.refreshButtonText}>
            {loading ? '...' : 'Refresh'}
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Stale or Live Status Banner */}
        {data && (
          <View
            style={[
              styles.statusBanner,
              data.stale ? styles.staleBanner : styles.liveBanner,
            ]}
          >
            <Text style={styles.statusBannerIcon}>
              {data.stale ? '⚠️' : '✅'}
            </Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.statusBannerTitle}>
                {data.stale
                  ? 'STALE FORECAST (FALLBACK)'
                  : 'LIVE PRODUCTION FORECAST'}
              </Text>
              <Text style={styles.statusBannerText}>
                {data.stale
                  ? 'Serving stored forecast from database. Upstream real-time inference is degraded.'
                  : 'Live verified inference from model pipeline. Origin: ' +
                    (data.origin || '2025-09')}
              </Text>
            </View>
          </View>
        )}

        {/* Error Alert */}
        {error && (
          <View style={styles.errorBox}>
            <Text style={styles.errorTitle}>Connection Notice</Text>
            <Text style={styles.errorText}>{error}</Text>
            <Text style={styles.errorHint}>
              Ensure Django gateway is running on port 8080 or pass
              EXPO_PUBLIC_API_URL.
            </Text>
          </View>
        )}

        {/* Loading Indicator */}
        {loading && !data && (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color="#4f46e5" />
            <Text style={styles.loadingText}>Fetching 12-month model forecast...</Text>
          </View>
        )}

        {/* Uncertainty Fan Chart Representation */}
        {points.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Forecast Fan Chart (Uncertainty Spread)</Text>
            <Text style={styles.cardSubtitle}>
              Oct 2025 – Sep 2026 • 80% & 95% Model Prediction Intervals
            </Text>

            {/* Visual Fan Band Bars */}
            <View style={styles.fanChartContainer}>
              {points.map((p, i) => {
                const minScale = 10000;
                const maxScale = 24000;
                const range = maxScale - minScale;
                const l95Pct = Math.max(0, (p.lower_95 - minScale) / range);
                const u95Pct = Math.min(1, (p.upper_95 - minScale) / range);
                const l80Pct = Math.max(0, (p.lower_80 - minScale) / range);
                const u80Pct = Math.min(1, (p.upper_80 - minScale) / range);
                const ptPct = (p.point - minScale) / range;

                return (
                  <View key={i} style={styles.fanColumn}>
                    {/* 95% Interval Band */}
                    <View
                      style={[
                        styles.band95,
                        {
                          bottom: `${l95Pct * 100}%`,
                          height: `${(u95Pct - l95Pct) * 100}%`,
                        },
                      ]}
                    />
                    {/* 80% Interval Band */}
                    <View
                      style={[
                        styles.band80,
                        {
                          bottom: `${l80Pct * 100}%`,
                          height: `${(u80Pct - l80Pct) * 100}%`,
                        },
                      ]}
                    />
                    {/* Central Point */}
                    <View
                      style={[
                        styles.pointMarker,
                        { bottom: `${ptPct * 100}%` },
                      ]}
                    />
                    {/* Month Label */}
                    <Text style={styles.columnLabel}>
                      {p.month.substring(5, 7)}
                    </Text>
                  </View>
                );
              })}
            </View>

            {/* Legend */}
            <View style={styles.legendRow}>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: '#4f46e5' }]} />
                <Text style={styles.legendText}>Point</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendBox, { backgroundColor: '#a5b4fc' }]} />
                <Text style={styles.legendText}>80% Int</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendBox, { backgroundColor: '#e0e7ff' }]} />
                <Text style={styles.legendText}>95% Int</Text>
              </View>
            </View>
          </View>
        )}

        {/* Monthly Points List */}
        {points.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Monthly Numerical Detail</Text>
            {points.map((p, idx) => (
              <View key={idx} style={styles.pointRow}>
                <View>
                  <Text style={styles.monthText}>{p.month}</Text>
                  <Text style={styles.intervalText}>
                    80%: [{Math.round(p.lower_80).toLocaleString()} –{' '}
                    {Math.round(p.upper_80).toLocaleString()}]
                  </Text>
                  <Text style={styles.intervalTextMuted}>
                    95%: [{Math.round(p.lower_95).toLocaleString()} –{' '}
                    {Math.round(p.upper_95).toLocaleString()}]
                  </Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={styles.pricePointText}>
                    {p.point.toLocaleString(undefined, {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    })}
                  </Text>
                  <Text style={styles.unitsText}>INR / Unit</Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: '#0f172a',
  },
  subtitle: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  refreshButton: {
    backgroundColor: '#4f46e5',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 6,
  },
  refreshButtonText: {
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 13,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  statusBanner: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    alignItems: 'center',
  },
  liveBanner: {
    backgroundColor: '#f0fdf4',
    borderColor: '#bbf7d0',
    borderWidth: 1,
  },
  staleBanner: {
    backgroundColor: '#fffbeb',
    borderColor: '#fde68a',
    borderWidth: 1,
  },
  statusBannerIcon: {
    fontSize: 20,
    marginRight: 10,
  },
  statusBannerTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0f172a',
  },
  statusBannerText: {
    fontSize: 12,
    color: '#475569',
    marginTop: 2,
  },
  errorBox: {
    backgroundColor: '#fef2f2',
    borderWidth: 1,
    borderColor: '#fee2e2',
    padding: 14,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorTitle: {
    color: '#991b1b',
    fontWeight: '700',
    fontSize: 14,
  },
  errorText: {
    color: '#b91c1c',
    fontSize: 12,
    marginTop: 4,
  },
  errorHint: {
    color: '#6b7280',
    fontSize: 11,
    marginTop: 6,
  },
  loadingBox: {
    padding: 40,
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: '#64748b',
    fontSize: 14,
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0f172a',
  },
  cardSubtitle: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
    marginBottom: 16,
  },
  fanChartContainer: {
    height: 180,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    paddingTop: 10,
    paddingBottom: 25,
    borderBottomWidth: 1,
    borderBottomColor: '#cbd5e1',
  },
  fanColumn: {
    flex: 1,
    height: '100%',
    alignItems: 'center',
    position: 'relative',
  },
  band95: {
    position: 'absolute',
    width: '80%',
    backgroundColor: '#e0e7ff',
    borderRadius: 2,
  },
  band80: {
    position: 'absolute',
    width: '60%',
    backgroundColor: '#a5b4fc',
    borderRadius: 2,
  },
  pointMarker: {
    position: 'absolute',
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#4f46e5',
    marginLeft: -3,
  },
  columnLabel: {
    position: 'absolute',
    bottom: -20,
    fontSize: 10,
    color: '#64748b',
  },
  legendRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 16,
    marginTop: 14,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendBox: {
    width: 12,
    height: 12,
    borderRadius: 2,
  },
  legendText: {
    fontSize: 12,
    color: '#64748b',
  },
  pointRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  monthText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1e293b',
  },
  intervalText: {
    fontSize: 12,
    color: '#475569',
    marginTop: 2,
  },
  intervalTextMuted: {
    fontSize: 11,
    color: '#94a3b8',
    marginTop: 1,
  },
  pricePointText: {
    fontSize: 16,
    fontWeight: '800',
    color: '#2563eb',
  },
  unitsText: {
    fontSize: 10,
    color: '#94a3b8',
  },
});
