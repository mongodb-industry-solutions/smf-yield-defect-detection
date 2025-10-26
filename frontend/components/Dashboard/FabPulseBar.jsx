"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Description } from '@leafygreen-ui/typography';
import QueryTransparencyCard from '@/components/common/QueryTransparencyCard';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import styles from './FabPulseBar.module.css';

const FabPulseBar = () => {
  const { kpis: preloadedKpis, isPreloaded, isLoading: providerLoading } = useDashboardData();
  const [kpiData, setKpiData] = useState(null);
  const [isLoading, setIsLoading] = useState(!isPreloaded);
  const [showQuery, setShowQuery] = useState(false);
  const [queryTime, setQueryTime] = useState(null);

  // Add default/skeleton data for immediate display
  const defaultKPI = {
    yield: { label: 'Current Yield', value: '--', unit: '%', trend: 'up', trendValue: 0 },
    alerts: { label: 'Active Alerts', value: '--', unit: '', trend: 'up', trendValue: 0 },
    mttr: { label: 'Avg Resolution Time', value: '--', unit: 'min', trend: 'down', trendValue: 0 },
    savings: { label: 'Cost Savings', value: '--', unit: 'M', trend: 'up', trendValue: 0 }
  };

  const fetchKPIData = async () => {
    const startTime = performance.now();
    try {
      const response = await fetch('http://localhost:8000/kpi/statistics');
      const data = await response.json();
      const endTime = performance.now();

      setKpiData(data.kpi);
      setQueryTime(Math.round(endTime - startTime));
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching KPI data:', error);
      setIsLoading(false);
    }
  };

  // Use preloaded KPI data if available
  useEffect(() => {
    if (preloadedKpis && isPreloaded) {
      console.log('✅ FabPulseBar: Using preloaded KPI data');
      
      // Transform preloaded data to match expected format
      const transformedData = {
        yield: {
          label: 'Current Yield',
          value: preloadedKpis.yield?.current || 0,
          unit: '%',
          trend: preloadedKpis.yield?.trend || 'up',
          trendValue: Math.abs(preloadedKpis.yield?.current - preloadedKpis.yield?.average) || 0
        },
        alerts: {
          label: 'Active Alerts',
          value: preloadedKpis.active_alerts?.total || 0,
          unit: '',
          trend: 'up',
          trendValue: preloadedKpis.active_alerts?.critical || 0
        },
        mttr: {
          label: 'Avg Resolution Time',
          value: 45, // Placeholder - can calculate from alerts if needed
          unit: 'min',
          trend: 'down',
          trendValue: 5
        },
        savings: {
          label: 'Cost Savings',
          value: '2.1',
          unit: 'M',
          trend: 'up',
          trendValue: 15
        }
      };
      
      setKpiData(transformedData);
      setIsLoading(false);
      setQueryTime(0); // Instant from cache
      return;
    }
  }, [preloadedKpis, isPreloaded]);

  // MongoDB Aggregation Pipeline for KPI Calculation
  const kpiAggregationPipeline = [
    {
      $facet: {
        yieldStats: [
          { $match: { timestamp: { $gte: "$$last24Hours" } } },
          { $group: { _id: null, avgYield: { $avg: "$yield_percentage" } } }
        ],
        alertStats: [
          {
            $lookup: {
              from: "alerts",
              pipeline: [
                { $match: { status: "open" } },
                { $count: "total" }
              ],
              as: "activeAlerts"
            }
          }
        ],
        resolutionStats: [
          {
            $lookup: {
              from: "alerts",
              pipeline: [
                { $match: { status: "resolved", resolved_at: { $gte: "$$last7Days" } } },
                {
                  $project: {
                    resolutionTime: {
                      $subtract: ["$resolved_at", "$timestamp"]
                    }
                  }
                },
                { $group: { _id: null, avgMTTR: { $avg: "$resolutionTime" } } }
              ],
              as: "mttrData"
            }
          }
        ]
      }
    }
  ];

  useEffect(() => {
    // If we have preloaded data, skip ONLY the initial fetch
    // But still set up the auto-refresh interval
    if (!isPreloaded || !preloadedKpis) {
      // No preloaded data, do initial fetch
      console.log('🔄 FabPulseBar: No preloaded data, fetching...');
      fetchKPIData();
    } else {
      console.log('⏭️  FabPulseBar: Skipping initial fetch, using preloaded data');
    }

    // CRITICAL: Set up auto-refresh every 8 seconds regardless of preload
    // This ensures data keeps updating after initial load
    const interval = setInterval(() => {
      console.log('🔄 FabPulseBar: Auto-refreshing KPI data...');
      fetchKPIData();
    }, 8000);

    return () => clearInterval(interval);
  }, []); // Empty deps - run once on mount

  const getMetricColor = (metric, value) => {
    if (!metric.thresholds) return 'var(--color-status-good)';

    if (value >= metric.thresholds.good) return 'var(--color-status-good)';
    if (value >= metric.thresholds.warning) return 'var(--color-status-warning)';
    return 'var(--color-status-critical)';
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
        {/* Compact Single-Line Header with Inline Metrics */}
        <div className={styles.header}>
          {/* Left: Title and Badge */}
          <div className={styles.headerLeft}>
            <H3 className={styles.title}>Fab Pulse</H3>
            <Badge variant="green" className={styles.mongoBadge}>
              <Icon glyph="Database" size="small" />
            </Badge>
          </div>

          {/* Center: Inline KPI Metrics */}
          <div className={styles.metricsGrid}>
            {metrics.map(metric => (
              <div key={metric.key} className={styles.metric}>
                <span className={styles.metricLabel}>{metric.data.label}:</span>
                <div className={styles.metricValue}>
                  <span
                    className={styles.value}
                    style={{
                      color: metric.highlight ? getMetricColor(metric.data, metric.data.value) : 'var(--color-neutral-dark3)'
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

          {/* Right: LIVE indicator and Query button */}
          <div className={styles.headerRight}>
            <div className={styles.pulseIndicator}>
              <span className={styles.pulseDot}></span>
              <span className={styles.pulseText}>LIVE</span>
            </div>
            <button
              className={styles.queryButton}
              onClick={() => setShowQuery(!showQuery)}
              title="Show MongoDB Query"
            >
              <Icon glyph="Code" size="small" />
              Query
            </button>
          </div>
        </div>

        {/* MongoDB Query Transparency */}
        {showQuery && (
          <div className={styles.querySection}>
            <QueryTransparencyCard
              title="KPI Calculation Pipeline"
              query={kpiAggregationPipeline}
              queryType="aggregation"
              executionTime={queryTime}
              documentsScanned={4}
              indexUsed="timestamp_1_status_1"
              defaultOpen={true}
            />
          </div>
        )}
      </Card>
    </div>
  );
};

export default FabPulseBar;