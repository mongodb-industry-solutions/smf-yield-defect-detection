import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { alertAPI, equipmentAPI, kpiAPI } from '../lib/api';

// Create context
const DashboardDataContext = createContext();

// Hook to use dashboard data
export const useDashboardData = () => {
  const context = useContext(DashboardDataContext);
  if (!context) {
    throw new Error('useDashboardData must be used within DashboardDataProvider');
  }
  return context;
};

export const DashboardDataProvider = ({ children, mode = 'normal', preloadedData = null }) => {
  // State for all dashboard data
  const [data, setData] = useState({
    alerts: [],
    equipmentStatus: [],
    kpis: null,
    chartData: null,
    wafers: [],
    isLoading: !preloadedData, // Not loading if we have preloaded data
    isPreloaded: !!preloadedData,
    lastFetch: preloadedData ? Date.now() : null
  });

  // Fetch all dashboard data (memoized to prevent unnecessary re-creation)
  const fetchAllData = useCallback(async () => {
    console.log(`Fetching dashboard data (mode: ${mode})...`);
    const startTime = Date.now();

    try {
      // Always fetch alerts and KPIs (no time filter - get all alerts)
      const promises = [
        alertAPI.getAlerts(null, 20),
        kpiAPI.getKPIStatistics()
      ];

      // Only fetch equipment status in normal mode (skip in agentic mode)
      if (mode === 'normal') {
        promises.push(equipmentAPI.getEquipmentStatus());
      }

      const results = await Promise.all(promises);
      const alertsData = results[0];
      const kpisData = results[1];
      const equipmentData = results[2] || null;

      const fetchTime = Date.now() - startTime;
      console.log(`Data fetched in ${fetchTime}ms`);

      // Process equipment data - flatten the matrix structure
      let equipmentList = [];
      if (equipmentData?.matrix) {
        // Flatten all equipment from the matrix into a single array
        Object.values(equipmentData.matrix).forEach(equipmentGroup => {
          if (Array.isArray(equipmentGroup)) {
            equipmentGroup.forEach(eq => {
              equipmentList.push({
                equipment_id: eq.equipment_id,
                status: eq.status,
                metrics: eq.metrics,
                last_update: eq.last_update,
                process_step: eq.process_step || 'UNKNOWN'
              });
            });
          }
        });
      }

      // Update state with all data
      console.log('[DashboardDataProvider] Setting alerts:', alertsData?.alerts?.length, alertsData?.alerts);
      console.log('[DashboardDataProvider] Setting KPIs:', kpisData?.kpi);

      setData(prev => ({
        ...prev,
        alerts: alertsData?.alerts || [],
        equipmentStatus: equipmentList,
        kpis: kpisData?.kpi || null,
        isLoading: false,
        lastFetch: Date.now()
      }));
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setData(prev => ({ ...prev, isLoading: false }));
    }
  }, [mode]); // Only recreate if mode changes

  // Initialize with preloaded data if available
  useEffect(() => {
    if (preloadedData) {
      console.log('✅ Using preloaded dashboard data');
      
      // Transform preloaded data to match expected structure
      const equipmentList = preloadedData.equipment || [];
      
      setData({
        alerts: preloadedData.alerts || [],
        equipmentStatus: equipmentList,
        kpis: preloadedData.kpis || null,
        chartData: preloadedData.chart_data || null,
        wafers: preloadedData.wafers || [],
        isLoading: false,
        isPreloaded: true,
        lastFetch: Date.now()
      });
    }
  }, [preloadedData]);

  // Initial fetch on mount and when mode changes (skip if preloaded data exists)
  useEffect(() => {
    if (!preloadedData) {
      // No preloaded data - fetch immediately and start polling
      fetchAllData();
      const interval = setInterval(fetchAllData, 60000);
      return () => clearInterval(interval);
    } else {
      // Preloaded data exists - delay first refresh by 1 minute
      console.log('✅ DashboardDataProvider: Using preloaded data, delaying first refresh by 1 minute');
      const delayedRefresh = setTimeout(() => {
        console.log('🔄 DashboardDataProvider: Starting periodic refresh after 1 minute delay');
        fetchAllData();
        // Start polling after the delayed first refresh
        const interval = setInterval(fetchAllData, 60000);
        // Note: This interval won't be cleaned up, but that's acceptable as it runs for the lifetime of the dashboard
      }, 60000); // 1 minute delay

      return () => clearTimeout(delayedRefresh);
    }
  }, [mode, preloadedData]);

  // Provide refresh function for manual updates (memoized to prevent re-renders)
  const refresh = useCallback(() => {
    setData(prev => ({ ...prev, isLoading: true }));
    fetchAllData();
  }, [fetchAllData]); // Depends on fetchAllData which only changes when mode changes

  const value = {
    ...data,
    refresh
  };

  return (
    <DashboardDataContext.Provider value={value}>
      {children}
    </DashboardDataContext.Provider>
  );
};