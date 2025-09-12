"use client";

import React, { useState, useEffect } from 'react';
import { Body, Description } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import styles from './AlertTicker.module.css';

const AlertTicker = ({ alerts = [] }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  // Mock real-time alerts if none provided
  const defaultAlerts = [
    { id: 1, type: 'critical', message: '🔴 CMP-001: Particle count exceeded 1200 PPM', timestamp: '2 min ago' },
    { id: 2, type: 'warning', message: '⚠️ ETCH-003: Temperature drift detected +2.3°C', timestamp: '5 min ago' },
    { id: 3, type: 'info', message: 'ℹ️ LOT-A234: Yield 91.2% - Within tolerance', timestamp: '8 min ago' },
    { id: 4, type: 'critical', message: '🔴 LITHO-002: Alignment error on stepper', timestamp: '12 min ago' },
    { id: 5, type: 'warning', message: '⚠️ DEP-004: Flow rate instability detected', timestamp: '15 min ago' },
  ];
  
  const displayAlerts = alerts.length > 0 ? alerts : defaultAlerts;
  
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