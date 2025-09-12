"use client";

import React, { useState } from 'react';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import Modal from '@leafygreen-ui/modal';
import { Body, Description, H3, Label, Overline } from '@leafygreen-ui/typography';
import styles from './EquipmentFleetList.module.css';

const EquipmentDetailsModal = ({ equipment, open, onClose }) => {
  if (!equipment) return null;
  
  return (
    <Modal open={open} setOpen={onClose}>
      <div className={styles.modalContent}>
        <div className={styles.modalHeader}>
          <H3>{equipment.name}</H3>
          <Badge variant={equipment.status === 'critical' ? 'red' : equipment.status === 'warning' ? 'yellow' : 'green'}>
            {equipment.status.toUpperCase()}
          </Badge>
        </div>
        
        <div className={styles.detailsGrid}>
          <div className={styles.detailSection}>
            <Label>Equipment Type</Label>
            <Body>{equipment.type}</Body>
          </div>
          
          <div className={styles.detailSection}>
            <Label>Current Lot</Label>
            <Body>{equipment.currentLot || 'N/A'}</Body>
          </div>
          
          <div className={styles.detailSection}>
            <Label>All Metrics</Label>
            <div className={styles.metricsList}>
              {Object.entries(equipment.metrics || {}).map(([key, metric]) => (
                <div key={key} className={styles.metricItem}>
                  <Description>{key.replace(/_/g, ' ')}: {metric.value} {metric.status !== 'good' && `(threshold: ${metric.threshold})`}</Description>
                </div>
              ))}
            </div>
          </div>
          
          <div className={styles.detailSection}>
            <Label>Next Maintenance</Label>
            <Body>{equipment.nextMaintenance || 'Not scheduled'}</Body>
          </div>
        </div>
      </div>
    </Modal>
  );
};

const EquipmentFleetList = ({ equipment = [], searchTerm = '', statusFilter = 'all', typeFilter = 'all' }) => {
  const [selectedEquipment, setSelectedEquipment] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  
  // Get critical metric for each equipment
  const getCriticalMetric = (eq) => {
    if (!eq.metrics) return { text: '✓ Normal', severity: 'good' };
    
    // Find the most critical metric violation
    const violations = Object.entries(eq.metrics)
      .filter(([_, metric]) => metric.status !== 'good' && metric.status !== 'idle')
      .sort((a, b) => {
        const severity = { critical: 0, warning: 1 };
        return (severity[a[1].status] || 2) - (severity[b[1].status] || 2);
      });
    
    if (violations.length === 0) {
      return { text: '✓ Normal', severity: 'good' };
    }
    
    const [metricName, metric] = violations[0];
    const displayName = metricName.replace(/_/g, ' ');
    const icon = metric.status === 'critical' ? '🔴' : '⚠️';
    return {
      text: `${icon} ${displayName}: ${metric.value}/${metric.threshold}`,
      severity: metric.status
    };
  };
  
  // Calculate health score
  const getHealthScore = (eq) => {
    if (!eq.metrics) return 100;
    
    const metrics = Object.values(eq.metrics);
    const goodMetrics = metrics.filter(m => m.status === 'good' || m.status === 'idle').length;
    return Math.round((goodMetrics / metrics.length) * 100);
  };
  
  // Get next action
  const getNextAction = (eq) => {
    if (eq.status === 'critical') return 'Immediate attention';
    if (eq.status === 'warning') return 'Monitor closely';
    if (eq.status === 'maintenance') return 'In maintenance';
    if (eq.status === 'idle') return 'Ready to run';
    if (eq.nextMaintenance && parseInt(eq.nextMaintenance) <= 24) return `Maint in ${eq.nextMaintenance}`;
    return 'Operating normally';
  };
  
  // Filter equipment
  const filteredEquipment = equipment.filter(eq => {
    if (searchTerm && !eq.name.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }
    if (statusFilter !== 'all' && eq.status !== statusFilter) {
      return false;
    }
    if (typeFilter !== 'all' && eq.type !== typeFilter) {
      return false;
    }
    return true;
  });
  
  // Sort by criticality
  const sortedEquipment = [...filteredEquipment].sort((a, b) => {
    const statusOrder = { critical: 0, warning: 1, maintenance: 2, idle: 3, good: 4 };
    return (statusOrder[a.status] || 5) - (statusOrder[b.status] || 5);
  });
  
  // Group by type
  const groupedEquipment = sortedEquipment.reduce((groups, eq) => {
    const type = eq.type || 'OTHER';
    if (!groups[type]) groups[type] = [];
    groups[type].push(eq);
    return groups;
  }, {});
  
  const getStatusBadgeVariant = (status) => {
    switch(status) {
      case 'critical': return 'red';
      case 'warning': return 'yellow';
      case 'maintenance': return 'blue';
      case 'idle': return 'lightgray';
      case 'good': return 'green';
      default: return 'darkgray';
    }
  };
  
  const getTypeIcon = (type) => {
    switch(type) {
      case 'CMP': return 'Settings';
      case 'ETCH': return 'Cloud';
      case 'LITHO': return 'Visibility';
      case 'DEP': return 'Copy';
      case 'CLEAN': return 'Refresh';
      default: return 'InfoWithCircle';
    }
  };
  
  const handleRowClick = (eq) => {
    setSelectedEquipment(eq);
    setShowDetails(true);
  };
  
  if (sortedEquipment.length === 0) {
    return (
      <div className={styles.noResults}>
        <Icon glyph="Search" size="large" fill="#6b778c" />
        <Body>No equipment found matching your filters</Body>
        <Description>Try adjusting your search criteria</Description>
      </div>
    );
  }
  
  return (
    <>
      <div className={styles.fleetListContainer}>
        {Object.entries(groupedEquipment).map(([type, equipmentList]) => (
          <div key={type} className={styles.typeGroup}>
            <div className={styles.typeHeader}>
              <Icon glyph={getTypeIcon(type)} size="small" />
              <Overline>{type} TOOLS ({equipmentList.length})</Overline>
            </div>
            
            <table className={styles.equipmentTable}>
              <thead>
                <tr>
                  <th className={styles.headerCell}>Equipment</th>
                  <th className={styles.headerCell}>Status</th>
                  <th className={styles.headerCell}>Critical Metric</th>
                  <th className={styles.headerCell}>Current Lot</th>
                  <th className={styles.headerCell}>Health</th>
                  <th className={styles.headerCell}>Next Action</th>
                </tr>
              </thead>
              <tbody>
                {equipmentList.map(eq => {
                  const criticalMetric = getCriticalMetric(eq);
                  const healthScore = getHealthScore(eq);
                  const nextAction = getNextAction(eq);
                  
                  return (
                    <tr 
                      key={eq.id} 
                      onClick={() => handleRowClick(eq)}
                      className={styles.equipmentRow}
                    >
                      <td className={styles.equipmentCell}>
                        <div className={styles.equipmentName}>
                          <Body weight="medium">{eq.name}</Body>
                        </div>
                      </td>
                      <td>
                        <Badge 
                          variant={getStatusBadgeVariant(eq.status)}
                          size="small"
                        >
                          {eq.status.toUpperCase()}
                        </Badge>
                      </td>
                      <td>
                        <span className={`${styles.criticalMetric} ${styles[criticalMetric.severity]}`}>
                          {criticalMetric.text}
                        </span>
                      </td>
                      <td>
                        <Description>{eq.currentLot || '--'}</Description>
                      </td>
                      <td>
                        <span className={`${styles.healthScore} ${healthScore < 70 ? styles.low : healthScore < 90 ? styles.medium : styles.high}`}>
                          {healthScore}%
                        </span>
                      </td>
                      <td>
                        <Description className={styles.nextAction}>{nextAction}</Description>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}
      </div>
      
      <EquipmentDetailsModal 
        equipment={selectedEquipment}
        open={showDetails}
        onClose={() => setShowDetails(false)}
      />
    </>
  );
};

export default EquipmentFleetList;