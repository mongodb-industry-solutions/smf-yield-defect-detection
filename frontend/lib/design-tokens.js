/**
 * Design Tokens - MongoDB LeafyGreen UI
 * Centralized design system for SMF Yield Defect Detection
 */

import { palette } from '@leafygreen-ui/palette';
import { spacing } from '@leafygreen-ui/tokens';

// ========================================
// CORE COLOR SYSTEM
// ========================================

export const colors = {
  // MongoDB Primary Brand Colors
  primary: {
    dark3: palette.green.dark3,   // Headers, primary actions
    dark2: palette.green.dark2,   // Navigation background
    dark1: palette.green.dark1,   // Hover states
    base: palette.green.base,     // Primary brand color
    light1: palette.green.light1, // Subtle highlights
    light2: palette.green.light2, // Success backgrounds
    light3: palette.green.light3, // Section backgrounds
  },

  // Risk-Based Semantic Colors (SMF-specific)
  risk: {
    critical: palette.red.dark2,    // 90+ risk score, critical alerts
    high: palette.red.base,         // 70-89 risk score, high severity
    medium: palette.yellow.base,    // 40-69 risk score, warnings
    low: palette.green.base,        // <40 risk score, normal operation
  },

  // Status Colors (Equipment & Process)
  status: {
    good: palette.green.dark2,       // Normal operation
    warning: palette.yellow.base,    // Warning state
    critical: palette.red.base,      // Critical/excursion state
    unknown: palette.gray.base,      // Unknown/offline
  },

  // MongoDB Feature-Specific Accents
  features: {
    atlas: palette.blue.base,        // Text search
    vector: palette.purple.base,     // Vector search
    hybrid: palette.green.base,      // Combined search
    graph: palette.blue.dark1,       // Network visualization
    timeSeries: palette.blue.light1, // Time series data
  },

  // Neutral Colors
  neutral: {
    dark3: palette.gray.dark3,       // Darkest gray, footers
    dark2: palette.gray.dark2,       // Very dark gray
    dark1: palette.gray.dark1,       // Darker gray, secondary text
    base: palette.gray.base,         // Base gray
    light1: palette.gray.light1,     // Light gray
    light2: palette.gray.light2,     // Lighter gray, backgrounds
    light3: palette.gray.light3,     // Lightest gray, text on dark
  },

  // Semantic UI Colors
  success: palette.green.light2,
  error: palette.red.light2,
  info: palette.blue.light2,
  warningBg: palette.yellow.light2,
};

// ========================================
// TYPOGRAPHY SYSTEM
// ========================================

export const typography = {
  // Text Colors
  text: {
    primary: palette.gray.dark3,
    secondary: palette.gray.dark1,
    disabled: palette.gray.base,
    inverse: palette.gray.light3,  // Text on dark backgrounds
    link: palette.blue.dark1,
    success: palette.green.dark2,
    warning: palette.yellow.dark2,
    error: palette.red.base,
  },

  // Font Families (LeafyGreen defaults)
  fonts: {
    primary: '"Euclid Circular A", "Helvetica Neue", Helvetica, Arial, sans-serif',
    mono: '"Source Code Pro", "Courier New", monospace',
    serif: '"MongoDB Value Serif", Georgia, serif',
  },

  // Font Weights
  weights: {
    light: 300,
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },

  // Font Sizes
  sizes: {
    xs: '12px',
    sm: '13px',
    base: '14px',
    md: '16px',
    lg: '18px',
    xl: '24px',
    xxl: '32px',
    xxxl: '48px',
  },
};

// ========================================
// SPACING SYSTEM
// ========================================

export { spacing };

// Convenience spacing scale
export const space = {
  xs: spacing[1],      // 4px
  sm: spacing[2],      // 8px
  md: spacing[3],      // 16px
  lg: spacing[4],      // 32px
  xl: spacing[5],      // 64px
  xxl: spacing[6],     // 88px (if available)
};

// ========================================
// LAYOUT & SIZING
// ========================================

export const layout = {
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },

  shadows: {
    sm: '0 2px 6px rgba(0, 0, 0, 0.08)',
    md: '0 4px 12px rgba(0, 0, 0, 0.12)',
    lg: '0 8px 24px rgba(0, 0, 0, 0.16)',
    xl: '0 12px 48px rgba(0, 0, 0, 0.20)',
  },

  elevation: {
    flat: '0',
    raised: '1',
    overlay: '2',
    modal: '3',
    popover: '4',
  },
};

// ========================================
// ANIMATIONS
// ========================================

export const animations = {
  duration: {
    fast: '150ms',
    normal: '200ms',
    slow: '300ms',
    slower: '500ms',
  },

  easing: {
    standard: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
    decelerate: 'cubic-bezier(0.0, 0.0, 0.2, 1)',
    accelerate: 'cubic-bezier(0.4, 0.0, 1, 1)',
    sharp: 'cubic-bezier(0.4, 0.0, 0.6, 1)',
  },
};

// ========================================
// HELPER FUNCTIONS
// ========================================

/**
 * Get severity color based on severity level
 * @param {string} severity - critical, high, medium, low, warning, info
 * @returns {string} Hex color code
 */
export const getSeverityColor = (severity) => {
  const level = severity?.toLowerCase();
  switch (level) {
    case 'critical':
      return colors.risk.critical;
    case 'high':
      return colors.risk.high;
    case 'warning':
    case 'medium':
      return colors.risk.medium;
    case 'low':
    case 'info':
      return colors.risk.low;
    default:
      return colors.neutral.base;
  }
};

/**
 * Get Badge variant based on severity
 * @param {string} severity - critical, high, medium, low, warning, info
 * @returns {string} LeafyGreen Badge variant
 */
export const getSeverityVariant = (severity) => {
  const level = severity?.toLowerCase();
  switch (level) {
    case 'critical':
    case 'high':
      return 'red';
    case 'warning':
    case 'medium':
      return 'yellow';
    case 'low':
      return 'green';
    case 'info':
      return 'blue';
    default:
      return 'lightgray';
  }
};

/**
 * Get status color for equipment
 * @param {string} status - good, warning, critical, unknown
 * @returns {string} Hex color code
 */
export const getStatusColor = (status) => {
  const state = status?.toLowerCase();
  switch (state) {
    case 'good':
    case 'normal':
      return colors.status.good;
    case 'warning':
    case 'caution':
      return colors.status.warning;
    case 'critical':
    case 'excursion':
      return colors.status.critical;
    default:
      return colors.status.unknown;
  }
};

/**
 * Get metric threshold color
 * @param {number} value - Current value
 * @param {object} thresholds - { good: number, warning: number }
 * @returns {string} Hex color code
 */
export const getMetricColor = (value, thresholds) => {
  if (!thresholds) return colors.primary.dark2;
  if (value >= thresholds.good) return colors.status.good;
  if (value >= thresholds.warning) return colors.status.warning;
  return colors.status.critical;
};

// ========================================
// GLASSMORPHISM STYLES
// ========================================

export const glassMorphism = {
  light: {
    background: 'rgba(255, 255, 255, 0.7)',
    backdropFilter: 'blur(10px)',
    border: '1px solid rgba(255, 255, 255, 0.18)',
  },
  dark: {
    background: 'rgba(30, 45, 61, 0.8)',
    backdropFilter: 'blur(10px)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
  },
};

// ========================================
// EXPORTS
// ========================================

export default {
  colors,
  typography,
  spacing,
  space,
  layout,
  animations,
  getSeverityColor,
  getSeverityVariant,
  getStatusColor,
  getMetricColor,
  glassMorphism,
};
