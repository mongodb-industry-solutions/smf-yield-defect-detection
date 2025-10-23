"use client";

import { createContext, useContext, useEffect, useState } from 'react';
import io from 'socket.io-client';

const WebSocketContext = createContext();

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [sensorData, setSensorData] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [equipment, setEquipment] = useState([]);

  useEffect(() => {
    // Initialize WebSocket connection
    const socketUrl = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8000';
    const newSocket = io(socketUrl, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    newSocket.on('connect', () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    });

    newSocket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    });

    // Real-time sensor updates
    newSocket.on('sensor_update', (data) => {
      setSensorData(prev => {
        const updated = [...prev, data];
        // Keep only last 100 data points
        return updated.slice(-100);
      });
    });

    // Real-time alerts
    newSocket.on('alert', (alert) => {
      setAlerts(prev => [alert, ...prev].slice(0, 10));
    });

    // Equipment status updates
    newSocket.on('equipment_status', (status) => {
      setEquipment(prev => {
        const index = prev.findIndex(e => e.id === status.id);
        if (index >= 0) {
          const updated = [...prev];
          updated[index] = status;
          return updated;
        }
        return [...prev, status];
      });
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, []);

  // Simulate real-time data for demo purposes
  useEffect(() => {
    if (!isConnected) return;

    const interval = setInterval(() => {
      // Simulate sensor data
      const mockSensorData = {
        timestamp: new Date().toISOString(),
        equipment: 'CMP-01',
        metrics: {
          particle_count: 950 + Math.random() * 400,
          pressure: 45 + Math.random() * 10,
          temperature: 20 + Math.random() * 5,
          rf_power: 95 + Math.random() * 20,
        }
      };
      setSensorData(prev => [...prev, mockSensorData].slice(-100));

      // Simulate occasional alerts
      if (Math.random() > 0.95) {
        const mockAlert = {
          id: `alert-${Date.now()}`,
          timestamp: new Date().toISOString(),
          type: Math.random() > 0.5 ? 'particle_excursion' : 'equipment_drift',
          severity: Math.random() > 0.7 ? 'critical' : 'warning',
          equipment: `CMP-0${Math.floor(Math.random() * 3) + 1}`,
          message: 'Anomaly detected in process parameters'
        };
        setAlerts(prev => [mockAlert, ...prev].slice(0, 10));
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isConnected]);

  const value = {
    socket,
    isConnected,
    sensorData,
    alerts,
    equipment,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};