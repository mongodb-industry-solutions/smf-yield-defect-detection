"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import styles from './LiveWaferYieldMap.module.css';

const LiveWaferImageMap = () => {
  const [waferData, setWaferData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedWafer, setSelectedWafer] = useState(0);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Fetch wafer data with thumbnails
  const fetchWaferData = async () => {
    console.log('Fetching latest wafer data with images...');
    try {
      const response = await fetch('http://localhost:8000/wafers/latest?limit=3');
      const data = await response.json();

      if (data.wafers && data.wafers.length > 0) {
        console.log(`Fetched ${data.wafers.length} wafers with thumbnails`);
        setWaferData(data.wafers);
        setIsLoading(false);
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Error fetching wafer data:', error);
      setIsLoading(false);
    }
  };

  // Initial fetch and auto-refresh
  useEffect(() => {
    fetchWaferData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchWaferData, 30000);
    return () => clearInterval(interval);
  }, []);

  const currentWafer = waferData?.[selectedWafer];

  // Get wafer image source - use full_image_base64
  const getWaferImageSrc = (wafer) => {
    // Use full_image_base64 which contains the complete image
    if (wafer?.ink_map?.full_image_base64) {
      return `data:image/png;base64,${wafer.ink_map.full_image_base64}`;
    }
    return null;
  };

  if (isLoading) {
    return (
      <div className={styles.container}>
        <Card className={styles.card}>
          <div className={styles.loadingState} style={{ padding: '40px' }}>
            <div className={styles.spinner}></div>
            <p>Loading wafer images...</p>
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
              {currentWafer ? `Wafer: ${currentWafer.wafer_id} • Lot: ${currentWafer.lot_id}` : 'Select a wafer'}
            </p>
          </div>
          <div className={styles.headerRight}>
            <span className={styles.liveIndicator}>
              <span className={styles.liveDot}></span>
              LIVE
            </span>
          </div>
        </div>

        <div className={styles.content}>
          <div className={styles.mapSection}>
            {/* Display the actual wafer thumbnail image */}
            <div style={{
              width: '300px',
              height: '300px',
              margin: '0 auto',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#f7f9fb',
              borderRadius: '8px',
              border: '1px solid #e0e4e7'
            }}>
              {currentWafer && getWaferImageSrc(currentWafer) ? (
                <img
                  src={getWaferImageSrc(currentWafer)}
                  alt={`Wafer ${currentWafer.wafer_id}`}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    borderRadius: '8px'
                  }}
                />
              ) : (
                <div style={{ color: '#6b778c', textAlign: 'center' }}>
                  No image available
                </div>
              )}
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

            {/* Last update time */}
            {lastUpdate && (
              <div style={{ fontSize: '11px', color: '#6b778c', marginTop: '8px', textAlign: 'center' }}>
                Last update: {lastUpdate.toLocaleTimeString()} • Auto-refresh: 30s
              </div>
            )}
          </div>

          {/* Stats section */}
          <div className={styles.statsSection}>
            {currentWafer && (
              <>
                {/* Yield indicator */}
                <div className={styles.yieldIndicator}>
                  <div
                    className={styles.yieldValue}
                    style={{
                      color: currentWafer.yield_percentage >= 92 ? '#00684a' :
                             currentWafer.yield_percentage >= 85 ? '#FDB813' : '#DC382D'
                    }}
                  >
                    {currentWafer.yield_percentage?.toFixed(1)}%
                  </div>
                  <div className={styles.yieldLabel}>Current Yield</div>
                </div>

                {/* Defect info */}
                <div className={styles.defectInfo}>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Pattern:</span>
                    <Badge variant={
                      currentWafer.defect_summary?.pattern === 'clustered' ? 'red' :
                      currentWafer.defect_summary?.pattern === 'edge' ? 'yellow' :
                      currentWafer.defect_summary?.pattern === 'systematic' ? 'yellow' : 'lightgray'
                    }>
                      {currentWafer.defect_summary?.pattern || 'Unknown'}
                    </Badge>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Severity:</span>
                    <Badge variant={
                      currentWafer.defect_summary?.severity === 'high' ? 'red' :
                      currentWafer.defect_summary?.severity === 'medium' ? 'yellow' : 'blue'
                    }>
                      {currentWafer.defect_summary?.severity || 'Low'}
                    </Badge>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Failed Dies:</span>
                    <span className={styles.value}>
                      {currentWafer.defect_summary?.failed_dies || 0} / {currentWafer.defect_summary?.total_dies || 625}
                    </span>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Equipment:</span>
                    <span className={styles.value}>{currentWafer.equipment_id || 'N/A'}</span>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Timestamp:</span>
                    <span className={styles.value}>
                      {currentWafer.inspection_timestamp
                        ? new Date(currentWafer.inspection_timestamp).toLocaleTimeString()
                        : 'N/A'}
                    </span>
                  </div>
                </div>

                {/* Image info */}
                {currentWafer.ink_map && (
                  <div className={styles.batchStats}>
                    <div className={styles.statsTitle}>Image Details</div>
                    <div style={{ fontSize: '12px', color: '#6b778c' }}>
                      <div>Format: {currentWafer.ink_map.format || 'PNG'}</div>
                      <div>Size: {currentWafer.ink_map.full_image_size || '500x500'}</div>
                      <div>Storage: {currentWafer.ink_map.full_image_base64 ? 'MongoDB' : 'S3'}</div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};

export default LiveWaferImageMap;