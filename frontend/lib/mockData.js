// Mock data for Phase 1 dashboard implementation
export const kpiData = {
  yield: {
    label: 'Current Yield',
    value: 94.2,
    unit: '%',
    trend: 'up',
    trendValue: 2.3,
    target: 95,
    thresholds: { critical: 85, warning: 92, good: 95 },
    mongoMetrics: { queryTime: 12, docsScanned: 5764 }
  },
  alerts: {
    label: 'Active Alerts',
    value: 3,
    unit: '',
    trend: 'down',
    trendValue: -2,
    severity: 'warning',
    thresholds: { critical: 10, warning: 5, good: 2 },
    mongoMetrics: { queryTime: 8, docsScanned: 19 }
  },
  mttr: {
    label: 'Avg Resolution Time',
    value: 12,
    unit: 'min',
    trend: 'down',
    trendValue: -85,
    trendLabel: '% improvement',
    thresholds: { critical: 60, warning: 30, good: 15 },
    mongoMetrics: { queryTime: 23, docsScanned: 72 }
  },
  savings: {
    label: 'Cost Savings',
    value: 2.4,
    unit: 'M',
    prefix: '$',
    trend: 'up',
    trendValue: 18,
    period: 'This Month',
    thresholds: { critical: 0, warning: 1, good: 2 },
    mongoMetrics: { queryTime: 15, docsScanned: 100 }
  }
};

// Demo alerts for the alert panel
export const demoAlerts = [
  {
    id: 'alert-001',
    timestamp: new Date(Date.now() - 5 * 60000).toISOString(), // 5 mins ago
    type: 'particle_excursion',
    severity: 'critical',
    equipment: 'CMP-01',
    metric: 'particle_count',
    value: 1250,
    threshold: 1000,
    message: 'Particle count exceeded threshold on CMP-01'
  },
  {
    id: 'alert-002',
    timestamp: new Date(Date.now() - 15 * 60000).toISOString(), // 15 mins ago
    type: 'equipment_drift',
    severity: 'warning',
    equipment: 'ETCH-03',
    metric: 'rf_power',
    value: 105,
    threshold: 100,
    message: 'RF Power drift detected on ETCH-03'
  },
  {
    id: 'alert-003',
    timestamp: new Date(Date.now() - 30 * 60000).toISOString(), // 30 mins ago
    type: 'temperature_variation',
    severity: 'warning',
    equipment: 'LITHO-02',
    metric: 'temperature',
    value: 22.5,
    threshold: 20,
    message: 'Temperature variation on LITHO-02'
  }
];

// Equipment status for monitoring view - Full fab fleet
export const equipmentStatus = [
  // CMP Tools (Chemical Mechanical Polishing)
  {
    id: 'CMP-01',
    name: 'CMP-01',
    type: 'CMP',
    status: 'critical',
    utilization: 87,
    currentLot: 'L-2451',
    nextMaintenance: '72h',
    lastMaintenance: '2 days ago',
    sparklineData: [45, 48, 52, 58, 65, 78, 92, 98, 105, 125],
    metrics: {
      particle_count: { value: 1250, status: 'critical', threshold: 1000 },
      pressure: { value: 45, status: 'good', threshold: 50 },
      temperature: { value: 21, status: 'good', threshold: 25 }
    }
  },
  {
    id: 'CMP-02',
    name: 'CMP-02',
    type: 'CMP',
    status: 'warning',
    utilization: 92,
    currentLot: 'L-2452',
    nextMaintenance: '48h',
    sparklineData: [42, 44, 46, 48, 52, 55, 58, 62, 68, 75],
    metrics: {
      particle_count: { value: 950, status: 'warning', threshold: 1000 },
      pressure: { value: 48, status: 'good', threshold: 50 },
      temperature: { value: 22, status: 'good', threshold: 25 }
    }
  },
  {
    id: 'CMP-03',
    name: 'CMP-03',
    type: 'CMP',
    status: 'good',
    utilization: 78,
    currentLot: 'L-2453',
    nextMaintenance: '120h',
    sparklineData: [30, 32, 31, 33, 32, 34, 33, 35, 34, 36],
    metrics: {
      particle_count: { value: 450, status: 'good', threshold: 1000 },
      pressure: { value: 42, status: 'good', threshold: 50 },
      temperature: { value: 20, status: 'good', threshold: 25 }
    }
  },
  
  // ETCH Tools (Plasma Etching)
  {
    id: 'ETCH-01',
    name: 'ETCH-01',
    type: 'ETCH',
    status: 'good',
    utilization: 85,
    currentLot: 'L-2454',
    nextMaintenance: '96h',
    sparklineData: [88, 89, 87, 88, 90, 89, 88, 87, 89, 88],
    metrics: {
      rf_power: { value: 95, status: 'good', threshold: 100 },
      flow_rate: { value: 145, status: 'good', threshold: 200 },
      chamber_pressure: { value: 0.45, status: 'good', threshold: 1.0 }
    }
  },
  {
    id: 'ETCH-02',
    name: 'ETCH-02',
    type: 'ETCH',
    status: 'idle',
    utilization: 0,
    currentLot: '--',
    nextMaintenance: '84h',
    sparklineData: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    metrics: {
      rf_power: { value: 0, status: 'idle', threshold: 100 },
      flow_rate: { value: 0, status: 'idle', threshold: 200 },
      chamber_pressure: { value: 0, status: 'idle', threshold: 1.0 }
    }
  },
  {
    id: 'ETCH-03',
    name: 'ETCH-03',
    type: 'ETCH',
    status: 'warning',
    utilization: 96,
    currentLot: 'L-2455',
    nextMaintenance: '24h',
    sparklineData: [92, 93, 94, 95, 96, 98, 100, 102, 104, 105],
    metrics: {
      rf_power: { value: 105, status: 'warning', threshold: 100 },
      flow_rate: { value: 150, status: 'good', threshold: 200 },
      chamber_pressure: { value: 0.5, status: 'good', threshold: 1.0 }
    }
  },
  
  // LITHO Tools (Lithography)
  {
    id: 'LITHO-01',
    name: 'LITHO-01',
    type: 'LITHO',
    status: 'maintenance',
    utilization: 0,
    currentLot: 'MAINT',
    nextMaintenance: 'In Progress',
    sparklineData: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    metrics: {
      temperature: { value: 20, status: 'maintenance', threshold: 20 },
      alignment: { value: 0, status: 'maintenance', threshold: 0.05 },
      exposure_dose: { value: 0, status: 'maintenance', threshold: 300 }
    }
  },
  {
    id: 'LITHO-02',
    name: 'LITHO-02',
    type: 'LITHO',
    status: 'warning',
    utilization: 98,
    currentLot: 'L-2456',
    nextMaintenance: '36h',
    sparklineData: [19, 19.5, 20, 20.5, 21, 21.5, 22, 22.2, 22.4, 22.5],
    metrics: {
      temperature: { value: 22.5, status: 'warning', threshold: 20 },
      alignment: { value: 0.02, status: 'good', threshold: 0.05 },
      exposure_dose: { value: 250, status: 'good', threshold: 300 }
    }
  },
  {
    id: 'LITHO-03',
    name: 'LITHO-03',
    type: 'LITHO',
    status: 'good',
    utilization: 82,
    currentLot: 'L-2457',
    nextMaintenance: '108h',
    sparklineData: [18, 18.5, 19, 19.2, 19.4, 19.5, 19.6, 19.7, 19.8, 19.9],
    metrics: {
      temperature: { value: 19.9, status: 'good', threshold: 20 },
      alignment: { value: 0.01, status: 'good', threshold: 0.05 },
      exposure_dose: { value: 240, status: 'good', threshold: 300 }
    }
  },
  
  // DEP Tools (Deposition)
  {
    id: 'DEP-01',
    name: 'DEP-01',
    type: 'DEP',
    status: 'good',
    utilization: 91,
    currentLot: 'L-2458',
    nextMaintenance: '60h',
    sparklineData: [380, 385, 390, 395, 400, 398, 396, 394, 392, 390],
    metrics: {
      deposition_rate: { value: 95, status: 'good', threshold: 150 },
      temperature: { value: 390, status: 'good', threshold: 500 },
      gas_flow: { value: 48, status: 'good', threshold: 80 }
    }
  },
  {
    id: 'DEP-02',
    name: 'DEP-02',
    type: 'DEP',
    status: 'good',
    utilization: 88,
    currentLot: 'L-2459',
    nextMaintenance: '132h',
    sparklineData: [400, 402, 404, 406, 408, 410, 412, 414, 416, 418],
    metrics: {
      deposition_rate: { value: 105, status: 'good', threshold: 150 },
      temperature: { value: 418, status: 'good', threshold: 500 },
      gas_flow: { value: 52, status: 'good', threshold: 80 }
    }
  },
  {
    id: 'DEP-03',
    name: 'DEP-03',
    type: 'DEP',
    status: 'good',
    utilization: 79,
    currentLot: 'L-2460',
    nextMaintenance: '156h',
    sparklineData: [410, 408, 406, 404, 402, 400, 398, 396, 394, 392],
    metrics: {
      deposition_rate: { value: 98, status: 'good', threshold: 150 },
      temperature: { value: 392, status: 'good', threshold: 500 },
      gas_flow: { value: 45, status: 'good', threshold: 80 }
    }
  },
  
  // CLEAN Tools (Wafer Cleaning)
  {
    id: 'CLEAN-01',
    name: 'CLEAN-01',
    type: 'CLEAN',
    status: 'good',
    utilization: 94,
    currentLot: 'L-2461',
    nextMaintenance: '48h',
    sparklineData: [12, 12.5, 13, 13.2, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9],
    metrics: {
      flow_rate: { value: 180, status: 'good', threshold: 250 },
      temperature: { value: 65, status: 'good', threshold: 80 },
      chemical_concentration: { value: 13.9, status: 'good', threshold: 15 }
    }
  },
  {
    id: 'CLEAN-02',
    name: 'CLEAN-02',
    type: 'CLEAN',
    status: 'good',
    utilization: 86,
    currentLot: 'L-2462',
    nextMaintenance: '72h',
    sparklineData: [11, 11.2, 11.4, 11.6, 11.8, 12, 12.2, 12.4, 12.6, 12.8],
    metrics: {
      flow_rate: { value: 175, status: 'good', threshold: 250 },
      temperature: { value: 68, status: 'good', threshold: 80 },
      chemical_concentration: { value: 12.8, status: 'good', threshold: 15 }
    }
  },
  {
    id: 'CLEAN-03',
    name: 'CLEAN-03',
    type: 'CLEAN',
    status: 'good',
    utilization: 90,
    currentLot: 'L-2463',
    nextMaintenance: '96h',
    sparklineData: [10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.2],
    metrics: {
      flow_rate: { value: 190, status: 'good', threshold: 250 },
      temperature: { value: 70, status: 'good', threshold: 80 },
      chemical_concentration: { value: 14.2, status: 'warning', threshold: 15 }
    }
  }
];

// Fab-wide metrics for the pulse bar
export const fabMetrics = {
  oee: { value: 87.3, unit: '%', trend: 'up' },
  excursions: { value: 2, severity: 'warning', trend: 'down' },
  toolsOnline: { value: '12/15', trend: 'stable' },
  currentYield: { value: 94.2, unit: '%', trend: 'up' },
  wip: { value: 423, unit: ' wafers', trend: 'up' }
};

// Sample wafer defect data for defect analysis view
export const waferDefects = [
  {
    wafer_id: 'W-2024-001',
    lot_id: 'LOT-2024-100',
    timestamp: new Date(Date.now() - 60 * 60000).toISOString(),
    yield: 89.5,
    defect_count: 125,
    pattern: 'clustered',
    severity: 'high',
    equipment: 'CMP-01'
  },
  {
    wafer_id: 'W-2024-002',
    lot_id: 'LOT-2024-100',
    timestamp: new Date(Date.now() - 120 * 60000).toISOString(),
    yield: 92.3,
    defect_count: 78,
    pattern: 'edge',
    severity: 'medium',
    equipment: 'ETCH-03'
  },
  {
    wafer_id: 'W-2024-003',
    lot_id: 'LOT-2024-101',
    timestamp: new Date(Date.now() - 180 * 60000).toISOString(),
    yield: 95.1,
    defect_count: 42,
    pattern: 'random',
    severity: 'low',
    equipment: 'DEP-05'
  }
];

// Historical yield trend data for charts
export const yieldTrendData = {
  labels: ['6h ago', '5h ago', '4h ago', '3h ago', '2h ago', '1h ago', 'Now'],
  datasets: [
    {
      label: 'Yield %',
      data: [95.2, 94.8, 93.5, 91.2, 92.8, 93.7, 94.2],
      borderColor: 'rgb(0, 104, 74)', // MongoDB green
      backgroundColor: 'rgba(0, 104, 74, 0.1)',
      tension: 0.4
    },
    {
      label: 'Target',
      data: [95, 95, 95, 95, 95, 95, 95],
      borderColor: 'rgb(128, 128, 128)',
      borderDash: [5, 5],
      fill: false
    }
  ]
};

// Demo scenarios for guided walkthrough
export const demoScenarios = [
  {
    id: 'particle_crisis',
    name: 'Particle Contamination Crisis',
    description: 'CMP tool particle spike leads to clustered defects requiring immediate intervention',
    duration: '3 minutes',
    severity: 'critical',
    features: ['Time Series Monitoring', 'Vector Search', 'AI Root Cause Analysis'],
    steps: [
      'Particle count exceeds 1000 threshold',
      'Alert triggers in real-time',
      'Correlated wafer defects identified',
      'Vector search finds similar patterns',
      'AI identifies contaminated slurry batch',
      'Recommended actions provided'
    ]
  },
  {
    id: 'drift_prevention',
    name: 'Equipment Drift Prevention',
    description: 'Predictive maintenance prevents potential yield loss from equipment drift',
    duration: '2 minutes',
    severity: 'warning',
    features: ['Predictive Analytics', 'Trend Detection', 'Preventive Actions'],
    steps: [
      'RF power showing upward trend',
      'AI predicts excursion in 4 hours',
      'Maintenance recommendation generated',
      'Schedule preventive maintenance',
      'Avoid potential $2M loss'
    ]
  },
  {
    id: 'unknown_pattern',
    name: 'Unknown Defect Pattern',
    description: 'New defect pattern identified and resolved using vector similarity search',
    duration: '4 minutes',
    severity: 'medium',
    features: ['Vector Search', 'Pattern Matching', 'Historical Analysis'],
    steps: [
      'Upload new defect image',
      'Vector search initiated',
      'Top 10 similar patterns found',
      'Historical resolutions reviewed',
      'Best solution applied',
      'Effectiveness monitored'
    ]
  }
];