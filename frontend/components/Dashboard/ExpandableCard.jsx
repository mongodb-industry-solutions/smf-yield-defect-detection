"use client";

import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import IconButton from '@leafygreen-ui/icon-button';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import Code from '@leafygreen-ui/code';
import { appPalette } from '@/lib/palette';
import styles from './ExpandableCard.module.css';

const ExpandableCard = ({ 
  title, 
  description, 
  metrics = null,
  mongoQuery = null,
  children,
  defaultExpanded = false,
  icon = 'Database',
  status = 'active' // active, complete, pending
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  
  const getStatusColor = () => {
    switch(status) {
      case 'complete': return appPalette.status.success;
      case 'pending': return appPalette.status.warning;
      default: return appPalette.status.info;
    }
  };

  return (
    <Card 
      className={styles.card}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.12)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
      }}
    >
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Icon 
            glyph={icon} 
            size="large" 
            fill={getStatusColor()}
          />
          <div className={styles.headerText}>
            <H3 className={styles.title}>{title}</H3>
            <Description className={styles.description}>{description}</Description>
          </div>
        </div>
        
        <div className={styles.headerRight}>
          {metrics && (
            <div className={styles.metrics}>
              <Icon glyph="Database" size="small" fill={appPalette.text.secondary} />
              <Description>{metrics}</Description>
            </div>
          )}
          <IconButton
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            <Icon glyph={isExpanded ? 'ChevronUp' : 'ChevronDown'} />
          </IconButton>
        </div>
      </div>

      {isExpanded && (
        <div className={styles.content}>
          {children}
          
          {mongoQuery && (
            <div className={styles.querySection}>
              <div className={styles.queryHeader}>
                <Icon glyph="Code" size="small" fill={appPalette.text.secondary} />
                <Description>MongoDB Query</Description>
              </div>
              <Code 
                language="javascript" 
                copyable
                className={styles.codeBlock}
              >
                {typeof mongoQuery === 'string' 
                  ? mongoQuery 
                  : JSON.stringify(mongoQuery, null, 2)}
              </Code>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

export default ExpandableCard;