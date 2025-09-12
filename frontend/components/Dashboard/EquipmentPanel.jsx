"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import { SegmentedControl, SegmentedControlOption } from '@leafygreen-ui/segmented-control';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import { equipmentStatus } from '@/lib/mockData';
import { appPalette } from '@/lib/palette';
import styles from './EquipmentPanel.module.css';

const EquipmentPanel = () => {
  const [selectedEquipment, setSelectedEquipment] = useState('CMP-01');
  
  const currentEquipment = equipmentStatus.find(eq => eq.id === selectedEquipment) || equipmentStatus[0];

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

  return (
    <Card className={styles.panel}>
      <div className={styles.header}>
        <H3 className={styles.title}>Equipment Health</H3>
      </div>
      
      <div className={styles.controls}>
        <SegmentedControl
          value={selectedEquipment}
          onChange={setSelectedEquipment}
          aria-label="Select Equipment"
          size="small"
        >
          {equipmentStatus.map(equipment => (
            <SegmentedControlOption 
              key={equipment.id} 
              value={equipment.id}
            >
              {equipment.name}
            </SegmentedControlOption>
          ))}
        </SegmentedControl>
      </div>
      
      <div className={styles.equipmentContainer}>
        <div className={styles.equipmentCard}>
          <div className={styles.equipmentHeader}>
            <div className={styles.equipmentInfo}>
              <Icon glyph="Settings" size="large" fill={getStatusColor(currentEquipment.status)} />
              <div>
                <Body weight="medium">{currentEquipment.type}</Body>
                <Description>Last maintenance: {currentEquipment.lastMaintenance}</Description>
              </div>
            </div>
            <Badge variant={getStatusBadgeVariant(currentEquipment.status)}>
              {currentEquipment.status.toUpperCase()}
            </Badge>
          </div>
          
          <div className={styles.metricsGrid}>
            <div className={styles.availabilitySection}>
              <div className={styles.metricHeader}>
                <Description>Availability</Description>
                <Body weight="medium">{currentEquipment.availability}%</Body>
              </div>
              <div className={styles.progressBar}>
                <div 
                  className={styles.progressFill}
                  style={{
                    width: `${currentEquipment.availability}%`,
                    backgroundColor: currentEquipment.availability >= 95 
                      ? appPalette.status.success 
                      : currentEquipment.availability >= 90 
                      ? appPalette.status.warning 
                      : appPalette.status.critical
                  }}
                />
              </div>
            </div>
            
            <div className={styles.keyMetrics}>
              <Description className={styles.metricsTitle}>Key Metrics</Description>
              {Object.entries(currentEquipment.metrics).map(([key, data]) => (
                <div key={key} className={styles.metric}>
                  <div className={styles.metricInfo}>
                    <Description>{key.replace(/_/g, ' ').toUpperCase()}</Description>
                    <div className={styles.metricValues}>
                      <Body weight="medium">{data.value}</Body>
                      <Description>/ {data.threshold}</Description>
                    </div>
                  </div>
                  <Badge 
                    variant={data.status === 'critical' ? 'red' : data.status === 'warning' ? 'yellow' : 'green'}
                    size="small"
                  >
                    {data.status}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default EquipmentPanel;