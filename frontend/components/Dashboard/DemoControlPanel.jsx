"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import Toggle from '@leafygreen-ui/toggle';
import { demoAPI, aiAgentAPI } from '@/lib/api';
import styles from './DemoControlPanel.module.css';

const DemoControlPanel = () => {
  // State management
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [excursionForm, setExcursionForm] = useState({
    equipment_id: 'CMP_TOOL_01',
    pattern: 'drift' // 'drift', 'spike', 'false_positive', 'oscillation'
  });
  const [injectionSuccess, setInjectionSuccess] = useState(null);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(null);

  // AI Agent state
  const [aiEnabled, setAiEnabled] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);

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

  // Fetch AI agent status
  const fetchAIStatus = async () => {
    try {
      const data = await aiAgentAPI.getStatus();
      setAiEnabled(data.enabled);
    } catch (err) {
      console.error('Error fetching AI agent status:', err);
    }
  };

  // Fetch status on mount and set up polling
  useEffect(() => {
    fetchStatus(); // Initial fetch
    fetchAIStatus(); // Fetch AI status

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
        // Start demo mode with appropriate mode based on AI agents status
        // If AI agents are enabled, set excursion probability to 0 for manual pattern injection
        const params = aiEnabled ? { mode: 'agentic' } : { mode: 'charts' };
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

  // Handle pattern injection
  const handleInjectExcursion = async () => {
    setLoading(true);
    setError(null);
    setInjectionSuccess(null);

    try {
      const result = await demoAPI.injectPattern({
        equipment_id: excursionForm.equipment_id,
        pattern: excursionForm.pattern
      });

      setInjectionSuccess(`${excursionForm.pattern.toUpperCase()} pattern injected! Will evolve over ${result.total_stages} batches.`);

      // Clear success message after 5 seconds
      setTimeout(() => setInjectionSuccess(null), 5000);
    } catch (err) {
      console.error('Error injecting pattern:', err);
      setError('Failed to inject pattern');
    } finally {
      setLoading(false);
    }
  };

  // Handle demo reset
  const handleReset = async () => {
    setResetLoading(true);
    setError(null);
    setResetSuccess(null);

    try {
      const result = await demoAPI.reset();
      setResetSuccess(`Reset complete! ${result.alerts_resolved} alerts resolved, ${result.healthy_wafers_generated} healthy wafers generated. New yield: ${result.new_yield}%`);

      // Clear success message after 7 seconds
      setTimeout(() => setResetSuccess(null), 7000);

      // Trigger page refresh after 2 seconds to update all dashboards
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err) {
      console.error('Error resetting demo:', err);
      setError('Failed to reset demo');
    } finally {
      setResetLoading(false);
    }
  };

  // Handle AI Agent toggle
  const handleAIToggle = async (checked) => {
    setAiLoading(true);
    try {
      await aiAgentAPI.toggle(checked);
      setAiEnabled(checked);
      console.log(`AI Agents ${checked ? 'enabled' : 'disabled'}`);
    } catch (err) {
      console.error('Error toggling AI agents:', err);
      setError('Failed to toggle AI agents');
      // Revert on error
      setAiEnabled(!checked);
    } finally {
      setAiLoading(false);
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

          {status?.active && (
            <Button
              variant="primary"
              size="small"
              disabled={resetLoading}
              onClick={handleReset}
              className={styles.compactReset}
              style={{ marginLeft: '8px' }}
            >
              {resetLoading ? '...' : 'Reset Demo'}
            </Button>
          )}
        </div>

        {/* Right: AI Toggle & Excursion Injection */}
        <div className={styles.rightSection}>
          {/* AI Agent Toggle */}
          <div className={styles.aiToggleContainer}>
            <span className={styles.aiLabel}>AI Agents</span>
            <Toggle
              size="small"
              checked={aiEnabled}
              onChange={handleAIToggle}
              disabled={aiLoading}
              aria-label="Toggle AI Agents"
            />
          </div>

          <div className={styles.divider}></div>

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
              value={excursionForm.pattern}
              onChange={(e) => setExcursionForm({...excursionForm, pattern: e.target.value})}
              disabled={!status?.active}
              title={
                excursionForm.pattern === 'drift' ? '📈 Gradual increase - filter degradation' :
                excursionForm.pattern === 'spike' ? '⚡ Sudden persistent - equipment malfunction' :
                excursionForm.pattern === 'false_positive' ? '🔔 Single spike - tests AI filtering' :
                '🌊 Cyclic pattern - recurring issue'
              }
            >
              <option value="drift">📈 Drift</option>
              <option value="spike">⚡ Spike</option>
              <option value="false_positive">🔔 False+</option>
              <option value="oscillation">🌊 Oscillation</option>
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

      {/* Success/Error messages */}
      {resetSuccess && (
        <div className={styles.compactSuccess} style={{ marginTop: '8px' }}>
          ✅ {resetSuccess}
        </div>
      )}
      {error && (
        <div className={styles.compactError}>
          {error}
        </div>
      )}
    </Card>
  );
};

export default DemoControlPanel;