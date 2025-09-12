"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import { appPalette } from '@/lib/palette';
import styles from './EquipmentStatusCard.module.css';

const EquipmentStatusCard = ({ equipment }) => {
  const getStatusColor = (status) => {
    switch(status) {
      case 'critical': return appPalette.status.critical;
      case 'warning': return appPalette.status.warning;
      case 'good': return appPalette.status.success;
      default: return appPalette.text.secondary;
    }
  };
  
  const getStatusBadgeVariant = (status) => {
    switch(status) {
      case 'critical': return 'red';
      case 'warning': return 'yellow';
      case 'good': return 'green';
      default: return 'gray';
    }
  };
  
  const getStatusIcon = (status) => {
    switch(status) {
      case 'critical': return 'X';
      case 'warning': return 'Warning';
      case 'good': return 'Checkmark';
      default: return 'QuestionMarkWithCircle';
    }
  };

  return (
    <Card className={styles.card}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Icon 
            glyph="Settings" 
            size="large" 
            fill={getStatusColor(equipment.status)}
          />
          <div>
            <H3 className={styles.equipmentName}>{equipment.name}</H3>
            <Description>{equipment.type}</Description>
          </div>
        </div>
        
        <Badge variant={getStatusBadgeVariant(equipment.status)}>
          {equipment.status.toUpperCase()}
        </Badge>
      </div>
      
      <div className={styles.availability}>
        <div className={styles.availabilityHeader}>
          <Description>Availability</Description>
          <Body weight="medium">{equipment.availability}%</Body>
        </div>
        <div className={styles.availabilityBar}>
          <div 
            className={styles.availabilityFill}
            style={{
              width: `${equipment.availability}%`,
              backgroundColor: equipment.availability >= 95 
                ? appPalette.status.success 
                : equipment.availability >= 90 
                ? appPalette.status.warning 
                : appPalette.status.critical
            }}
          />
        </div>
      </div>
      
      <div className={styles.metrics}>
        <Description className={styles.metricsTitle}>Key Metrics</Description>
        {Object.entries(equipment.metrics).map(([key, data]) => (
          <div key={key} className={styles.metric}>
            <div className={styles.metricHeader}>
              <Description className={styles.metricName}>
                {key.replace(/_/g, ' ').toUpperCase()}
              </Description>
              <Icon 
                glyph={getStatusIcon(data.status)} 
                size="xsmall" 
                fill={getStatusColor(data.status)}
              />
            </div>
            <div className={styles.metricValue}>
              <Body weight="medium">
                {data.value}
              </Body>
              <Description className={styles.metricThreshold}>
                / {data.threshold}
              </Description>
            </div>
            <div className={styles.metricBar}>
              <div 
                className={styles.metricFill}
                style={{
                  width: `${Math.min((data.value / data.threshold) * 100, 100)}%`,
                  backgroundColor: getStatusColor(data.status)
                }}
              />
            </div>
          </div>
        ))}
      </div>
      
      <div className={styles.footer}>
        <div className={styles.footerItem}>
          <Icon glyph="Clock" size="small" fill={appPalette.text.secondary} />
          <Description>Last maintenance: {equipment.lastMaintenance}</Description>
        </div>
        <div className={styles.footerItem}>
          <Icon glyph="Database" size="small" fill={appPalette.text.secondary} />
          <Description>ID: {equipment.id}</Description>
        </div>
      </div>
    </Card>
  );
};

export default EquipmentStatusCard;