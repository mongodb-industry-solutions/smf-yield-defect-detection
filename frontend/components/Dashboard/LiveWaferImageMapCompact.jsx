"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import styles from './LiveWaferImageMapCompact.module.css';

const LiveWaferImageMapCompact = () => {
  const [waferData, setWaferData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedWafer, setSelectedWafer] = useState(0);

  // Fetch wafer data with thumbnails
  const fetchWaferData = async () => {
    try {
      const response = await fetch('http://localhost:8000/wafers/latest?limit=3');
      const data = await response.json();

      if (data.wafers && data.wafers.length > 0) {
        setWaferData(data.wafers);
        setIsLoading(false);
      }
    } catch (error) {
      console.error('Error fetching wafer data:', error);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWaferData();
    const interval = setInterval(fetchWaferData, 30000);
    return () => clearInterval(interval);
  }, []);

  const currentWafer = waferData?.[selectedWafer];

  const getWaferImageSrc = (wafer) => {
    if (wafer?.ink_map?.full_image_base64) {
      return `data:image/png;base64,${wafer.ink_map.full_image_base64}`;
    }
    return null;
  };

  if (isLoading) {
    return (
      <div className={styles.container}>
        <Card className={styles.card}>
          <div className={styles.header}>
            <div className={styles.headerLeft}>
              <h3>Live Wafer Defect Map</h3>
              <p className={styles.subtitle}>
                Real-time wafer inspection • Defect pattern analysis
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
            <div className={styles.loadingOverlay}>
              <div className={styles.spinner}></div>
              <p>Loading wafer data...</p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3>Live Wafer Defect Map</h3>
            <p className={styles.subtitle}>
              Real-time wafer inspection • Defect pattern analysis
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
          {/* Main content area */}
          <div className={styles.contentWrapper}>
            {/* Left: Wafer Image */}
            <div className={styles.imageSection}>
              <div className={styles.imageContainer}>
                {currentWafer && getWaferImageSrc(currentWafer) ? (
                  <img
                    src={getWaferImageSrc(currentWafer)}
                    alt={`Wafer ${currentWafer.wafer_id}`}
                    className={styles.waferImage}
                  />
                ) : (
                  <div className={styles.noImage}>Loading wafer image...</div>
                )}
              </div>

              {/* Wafer info below image */}
              <div className={styles.waferInfo}>
                <div className={styles.currentWaferId}>
                  {currentWafer ? currentWafer.wafer_id : '--'}
                </div>
                <div className={styles.currentLotId}>
                  {currentWafer ? currentWafer.lot_id : '--'}
                </div>
              </div>

              {/* Wafer selector tabs */}
              <div className={styles.waferSelector}>
                {waferData?.map((wafer, index) => (
                  <button
                    key={wafer.wafer_id}
                    className={`${styles.waferTab} ${index === selectedWafer ? styles.active : ''}`}
                    onClick={() => setSelectedWafer(index)}
                  >
                    {wafer.wafer_id.split('_').pop()}
                  </button>
                ))}
              </div>
            </div>

        {/* Right: Compact Stats */}
        <div className={styles.statsSection}>
          {currentWafer && (
            <>
              {/* Yield with inline value */}
              <div className={styles.yieldRow}>
                <span className={styles.yieldLabel}>Yield:</span>
                <span
                  className={styles.yieldValue}
                  style={{
                    color: currentWafer.defect_summary?.yield_percentage >= 92 ? '#00684a' :
                           currentWafer.defect_summary?.yield_percentage >= 85 ? '#FDB813' : '#DC382D'
                  }}
                >
                  {currentWafer.defect_summary?.yield_percentage?.toFixed(1) || '--'}%
                </span>
              </div>

              {/* Compact info grid */}
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <span className={styles.label}>Pattern:</span>
                  <Badge variant={
                    currentWafer.defect_summary?.defect_pattern === 'clustered' ? 'red' :
                    currentWafer.defect_summary?.defect_pattern === 'edge' ? 'yellow' : 'lightgray'
                  } size="small">
                    {currentWafer.defect_summary?.defect_pattern || 'Unknown'}
                  </Badge>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Severity:</span>
                  <Badge variant={
                    currentWafer.defect_summary?.severity === 'high' ? 'red' :
                    currentWafer.defect_summary?.severity === 'medium' ? 'yellow' : 'blue'
                  } size="small">
                    {currentWafer.defect_summary?.severity || 'Low'}
                  </Badge>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Failed:</span>
                  <span className={styles.value}>
                    {currentWafer.defect_summary?.failed_dies || 0}/{currentWafer.defect_summary?.total_dies || 625}
                  </span>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Tool:</span>
                  <span className={styles.value}>
                    {currentWafer.process_context?.equipment_used?.[0] || currentWafer.equipment_id || 'N/A'}
                  </span>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Time:</span>
                  <span className={styles.value}>
                    {currentWafer.inspection_timestamp
                      ? new Date(currentWafer.inspection_timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit'
                        })
                      : 'N/A'}
                  </span>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Defects:</span>
                  <span className={styles.value}>
                    {currentWafer.defects?.length || currentWafer.defect_summary?.total_defects || 0}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default LiveWaferImageMapCompact;