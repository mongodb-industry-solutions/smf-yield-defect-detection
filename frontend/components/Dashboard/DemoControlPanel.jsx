"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import Toggle from '@leafygreen-ui/toggle';
import Select from '@leafygreen-ui/select';
import { Option } from '@leafygreen-ui/select';
import { demoAPI, aiAgentAPI, alertAPI } from '@/lib/api';
import styles from './DemoControlPanel.module.css';

const DemoControlPanel = ({ dashboardMode = 'normal', onAnalysisComplete }) => {
  // Demo Mode State (for 'normal' and 'charts' modes)
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [demoScenario, setDemoScenario] = useState('continuous'); // 'continuous', 'lot_processing_drift', 'lot_processing_spike', 'lot_processing_oscillation'
  const [excursionForm, setExcursionForm] = useState({
    equipment_id: 'CMP_TOOL_01',
    excursion_type: 'particle' // 'particle', 'rf_power', 'temperature'
  });
  const [injectionSuccess, setInjectionSuccess] = useState(null);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(null);

  // Lot processing progress tracking
  const [lotProgress, setLotProgress] = useState(null);
  const [progressInterval, setProgressInterval] = useState(null);

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

  // Previously Analyzed Alerts State
  const [analyzedAlerts, setAnalyzedAlerts] = useState([]);
  const [selectedAlertId, setSelectedAlertId] = useState('');
  const [loadingAnalyzedAlerts, setLoadingAnalyzedAlerts] = useState(false);
  const [loadingAlertData, setLoadingAlertData] = useState(false);

  // Lot Processing Alerts State (for selecting existing alerts to analyze)
  const [lotAlerts, setLotAlerts] = useState([]);
  const [selectedLotAlertId, setSelectedLotAlertId] = useState('');
  const [loadingLotAlerts, setLoadingLotAlerts] = useState(false);

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

  // Fetch previously analyzed alerts
  const fetchAnalyzedAlerts = async () => {
    setLoadingAnalyzedAlerts(true);
    try {
      const data = await alertAPI.getAnalyzedAlerts(50);
      setAnalyzedAlerts(data.alerts || []);
      console.log('📊 Loaded analyzed alerts:', data.alerts?.length);
    } catch (err) {
      console.error('Error fetching analyzed alerts:', err);
    } finally {
      setLoadingAnalyzedAlerts(false);
    }
  };

  // Fetch lot processing alerts (for reusing in agentic AI mode)
  const fetchLotAlerts = async () => {
    setLoadingLotAlerts(true);
    try {
      // Fetch recent alerts
      const data = await alertAPI.getAll(50);

      // Filter for lot processing alerts (have scenario_id and is_lot_processing_scenario)
      const filtered = (data.alerts || []).filter(alert => {
        const sourceData = alert.source_data || {};
        return sourceData.scenario_id && sourceData.is_lot_processing_scenario === true;
      });

      setLotAlerts(filtered);
      console.log('📦 Loaded lot processing alerts:', filtered.length);
    } catch (err) {
      console.error('Error fetching lot alerts:', err);
      setLotAlerts([]);
    } finally {
      setLoadingLotAlerts(false);
    }
  };

  // Handle alert selection and load its data
  const handleAlertSelection = async (alertId) => {
    if (!alertId) {
      setSelectedAlertId('');
      setAlertId(null);
      setAnalysisComplete(false);
      return;
    }

    setSelectedAlertId(alertId);
    setLoadingAlertData(true);
    setPipelineError(null);

    try {
      console.log('📥 Loading alert data for:', alertId);

      // Fetch alert details to get agent analysis
      const agentDetails = await alertAPI.getAgentDetails(alertId);
      console.log('📊 Agent details loaded:', agentDetails);

      // Set alert ID and mark analysis as complete
      setAlertId(alertId);
      setAnalysisComplete(true);
      setCurrentAgent(null);
      setProgressPercent(100);

      // Notify parent component that analysis data is loaded
      if (onAnalysisComplete) {
        onAnalysisComplete(alertId);
      }

      console.log('✅ Alert analysis loaded successfully');
    } catch (err) {
      console.error('❌ Error loading alert data:', err);
      setPipelineError('Failed to load alert analysis data');
    } finally {
      setLoadingAlertData(false);
    }
  };

  // Fetch status on mount (no polling needed)
  useEffect(() => {
    fetchStatus(); // Initial fetch
    fetchAutoExcursionsStatus(); // Fetch auto-excursions status
    fetchAnalyzedAlerts(); // Fetch previously analyzed alerts

    // Poll demo status every 5 seconds to detect auto-stop
    const statusPollInterval = setInterval(() => {
      fetchStatus();
    }, 5000);

    // Cleanup on unmount
    return () => {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      clearInterval(statusPollInterval);
    };
  }, []);

  // Fetch lot processing alerts when in agentic mode
  useEffect(() => {
    if (dashboardMode === 'agentic') {
      fetchLotAlerts();
    }
  }, [dashboardMode]);

  // Handle Start/Stop toggle
  const handleToggle = async () => {
    setLoading(true);
    setError(null);

    try {
      if (status?.active) {
        // Stop demo mode
        const confirmMsg = demoScenario.startsWith('lot_processing_')
          ? 'Stop lot processing?'
          : 'Stop demo mode? This will cleanup recent alerts.';
        if (window.confirm(confirmMsg)) {
          // Clear progress interval if running
          if (progressInterval) {
            clearInterval(progressInterval);
            setProgressInterval(null);
          }
          setLotProgress(null);

          await demoAPI.stop();
          await fetchStatus();
        }
      } else {
        // Check if this is a lot processing scenario - use bulk insert instead of gradual demo
        if (demoScenario.startsWith('lot_processing_')) {
          // Bulk insert all lot data at once (no 3-minute wait)
          const result = await demoAPI.bulkInsertLot(demoScenario);
          console.log('✅ Bulk lot insertion complete:', result);

          // Show success message with lot ID
          setInjectionSuccess(result.message);
          setTimeout(() => setInjectionSuccess(null), 5000);

          // No need to fetch status or start progress tracking - instant insertion
        } else {
          // Start demo mode with appropriate mode based on auto-excursions status
          // If auto-excursions are DISABLED, use agentic mode (excursion probability = 0)
          // If auto-excursions are ENABLED, use charts mode (normal probability)
          const params = {
            mode: autoExcursionsEnabled ? 'charts' : 'agentic',
            scenario: demoScenario
          };

          const result = await demoAPI.start(params);
          await fetchStatus();
        }
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
      const result = await demoAPI.injectExcursion({
        equipment_id: excursionForm.equipment_id,
        excursion_type: excursionForm.excursion_type
      });

      const excursionLabel = excursionForm.excursion_type === 'particle' ? 'Particle Count' :
                             excursionForm.excursion_type === 'rf_power' ? 'RF Power' :
                             'Temperature';
      setInjectionSuccess(`${excursionLabel} excursion injected on ${excursionForm.equipment_id}!`);

      // Refresh demo status (excursion injection stops demo mode)
      await fetchStatus();

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

  // Handle AI Agent Pipeline Execution using LangGraph
  const handleRunAnalysis = async () => {
    setPipelineRunning(true);
    setPipelineError(null);
    setAnalysisComplete(false);
    setProgressPercent(0);
    setCurrentAgent(1);
    setAlertId(null);

    try {
      let newAlertId = null;
      let response = null;

      // Simulate progress updates for better UX
      let progressInterval;
      const startProgressSimulation = () => {
        let currentProgress = 0;
        progressInterval = setInterval(() => {
          currentProgress += 2;
          if (currentProgress <= 95) {
            setProgressPercent(currentProgress);
            // Update agent number based on progress
            if (currentProgress < 25) setCurrentAgent(1);
            else if (currentProgress < 50) setCurrentAgent(2);
            else if (currentProgress < 75) setCurrentAgent(3);
            else setCurrentAgent(4);
          }
        }, 1200);
      };

      // OPTION 1: Analyze existing lot processing alert with LangGraph
      if (selectedLotAlertId) {
        console.log('🔄 Running LangGraph workflow on existing alert:', selectedLotAlertId);

        // Start progress simulation
        startProgressSimulation();

        // Use LangGraph workflow with existing alert
        response = await aiAgentAPI.runLangGraphWorkflow(selectedScenario, selectedLotAlertId);

        clearInterval(progressInterval);
        newAlertId = response.alert_id;

        console.log('✅ LangGraph workflow complete. Used existing alert:', newAlertId);
        console.log('📊 Workflow Response:', JSON.stringify(response, null, 2));
      }
      // OPTION 2: Create new alert from scenario with LangGraph
      else {
        console.log('🆕 Running LangGraph workflow for new scenario:', selectedScenario);

        // Start progress simulation
        startProgressSimulation();

        // Use LangGraph workflow without alert_id (will create new alert)
        response = await aiAgentAPI.runLangGraphWorkflow(selectedScenario);

        clearInterval(progressInterval);
        newAlertId = response.alert_id;

        console.log('✅ LangGraph workflow complete. Created new alert:', newAlertId);
        console.log('📊 Workflow Response:', JSON.stringify(response, null, 2));
      }

      // Set final state
      setAlertId(newAlertId);
      setProgressPercent(100);
      setCurrentAgent(4);

      // Notify parent Dashboard about the created/analyzed alert
      if (onAnalysisComplete) {
        onAnalysisComplete(newAlertId);
      }

      // Pipeline complete!
      setAnalysisComplete(true);
      console.log(`🎉 Full LangGraph pipeline complete! Alert ID: ${newAlertId}`);

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
          {/* Left: Scenario Selection & Previously Analyzed Alerts */}
          <div className={styles.scenarioSection}>
            {/* Option 1: Select existing lot processing alert */}
            <div style={{ marginBottom: '12px' }}>
              <span className={styles.scenarioLabel}>Lot Processing Alerts</span>
              <select
                className={styles.scenarioSelect}
                value={selectedLotAlertId}
                onChange={async (e) => {
                  const alertId = e.target.value;
                  setSelectedLotAlertId(alertId);

                  if (alertId) {
                    // Clear other selections
                    setSelectedAlertId('');

                    // Load the alert data and display it (if it has agent analysis already)
                    setLoadingAlertData(true);
                    setPipelineError(null);

                    try {
                      console.log('📥 Loading lot processing alert data:', alertId);

                      // Fetch alert details to check if it has agent analysis
                      const alert = await alertAPI.getById(alertId);
                      console.log('📊 Alert data:', alert);

                      // Check if this alert already has AI agent analysis
                      const hasAgentAnalysis = alert.alert?.supervisor_agent_analysis ||
                                               alert.alert?.rca_agent_analysis ||
                                               alert.alert?.investigation_agent_analysis ||
                                               alert.alert?.monitoring_agent_analysis;

                      if (hasAgentAnalysis) {
                        // Alert already analyzed - display it
                        console.log('✅ Alert already has agent analysis - loading for display');
                        setAlertId(alertId);
                        setAnalysisComplete(true);
                        setCurrentAgent(null);
                        setProgressPercent(100);

                        // Notify parent component
                        if (onAnalysisComplete) {
                          onAnalysisComplete(alertId);
                        }
                      } else {
                        // Alert not yet analyzed - just set it for analysis
                        console.log('📝 Alert not yet analyzed - ready to run pipeline');
                        setAlertId(null);
                        setAnalysisComplete(false);
                      }
                    } catch (err) {
                      console.error('❌ Error loading lot alert:', err);
                      setPipelineError('Failed to load alert data');
                    } finally {
                      setLoadingAlertData(false);
                    }
                  } else {
                    // Cleared selection
                    setAlertId(null);
                    setAnalysisComplete(false);
                  }
                }}
                disabled={pipelineRunning || loadingAlertData || loadingLotAlerts}
              >
                <option value="">
                  {loadingLotAlerts ? 'Loading...' : 'Select an alert to analyze...'}
                </option>
                {lotAlerts.map((alert) => {
                  const sourceData = alert.source_data || {};
                  const scenarioLabel = sourceData.scenario_id === 'gradual_drift' ? 'Drift' :
                                       sourceData.scenario_id === 'sudden_spike' ? 'Spike' :
                                       sourceData.scenario_id === 'oscillating_pattern' ? 'Oscillation' : 'Unknown';
                  return (
                    <option key={alert.alert_id} value={alert.alert_id}>
                      {alert.lot_id} • {scenarioLabel} • {alert.severity?.toUpperCase()} • {new Date(alert.timestamp).toLocaleTimeString()}
                    </option>
                  );
                })}
              </select>
              {loadingLotAlerts && (
                <div style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>
                  Loading lot processing alerts...
                </div>
              )}
            </div>
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
          {/* Scenario Selector - only show when demo is not active */}
          {!status?.active && (
            <select
              className={styles.compactSelect}
              value={demoScenario}
              onChange={(e) => setDemoScenario(e.target.value)}
              disabled={loading}
              style={{ marginRight: '8px' }}
            >
              <option value="continuous">Continuous</option>
              <option value="lot_processing_drift">Lot: Gradual Drift (3 min)</option>
              <option value="lot_processing_spike">Lot: Sudden Spike (3 min)</option>
              <option value="lot_processing_oscillation">Lot: Oscillation (3 min)</option>
            </select>
          )}

          <div className={styles.statusBadge}>
            <span className={styles.demoLabel}>
              {demoScenario.startsWith('lot_processing_') ? '📦 LOT' : '🚧 DEMO'}
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

      {/* Lot Processing Progress */}
      {status?.active && demoScenario.startsWith('lot_processing_') && lotProgress && (
        <div className={styles.lotProgressSection}>
          <div className={styles.progressInfo}>
            <span>
              Lot 2025 ({demoScenario.split('_')[2]}): Wafer {lotProgress.currentWafer}/{lotProgress.totalWafers}
            </span>
            <span className={styles.progressTime}>
              Time: {Math.floor(lotProgress.elapsed / 60)}:{(lotProgress.elapsed % 60).toString().padStart(2, '0')} / 3:00
            </span>
          </div>
          <div className={styles.progressBar}>
            <div
              className={styles.progressFill}
              style={{ width: `${lotProgress.progress}%` }}
            />
          </div>
          {/* Show excursion warnings based on scenario pattern */}
          {demoScenario === 'lot_processing_drift' && lotProgress.currentWafer >= 10 && lotProgress.currentWafer <= 17 && (
            <div className={styles.excursionWarning}>
              ⚠️ Gradual particle increase at wafer {lotProgress.currentWafer}
            </div>
          )}
          {demoScenario === 'lot_processing_spike' && lotProgress.currentWafer === 15 && (
            <div className={styles.excursionWarning}>
              ⚠️ Sudden particle spike at wafer {lotProgress.currentWafer}
            </div>
          )}
          {demoScenario === 'lot_processing_oscillation' && lotProgress.currentWafer >= 12 && lotProgress.currentWafer <= 19 && (
            <div className={styles.excursionWarning}>
              ⚠️ Cyclic particle pattern at wafer {lotProgress.currentWafer}
            </div>
          )}
        </div>
      )}

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