"use client";

import React from 'react';
import { Body, Subtitle } from '@leafygreen-ui/typography';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import styles from './WaferVisualization.module.css';

export default function WaferVisualization({ data }) {
  if (!data || !data.wafer) {
    return null;
  }

  const { wafer, wafer_type, similar_historical_patterns, search_metadata } = data;
  const inkMap = wafer.ink_map || {};
  const defectSummary = wafer.defect_summary || {};

  // Get image source (thumbnail_base64 or full_image_url)
  const getImageSrc = (inkMapData) => {
    if (inkMapData?.thumbnail_base64) {
      return `data:image/png;base64,${inkMapData.thumbnail_base64}`;
    }
    return null;
  };

  const currentImage = getImageSrc(inkMap);

  return (
    <div className={styles.container}>
      {/* Current Wafer Section */}
      <div className={styles.currentWafer}>
        <div className={styles.header}>
          <Subtitle>Current Wafer: {wafer.wafer_id}</Subtitle>
          <Badge variant={wafer_type === 'new' ? 'blue' : 'lightgray'}>
            {wafer_type === 'new' ? 'New Wafer' : 'Historical'}
          </Badge>
        </div>

        <div className={styles.waferContent}>
          {currentImage && (
            <div className={styles.waferImageContainer}>
              <img
                src={currentImage}
                alt={`Wafer ${wafer.wafer_id} defect map`}
                className={styles.waferImage}
              />
              <Body className={styles.imageCaption}>Ink Map Visualization</Body>
            </div>
          )}

          <div className={styles.waferInfo}>
            <div className={styles.infoGrid}>
              <div className={styles.infoItem}>
                <Body weight="medium">Lot ID:</Body>
                <Body>{wafer.lot_id}</Body>
              </div>
              <div className={styles.infoItem}>
                <Body weight="medium">Yield:</Body>
                <Body>
                  {defectSummary.yield_percentage?.toFixed(2)}%
                  ({defectSummary.failed_dies}/{defectSummary.total_dies} dies failed)
                </Body>
              </div>
              <div className={styles.infoItem}>
                <Body weight="medium">Defect Pattern:</Body>
                <Badge variant={defectSummary.severity === 'high' ? 'red' : 'yellow'}>
                  {defectSummary.defect_pattern} - {defectSummary.severity}
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Similar Patterns Section */}
      {similar_historical_patterns && similar_historical_patterns.length > 0 && (
        <div className={styles.similarPatterns}>
          <div className={styles.similarHeader}>
            <Icon glyph="Charts" />
            <Subtitle>
              Similar Historical Patterns ({similar_historical_patterns.length})
            </Subtitle>
            {search_metadata?.embedding_type && (
              <Badge variant="green">{search_metadata.embedding_type} search</Badge>
            )}
          </div>

          <div className={styles.patternsGrid}>
            {similar_historical_patterns.map((pattern, idx) => {
              const patternImage = getImageSrc(pattern.ink_map);
              const score = (pattern.similarity_score * 100).toFixed(1);

              return (
                <div key={idx} className={styles.patternCard}>
                  <div className={styles.patternHeader}>
                    <Body weight="medium">{pattern.wafer_id}</Body>
                    <Badge variant={score > 90 ? 'green' : 'blue'}>
                      {score}% match
                    </Badge>
                  </div>

                  {patternImage && (
                    <div className={styles.patternImageContainer}>
                      <img
                        src={patternImage}
                        alt={`Similar pattern ${pattern.wafer_id}`}
                        className={styles.patternImage}
                      />
                    </div>
                  )}

                  <div className={styles.patternInfo}>
                    <Body className={styles.patternDescription}>
                      {pattern.description}
                    </Body>
                    <div className={styles.patternMeta}>
                      <Body baseFontSize={13}>
                        Yield: {pattern.defect_summary?.yield_percentage?.toFixed(1)}%
                      </Body>
                      <Body baseFontSize={13}>
                        {pattern.defect_summary?.defect_pattern}
                      </Body>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
