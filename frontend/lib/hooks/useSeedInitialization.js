/**
 * Custom hook for managing seed initialization and dashboard preload
 * 
 * This hook handles the complete initialization flow:
 * 1. Check if seed data exists and is fresh (< 15 minutes)
 * 2. Initialize seed if needed (baseline + anomaly data)
 * 3. Preload all dashboard data in one call
 * 4. Return preloaded data for instant dashboard rendering
 */

import { useState, useEffect, useCallback } from 'react';
import { demoAPI } from '../api';

// Phase constants
const PHASES = {
  CHECKING: 'Checking seed status...',
  SEEDING_BASELINE: 'Seeding baseline data...',
  SEEDING_ANOMALIES: 'Seeding anomaly patterns...',
  LOADING_DASHBOARD: 'Loading dashboard data...',
  PREPARING: 'Preparing visualization...',
  COMPLETE: 'Complete'
};

export const useSeedInitialization = () => {
  const [state, setState] = useState({
    isInitializing: true,
    currentPhase: PHASES.CHECKING,
    progress: 0,
    preloadedData: null,
    error: null
  });

  const initialize = useCallback(async () => {
    try {
      // Phase 1: Check seed status
      setState(prev => ({
        ...prev,
        isInitializing: true,
        currentPhase: PHASES.CHECKING,
        progress: 10,
        error: null
      }));

      console.log('🌱 Checking seed status...');
      const seedStatus = await demoAPI.getSeedStatus();
      console.log('✅ Seed status:', seedStatus);

      // Phase 2: Initialize seed if needed
      if (seedStatus.needs_refresh || !seedStatus.seeded) {
        console.log('🌱 Seed data needs initialization');
        
        // Sub-phase: Seeding baseline
        setState(prev => ({
          ...prev,
          currentPhase: PHASES.SEEDING_BASELINE,
          progress: 20
        }));

        const startTime = Date.now();
        const seedResult = await demoAPI.initializeSeed();
        const seedDuration = Date.now() - startTime;
        
        console.log(`✅ Seed initialized in ${seedDuration}ms:`, seedResult.stats);
        
        // Brief pause for anomaly phase UI
        setState(prev => ({
          ...prev,
          currentPhase: PHASES.SEEDING_ANOMALIES,
          progress: 50
        }));
        
        await new Promise(resolve => setTimeout(resolve, 500));
      } else {
        console.log('✅ Seed data is fresh, skipping initialization');
        setState(prev => ({
          ...prev,
          progress: 50
        }));
      }

      // Phase 3: Preload dashboard data
      setState(prev => ({
        ...prev,
        currentPhase: PHASES.LOADING_DASHBOARD,
        progress: 70
      }));

      console.log('📊 Preloading dashboard data...');
      const preloadStart = Date.now();
      const dashboardData = await demoAPI.getPreloadedData();
      const preloadDuration = Date.now() - preloadStart;
      
      console.log(`✅ Dashboard preloaded in ${preloadDuration}ms`);
      console.log('📊 Data sections:', Object.keys(dashboardData.data || {}));

      // Phase 4: Preparing visualization
      setState(prev => ({
        ...prev,
        currentPhase: PHASES.PREPARING,
        progress: 90
      }));

      // Brief pause for smooth transition
      await new Promise(resolve => setTimeout(resolve, 300));

      // Complete
      setState({
        isInitializing: false,
        currentPhase: PHASES.COMPLETE,
        progress: 100,
        preloadedData: dashboardData.data,
        error: null
      });

      console.log('✅ Initialization complete!');
    } catch (error) {
      console.error('❌ Initialization failed:', error);
      setState(prev => ({
        ...prev,
        isInitializing: false,
        error: error.message || 'Failed to initialize dashboard'
      }));
    }
  }, []);

  // Auto-initialize on mount
  useEffect(() => {
    initialize();
  }, [initialize]);

  // Retry function
  const retry = useCallback(() => {
    console.log('🔄 Retrying initialization...');
    initialize();
  }, [initialize]);

  return {
    isInitializing: state.isInitializing,
    currentPhase: state.currentPhase,
    progress: state.progress,
    preloadedData: state.preloadedData,
    error: state.error,
    retry
  };
};

export default useSeedInitialization;

