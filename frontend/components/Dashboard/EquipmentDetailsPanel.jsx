"use client";

import React, { useState, useEffect } from 'react';
import Button from '@leafygreen-ui/button';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import IconButton from '@leafygreen-ui/icon-button';
import { Tab, Tabs } from '@leafygreen-ui/tabs';
import Card from '@leafygreen-ui/card';
import { H2, H3, Body, Description, Label } from '@leafygreen-ui/typography';
import { equipmentAPI } from '@/lib/api';
import { getSeverityVariant, getStatusColor } from '@/lib/design-tokens';
import styles from './EquipmentDetailsPanel.module.css';

const EquipmentDetailsPanel = ({ equipmentId, isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState(0);
  const [equipmentData, setEquipmentData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [timeWindow, setTimeWindow] = useState(24);

  // Fetch equipment details when panel opens
  useEffect(() => {
    if (isOpen && equipmentId) {
      fetchEquipmentDetails();
    } else if (!isOpen) {
      // Reset state when panel closes
      setActiveTab(0);
      setEquipmentData(null);
      setError(null);
    }
  }, [isOpen, equipmentId, timeWindow]);

  const fetchEquipmentDetails = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await equipmentAPI.getEquipmentDetails(equipmentId, timeWindow);
      setEquipmentData(data);
    } catch (err) {
      console.error('Error fetching equipment details:', err);
      setError(err.message || 'Failed to load equipment details');
    } finally {
      setIsLoading(false);
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
    return date.toLocaleString();
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getMetricColor = (value, threshold, reverse = false) => {
    if (reverse) {
      return value >= threshold ? 'var(--color-status-good)' : 'var(--color-status-critical)';
    }
    return value > threshold ? 'var(--color-status-critical)' : 'var(--color-status-good)';
  };

  const renderOverviewTab = () => {
    if (!equipmentData) return null;

    const { current_metrics, statistics, status } = equipmentData;

    return (
      <div className={styles.tabContent}>
        {/* Current Status Section */}
        <Card className={styles.sectionCard}>
          <div className={styles.sectionHeader}>
            <Icon glyph="ActivityFeed" />
            <H3>Current Status</H3>
          </div>
          <div className={styles.statusGrid}>
            <div className={styles.statusItem}>
              <Label>Equipment Status</Label>
              <div className={styles.statusBadgeRow}>
                <span
                  className={styles.statusDot}
                  style={{ backgroundColor: getStatusColor(status) }}
                />
                <Badge variant={getSeverityVariant(status)}>
                  {status?.toUpperCase() || 'UNKNOWN'}
                </Badge>
              </div>
            </div>
            <div className={styles.statusItem}>
              <Label>Last Update</Label>
              <Body>{formatTimestamp(equipmentData.last_update)}</Body>
            </div>
          </div>
        </Card>

        {/* Current Metrics Section */}
        {current_metrics && (
          <Card className={styles.sectionCard}>
            <div className={styles.sectionHeader}>
              <Icon glyph="Charts" />
              <H3>Current Metrics</H3>
            </div>
            <div className={styles.metricsGrid}>
              <div className={styles.metricItem}>
                <Label>Particle Count</Label>
                <div
                  className={styles.metricValue}
                  style={{ color: getMetricColor(current_metrics.particle_count, 1000) }}
                >
                  {current_metrics.particle_count?.toFixed(0) || 'N/A'}
                </div>
                <Description>Threshold: &lt; 1000</Description>
              </div>
              <div className={styles.metricItem}>
                <Label>RF Power</Label>
                <div
                  className={styles.metricValue}
                  style={{ color: getMetricColor(current_metrics.rf_power, 1400) }}
                >
                  {current_metrics.rf_power?.toFixed(1) || 'N/A'} W
                </div>
                <Description>Threshold: &lt; 1400W</Description>
              </div>
              <div className={styles.metricItem}>
                <Label>Temperature</Label>
                <div
                  className={styles.metricValue}
                  style={{ color: getMetricColor(current_metrics.temperature, 75) }}
                >
                  {current_metrics.temperature?.toFixed(1) || 'N/A'} °C
                </div>
                <Description>Threshold: &lt; 75°C</Description>
              </div>
              <div className={styles.metricItem}>
                <Label>Chamber Pressure</Label>
                <div className={styles.metricValue}>
                  {current_metrics.chamber_pressure?.toFixed(1) || 'N/A'} Torr
                </div>
                <Description>Normal range</Description>
              </div>
              <div className={styles.metricItem}>
                <Label>Flow Rate</Label>
                <div className={styles.metricValue}>
                  {current_metrics.flow_rate?.toFixed(1) || 'N/A'} sccm
                </div>
                <Description>Normal range</Description>
              </div>
            </div>
          </Card>
        )}

        {/* Statistics Section */}
        {statistics && (
          <Card className={styles.sectionCard}>
            <div className={styles.sectionHeader}>
              <Icon glyph="ChartBar" />
              <H3>24-Hour Statistics</H3>
            </div>
            <div className={styles.statsGrid}>
              <div className={styles.statItem}>
                <div className={styles.statValue}>{statistics.total_wafers_processed}</div>
                <Label>Wafers Processed</Label>
              </div>
              <div className={styles.statItem}>
                <div
                  className={styles.statValue}
                  style={{ color: getMetricColor(statistics.avg_yield_24h, 85, true) }}
                >
                  {statistics.avg_yield_24h?.toFixed(2) || '0'}%
                </div>
                <Label>Average Yield</Label>
              </div>
              <div className={styles.statItem}>
                <div
                  className={styles.statValue}
                  style={{ color: statistics.excursion_count_24h > 0 ? 'var(--color-status-warning)' : 'var(--color-status-good)' }}
                >
                  {statistics.excursion_count_24h}
                </div>
                <Label>Excursions</Label>
              </div>
              <div className={styles.statItem}>
                <div className={styles.statValue}>{statistics.utilization_percentage?.toFixed(1) || '0'}%</div>
                <Label>Utilization</Label>
              </div>
            </div>
          </Card>
        )}
      </div>
    );
  };

  const renderWafersLotsTab = () => {
    if (!equipmentData) return null;

    const { related_lots, related_wafers } = equipmentData;

    return (
      <div className={styles.tabContent}>
        {/* Related Lots Section */}
        <Card className={styles.sectionCard}>
          <div className={styles.sectionHeader}>
            <Icon glyph="Folder" />
            <H3>Related Lots ({related_lots?.length || 0})</H3>
          </div>
          {related_lots && related_lots.length > 0 ? (
            <div className={styles.lotsList}>
              {related_lots.map((lot, index) => (
                <div key={index} className={styles.lotCard}>
                  <div className={styles.lotHeader}>
                    <Body className={styles.lotId}>{lot.lot_id}</Body>
                    <Badge variant="lightgray">{lot.wafer_count} wafers</Badge>
                  </div>
                  <div className={styles.lotMetrics}>
                    <div className={styles.lotMetric}>
                      <Label>Avg Yield</Label>
                      <Body
                        style={{
                          color: getMetricColor(lot.avg_yield, 85, true),
                          fontWeight: 600
                        }}
                      >
                        {lot.avg_yield}%
                      </Body>
                    </div>
                    <div className={styles.lotMetric}>
                      <Label>Inspection Period</Label>
                      <Description>{lot.inspection_period}</Description>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <Icon glyph="InformationWithCircle" />
              <Description>No lots found in the selected time window</Description>
            </div>
          )}
        </Card>

        {/* Related Wafers Section */}
        <Card className={styles.sectionCard}>
          <div className={styles.sectionHeader}>
            <Icon glyph="Beaker" />
            <H3>Recent Wafers ({related_wafers?.length || 0})</H3>
          </div>
          {related_wafers && related_wafers.length > 0 ? (
            <div className={styles.wafersList}>
              {related_wafers.map((wafer, index) => (
                <div key={index} className={styles.waferRow}>
                  <div className={styles.waferInfo}>
                    <Body className={styles.waferId}>{wafer.wafer_id}</Body>
                    <Description>{wafer.lot_id || 'No lot'}</Description>
                  </div>
                  <div className={styles.waferMetrics}>
                    <div
                      className={styles.yieldBadge}
                      style={{
                        backgroundColor: wafer.yield_percentage >= 85 ? 'rgba(0, 104, 74, 0.1)' : 'rgba(253, 184, 19, 0.1)',
                        color: wafer.yield_percentage >= 85 ? '#00684A' : '#FDB813'
                      }}
                    >
                      {wafer.yield_percentage?.toFixed(2)}%
                    </div>
                    <Badge variant="lightgray">{wafer.defect_pattern}</Badge>
                  </div>
                  <Description className={styles.waferTimestamp}>
                    {formatDate(wafer.inspection_timestamp)}
                  </Description>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <Icon glyph="InformationWithCircle" />
              <Description>No wafers found in the selected time window</Description>
            </div>
          )}
        </Card>
      </div>
    );
  };

  const renderProcessMaterialsTab = () => {
    if (!equipmentData) return null;

    const { process_materials } = equipmentData;
    const { slurry_batches, recipes, reticles } = process_materials || {};

    return (
      <div className={styles.tabContent}>
        {/* Slurry Batches Section */}
        <Card className={styles.sectionCard}>
          <div className={styles.sectionHeader}>
            <Icon glyph="Beaker" />
            <H3>Slurry Batches ({slurry_batches?.length || 0})</H3>
          </div>
          {slurry_batches && slurry_batches.length > 0 ? (
            <div className={styles.materialsList}>
              {slurry_batches.map((batch, index) => (
                <div
                  key={index}
                  className={`${styles.materialCard} ${batch.is_problematic ? styles.problematic : ''}`}
                >
                  <div className={styles.materialHeader}>
                    <Body className={styles.materialId}>{batch.batch_id}</Body>
                    <div className={styles.materialBadges}>
                      {batch.is_problematic && (
                        <Badge variant="red">
                          <Icon glyph="Warning" size="small" /> Problematic
                        </Badge>
                      )}
                      <Badge variant="lightgray">Used {batch.usage_count}x</Badge>
                    </div>
                  </div>
                  {batch.issues && batch.issues.length > 0 && (
                    <div className={styles.issuesList}>
                      <Label>Issues:</Label>
                      <ul>
                        {batch.issues.map((issue, i) => (
                          <li key={i}>
                            <Description>{issue}</Description>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <Icon glyph="InformationWithCircle" />
              <Description>No slurry batches found for this equipment</Description>
            </div>
          )}
        </Card>

        {/* Etch Recipes Section */}
        <Card className={styles.sectionCard}>
          <div className={styles.sectionHeader}>
            <Icon glyph="Code" />
            <H3>Etch Recipes ({recipes?.length || 0})</H3>
          </div>
          {recipes && recipes.length > 0 ? (
            <div className={styles.materialsList}>
              {recipes.map((recipe, index) => (
                <div key={index} className={styles.materialCard}>
                  <div className={styles.materialHeader}>
                    <Body className={styles.materialId}>{recipe.recipe_id}</Body>
                    <Badge variant="lightgray">Used {recipe.usage_count}x</Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <Icon glyph="InformationWithCircle" />
              <Description>No etch recipes applicable for this equipment type</Description>
            </div>
          )}
        </Card>

        {/* Reticles Section */}
        <Card className={styles.sectionCard}>
          <div className={styles.sectionHeader}>
            <Icon glyph="Sparkle" />
            <H3>Reticles ({reticles?.length || 0})</H3>
          </div>
          {reticles && reticles.length > 0 ? (
            <div className={styles.materialsList}>
              {reticles.map((reticle, index) => (
                <div key={index} className={styles.materialCard}>
                  <div className={styles.materialHeader}>
                    <Body className={styles.materialId}>{reticle.reticle_id}</Body>
                    <Badge variant="lightgray">Used {reticle.usage_count}x</Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <Icon glyph="InformationWithCircle" />
              <Description>No reticles applicable for this equipment type</Description>
            </div>
          )}
        </Card>
      </div>
    );
  };

  const renderAlertsPerformanceTab = () => {
    if (!equipmentData) return null;

    const { recent_alerts, statistics } = equipmentData;

    return (
      <div className={styles.tabContent}>
        {/* Recent Alerts Section */}
        <Card className={styles.sectionCard}>
          <div className={styles.sectionHeader}>
            <Icon glyph="Bell" />
            <H3>Recent Alerts ({recent_alerts?.length || 0})</H3>
          </div>
          {recent_alerts && recent_alerts.length > 0 ? (
            <div className={styles.alertsList}>
              {recent_alerts.map((alert, index) => (
                <div key={index} className={`${styles.alertCard} ${styles[alert.severity]}`}>
                  <div className={styles.alertHeader}>
                    <Badge variant={getSeverityVariant(alert.severity)}>
                      {alert.severity?.toUpperCase()}
                    </Badge>
                    <Badge variant={alert.status === 'open' ? 'red' : 'lightgray'}>
                      {alert.status?.toUpperCase()}
                    </Badge>
                  </div>
                  <Body className={styles.alertType}>{alert.alert_type?.replace(/_/g, ' ')}</Body>
                  <Description className={styles.alertTimestamp}>
                    {formatTimestamp(alert.timestamp)}
                  </Description>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <Icon glyph="CheckmarkWithCircle" />
              <Description>No recent alerts for this equipment</Description>
            </div>
          )}
        </Card>

        {/* Performance Summary */}
        {statistics && (
          <Card className={styles.sectionCard}>
            <div className={styles.sectionHeader}>
              <Icon glyph="ChartBar" />
              <H3>Performance Summary</H3>
            </div>
            <div className={styles.performanceGrid}>
              <div className={styles.performanceItem}>
                <div className={styles.performanceIcon} style={{ backgroundColor: 'rgba(0, 104, 74, 0.1)' }}>
                  <Icon glyph="Checkmark" fill="#00684A" />
                </div>
                <div className={styles.performanceContent}>
                  <div className={styles.performanceValue}>
                    {statistics.total_wafers_processed}
                  </div>
                  <Label>Total Wafers</Label>
                  <Description>Processed in last {equipmentData.time_window_hours}h</Description>
                </div>
              </div>
              <div className={styles.performanceItem}>
                <div className={styles.performanceIcon} style={{ backgroundColor: 'rgba(0, 104, 74, 0.1)' }}>
                  <Icon glyph="ChartBar" fill="#00684A" />
                </div>
                <div className={styles.performanceContent}>
                  <div className={styles.performanceValue} style={{
                    color: getMetricColor(statistics.avg_yield_24h, 85, true)
                  }}>
                    {statistics.avg_yield_24h?.toFixed(2)}%
                  </div>
                  <Label>Average Yield</Label>
                  <Description>Target: ≥ 85%</Description>
                </div>
              </div>
              <div className={styles.performanceItem}>
                <div className={styles.performanceIcon} style={{
                  backgroundColor: statistics.excursion_count_24h > 0 ? 'rgba(253, 184, 19, 0.1)' : 'rgba(0, 104, 74, 0.1)'
                }}>
                  <Icon glyph="Warning" fill={statistics.excursion_count_24h > 0 ? '#FDB813' : '#00684A'} />
                </div>
                <div className={styles.performanceContent}>
                  <div className={styles.performanceValue} style={{
                    color: statistics.excursion_count_24h > 0 ? 'var(--color-status-warning)' : 'var(--color-status-good)'
                  }}>
                    {statistics.excursion_count_24h}
                  </div>
                  <Label>Excursions</Label>
                  <Description>In last {equipmentData.time_window_hours}h</Description>
                </div>
              </div>
            </div>
          </Card>
        )}
      </div>
    );
  };

  if (!isOpen) return null;

  // Loading state
  if (isLoading && !equipmentData) {
    return (
      <div className={styles.backdrop} onClick={onClose}>
        <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
          <div className={styles.loadingState}>
            <div className={styles.spinner}></div>
            <Body>Loading equipment details...</Body>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !equipmentData) {
    return (
      <div className={styles.backdrop} onClick={onClose}>
        <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
          <div className={styles.errorState}>
            <Icon glyph="Warning" size="large" fill="var(--color-status-critical)" />
            <H3>Error Loading Equipment Details</H3>
            <Description>{error}</Description>
            <Button onClick={fetchEquipmentDetails}>Retry</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.panelHeader}>
          <div className={styles.headerContent}>
            <div className={styles.headerTitle}>
              <Icon glyph="Laptop" size="large" />
              <div>
                <H2>{equipmentId}</H2>
                <Description>Process: {equipmentData?.process_step || 'Unknown'}</Description>
              </div>
            </div>
            <IconButton
              aria-label="Close panel"
              onClick={onClose}
              className={styles.closeButton}
            >
              <Icon glyph="X" />
            </IconButton>
          </div>
          {equipmentData && (
            <div className={styles.headerBadges}>
              <Badge variant={getSeverityVariant(equipmentData.status)}>
                {equipmentData.status?.toUpperCase()}
              </Badge>
              <Badge variant="blue">
                <Icon glyph="Clock" size="small" /> {equipmentData.time_window_hours}h window
              </Badge>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className={styles.tabsContainer}>
          <Tabs
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            className={styles.tabs}
          >
            <Tab name="Overview">
              {renderOverviewTab()}
            </Tab>
            <Tab name="Wafers & Lots">
              {renderWafersLotsTab()}
            </Tab>
            <Tab name="Process Materials">
              {renderProcessMaterialsTab()}
            </Tab>
            <Tab name="Alerts & Performance">
              {renderAlertsPerformanceTab()}
            </Tab>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default EquipmentDetailsPanel;
