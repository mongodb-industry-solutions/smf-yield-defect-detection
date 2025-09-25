"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import styles from './LiveParticleMonitor.module.css';

const LiveParticleMonitor = () => {
  const [isLoading, setIsLoading] = useState(true);

  // Load Atlas Charts URL from environment variable
  const chartUrl = process.env.NEXT_PUBLIC_ATLAS_CHART_PARTICLE_URL || 'https://charts.mongodb.com/placeholder';

  const handleIframeLoad = () => {
    setIsLoading(false);
  };

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3>Live Particle Monitor</h3>
            <p className={styles.subtitle}>
              Real-time particle count across all equipment • 30-min window
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
              <p>Loading particle trends...</p>
            </div>
          )}

          <iframe
            src={chartUrl}
            className={styles.chartIframe}
            onLoad={handleIframeLoad}
            title="Live Particle Monitor"
            frameBorder="0"
            allowFullScreen
          />
        </div>
      </Card>
    </div>
  );
};

export default LiveParticleMonitor;