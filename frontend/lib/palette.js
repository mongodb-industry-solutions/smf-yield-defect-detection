import { palette } from '@leafygreen-ui/palette';

export const appPalette = {
  // Status colors for different states
  status: {
    success: palette.green.dark2,
    critical: palette.red.base,
    warning: palette.yellow.base,
    info: palette.blue.base,
    ai: palette.purple.base,
    neutral: palette.gray.base
  },
  
  // Background colors
  backgrounds: {
    main: palette.green.light3,
    card: 'white',
    header: palette.green.dark3,
    section: palette.gray.light3,
    alert: palette.red.light2,
    warning: palette.yellow.light2,
    success: palette.green.light2,
    info: palette.blue.light2
  },
  
  // Text colors
  text: {
    primary: palette.gray.dark3,
    secondary: palette.gray.dark1,
    light: palette.gray.light3,
    success: palette.green.dark2,
    error: palette.red.dark2,
    warning: palette.yellow.dark2,
    link: palette.blue.dark1
  },
  
  // KPI card color variants
  kpi: {
    good: { 
      bg: palette.green.light2, 
      text: palette.green.dark2,
      border: palette.green.base
    },
    warning: { 
      bg: palette.yellow.light2, 
      text: palette.yellow.dark2,
      border: palette.yellow.base
    },
    critical: { 
      bg: palette.red.light2, 
      text: palette.red.dark2,
      border: palette.red.base
    },
    info: {
      bg: palette.blue.light2,
      text: palette.blue.dark2,
      border: palette.blue.base
    }
  },
  
  // Chart colors for data visualization
  charts: {
    primary: palette.green.base,
    secondary: palette.blue.base,
    tertiary: palette.purple.base,
    warning: palette.yellow.base,
    danger: palette.red.base,
    neutral: palette.gray.base
  }
};

// Helper function to get KPI variant based on value and thresholds
export const getKPIVariant = (value, thresholds) => {
  if (!thresholds) return 'info';
  
  const { critical, warning, good } = thresholds;
  
  if (good && value >= good) return 'good';
  if (critical && value <= critical) return 'critical';
  if (warning && value <= warning) return 'warning';
  
  return 'info';
};

// Helper function for trend colors
export const getTrendColor = (trend) => {
  switch(trend) {
    case 'up': return palette.green.base;
    case 'down': return palette.red.base;
    case 'stable': return palette.gray.base;
    default: return palette.gray.base;
  }
};