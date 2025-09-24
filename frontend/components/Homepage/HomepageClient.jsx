"use client";

import React from 'react';
import Link from 'next/link';
import Card from '@leafygreen-ui/card';
import Button from '@leafygreen-ui/button';
import { H1, H2, H3, Body, Description } from '@leafygreen-ui/typography';
import styles from './Homepage.module.css';

const HomepageClient = () => {
  return (
    <div className={styles.container}>
      {/* Hero Section */}
      <div className={styles.hero}>
        <H1 className={styles.heroTitle}>
          SMF Yield Defect Detection System
        </H1>
        <Description className={styles.heroSubtitle}>
          Real-time semiconductor manufacturing monitoring powered by MongoDB
        </Description>
        <Body className={styles.heroDescription}>
          Addressing a $50B+ annual industry challenge by reducing yield loss detection from hours to seconds
        </Body>
        <Link href="/live-monitoring">
          <Button variant="primary" size="large" className={styles.ctaButton}>
            Enter Live Monitoring Dashboard
          </Button>
        </Link>
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
                Track 5,764+ sensor data points across CMP, ETCH, and LITHO equipment with live updates every 8 seconds
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>⚠️</div>
              <H3 className={styles.cardTitle}>Intelligent Alert Correlation</H3>
              <Description className={styles.cardDescription}>
                Automatic correlation of excursions with process context, identifying problematic materials and batches
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>🎯</div>
              <H3 className={styles.cardTitle}>Wafer Defect Visualization</H3>
              <Description className={styles.cardDescription}>
                Visual defect maps with pattern recognition across 100+ wafers, identifying clusters and systematic issues
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>🔧</div>
              <H3 className={styles.cardTitle}>Equipment Health Tracking</H3>
              <Description className={styles.cardDescription}>
                Real-time health monitoring with particle counts, RF power, and temperature metrics for all equipment
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
                <Description>5,764 sensor records with 30-minute granularity and 90-day retention</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>🔍</span>
              <div>
                <strong>Vector Search</strong>
                <Description>191 embeddings for semantic root cause analysis using Voyage AI</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>🔄</span>
              <div>
                <strong>Change Streams</strong>
                <Description>Real-time alerts triggered on excursion detection</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>📊</span>
              <div>
                <strong>Aggregation Pipelines</strong>
                <Description>Complex correlation analysis with $lookup for process context</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>💾</span>
              <div>
                <strong>Hybrid Storage</strong>
                <Description>Thumbnails in MongoDB, full wafer images in S3</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>🗄️</span>
              <div>
                <strong>Flexible Schema</strong>
                <Description>Adapts to diverse semiconductor data without migrations</Description>
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