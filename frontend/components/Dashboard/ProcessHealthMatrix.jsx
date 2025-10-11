"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import Tooltip from '@leafygreen-ui/tooltip';
import IconButton from '@leafygreen-ui/icon-button';
import QueryTransparencyCard from '@/components/common/QueryTransparencyCard';
import styles from './ProcessHealthMatrix.module.css';

const ProcessHealthMatrix = ({ isCollapsed = false, onToggle = () => {} }) => {
  const [equipmentData, setEquipmentData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [showQuery, setShowQuery] = useState(false);

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
        return 'var(--color-status-critical)';
      case 'warning':
        return 'var(--color-status-warning)';
      case 'good':
        return 'var(--color-status-good)';
      default:
        return 'var(--color-status-unknown)';
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

  // MongoDB Time Series query for equipment status
  const equipmentQuery = {
    description: "Time Series Collection Query",
    collection: "process_sensor_ts",
    query: {
      pipeline: [
        {
          $match: {
            timestamp: { $gte: "$$last_30_minutes" },
            equipment_id: { $in: ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "ETCH_02", "LITHO_01", "LITHO_02"] }
          }
        },
        {
          $sort: { timestamp: -1 }
        },
        {
          $group: {
            _id: "$equipment_id",
            latest_timestamp: { $first: "$timestamp" },
            metrics: { $first: "$metrics" },
            process_type: { $first: "$process_type" }
          }
        }
      ]
    },
    performance: {
      avgQueryTime: "12ms",
      documentsScanned: equipmentData?.total_equipment || 6,
      indexUsed: "equipment_id_1_timestamp_-1"
    }
  };

  if (isLoading && !equipmentData) {
    return (
      <div className={styles.container}>
        <Card className={styles.card}>
          <div className={styles.header}>
            <h3>Equipment Health Matrix</h3>
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

  // Collapsed view - vertical strip
  if (isCollapsed) {
    return (
      <div className={styles.collapsedView}>
        <IconButton
          className={styles.toggleButton}
          onClick={onToggle}
          aria-label="Expand Equipment Health Matrix"
        >
          <Icon glyph="ChevronRight" />
        </IconButton>
        <div className={styles.verticalLabel}>Equipment Health</div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <IconButton
          className={styles.collapseButton}
          onClick={onToggle}
          aria-label="Collapse Equipment Health Matrix"
        >
          <Icon glyph="ChevronLeft" />
        </IconButton>
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <div className={styles.titleRow}>
              <h3>Equipment Health Matrix</h3>
              <p className={styles.subtitle}>
                {equipmentData?.total_equipment || 0} tools monitored • Last update: {formatTimestamp(lastRefresh)}
              </p>
            </div>
            <div className={styles.badgeRow}>
              <Badge variant="blue" className={styles.mongoBadge}>
                <Icon glyph="TimeSeries" size="small" /> Time Series Collection
              </Badge>
              <IconButton
                aria-label="Show MongoDB query"
                onClick={() => setShowQuery(!showQuery)}
                className={styles.queryButton}
              >
                <Icon glyph={showQuery ? "ChevronUp" : "Code"} />
              </IconButton>
            </div>
          </div>
        </div>

        {/* Query Transparency Panel */}
        {showQuery && (
          <QueryTransparencyCard
            title="Equipment Status Query"
            query={equipmentQuery}
          />
        )}

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
                      <Tooltip
                        key={eq.equipment_id}
                        align="top"
                        justify="middle"
                        trigger={
                          <div
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
                                    color: eq.metrics?.particle_count > 1000 ? 'var(--color-status-critical)' :
                                           eq.metrics?.particle_count > 800 ? 'var(--color-status-warning)' : 'inherit'
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
                                    color: eq.metrics?.rf_power > 1400 ? 'var(--color-status-critical)' :
                                           eq.metrics?.rf_power > 1350 ? 'var(--color-status-warning)' : 'inherit'
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
                                    color: eq.metrics?.temperature > 75 ? 'var(--color-status-critical)' :
                                           eq.metrics?.temperature > 70 ? 'var(--color-status-warning)' : 'inherit'
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
                          </div>
                        }
                      >
                        <div className={styles.tooltipContent}>
                          <div className={styles.tooltipHeader}>
                            <strong>{eq.equipment_id}</strong>
                          </div>
                          <div className={styles.tooltipMetrics}>
                            <div><strong>Particle Count:</strong> {eq.metrics?.particle_count}</div>
                            <div><strong>RF Power:</strong> {eq.metrics?.rf_power?.toFixed(1)} W</div>
                            <div><strong>Pressure:</strong> {eq.metrics?.chamber_pressure?.toFixed(1)} Torr</div>
                            <div><strong>Temperature:</strong> {eq.metrics?.temperature?.toFixed(1)} °C</div>
                            <div><strong>Flow Rate:</strong> {eq.metrics?.flow_rate?.toFixed(1)} sccm</div>
                            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.2)' }}>
                              <strong>Status:</strong> {eq.status.toUpperCase()}
                            </div>
                          </div>
                        </div>
                      </Tooltip>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className={styles.legend}>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: 'var(--color-status-good)' }}></span>
            <span>Normal Operation</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: 'var(--color-status-warning)' }}></span>
            <span>Warning</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: 'var(--color-status-critical)' }}></span>
            <span>Critical/Excursion</span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ProcessHealthMatrix;