"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Button from '@leafygreen-ui/button';
import { SAMPLE_WAFER_MONGO_DATA } from '@/lib/sampleWaferData';
import { waferAPI } from '@/lib/api';
import styles from './LiveWaferImageMapCompact.module.css';

const LiveWaferImageMapCompact = () => {
  const [waferData, setWaferData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedWafer, setSelectedWafer] = useState(0);
  const [showMongoPanel, setShowMongoPanel] = useState(false);

  // Fetch wafer data with thumbnails
  const fetchWaferData = async () => {
    const startTime = performance.now();
    console.log('[LiveWaferImageMapCompact] 🚀 Starting wafer fetch...');

    try {
      const fetchStart = performance.now();
      const data = await waferAPI.getLatestWafers(3);
      const fetchEnd = performance.now();
      console.log(`[LiveWaferImageMapCompact] ⏱️  Fetch request completed in ${(fetchEnd - fetchStart).toFixed(0)}ms`);
      console.log(`[LiveWaferImageMapCompact] 📊 Received ${data.wafers?.length || 0} wafers`);

      if (data.wafers && data.wafers.length > 0) {
        // Log image sizes
        data.wafers.forEach((wafer, idx) => {
          const imageSize = wafer?.ink_map?.full_image_base64?.length || 0;
          console.log(`[LiveWaferImageMapCompact] 🖼️  Wafer ${idx + 1}: ${wafer.wafer_id}, image size: ${(imageSize / 1024).toFixed(1)}KB`);
        });

        const stateStart = performance.now();
        setWaferData(data.wafers);
        const stateEnd = performance.now();
        console.log(`[LiveWaferImageMapCompact] 💾 State update completed in ${(stateEnd - stateStart).toFixed(0)}ms`);
      } else {
        console.log('[LiveWaferImageMapCompact] ⚠️  No wafers received');
      }

      setIsLoading(false);
      const totalTime = performance.now() - startTime;
      console.log(`[LiveWaferImageMapCompact] ✅ Total fetch cycle completed in ${totalTime.toFixed(0)}ms`);
    } catch (error) {
      const totalTime = performance.now() - startTime;
      console.error(`[LiveWaferImageMapCompact] ❌ Error after ${totalTime.toFixed(0)}ms:`, error);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWaferData();
    const interval = setInterval(fetchWaferData, 30000);
    return () => clearInterval(interval);
  }, []);

  // Toggle MongoDB panel visibility
  const toggleMongoPanel = () => {
    setShowMongoPanel(!showMongoPanel);
  };

  // Communicate panel state to FabPulseBar via custom event
  useEffect(() => {
    const event = new CustomEvent('mongoPanelStateChange', {
      detail: { isOpen: showMongoPanel }
    });
    window.dispatchEvent(event);
  }, [showMongoPanel]);

  const currentWafer = waferData?.[selectedWafer];

  const getWaferImageSrc = (wafer) => {
    if (wafer?.ink_map?.full_image_base64) {
      return `data:image/png;base64,${wafer.ink_map.full_image_base64}`;
    }
    return null;
  };

  if (isLoading) {
    return (
      <div className={styles.container}>
        <Card className={styles.card}>
          <div className={styles.header}>
            <div className={styles.headerLeft}>
              <h3>Live Wafer Defect Map</h3>
              <p className={styles.subtitle}>
                Real-time wafer inspection • Defect pattern analysis
              </p>
            </div>
            <div className={styles.headerRight}>
              <span className={styles.liveIndicator}>
                <span className={styles.liveDot}></span>
                LIVE
              </span>
            </div>
          </div>
          <div className={styles.chartContainer}>
            <div className={styles.loadingOverlay}>
              <div className={styles.spinner}></div>
              <p>Loading wafer data...</p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3>Live Wafer Defect Map</h3>
            <p className={styles.subtitle}>
              Real-time wafer inspection • Defect pattern analysis
            </p>
          </div>
          <div className={styles.headerRight}>
            <Button
              variant="primary"
              size="small"
              onClick={toggleMongoPanel}
              style={{ marginRight: '12px' }}
            >
              {showMongoPanel ? 'Hide' : 'View'} MongoDB Structure
            </Button>
            <span className={styles.liveIndicator}>
              <span className={styles.liveDot}></span>
              LIVE
            </span>
          </div>
        </div>

        <div className={styles.chartContainer}>
          {/* Main content area */}
          <div className={styles.contentWrapper}>
            {/* Left: Wafer Image */}
            <div className={styles.imageSection}>
              <div className={styles.imageContainer}>
                {currentWafer && getWaferImageSrc(currentWafer) ? (
                  <img
                    src={getWaferImageSrc(currentWafer)}
                    alt={`Wafer ${currentWafer.wafer_id}`}
                    className={styles.waferImage}
                  />
                ) : (
                  <div className={styles.noImage}>Loading wafer image...</div>
                )}
              </div>

              {/* Wafer info below image */}
              <div className={styles.waferInfo}>
                <div className={styles.currentWaferId}>
                  {currentWafer ? currentWafer.wafer_id : '--'}
                </div>
                <div className={styles.currentLotId}>
                  {currentWafer ? currentWafer.lot_id : '--'}
                </div>
              </div>

              {/* Wafer selector tabs */}
              <div className={styles.waferSelector}>
                {waferData?.map((wafer, index) => (
                  <button
                    key={wafer.wafer_id}
                    className={`${styles.waferTab} ${index === selectedWafer ? styles.active : ''}`}
                    onClick={() => setSelectedWafer(index)}
                  >
                    {wafer.wafer_id.split('_').pop()}
                  </button>
                ))}
              </div>
            </div>

        {/* Right: Compact Stats */}
        <div className={styles.statsSection}>
          {currentWafer && (
            <>
              {/* Yield with inline value */}
              <div className={styles.yieldRow}>
                <span className={styles.yieldLabel}>Yield:</span>
                <span
                  className={styles.yieldValue}
                  style={{
                    color: currentWafer.defect_summary?.yield_percentage >= 92 ? '#00684a' :
                           currentWafer.defect_summary?.yield_percentage >= 85 ? '#FDB813' : '#DC382D'
                  }}
                >
                  {currentWafer.defect_summary?.yield_percentage?.toFixed(1) || '--'}%
                </span>
              </div>

              {/* Compact info grid */}
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <span className={styles.label}>Pattern:</span>
                  <Badge variant={
                    currentWafer.defect_summary?.defect_pattern === 'clustered' ? 'red' :
                    currentWafer.defect_summary?.defect_pattern === 'edge' ? 'yellow' : 'lightgray'
                  } size="small">
                    {currentWafer.defect_summary?.defect_pattern || 'Unknown'}
                  </Badge>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Severity:</span>
                  <Badge variant={
                    currentWafer.defect_summary?.severity === 'high' ? 'red' :
                    currentWafer.defect_summary?.severity === 'medium' ? 'yellow' : 'blue'
                  } size="small">
                    {currentWafer.defect_summary?.severity || 'Low'}
                  </Badge>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Failed:</span>
                  <span className={styles.value}>
                    {currentWafer.defect_summary?.failed_dies || 0}/{currentWafer.defect_summary?.total_dies || 625}
                  </span>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Tool:</span>
                  <span className={styles.value}>
                    {currentWafer.process_context?.equipment_used?.[0] || currentWafer.equipment_id || 'N/A'}
                  </span>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Time:</span>
                  <span className={styles.value}>
                    {currentWafer.inspection_timestamp
                      ? new Date(currentWafer.inspection_timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit'
                        })
                      : 'N/A'}
                  </span>
                </div>

                <div className={styles.infoItem}>
                  <span className={styles.label}>Defects:</span>
                  <span className={styles.value}>
                    {currentWafer.defects?.length || currentWafer.defect_summary?.total_defects || 0}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
          </div>
        </div>
      </Card>

      {/* MongoDB Structure Panel - Fixed position above FabPulseBar */}
      {showMongoPanel && (
        <div className={styles.mongoPanel}>
          <div className={styles.mongoPanelContent}>
            <h2>MongoDB Wafer Document Structure</h2>

            {/* Metadata Section */}
            <div className={styles.mongoSection}>
              <h3>Document Metadata</h3>
              <table className={styles.mongoTable}>
                <tbody>
                  <tr>
                    <td>Collection:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.metadata.collection_name}</td>
                  </tr>
                  <tr>
                    <td>Database:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.metadata.database_name}</td>
                  </tr>
                  <tr>
                    <td>Wafer ID:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.document.wafer_id}</td>
                  </tr>
                  <tr>
                    <td>Document Size:</td>
                    <td>{(SAMPLE_WAFER_MONGO_DATA.metadata.document_size_bytes / 1024).toFixed(2)} KB</td>
                  </tr>
                  <tr>
                    <td>Embedding Dimensions:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.metadata.embedding_dimensions}</td>
                  </tr>
                  <tr>
                    <td>Embedding Model:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.metadata.embedding_model}</td>
                  </tr>
                  <tr>
                    <td>Embedding Type:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.metadata.embedding_type}</td>
                  </tr>
                  <tr>
                    <td>Die Map Size:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.metadata.die_map_size}</td>
                  </tr>
                  <tr>
                    <td>Defect Count:</td>
                    <td>{SAMPLE_WAFER_MONGO_DATA.metadata.defect_count}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* JSON Document Section */}
            <div className={styles.mongoSection}>
              <h3>Full Document (JSON)</h3>
              <pre className={styles.jsonPre}>
                {JSON.stringify(SAMPLE_WAFER_MONGO_DATA.document, null, 2)}
              </pre>
            </div>

            {/* Info Note */}
            <div className={styles.infoNote}>
              <span className="emoji">💡</span>
              <div className="content">
                <strong style={{ display: 'block', marginBottom: '8px' }}>About This Document</strong>
                This shows the complete MongoDB document structure for wafer <strong>W_0001</strong> (oldest wafer with embeddings).
                The document includes a <strong>1024-dimensional embedding vector</strong> from the <strong>voyage-multimodal-3</strong> model,
                which is used for semantic similarity search to find similar defect patterns. Data is pre-loaded for instant display.
              </div>
            </div>

            {/* Close button */}
            <button
              className={styles.closeButton}
              onClick={toggleMongoPanel}
              aria-label="Close panel"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveWaferImageMapCompact;