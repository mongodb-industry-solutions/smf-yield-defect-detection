/**
 * EnhancedWebSocketManager - Advanced WebSocket client with MongoDB operation tracking
 * Features:
 * - Auto-reconnection with exponential backoff
 * - MongoDB operation tracking
 * - Custom event emission for different message types
 * - Connection state management
 * - Message queuing during disconnection
 */

class EnhancedWebSocketManager {
  constructor(url, options = {}) {
    this.url = url;
    this.options = {
      maxReconnectAttempts: 5,
      reconnectInterval: 1000,
      heartbeatInterval: 30000,
      messageQueueSize: 100,
      ...options
    };

    // Connection state
    this.ws = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;

    // Message handling
    this.messageQueue = [];
    this.eventHandlers = new Map();
    this.mongoOperations = new Map();

    // MongoDB operation tracking
    this.operationStats = {
      changeStreams: { count: 0, active: false, lastActivity: null },
      timeSeries: { count: 0, active: false, lastActivity: null },
      vectorSearch: { count: 0, active: false, lastActivity: null },
      aggregation: { count: 0, active: false, lastActivity: null },
      transactions: { count: 0, active: false, lastActivity: null }
    };

    // Bind methods
    this.connect = this.connect.bind(this);
    this.disconnect = this.disconnect.bind(this);
    this.send = this.send.bind(this);
    this.on = this.on.bind(this);
    this.off = this.off.bind(this);
  }

  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  setupEventHandlers() {
    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.isConnected = true;
      this.reconnectAttempts = 0;

      // Clear reconnect timer
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }

      // Start heartbeat
      this.startHeartbeat();

      // Flush message queue
      this.flushMessageQueue();

      // Emit connected event
      this.emit('connected', { timestamp: new Date().toISOString() });
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
        // Handle non-JSON messages
        this.emit('raw-message', event.data);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket disconnected', event.code, event.reason);
      this.isConnected = false;

      // Stop heartbeat
      this.stopHeartbeat();

      // Emit disconnected event
      this.emit('disconnected', {
        code: event.code,
        reason: event.reason,
        timestamp: new Date().toISOString()
      });

      // Schedule reconnection if not manually closed
      if (event.code !== 1000) {
        this.scheduleReconnect();
      }
    };
  }

  handleMessage(message) {
    const { type, data, metadata = {} } = message;

    // Track MongoDB operations
    if (metadata.mongoOperation) {
      this.trackMongoOperation(metadata.mongoOperation, metadata);
    }

    // Route message based on type
    switch (type) {
      case 'sensor_update':
        this.handleSensorUpdate(data, metadata);
        break;

      case 'alert':
        this.handleAlert(data, metadata);
        break;

      case 'wafer_update':
        this.handleWaferUpdate(data, metadata);
        break;

      case 'equipment_status':
        this.handleEquipmentStatus(data, metadata);
        break;

      case 'mongo_operation':
        this.handleMongoOperation(data, metadata);
        break;

      default:
        // Emit generic message event
        this.emit('message', { type, data, metadata });
    }

    // Always emit the specific message type
    this.emit(type, { data, metadata });
  }

  trackMongoOperation(operation, metadata) {
    const opType = operation.type || 'unknown';

    if (this.operationStats[opType]) {
      this.operationStats[opType].count++;
      this.operationStats[opType].active = true;
      this.operationStats[opType].lastActivity = new Date().toISOString();

      // Deactivate after a timeout
      setTimeout(() => {
        this.operationStats[opType].active = false;
      }, 2000);
    }

    // Track individual operations
    const opId = `${opType}-${Date.now()}`;
    this.mongoOperations.set(opId, {
      type: opType,
      timestamp: new Date().toISOString(),
      duration: metadata.duration || null,
      collection: metadata.collection || null,
      pipeline: metadata.pipeline || null,
      documentsAffected: metadata.documentsAffected || null
    });

    // Emit MongoDB operation event
    this.emit('mongo-stats-update', this.operationStats);

    // Clean up old operations (keep last 100)
    if (this.mongoOperations.size > 100) {
      const oldestKey = this.mongoOperations.keys().next().value;
      this.mongoOperations.delete(oldestKey);
    }
  }

  handleSensorUpdate(data, metadata) {
    // Track if this is from Change Streams
    if (metadata.source === 'change_stream') {
      this.trackMongoOperation({ type: 'changeStreams' }, metadata);
    }

    this.emit('sensor-data', {
      ...data,
      timestamp: metadata.timestamp || new Date().toISOString()
    });
  }

  handleAlert(data, metadata) {
    // Track aggregation pipeline for correlation
    if (metadata.correlationPipeline) {
      this.trackMongoOperation({ type: 'aggregation' }, {
        ...metadata,
        pipeline: metadata.correlationPipeline
      });
    }

    this.emit('alert-notification', {
      ...data,
      severity: metadata.severity || 'medium',
      timestamp: metadata.timestamp || new Date().toISOString()
    });
  }

  handleWaferUpdate(data, metadata) {
    // Track vector search if similarity analysis was performed
    if (metadata.similaritySearch) {
      this.trackMongoOperation({ type: 'vectorSearch' }, {
        ...metadata,
        embeddings: metadata.embeddings
      });
    }

    this.emit('wafer-processed', {
      ...data,
      defectPattern: metadata.pattern || null,
      timestamp: metadata.timestamp || new Date().toISOString()
    });
  }

  handleEquipmentStatus(data, metadata) {
    // Track time-series aggregation
    if (metadata.timeSeriesQuery) {
      this.trackMongoOperation({ type: 'timeSeries' }, metadata);
    }

    this.emit('equipment-update', {
      ...data,
      timestamp: metadata.timestamp || new Date().toISOString()
    });
  }

  handleMongoOperation(data, metadata) {
    // Direct MongoDB operation update
    this.trackMongoOperation(data, metadata);

    this.emit('mongo-operation', {
      operation: data,
      stats: this.operationStats,
      timestamp: new Date().toISOString()
    });
  }

  send(type, data, metadata = {}) {
    const message = JSON.stringify({
      type,
      data,
      metadata: {
        ...metadata,
        clientTimestamp: new Date().toISOString()
      }
    });

    if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(message);
        return true;
      } catch (error) {
        console.error('Failed to send message:', error);
        this.queueMessage(message);
        return false;
      }
    } else {
      this.queueMessage(message);
      return false;
    }
  }

  queueMessage(message) {
    if (this.messageQueue.length >= this.options.messageQueueSize) {
      this.messageQueue.shift(); // Remove oldest message
    }
    this.messageQueue.push(message);
  }

  flushMessageQueue() {
    while (this.messageQueue.length > 0 && this.isConnected) {
      const message = this.messageQueue.shift();
      try {
        this.ws.send(message);
      } catch (error) {
        console.error('Failed to flush message:', error);
        this.messageQueue.unshift(message); // Put it back
        break;
      }
    }
  }

  startHeartbeat() {
    this.stopHeartbeat();

    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
        this.send('ping', { timestamp: Date.now() });
      }
    }, this.options.heartbeatInterval);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.emit('max-reconnect-exceeded', {
        attempts: this.reconnectAttempts,
        timestamp: new Date().toISOString()
      });
      return;
    }

    const delay = Math.min(
      this.options.reconnectInterval * Math.pow(2, this.reconnectAttempts),
      30000 // Max 30 seconds
    );

    console.log(`Scheduling reconnection in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  disconnect() {
    this.stopHeartbeat();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
      this.ws = null;
    }

    this.isConnected = false;
    this.messageQueue = [];
  }

  on(event, handler) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    this.eventHandlers.get(event).add(handler);
  }

  off(event, handler) {
    if (this.eventHandlers.has(event)) {
      this.eventHandlers.get(event).delete(handler);
    }
  }

  emit(event, data) {
    if (this.eventHandlers.has(event)) {
      this.eventHandlers.get(event).forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in event handler for ${event}:`, error);
        }
      });
    }
  }

  // Utility methods
  getConnectionState() {
    return {
      isConnected: this.isConnected,
      readyState: this.ws ? this.ws.readyState : null,
      reconnectAttempts: this.reconnectAttempts,
      queuedMessages: this.messageQueue.length
    };
  }

  getMongoStats() {
    return { ...this.operationStats };
  }

  getRecentOperations(limit = 10) {
    const operations = Array.from(this.mongoOperations.values());
    return operations.slice(-limit);
  }

  clearStats() {
    Object.keys(this.operationStats).forEach(key => {
      this.operationStats[key] = { count: 0, active: false, lastActivity: null };
    });
    this.mongoOperations.clear();
    this.emit('mongo-stats-update', this.operationStats);
  }
}

// Export for use in React components
export default EnhancedWebSocketManager;