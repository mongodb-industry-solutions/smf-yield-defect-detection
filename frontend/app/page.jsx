"use client";

import Dashboard from "@/components/Dashboard/Dashboard";
import { DashboardDataProvider } from "@/contexts/DashboardDataProvider";

export default function HomePage() {
  // Phase 1: Display the new dashboard with optimized data loading
  return (
    <DashboardDataProvider>
      <Dashboard />
    </DashboardDataProvider>
  );
}