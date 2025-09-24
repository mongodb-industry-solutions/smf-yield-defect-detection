"use client";

import React, { useState, useEffect } from 'react';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import styles from './EquipmentStatusStrip.module.css';

const EquipmentStatusStrip = () => {
  const { equipmentStatus, refresh } = useDashboardData();
  const [hoveredEquipment, setHoveredEquipment] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refresh();
    }, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const getStatusColor = (metrics) => {
    if (!metrics) return '#6b778c';
    const { particle_count, rf_power, temperature } = metrics;

    if (particle_count > 1000 || rf_power > 1400 || temperature > 75) {
      return '#DC382D'; // Critical
    } else if (particle_count > 800 || rf_power > 1350 || temperature > 70) {
      return '#FDB813'; // Warning
    } else if (particle_count > 600 || rf_power > 1300 || temperature > 68) {
      return '#FFE169'; // Caution
    }
    return '#13AA52'; // Good
  };

  const getStatusText = (metrics) => {
    if (!metrics) return 'OFFLINE';
    const { particle_count, rf_power, temperature } = metrics;

    if (particle_count > 1000 || rf_power > 1400 || temperature > 75) {
      return 'CRITICAL';
    } else if (particle_count > 800 || rf_power > 1350 || temperature > 70) {
      return 'WARNING';
    } else if (particle_count > 600 || rf_power > 1300 || temperature > 68) {
      return 'CAUTION';
    }
    return 'HEALTHY';
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / 60000);

    if (diffInMinutes < 60) {
      return `${diffInMinutes}m ago`;
    } else if (diffInMinutes < 1440) {
      const hours = Math.floor(diffInMinutes / 60);
      return `${hours}h ago`;
    }
    return date.toLocaleDateString();
  };

  // Group equipment by type
  const groupedEquipment = {};
  if (equipmentStatus && equipmentStatus.length > 0) {
    equipmentStatus.forEach(eq => {
      const type = eq.equipment_id.split('_')[0];
      if (!groupedEquipment[type]) {
        groupedEquipment[type] = [];
      }
      groupedEquipment[type].push(eq);
    });
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.title}>
          <span className={styles.titleText}>Equipment Fleet Status</span>
          <div className={styles.liveIndicator}>
            <span className={styles.liveDot}></span>
            <span className={styles.liveText}>LIVE</span>
          </div>
        </div>
        <button
          className={`${styles.refreshBtn} ${isRefreshing ? styles.spinning : ''}`}
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          ↻
        </button>
      </div>

      <div className={styles.equipmentRow}>
        {Object.keys(groupedEquipment).length > 0 ? (
          Object.entries(groupedEquipment).map(([type, equipment]) => (
            <div key={type} className={styles.typeGroup}>
              <div className={styles.typeLabel}>{type}</div>
              <div className={styles.equipmentList}>
                {equipment.map(eq => {
                  const statusColor = getStatusColor(eq.latest_metrics);
                  const statusText = getStatusText(eq.latest_metrics);
                  const isHovered = hoveredEquipment === eq.equipment_id;

                  return (
                    <div
                      key={eq.equipment_id}
                      className={styles.equipmentCard}
                      onMouseEnter={() => setHoveredEquipment(eq.equipment_id)}
                      onMouseLeave={() => setHoveredEquipment(null)}
                      style={{
                        borderColor: statusColor,
                        background: isHovered ? `${statusColor}10` : 'white'
                      }}
                    >
                      <div
                        className={styles.statusIndicator}
                        style={{ backgroundColor: statusColor }}
                      />
                      <div className={styles.equipmentInfo}>
                        <div className={styles.equipmentId}>
                          {eq.equipment_id.split('_').slice(-1)[0]}
                        </div>
                        <div className={styles.statusBadge} style={{ color: statusColor }}>
                          {statusText}
                        </div>
                      </div>

                      {isHovered && eq.latest_metrics && (
                        <div className={styles.tooltip}>
                          <div className={styles.tooltipHeader}>
                            <strong>{eq.equipment_id}</strong>
                            <span className={styles.timestamp}>
                              {formatTimestamp(eq.latest_timestamp)}
                            </span>
                          </div>
                          <div className={styles.tooltipMetrics}>
                            <div className={styles.metric}>
                              <span>Particles:</span>
                              <strong style={{
                                color: eq.latest_metrics.particle_count > 1000 ? '#DC382D' :
                                       eq.latest_metrics.particle_count > 800 ? '#FDB813' : '#13AA52'
                              }}>
                                {eq.latest_metrics.particle_count}
                              </strong>
                            </div>
                            <div className={styles.metric}>
                              <span>RF Power:</span>
                              <strong>{eq.latest_metrics.rf_power?.toFixed(1)}W</strong>
                            </div>
                            <div className={styles.metric}>
                              <span>Temp:</span>
                              <strong>{eq.latest_metrics.temperature?.toFixed(1)}°C</strong>
                            </div>
                            <div className={styles.metric}>
                              <span>Pressure:</span>
                              <strong>{eq.latest_metrics.chamber_pressure?.toFixed(1)}</strong>
                            </div>
                            <div className={styles.metric}>
                              <span>Flow:</span>
                              <strong>{eq.latest_metrics.flow_rate?.toFixed(1)}</strong>
                            </div>
                          </div>
                          <div className={styles.processStep}>
                            Process: {eq.process_step || 'Unknown'}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        ) : (
          <div className={styles.noData}>
            <p>Loading equipment status...</p>
          </div>
        )}
      </div>

      {/* Summary stats */}
      <div className={styles.summaryRow}>
        {equipmentStatus && equipmentStatus.length > 0 && (
          <>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Total:</span>
              <span className={styles.summaryValue}>{equipmentStatus.length}</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Healthy:</span>
              <span className={styles.summaryValue} style={{ color: '#13AA52' }}>
                {equipmentStatus.filter(eq => {
                  const status = getStatusText(eq.latest_metrics);
                  return status === 'HEALTHY';
                }).length}
              </span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Warning:</span>
              <span className={styles.summaryValue} style={{ color: '#FDB813' }}>
                {equipmentStatus.filter(eq => {
                  const status = getStatusText(eq.latest_metrics);
                  return status === 'WARNING' || status === 'CAUTION';
                }).length}
              </span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryLabel}>Critical:</span>
              <span className={styles.summaryValue} style={{ color: '#DC382D' }}>
                {equipmentStatus.filter(eq => {
                  const status = getStatusText(eq.latest_metrics);
                  return status === 'CRITICAL';
                }).length}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default EquipmentStatusStrip;