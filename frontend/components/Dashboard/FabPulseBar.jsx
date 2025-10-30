"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Description } from '@leafygreen-ui/typography';
import QueryTransparencyCard from '@/components/common/QueryTransparencyCard';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import { kpiAPI } from '@/lib/api';
import styles from './FabPulseBar.module.css';

// Helper function to get mode-specific MTTR and Savings
const getModeSpecificKPIs = (mode) => {
  const modeConfig = {
    'normal': { mttr: 360, savings: 3.0 },   // 6 hrs, $3M
    'search': { mttr: 180, savings: 5.0 },   // 3 hrs, $5M
    'agentic': { mttr: 60, savings: 8.0 }    // 1 hr, $8M
  };
  return modeConfig[mode] || modeConfig['normal'];
};

const FabPulseBar = ({ dashboardMode = 'normal' }) => {
  const { kpis: preloadedKpis, isPreloaded, isLoading: providerLoading } = useDashboardData();
  const [kpiData, setKpiData] = useState(null);
  const [isLoading, setIsLoading] = useState(!isPreloaded);
  const [showQuery, setShowQuery] = useState(false);
  const [queryTime, setQueryTime] = useState(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

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
      const data = await kpiAPI.getKPIStatistics();
      const endTime = performance.now();

      // Override MTTR and Savings based on dashboard mode
      const modeKPIs = getModeSpecificKPIs(dashboardMode);
      const overriddenKPIs = {
        ...data.kpi,
        mttr: { ...data.kpi.mttr, value: modeKPIs.mttr },
        savings: { ...data.kpi.savings, value: modeKPIs.savings }
      };

      setKpiData(overriddenKPIs);
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
      // Handle both old format (active_alerts.total) and new format (alerts.value)
      const transformedData = {
        yield: {
          label: 'Current Yield',
          value: preloadedKpis.yield?.value || preloadedKpis.yield?.current || 0,
          unit: '%',
          trend: preloadedKpis.yield?.trend || 'up',
          trendValue: preloadedKpis.yield?.trendValue || Math.abs(preloadedKpis.yield?.current - preloadedKpis.yield?.average) || 0
        },
        alerts: {
          label: 'Active Alerts',
          value: preloadedKpis.alerts?.value || preloadedKpis.active_alerts?.total || 0,
          unit: '',
          trend: preloadedKpis.alerts?.trend || 'up',
          trendValue: preloadedKpis.alerts?.trendValue || preloadedKpis.active_alerts?.critical || 0
        },
        mttr: {
          label: 'Avg Resolution Time',
          value: preloadedKpis.mttr?.value || 45,
          unit: 'min',
          trend: preloadedKpis.mttr?.trend || 'down',
          trendValue: preloadedKpis.mttr?.trendValue || 5
        },
        savings: {
          label: 'Cost Savings',
          value: preloadedKpis.savings?.value || '2.1',
          unit: 'M',
          trend: preloadedKpis.savings?.trend || 'up',
          trendValue: preloadedKpis.savings?.trendValue || 15
        }
      };

      // Override MTTR and Savings based on dashboard mode
      const modeKPIs = getModeSpecificKPIs(dashboardMode);
      const overriddenData = {
        ...transformedData,
        mttr: { ...transformedData.mttr, value: modeKPIs.mttr },
        savings: { ...transformedData.savings, value: modeKPIs.savings }
      };

      setKpiData(overriddenData);
      setIsLoading(false);
      setQueryTime(0); // Instant from cache
      return;
    }
  }, [preloadedKpis, isPreloaded, dashboardMode]);

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
    // IMPORTANT: Include dashboardMode in deps so interval is recreated with current mode
    const interval = setInterval(() => {
      console.log('🔄 FabPulseBar: Auto-refreshing KPI data...');
      fetchKPIData();
    }, 8000);

    return () => clearInterval(interval);
  }, [dashboardMode, isPreloaded, preloadedKpis]); // Recreate interval when mode changes

  // Listen for MongoDB panel state changes
  useEffect(() => {
    const handlePanelStateChange = (event) => {
      setIsPanelOpen(event.detail.isOpen);
    };

    window.addEventListener('mongoPanelStateChange', handlePanelStateChange);

    return () => {
      window.removeEventListener('mongoPanelStateChange', handlePanelStateChange);
    };
  }, []);

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
    <div className={`${styles.container} ${isPanelOpen ? styles.grayed : ''}`}>
      <Card className={`${styles.card} ${isPanelOpen ? styles.cardGrayed : ''}`}>
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