"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import { demoAPI } from '@/lib/api';
import styles from './DemoControlPanel.module.css';

// Equipment-specific excursion thresholds (aligned with backend config/thresholds.py)
const EXCURSION_THRESHOLDS = {
  temperature: {
    CMP: { baseline: 65, alert_threshold: 70, unit: '°C' },
    ETCH: { baseline: 70, alert_threshold: 75, unit: '°C' },
    LITHO: { baseline: 22, alert_threshold: 25, unit: '°C' }
  },
  rf_power: {
    CMP: { baseline: 1450, alert_threshold: 1550, unit: 'W' },
    ETCH: { baseline: 1200, alert_threshold: 1300, unit: 'W' },
    LITHO: { baseline: 800, alert_threshold: 900, unit: 'W' }
  }
};

const DemoControlPanel = ({ dashboardMode = 'normal', onAnalysisComplete }) => {
  // Demo Mode State (for 'normal' and 'charts' modes)
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [excursionForm, setExcursionForm] = useState({
    equipment_id: 'CMP_TOOL_01',
    excursion_type: 'temperature', // 'temperature', 'rf_power' (physics-based: root causes only)
    excursion_value: null // Optional explicit value (°C for temp, W for RF power)
  });
  const [injectionSuccess, setInjectionSuccess] = useState(null);

  // Helper function: Get threshold info for current equipment and excursion type
  const getCurrentThresholdInfo = () => {
    const equipmentType = excursionForm.equipment_id.split('_')[0]; // CMP, ETCH, LITHO
    return EXCURSION_THRESHOLDS[excursionForm.excursion_type][equipmentType];
  };

  // Fetch status function
  const fetchStatus = async () => {
    try {
      const data = await demoAPI.getStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching demo status:', err);
      setError('Failed to fetch status');
    }
  };

  // Fetch status on mount (no polling needed)
  useEffect(() => {
    fetchStatus(); // Initial fetch

    // Poll demo status every 5 seconds to detect auto-stop
    const statusPollInterval = setInterval(() => {
      fetchStatus();
    }, 5000);

    // Cleanup on unmount
    return () => {
      clearInterval(statusPollInterval);
    };
  }, []);

  // Handle Start/Stop toggle
  const handleToggle = async () => {
    setLoading(true);
    setError(null);

    try {
      if (status?.active) {
        // Stop demo mode
        if (window.confirm('Stop demo mode? This will cleanup recent alerts.')) {
          await demoAPI.stop();
          await fetchStatus();
        }
      } else {
        // Start demo mode (manual injection only, no auto-excursions)
        const params = {
          mode: 'charts',
          scenario: 'continuous'
          // excursion_probability defaults to 0.0 (manual only)
        };

        await demoAPI.start(params);
        await fetchStatus();
      }
    } catch (err) {
      console.error('Error toggling demo mode:', err);
      setError(`Failed to ${status?.active ? 'stop' : 'start'} demo mode`);
    } finally {
      setLoading(false);
    }
  };

  // Start tracking lot progress
  const startLotProgressTracking = (durationSeconds) => {
    const startTime = Date.now();
    const endTime = startTime + (durationSeconds * 1000);

    // Update progress every second
    const interval = setInterval(async () => {
      const now = Date.now();
      const elapsed = (now - startTime) / 1000;
      const remaining = Math.max(0, (endTime - now) / 1000);
      const progress = Math.min(100, (elapsed / durationSeconds) * 100);

      setLotProgress({
        elapsed: Math.floor(elapsed),
        remaining: Math.floor(remaining),
        progress: Math.floor(progress),
        currentWafer: Math.floor((elapsed / durationSeconds) * 25) + 1,
        totalWafers: 25
      });

      // Check if complete OR if backend auto-stopped
      if (remaining <= 0) {
        clearInterval(interval);
        setProgressInterval(null);
        setLotProgress(null);
        // Fetch final status - backend should have auto-stopped
        await fetchStatus();
      } else if (Math.floor(elapsed) % 5 === 0) {
        // Also check backend status every 5 seconds
        try {
          const currentStatus = await demoAPI.getStatus();
          if (!currentStatus.active) {
            // Backend has stopped (manually or auto)
            clearInterval(interval);
            setProgressInterval(null);
            setLotProgress(null);
            setStatus(currentStatus);
          }
        } catch (err) {
          console.error('Error checking status:', err);
        }
      }
    }, 1000);

    setProgressInterval(interval);
  };

  // Handle excursion injection
  const handleInjectExcursion = async () => {
    setLoading(true);
    setError(null);
    setInjectionSuccess(null);

    try {
      // Build payload with optional explicit excursion value
      const payload = {
        equipment_id: excursionForm.equipment_id,
        excursion_type: excursionForm.excursion_type
      };

      // Add explicit value if provided (otherwise backend auto-calculates)
      if (excursionForm.excursion_value !== null) {
        if (excursionForm.excursion_type === 'temperature') {
          payload.temperature = excursionForm.excursion_value;
        } else if (excursionForm.excursion_type === 'rf_power') {
          payload.rf_power = excursionForm.excursion_value;
        }
      }

      const result = await demoAPI.injectExcursionNextCycle(payload);

      const excursionLabel = excursionForm.excursion_type === 'rf_power' ? 'RF Power Drift' :
                             excursionForm.excursion_type === 'temperature' ? 'Temperature Drift' :
                             'Root Cause';
      const valueStr = excursionForm.excursion_value
        ? ` (${excursionForm.excursion_value}${getCurrentThresholdInfo().unit})`
        : '';
      const injectsIn = result?.injects_in_seconds || 5;
      setInjectionSuccess(`${excursionLabel}${valueStr} excursion scheduled for ${excursionForm.equipment_id}! Will inject in ~${injectsIn}s (no demo restart needed)`);

      // Notify wafer map component to show loading state
      const event = new CustomEvent('excursionInjected', {
        detail: {
          equipment_id: excursionForm.equipment_id,
          excursion_type: excursionForm.excursion_type,
          injects_in_seconds: injectsIn
        }
      });
      window.dispatchEvent(event);

      // Demo continues running - no need to refresh status

      // Clear success message after 5 seconds
      setTimeout(() => setInjectionSuccess(null), 5000);
    } catch (err) {
      console.error('Error injecting excursion:', err);
      setError('Failed to inject excursion');
    } finally {
      setLoading(false);
    }
  };

  // NORMAL MODE - Standard Demo Control Panel
  return (
    <Card className={styles.compactPanel}>
      <div className={styles.compactContainer}>
        {/* Left: Status & Control */}
        <div className={styles.leftSection}>
          <div className={styles.statusBadge}>
            <span className={styles.demoLabel}>
              🚧 DEMO
            </span>
            <span className={status?.active ? styles.activeIndicator : styles.inactiveIndicator}>
              {status?.active ? '● ACTIVE' : '○ INACTIVE'}
            </span>
          </div>

          <Button
            variant={status?.active ? 'danger' : 'primary'}
            size="small"
            disabled={loading}
            onClick={handleToggle}
            className={styles.compactToggle}
          >
            {loading ? '...' : (status?.active ? 'Stop' : 'Start')}
          </Button>
        </div>

        {/* Right: Auto-Excursions Toggle & Excursion Injection */}
        <div className={styles.rightSection}>
          <div className={styles.injectionControls}>
            <select
              className={styles.compactSelect}
              value={excursionForm.equipment_id}
              onChange={(e) => setExcursionForm({...excursionForm, equipment_id: e.target.value})}
              disabled={!status?.active}
            >
              <option value="CMP_TOOL_01">CMP_01</option>
              <option value="CMP_TOOL_02">CMP_02</option>
              <option value="ETCH_01">ETCH_01</option>
              <option value="ETCH_02">ETCH_02</option>
              <option value="LITHO_01">LITHO_01</option>
              <option value="LITHO_02">LITHO_02</option>
            </select>

            <select
              className={styles.compactSelect}
              value={excursionForm.excursion_type}
              onChange={(e) => setExcursionForm({
                ...excursionForm,
                excursion_type: e.target.value,
                excursion_value: null  // Reset value when switching between temp/RF
              })}
              disabled={!status?.active}
              title={
                excursionForm.excursion_type === 'rf_power'
                  ? '⚡ RF power drift → particle count calculated'
                  : '🌡️ Temperature drift → particle count calculated'
              }
            >
              <option value="temperature">🌡️ Temperature Drift</option>
              <option value="rf_power">⚡ RF Power Drift</option>
            </select>

            <div className={styles.valueInputGroup}>
              <input
                type="number"
                className={styles.compactInput}
                value={excursionForm.excursion_value || ''}
                onChange={(e) => setExcursionForm({
                  ...excursionForm,
                  excursion_value: e.target.value ? parseFloat(e.target.value) : null
                })}
                placeholder={`e.g. ${getCurrentThresholdInfo().alert_threshold}`}
                disabled={!status?.active}
                title={`${getCurrentThresholdInfo().unit === '°C' ? 'Temperature' : 'RF Power'}: Baseline ${getCurrentThresholdInfo().baseline}${getCurrentThresholdInfo().unit}, Alert at ${getCurrentThresholdInfo().alert_threshold}${getCurrentThresholdInfo().unit}+`}
              />
              <span className={styles.unitLabel}>{getCurrentThresholdInfo().unit}</span>
            </div>

            <Button
              variant="default"
              size="small"
              disabled={loading || !status?.active}
              onClick={handleInjectExcursion}
              className={styles.compactInject}
            >
              Inject
            </Button>
          </div>

          {injectionSuccess && (
            <div className={styles.compactSuccess}>✓</div>
          )}
        </div>
      </div>

      {/* Error messages */}
      {error && (
        <div className={styles.compactError}>
          {error}
        </div>
      )}
    </Card>
  );
};

export default DemoControlPanel;