// Semantic color system for SMF Yield Defect Detection Dashboard
// MongoDB feature colors, severity levels, and process indicators

export const semanticColors = {
  // Risk/Severity levels for alerts and defects
  severity: {
    critical: '#8B0000',     // Dark red - Critical alerts
    high: '#C62D42',         // Red - High severity
    medium: '#F39C12',       // Orange - Medium severity
    low: '#00A86B',          // Green - Low severity/normal
    info: '#0070F3',         // Blue - Informational
  },

  // MongoDB feature colors for transparency
  mongodb: {
    changeStreams: '#00ED64',    // Bright green - Real-time updates
    vectorSearch: '#9B59B6',     // Purple - AI/ML features
    atlasSearch: '#3498DB',      // Blue - Text search
    timeSeries: '#F39C12',       // Orange - Time-series data
    aggregation: '#E67E22',      // Dark orange - Pipeline operations
    transactions: '#00684A',     // Dark green - ACID transactions
    sharding: '#34495E',         // Dark gray - Distributed data
  },

  // Equipment status colors
  equipment: {
    online: '#00ED64',       // Bright green - Operating normally
    idle: '#95A5A6',         // Gray - Not in use
    warning: '#FBB13C',      // Yellow - Warning state
    critical: '#E11900',     // Red - Critical issue
    maintenance: '#3498DB',   // Blue - Under maintenance
    offline: '#2C3E50',      // Dark gray - Powered off
  },

  // Defect pattern colors for wafer maps
  patterns: {
    clustered: '#FF6B6B',    // Red - Particle contamination
    edge: '#4ECDC4',         // Teal - Handling issues
    systematic: '#45B7D1',    // Light blue - Equipment drift
    random: '#96CEB4',       // Mint - Baseline defects
    scratch: '#D4A574',      // Brown - Physical damage
    center: '#FFD93D',       // Yellow - Center focused
    none: '#E8E8E8',         // Light gray - No pattern
  },

  // Process status indicators
  process: {
    good: '#D4EDDA',         // Light green background
    problematic: '#F8D7DA',   // Light red background
    warning: '#FFF3CD',      // Light yellow background
    unknown: '#E2E3E5',      // Light gray background
    goodText: '#155724',     // Dark green text
    problematicText: '#721C24', // Dark red text
    warningText: '#856404',   // Dark yellow text
    unknownText: '#383D41',   // Dark gray text
  },

  // Chart colors for data visualization
  charts: {
    primary: '#00684A',      // MongoDB green
    secondary: '#13AA52',    // Light MongoDB green
    tertiary: '#00ED64',     // Bright green
    quaternary: '#3498DB',   // Blue
    danger: '#E11900',       // Red
    warning: '#FBB13C',      // Yellow
    gridLines: 'rgba(0, 0, 0, 0.05)',
    tooltipBg: 'rgba(0, 0, 0, 0.8)',
  },

  // Background colors for panels
  backgrounds: {
    panel: '#FFFFFF',
    panelHover: '#F7F9FB',
    section: '#F7F9FB',
    overlay: 'rgba(0, 0, 0, 0.5)',
    glass: 'rgba(255, 255, 255, 0.95)',
    glassHover: 'rgba(255, 255, 255, 0.98)',
  },

  // Border colors
  borders: {
    default: '#E0E4E7',
    light: 'rgba(224, 228, 231, 0.6)',
    focus: '#00684A',
    error: '#E11900',
    success: '#00ED64',
  },

  // Text colors
  text: {
    primary: '#1A1A1A',
    secondary: '#5E6C84',
    tertiary: '#95A5A6',
    inverse: '#FFFFFF',
    link: '#0070F3',
    linkHover: '#0051CC',
  },

  // Shadow definitions
  shadows: {
    small: '0 2px 4px rgba(0, 0, 0, 0.05)',
    medium: '0 4px 12px rgba(0, 0, 0, 0.08)',
    large: '0 8px 24px rgba(0, 0, 0, 0.12)',
    glow: '0 0 20px rgba(0, 237, 100, 0.3)',
  },
};

// Helper functions for getting colors

export const getSeverityColor = (severity) => {
  const severityLower = severity?.toLowerCase();
  return semanticColors.severity[severityLower] || semanticColors.severity.info;
};

export const getSeverityBgColor = (severity) => {
  const colors = {
    critical: 'rgba(139, 0, 0, 0.1)',
    high: 'rgba(198, 45, 66, 0.1)',
    medium: 'rgba(243, 156, 18, 0.1)',
    low: 'rgba(0, 168, 107, 0.1)',
    info: 'rgba(0, 112, 243, 0.1)',
  };
  return colors[severity?.toLowerCase()] || colors.info;
};

export const getMongoDBColor = (feature) => {
  return semanticColors.mongodb[feature] || semanticColors.mongodb.aggregation;
};

export const getPatternColor = (pattern) => {
  const patternLower = pattern?.toLowerCase().replace(/_/g, '');
  return semanticColors.patterns[patternLower] || semanticColors.patterns.none;
};

export const getEquipmentColor = (status) => {
  const statusLower = status?.toLowerCase();
  return semanticColors.equipment[statusLower] || semanticColors.equipment.offline;
};

export const getEquipmentBgColor = (status) => {
  const colors = {
    online: 'rgba(0, 237, 100, 0.1)',
    idle: 'rgba(149, 165, 166, 0.1)',
    warning: 'rgba(251, 177, 60, 0.1)',
    critical: 'rgba(225, 25, 0, 0.1)',
    maintenance: 'rgba(52, 152, 219, 0.1)',
    offline: 'rgba(44, 62, 80, 0.1)',
  };
  return colors[status?.toLowerCase()] || colors.offline;
};

export const getProcessColor = (status) => {
  const statusLower = status?.toLowerCase();
  if (statusLower === 'good' || statusLower === 'pass') {
    return { bg: semanticColors.process.good, text: semanticColors.process.goodText };
  } else if (statusLower === 'problematic' || statusLower === 'fail') {
    return { bg: semanticColors.process.problematic, text: semanticColors.process.problematicText };
  } else if (statusLower === 'warning') {
    return { bg: semanticColors.process.warning, text: semanticColors.process.warningText };
  } else {
    return { bg: semanticColors.process.unknown, text: semanticColors.process.unknownText };
  }
};

// Get contrasting text color for any background
export const getContrastText = (bgColor) => {
  // Simple contrast calculation
  const color = bgColor.replace('#', '');
  const r = parseInt(color.substr(0, 2), 16);
  const g = parseInt(color.substr(2, 2), 16);
  const b = parseInt(color.substr(4, 2), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? semanticColors.text.primary : semanticColors.text.inverse;
};

// Export default for convenience
export default semanticColors;