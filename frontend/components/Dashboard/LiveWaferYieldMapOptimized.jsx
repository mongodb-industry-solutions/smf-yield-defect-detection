"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import styles from './LiveWaferYieldMap.module.css';

// Cache for die map data
const dieMapCache = new Map();

const LiveWaferYieldMapOptimized = () => {
  const [waferData, setWaferData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedWafer, setSelectedWafer] = useState(0);
  const [currentDieMap, setCurrentDieMap] = useState(null);
  const [isFetchingMap, setIsFetchingMap] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);

  // Fetch wafer list only (without die maps initially)
  const fetchWaferList = async () => {
    console.log('Fetching latest wafer data...');
    try {
      const response = await fetch('http://localhost:8000/wafers/latest?limit=3'); // Reduced from 5 to 3
      const data = await response.json();

      if (data.wafers && data.wafers.length > 0) {
        console.log(`Fetched ${data.wafers.length} wafers:`, data.wafers.map(w => w.wafer_id));
        setWaferData(data.wafers);
        setIsLoading(false);
        setLastUpdate(new Date());

        // Fetch die map for first wafer only
        if (data.wafers[0]) {
          fetchDieMap(data.wafers[0].wafer_id);
        }
      }
    } catch (error) {
      console.error('Error fetching wafer data:', error);
      setIsLoading(false);
    }
  };

  // Fetch individual die map - no caching for now to ensure freshness
  const fetchDieMap = async (waferId) => {
    console.log(`Fetching die map for ${waferId}...`);
    setIsFetchingMap(true);
    setCurrentDieMap(null); // Clear current map to show loading

    try {
      const response = await fetch(`http://localhost:8000/wafers/${waferId}/visualization`);
      const data = await response.json();

      console.log(`Die map fetched for ${waferId}`);
      setCurrentDieMap(data.die_map);
    } catch (error) {
      console.error(`Failed to fetch die map for ${waferId}`, error);
    } finally {
      setIsFetchingMap(false);
    }
  };

  // Optimized canvas drawing with requestAnimationFrame
  const drawWaferMap = useCallback(() => {
    if (!currentDieMap || !canvasRef.current) return;

    // Cancel any pending animation frame
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    animationFrameRef.current = requestAnimationFrame(() => {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d', { alpha: false });

      // Use smaller canvas for better performance
      canvas.width = 300;
      canvas.height = 300;

      const padding = 15;
      const gridSize = 25;
      const availableSize = canvas.width - (padding * 2);
      const dieSize = availableSize / gridSize;

      // Clear with solid color (faster than clearRect)
      ctx.fillStyle = '#f7f9fb';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw circular boundary
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const radius = availableSize / 2;

      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
      ctx.strokeStyle = '#e0e4e7';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Batch similar colored dies for fewer draw calls
      const passDies = [];
      const failDies = [];

      const isFlat = !Array.isArray(currentDieMap[0]);

      for (let row = 0; row < gridSize; row++) {
        for (let col = 0; col < gridSize; col++) {
          let dieValue;
          if (isFlat) {
            const index = row * gridSize + col;
            dieValue = currentDieMap[index];
          } else {
            dieValue = currentDieMap[row] && currentDieMap[row][col];
          }

          const x = padding + col * dieSize;
          const y = padding + row * dieSize;
          const dieCenterX = x + dieSize / 2;
          const dieCenterY = y + dieSize / 2;
          const distance = Math.sqrt(
            Math.pow(dieCenterX - centerX, 2) +
            Math.pow(dieCenterY - centerY, 2)
          );

          if (distance <= radius - dieSize/2) {
            if (dieValue === 1 || dieValue === 1.0) {
              passDies.push({ x, y, size: dieSize - 1 });
            } else if (dieValue === 0 || dieValue === 0.0) {
              failDies.push({ x, y, size: dieSize - 1 });
            }
          }
        }
      }

      // Draw all pass dies at once
      ctx.fillStyle = '#00684a';
      passDies.forEach(die => {
        ctx.fillRect(die.x, die.y, die.size, die.size);
      });

      // Draw all fail dies at once
      ctx.fillStyle = '#DC382D';
      failDies.forEach(die => {
        ctx.fillRect(die.x, die.y, die.size, die.size);
      });
    });
  }, [currentDieMap]);

  // Initial fetch
  useEffect(() => {
    fetchWaferList();

    // Longer refresh interval (30 seconds instead of 15)
    const interval = setInterval(fetchWaferList, 30000);

    return () => {
      clearInterval(interval);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Draw when die map changes
  useEffect(() => {
    drawWaferMap();
  }, [currentDieMap, drawWaferMap]);

  // Handle wafer selection
  const handleWaferSelect = (index) => {
    console.log(`Selecting wafer at index ${index}`);
    setSelectedWafer(index);
    const wafer = waferData[index];

    if (wafer) {
      console.log(`Loading wafer ${wafer.wafer_id}`);
      fetchDieMap(wafer.wafer_id);
    }
  };

  // Memoized calculations
  const currentWafer = useMemo(() => waferData?.[selectedWafer], [waferData, selectedWafer]);

  const stats = useMemo(() => {
    if (!currentWafer) return null;
    return {
      yieldColor: currentWafer.yield_percentage >= 92 ? '#00684a' :
                  currentWafer.yield_percentage >= 85 ? '#FDB813' : '#DC382D',
      patternVariant: currentWafer.defect_summary?.pattern === 'clustered' ? 'red' :
                      currentWafer.defect_summary?.pattern === 'edge' ? 'yellow' : 'lightgray',
      severityVariant: currentWafer.defect_summary?.severity === 'high' ? 'red' :
                       currentWafer.defect_summary?.severity === 'medium' ? 'yellow' : 'blue'
    };
  }, [currentWafer]);

  if (isLoading) {
    return (
      <div className={styles.container}>
        <Card className={styles.card}>
          <div className={styles.loadingState} style={{ padding: '40px' }}>
            <div className={styles.spinner}></div>
            <p>Loading wafer map...</p>
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
            <h3>Live Wafer Yield Map</h3>
            <p className={styles.subtitle}>
              {currentWafer ? `Wafer: ${currentWafer.wafer_id} • Lot: ${currentWafer.lot_id}` : 'Loading...'}
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
            <div style={{ position: 'relative', width: '300px', height: '300px', margin: '0 auto' }}>
              {(isFetchingMap || !currentDieMap) && (
                <div style={{
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  background: 'rgba(255, 255, 255, 0.95)',
                  padding: '15px 20px',
                  borderRadius: '8px',
                  zIndex: 10,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '10px'
                }}>
                  <div className={styles.spinner}></div>
                  <div>Loading wafer map...</div>
                </div>
              )}

              <canvas
                ref={canvasRef}
                width={300}
                height={300}
                className={styles.waferCanvas}
                style={{
                  width: '300px',
                  height: '300px',
                  opacity: isFetchingMap || !currentDieMap ? 0.3 : 1,
                  transition: 'opacity 0.3s'
                }}
              />
            </div>

            <div className={styles.waferSelector}>
              {waferData?.map((wafer, index) => (
                <button
                  key={wafer.wafer_id}
                  className={`${styles.waferTab} ${index === selectedWafer ? styles.active : ''}`}
                  onClick={() => handleWaferSelect(index)}
                >
                  {wafer.wafer_id.split('_').pop()}
                </button>
              ))}
            </div>

            {lastUpdate && (
              <div style={{ fontSize: '11px', color: '#6b778c', marginTop: '8px' }}>
                Last update: {lastUpdate.toLocaleTimeString()}
              </div>
            )}
          </div>

          <div className={styles.statsSection}>
            {currentWafer && stats && (
              <>
                <div className={styles.yieldIndicator}>
                  <div className={styles.yieldValue} style={{ color: stats.yieldColor }}>
                    {currentWafer.yield_percentage?.toFixed(1)}%
                  </div>
                  <div className={styles.yieldLabel}>Current Yield</div>
                </div>

                <div className={styles.defectInfo}>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Pattern:</span>
                    <Badge variant={stats.patternVariant}>
                      {currentWafer.defect_summary?.pattern || 'Unknown'}
                    </Badge>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Severity:</span>
                    <Badge variant={stats.severityVariant}>
                      {currentWafer.defect_summary?.severity || 'Low'}
                    </Badge>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.label}>Equipment:</span>
                    <span className={styles.value}>{currentWafer.equipment_id || 'N/A'}</span>
                  </div>
                </div>

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
    </div>
  );
};

export default LiveWaferYieldMapOptimized;