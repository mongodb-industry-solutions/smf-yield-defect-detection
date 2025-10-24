// API service for connecting to backend monitoring endpoints

// Use Next.js API proxy route for single-pod Kanopy deployment
// This allows client-side code to call backend via server-side proxy
// which can use loopback (127.0.0.1) communication within the pod
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/backend';

// Helper function for API calls
async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Error fetching ${endpoint}:`, error);
    throw error;
  }
}

// Sensor APIs
export const sensorAPI = {
  // Get real-time sensor data
  getRealtimeSensors: async (equipmentId = null, limit = 50) => {
    const params = new URLSearchParams();
    if (equipmentId) params.append('equipment_id', equipmentId);
    params.append('limit', limit);

    return fetchAPI(`/sensors/realtime?${params}`);
  },

  // Get sensor stream for specific equipment
  getSensorStream: async (equipmentId, windowMinutes = 60, interval = 1) => {
    const params = new URLSearchParams({
      window_minutes: windowMinutes,
      interval: interval
    });

    return fetchAPI(`/sensors/stream/${equipmentId}?${params}`);
  },

  // Inject excursion for demo scenarios
  injectExcursion: async (excursionData) => {
    return fetchAPI('/sensors/write', {
      method: 'POST',
      body: JSON.stringify(excursionData)
    });
  }
};

// Wafer APIs
export const waferAPI = {
  // Get latest wafer inspections
  getLatestWafers: async (limit = 10, pattern = null, minYield = null) => {
    const params = new URLSearchParams({ limit });
    if (pattern) params.append('pattern', pattern);
    if (minYield) params.append('min_yield', minYield);
    
    return fetchAPI(`/wafers/latest?${params}`);
  },
  
  // Get wafer batch history
  getWaferBatches: async (limit = 5, includeStats = true) => {
    const params = new URLSearchParams({
      limit,
      include_stats: includeStats
    });

    return fetchAPI(`/wafers/batches?${params}`);
  },

  // Get yield timeline for charting
  getYieldTimeline: async (limit = 50, includeAlerts = true) => {
    const params = new URLSearchParams({
      limit,
      include_alerts: includeAlerts
    });

    return fetchAPI(`/wafers/yield-timeline?${params}`);
  },

  // Get oldest wafer with full MongoDB document including embeddings
  getOldestWaferRaw: async () => {
    return fetchAPI('/wafers/oldest/raw');
  }
};

// Equipment APIs
export const equipmentAPI = {
  // Get equipment status matrix
  getEquipmentStatus: async () => {
    return fetchAPI('/equipment/status');
  },

  // Get metrics for specific equipment
  getEquipmentMetrics: async (equipmentId, hours = 24) => {
    const params = new URLSearchParams({ hours });
    return fetchAPI(`/equipment/${equipmentId}/metrics?${params}`);
  },

  // Get comprehensive equipment details (lots, wafers, materials, alerts)
  getEquipmentDetails: async (equipmentId, hours = 24) => {
    const params = new URLSearchParams({ hours });
    return fetchAPI(`/equipment/${equipmentId}/details?${params}`);
  }
};

// Alert APIs
export const alertAPI = {
  // Get alerts
  getAlerts: async (severity = null, limit = 100) => {
    const params = new URLSearchParams({ limit });
    if (severity) params.append('severity', severity);

    return fetchAPI(`/alerts?${params}`);
  },

  // Alias for getAlerts (for consistency)
  getAll: async (limit = 100, severity = null) => {
    const params = new URLSearchParams({ limit });
    if (severity) params.append('severity', severity);

    return fetchAPI(`/alerts?${params}`);
  },

  // Get alert by ID
  getById: async (alertId) => {
    return fetchAPI(`/alerts/${alertId}`);
  },

  // Get analyzed alerts (alerts with AI agent analysis)
  getAnalyzedAlerts: async (limit = 50) => {
    const params = new URLSearchParams({ limit });
    return fetchAPI(`/alerts/analyzed?${params}`);
  },

  // Get alert statistics
  getAlertStatistics: async (timeWindowHours = 24) => {
    const params = new URLSearchParams({ time_window_hours: timeWindowHours });
    return fetchAPI(`/alerts/statistics/summary?${params}`);
  },

  // Get alert correlation analysis
  getAlertCorrelation: async (alertId) => {
    return fetchAPI(`/alerts/${alertId}/correlation`);
  },

  // Trigger correlation analysis
  analyzeAlert: async (alertId) => {
    return fetchAPI(`/alerts/${alertId}/analyze`, {
      method: 'POST'
    });
  },

  // Get AI agent execution details for an alert
  getAgentDetails: async (alertId) => {
    return fetchAPI(`/alerts/${alertId}/agent-details`);
  }
};

// WebSocket connections
export const createWebSocketConnection = (endpoint, onMessage, onError) => {
  const wsUrl = API_BASE_URL.replace('http', 'ws');
  const ws = new WebSocket(`${wsUrl}/ws/${endpoint}`);
  
  ws.onopen = () => {
    console.log(`WebSocket connected to ${endpoint}`);
  };
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error('WebSocket message parse error:', error);
    }
  };
  
  ws.onerror = (error) => {
    console.error(`WebSocket error on ${endpoint}:`, error);
    if (onError) onError(error);
  };
  
  ws.onclose = () => {
    console.log(`WebSocket disconnected from ${endpoint}`);
  };
  
  return ws;
};

// Monitoring control
export const monitoringAPI = {
  // Start monitoring
  startMonitoring: async () => {
    return fetchAPI('/monitoring/start', { method: 'POST' });
  },
  
  // Stop monitoring
  stopMonitoring: async () => {
    return fetchAPI('/monitoring/stop', { method: 'POST' });
  },
  
  // Get monitoring status
  getMonitoringStatus: async () => {
    return fetchAPI('/monitoring/status');
  }
};

// KPI APIs
export const kpiAPI = {
  // Get comprehensive KPI statistics
  getKPIStatistics: async () => {
    return fetchAPI('/kpi/statistics');
  }
};

// Search APIs for demo scenarios
export const searchAPI = {
  // Semantic search across knowledge base
  semanticSearch: async (query, limit = 10) => {
    return fetchAPI('/search/semantic', {
      method: 'POST',
      body: JSON.stringify({ query, limit })
    });
  },

  // Vector search for similar defects
  similarDefects: async (waferId, threshold = 0.8) => {
    return fetchAPI('/search/similar-defects', {
      method: 'POST',
      body: JSON.stringify({ wafer_id: waferId, threshold })
    });
  }
};

// Agent/AI APIs
export const agentAPI = {
  // Start AI diagnosis workflow
  startDiagnosis: async (alertData) => {
    return fetchAPI('/agent/start', {
      method: 'POST',
      body: JSON.stringify(alertData)
    });
  },

  // Resume agent session
  resumeSession: async (threadId) => {
    return fetchAPI(`/agent/resume/${threadId}`);
  },

  // Get agent documents
  getDocuments: async (threadId) => {
    return fetchAPI(`/agent/documents/${threadId}`);
  },

  // Get past issues
  getPastIssues: async (limit = 10) => {
    const params = new URLSearchParams({ limit });
    return fetchAPI(`/agent/past_issues?${params}`);
  }
};

// Process context APIs
export const processAPI = {
  // Get process context (batches, recipes, reticles)
  getProcessContext: async (contextType = null) => {
    const params = new URLSearchParams();
    if (contextType) params.append('type', contextType);
    return fetchAPI(`/process-context?${params}`);
  },

  // Get problematic batches
  getProblematicBatches: async () => {
    return fetchAPI('/process-context/problematic');
  }
};

export default {
  sensors: sensorAPI,
  wafers: waferAPI,
  equipment: equipmentAPI,
  alerts: alertAPI,
  monitoring: monitoringAPI,
  kpi: kpiAPI,
  search: searchAPI,
  agent: agentAPI,
  process: processAPI,
  createWebSocket: createWebSocketConnection
};

// Demo Mode APIs
export const demoAPI = {
  // Start demo mode data generation with optional parameters
  start: async (params = {}) => {
    return fetchAPI('/demo/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params)
    });
  },

  // Stop demo mode and cleanup
  stop: async () => {
    return fetchAPI('/demo/stop', { method: 'POST' });
  },

  // Reset demo to healthy state
  reset: async () => {
    return fetchAPI('/demo/reset', { method: 'POST' });
  },

  // Get current demo status
  getStatus: async () => {
    return fetchAPI('/demo/status');
  },

  // Inject manual excursion
  injectExcursion: async (data) => {
    return fetchAPI('/demo/inject-excursion', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  // Check seed status
  getSeedStatus: async () => {
    return fetchAPI('/api/demo/seed-status');
  },

  // Initialize seed data (one-time)
  initializeSeed: async () => {
    return fetchAPI('/api/demo/initialize-seed', { method: 'POST' });
  },

  // Get preloaded dashboard data
  getPreloadedData: async () => {
    return fetchAPI('/api/dashboard/preload');
  },

  // Bulk insert lot scenario (instant, no 3-minute wait)
  bulkInsertLot: async (scenario) => {
    return fetchAPI('/demo/bulk-insert-lot', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ scenario })
    });
  }
};

// AI Agent Control APIs
export const aiAgentAPI = {
  // Get AI agent system status
  getStatus: async () => {
    return fetchAPI('/ai-agents/status');
  },

  // Toggle AI agent system
  toggle: async (enabled) => {
    return fetchAPI(`/ai-agents/toggle?enabled=${enabled}`, {
      method: 'POST'
    });
  },

  // Analyze existing alert (e.g., from lot processing)
  analyzeAlert: async (alert_id) => {
    return fetchAPI(`/ai-agents/analyze-alert/${alert_id}`, {
      method: 'POST'
    });
  },

  // Run LangGraph workflow for scenario analysis
  // Can optionally provide an existing alert_id to analyze
  runLangGraphWorkflow: async (scenario_id, alert_id = null) => {
    const body = alert_id ? { alert_id } : {};
    return fetchAPI(`/ai-agents/analyze-workflow/${scenario_id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });
  }
};

// Collections Data APIs
export const collectionsAPI = {
  // Get latest documents from a collection
  getLatest: async (collectionName, limit = 3) => {
    return fetchAPI(`/collections/${collectionName}/latest?limit=${limit}`);
  }
};