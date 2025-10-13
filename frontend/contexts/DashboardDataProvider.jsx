import React, { createContext, useContext, useState, useEffect } from 'react';
import { alertAPI, equipmentAPI } from '../lib/api';

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

export const DashboardDataProvider = ({ children, mode = 'normal' }) => {
  // State for alerts only
  const [data, setData] = useState({
    alerts: [],
    equipmentStatus: [],
    isLoading: true,
    lastFetch: null
  });

  // Fetch all dashboard data
  const fetchAllData = async () => {
    console.log(`Fetching dashboard data (mode: ${mode})...`);
    const startTime = Date.now();

    try {
      // Always fetch alerts
      const promises = [alertAPI.getAlerts(null, 20)];

      // Only fetch equipment status in normal mode (skip in agentic mode)
      if (mode === 'normal') {
        promises.push(equipmentAPI.getEquipmentStatus());
      }

      const results = await Promise.all(promises);
      const alertsData = results[0];
      const equipmentData = results[1] || null;

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
                latest_metrics: eq.metrics,
                latest_timestamp: eq.last_update,
                process_step: eq.process_step || 'UNKNOWN'
              });
            });
          }
        });
      }

      // Update state with all data
      setData({
        alerts: alertsData?.alerts || [],
        equipmentStatus: equipmentList,
        isLoading: false,
        lastFetch: Date.now()
      });
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setData(prev => ({ ...prev, isLoading: false }));
    }
  };

  // Initial fetch on mount and when mode changes
  useEffect(() => {
    fetchAllData();

    // Refresh data every 60 seconds (increased from 30s)
    const interval = setInterval(fetchAllData, 60000);

    return () => clearInterval(interval);
  }, [mode]);

  // Provide refresh function for manual updates
  const refresh = () => {
    setData(prev => ({ ...prev, isLoading: true }));
    fetchAllData();
  };

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