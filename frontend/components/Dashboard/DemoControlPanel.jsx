"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import Toggle from '@leafygreen-ui/toggle';
import { demoAPI, aiAgentAPI } from '@/lib/api';
import styles from './DemoControlPanel.module.css';

const DemoControlPanel = ({ dashboardMode = 'normal', onAnalysisComplete }) => {
  // Demo Mode State (for 'normal' and 'charts' modes)
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [excursionForm, setExcursionForm] = useState({
    equipment_id: 'CMP_TOOL_01',
    excursion_type: 'particle' // 'particle', 'rf_power', 'temperature'
  });
  const [injectionSuccess, setInjectionSuccess] = useState(null);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(null);

  // Auto-excursions state
  const [autoExcursionsEnabled, setAutoExcursionsEnabled] = useState(false);
  const [autoExcursionsLoading, setAutoExcursionsLoading] = useState(false);

  // Agentic AI Mode State (for 'agentic' mode)
  const [selectedScenario, setSelectedScenario] = useState('gradual_drift');
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [currentAgent, setCurrentAgent] = useState(null); // 1, 2, 3, or 4
  const [progressPercent, setProgressPercent] = useState(0);
  const [alertId, setAlertId] = useState(null);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const [pipelineError, setPipelineError] = useState(null);

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

  // Fetch auto-excursions status
  const fetchAutoExcursionsStatus = async () => {
    try {
      const data = await aiAgentAPI.getStatus();
      setAutoExcursionsEnabled(data.enabled);
    } catch (err) {
      console.error('Error fetching auto-excursions status:', err);
    }
  };

  // Fetch status on mount (no polling needed)
  useEffect(() => {
    fetchStatus(); // Initial fetch
    fetchAutoExcursionsStatus(); // Fetch auto-excursions status
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
        // Start demo mode with appropriate mode based on auto-excursions status
        // If auto-excursions are DISABLED, use agentic mode (excursion probability = 0)
        // If auto-excursions are ENABLED, use charts mode (normal probability)
        const params = autoExcursionsEnabled ? { mode: 'charts' } : { mode: 'agentic' };
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

  // Handle excursion injection
  const handleInjectExcursion = async () => {
    setLoading(true);
    setError(null);
    setInjectionSuccess(null);

    try {
      const result = await demoAPI.injectExcursion({
        equipment_id: excursionForm.equipment_id,
        excursion_type: excursionForm.excursion_type
      });

      const excursionLabel = excursionForm.excursion_type === 'particle' ? 'Particle Count' :
                             excursionForm.excursion_type === 'rf_power' ? 'RF Power' :
                             'Temperature';
      setInjectionSuccess(`${excursionLabel} excursion injected on ${excursionForm.equipment_id}!`);

      // Clear success message after 5 seconds
      setTimeout(() => setInjectionSuccess(null), 5000);
    } catch (err) {
      console.error('Error injecting excursion:', err);
      setError('Failed to inject excursion');
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

  // Handle auto-excursions toggle
  const handleAutoExcursionsToggle = async (checked) => {
    setAutoExcursionsLoading(true);
    try {
      await aiAgentAPI.toggle(checked);
      setAutoExcursionsEnabled(checked);
      console.log(`Auto-excursions ${checked ? 'enabled' : 'disabled'}`);
    } catch (err) {
      console.error('Error toggling auto-excursions:', err);
      setError('Failed to toggle auto-excursions');
      // Revert on error
      setAutoExcursionsEnabled(!checked);
    } finally {
      setAutoExcursionsLoading(false);
    }
  };

  // Handle AI Agent Pipeline Execution
  const handleRunAnalysis = async () => {
    setPipelineRunning(true);
    setPipelineError(null);
    setAnalysisComplete(false);
    setProgressPercent(0);
    setCurrentAgent(null);
    setAlertId(null);

    try {
      // Agent 1: Monitoring Agent (12-15s)
      console.log('🤖 Running Agent 1: Monitoring Agent...');
      setCurrentAgent(1);
      setProgressPercent(25);
      const monitoringResponse = await fetch(
        `http://localhost:8000/ai-agents/analyze-scenario/${selectedScenario}`,
        { method: 'POST' }
      );
      if (!monitoringResponse.ok) throw new Error('Monitoring Agent failed');
      const monitoringData = await monitoringResponse.json();
      const newAlertId = monitoringData.alert_id;
      setAlertId(newAlertId);
      console.log(`✅ Agent 1 complete. Alert ID: ${newAlertId}`);

      // Notify parent Dashboard about the created alert
      if (onAnalysisComplete) {
        onAnalysisComplete(newAlertId);
      }

      // Agent 2: Investigation Agent (21-26s)
      console.log('🤖 Running Agent 2: Investigation Agent...');
      setCurrentAgent(2);
      setProgressPercent(50);
      const investigationResponse = await fetch(
        `http://localhost:8000/ai-agents/agent-2-investigation/${newAlertId}`,
        { method: 'POST' }
      );
      if (!investigationResponse.ok) throw new Error('Investigation Agent failed');
      console.log('✅ Agent 2 complete');

      // Agent 3: RCA Agent (15-25s)
      console.log('🤖 Running Agent 3: RCA Agent...');
      setCurrentAgent(3);
      setProgressPercent(75);
      const rcaResponse = await fetch(
        `http://localhost:8000/ai-agents/agent-3-rca/${newAlertId}`,
        { method: 'POST' }
      );
      if (!rcaResponse.ok) throw new Error('RCA Agent failed');
      console.log('✅ Agent 3 complete');

      // Agent 4: Supervisor Agent (18-22s)
      console.log('🤖 Running Agent 4: Supervisor Agent...');
      setCurrentAgent(4);
      setProgressPercent(100);
      const supervisorResponse = await fetch(
        `http://localhost:8000/ai-agents/agent-4-supervisor/${newAlertId}`,
        { method: 'POST' }
      );
      if (!supervisorResponse.ok) throw new Error('Supervisor Agent failed');
      console.log('✅ Agent 4 complete');

      // Pipeline complete!
      setAnalysisComplete(true);
      console.log(`🎉 Full pipeline complete! Total time: ~66-88s. Alert ID: ${newAlertId}`);

    } catch (err) {
      console.error('Pipeline error:', err);
      setPipelineError(err.message || 'Pipeline execution failed');
    } finally {
      setPipelineRunning(false);
    }
  };

  // Conditional Rendering based on dashboardMode
  if (dashboardMode === 'agentic') {
    // AGENTIC AI MODE - Scenario Analysis Panel
    return (
      <Card className={styles.compactPanel}>
        <div className={styles.agenticContainer}>
          {/* Left: Scenario Selection */}
          <div className={styles.scenarioSection}>
            <span className={styles.scenarioLabel}>🤖 AI Analysis Scenario</span>
            <select
              className={styles.scenarioSelect}
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              disabled={pipelineRunning}
            >
              <option value="gradual_drift">Gradual Drift Pattern</option>
              <option value="sudden_spike">Sudden Spike Event</option>
              <option value="oscillating_pattern">Oscillating Pattern</option>
            </select>
          </div>

          {/* Right: Run Analysis Button & Progress */}
          <div className={styles.analysisSection}>
            <Button
              variant="primary"
              size="small"
              disabled={pipelineRunning}
              onClick={handleRunAnalysis}
              className={styles.runAnalysisButton}
            >
              {pipelineRunning ? 'Running...' : 'Run Analysis'}
            </Button>

            {/* Pipeline Progress */}
            {pipelineRunning && currentAgent && (
              <div className={styles.pipelineProgress}>
                <div className={styles.progressBar}>
                  <div
                    className={styles.progressFill}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <span className={styles.agentStatus}>
                  Agent {currentAgent}/4 • {progressPercent}%
                </span>
              </div>
            )}

            {/* Analysis Complete */}
            {analysisComplete && alertId && (
              <div className={styles.analysisComplete}>
                ✅ Analysis Complete • Alert: {alertId.slice(0, 8)}...
              </div>
            )}

            {/* Pipeline Error */}
            {pipelineError && (
              <div className={styles.pipelineError}>
                ❌ {pipelineError}
              </div>
            )}
          </div>
        </div>
      </Card>
    );
  }

  // CHARTS MODE - Standard Demo Control Panel
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

        {/* Right: Auto-Excursions Toggle & Excursion Injection */}
        <div className={styles.rightSection}>
          {/* Auto-Excursions Toggle */}
          <div className={styles.aiToggleContainer}>
            <span className={styles.aiLabel}>Auto Excursions</span>
            <Toggle
              size="small"
              checked={autoExcursionsEnabled}
              onChange={handleAutoExcursionsToggle}
              disabled={autoExcursionsLoading || status?.active}
              aria-label="Toggle Automatic Excursions"
              title={status?.active ? "Stop demo mode to change auto-excursions setting" : "Enable/disable automatic excursions"}
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
              value={excursionForm.excursion_type}
              onChange={(e) => setExcursionForm({...excursionForm, excursion_type: e.target.value})}
              disabled={!status?.active}
              title={
                excursionForm.excursion_type === 'particle' ? '⚠️ Particle count excursion' :
                excursionForm.excursion_type === 'rf_power' ? '⚡ RF power drift' :
                '🌡️ Temperature drift'
              }
            >
              <option value="particle">⚠️ Particle</option>
              <option value="rf_power">⚡ RF Power</option>
              <option value="temperature">🌡️ Temperature</option>
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