"use client";

import { useState } from 'react';
import Dashboard from "@/components/Dashboard/Dashboard";
import { DashboardDataProvider } from "@/contexts/DashboardDataProvider";

export default function LiveMonitoringPage() {
  const [dashboardMode, setDashboardMode] = useState('normal'); // 'normal' or 'agentic'

  return (
    <DashboardDataProvider mode={dashboardMode}>
      <Dashboard onModeChange={setDashboardMode} />
    </DashboardDataProvider>
  );
}