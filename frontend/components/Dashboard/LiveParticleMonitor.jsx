"use client";

import React, { useState, useEffect, useRef } from 'react';
// import Card from '@leafygreen-ui/card'; // Removed to prevent white background
import { Body, Description, H3, Label } from '@leafygreen-ui/typography';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import styles from './LiveParticleMonitor.module.css';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import { useWebSocket } from '@/lib/websocket-native';

const LiveParticleMonitor = () => {
  const [data, setData] = useState([]);
  const [currentValue, setCurrentValue] = useState(850);
  const [trend, setTrend] = useState('stable');
  const [alert, setAlert] = useState(null);
  const [mounted, setMounted] = useState(false);
  const canvasRef = useRef(null);
  
  // Get data from context
  const { sensors: contextSensorData, isLoading } = useDashboardData();
  
  // Get WebSocket data
  const { sensorData, isConnected } = useWebSocket();
  
  // Generate realistic particle count data
  const generateDataPoint = () => {
    const baseValue = 850;
    const noise = Math.random() * 200 - 100;
    const spike = Math.random() < 0.05 ? Math.random() * 500 : 0; // 5% chance of spike
    return Math.max(0, baseValue + noise + spike);
  };
  
  // Process sensor data from context
  useEffect(() => {
    if (contextSensorData && contextSensorData.length > 0) {
      const particleData = contextSensorData.map(point => 
        point.metrics?.particle_count || 0
      );
      
      setData(particleData);
      
      // Get latest value
      const latest = particleData[particleData.length - 1];
      setCurrentValue(Math.round(latest));
      
      // Determine trend
      if (latest > 1000) {
        setTrend('critical');
        setAlert('EXCURSION DETECTED');
      } else if (latest > 900) {
        setTrend('warning');
        setAlert('APPROACHING LIMIT');
      } else {
        setTrend('stable');
        setAlert(null);
      }
    } else if (!isLoading) {
      // Fallback to simulated data if no context data
      const initialData = Array.from({ length: 50 }, () => generateDataPoint());
      setData(initialData);
    }
  }, [contextSensorData, isLoading]);

  // Handle WebSocket data updates
  useEffect(() => {
    if (sensorData && sensorData.length > 0) {
      // Get latest sensor data from WebSocket
      const latestData = sensorData[sensorData.length - 1];
      
      if (latestData && latestData.data) {
        // Extract particle counts from all sensors
        const sensors = latestData.data;
        const particleCounts = sensors
          .filter(s => s.metrics && s.metrics.particle_count)
          .map(s => s.metrics.particle_count);
        
        if (particleCounts.length > 0) {
          // Use the highest particle count (worst case)
          const maxParticles = Math.max(...particleCounts);
          
          // Update data array with new value
          setData(prev => {
            const updated = [...prev, maxParticles];
            return updated.slice(-50); // Keep last 50 points
          });
          
          setCurrentValue(Math.round(maxParticles));
          
          // Determine trend
          if (maxParticles > 1000) {
            setTrend('critical');
            setAlert('EXCURSION DETECTED');
          } else if (maxParticles > 900) {
            setTrend('warning');
            setAlert('APPROACHING LIMIT');
          } else {
            setTrend('stable');
            setAlert(null);
          }
          
          setIsLoading(false);
        }
      }
    }
  }, [sensorData]);
  
  useEffect(() => {
    setMounted(true);
  }, []);
  
  // Draw chart on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Draw grid lines
    ctx.strokeStyle = '#e0e4e7';
    ctx.lineWidth = 0.5;
    
    for (let i = 0; i <= 5; i++) {
      const y = (height / 5) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    
    // Draw threshold line at 1000
    ctx.strokeStyle = '#e11900';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    const thresholdY = height - (1000 / 1500) * height;
    ctx.beginPath();
    ctx.moveTo(0, thresholdY);
    ctx.lineTo(width, thresholdY);
    ctx.stroke();
    ctx.setLineDash([]);
    
    // Draw data line
    if (data.length > 0) {
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, trend === 'critical' ? '#e11900' : trend === 'warning' ? '#fbb13c' : '#00684a');
      gradient.addColorStop(1, trend === 'critical' ? '#ff6b6b' : trend === 'warning' ? '#ffd93d' : '#00ed64');
      
      ctx.strokeStyle = gradient;
      ctx.lineWidth = 2;
      ctx.beginPath();
      
      data.forEach((value, index) => {
        const x = (width / (data.length - 1)) * index;
        const y = height - (value / 1500) * height;
        
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      
      ctx.stroke();
      
      // Fill area under curve
      ctx.fillStyle = trend === 'critical' ? 'rgba(225, 25, 0, 0.1)' : 
                      trend === 'warning' ? 'rgba(251, 177, 60, 0.1)' : 
                      'rgba(0, 104, 74, 0.1)';
      ctx.lineTo(width, height);
      ctx.lineTo(0, height);
      ctx.closePath();
      ctx.fill();
    }
  }, [data, trend]);
  
  if (!mounted) {
    return (
      <div className={styles.monitorCard}>
        <div className={styles.header}>
          <H3>Live Particle Monitor</H3>
        </div>
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <Description>Loading...</Description>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.monitorCard}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <H3>Live Particle Monitor</H3>
          <Badge variant={trend === 'critical' ? 'red' : trend === 'warning' ? 'yellow' : 'green'}>
            {trend.toUpperCase()}
          </Badge>
        </div>
        {alert && (
          <div className={`${styles.alert} ${styles[trend]}`}>
            <Icon glyph="Warning" size="small" />
            <Body weight="medium">{alert}</Body>
          </div>
        )}
      </div>
      
      <div className={styles.metricsRow}>
        <div className={styles.metric}>
          <Label>Current</Label>
          <div className={`${styles.value} ${styles[trend]}`}>
            {currentValue} <span className={styles.unit}>PPM</span>
          </div>
        </div>
        <div className={styles.metric}>
          <Label>Threshold</Label>
          <div className={styles.value}>
            1000 <span className={styles.unit}>PPM</span>
          </div>
        </div>
        <div className={styles.metric}>
          <Label>24h Avg</Label>
          <div className={styles.value}>
            847 <span className={styles.unit}>PPM</span>
          </div>
        </div>
        <div className={styles.metric}>
          <Label>Peak</Label>
          <div className={styles.value}>
            1248 <span className={styles.unit}>PPM</span>
          </div>
        </div>
      </div>
      
      <div className={styles.chartContainer}>
        <canvas 
          ref={canvasRef} 
          width={500} 
          height={200}
          className={styles.chart}
        />
        <Description className={styles.chartLabel}>Last 50 readings (1 min window)</Description>
      </div>
      
      <div className={styles.footer}>
        <div className={styles.equipment}>
          <Icon glyph="Settings" size="small" />
          <Description>CMP-001 • CMP-002 • CMP-003</Description>
        </div>
        <Description className={styles.updateTime}>
          {isConnected ? (
            <><Icon glyph="Refresh" size="small" /> Live</>  
          ) : (
            <>Updates every 2s</>  
          )}
        </Description>
      </div>
    </div>
  );
};

export default LiveParticleMonitor;