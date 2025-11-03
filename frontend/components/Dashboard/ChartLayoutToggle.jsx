"use client";

import React from 'react';
import { SegmentedControl, SegmentedControlOption } from '@leafygreen-ui/segmented-control';
import Icon from '@leafygreen-ui/icon';
import styles from './ChartLayoutToggle.module.css';

/**
 * ChartLayoutToggle Component
 * 
 * Provides a toggle control for switching between grid and vertical chart layouts
 * in the dashboard's normal mode.
 */
const ChartLayoutToggle = ({ layout, onLayoutChange }) => {
  return (
    <div className={styles.layoutToggleContainer}>
      <SegmentedControl
        size="small"
        value={layout}
        onChange={(value) => onLayoutChange(value)}
        aria-label="Chart layout toggle"
      >
        <SegmentedControlOption value="grid" aria-label="Grid layout">
          <div className={styles.optionContent}>
            <Icon glyph="Apps" size="small" />
            <span>Grid</span>
          </div>
        </SegmentedControlOption>
        <SegmentedControlOption value="vertical" aria-label="Vertical layout">
          <div className={styles.optionContent}>
            <Icon glyph="Menu" size="small" />
            <span>Stack</span>
          </div>
        </SegmentedControlOption>
      </SegmentedControl>
    </div>
  );
};

export default ChartLayoutToggle;

