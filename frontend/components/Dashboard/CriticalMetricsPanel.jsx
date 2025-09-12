"use client";

import React, { useEffect, useRef, useState } from 'react';
import { Chart as ChartJS, registerables } from 'chart.js';
import Card from '@leafygreen-ui/card';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import styles from './CriticalMetricsPanel.module.css';

ChartJS.register(...registerables);

const MetricChart = ({ title, type, data, height = 150 }) => {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);
  
  useEffect(() => {
    if (!chartRef.current) return;
    
    if (chartInstance.current) {
      chartInstance.current.destroy();
    }
    
    const ctx = chartRef.current.getContext('2d');
    
    const getChartConfig = () => {
      switch(type) {
        case 'particle-monitor':
          return {
            type: 'line',
            data: {
              labels: data.labels || ['4h', '3h', '2h', '1h', 'Now'],
              datasets: [
                {
                  label: 'CMP-01',
                  data: data.cmp01 || [450, 520, 680, 950, 1250],
                  borderColor: '#e11900',
                  backgroundColor: 'rgba(225, 25, 0, 0.1)',
                  tension: 0.3,
                  borderWidth: 2
                },
                {
                  label: 'CMP-02',
                  data: data.cmp02 || [420, 440, 480, 620, 950],
                  borderColor: '#fbb13c',
                  backgroundColor: 'rgba(251, 177, 60, 0.1)',
                  tension: 0.3,
                  borderWidth: 2
                },
                {
                  label: 'CMP-03',
                  data: data.cmp03 || [380, 390, 400, 420, 450],
                  borderColor: '#00684a',
                  backgroundColor: 'rgba(0, 104, 74, 0.1)',
                  tension: 0.3,
                  borderWidth: 2
                },
                {
                  label: 'Threshold',
                  data: [1000, 1000, 1000, 1000, 1000],
                  borderColor: '#e11900',
                  borderDash: [5, 5],
                  borderWidth: 1,
                  fill: false,
                  pointRadius: 0
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  position: 'top',
                  labels: {
                    boxWidth: 12,
                    font: { size: 10 }
                  }
                },
                tooltip: {
                  mode: 'index',
                  intersect: false
                }
              },
              scales: {
                y: {
                  beginAtZero: true,
                  title: {
                    display: true,
                    text: 'Particles/cm³',
                    font: { size: 10 }
                  },
                  grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                  }
                },
                x: {
                  grid: {
                    display: false
                  }
                }
              }
            }
          };
          
        case 'process-stability':
          return {
            type: 'line',
            data: {
              labels: data.labels || ['4h', '3h', '2h', '1h', 'Now'],
              datasets: [
                {
                  label: 'RF Power (normalized)',
                  data: data.rfPower || [0, 0.2, 0.5, 0.8, 1.2],
                  borderColor: '#0884dc',
                  backgroundColor: 'rgba(8, 132, 220, 0.1)',
                  tension: 0.3,
                  borderWidth: 2
                },
                {
                  label: 'Temperature (normalized)',
                  data: data.temperature || [-0.2, 0, 0.3, 0.6, 0.9],
                  borderColor: '#00ed64',
                  backgroundColor: 'rgba(0, 237, 100, 0.1)',
                  tension: 0.3,
                  borderWidth: 2
                },
                {
                  label: 'Pressure (normalized)',
                  data: data.pressure || [0.1, 0.1, 0.2, 0.4, 0.7],
                  borderColor: '#fbb13c',
                  backgroundColor: 'rgba(251, 177, 60, 0.1)',
                  tension: 0.3,
                  borderWidth: 2
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  position: 'top',
                  labels: {
                    boxWidth: 12,
                    font: { size: 10 }
                  }
                },
                tooltip: {
                  mode: 'index',
                  intersect: false
                },
                annotation: {
                  annotations: {
                    upperBand: {
                      type: 'box',
                      yMin: 1,
                      yMax: 2,
                      backgroundColor: 'rgba(225, 25, 0, 0.05)'
                    },
                    lowerBand: {
                      type: 'box',
                      yMin: -2,
                      yMax: -1,
                      backgroundColor: 'rgba(225, 25, 0, 0.05)'
                    }
                  }
                }
              },
              scales: {
                y: {
                  min: -2,
                  max: 2,
                  title: {
                    display: true,
                    text: 'Deviation (σ)',
                    font: { size: 10 }
                  },
                  grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                  }
                },
                x: {
                  grid: {
                    display: false
                  }
                }
              }
            }
          };
          
        case 'batch-quality':
          return {
            type: 'bar',
            data: {
              labels: data.labels || ['SB-048', 'SB-049', 'SB-050', 'SB-051', 'SB-052'],
              datasets: [
                {
                  label: 'Quality Score',
                  data: data.scores || [95, 94, 78, 92, 96],
                  backgroundColor: (context) => {
                    const value = context.parsed.y;
                    if (value >= 95) return '#00ed64';
                    if (value >= 90) return '#fbb13c';
                    return '#e11900';
                  },
                  borderWidth: 0
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  display: false
                },
                tooltip: {
                  callbacks: {
                    label: (context) => `Score: ${context.parsed.y}%`
                  }
                }
              },
              scales: {
                y: {
                  beginAtZero: true,
                  max: 100,
                  title: {
                    display: true,
                    text: 'Quality %',
                    font: { size: 10 }
                  },
                  grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                  }
                },
                x: {
                  grid: {
                    display: false
                  }
                }
              }
            }
          };
          
        default:
          return null;
      }
    };
    
    const config = getChartConfig();
    if (config) {
      chartInstance.current = new ChartJS(ctx, config);
    }
    
    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [type, data]);
  
  return (
    <Card className={styles.metricCard}>
      <div className={styles.cardHeader}>
        <H3 className={styles.metricTitle}>{title}</H3>
      </div>
      <div className={styles.chartContainer} style={{ height }}>
        <canvas ref={chartRef} />
      </div>
    </Card>
  );
};

const CriticalMetricsPanel = () => {
  // Simulate real-time data updates
  const [metricsData, setMetricsData] = useState({
    particleData: {
      labels: ['4h ago', '3h ago', '2h ago', '1h ago', 'Now'],
      cmp01: [450, 520, 680, 950, 1250],
      cmp02: [420, 440, 480, 620, 950],
      cmp03: [380, 390, 400, 420, 450]
    },
    stabilityData: {
      labels: ['4h ago', '3h ago', '2h ago', '1h ago', 'Now'],
      rfPower: [0, 0.2, 0.5, 0.8, 1.2],
      temperature: [-0.2, 0, 0.3, 0.6, 0.9],
      pressure: [0.1, 0.1, 0.2, 0.4, 0.7]
    },
    batchData: {
      labels: ['SB-048', 'SB-049', 'SB-050', 'SB-051', 'SB-052'],
      scores: [95, 94, 78, 92, 96]
    }
  });
  
  return (
    <div className={styles.metricsPanel}>
      <MetricChart 
        title="Particle Count Monitor"
        type="particle-monitor"
        data={metricsData.particleData}
      />
      
      <MetricChart 
        title="Process Stability Tracker"
        type="process-stability"
        data={metricsData.stabilityData}
      />
      
      <MetricChart 
        title="Batch Quality Score"
        type="batch-quality"
        data={metricsData.batchData}
        height={120}
      />
    </div>
  );
};

export default CriticalMetricsPanel;