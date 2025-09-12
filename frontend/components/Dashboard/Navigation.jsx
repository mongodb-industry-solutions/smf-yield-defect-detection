"use client";

import React from 'react';
import { Tabs, Tab } from '@leafygreen-ui/tabs';
import styles from './Navigation.module.css';

const Navigation = ({ activeTab, setActiveTab }) => {
  return (
    <nav className={styles.navigation}>
      <div className={styles.tabContainer}>
        <Tabs
          selected={activeTab}
          setSelected={setActiveTab}
          aria-label="Dashboard Navigation"
        >
          <Tab name="monitoring" label="MONITORING" />
          <Tab name="defects" label="DEFECTS" />
          <Tab name="rca" label="RCA" />
          <Tab name="trends" label="TRENDS" />
        </Tabs>
      </div>
    </nav>
  );
};

export default Navigation;