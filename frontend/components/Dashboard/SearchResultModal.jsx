"use client";

import React from 'react';
import Modal from '@leafygreen-ui/modal';
import Button from '@leafygreen-ui/button';
import Badge from '@leafygreen-ui/badge';
import { H2, H3, Body, Description } from '@leafygreen-ui/typography';
import styles from './SearchResultModal.module.css';

const SearchResultModal = ({ result, open, onClose }) => {
  if (!result) return null;

  const { collectionType } = result;

  return (
    <Modal
      open={open}
      setOpen={onClose}
      size="default"
    >
      <div className={styles.modalContent}>
        {collectionType === 'wafer' && <WaferDetails result={result} />}
        {collectionType === 'process' && <ProcessDetails result={result} />}
        {collectionType === 'knowledge' && <KnowledgeDetails result={result} />}

        <div className={styles.modalFooter}>
          <Button variant="default" onClick={onClose}>Close</Button>
          <Button
            onClick={() => {
              navigator.clipboard.writeText(JSON.stringify(result, null, 2));
              alert('Full data copied to clipboard');
            }}
          >
            Copy Full Data
          </Button>
        </div>
      </div>
    </Modal>
  );
};

// Wafer Details Component
const WaferDetails = ({ result }) => {
  return (
    <div className={styles.detailsContainer}>
      <div className={styles.header}>
        <H2>Wafer Details: {result.wafer_id}</H2>
        <Badge variant={
          result.severity === 'high' ? 'red' :
          result.severity === 'medium' ? 'yellow' : 'blue'
        }>
          {result.severity?.toUpperCase()}
        </Badge>
      </div>

      <div className={styles.grid}>
        <div className={styles.section}>
          <H3>Basic Information</H3>
          <div className={styles.infoGrid}>
            <div className={styles.infoItem}>
              <Body weight="medium">Wafer ID:</Body>
              <Body>{result.wafer_id}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Lot ID:</Body>
              <Body>{result.lot_id}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Equipment:</Body>
              <Body>{result.equipment_id}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Defect Pattern:</Body>
              <Body>{result.defect_pattern}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Yield:</Body>
              <Body>{result.yield_percentage}%</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Failed Dies:</Body>
              <Body>{result.failed_dies} / 625</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Search Score:</Body>
              <Body>{result.score?.toFixed(4)}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Inspection Time:</Body>
              <Body>{result.inspection_timestamp ? new Date(result.inspection_timestamp).toLocaleString() : 'N/A'}</Body>
            </div>
          </div>
        </div>

        {result.ink_map && (
          <div className={styles.section}>
            <H3>Wafer Map</H3>
            {result.ink_map.thumbnail_base64 ? (
              <div className={styles.imageContainer}>
                <img
                  src={`data:image/png;base64,${result.ink_map.thumbnail_base64}`}
                  alt={`Wafer ${result.wafer_id} map`}
                  className={styles.waferImage}
                />
                <Description>
                  Thumbnail: {result.ink_map.thumbnail_size}
                  {result.ink_map.full_image_url && (
                    <> | Full image: {result.ink_map.full_image_size}</>
                  )}
                </Description>
              </div>
            ) : (
              <Description>No thumbnail available</Description>
            )}
          </div>
        )}
      </div>

      {result.description && (
        <div className={styles.section}>
          <H3>Description</H3>
          <Body>{result.description}</Body>
        </div>
      )}

      {result.defect_summary && (
        <div className={styles.section}>
          <H3>Defect Summary</H3>
          <div className={styles.infoGrid}>
            <div className={styles.infoItem}>
              <Body weight="medium">Total Dies:</Body>
              <Body>{result.defect_summary.total_dies}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Failed Dies:</Body>
              <Body>{result.defect_summary.failed_dies}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Yield:</Body>
              <Body>{result.defect_summary.yield_percentage}%</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Pattern:</Body>
              <Body>{result.defect_summary.defect_pattern}</Body>
            </div>
            <div className={styles.infoItem}>
              <Body weight="medium">Severity:</Body>
              <Body>{result.defect_summary.severity}</Body>
            </div>
          </div>
        </div>
      )}

      {result.defects && result.defects.length > 0 && (
        <div className={styles.section}>
          <H3>Defect Coordinates</H3>
          <Description>
            {result.defects.length} defect location(s) recorded
            {result.defects.length <= 10 && (
              <div className={styles.defectList}>
                {result.defects.slice(0, 10).map((defect, idx) => (
                  <span key={idx} className={styles.defectCoord}>
                    ({defect.x}, {defect.y})
                  </span>
                ))}
              </div>
            )}
          </Description>
        </div>
      )}

      {result.process_context && Object.keys(result.process_context).length > 0 && (
        <div className={styles.section}>
          <H3>Process Context</H3>
          <div className={styles.infoGrid}>
            {Object.entries(result.process_context).map(([key, value]) => (
              <div key={key} className={styles.infoItem}>
                <Body weight="medium">{key.replace(/_/g, ' ')}:</Body>
                <Body>{String(value)}</Body>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Process Context Details Component
const ProcessDetails = ({ result }) => {
  return (
    <div className={styles.detailsContainer}>
      <div className={styles.header}>
        <H2>{result.context_id}</H2>
        <div className={styles.badges}>
          <Badge variant="lightgray">{result.context_type}</Badge>
          {result.is_problematic && <Badge variant="red">PROBLEMATIC</Badge>}
        </div>
      </div>

      <div className={styles.section}>
        <H3>Basic Information</H3>
        <div className={styles.infoGrid}>
          <div className={styles.infoItem}>
            <Body weight="medium">Context ID:</Body>
            <Body>{result.context_id}</Body>
          </div>
          <div className={styles.infoItem}>
            <Body weight="medium">Context Type:</Body>
            <Body>{result.context_type}</Body>
          </div>
          <div className={styles.infoItem}>
            <Body weight="medium">Search Score:</Body>
            <Body>{result.score?.toFixed(4)}</Body>
          </div>
          {result.manufacturer && (
            <div className={styles.infoItem}>
              <Body weight="medium">Manufacturer:</Body>
              <Body>{result.manufacturer}</Body>
            </div>
          )}
          {result.composition && (
            <div className={styles.infoItem}>
              <Body weight="medium">Composition:</Body>
              <Body>{result.composition}</Body>
            </div>
          )}
          {result.process_type && (
            <div className={styles.infoItem}>
              <Body weight="medium">Process Type:</Body>
              <Body>{result.process_type}</Body>
            </div>
          )}
        </div>
      </div>

      {result.slurry_details && (
        <div className={styles.section}>
          <H3>Slurry Details</H3>
          <div className={styles.jsonView}>
            <pre>{JSON.stringify(result.slurry_details, null, 2)}</pre>
          </div>
        </div>
      )}

      {result.recipe_details && (
        <div className={styles.section}>
          <H3>Recipe Details</H3>
          <div className={styles.jsonView}>
            <pre>{JSON.stringify(result.recipe_details, null, 2)}</pre>
          </div>
        </div>
      )}

      {result.reticle_details && (
        <div className={styles.section}>
          <H3>Reticle Details</H3>
          <div className={styles.jsonView}>
            <pre>{JSON.stringify(result.reticle_details, null, 2)}</pre>
          </div>
        </div>
      )}

      {result.known_issues && result.known_issues.length > 0 && (
        <div className={styles.section}>
          <H3>Known Issues</H3>
          {result.known_issues.map((issue, idx) => (
            <div key={idx} className={styles.issueCard}>
              <Badge variant="red">{issue.severity}</Badge>
              <Body>{issue.description}</Body>
              <Description>Date: {issue.date}</Description>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Knowledge Base Details Component
const KnowledgeDetails = ({ result }) => {
  return (
    <div className={styles.detailsContainer}>
      <div className={styles.header}>
        <H2>{result.title}</H2>
        <Badge variant={result.document_type === 'rca_report' ? 'yellow' : 'blue'}>
          {result.document_type === 'rca_report' ? 'RCA Report' : 'Troubleshooting Guide'}
        </Badge>
      </div>

      <div className={styles.section}>
        <H3>Document Information</H3>
        <div className={styles.infoGrid}>
          <div className={styles.infoItem}>
            <Body weight="medium">Document ID:</Body>
            <Body>{result.document_id}</Body>
          </div>
          <div className={styles.infoItem}>
            <Body weight="medium">Document Type:</Body>
            <Body>{result.document_type}</Body>
          </div>
          <div className={styles.infoItem}>
            <Body weight="medium">Search Score:</Body>
            <Body>{result.score?.toFixed(4)}</Body>
          </div>
          {result.process_area && (
            <div className={styles.infoItem}>
              <Body weight="medium">Process Area:</Body>
              <Body>{result.process_area}</Body>
            </div>
          )}
          {result.defect_type && (
            <div className={styles.infoItem}>
              <Body weight="medium">Defect Type:</Body>
              <Body>{result.defect_type}</Body>
            </div>
          )}
          {result.estimated_resolution_time && (
            <div className={styles.infoItem}>
              <Body weight="medium">Est. Resolution Time:</Body>
              <Body>{result.estimated_resolution_time}</Body>
            </div>
          )}
          {result.resolution_time_hours && (
            <div className={styles.infoItem}>
              <Body weight="medium">Resolution Time:</Body>
              <Body>{result.resolution_time_hours} hours</Body>
            </div>
          )}
        </div>
      </div>

      {result.root_cause && (
        <div className={styles.section}>
          <H3>Root Cause</H3>
          <Body className={styles.highlight}>{result.root_cause}</Body>
        </div>
      )}

      {result.content && (
        <div className={styles.section}>
          <H3>Full Content</H3>
          <Body className={styles.content}>{result.content}</Body>
        </div>
      )}

      {result.findings && Object.keys(result.findings).length > 0 && (
        <div className={styles.section}>
          <H3>Findings</H3>
          <div className={styles.jsonView}>
            <pre>{JSON.stringify(result.findings, null, 2)}</pre>
          </div>
        </div>
      )}

      {result.solutions && result.solutions.length > 0 && (
        <div className={styles.section}>
          <H3>Solutions & Recommendations</H3>
          {result.solutions.map((solution, idx) => (
            <div key={idx} className={styles.solutionCard}>
              <Body weight="medium">{idx + 1}. {solution.action || solution.title || solution}</Body>
              {solution.description && (
                <Description>{solution.description}</Description>
              )}
              {solution.expected_outcome && (
                <Description>Expected Outcome: {solution.expected_outcome}</Description>
              )}
            </div>
          ))}
        </div>
      )}

      {result.corrective_actions && result.corrective_actions.length > 0 && (
        <div className={styles.section}>
          <H3>Corrective Actions</H3>
          {result.corrective_actions.map((action, idx) => (
            <div key={idx} className={styles.solutionCard}>
              <Body weight="medium">{idx + 1}. {action}</Body>
            </div>
          ))}
        </div>
      )}

      {result.metadata && Object.keys(result.metadata).length > 0 && (
        <div className={styles.section}>
          <H3>Additional Metadata</H3>
          <div className={styles.jsonView}>
            <pre>{JSON.stringify(result.metadata, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchResultModal;
