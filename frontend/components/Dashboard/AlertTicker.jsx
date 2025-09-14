"use client";

import React, { useState, useEffect } from 'react';
import { Body, Description } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import styles from './AlertTicker.module.css';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import { useWebSocket } from '@/lib/websocket-native';

const AlertTicker = ({ alerts = [] }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  // Get data from context and WebSocket
  const { alerts: contextAlerts, isLoading } = useDashboardData();
  const { alertData, isConnected } = useWebSocket();
  const [backendAlerts, setBackendAlerts] = useState([]);
  
  // Process context alerts to frontend format
  useEffect(() => {
    if (contextAlerts && contextAlerts.length > 0) {
      // Transform backend alerts to frontend format
      const formattedAlerts = contextAlerts.map(alert => {
        const icon = alert.severity === 'critical' ? '🔴' : 
                     alert.severity === 'high' ? '⚠️' : 
                     alert.severity === 'medium' ? '⚠️' : 'ℹ️';
        
        const equipment = alert.equipment_id || 'Unknown';
        const violations = alert.violations || [];
        const mainViolation = violations[0];
        
        let message = `${icon} ${equipment}: `;
        if (mainViolation) {
          message += `${mainViolation.metric} ${mainViolation.current_value > mainViolation.threshold ? 'exceeded' : 'drift'} (${mainViolation.current_value})`;
        } else {
          message += alert.alert_type || 'Alert detected';
        }
        
        // Calculate time ago
        const timestamp = new Date(alert.timestamp);
        const now = new Date();
        const diffMinutes = Math.floor((now - timestamp) / 60000);
        const timeAgo = diffMinutes < 60 ? `${diffMinutes} min ago` : 
                       `${Math.floor(diffMinutes / 60)} hours ago`;
        
        return {
          id: alert._id,
          type: alert.severity === 'critical' || alert.severity === 'high' ? 'critical' : 
                alert.severity === 'medium' ? 'warning' : 'info',
          message: message,
          timestamp: timeAgo
        };
      });
      
      setBackendAlerts(formattedAlerts);
    }
  }, [contextAlerts]);
  
  // Mock real-time alerts if none provided
  const defaultAlerts = [
    { id: 1, type: 'critical', message: '🔴 CMP-001: Particle count exceeded 1200 PPM', timestamp: '2 min ago' },
    { id: 2, type: 'warning', message: '⚠️ ETCH-003: Temperature drift detected +2.3°C', timestamp: '5 min ago' },
    { id: 3, type: 'info', message: 'ℹ️ LOT-A234: Yield 91.2% - Within tolerance', timestamp: '8 min ago' },
    { id: 4, type: 'critical', message: '🔴 LITHO-002: Alignment error on stepper', timestamp: '12 min ago' },
    { id: 5, type: 'warning', message: '⚠️ DEP-004: Flow rate instability detected', timestamp: '15 min ago' },
  ];
  
  // Use backend alerts if available, otherwise use provided alerts or defaults
  const displayAlerts = backendAlerts.length > 0 ? backendAlerts : 
                        alerts.length > 0 ? alerts : defaultAlerts;
  
  // Handle WebSocket alert updates
  useEffect(() => {
    if (alertData && alertData.length > 0) {
      // Get latest alert data from WebSocket
      const latestAlert = alertData[alertData.length - 1];
      
      if (latestAlert && latestAlert.type === 'new_alert') {
        // Transform WebSocket alert to frontend format
        const icon = latestAlert.severity === 'critical' ? '🔴' : 
                     latestAlert.severity === 'high' ? '⚠️' : 
                     latestAlert.severity === 'medium' ? '⚠️' : 'ℹ️';
        
        const newAlert = {
          id: latestAlert.alert_id || `alert-${Date.now()}`,
          type: latestAlert.severity === 'critical' || latestAlert.severity === 'high' ? 'critical' : 
                latestAlert.severity === 'medium' ? 'warning' : 'info',
          message: `${icon} ${latestAlert.equipment || 'Unknown'}: ${latestAlert.message || 'Alert detected'}`,
          timestamp: 'Just now'
        };
        
        // Add new alert to the beginning of the list
        setBackendAlerts(prev => [newAlert, ...prev].slice(0, 20)); // Keep max 20 alerts
      }
    }
  }, [alertData]);
  
  useEffect(() => {
    setMounted(true);
  }, []);
  
  useEffect(() => {
    if (!mounted || displayAlerts.length <= 1) return;
    
    const interval = setInterval(() => {
      setIsAnimating(true);
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % displayAlerts.length);
        setIsAnimating(false);
      }, 300);
    }, 4000);
    
    return () => clearInterval(interval);
  }, [displayAlerts.length, mounted]);
  
  const currentAlert = displayAlerts[currentIndex] || displayAlerts[0];
  
  const getAlertClass = (type) => {
    switch(type) {
      case 'critical': return styles.critical;
      case 'warning': return styles.warning;
      case 'info': return styles.info;
      default: return styles.info;
    }
  };
  
  const handlePrevious = () => {
    setCurrentIndex((prev) => (prev - 1 + displayAlerts.length) % displayAlerts.length);
  };
  
  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % displayAlerts.length);
  };
  
  if (!mounted || displayAlerts.length === 0) {
    return (
      <div className={styles.tickerContainer}>
        <div className={styles.noAlerts}>
          <Icon glyph="Checkmark" size="small" />
          <Description>All systems operating normally</Description>
        </div>
      </div>
    );
  }
  
  return (
    <div className={`${styles.tickerContainer} ${getAlertClass(currentAlert.type)}`}>
      <div className={styles.tickerContent}>
        <button className={styles.navButton} onClick={handlePrevious}>
          <Icon glyph="ChevronLeft" size="small" />
        </button>
        
        <div className={`${styles.alertMessage} ${isAnimating ? styles.animating : ''}`}>
          <Body weight="medium">{currentAlert.message}</Body>
          <Description className={styles.timestamp}>{currentAlert.timestamp}</Description>
        </div>
        
        <button className={styles.navButton} onClick={handleNext}>
          <Icon glyph="ChevronRight" size="small" />
        </button>
      </div>
      
      <div className={styles.indicators}>
        {displayAlerts.map((_, index) => (
          <span
            key={index}
            className={`${styles.indicator} ${index === currentIndex ? styles.active : ''}`}
            onClick={() => setCurrentIndex(index)}
          />
        ))}
      </div>
    </div>
  );
};

export default AlertTicker;