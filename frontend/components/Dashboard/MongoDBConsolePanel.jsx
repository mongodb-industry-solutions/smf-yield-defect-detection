"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import IconButton from '@leafygreen-ui/icon-button';
import styles from './MongoDBConsolePanel.module.css';

/**
 * MongoDBConsolePanel - Shows live MongoDB operations flow
 * Displays the pipeline: Excursion → Change Stream → Alert → Vector Search → RCA
 */
const MongoDBConsolePanel = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Sample operations flow showing what happens when an excursion occurs
  const operationsFlow = [
    {
      step: 1,
      feature: 'Time Series Query',
      icon: 'TimeSeries',
      color: '#00684a',
      query: 'db.process_sensor_ts.find({ particle_count: { $gt: 1000 } })',
      description: 'Particle excursion detected',
      status: 'complete',
      time: '12ms'
    },
    {
      step: 2,
      feature: 'Change Stream',
      icon: 'RefreshData',
      color: '#00a35c',
      query: 'db.process_sensor_ts.watch([{ $match: { "fullDocument.metrics.particle_count": { $gt: 1000 } } }])',
      description: 'Real-time monitoring triggered',
      status: 'active',
      time: 'Live'
    },
    {
      step: 3,
      feature: 'Aggregation Pipeline',
      icon: 'Diagram3',
      color: '#13aa52',
      query: 'db.alerts.insertOne({ severity: "critical", equipment_id: "CMP_TOOL_02", ... })',
      description: 'Alert created and stored',
      status: 'complete',
      time: '8ms'
    },
    {
      step: 4,
      feature: 'Vector Search',
      icon: 'MagnifyingGlass',
      color: '#589636',
      query: 'db.historical_knowledge.aggregate([{ $vectorSearch: { queryVector: [...], path: "embedding", numCandidates: 50, limit: 10 } }])',
      description: 'Finding similar past defects',
      status: 'complete',
      time: '23ms'
    },
    {
      step: 5,
      feature: 'Graph Lookup',
      icon: 'Connect',
      color: '#3fa142',
      query: 'db.process_context.aggregate([{ $graphLookup: { from: "wafer_defects", startWith: "$batch_id", connectFromField: "batch_id", connectToField: "batch_id", as: "related_defects" } }])',
      description: 'Correlation analysis running',
      status: 'running',
      time: '45ms'
    }
  ];

  return (
    <div className={styles.compactPanel}>
      {/* Collapsed Header */}
      <div className={styles.header} onClick={() => setIsExpanded(!isExpanded)}>
        <div className={styles.headerLeft}>
          <Icon glyph="Database" fill="#00684a" />
          <h4 className={styles.title}>MongoDB Console</h4>
          <Badge variant="darkgray" className={styles.badge}>
            <Icon glyph="Sparkle" size="small" /> Live Operations
          </Badge>
          <div className={styles.pipelineIndicator}>
            {operationsFlow.map((op, idx) => (
              <div
                key={idx}
                className={`${styles.dot} ${op.status === 'active' ? styles.activeDot : ''} ${op.status === 'running' ? styles.runningDot : ''}`}
                style={{ backgroundColor: op.color }}
                title={op.feature}
              />
            ))}
          </div>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.statsText}>
            5 operations • 88ms total
          </span>
          <IconButton
            aria-label={isExpanded ? "Collapse" : "Expand"}
            className={styles.expandButton}
          >
            <Icon glyph={isExpanded ? "ChevronDown" : "ChevronRight"} />
          </IconButton>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className={styles.expandedContent}>
          <div className={styles.flowContainer}>
            {operationsFlow.map((op, index) => (
              <React.Fragment key={index}>
                <div className={styles.operationCard}>
                  <div className={styles.operationHeader}>
                    <div className={styles.stepBadge}>
                      <span className={styles.stepNumber}>{op.step}</span>
                    </div>
                    <Icon glyph={op.icon} fill={op.color} />
                    <div className={styles.operationInfo}>
                      <div className={styles.featureName}>{op.feature}</div>
                      <div className={styles.description}>{op.description}</div>
                    </div>
                    <div className={styles.operationStatus}>
                      {op.status === 'active' && (
                        <Badge variant="blue">
                          <span className={styles.pulsingDot}></span> ACTIVE
                        </Badge>
                      )}
                      {op.status === 'running' && (
                        <Badge variant="lightgray">
                          <Icon glyph="Clock" size="small" /> {op.time}
                        </Badge>
                      )}
                      {op.status === 'complete' && (
                        <Badge variant="green">
                          <Icon glyph="Checkmark" size="small" /> {op.time}
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* MongoDB Query */}
                  <div className={styles.queryBox}>
                    <code className={styles.queryCode}>{op.query}</code>
                  </div>
                </div>

                {/* Flow Arrow */}
                {index < operationsFlow.length - 1 && (
                  <div className={styles.flowArrow}>
                    <Icon glyph="ArrowRight" fill="#a0aec0" size="small" />
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Footer with MongoDB branding */}
          <div className={styles.footer}>
            <Icon glyph="Logo" fill="#00684a" size="small" />
            <span className={styles.footerText}>
              Real-time operations powered by MongoDB Atlas • Time Series • Vector Search • Change Streams
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default MongoDBConsolePanel;
