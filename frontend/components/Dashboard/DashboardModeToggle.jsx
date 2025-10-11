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
      >
        <SegmentedControlOption value="normal">
          Charts
        </SegmentedControlOption>
        <SegmentedControlOption value="agentic">
          Agentic AI
        </SegmentedControlOption>
      </SegmentedControl>
    </div>
  );
};

export default DashboardModeToggle;
