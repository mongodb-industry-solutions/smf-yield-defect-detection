"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import { Body, Description, H3, Label } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import Modal from '@leafygreen-ui/modal';
import Badge from '@leafygreen-ui/badge';
import styles from './EquipmentFleetGrid.module.css';

const MetricSparkline = ({ data = [], color }) => {
  if (!data || data.length === 0) return null;
  
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const width = 120;
  const height = 35;
  
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');
  
  return (
    <svg width={width} height={height} className={styles.sparkline}>
      <polyline
        points={points}
        fill="none"
        stroke={color || '#00684a'}
        strokeWidth="1.5"
      />
    </svg>
  );
};

const TrendIndicator = ({ value, prevValue }) => {
  if (!prevValue || value === prevValue) {
    return <span style={{ color: '#6b778c', fontSize: '12px' }}>–</span>;
  }
  
  const percentChange = ((value - prevValue) / prevValue * 100).toFixed(1);
  const isUp = value > prevValue;
  
  return (
    <div className={styles.trendIndicator}>
      <Icon 
        glyph={isUp ? "ArrowUp" : "ArrowDown"} 
        size="xsmall" 
        fill={isUp ? "#e11900" : "#00ed64"}
      />
      <span className={styles.trendValue}>{Math.abs(percentChange)}%</span>
    </div>
  );
};

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
            <Label>Utilization</Label>
            <div className={styles.utilizationDetail}>
              <Body>{equipment.utilization}%</Body>
              <TrendIndicator value={equipment.utilization} prevValue={equipment.prevUtilization} />
            </div>
          </div>
          
          <div className={styles.detailSection}>
            <Label>Next Maintenance</Label>
            <Body>{equipment.nextMaintenance || 'Not scheduled'}</Body>
          </div>
          
          <div className={styles.detailSection}>
            <Label>Process Parameters</Label>
            <div className={styles.parametersList}>
              <div className={styles.parameter}>
                <Description>Temperature: 25.3°C</Description>
                <TrendIndicator value={25.3} prevValue={25.1} />
              </div>
              <div className={styles.parameter}>
                <Description>Pressure: 1.2 bar</Description>
                <TrendIndicator value={1.2} prevValue={1.3} />
              </div>
              <div className={styles.parameter}>
                <Description>Flow Rate: 45 L/min</Description>
                <TrendIndicator value={45} prevValue={44} />
              </div>
            </div>
          </div>
          
          <div className={styles.detailSection}>
            <Label>Recent Alerts</Label>
            <div className={styles.alertsList}>
              {equipment.status === 'critical' && (
                <div className={styles.alertItem}>
                  <Icon glyph="Warning" size="small" fill="#e11900" />
                  <Description>High particle count detected</Description>
                </div>
              )}
              {equipment.status === 'warning' && (
                <div className={styles.alertItem}>
                  <Icon glyph="InfoWithCircle" size="small" fill="#fbb13c" />
                  <Description>Approaching maintenance window</Description>
                </div>
              )}
            </div>
          </div>
        </div>
        
        <div className={styles.modalFooter}>
          <Description>Last updated: 2 minutes ago</Description>
        </div>
      </div>
    </Modal>
  );
};

const EquipmentCard = ({ equipment }) => {
  const [showDetails, setShowDetails] = useState(false);
  const getStatusClass = (status) => {
    switch(status) {
      case 'critical': return styles.critical;
      case 'warning': return styles.warning;
      case 'good': return styles.good;
      case 'idle': return styles.idle;
      case 'maintenance': return styles.maintenance;
      default: return styles.unknown;
    }
  };
  
  const getStatusIndicator = (status) => {
    switch(status) {
      case 'critical': 
        return (
          <div className={styles.statusBadge}>
            <span className={`${styles.statusDot} ${styles.critical}`} />
            <span className={styles.statusText}>CRITICAL</span>
          </div>
        );
      case 'warning': 
        return (
          <div className={styles.statusBadge}>
            <span className={`${styles.statusDot} ${styles.warning}`} />
            <span className={styles.statusText}>WARNING</span>
          </div>
        );
      case 'good': 
        return (
          <div className={styles.statusBadge}>
            <span className={`${styles.statusDot} ${styles.good}`} />
            <span className={styles.statusText}>GOOD</span>
          </div>
        );
      case 'idle': 
        return (
          <div className={styles.statusBadge}>
            <span className={`${styles.statusDot} ${styles.idle}`} />
            <span className={styles.statusText}>IDLE</span>
          </div>
        );
      case 'maintenance': 
        return (
          <div className={styles.statusBadge}>
            <span className={`${styles.statusDot} ${styles.maintenance}`} />
            <span className={styles.statusText}>MAINT</span>
          </div>
        );
      default: 
        return (
          <div className={styles.statusBadge}>
            <span className={`${styles.statusDot} ${styles.unknown}`} />
            <span className={styles.statusText}>UNKNOWN</span>
          </div>
        );
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
  
  const getSparklineColor = (status) => {
    switch(status) {
      case 'critical': return '#e11900';
      case 'warning': return '#fbb13c';
      case 'good': return '#00684a';
      case 'idle': return '#c1c7c6';
      case 'maintenance': return '#0884dc';
      default: return '#6b778c';
    }
  };
  
  const isInactive = equipment.status === 'idle' || equipment.status === 'maintenance';
  
  return (
    <>
      <Card 
        className={`${styles.equipmentCard} ${getStatusClass(equipment.status)}`}
        onClick={() => setShowDetails(true)}
      >
      <div className={styles.cardHeader}>
        <div className={styles.equipmentName}>
          <Icon 
            glyph={getTypeIcon(equipment.type)} 
            size="small" 
            fill={getSparklineColor(equipment.status)}
          />
          <Body weight="medium">{equipment.name}</Body>
        </div>
        <div className={styles.statusIndicator}>
          {getStatusIndicator(equipment.status)}
        </div>
      </div>
      
      <div className={styles.cardBody}>
        {equipment.status === 'maintenance' ? (
          <div className={styles.maintenanceInfo}>
            <Icon glyph="Wrench" size="large" />
            <Description>MAINTENANCE</Description>
            <Body weight="medium">2h remaining</Body>
          </div>
        ) : equipment.status === 'idle' ? (
          <div className={styles.idleInfo}>
            <Description>IDLE</Description>
            <Body>Ready for production</Body>
          </div>
        ) : (
          <>
            <div className={styles.metricRow}>
              <Description>Lot</Description>
              <div className={styles.metricValue}>
                <Body weight="medium">{equipment.currentLot}</Body>
              </div>
            </div>
            
            <div className={styles.metricRow}>
              <Description>Utilization</Description>
              <div className={styles.metricWithTrend}>
                <TrendIndicator value={equipment.utilization} prevValue={equipment.prevUtilization} />
                <div className={styles.utilizationBar}>
                <div className={styles.utilizationBarContainer}>
                  <div 
                    className={styles.utilizationFill}
                    style={{ 
                      width: `${equipment.utilization}%`,
                      backgroundColor: equipment.utilization > 95 ? '#fbb13c' : '#00ed64'
                    }}
                  />
                </div>
                <Description>{equipment.utilization}%</Description>
              </div>
              </div>
            </div>
            
            <div className={styles.sparklineContainer}>
              <MetricSparkline 
                data={equipment.sparklineData} 
                color={getSparklineColor(equipment.status)}
              />
            </div>
          </>
        )}
      </div>
      
      <div className={styles.cardFooter}>
        <Description>
          {isInactive ? (
            equipment.status === 'maintenance' ? 'In Progress' : 'Standing By'
          ) : (
            `Maint: ${equipment.nextMaintenance}`
          )}
        </Description>
      </div>
      </Card>
      <EquipmentDetailsModal 
        equipment={equipment} 
        open={showDetails} 
        onClose={() => setShowDetails(false)} 
      />
    </>
  );
};

const EquipmentFleetGrid = ({ equipment = [], searchTerm = '', statusFilter = 'all', typeFilter = 'all' }) => {
  const [loading, setLoading] = useState(false);
  
  // Simulate loading state briefly for demonstration
  React.useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => setLoading(false), 300);
    return () => clearTimeout(timer);
  }, [searchTerm, statusFilter, typeFilter]);
  
  const filteredEquipment = equipment.filter(eq => {
    // Search filter
    if (searchTerm && !eq.name.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }
    
    // Status filter
    if (statusFilter !== 'all' && eq.status !== statusFilter) {
      return false;
    }
    
    // Type filter
    if (typeFilter !== 'all' && eq.type !== typeFilter) {
      return false;
    }
    
    return true;
  });
  
  const sortedEquipment = [...filteredEquipment].sort((a, b) => {
    const statusOrder = { critical: 0, warning: 1, maintenance: 2, idle: 3, good: 4 };
    return (statusOrder[a.status] || 5) - (statusOrder[b.status] || 5);
  });
  
  if (loading) {
    return (
      <div className={styles.fleetGrid}>
        {[...Array(6)].map((_, i) => (
          <div key={i} className={styles.skeletonCard}>
            <div className={styles.shimmer} />
          </div>
        ))}
      </div>
    );
  }
  
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
    <div className={styles.fleetGrid}>
      {sortedEquipment.map(eq => (
        <EquipmentCard key={eq.id} equipment={eq} />
      ))}
    </div>
  );
};

export default EquipmentFleetGrid;