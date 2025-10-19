/**
 * Seed Loading Screen Component
 * 
 * Full-screen loading overlay shown during initial seed initialization and dashboard preload.
 * Displays progress through multiple phases with visual indicators.
 */

import React from 'react';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import { Spinner } from '@leafygreen-ui/loading-indicator';
import styles from './SeedLoadingScreen.module.css';

const PHASE_CONFIGS = [
  {
    id: 'checking',
    label: 'Checking seed status',
    icon: 'Refresh',
    estimate: '< 1s'
  },
  {
    id: 'baseline',
    label: 'Seeding baseline data',
    icon: 'Cloud',
    estimate: '~6s'
  },
  {
    id: 'anomalies',
    label: 'Seeding anomaly patterns',
    icon: 'ImportantWithCircle',
    estimate: '~4s'
  },
  {
    id: 'dashboard',
    label: 'Loading dashboard data',
    icon: 'Charts',
    estimate: '~2s'
  },
  {
    id: 'preparing',
    label: 'Preparing visualization',
    icon: 'Checkmark',
    estimate: '~1s'
  }
];

const SeedLoadingScreen = ({ phase = 'Checking seed status...', progress = 0 }) => {
  // Determine which phase is active based on the phase text
  const getPhaseState = (phaseConfig) => {
    const phaseText = phase.toLowerCase();
    const configLabel = phaseConfig.label.toLowerCase();
    
    if (phaseText.includes(configLabel.split(' ')[1])) {
      return 'active';
    }
    
    // Check if this phase should be marked as completed
    const phaseOrder = ['checking', 'baseline', 'anomalies', 'dashboard', 'preparing'];
    const currentPhaseIndex = phaseOrder.findIndex(p => phaseText.includes(p) || phaseText.includes('seed') && p === 'baseline');
    const configPhaseIndex = phaseOrder.indexOf(phaseConfig.id);
    
    if (configPhaseIndex < currentPhaseIndex) {
      return 'completed';
    }
    
    return 'pending';
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.container}>
        {/* Animated MongoDB-style spinner */}
        <div className={styles.spinnerWrapper}>
          <Spinner />
        </div>

        {/* Main heading */}
        <h1 className={styles.heading}>Initializing Monitoring Dashboard</h1>
        
        {/* Current phase text */}
        <p className={styles.phaseText}>{phase}</p>

        {/* Progress bar */}
        <div className={styles.progressBarContainer}>
          <div className={styles.progressBarBackground}>
            <div 
              className={styles.progressBarFill}
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className={styles.progressPercent}>{progress}%</span>
        </div>

        {/* Phase list */}
        <div className={styles.phasesList}>
          {PHASE_CONFIGS.map((phaseConfig) => {
            const state = getPhaseState(phaseConfig);
            
            return (
              <div 
                key={phaseConfig.id} 
                className={`${styles.phaseItem} ${styles[`phaseItem--${state}`]}`}
              >
                <div className={styles.phaseIcon}>
                  {state === 'completed' ? (
                    <Icon glyph="Checkmark" className={styles.iconCompleted} />
                  ) : state === 'active' ? (
                    <Spinner />
                  ) : (
                    <Icon glyph={phaseConfig.icon} className={styles.iconPending} />
                  )}
                </div>
                
                <div className={styles.phaseContent}>
                  <span className={styles.phaseLabel}>{phaseConfig.label}</span>
                  {state === 'pending' && (
                    <Badge variant="lightgray" className={styles.phaseEstimate}>
                      {phaseConfig.estimate}
                    </Badge>
                  )}
                  {state === 'completed' && (
                    <Badge variant="green" className={styles.phaseComplete}>
                      Complete
                    </Badge>
                  )}
                  {state === 'active' && (
                    <Badge variant="blue" className={styles.phaseActive}>
                      In progress
                    </Badge>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer note */}
        <p className={styles.footerNote}>
          <Icon glyph="InfoWithCircle" size="small" />
          <span>First-time initialization • Subsequent loads will be instant</span>
        </p>
      </div>
    </div>
  );
};

export default SeedLoadingScreen;

