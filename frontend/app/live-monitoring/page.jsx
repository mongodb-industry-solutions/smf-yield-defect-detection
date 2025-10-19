"use client";

import { useState } from 'react';
import Dashboard from "@/components/Dashboard/Dashboard";
import SeedLoadingScreen from "@/components/Dashboard/SeedLoadingScreen";
import { DashboardDataProvider } from "@/contexts/DashboardDataProvider";
import { useSeedInitialization } from "@/lib/hooks/useSeedInitialization";
import Button from '@leafygreen-ui/button';
import Icon from '@leafygreen-ui/icon';

export default function LiveMonitoringPage() {
  const [dashboardMode, setDashboardMode] = useState('normal'); // 'normal' or 'agentic'
  
  // Initialize seed and preload dashboard data
  const { 
    isInitializing, 
    currentPhase, 
    progress, 
    preloadedData, 
    error, 
    retry 
  } = useSeedInitialization();

  // Show loading screen during initialization
  if (isInitializing) {
    return <SeedLoadingScreen phase={currentPhase} progress={progress} />;
  }

  // Show error screen with retry option
  if (error) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #001e2b 0%, #00111a 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px'
      }}>
        <div style={{
          maxWidth: '500px',
          textAlign: 'center',
          padding: '48px',
          background: 'rgba(0, 30, 43, 0.8)',
          borderRadius: '16px',
          border: '1px solid rgba(255, 61, 61, 0.3)'
        }}>
          <Icon 
            glyph="Warning" 
            size="xlarge" 
            style={{ color: '#FF3D3D', marginBottom: '24px' }} 
          />
          <h2 style={{ 
            color: '#ffffff', 
            marginBottom: '16px',
            fontSize: '24px',
            fontWeight: 600
          }}>
            Initialization Failed
          </h2>
          <p style={{ 
            color: 'rgba(255, 255, 255, 0.7)', 
            marginBottom: '32px',
            lineHeight: '1.6'
          }}>
            {error}
          </p>
          <Button 
            variant="primary" 
            onClick={retry}
            leftGlyph={<Icon glyph="Refresh" />}
          >
            Retry Initialization
          </Button>
        </div>
      </div>
    );
  }

  // Render dashboard with preloaded data
  return (
    <DashboardDataProvider mode={dashboardMode} preloadedData={preloadedData}>
      <Dashboard onModeChange={setDashboardMode} />
    </DashboardDataProvider>
  );
}