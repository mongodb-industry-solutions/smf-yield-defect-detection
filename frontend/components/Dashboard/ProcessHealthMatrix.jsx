"use client";

import React, { useState, useEffect } from 'react';
// import Card from '@leafygreen-ui/card'; // Removed to prevent white background
import { Body, Description, H3, Label } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import styles from './ProcessHealthMatrix.module.css';
import { equipmentAPI } from '@/lib/api';

const ProcessHealthMatrix = () => {
  const [processData, setProcessData] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [equipmentStatus, setEquipmentStatus] = useState({});
  
  // Process types and equipment mapping
  const processes = [
    { name: 'CMP', equipment: ['CMP-001', 'CMP-002', 'CMP-003'] },
    { name: 'ETCH', equipment: ['ETCH-001', 'ETCH-002', 'ETCH-003'] },
    { name: 'LITHO', equipment: ['LITHO-001', 'LITHO-002'] },
    { name: 'DEP', equipment: ['DEP-001', 'DEP-002'] },
    { name: 'CLEAN', equipment: ['CLEAN-001', 'CLEAN-002'] },
  ];
  
  // Metrics to track
  const metrics = ['Particle', 'Temp', 'Pressure', 'Flow', 'Power'];
  
  // Map backend status to frontend status
  const mapStatus = (metrics) => {
    // Check for critical conditions
    if (metrics?.particle_count > 1200 || metrics?.temperature > 102) return 'critical';
    if (metrics?.particle_count > 1000 || metrics?.temperature > 100) return 'warning';
    if (metrics?.rf_power < 10) return 'idle';
    return 'good';
  };
  
  // Fetch equipment status from backend
  const fetchEquipmentStatus = async () => {
    try {
      const response = await equipmentAPI.getEquipmentStatus();
      
      if (response && response.matrix) {
        setEquipmentStatus(response.matrix);
        
        // Transform backend data to frontend format
        const transformed = processes.map(process => {
          // Get equipment data from matrix based on process name
          const processKey = process.name; // CMP, ETCH, LITHO, etc.
          const backendEquipment = response.matrix[processKey] || [];
          
          // Map frontend equipment names to backend data
          const processEquipment = process.equipment.map(eq => {
            // Find matching equipment in backend data
            const backendEq = backendEquipment.find(be => 
              be.equipment_id && be.equipment_id.includes(eq.split('-')[1])
            );
            
            const metrics = backendEq?.metrics || {};
            
            // Map individual metric statuses with proper thresholds
            const metricStatuses = {};
            metricStatuses['Particle'] = metrics.particle_count > 1200 ? 'critical' : 
                                        metrics.particle_count > 1000 ? 'warning' : 'good';
            metricStatuses['Temp'] = metrics.temperature > 102 ? 'critical' : 
                                     metrics.temperature > 100 ? 'warning' : 'good';
            metricStatuses['Pressure'] = metrics.chamber_pressure > 50 ? 'warning' : 'good';
            metricStatuses['Flow'] = metrics.flow_rate < 5 ? 'warning' : 'good';
            metricStatuses['Power'] = metrics.rf_power < 10 ? 'idle' : 
                                      metrics.rf_power > 1500 ? 'warning' : 'good';
            
            // Calculate utilization based on rf_power (simplified)
            const utilization = metrics.rf_power ? 
              Math.min(100, Math.round((metrics.rf_power / 1500) * 100)) : 
              Math.round(Math.random() * 100);
            
            return {
              name: eq,
              metrics: metricStatuses,
              status: backendEq ? mapStatus(metrics) : 'idle',
              utilization: utilization
            };
          });
          
          return {
            name: process.name,
            equipment: processEquipment
          };
        });
        
        setProcessData(transformed);
        setLastUpdate(new Date());
      } else {
        // Fallback if no data
        generateSimulatedData();
      }
    } catch (error) {
      console.error('Error fetching equipment status:', error);
      // Fallback to simulated data
      generateSimulatedData();
    } finally {
      setIsLoading(false);
    }
  };
  
  // Generate simulated data as fallback
  const generateSimulatedData = () => {
    const generateHealthStatus = () => {
      const rand = Math.random();
      if (rand < 0.05) return 'critical';
      if (rand < 0.15) return 'warning';
      if (rand < 0.25) return 'idle';
      return 'good';
    };
    
    const data = processes.map(process => ({
      name: process.name,
      equipment: process.equipment.map(eq => ({
        name: eq,
        metrics: metrics.reduce((acc, metric) => {
          acc[metric] = generateHealthStatus();
          return acc;
        }, {}),
        status: generateHealthStatus(),
        utilization: Math.round(Math.random() * 100),
      })),
    }));
    
    setProcessData(data);
    setLastUpdate(new Date());
  };
  
  // Initialize and poll equipment status
  useEffect(() => {
    setMounted(true);
    
    // Initial fetch
    fetchEquipmentStatus();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(() => {
      fetchEquipmentStatus();
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);
  
  const getStatusColor = (status) => {
    switch(status) {
      case 'critical': return '#e11900';
      case 'warning': return '#fbb13c';
      case 'good': return '#00ed64';
      case 'idle': return '#c1c7c6';
      default: return '#6b778c';
    }
  };
  
  const getStatusIcon = (status) => {
    switch(status) {
      case 'critical': return { glyph: 'X', color: '#e11900' };
      case 'warning': return { glyph: 'Warning', color: '#fbb13c' };
      case 'good': return { glyph: 'Checkmark', color: '#00684a' };
      case 'idle': return { glyph: 'Pause', color: '#6b778c' };
      default: return { glyph: 'QuestionMarkWithCircle', color: '#6b778c' };
    }
  };
  
  const formatTime = (date) => {
    if (!date) return '--:--:--';
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
  };
  
  return (
    <div className={styles.matrixCard}>
      <div className={styles.header}>
        <H3>Process Health Matrix</H3>
        <div className={styles.lastUpdate}>
          <Icon glyph="Refresh" size="small" />
          <Description>{formatTime(lastUpdate)}</Description>
        </div>
      </div>
      
      <div className={styles.matrixContainer}>
        <div className={styles.matrixHeader}>
          <div className={styles.processLabel}>Process</div>
          <div className={styles.equipmentLabel}>Equipment</div>
          {metrics.map(metric => (
            <div key={metric} className={styles.metricLabel}>
              {metric}
            </div>
          ))}
          <div className={styles.utilizationLabel}>Util%</div>
        </div>
        
        <div className={styles.matrixBody}>
          {processData.map(process => (
            <div key={process.name} className={styles.processGroup}>
              <div className={styles.processName}>
                <Body weight="medium">{process.name}</Body>
              </div>
              <div className={styles.equipmentRows}>
                {process.equipment.map(eq => (
                  <div key={eq.name} className={styles.equipmentRow}>
                    <div className={styles.equipmentName}>
                      <Description>{eq.name}</Description>
                    </div>
                    {metrics.map(metric => (
                      <div 
                        key={metric} 
                        className={`${styles.metricCell} ${styles[eq.metrics[metric]]}`}
                        title={`${metric}: ${eq.metrics[metric]}`}
                      >
                        <Icon 
                          glyph={getStatusIcon(eq.metrics[metric]).glyph} 
                          size="small" 
                          fill={getStatusIcon(eq.metrics[metric]).color}
                        />
                      </div>
                    ))}
                    <div className={styles.utilizationCell}>
                      <div className={styles.utilizationBar}>
                        <div 
                          className={`${styles.utilizationFill} ${eq.utilization > 90 ? styles.high : eq.utilization > 50 ? styles.medium : styles.low}`}
                          style={{ width: `${eq.utilization}%` }}
                        />
                      </div>
                      <span className={styles.utilizationText}>
                        {eq.utilization}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      
      <div className={styles.summary}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryDot} style={{ backgroundColor: '#e11900' }} />
          <Description>
            {processData.reduce((count, p) => 
              count + p.equipment.filter(e => 
                Object.values(e.metrics).includes('critical')
              ).length, 0
            )} Critical
          </Description>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryDot} style={{ backgroundColor: '#fbb13c' }} />
          <Description>
            {processData.reduce((count, p) => 
              count + p.equipment.filter(e => 
                Object.values(e.metrics).includes('warning')
              ).length, 0
            )} Warning
          </Description>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryDot} style={{ backgroundColor: '#00ed64' }} />
          <Description>
            {processData.reduce((count, p) => 
              count + p.equipment.filter(e => 
                Object.values(e.metrics).every(m => m === 'good')
              ).length, 0
            )} Healthy
          </Description>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryDot} style={{ backgroundColor: '#c1c7c6' }} />
          <Description>
            {processData.reduce((count, p) => 
              count + p.equipment.filter(e => e.status === 'idle').length, 0
            )} Idle
          </Description>
        </div>
      </div>
    </div>
  );
};

export default ProcessHealthMatrix;