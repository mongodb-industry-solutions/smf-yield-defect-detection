"use client";

import { createContext, useContext, useEffect, useState, useRef } from 'react';

const WebSocketContext = createContext();

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [sensorData, setSensorData] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [waferUpdates, setWaferUpdates] = useState([]);
  
  // WebSocket references
  const sensorWs = useRef(null);
  const alertWs = useRef(null);
  const waferWs = useRef(null);
  
  // Connection status for each WebSocket
  const [connections, setConnections] = useState({
    sensors: false,
    alerts: false,
    wafers: false
  });

  useEffect(() => {
    // WebSocket URL construction for single-pod deployment
    // In browser: use same host as frontend (window.location) + /ws path
    // Backend WebSocket server handles the /ws/* endpoints
    let wsUrl;

    if (typeof window !== 'undefined') {
      // Browser environment: construct WebSocket URL from current location
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      wsUrl = `${protocol}//${host}`;
    } else {
      // Fallback for server-side rendering (shouldn't be used)
      wsUrl = 'ws://localhost:8000';
    }

    console.log(`[WebSocket] Connecting to: ${wsUrl}`);
    let mounted = true; // Track if component is still mounted

    // Connect to sensor WebSocket
    const connectSensorWs = () => {
      if (!mounted) return; // Don't connect if unmounted

      try {
        sensorWs.current = new WebSocket(`${wsUrl}/ws/sensors`);
        
        sensorWs.current.onopen = () => {
          console.log('Sensor WebSocket connected');
          setConnections(prev => ({ ...prev, sensors: true }));
        };
        
        sensorWs.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('Sensor WebSocket received:', data.type);

            // Handle sensor update messages
            if (data.type === 'sensor_update') {
              setSensorData(prev => {
                const updated = [...prev, data];
                // Keep only last 100 data points
                return updated.slice(-100);
              });
            } else if (data.type === 'connection' || data.type === 'subscription_updated' || data.type === 'pong') {
              // Connection management messages - no action needed
              console.log('Sensor WebSocket status:', data.type, data);
            } else {
              // Log any other message types for debugging
              console.log('Sensor WebSocket unhandled message type:', data.type, data);
            }
          } catch (error) {
            console.error('Error parsing sensor data:', error);
          }
        };
        
        sensorWs.current.onerror = (error) => {
          console.error('Sensor WebSocket error:', error);
        };
        
        sensorWs.current.onclose = () => {
          console.log('Sensor WebSocket disconnected');
          setConnections(prev => ({ ...prev, sensors: false }));
          // Reconnect after 5 seconds if still mounted
          if (mounted) {
            setTimeout(connectSensorWs, 5000);
          }
        };
      } catch (error) {
        console.error('Failed to connect sensor WebSocket:', error);
        if (mounted) {
          setTimeout(connectSensorWs, 5000);
        }
      }
    };
    
    // Connect to alerts WebSocket
    const connectAlertWs = () => {
      if (!mounted) return; // Don't connect if unmounted

      try {
        alertWs.current = new WebSocket(`${wsUrl}/ws/alerts`);
        
        alertWs.current.onopen = () => {
          console.log('Alert WebSocket connected');
          setConnections(prev => ({ ...prev, alerts: true }));
          // No need to send start message - backend automatically starts streaming
        };
        
        alertWs.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('Alert WebSocket received:', data.type);

            // Handle different alert message types from backend
            if (data.type === 'new_alert' || data.type === 'wafer_alert') {
              setAlerts(prev => [data, ...prev].slice(0, 20));
            } else if (data.type === 'correlation_complete') {
              // Update the alert with correlation data
              setAlerts(prev => prev.map(alert =>
                alert.alert_id === data.alert_id
                  ? { ...alert, correlations: data.correlations }
                  : alert
              ));
            } else if (data.type === 'rca_complete') {
              // Update the alert with RCA data
              setAlerts(prev => prev.map(alert =>
                alert.alert_id === data.alert_id
                  ? { ...alert, rca: data.rca }
                  : alert
              ));
            } else if (data.type === 'connection' || data.type === 'subscription_updated' || data.type === 'pong') {
              // Connection management messages - no action needed
              console.log('Alert WebSocket status:', data.type, data);
            } else {
              // Log any other message types for debugging
              console.log('Alert WebSocket unhandled message type:', data.type, data);
            }
          } catch (error) {
            // Handle text messages
            console.log('Alert WebSocket text message:', event.data);
          }
        };
        
        alertWs.current.onerror = (error) => {
          console.error('Alert WebSocket error:', error);
        };
        
        alertWs.current.onclose = () => {
          console.log('Alert WebSocket disconnected');
          setConnections(prev => ({ ...prev, alerts: false }));
          // Reconnect after 5 seconds if still mounted
          if (mounted) {
            setTimeout(connectAlertWs, 5000);
          }
        };
      } catch (error) {
        console.error('Failed to connect alert WebSocket:', error);
        if (mounted) {
          setTimeout(connectAlertWs, 5000);
        }
      }
    };
    
    // Connect to wafer WebSocket
    const connectWaferWs = () => {
      if (!mounted) return; // Don't connect if unmounted

      try {
        waferWs.current = new WebSocket(`${wsUrl}/ws/wafers`);
        
        waferWs.current.onopen = () => {
          console.log('Wafer WebSocket connected');
          setConnections(prev => ({ ...prev, wafers: true }));
        };
        
        waferWs.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('Wafer WebSocket received:', data.type);

            // Handle different wafer message types from backend
            if (data.type === 'new_wafer_defect' || data.type === 'wafer_update') {
              setWaferUpdates(prev => {
                const updated = [...prev, data];
                // Keep only last 10 wafer updates
                return updated.slice(-10);
              });
            } else if (data.type === 'connection' || data.type === 'subscription_updated' || data.type === 'pong') {
              // Connection management messages - no action needed
              console.log('Wafer WebSocket status:', data.type, data);
            } else {
              // Log any other message types for debugging
              console.log('Wafer WebSocket unhandled message type:', data.type, data);
            }
          } catch (error) {
            console.error('Error parsing wafer data:', error);
          }
        };
        
        waferWs.current.onerror = (error) => {
          console.error('Wafer WebSocket error:', error);
        };
        
        waferWs.current.onclose = () => {
          console.log('Wafer WebSocket disconnected');
          setConnections(prev => ({ ...prev, wafers: false }));
          // Reconnect after 5 seconds if still mounted
          if (mounted) {
            setTimeout(connectWaferWs, 5000);
          }
        };
      } catch (error) {
        console.error('Failed to connect wafer WebSocket:', error);
        if (mounted) {
          setTimeout(connectWaferWs, 5000);
        }
      }
    };
    
    // Initialize all WebSocket connections with a small delay for React StrictMode
    const connectionTimeout = setTimeout(() => {
      if (mounted) {
        connectSensorWs();
        connectAlertWs();
        connectWaferWs();
      }
    }, 100);

    // Update overall connection status
    const checkConnection = setInterval(() => {
      if (mounted) {
        const anyConnected = connections.sensors || connections.alerts || connections.wafers;
        setIsConnected(anyConnected);
      }
    }, 1000);

    // Cleanup on unmount
    return () => {
      mounted = false; // Mark as unmounted
      clearTimeout(connectionTimeout);
      clearInterval(checkConnection);

      // Close WebSocket connections gracefully
      if (sensorWs.current && sensorWs.current.readyState === WebSocket.OPEN) {
        sensorWs.current.close(1000, 'Component unmounting');
      }
      if (alertWs.current && alertWs.current.readyState === WebSocket.OPEN) {
        alertWs.current.close(1000, 'Component unmounting');
      }
      if (waferWs.current && waferWs.current.readyState === WebSocket.OPEN) {
        waferWs.current.close(1000, 'Component unmounting');
      }
    };
  }, []);
  
  // Update overall connection status when individual connections change
  useEffect(() => {
    const anyConnected = connections.sensors || connections.alerts || connections.wafers;
    setIsConnected(anyConnected);
  }, [connections]);

  const value = {
    isConnected,
    connections,
    sensorData,
    alerts,
    waferUpdates,
    // Expose WebSocket instances if components need direct access
    sensorWs: sensorWs.current,
    alertWs: alertWs.current,
    waferWs: waferWs.current,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};