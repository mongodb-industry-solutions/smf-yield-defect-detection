"use client";

import React from 'react';
import FabPulseBar from './FabPulseBar';
import ProcessHealthMatrix from './ProcessHealthMatrix';
import AlertsPanel from './AlertsPanel';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import styles from './Dashboard.module.css';

const Dashboard = () => {
  const { refresh } = useDashboardData();

  return (
    <div className={styles.dashboard}>
      <FabPulseBar />
      <div className={styles.dashboardBody}>
        <div className={styles.leftPanel}>
          <ProcessHealthMatrix />
        </div>
        <div className={styles.centerPanel}>
          {/* Space for other monitoring widgets */}
          <div className={styles.placeholder}>
            <h3>Main Monitoring Area</h3>
            <p>Live charts and analytics will go here</p>
          </div>
        </div>
        <div className={styles.rightPanel}>
          <AlertsPanel />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;