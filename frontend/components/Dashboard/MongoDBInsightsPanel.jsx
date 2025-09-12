"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import { appPalette } from '@/lib/palette';
import styles from './MongoDBInsightsPanel.module.css';

const MongoDBInsightsPanel = ({ operations = [] }) => {
  // Default operations if none provided
  const defaultOperations = [
    { 
      type: 'Time Series Aggregation', 
      collection: 'process_sensor_ts',
      status: 'running', 
      time: null,
      docsScanned: 5764
    },
    { 
      type: 'Vector Search', 
      collection: 'historical_knowledge',
      status: 'complete', 
      time: '23ms',
      docsScanned: 191
    },
    { 
      type: '$rankFusion', 
      collection: 'wafer_defects',
      status: 'pending',
      time: null,
      docsScanned: null
    }
  ];
  
  const activeOperations = operations.length > 0 ? operations : defaultOperations;
  
  const getStatusIcon = (status) => {
    switch(status) {
      case 'running': return 'Refresh';
      case 'complete': return 'Checkmark';
      case 'pending': return 'Clock';
      default: return 'Database';
    }
  };
  
  const getStatusColor = (status) => {
    switch(status) {
      case 'running': return appPalette.status.info;
      case 'complete': return appPalette.status.success;
      case 'pending': return appPalette.status.warning;
      default: return appPalette.text.secondary;
    }
  };
  
  const getStatusVariant = (status) => {
    switch(status) {
      case 'running': return 'blue';
      case 'complete': return 'green';
      case 'pending': return 'yellow';
      default: return 'gray';
    }
  };

  return (
    <Card className={styles.panel}>
      <div className={styles.header}>
        <Icon glyph="Database" size="large" fill={appPalette.status.success} />
        <H3 className={styles.title}>MongoDB Operations Monitor</H3>
      </div>
      
      <div className={styles.operationsList}>
        {activeOperations.map((op, index) => (
          <div key={index} className={styles.operation}>
            <div className={styles.operationHeader}>
              <div className={styles.operationInfo}>
                <Icon 
                  glyph={getStatusIcon(op.status)} 
                  size="small" 
                  fill={getStatusColor(op.status)}
                  className={op.status === 'running' ? styles.spinning : ''}
                />
                <Body className={styles.operationType}>{op.type}</Body>
                <Badge variant={getStatusVariant(op.status)}>
                  {op.status.toUpperCase()}
                </Badge>
              </div>
              
              <div className={styles.operationMetrics}>
                {op.time && (
                  <div className={styles.metric}>
                    <Icon glyph="Clock" size="xsmall" fill={appPalette.text.secondary} />
                    <Description>{op.time}</Description>
                  </div>
                )}
                {op.docsScanned && (
                  <div className={styles.metric}>
                    <Icon glyph="File" size="xsmall" fill={appPalette.text.secondary} />
                    <Description>{op.docsScanned.toLocaleString()} docs</Description>
                  </div>
                )}
              </div>
            </div>
            
            {op.collection && (
              <div className={styles.operationDetails}>
                <Description className={styles.collection}>
                  Collection: {op.collection}
                </Description>
              </div>
            )}
            
            {op.status === 'running' && (
              <div className={styles.progressBar}>
                <div className={styles.progressFill} />
              </div>
            )}
          </div>
        ))}
      </div>
      
      <div className={styles.footer}>
        <div className={styles.footerMetric}>
          <Icon glyph="Database" size="small" fill={appPalette.text.secondary} />
          <Description>Database: smf-yield-defect</Description>
        </div>
        <div className={styles.footerMetric}>
          <Icon glyph="Cloud" size="small" fill={appPalette.text.secondary} />
          <Description>MongoDB Atlas</Description>
        </div>
      </div>
    </Card>
  );
};

export default MongoDBInsightsPanel;