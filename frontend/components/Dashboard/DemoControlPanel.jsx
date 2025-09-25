"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import { demoAPI } from '@/lib/api';
import styles from './DemoControlPanel.module.css';

const DemoControlPanel = () => {
  // State management
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [excursionForm, setExcursionForm] = useState({
    equipment_id: 'CMP_TOOL_01',
    excursion_type: 'particle'
  });
  const [injectionSuccess, setInjectionSuccess] = useState(null);

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

  // Fetch status on mount and set up polling
  useEffect(() => {
    fetchStatus(); // Initial fetch

    // Poll every 2 seconds
    const interval = setInterval(fetchStatus, 2000);

    return () => clearInterval(interval); // Cleanup on unmount
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
        // Start demo mode
        await demoAPI.start();
        await fetchStatus();
      }
    } catch (err) {
      console.error('Error toggling demo mode:', err);
      setError(`Failed to ${status?.active ? 'stop' : 'start'} demo mode`);
    } finally {
      setLoading(false);
    }
  };

  // Handle excursion injection
  const handleInjectExcursion = async () => {
    setLoading(true);
    setError(null);
    setInjectionSuccess(null);

    try {
      const result = await demoAPI.injectExcursion(excursionForm);
      setInjectionSuccess(`Excursion injected for ${result.equipment_id}! Alert will be created within 3 seconds.`);

      // Clear success message after 5 seconds
      setTimeout(() => setInjectionSuccess(null), 5000);
    } catch (err) {
      console.error('Error injecting excursion:', err);
      setError('Failed to inject excursion');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className={styles.compactPanel}>
      <div className={styles.compactContainer}>
        {/* Left: Status & Control */}
        <div className={styles.leftSection}>
          <div className={styles.statusBadge}>
            <span className={styles.demoLabel}>🚧 DEMO</span>
            <span className={status?.active ? styles.activeIndicator : styles.inactiveIndicator}>
              {status?.active ? '● ACTIVE' : '○ INACTIVE'}
            </span>
          </div>

          {status?.active && (
            <div className={styles.rateInfo}>
              <span>{status?.expected_rate?.per_minute || '--'}/min</span>
              <span className={styles.separator}>•</span>
              <span>{status?.expected_rate?.per_2_minutes || '--'}/2min</span>
            </div>
          )}

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

        {/* Right: Excursion Injection */}
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
              <option value="LITHO_01">LITHO_01</option>
            </select>

            <select
              className={styles.compactSelect}
              value={excursionForm.excursion_type}
              onChange={(e) => setExcursionForm({...excursionForm, excursion_type: e.target.value})}
              disabled={!status?.active}
            >
              <option value="particle">Particle</option>
              <option value="temperature">Temp</option>
              <option value="rf_power">RF</option>
            </select>

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

      {/* Error bar if needed */}
      {error && (
        <div className={styles.compactError}>
          {error}
        </div>
      )}
    </Card>
  );
};

export default DemoControlPanel;