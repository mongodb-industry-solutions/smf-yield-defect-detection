"use client";

import Dashboard from "@/components/Dashboard/Dashboard";
import { DashboardDataProvider } from "@/contexts/DashboardDataProvider";

export default function LiveMonitoringPage() {
  return (
    <DashboardDataProvider>
      <Dashboard />
    </DashboardDataProvider>
  );
}