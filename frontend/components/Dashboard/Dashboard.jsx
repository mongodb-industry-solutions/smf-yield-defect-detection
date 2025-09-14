"use client";

import React, { useState, useEffect } from 'react';
import Header from './Header';
import Navigation from './Navigation';
import Card from '@leafygreen-ui/card';
import { H2, H3, Body } from '@leafygreen-ui/typography';
import Banner from '@leafygreen-ui/banner';

// Import new dashboard components
import FabPulseBar from './FabPulseBar';
import EquipmentFleetGrid from './EquipmentFleetGrid';
import EquipmentFleetList from './EquipmentFleetList';
import CriticalMetricsPanel from './CriticalMetricsPanel';
import IntelligentAlertsPanel from './IntelligentAlertsPanel';
import FilterSearchBar from './FilterSearchBar';
import AlertTicker from './AlertTicker';
import LiveParticleMonitor from './LiveParticleMonitor';
import LiveWaferYieldMap from './LiveWaferYieldMap';
import ProcessHealthMatrix from './ProcessHealthMatrix';

// Import API services
import { equipmentAPI } from '@/lib/api';

// Import utilities
import { WebSocketProvider } from '@/lib/websocket-native';
import styles from './Dashboard.module.css';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('monitoring');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'grid'
  const [equipmentData, setEquipmentData] = useState([]);
  const [isLoadingEquipment, setIsLoadingEquipment] = useState(true);
  
  // Transform backend equipment data to frontend format
  const transformEquipmentData = (backendData) => {
    const transformed = [];
    
    if (!backendData || !backendData.matrix) return [];
    
    Object.entries(backendData.matrix).forEach(([processType, equipmentList]) => {
      equipmentList.forEach(eq => {
        const metrics = eq.metrics || {};
        
        // Determine status based on thresholds
        let status = 'good';
        if (metrics.particle_count > 1200) status = 'critical';
        else if (metrics.particle_count > 1000) status = 'warning';
        else if (metrics.rf_power < 10) status = 'idle';
        else if (metrics.temperature > 100) status = 'warning';
        
        // Calculate utilization
        const utilization = metrics.rf_power ? 
          Math.min(100, Math.round((metrics.rf_power / 1500) * 100)) : 50;
        
        // Transform metrics to frontend format
        const transformedMetrics = {
          particle_count: {
            value: metrics.particle_count || 0,
            status: metrics.particle_count > 1200 ? 'critical' : 
                   metrics.particle_count > 1000 ? 'warning' : 'good',
            threshold: 1000
          },
          pressure: {
            value: metrics.chamber_pressure || 0,
            status: metrics.chamber_pressure > 50 ? 'warning' : 'good',
            threshold: 50
          },
          temperature: {
            value: metrics.temperature || 0,
            status: metrics.temperature > 100 ? 'warning' : 'good',
            threshold: 100
          },
          rf_power: {
            value: metrics.rf_power || 0,
            status: metrics.rf_power > 1500 ? 'warning' : 
                   metrics.rf_power < 10 ? 'idle' : 'good',
            threshold: 1500
          },
          flow_rate: {
            value: metrics.flow_rate || 0,
            status: metrics.flow_rate < 5 ? 'warning' : 'good',
            threshold: 100
          }
        };
        
        transformed.push({
          id: eq.equipment_id,
          name: eq.equipment_id.replace('_', '-'),
          type: processType,
          status: status,
          utilization: utilization,
          currentLot: `L-${Math.floor(Math.random() * 9000) + 1000}`,
          nextMaintenance: `${Math.floor(Math.random() * 168)}h`,
          lastMaintenance: `${Math.floor(Math.random() * 7)} days ago`,
          metrics: transformedMetrics,
          lastUpdate: eq.last_update
        });
      });
    });
    
    return transformed;
  };
  
  // Fetch equipment status from backend
  const fetchEquipmentStatus = async () => {
    try {
      const response = await equipmentAPI.getEquipmentStatus();
      const transformed = transformEquipmentData(response);
      setEquipmentData(transformed);
    } catch (error) {
      console.error('Error fetching equipment status:', error);
      // Could fall back to mock data here if needed
    } finally {
      setIsLoadingEquipment(false);
    }
  };
  
  useEffect(() => {
    // Fetch equipment data on mount
    fetchEquipmentStatus();
    
    // Refresh every 10 seconds
    const interval = setInterval(() => {
      fetchEquipmentStatus();
    }, 10000);
    
    return () => clearInterval(interval);
  }, []);
  
  const renderTabContent = () => {
    switch(activeTab) {
      case 'monitoring':
        return (
          <div className={styles.monitoringDashboard}>
            {/* Fab Pulse Bar - Key KPIs */}
            <FabPulseBar />
            
            {/* Alert Ticker - Top scrolling alerts */}
            <AlertTicker />
            
            {/* Main Dashboard Layout - 60/40 split */}
            <div className={styles.dashboardLayout}>
              {/* Left Side - Critical Metrics (60%) */}
              <div className={styles.metricsSection}>
                {/* Live Particle Monitor */}
                <div className={styles.metricCard}>
                  <LiveParticleMonitor />
                </div>
                
                {/* Live Wafer Yield Map */}
                <div className={styles.metricCard}>
                  <LiveWaferYieldMap />
                </div>
                
                {/* Process Health Matrix */}
                <div className={styles.metricCard}>
                  <ProcessHealthMatrix />
                </div>
              </div>
              
              {/* Right Side - Equipment Fleet Status (40%) */}
              <div className={styles.fleetSection}>
                <div className={styles.sectionHeader}>
                  <H3 className={styles.sectionTitle}>EQUIPMENT FLEET STATUS</H3>
                </div>
                <div className={styles.filterBar}>
                  <FilterSearchBar 
                    onSearch={setSearchTerm}
                    onStatusFilter={setStatusFilter}
                    onTypeFilter={setTypeFilter}
                  />
                </div>
                <div className={styles.fleetContent}>
                  <EquipmentFleetList 
                    equipment={equipmentData}
                    searchTerm={searchTerm}
                    statusFilter={statusFilter}
                    typeFilter={typeFilter}
                  />
                </div>
              </div>
            </div>
          </div>
        );
        
      case 'defects':
        return (
          <div className={styles.contentArea}>
            <Card className={styles.placeholderCard}>
              <H2>Wafer Defect Analysis</H2>
              <Body>
                Interactive wafer maps with vector similarity search for pattern matching.
                MongoDB Atlas Vector Search enables 99% accuracy in defect classification.
              </Body>
              <div className={styles.placeholder}>
                Coming Soon: Wafer visualization with defect heatmaps
              </div>
            </Card>
          </div>
        );
        
      case 'rca':
        return (
          <div className={styles.contentArea}>
            <Card className={styles.placeholderCard}>
              <H2>AI-Powered Root Cause Analysis</H2>
              <Body>
                LangGraph workflow visualization showing multi-step analysis process.
                Reduces MTTR by 85% through intelligent pattern recognition.
              </Body>
              <div className={styles.placeholder}>
                Coming Soon: Interactive RCA workflow
              </div>
            </Card>
          </div>
        );
        
      case 'trends':
        return (
          <div className={styles.contentArea}>
            <Card className={styles.placeholderCard}>
              <H2>Historical Trends & Analytics</H2>
              <Body>
                Time-series analysis powered by MongoDB's optimized bucketing strategy.
                Analyze yield trends, defect patterns, and equipment performance over time.
              </Body>
              <div className={styles.placeholder}>
                Coming Soon: Advanced analytics dashboard
              </div>
            </Card>
          </div>
        );
        
      default:
        return null;
    }
  };
  
  return (
    <WebSocketProvider>
      <div className={styles.dashboard}>
        <Header />
        <Navigation activeTab={activeTab} setActiveTab={setActiveTab} />
        <main className={styles.main}>
          {renderTabContent()}
        </main>
      </div>
    </WebSocketProvider>
  );
};

export default Dashboard;