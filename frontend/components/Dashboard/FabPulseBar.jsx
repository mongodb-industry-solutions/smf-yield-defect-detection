"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import styles from './FabPulseBar.module.css';

const FabPulseBar = () => {
  const [kpiData, setKpiData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Add default/skeleton data for immediate display
  const defaultKPI = {
    yield: { label: 'Current Yield', value: '--', unit: '%', trend: 'up', trendValue: 0 },
    alerts: { label: 'Active Alerts', value: '--', unit: '', trend: 'up', trendValue: 0 },
    mttr: { label: 'Avg Resolution Time', value: '--', unit: 'min', trend: 'down', trendValue: 0 },
    savings: { label: 'Cost Savings', value: '--', unit: 'M', trend: 'up', trendValue: 0 }
  };

  const fetchKPIData = async () => {
    try {
      const response = await fetch('http://localhost:8000/kpi/statistics');
      const data = await response.json();
      setKpiData(data.kpi);
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching KPI data:', error);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchKPIData();

    // Set up auto-refresh every 8 seconds
    const interval = setInterval(fetchKPIData, 8000);

    return () => clearInterval(interval);
  }, []);

  const getMetricColor = (metric, value) => {
    if (!metric.thresholds) return '#00684a';

    if (value >= metric.thresholds.good) return '#00684a'; // Green
    if (value >= metric.thresholds.warning) return '#FDB813'; // Yellow
    return '#DC382D'; // Red
  };

  const getTrendIcon = (trend) => {
    if (trend === 'up') return '↑';
    if (trend === 'down') return '↓';
    return '−';
  };

  // Use default data while loading to prevent layout shift
  const displayData = kpiData || defaultKPI;

  const metrics = [
    {
      key: 'yield',
      data: displayData.yield,
      format: (val) => val === '--' ? val : `${val}%`,
      highlight: true
    },
    {
      key: 'alerts',
      data: displayData.alerts,
      format: (val) => val,
      highlight: displayData.alerts.value > 10
    },
    {
      key: 'mttr',
      data: displayData.mttr,
      format: (val) => val === '--' ? val : `${val} ${displayData.mttr.unit}`,
      highlight: false
    },
    {
      key: 'savings',
      data: displayData.savings,
      format: (val) => val === '--' ? val : `$${val}${displayData.savings.unit}`,
      highlight: false
    }
  ];

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.metricsGrid}>
          {metrics.map(metric => (
            <div key={metric.key} className={styles.metric}>
              <div className={styles.metricLabel}>{metric.data.label}</div>
              <div className={styles.metricValue}>
                <span
                  className={styles.value}
                  style={{
                    color: metric.highlight ? getMetricColor(metric.data, metric.data.value) : '#1e2d3d'
                  }}
                >
                  {metric.format(metric.data.value)}
                </span>
                <span
                  className={`${styles.trend} ${metric.data.trend === 'up' ? styles.trendUp : styles.trendDown}`}
                >
                  {getTrendIcon(metric.data.trend)}
                  {Math.abs(metric.data.trendValue)}%
                </span>
              </div>
            </div>
          ))}
        </div>
        <div className={styles.pulseIndicator}>
          <span className={styles.pulseDot}></span>
          <span className={styles.pulseText}>LIVE</span>
        </div>
      </Card>
    </div>
  );
};

export default FabPulseBar;