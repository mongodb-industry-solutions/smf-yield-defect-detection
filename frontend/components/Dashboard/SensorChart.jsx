"use client";

import React, { useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import Card from '@leafygreen-ui/card';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import { appPalette } from '@/lib/palette';
import { useWebSocket } from '@/lib/websocket';
import styles from './SensorChart.module.css';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const SensorChart = ({ 
  metric = 'particle_count',
  title = 'Particle Count',
  threshold = 1000,
  unit = 'particles/cm³',
  equipment = 'CMP-01'
}) => {
  const { sensorData, isConnected } = useWebSocket();
  const [chartData, setChartData] = useState({
    labels: [],
    datasets: []
  });

  useEffect(() => {
    // Filter data for this equipment and metric
    const relevantData = sensorData
      .filter(d => d.equipment === equipment)
      .slice(-20); // Last 20 points

    const labels = relevantData.map(d => {
      const date = new Date(d.timestamp);
      return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
      });
    });

    const values = relevantData.map(d => d.metrics[metric] || 0);
    const thresholdLine = new Array(labels.length).fill(threshold);

    // Determine if we're in alert state
    const latestValue = values[values.length - 1];
    const isAlert = latestValue > threshold;

    setChartData({
      labels,
      datasets: [
        {
          label: title,
          data: values,
          borderColor: isAlert ? appPalette.status.critical : appPalette.status.success,
          backgroundColor: isAlert 
            ? 'rgba(234, 57, 67, 0.1)' 
            : 'rgba(0, 104, 74, 0.1)',
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 5,
        },
        {
          label: 'Threshold',
          data: thresholdLine,
          borderColor: appPalette.status.warning,
          borderDash: [5, 5],
          borderWidth: 1,
          fill: false,
          pointRadius: 0,
          pointHoverRadius: 0,
        }
      ]
    });
  }, [sensorData, metric, title, threshold, equipment]);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          usePointStyle: true,
          padding: 15,
          font: {
            size: 12,
            family: 'Akzidenz, -apple-system, sans-serif'
          }
        }
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        padding: 12,
        titleFont: {
          size: 13,
          weight: 'bold'
        },
        bodyFont: {
          size: 12
        },
        callbacks: {
          label: (context) => {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += context.parsed.y.toFixed(1) + ' ' + unit;
            }
            return label;
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        grid: {
          display: false
        },
        ticks: {
          maxTicksLimit: 6,
          font: {
            size: 11
          }
        }
      },
      y: {
        display: true,
        grid: {
          color: 'rgba(0, 0, 0, 0.05)'
        },
        ticks: {
          font: {
            size: 11
          },
          callback: function(value) {
            return value.toFixed(0);
          }
        }
      }
    },
    animation: {
      duration: 300
    }
  };

  const latestValue = sensorData
    .filter(d => d.equipment === equipment)
    .slice(-1)[0]?.metrics[metric] || 0;
  
  const isAlert = latestValue > threshold;

  return (
    <Card className={styles.chartCard}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <Icon 
            glyph={isAlert ? "Warning" : "Charts"} 
            size="large" 
            fill={isAlert ? appPalette.status.critical : appPalette.status.info}
          />
          <div>
            <H3 className={styles.title}>{title}</H3>
            <Description>{equipment}</Description>
          </div>
        </div>
        
        <div className={styles.status}>
          <div className={styles.connectionStatus}>
            <div className={`${styles.statusDot} ${isConnected ? styles.connected : styles.disconnected}`} />
            <Description>{isConnected ? 'Live' : 'Offline'}</Description>
          </div>
          
          <div className={styles.currentValue}>
            <Body weight="medium" className={isAlert ? styles.alertValue : styles.normalValue}>
              {latestValue.toFixed(1)}
            </Body>
            <Description>{unit}</Description>
          </div>
        </div>
      </div>
      
      <div className={styles.chartContainer}>
        {chartData.labels.length > 0 ? (
          <Line data={chartData} options={options} />
        ) : (
          <div className={styles.noData}>
            <Icon glyph="Clock" size="large" fill={appPalette.text.secondary} />
            <Description>Waiting for data...</Description>
          </div>
        )}
      </div>
      
      {isAlert && (
        <div className={styles.alertBar}>
          <Icon glyph="Warning" size="small" fill={appPalette.white} />
          <Body className={styles.alertText}>
            Threshold exceeded: {latestValue.toFixed(1)} {unit} (limit: {threshold})
          </Body>
        </div>
      )}
    </Card>
  );
};

export default SensorChart;