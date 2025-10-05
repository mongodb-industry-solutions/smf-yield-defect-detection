"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import styles from './LiveParticleMonitor.module.css';

const LiveTemperatureMonitor = () => {
  const [isLoading, setIsLoading] = useState(true);

  // Load Atlas Charts URL from environment variable
  const chartUrl = process.env.NEXT_PUBLIC_ATLAS_CHART_TEMPERATURE_URL || 'https://charts.mongodb.com/placeholder';

  const handleIframeLoad = () => {
    setIsLoading(false);
  };

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3>Temperature Monitor</h3>
            <p className={styles.subtitle}>
              Real-time temperature across equipment • 30-min window
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
              <p>Loading temperature trends...</p>
            </div>
          )}

          <iframe
            src={chartUrl}
            className={styles.chartIframe}
            onLoad={handleIframeLoad}
            title="Live Temperature Monitor"
            frameBorder="0"
            allowFullScreen
          />
        </div>
      </Card>
    </div>
  );
};

export default LiveTemperatureMonitor;
