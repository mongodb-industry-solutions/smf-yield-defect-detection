import React from 'react';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { getMongoDBColor } from '@/utils/semanticColors';
import styles from './MongoDBBadge.module.css';

const MongoDBBadge = ({
  feature,
  count,
  active = false,
  size = 'default',
  className = '',
  onClick,
  customLabel,
  showIcon = true,
}) => {
  // Map features to LeafyGreen badge variants
  const getVariant = () => {
    switch(feature) {
      case 'changeStreams': return 'green';
      case 'vectorSearch': return 'purple';
      case 'atlasSearch': return 'blue';
      case 'timeSeries': return 'yellow';
      case 'aggregation': return 'lightgray';
      case 'transactions': return 'darkgreen';
      case 'sharding': return 'darkgray';
      default: return 'lightgray';
    }
  };

  // Map features to LeafyGreen icon glyphs
  const getIcon = () => {
    switch(feature) {
      case 'changeStreams': return 'Refresh';
      case 'vectorSearch': return 'Diagram';
      case 'atlasSearch': return 'MagnifyingGlass';
      case 'timeSeries': return 'Charts';
      case 'aggregation': return 'Code';
      case 'transactions': return 'Lock';
      case 'sharding': return 'Cloud';
      default: return 'Database';
    }
  };

  // Get display label for the feature
  const getLabel = () => {
    if (customLabel) return customLabel;

    switch(feature) {
      case 'changeStreams': return 'Change Streams';
      case 'vectorSearch': return 'Vector Search';
      case 'atlasSearch': return 'Atlas Search';
      case 'timeSeries': return 'Time Series';
      case 'aggregation': return 'Aggregation';
      case 'transactions': return 'Transactions';
      case 'sharding': return 'Sharding';
      default: return feature;
    }
  };

  const badgeClasses = `
    ${styles.badge}
    ${active ? styles.active : styles.idle}
    ${onClick ? styles.clickable : ''}
    ${className}
  `.trim();

  const content = (
    <>
      {showIcon && (
        <span className={styles.iconWrapper}>
          <Icon glyph={getIcon()} size="small" />
        </span>
      )}
      <span className={styles.label}>{getLabel()}</span>
      {count !== undefined && count !== null && (
        <span className={styles.count}>
          {count > 999 ? '999+' : count}
        </span>
      )}
      {active && <span className={styles.pulse} />}
    </>
  );

  const badge = (
    <Badge
      variant={getVariant()}
      className={badgeClasses}
      size={size}
    >
      {content}
    </Badge>
  );

  if (onClick) {
    return (
      <button
        onClick={onClick}
        className={styles.badgeButton}
        type="button"
        aria-label={`${getLabel()} - ${active ? 'Active' : 'Idle'}${count !== undefined ? ` (${count})` : ''}`}
      >
        {badge}
      </button>
    );
  }

  return badge;
};

// Compound component for badge groups
export const MongoDBBadgeGroup = ({ children, className = '' }) => {
  return (
    <div className={`${styles.badgeGroup} ${className}`}>
      {children}
    </div>
  );
};

// Export specific badge presets for common use cases
export const ChangeStreamsBadge = (props) => (
  <MongoDBBadge feature="changeStreams" {...props} />
);

export const VectorSearchBadge = (props) => (
  <MongoDBBadge feature="vectorSearch" {...props} />
);

export const TimeSeriesBadge = (props) => (
  <MongoDBBadge feature="timeSeries" {...props} />
);

export const AggregationBadge = (props) => (
  <MongoDBBadge feature="aggregation" {...props} />
);

export default MongoDBBadge;