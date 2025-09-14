"use client";

import React, { useState, useEffect, useRef } from 'react';
// import Card from '@leafygreen-ui/card'; // Removed to prevent white background
import { Body, Description, H3, Label } from '@leafygreen-ui/typography';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import styles from './LiveWaferYieldMap.module.css';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import { useWebSocket } from '@/lib/websocket-native';

const LiveWaferYieldMap = () => {
  const [waferData, setWaferData] = useState(null);
  const [currentYield, setCurrentYield] = useState(92.3);
  const [defectCount, setDefectCount] = useState(0);
  const [pattern, setPattern] = useState('RANDOM');
  const [currentLot, setCurrentLot] = useState('LOT-A234');
  const [isProcessing, setIsProcessing] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [selectedBatch, setSelectedBatch] = useState(0);
  const [batchHistory, setBatchHistory] = useState([]);
  const canvasRef = useRef(null);
  
  // Get data from context and WebSocket
  const { wafers: contextWaferData, isLoading } = useDashboardData();
  const { waferData: wsWaferData, isConnected } = useWebSocket();
  
  // Generate defect patterns
  const generateWaferMap = (forBatch = false) => {
    const size = 25; // 25x25 die grid
    const map = Array(size).fill(null).map(() => Array(size).fill(1)); // 1 = good, 0 = defect
    
    // Randomly choose a pattern type
    const patterns = ['CLUSTERED', 'EDGE', 'RANDOM', 'SYSTEMATIC'];
    const selectedPattern = patterns[Math.floor(Math.random() * patterns.length)];
    
    let defects = 0;
    
    switch(selectedPattern) {
      case 'CLUSTERED':
        // Create cluster defects
        const clusterX = Math.floor(Math.random() * (size - 5)) + 2;
        const clusterY = Math.floor(Math.random() * (size - 5)) + 2;
        for (let i = clusterX - 2; i <= clusterX + 2; i++) {
          for (let j = clusterY - 2; j <= clusterY + 2; j++) {
            if (Math.random() < 0.7) {
              map[i][j] = 0;
              defects++;
            }
          }
        }
        break;
        
      case 'EDGE':
        // Create edge defects
        for (let i = 0; i < size; i++) {
          if (Math.random() < 0.3) {
            map[0][i] = 0;
            map[size-1][i] = 0;
            map[i][0] = 0;
            map[i][size-1] = 0;
            defects += 4;
          }
        }
        break;
        
      case 'SYSTEMATIC':
        // Create systematic pattern (every nth die)
        const step = 3;
        for (let i = 0; i < size; i += step) {
          for (let j = 0; j < size; j += step) {
            if (Math.random() < 0.5) {
              map[i][j] = 0;
              defects++;
            }
          }
        }
        break;
        
      default: // RANDOM
        // Random defects
        for (let i = 0; i < size; i++) {
          for (let j = 0; j < size; j++) {
            if (Math.random() < 0.08) {
              map[i][j] = 0;
              defects++;
            }
          }
        }
    }
    
    const totalDies = size * size;
    const goodDies = totalDies - defects;
    const calculatedYield = ((goodDies / totalDies) * 100).toFixed(1);
    
    if (forBatch) {
      return {
        map,
        defects,
        yieldPercentage: calculatedYield,
        pattern: selectedPattern,
        lotId: `LOT-${String.fromCharCode(65 + Math.floor(Math.random() * 26))}${Math.floor(Math.random() * 1000)}`,
        timestamp: new Date().toISOString(),
        totalDies,
        goodDies
      };
    } else {
      setWaferData(map);
      setDefectCount(defects);
      setCurrentYield(calculatedYield);
      setPattern(selectedPattern);
    }
  };
  
  // Fetch wafer batch data from backend
  const fetchWaferBatches = async () => {
    try {
      // First get latest wafers with die maps
      const waferResponse = { wafers: contextWaferData || [] };
      
      if (waferResponse && waferResponse.wafers && waferResponse.wafers.length > 0) {
        const history = waferResponse.wafers.map(wafer => {
          // Use real die_map from backend if available
          let map = null;
          if (wafer.die_map && Array.isArray(wafer.die_map)) {
            // Backend die_map is a 25x25 2D array
            map = wafer.die_map;
          } else {
            // Fallback to generated map if no die_map
            const generated = generateWaferMap(true);
            map = generated.map;
          }
          
          // Get defect info from wafer data
          const defectSummary = wafer.defect_summary || {};
          const defects = defectSummary.failed_dies || defectSummary.defect_count || 0;
          const yieldPct = defectSummary.yield_percentage || 
                          ((625 - defects) / 625 * 100).toFixed(1);
          const pattern = defectSummary.defect_pattern || defectSummary.pattern || 'random';
          
          return {
            map: map,
            defects: defects,
            yieldPercentage: parseFloat(yieldPct),
            pattern: pattern.toUpperCase(),
            lotId: wafer.lot_id || wafer.wafer_id || `W-${wafer._id?.substr(-4)}`,
            timestamp: wafer.inspection_timestamp || wafer.inspection_date || new Date().toISOString(),
            totalDies: 625,
            goodDies: 625 - defects
          };
        });
        
        setBatchHistory(history);
        if (history.length > 0) {
          const currentBatch = history[0];
          setWaferData(currentBatch.map);
          setDefectCount(currentBatch.defects);
          setCurrentYield(currentBatch.yieldPercentage);
          setPattern(currentBatch.pattern);
          setCurrentLot(currentBatch.lotId);
        }
      } else {
        // No data from backend, use simulated
        generateSimulatedBatches();
      }
    } catch (error) {
      console.error('Error fetching wafer batches:', error);
      // Fallback to simulated data
      generateSimulatedBatches();
    }
  };
  
  // Generate simulated batches as fallback
  const generateSimulatedBatches = () => {
    const history = [];
    for (let i = 4; i >= 0; i--) {
      const batch = generateWaferMap(true);
      batch.timestamp = new Date(Date.now() - i * 3600000).toISOString();
      history.push(batch);
    }
    setBatchHistory(history);
    
    const currentBatch = history[0];
    setWaferData(currentBatch.map);
    setDefectCount(currentBatch.defects);
    setCurrentYield(currentBatch.yieldPercentage);
    setPattern(currentBatch.pattern);
    setCurrentLot(currentBatch.lotId);
  };
  
  // Handle WebSocket wafer updates
  useEffect(() => {
    if (wsWaferData && wsWaferData.length > 0) {
      // Get latest wafer data from WebSocket
      const latestWafer = wsWaferData[wsWaferData.length - 1];
      
      if (latestWafer && latestWafer.type === 'new_wafer') {
        // Create new batch from WebSocket data
        const newBatch = {
          map: latestWafer.die_map || generateWaferMap(true).map,
          defects: latestWafer.defect_count || 0,
          yieldPercentage: latestWafer.yield_percentage || 92.0,
          pattern: (latestWafer.pattern || 'RANDOM').toUpperCase(),
          lotId: latestWafer.lot_id || `LOT-${Date.now()}`,
          timestamp: latestWafer.timestamp || new Date().toISOString(),
          totalDies: 625,
          goodDies: 625 - (latestWafer.defect_count || 0)
        };
        
        // Update batch history with new wafer
        setBatchHistory(prev => [newBatch, ...prev.slice(0, 4)]);
        
        // Update current display if viewing current batch
        if (selectedBatch === 0) {
          setWaferData(newBatch.map);
          setDefectCount(newBatch.defects);
          setCurrentYield(newBatch.yieldPercentage);
          setPattern(newBatch.pattern);
          setCurrentLot(newBatch.lotId);
        }
      }
    }
  }, [wsWaferData, selectedBatch]);
  
  // Initialize batch history once on mount
  useEffect(() => {
    setMounted(true);
    fetchWaferBatches();
    
    // Poll for updates every 10 seconds (fallback when WebSocket not connected)
    const interval = setInterval(() => {
      if (!isConnected) {
        fetchWaferBatches();
      }
    }, 10000);
    
    return () => clearInterval(interval);
  }, [isConnected]); // Only run once on mount
  
  // Handle live updates
  useEffect(() => {
    if (!mounted) return;
    
    // Simulate new wafer processing every 5 seconds
    const interval = setInterval(() => {
      if (selectedBatch === 0) { // Only update if viewing current batch
        setIsProcessing(true);
        setTimeout(() => {
          const newBatch = generateWaferMap(true);
          setBatchHistory(prev => {
            const updated = [newBatch, ...prev.slice(0, 4)];
            return updated;
          });
          if (selectedBatch === 0) { // Still on current batch
            setWaferData(newBatch.map);
            setDefectCount(newBatch.defects);
            setCurrentYield(newBatch.yieldPercentage);
            setPattern(newBatch.pattern);
            setCurrentLot(newBatch.lotId);
          }
          setIsProcessing(false);
        }, 500);
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [selectedBatch, mounted]);
  
  // Draw wafer map on canvas
  useEffect(() => {
    if (!waferData || !canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const size = waferData.length;
    
    // Define wafer parameters first
    const waferCenterX = canvas.width / 2;
    const waferCenterY = canvas.height / 2 - 20; // Move up to leave room for notch
    const waferRadius = 140; // Smaller radius to fit better
    const cellSize = (waferRadius * 2) / size; // Use wafer diameter for cell size
    
    // Clear canvas with gradient background
    const bgGradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    bgGradient.addColorStop(0, '#f0f4f8');
    bgGradient.addColorStop(1, '#e8eef5');
    ctx.fillStyle = bgGradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw circular wafer boundary
    ctx.strokeStyle = '#c1c7c6';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(waferCenterX, waferCenterY, waferRadius, 0, 2 * Math.PI);
    ctx.stroke();
    
    // Create circular clip
    ctx.save();
    ctx.beginPath();
    ctx.arc(waferCenterX, waferCenterY, waferRadius - 2, 0, 2 * Math.PI);
    ctx.clip();
    
    // Draw die map
    waferData.forEach((row, i) => {
      row.forEach((die, j) => {
        const x = j * cellSize;
        const y = i * cellSize;
        
        // Adjust coordinates to wafer center
        const adjustedX = x - (size * cellSize / 2) + waferCenterX;
        const adjustedY = y - (size * cellSize / 2) + waferCenterY;
        
        // Check if die is within circular boundary
        const distance = Math.sqrt(Math.pow(adjustedX + cellSize/2 - waferCenterX, 2) + Math.pow(adjustedY + cellSize/2 - waferCenterY, 2));
        
        if (distance < waferRadius - cellSize/2) {
          // Animate defects
          if (die === 0) {
            // Defect die - red with pulse animation
            const pulseIntensity = Math.sin(Date.now() / 500) * 0.2 + 0.8;
            ctx.fillStyle = `rgba(225, 25, 0, ${pulseIntensity})`;
          } else {
            // Good die - green
            ctx.fillStyle = '#00ed64';
          }
          
          ctx.fillRect(adjustedX, adjustedY, cellSize - 1, cellSize - 1);
          
          // Add grid lines
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
          ctx.lineWidth = 0.5;
          ctx.strokeRect(adjustedX, adjustedY, cellSize, cellSize);
        }
      });
    });
    
    ctx.restore();
    
    // Add notch indicator at bottom of wafer
    ctx.fillStyle = '#c1c7c6';
    ctx.beginPath();
    const notchY = waferCenterY + waferRadius - 5; // Place notch at edge of wafer
    ctx.arc(waferCenterX, notchY, 10, 0, Math.PI, true);
    ctx.fill();
  }, [waferData]);
  
  const getSeverity = () => {
    if (currentYield < 85) return 'critical';
    if (currentYield < 92) return 'warning';
    return 'good';
  };
  
  const getPatternIcon = () => {
    switch(pattern) {
      case 'CLUSTERED': return 'Cloud';
      case 'EDGE': return 'Shell';
      case 'SYSTEMATIC': return 'Copy';
      default: return 'Refresh';
    }
  };
  
  if (!mounted) {
    return (
      <div className={styles.yieldMapCard}>
        <div className={styles.header}>
          <H3>Live Wafer Yield Map</H3>
        </div>
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <Description>Loading...</Description>
        </div>
      </div>
    );
  }

  const handleBatchSelect = (index) => {
    setSelectedBatch(index);
    const batch = batchHistory[index];
    if (batch) {
      setWaferData(batch.map);
      setDefectCount(batch.defects);
      setCurrentYield(batch.yieldPercentage);
      setPattern(batch.pattern);
      setCurrentLot(batch.lotId);
    }
  };

  return (
    <div className={styles.yieldMapCard}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <H3>Live Wafer Yield Map</H3>
          <Badge variant={getSeverity() === 'critical' ? 'red' : getSeverity() === 'warning' ? 'yellow' : 'green'}>
            {currentYield}% YIELD
          </Badge>
        </div>
        {isProcessing && selectedBatch === 0 && (
          <div className={styles.processing}>
            <div className={styles.spinner} />
            <Description>Processing...</Description>
          </div>
        )}
      </div>
      
      <div className={styles.batchSelector}>
        <Label>Batch History</Label>
        <div className={styles.batchTabs}>
          {batchHistory.map((batch, index) => (
            <button
              key={index}
              className={`${styles.batchTab} ${selectedBatch === index ? styles.active : ''}`}
              onClick={() => handleBatchSelect(index)}
              title={batch.lotId}
            >
              <div className={styles.batchLabel}>
                {index === 0 ? 'Current' : `−${index}h`}
              </div>
              <div className={`${styles.batchYield} ${parseFloat(batch.yieldPercentage) < 85 ? styles.critical : parseFloat(batch.yieldPercentage) < 92 ? styles.warning : styles.good}`}>
                {batch.yieldPercentage}%
              </div>
            </button>
          ))}
        </div>
      </div>
      
      <div className={styles.lotInfo}>
        <div className={styles.lotBadge}>
          <Icon glyph="File" size="small" />
          <Body weight="medium">{currentLot}</Body>
        </div>
        <Description>LITHO-002 • Step 5/8</Description>
        {selectedBatch > 0 && (
          <Badge variant="lightgray">
            Historical
          </Badge>
        )}
      </div>
      
      <div className={styles.mapContainer}>
        <canvas 
          ref={canvasRef} 
          width={350} 
          height={380}
          className={`${styles.waferCanvas} ${isProcessing ? styles.processing : ''}`}
          style={{ width: '350px', height: '380px' }}
        />
        
        <div className={styles.mapStats}>
          <div className={styles.stat}>
            <Label>Pattern</Label>
            <div className={styles.patternBadge}>
              <Icon glyph={getPatternIcon()} size="xsmall" />
              <Body weight="medium">{pattern}</Body>
            </div>
          </div>
          <div className={styles.stat}>
            <Label>Defects</Label>
            <Body weight="medium" className={styles.defectCount}>{defectCount} dies</Body>
          </div>
          <div className={styles.stat}>
            <Label>Good Dies</Label>
            <Body weight="medium" className={styles.goodCount}>{625 - defectCount}/625</Body>
          </div>
          
          {batchHistory.length > 0 && (
            <>
              <div className={styles.statDivider} />
              <div className={styles.stat}>
                <Label>5-Batch Avg</Label>
                <Body weight="medium">
                  {(batchHistory.reduce((sum, b) => sum + parseFloat(b.yieldPercentage), 0) / batchHistory.length).toFixed(1)}%
                </Body>
              </div>
              <div className={styles.stat}>
                <Label>Trend</Label>
                <div className={styles.trendIndicator}>
                  {parseFloat(batchHistory[0]?.yieldPercentage) > parseFloat(batchHistory[1]?.yieldPercentage) ? (
                    <>
                      <Icon glyph="ArrowUp" size="xsmall" fill="#00684a" />
                      <Body weight="medium" style={{ color: '#00684a' }}>Improving</Body>
                    </>
                  ) : (
                    <>
                      <Icon glyph="ArrowDown" size="xsmall" fill="#e11900" />
                      <Body weight="medium" style={{ color: '#e11900' }}>Declining</Body>
                    </>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      
      <div className={styles.legend}>
        <div className={styles.legendItem}>
          <span className={`${styles.legendColor} ${styles.good}`} />
          <Description>Pass</Description>
        </div>
        <div className={styles.legendItem}>
          <span className={`${styles.legendColor} ${styles.defect}`} />
          <Description>Fail</Description>
        </div>
        <div className={styles.legendItem}>
          <span className={`${styles.legendColor} ${styles.edge}`} />
          <Description>Edge Exclusion</Description>
        </div>
      </div>
      
      <div className={styles.footer}>
        <Description className={styles.updateTime}>Next wafer in {5}s</Description>
        <div className={styles.actions}>
          <Icon glyph="Download" size="small" />
          <Icon glyph="Expand" size="small" />
        </div>
      </div>
    </div>
  );
};

export default LiveWaferYieldMap;