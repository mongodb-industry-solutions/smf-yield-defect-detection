"use client";

import React from 'react';
import styles from './LoadingSkeletons.module.css';

export const EquipmentCardSkeleton = () => (
  <div className={styles.equipmentCardSkeleton}>
    <div className={styles.cardHeader}>
      <div className={styles.titleSkeleton} />
      <div className={styles.badgeSkeleton} />
    </div>
    <div className={styles.cardBody}>
      <div className={styles.metricSkeleton} />
      <div className={styles.metricSkeleton} />
      <div className={styles.sparklineSkeleton} />
    </div>
    <div className={styles.cardFooter}>
      <div className={styles.footerSkeleton} />
    </div>
  </div>
);

export const AlertCardSkeleton = () => (
  <div className={styles.alertCardSkeleton}>
    <div className={styles.alertHeader}>
      <div className={styles.iconSkeleton} />
      <div className={styles.alertContent}>
        <div className={styles.titleSkeleton} />
        <div className={styles.messageSkeleton} />
        <div className={styles.correlationSkeleton} />
      </div>
    </div>
  </div>
);

export const MetricCardSkeleton = () => (
  <div className={styles.metricCardSkeleton}>
    <div className={styles.metricHeader}>
      <div className={styles.labelSkeleton} />
    </div>
    <div className={styles.metricValue}>
      <div className={styles.valueSkeleton} />
      <div className={styles.trendSkeleton} />
    </div>
    <div className={styles.chartSkeleton} />
  </div>
);

export const EquipmentFleetSkeleton = () => (
  <div className={styles.fleetSkeleton}>
    {[...Array(6)].map((_, i) => (
      <EquipmentCardSkeleton key={i} />
    ))}
  </div>
);

export const AlertsPanelSkeleton = () => (
  <div className={styles.alertsPanelSkeleton}>
    {[...Array(4)].map((_, i) => (
      <AlertCardSkeleton key={i} />
    ))}
  </div>
);

export const CriticalMetricsSkeleton = () => (
  <div className={styles.metricsSkeleton}>
    {[...Array(4)].map((_, i) => (
      <MetricCardSkeleton key={i} />
    ))}
  </div>
);