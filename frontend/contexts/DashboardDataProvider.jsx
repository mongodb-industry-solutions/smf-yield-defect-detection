import React, { createContext, useContext, useState, useEffect } from 'react';
import { 
  alertAPI, 
  kpiAPI, 
  equipmentAPI, 
  sensorAPI, 
  waferAPI 
} from '../lib/api';

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

export const DashboardDataProvider = ({ children }) => {
  // State for all dashboard data
  const [data, setData] = useState({
    kpi: null,
    alerts: [],
    equipment: null,
    sensors: [],
    wafers: [],
    isLoading: true,
    lastFetch: null
  });

  // Fetch all data in parallel
  const fetchAllData = async () => {
    console.log('Fetching all dashboard data in parallel...');
    const startTime = Date.now();
    
    try {
      // Start all requests in parallel
      const [kpiData, alertsData, equipmentData, sensorsData, wafersData] = await Promise.all([
        kpiAPI.getKPIStatistics().catch(err => {
          console.error('KPI fetch failed:', err);
          return null;
        }),
        alertAPI.getAlerts(null, 10).catch(err => {
          console.error('Alerts fetch failed:', err);
          return { alerts: [] };
        }),
        equipmentAPI.getEquipmentStatus().catch(err => {
          console.error('Equipment fetch failed:', err);
          return null;
        }),
        sensorAPI.getSensorStream('CMP_TOOL_01', 5, 1).catch(err => {
          console.error('Sensors fetch failed:', err);
          return { data: [] };
        }),
        waferAPI.getLatestWafers(5).catch(err => {
          console.error('Wafers fetch failed:', err);
          return { wafers: [] };
        })
      ]);

      const fetchTime = Date.now() - startTime;
      console.log(`All data fetched in ${fetchTime}ms`);

      // Update state with all data at once
      setData({
        kpi: kpiData,
        alerts: alertsData?.alerts || [],
        equipment: equipmentData,
        sensors: sensorsData?.data || [],
        wafers: wafersData?.wafers || [],
        isLoading: false,
        lastFetch: Date.now()
      });
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setData(prev => ({ ...prev, isLoading: false }));
    }
  };

  // Initial fetch on mount
  useEffect(() => {
    fetchAllData();
    
    // Refresh data every 30 seconds
    const interval = setInterval(fetchAllData, 30000);
    
    return () => clearInterval(interval);
  }, []);

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