"use client";

import React from 'react';
import Link from 'next/link';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H1, H2, H3, Body, Description, Subtitle } from '@leafygreen-ui/typography';
import styles from './Homepage.module.css';

const HomepageClient = () => {
  return (
    <div className={styles.container}>
      {/* Hero Section */}
      <div className={styles.hero}>
        <Badge variant="green" className={styles.heroBadge}>
          <Icon glyph="Database" size="small" /> Powered by MongoDB Atlas
        </Badge>
        <H1 className={styles.heroTitle}>
          Yield Analytics & Quality Control
        </H1>
        <Subtitle className={styles.heroSubtitle}>
          Real-time semiconductor manufacturing monitoring powered by MongoDB Atlas
        </Subtitle>
        <Body className={styles.heroDescription}>
          Addressing a <strong>$50B+ annual industry challenge</strong> by reducing yield loss detection from <strong>hours to seconds</strong>
        </Body>
        <div className={styles.heroActions}>
          <Link href="/live-monitoring">
            <Button variant="primary" size="large" className={styles.ctaButton}>
              <Icon glyph="Charts" /> Enter Dashboard
            </Button>
          </Link>
          <Button variant="default" size="large" className={styles.secondaryButton}>
            <Icon glyph="Play" /> Watch Demo
          </Button>
        </div>

        {/* Stats Bar */}
        <div className={styles.statsBar}>
          <div className={styles.stat}>
            <div className={styles.statValue}>Real-Time</div>
            <div className={styles.statLabel}>Sensor Monitoring</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statValue}>AI-Powered</div>
            <div className={styles.statLabel}>Defect Detection</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statValue}>Vector Search</div>
            <div className={styles.statLabel}>Root Cause Analysis</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statValue}>&lt; 1s</div>
            <div className={styles.statLabel}>Detection Time</div>
          </div>
        </div>
      </div>

      {/* What This Demo Shows */}
      <section className={styles.section}>
        <H2 className={styles.sectionTitle}>What This Demo Shows</H2>
        <div className={styles.cardGrid}>
          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>📊</div>
              <H3 className={styles.cardTitle}>Real-Time Sensor Monitoring</H3>
              <Description className={styles.cardDescription}>
                Track sensor data across CMP, ETCH, and LITHO equipment with live updates every 8 seconds using MongoDB Time Series Collections
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>⚠️</div>
              <H3 className={styles.cardTitle}>Intelligent Alert Correlation</H3>
              <Description className={styles.cardDescription}>
                Automatic correlation of excursions with process context, identifying problematic materials and batches using Aggregation Pipelines
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>🎯</div>
              <H3 className={styles.cardTitle}>Wafer Defect Visualization</H3>
              <Description className={styles.cardDescription}>
                Visual defect maps with pattern recognition, identifying clusters and systematic issues across semiconductor wafers
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>🔧</div>
              <H3 className={styles.cardTitle}>Equipment Health Tracking</H3>
              <Description className={styles.cardDescription}>
                Real-time health monitoring with particle counts, RF power, and temperature metrics for all equipment using Change Streams
              </Description>
            </div>
          </Card>
        </div>
      </section>

      {/* How MongoDB Powers This */}
      <section className={styles.mongoSection}>
        <H2 className={styles.sectionTitle}>How MongoDB Powers This</H2>
        <Card className={styles.mongoCard}>
          <div className={styles.mongoFeatures}>
            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>🕐</span>
              <div>
                <strong>Time Series Collections</strong>
                <Description>Optimized storage for sensor data with 30-minute granularity and 90-day retention</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>🔍</span>
              <div>
                <strong>Vector Search</strong>
                <Description>Semantic root cause analysis using Voyage AI embeddings for intelligent pattern matching</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>🔄</span>
              <div>
                <strong>Change Streams</strong>
                <Description>Real-time alerts triggered on excursion detection without polling</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>📊</span>
              <div>
                <strong>Aggregation Pipelines</strong>
                <Description>Complex correlation analysis with $lookup joins for process context enrichment</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>💾</span>
              <div>
                <strong>Hybrid Storage</strong>
                <Description>Efficient storage with thumbnails in MongoDB and full wafer images in S3</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>🗄️</span>
              <div>
                <strong>Flexible Schema</strong>
                <Description>Adapts to diverse semiconductor manufacturing data without schema migrations</Description>
              </div>
            </div>
          </div>
        </Card>
      </section>

      {/* Demo Story */}
      <section className={styles.section}>
        <H2 className={styles.sectionTitle}>The Demo Story</H2>
        <Card className={styles.storyCard}>
          <Body className={styles.storyText}>
            This demo simulates a real semiconductor fab scenario where a CMP (Chemical Mechanical Polishing)
            tool experiences a particle spike above 1000 counts. The system instantly detects this excursion,
            correlates it with clustered defects on wafers, and traces it back to a problematic slurry batch.
            Using MongoDB's capabilities, the entire detection-to-diagnosis cycle happens in seconds instead of hours.
          </Body>
        </Card>
      </section>
    </div>
  );
};

export default HomepageClient;