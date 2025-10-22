"use client";

import React, { useState, useEffect, useRef } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Button from '@leafygreen-ui/button';
import Modal from '@leafygreen-ui/modal';
import { waferAPI } from '@/lib/api';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import styles from './LiveWaferYieldMap.module.css';

const LiveWaferYieldMap = () => {
  const { wafers: preloadedWafers, isPreloaded } = useDashboardData();
  const [waferData, setWaferData] = useState(null);
  const [isLoading, setIsLoading] = useState(!isPreloaded);
  const [selectedWafer, setSelectedWafer] = useState(0);
  const [showMongoModal, setShowMongoModal] = useState(false);
  const [mongoData, setMongoData] = useState(null);
  const [loadingMongoData, setLoadingMongoData] = useState(false);
  const canvasRef = useRef(null);

  // Fetch die maps for wafers
  const fetchDieMaps = async (wafers) => {
    const wafersWithDieMaps = await Promise.all(
      wafers.slice(0, 5).map(async (wafer) => {
        try {
          const vizResponse = await fetch(
            `http://localhost:8000/wafers/${wafer.wafer_id}/visualization`
          );
          const vizData = await vizResponse.json();
          return { ...wafer, die_map: vizData.die_map };
        } catch (err) {
          console.error(`Failed to fetch die_map for ${wafer.wafer_id}`, err);
          return wafer;
        }
      })
    );
    return wafersWithDieMaps;
  };

  // Fetch wafer data
  const fetchWaferData = async () => {
    try {
      const response = await waferAPI.getLatestWafers(5);
      if (response.wafers && response.wafers.length > 0) {
        // Fetch die_map data for each wafer
        const wafersWithDieMaps = await fetchDieMaps(response.wafers);
        setWaferData(wafersWithDieMaps);
        setIsLoading(false);
      }
    } catch (error) {
      console.error('Error fetching wafer data:', error);
      setIsLoading(false);
    }
  };

  // Initial fetch and auto-refresh
  useEffect(() => {
    // Use preloaded data ONLY on initial mount if available
    // After that, let fetchWaferData handle all updates
    if (preloadedWafers && isPreloaded && preloadedWafers.length > 0 && !waferData) {
      console.log('✅ LiveWaferYieldMap: Using preloaded wafer data (one-time)');
      
      // Fetch die maps for preloaded wafers
      fetchDieMaps(preloadedWafers).then(wafersWithMaps => {
        setWaferData(wafersWithMaps);
        setIsLoading(false);
      });
    } else if (!preloadedWafers || !isPreloaded || preloadedWafers.length === 0) {
      // No preloaded data, do initial fetch
      console.log('🔄 LiveWaferYieldMap: No preloaded data, fetching...');
      fetchWaferData();
    }
    
    // CRITICAL: Set up auto-refresh every 20 seconds regardless of preload
    // This ensures data keeps updating after initial load
    // Increased from 15s to 20s (33% reduction in polling frequency)
    const interval = setInterval(() => {
      console.log('🔄 LiveWaferYieldMap: Auto-refreshing wafer data...');
      fetchWaferData();
    }, 20000);
    return () => clearInterval(interval);
  }, []); // Empty deps - run once on mount, then interval takes over

  // Draw wafer map on canvas
  useEffect(() => {
    if (!waferData || !waferData[selectedWafer] || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const wafer = waferData[selectedWafer];

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Calculate die size
    const padding = 20;
    const gridSize = 25; // 25x25 die map
    const availableSize = Math.min(canvas.width, canvas.height) - (padding * 2);
    const dieSize = availableSize / gridSize;

    // Draw circular wafer boundary
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = availableSize / 2;

    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = '#e0e4e7';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = '#f7f9fb';
    ctx.fill();

    // Draw die map if available
    if (wafer.die_map && Array.isArray(wafer.die_map)) {
      // Handle both flat and 2D arrays
      const isFlat = !Array.isArray(wafer.die_map[0]);

      for (let row = 0; row < gridSize; row++) {
        for (let col = 0; col < gridSize; col++) {
          let dieValue;
          if (isFlat) {
            // Flat array
            const index = row * gridSize + col;
            dieValue = wafer.die_map[index];
          } else {
            // 2D array
            dieValue = wafer.die_map[row] && wafer.die_map[row][col];
          }

          // Calculate die position
          const x = padding + col * dieSize;
          const y = padding + row * dieSize;

          // Check if die is within wafer circle
          const dieCenterX = x + dieSize / 2;
          const dieCenterY = y + dieSize / 2;
          const distance = Math.sqrt(
            Math.pow(dieCenterX - centerX, 2) +
            Math.pow(dieCenterY - centerY, 2)
          );

          if (distance <= radius - dieSize/2) {
            // Determine die color based on value
            if (dieValue === 1 || dieValue === 1.0) {
              ctx.fillStyle = '#00684a'; // Good die - green
            } else if (dieValue === 0 || dieValue === 0.0) {
              ctx.fillStyle = '#DC382D'; // Failed die - red
            } else {
              ctx.fillStyle = '#e0e4e7'; // Unknown - gray
            }

            // Draw die
            ctx.fillRect(x, y, dieSize - 1, dieSize - 1);
          }
        }
      }
    }

    // Draw defect pattern overlay if exists
    if (wafer.defect_summary?.pattern) {
      ctx.font = '12px monospace';
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillText(wafer.defect_summary.pattern.toUpperCase(), padding, canvas.height - padding);
    }

  }, [waferData, selectedWafer]);

  // Fetch MongoDB raw data for oldest wafer
  const fetchMongoData = async () => {
    setLoadingMongoData(true);
    try {
      const response = await waferAPI.getOldestWaferRaw();
      setMongoData(response);
      setShowMongoModal(true);
    } catch (error) {
      console.error('Error fetching MongoDB data:', error);
      alert('Failed to fetch MongoDB data. See console for details.');
    } finally {
      setLoadingMongoData(false);
    }
  };

  // Calculate batch statistics
  const getBatchStats = () => {
    if (!waferData || waferData.length === 0) return null;

    const currentWafer = waferData[selectedWafer];
    const lotWafers = waferData.filter(w => w.lot_id === currentWafer.lot_id);

    const avgYield = (lotWafers.reduce((sum, w) => sum + (w.yield_percentage || 0), 0) / lotWafers.length).toFixed(1);
    const minYield = Math.min(...lotWafers.map(w => w.yield_percentage || 0)).toFixed(1);
    const maxYield = Math.max(...lotWafers.map(w => w.yield_percentage || 0)).toFixed(1);

    return { avgYield, minYield, maxYield, count: lotWafers.length };
  };

  const batchStats = getBatchStats();
  const currentWafer = waferData?.[selectedWafer];

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3>Live Wafer Yield Map</h3>
            <p className={styles.subtitle}>
              {currentWafer ? `Wafer: ${currentWafer.wafer_id} • Lot: ${currentWafer.lot_id}` : 'Loading wafer data...'}
            </p>
          </div>
          <div className={styles.headerRight}>
            <Button
              variant="primary"
              size="small"
              onClick={fetchMongoData}
              disabled={loadingMongoData}
              style={{ marginRight: '12px' }}
            >
              {loadingMongoData ? 'Loading...' : 'View MongoDB Structure'}
            </Button>
            <span className={styles.liveIndicator}>
              <span className={styles.liveDot}></span>
              LIVE
            </span>
          </div>
        </div>

        <div className={styles.content}>
          <div className={styles.mapSection}>
            {isLoading ? (
              <div className={styles.loadingState}>
                <div className={styles.spinner}></div>
                <p>Loading wafer map...</p>
              </div>
            ) : (
              <>
                <canvas
                  ref={canvasRef}
                  width={400}
                  height={400}
                  className={styles.waferCanvas}
                />

                {/* Wafer selector */}
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
              </>
            )}
          </div>

          <div className={styles.statsSection}>
            {currentWafer && (
              <>
                {/* Yield indicator */}
                <div className={styles.yieldIndicator}>
                  <div className={styles.yieldValue} style={{
                    color: currentWafer.yield_percentage >= 92 ? '#00684a' :
                           currentWafer.yield_percentage >= 85 ? '#FDB813' : '#DC382D'
                  }}>
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
                      currentWafer.defect_summary?.pattern === 'edge' ? 'yellow' : 'lightgray'
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
                    <span className={styles.label}>Defects:</span>
                    <span className={styles.value}>{currentWafer.defect_summary?.total_defects || 0}</span>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Equipment:</span>
                    <span className={styles.value}>{currentWafer.equipment_id || 'N/A'}</span>
                  </div>
                </div>

                {/* Batch statistics */}
                {batchStats && (
                  <div className={styles.batchStats}>
                    <div className={styles.statsTitle}>Batch Statistics</div>
                    <div className={styles.statsGrid}>
                      <div className={styles.statItem}>
                        <span className={styles.statValue}>{batchStats.avgYield}%</span>
                        <span className={styles.statLabel}>Avg Yield</span>
                      </div>
                      <div className={styles.statItem}>
                        <span className={styles.statValue}>{batchStats.minYield}%</span>
                        <span className={styles.statLabel}>Min</span>
                      </div>
                      <div className={styles.statItem}>
                        <span className={styles.statValue}>{batchStats.maxYield}%</span>
                        <span className={styles.statLabel}>Max</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Legend */}
                <div className={styles.legend}>
                  <div className={styles.legendItem}>
                    <span className={styles.legendDot} style={{ backgroundColor: '#00684a' }}></span>
                    <span>Pass</span>
                  </div>
                  <div className={styles.legendItem}>
                    <span className={styles.legendDot} style={{ backgroundColor: '#DC382D' }}></span>
                    <span>Fail</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </Card>

      {/* MongoDB Structure Modal */}
      <Modal
        open={showMongoModal}
        setOpen={setShowMongoModal}
        size="large"
      >
        <div style={{ padding: '20px', maxHeight: '80vh', overflow: 'auto' }}>
          <h2 style={{ marginBottom: '16px', color: '#001E2B' }}>MongoDB Wafer Document Structure</h2>

          {mongoData && (
            <>
              <div style={{
                backgroundColor: '#F9FBFA',
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '20px',
                border: '1px solid #C1E1C5'
              }}>
                <h3 style={{ marginBottom: '12px', color: '#00684A' }}>Metadata</h3>
                <table style={{ width: '100%', fontSize: '14px' }}>
                  <tbody>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Collection:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.metadata.collection_name}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Database:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.metadata.database_name}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Wafer ID:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.document.wafer_id}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Document Size:</td>
                      <td style={{ padding: '4px 0' }}>{(mongoData.metadata.document_size_bytes / 1024).toFixed(2)} KB</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Embedding Dimensions:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.metadata.embedding_dimensions}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Embedding Model:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.metadata.embedding_model}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Embedding Type:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.metadata.embedding_type}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Die Map Size:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.metadata.die_map_size}</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '4px 0', fontWeight: 600 }}>Defect Count:</td>
                      <td style={{ padding: '4px 0' }}>{mongoData.metadata.defect_count}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div style={{
                backgroundColor: '#001E2B',
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '12px'
              }}>
                <h3 style={{ marginBottom: '12px', color: '#00ED64' }}>Full Document (JSON)</h3>
                <pre style={{
                  backgroundColor: '#13AA52',
                  color: '#001E2B',
                  padding: '16px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  overflow: 'auto',
                  maxHeight: '400px',
                  margin: 0,
                  fontFamily: 'monospace'
                }}>
                  {JSON.stringify(mongoData.document, null, 2)}
                </pre>
              </div>

              <div style={{
                backgroundColor: '#FFF8E1',
                padding: '12px',
                borderRadius: '8px',
                fontSize: '13px',
                border: '1px solid #FFD54F'
              }}>
                <strong>💡 Note:</strong> This shows the complete MongoDB document structure including the 1024-dimensional embedding vector from voyage-multimodal-3 model. The embedding is used for semantic similarity search to find similar defect patterns.
              </div>
            </>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default LiveWaferYieldMap;