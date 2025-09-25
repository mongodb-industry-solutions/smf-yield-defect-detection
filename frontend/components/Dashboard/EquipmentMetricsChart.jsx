"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import styles from './EquipmentMetricsChart.module.css';

const EquipmentMetricsChart = () => {
  const [isLoading, setIsLoading] = useState(true);

  // Load Atlas Charts URL from environment variable
  const chartUrl = process.env.NEXT_PUBLIC_ATLAS_CHART_METRICS_URL || 'https://charts.mongodb.com/placeholder';

  const handleIframeLoad = () => {
    setIsLoading(false);
  };

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3>Equipment Performance Metrics</h3>
            <p className={styles.subtitle}>
              Identify Temporal Patterns and Equipment Specific Issues
            </p>
          </div>
          <div className={styles.headerRight}>
            <span className={styles.liveIndicator}>
              <span className={styles.liveDot}></span>
              LIVE
            </span>
          </div>
        </div>

        <div className={styles.chartContainer}>
          {isLoading && (
            <div className={styles.loadingOverlay}>
              <div className={styles.spinner}></div>
              <p>Loading equipment metrics...</p>
            </div>
          )}

          <iframe
            src={chartUrl}
            className={styles.chartIframe}
            onLoad={handleIframeLoad}
            title="Equipment Performance Metrics"
            frameBorder="0"
            allowFullScreen
          />
        </div>
      </Card>
    </div>
  );
};

export default EquipmentMetricsChart;