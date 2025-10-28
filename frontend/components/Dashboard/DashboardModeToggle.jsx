"use client";

import React from 'react';
import { SegmentedControl, SegmentedControlOption } from '@leafygreen-ui/segmented-control';
import styles from './DashboardModeToggle.module.css';

const DashboardModeToggle = ({ mode, onModeChange }) => {
  return (
    <div className={styles.floatingContainer}>
      <SegmentedControl
        size="default"
        value={mode}
        onChange={(value) => onModeChange(value)}
        aria-controls="dashboard-content"
      >
        <SegmentedControlOption value="search" aria-controls="dashboard-content">
          Search
        </SegmentedControlOption>
        <SegmentedControlOption value="normal" aria-controls="dashboard-content">
          Charts
        </SegmentedControlOption>
        <SegmentedControlOption value="agentic" aria-controls="dashboard-content">
          Agentic AI
        </SegmentedControlOption>
      </SegmentedControl>
    </div>
  );
};

export default DashboardModeToggle;
