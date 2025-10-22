"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Button from '@leafygreen-ui/button';
import Modal from '@leafygreen-ui/modal';
import { SAMPLE_WAFER_MONGO_DATA } from '@/lib/sampleWaferData';
import styles from './LiveWaferImageMapCompact.module.css';

const LiveWaferImageMapCompact = () => {
  const [waferData, setWaferData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedWafer, setSelectedWafer] = useState(0);
  const [showMongoModal, setShowMongoModal] = useState(false);

  // Fetch wafer data with thumbnails
  const fetchWaferData = async () => {
    const startTime = performance.now();
    console.log('[LiveWaferImageMapCompact] 🚀 Starting wafer fetch...');

    try {
      const fetchStart = performance.now();
      const response = await fetch('http://localhost:8000/wafers/latest?limit=3&include_visualization=true');
      const fetchEnd = performance.now();
      console.log(`[LiveWaferImageMapCompact] ⏱️  Fetch request completed in ${(fetchEnd - fetchStart).toFixed(0)}ms`);

      const parseStart = performance.now();
      const data = await response.json();
      const parseEnd = performance.now();
      console.log(`[LiveWaferImageMapCompact] 📦 JSON parsing completed in ${(parseEnd - parseStart).toFixed(0)}ms`);
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

  // Show pre-loaded MongoDB sample data (instant - no API call)
  const showMongoData = () => {
    setShowMongoModal(true);
  };

  // Inject CSS to fix modal z-index above FabPulseBar
  useEffect(() => {
    if (showMongoModal) {
      const styleId = 'mongo-modal-zindex-fix';

      // Check if style already exists
      if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
          /* Override LeafyGreen Modal z-index to appear above FabPulseBar (z-index: 1001) */
          body > div[role="presentation"],
          body > div[role="presentation"] > *,
          div[role="dialog"],
          div[data-lg-id*="modal"] {
            z-index: 10001 !important;
          }
        `;
        document.head.appendChild(style);
      }

      // Cleanup function to remove style when modal closes
      return () => {
        const existingStyle = document.getElementById(styleId);
        if (existingStyle) {
          existingStyle.remove();
        }
      };
    }
  }, [showMongoModal]);

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
              onClick={showMongoData}
              style={{ marginRight: '12px' }}
            >
              View MongoDB Structure
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

      {/* MongoDB Structure Modal */}
      <Modal
        open={showMongoModal}
        setOpen={setShowMongoModal}
        size="large"
      >
          <div style={{
            padding: '24px',
            maxHeight: '85vh',
            overflow: 'auto',
            backgroundColor: 'var(--color-neutral-light3)'
          }}>
            <h2 style={{
              marginBottom: '20px',
              color: 'var(--color-neutral-dark3)',
              fontSize: '24px',
              fontWeight: 600,
              borderBottom: '2px solid var(--color-primary-base)',
              paddingBottom: '12px'
            }}>
              MongoDB Wafer Document Structure
            </h2>

            {/* Metadata Section */}
            <div style={{
              backgroundColor: '#ffffff',
              padding: '20px',
              borderRadius: '8px',
              marginBottom: '20px',
              border: '1px solid var(--color-neutral-light2)',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}>
              <h3 style={{
                marginBottom: '16px',
                color: 'var(--color-primary-dark2)',
                fontSize: '18px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span style={{
                  display: 'inline-block',
                  width: '4px',
                  height: '20px',
                  backgroundColor: 'var(--color-primary-base)',
                  borderRadius: '2px'
                }}></span>
                Document Metadata
              </h3>
              <table style={{
                width: '100%',
                fontSize: '14px',
                borderCollapse: 'collapse'
              }}>
                <tbody>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{
                      padding: '12px 8px',
                      fontWeight: 600,
                      color: 'var(--color-neutral-dark2)',
                      width: '40%'
                    }}>Collection:</td>
                    <td style={{
                      padding: '12px 8px',
                      color: 'var(--color-neutral-dark3)',
                      fontFamily: 'monospace',
                      fontSize: '13px'
                    }}>{SAMPLE_WAFER_MONGO_DATA.metadata.collection_name}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Database:</td>
                    <td style={{
                      padding: '12px 8px',
                      color: 'var(--color-neutral-dark3)',
                      fontFamily: 'monospace',
                      fontSize: '13px'
                    }}>{SAMPLE_WAFER_MONGO_DATA.metadata.database_name}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Wafer ID:</td>
                    <td style={{
                      padding: '12px 8px',
                      color: 'var(--color-primary-dark2)',
                      fontFamily: 'monospace',
                      fontWeight: 600,
                      fontSize: '13px'
                    }}>{SAMPLE_WAFER_MONGO_DATA.document.wafer_id}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Document Size:</td>
                    <td style={{ padding: '12px 8px', color: 'var(--color-neutral-dark3)' }}>
                      {(SAMPLE_WAFER_MONGO_DATA.metadata.document_size_bytes / 1024).toFixed(2)} KB
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Embedding Dimensions:</td>
                    <td style={{
                      padding: '12px 8px',
                      color: 'var(--color-neutral-dark3)',
                      fontWeight: 600
                    }}>{SAMPLE_WAFER_MONGO_DATA.metadata.embedding_dimensions}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Embedding Model:</td>
                    <td style={{
                      padding: '12px 8px',
                      color: 'var(--color-neutral-dark3)',
                      fontFamily: 'monospace',
                      fontSize: '13px'
                    }}>{SAMPLE_WAFER_MONGO_DATA.metadata.embedding_model}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Embedding Type:</td>
                    <td style={{ padding: '12px 8px', color: 'var(--color-neutral-dark3)' }}>
                      {SAMPLE_WAFER_MONGO_DATA.metadata.embedding_type}
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--color-neutral-light2)' }}>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Die Map Size:</td>
                    <td style={{ padding: '12px 8px', color: 'var(--color-neutral-dark3)' }}>
                      {SAMPLE_WAFER_MONGO_DATA.metadata.die_map_size}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ padding: '12px 8px', fontWeight: 600, color: 'var(--color-neutral-dark2)' }}>Defect Count:</td>
                    <td style={{ padding: '12px 8px', color: 'var(--color-neutral-dark3)' }}>
                      {SAMPLE_WAFER_MONGO_DATA.metadata.defect_count}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* JSON Document Section */}
            <div style={{
              backgroundColor: '#ffffff',
              padding: '20px',
              borderRadius: '8px',
              marginBottom: '20px',
              border: '1px solid var(--color-neutral-light2)',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}>
              <h3 style={{
                marginBottom: '16px',
                color: 'var(--color-primary-dark2)',
                fontSize: '18px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span style={{
                  display: 'inline-block',
                  width: '4px',
                  height: '20px',
                  backgroundColor: 'var(--color-primary-base)',
                  borderRadius: '2px'
                }}></span>
                Full Document (JSON)
              </h3>
              <pre style={{
                backgroundColor: 'var(--color-neutral-light3)',
                color: 'var(--color-neutral-dark3)',
                padding: '16px',
                borderRadius: '6px',
                fontSize: '12px',
                lineHeight: '1.6',
                overflow: 'auto',
                maxHeight: '450px',
                margin: 0,
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                border: '1px solid var(--color-neutral-light2)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}>
                {JSON.stringify(SAMPLE_WAFER_MONGO_DATA.document, null, 2)}
              </pre>
            </div>

            {/* Info Note */}
            <div style={{
              backgroundColor: 'var(--color-yellow-light2)',
              padding: '16px',
              borderRadius: '8px',
              fontSize: '14px',
              border: '1px solid var(--color-yellow-base)',
              display: 'flex',
              gap: '12px',
              alignItems: 'flex-start'
            }}>
              <span style={{
                fontSize: '20px',
                flexShrink: 0,
                marginTop: '2px'
              }}>💡</span>
              <div style={{ color: 'var(--color-neutral-dark3)' }}>
                <strong style={{ display: 'block', marginBottom: '4px' }}>About This Document</strong>
                This shows the complete MongoDB document structure for wafer <strong>W_0001</strong> (oldest wafer with embeddings).
                The document includes a <strong>1024-dimensional embedding vector</strong> from the <strong>voyage-multimodal-3</strong> model,
                which is used for semantic similarity search to find similar defect patterns. Data is pre-loaded for instant display.
              </div>
            </div>
          </div>
        </Modal>
    </div>
  );
};

export default LiveWaferImageMapCompact;