"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import styles from './ProcessHealthMatrix.module.css';

const ProcessHealthMatrix = () => {
  const [equipmentData, setEquipmentData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchEquipmentStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/equipment/status');
      const data = await response.json();
      setEquipmentData(data);
      setIsLoading(false);
      setLastRefresh(new Date());
    } catch (error) {
      console.error('Error fetching equipment status:', error);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchEquipmentStatus();

    // Set up auto-refresh every 10 seconds
    const interval = setInterval(fetchEquipmentStatus, 10000);

    return () => clearInterval(interval);
  }, []);

  const calculateStatus = (metrics) => {
    if (!metrics) return 'unknown';
    const { particle_count, rf_power, temperature } = metrics;

    // Critical thresholds
    if (particle_count > 1000 || rf_power > 1400 || temperature > 75) {
      return 'critical';
    }
    // Warning thresholds
    if (particle_count > 800 || rf_power > 1350 || temperature > 70) {
      return 'warning';
    }
    // Caution thresholds
    if (particle_count > 600 || rf_power > 1300 || temperature > 68) {
      return 'warning';
    }
    return 'good';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'critical':
        return '#DC382D';
      case 'warning':
        return '#FDB813';
      case 'good':
        return '#00684A';
      default:
        return '#6b778c';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'critical':
        return '⚠️';
      case 'warning':
        return '⚡';
      case 'good':
        return '✓';
      default:
        return '•';
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  const processTypes = ['CMP', 'ETCH', 'LITHO'];

  if (isLoading && !equipmentData) {
    return (
      <div className={styles.container}>
        <Card className={styles.card}>
          <div className={styles.header}>
            <h3>Equipment Health Matrix</h3>
            <div className={styles.headerRight}>
              <span className={styles.liveIndicator}>
                <span className={styles.liveDot}></span>
                LIVE
              </span>
            </div>
          </div>
          <div className={styles.loadingGrid}>
            {[1, 2, 3].map(i => (
              <div key={i} className={styles.loadingColumn}>
                <div className={styles.skeleton}></div>
                <div className={styles.skeleton}></div>
                <div className={styles.skeleton}></div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3>Equipment Health Matrix</h3>
            <p className={styles.subtitle}>
              {equipmentData?.total_equipment || 0} tools monitored • Last update: {formatTimestamp(lastRefresh)}
            </p>
          </div>
          <div className={styles.headerRight}>
            <span className={styles.liveIndicator}>
              <span className={styles.liveDot}></span>
              LIVE
            </span>
          </div>
        </div>

        <div className={styles.matrixGrid}>
          {processTypes.map(processType => {
            const equipment = equipmentData?.matrix?.[processType] || [];
            const criticalCount = equipment.filter(e => e.status === 'critical').length;
            const warningCount = equipment.filter(e => e.status === 'warning').length;

            return (
              <div key={processType} className={styles.processColumn}>
                <div className={styles.processHeader}>
                  <h4>{processType}</h4>
                  <div className={styles.statusSummary}>
                    {criticalCount > 0 && (
                      <span className={styles.criticalBadge}>{criticalCount}</span>
                    )}
                    {warningCount > 0 && (
                      <span className={styles.warningBadge}>{warningCount}</span>
                    )}
                    <span className={styles.totalBadge}>{equipment.length}</span>
                  </div>
                </div>

                <div className={styles.equipmentList}>
                  {equipment.length === 0 ? (
                    <div className={styles.noEquipment}>No equipment</div>
                  ) : (
                    equipment.map((eq, index) => (
                      <div
                        key={eq.equipment_id}
                        className={`${styles.equipmentCard} ${styles[eq.status]}`}
                        style={{ animationDelay: `${index * 0.05}s` }}
                      >
                        <div className={styles.equipmentHeader}>
                          <span
                            className={styles.statusDot}
                            style={{ backgroundColor: getStatusColor(eq.status) }}
                          ></span>
                          <span className={styles.equipmentId}>{eq.equipment_id}</span>
                        </div>

                        <div className={styles.equipmentMetrics}>
                          <div className={styles.metricRow}>
                            <span className={styles.metricLabel}>Particles:</span>
                            <span
                              className={styles.metricValue}
                              style={{
                                color: eq.metrics?.particle_count > 1000 ? '#DC382D' :
                                       eq.metrics?.particle_count > 800 ? '#FDB813' : 'inherit'
                              }}
                            >
                              {eq.metrics?.particle_count || 'N/A'}
                            </span>
                          </div>

                          <div className={styles.metricRow}>
                            <span className={styles.metricLabel}>RF Power:</span>
                            <span
                              className={styles.metricValue}
                              style={{
                                color: eq.metrics?.rf_power > 1400 ? '#DC382D' :
                                       eq.metrics?.rf_power > 1350 ? '#FDB813' : 'inherit'
                              }}
                            >
                              {eq.metrics?.rf_power ? `${eq.metrics.rf_power.toFixed(0)}W` : 'N/A'}
                            </span>
                          </div>

                          <div className={styles.metricRow}>
                            <span className={styles.metricLabel}>Temp:</span>
                            <span
                              className={styles.metricValue}
                              style={{
                                color: eq.metrics?.temperature > 75 ? '#DC382D' :
                                       eq.metrics?.temperature > 70 ? '#FDB813' : 'inherit'
                              }}
                            >
                              {eq.metrics?.temperature ? `${eq.metrics.temperature.toFixed(1)}°C` : 'N/A'}
                            </span>
                          </div>

                          {eq.status === 'critical' && (
                            <div className={styles.alertIndicator}>
                              {getStatusIcon(eq.status)} Excursion Detected
                            </div>
                          )}

                          <div className={styles.equipmentFooter}>
                            <span className={styles.lastUpdate}>
                              {formatTimestamp(eq.last_update)}
                            </span>
                          </div>
                        </div>

                        {/* Hover tooltip with all metrics */}
                        <div className={styles.tooltip}>
                          <div className={styles.tooltipHeader}>
                            {eq.equipment_id}
                          </div>
                          <div className={styles.tooltipMetrics}>
                            <div>Particles: {eq.metrics?.particle_count}</div>
                            <div>RF Power: {eq.metrics?.rf_power?.toFixed(1)} W</div>
                            <div>Pressure: {eq.metrics?.chamber_pressure?.toFixed(1)} Torr</div>
                            <div>Temp: {eq.metrics?.temperature?.toFixed(1)} °C</div>
                            <div>Flow: {eq.metrics?.flow_rate?.toFixed(1)} sccm</div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className={styles.legend}>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: '#00684A' }}></span>
            <span>Normal Operation</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: '#FDB813' }}></span>
            <span>Warning</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: '#DC382D' }}></span>
            <span>Critical/Excursion</span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ProcessHealthMatrix;