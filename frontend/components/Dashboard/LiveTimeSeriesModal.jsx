"use client";

import React, { useState, useEffect, useRef } from 'react';
import Modal from '@leafygreen-ui/modal';
import { H3, Description } from '@leafygreen-ui/typography';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import IconButton from '@leafygreen-ui/icon-button';
import Button from '@leafygreen-ui/button';
import { demoAPI } from '@/lib/api';
import styles from './LiveTimeSeriesModal.module.css';

const LiveTimeSeriesModal = ({ isOpen, onClose }) => {
  const [currentDoc, setCurrentDoc] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isDemoActive, setIsDemoActive] = useState(null); // null = unknown/checking, true = active, false = stopped
  const [error, setError] = useState(null);
  const [isStartingDemo, setIsStartingDemo] = useState(false);
  const [hasShownAllDocs, setHasShownAllDocs] = useState(true); // Track if we've cycled through current batch
  const wsRef = useRef(null);
  const pausedRef = useRef(false);
  const statusIntervalRef = useRef(null);

  const handleStartDemo = async () => {
    setIsStartingDemo(true);
    try {
      await demoAPI.start({ mode: 'charts', scenario: 'continuous' });
      // Demo will start and isDemoActive will be set by WebSocket data detection
    } catch (err) {
      console.error('Failed to start demo:', err);
      setError('Failed to start demo mode');
    } finally {
      setIsStartingDemo(false);
    }
  };

  useEffect(() => {
    pausedRef.current = isPaused;
  }, [isPaused]);

  // Check demo status via API (same as DemoControlPanel)
  useEffect(() => {
    if (!isOpen) return;

    const checkDemoStatus = async () => {
      try {
        const status = await demoAPI.getStatus();
        setIsDemoActive(status.active);
      } catch (err) {
        console.error('Error checking demo status:', err);
      }
    };

    // Check immediately on open
    checkDemoStatus();

    // Poll every 2 seconds
    statusIntervalRef.current = setInterval(checkDemoStatus, 2000);

    return () => {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
        statusIntervalRef.current = null;
      }
    };
  }, [isOpen]);

  // Cycle through documents once per batch, then wait for new data
  useEffect(() => {
    if (!isOpen || documents.length === 0 || isDemoActive !== true || hasShownAllDocs) return;

    const interval = setInterval(() => {
      if (pausedRef.current) return;

      setCurrentIndex(prev => {
        const nextIndex = prev + 1;
        if (nextIndex >= documents.length) {
          // We've shown all documents in this batch, stop cycling
          setHasShownAllDocs(true);
          return prev;
        }
        setCurrentDoc(documents[nextIndex]);
        return nextIndex;
      });
    }, 330); // 330ms × 6 docs ≈ 2 seconds (matches WebSocket interval)

    return () => clearInterval(interval);
  }, [isOpen, documents, isDemoActive, hasShownAllDocs]);

  useEffect(() => {
    if (!isOpen) return;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = process.env.NEXT_PUBLIC_API_URL?.replace(/^https?:\/\//, '').replace(/\/api\/backend$/, '')
      || window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/ws/sensors`;

    console.log('Connecting to WebSocket:', wsUrl);

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setError(null);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.type === 'sensor_update' && message.data && message.data.length > 0) {
            // Update documents list and reset cycling
            setDocuments(message.data);
            setCurrentDoc(message.data[0]);
            setCurrentIndex(0);
            setHasShownAllDocs(false); // New batch arrived, start cycling through it
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      wsRef.current.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('WebSocket connection error');
        setIsConnected(false);
      };

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
      };
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setError('Failed to connect to live data stream');
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setCurrentDoc(null);
      setDocuments([]);
      setCurrentIndex(0);
      setIsPaused(false);
      setIsDemoActive(null); // Reset to unknown state
      setError(null);
      setIsStartingDemo(false);
      setHasShownAllDocs(true);
    }
  }, [isOpen]);

  const handleClose = (open) => {
    if (!open) {
      onClose();
    }
  };

  // Determine badge status
  const getBadgeStatus = () => {
    if (!isConnected) return { variant: 'red', text: 'Disconnected' };
    if (isPaused) return { variant: 'yellow', text: 'Paused' };
    if (isDemoActive === null) return { variant: 'blue', text: 'Detecting...' };
    if (isDemoActive === false) return { variant: 'yellow', text: 'Demo Stopped' };
    return { variant: 'green', text: 'Live' };
  };

  const badgeStatus = getBadgeStatus();

  return (
    <Modal
      open={isOpen}
      setOpen={handleClose}
      className={styles.modal}
    >
      <div className={styles.container}>
        <div className={styles.header}>
          <H3>Live Time Series Inserts</H3>
          <div className={styles.badges}>
            <Badge variant={badgeStatus.variant}>
              {badgeStatus.text}
            </Badge>
            <Badge variant="blue">{documents.length} docs</Badge>
          </div>
        </div>

        <Description>
          Real-time documents from <code>process_sensor_ts</code>
        </Description>

        <div className={styles.controls}>
          <IconButton
            aria-label={isPaused ? 'Resume' : 'Pause'}
            onClick={() => setIsPaused(!isPaused)}
            disabled={isDemoActive !== true}
          >
            <Icon glyph={isPaused ? 'Play' : 'Pause'} />
          </IconButton>
          {currentDoc && (
            <span className={styles.equipmentLabel}>
              {currentDoc.equipment_id} • {new Date(currentDoc.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>

        {error && (
          <div className={styles.error}>
            <Icon glyph="Warning" />
            <span>{error}</span>
          </div>
        )}

        <div className={styles.codeContainer}>
          {!isConnected && !currentDoc ? (
            <div className={styles.loading}>
              <Icon glyph="Refresh" className={styles.spinner} />
              <span>Connecting to live data stream...</span>
            </div>
          ) : currentDoc ? (
            <pre className={styles.jsonDisplay}>
              {JSON.stringify(currentDoc, null, 2)}
            </pre>
          ) : (
            <div className={styles.empty}>
              <Icon glyph="InfoWithCircle" />
              <span>{isDemoActive === false ? 'Demo mode is not running.' : 'Waiting for data...'}</span>
              {isDemoActive === false && (
                <Button
                  variant="primary"
                  size="small"
                  leftGlyph={<Icon glyph="Play" />}
                  onClick={handleStartDemo}
                  disabled={isStartingDemo}
                  className={styles.startButton}
                >
                  {isStartingDemo ? 'Starting...' : 'Start Demo'}
                </Button>
              )}
            </div>
          )}
        </div>

        <div className={styles.footer}>
          <span>Collection: process_sensor_ts</span>
        </div>
      </div>
    </Modal>
  );
};

export default LiveTimeSeriesModal;
