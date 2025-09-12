"use client";

import React, { useState } from 'react';
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

// Import data
import { equipmentStatus, fabMetrics } from '@/lib/mockData';

// Import utilities
import { WebSocketProvider } from '@/lib/websocket';
import styles from './Dashboard.module.css';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('monitoring');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'grid'
  
  const renderTabContent = () => {
    switch(activeTab) {
      case 'monitoring':
        return (
          <div className={styles.monitoringDashboard}>
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
                    equipment={equipmentStatus}
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