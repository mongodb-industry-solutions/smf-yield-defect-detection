"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import Code from '@leafygreen-ui/code';
import styles from './AgenticWorkflowView.module.css';
import { collectionsAPI } from '@/lib/api';

const COLLECTIONS = [
  { name: 'historical_knowledge', label: 'Historical Knowledge' },
  { name: 'wafer_defects', label: 'Wafer Defects' },
  { name: 'alerts', label: 'Alerts' },
  { name: 'process_context', label: 'Process Context' },
  { name: 'process_sensor_ts', label: 'Process Sensor TS' }
];

const AgenticWorkflowView = ({ highlightedCollections = [], onCollectionClick }) => {
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [collectionData, setCollectionData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleCollectionClick = async (collectionName) => {
    // Notify parent which collection was clicked
    if (onCollectionClick) {
      onCollectionClick(collectionName);
    }

    // If clicking the same collection, toggle it closed
    if (selectedCollection === collectionName && collectionData) {
      setSelectedCollection(null);
      setCollectionData(null);
      return;
    }

    setLoading(true);
    setSelectedCollection(collectionName);
    try {
      // Load from local JSON file for instant loading
      const response = await fetch(`/data/sample_collections/${collectionName}.json`);
      const document = await response.json();

      // Format data to match API response structure
      const data = {
        collection: collectionName,
        count: 1,
        documents: [document]
      };

      setCollectionData(data);
    } catch (error) {
      console.error('Error loading collection data:', error);
      setCollectionData({ error: 'Failed to load data' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      {/* Single Unified Card */}
      <Card className={styles.unifiedCard}>
        {/* Header Section with Buttons */}
        <div className={styles.headerSection}>
          <div className={styles.headerContent}>
            <div>
              <Description className={styles.headerDescription}>
                Unified Data Foundation for AI Agents
              </Description>
              <H3 className={styles.headerTitle}>Agentic Data Layer</H3>
              <Body className={styles.headerSubtitle}>
                MongoDB Atlas Collections
              </Body>
            </div>

            <div className={styles.rightSection}>
              {/* Collection Buttons in Header */}
              <div className={styles.compactButtonsGrid}>
                {COLLECTIONS.map((collection) => (
                  <button
                    key={collection.name}
                    className={`${styles.compactButton}
                      ${selectedCollection === collection.name ? styles.active : ''}
                      ${highlightedCollections.includes(collection.name) ? styles.highlighted : ''}`}
                    onClick={() => handleCollectionClick(collection.name)}
                    disabled={loading}
                    title={collection.label}
                  >
                    <Icon glyph="CurlyBraces" size="small" className={styles.compactIcon} />
                    <span className={styles.compactLabel}>{collection.label}</span>
                  </button>
                ))}
              </div>
              <Badge variant="green">Atlas</Badge>
            </div>
          </div>
        </div>

        {/* Data Display Section */}
        {loading && (
          <div className={styles.dataSection}>
            <Body className={styles.loadingText}>Loading...</Body>
          </div>
        )}

        {!loading && collectionData && (
          <div className={styles.dataSection}>
            <div className={styles.dataSectionHeader}>
              <div>
                <Body weight="medium">{selectedCollection}</Body>
                <Body className={styles.dataSubtitle}>
                  {collectionData.count} document{collectionData.count !== 1 ? 's' : ''} (latest)
                </Body>
              </div>
              <Badge variant="blue">{collectionData.collection}</Badge>
            </div>

            {collectionData.error ? (
              <div className={styles.errorMessage}>
                <Body>{collectionData.error}</Body>
              </div>
            ) : (
              <div className={styles.documentsContainer}>
                {collectionData.documents && collectionData.documents.map((doc, index) => (
                  <div key={index} className={styles.documentBlock}>
                    <div className={styles.documentHeader}>
                      <Body weight="medium">Document {index + 1}</Body>
                      {doc._id && <Badge variant="lightgray" style={{ fontSize: '10px' }}>{doc._id}</Badge>}
                    </div>
                    <Code
                      language="javascript"
                      className={styles.codeBlock}
                    >
                      {JSON.stringify(doc, null, 2)}
                    </Code>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
};

export default AgenticWorkflowView;
