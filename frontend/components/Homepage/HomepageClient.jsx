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
          Agentic Yield Analytics
        </H1>
        <Subtitle className={styles.heroSubtitle}>
          Real-time semiconductor manufacturing monitoring powered by MongoDB Atlas
        </Subtitle>
        <Body className={styles.heroDescription}>
          Addressing a <strong>$50B+ annual industry challenge</strong> by reducing yield loss detection time
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
            <div className={styles.statValue}>Multimodal AI</div>
            <div className={styles.statLabel}>Voyage AI Embeddings</div>
          </div>
        </div>
      </div>

      {/* What This Demo Shows */}
      <section className={styles.section}>
        <H2 className={styles.sectionTitle}>What This Demo Shows</H2>
        <div className={styles.cardGrid}>
          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>
                <Icon glyph="Charts" size="xlarge" />
              </div>
              <H3 className={styles.cardTitle}>Real-Time Sensor Monitoring</H3>
              <Description className={styles.cardDescription}>
                Track sensor data across CMP, ETCH, and LITHO equipment with live updates every 8 seconds using MongoDB Time Series Collections
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>
                <Icon glyph="Sparkle" size="xlarge" />
              </div>
              <H3 className={styles.cardTitle}>AI-Powered Root Cause Analysis</H3>
              <Description className={styles.cardDescription}>
                Interactive LangGraph AI agent analyzes alerts, queries historical knowledge using vector search, and provides actionable recommendations with conversation memory
              </Description>
            </div>
          </Card>

          <Card className={styles.featureCard}>
            <div className={styles.cardContent}>
              <div className={styles.cardIcon}>
                <Icon glyph="Visibility" size="xlarge" />
              </div>
              <H3 className={styles.cardTitle}>Wafer Defect Visualization</H3>
              <Description className={styles.cardDescription}>
                Query wafer images using Voyage AI Multimodal-3 embeddings and MongoDB Vector Search to find similar defect patterns across semiconductor wafers
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
              <span className={styles.mongoIcon}>
                <Icon glyph="Clock" size="large" />
              </span>
              <div>
                <strong>Time Series Collections</strong>
                <Description>Optimized storage for sensor data with automatic downsampling and TTL-based cleanup</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>
                <Icon glyph="Refresh" size="large" />
              </span>
              <div>
                <strong>Change Streams</strong>
                <Description>Real-time monitoring triggers alerts instantly when sensor data exceeds thresholds</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>
                <Icon glyph="ActivityFeed" size="large" />
              </span>
              <div>
                <strong>Aggregation Pipelines</strong>
                <Description>Complex multi-stage pipelines with $lookup joins for alert correlation and KPI calculations</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>
                <Icon glyph="MagnifyingGlass" size="large" />
              </span>
              <div>
                <strong>Vector Search + Voyage AI</strong>
                <Description>Semantic search using Voyage AI Multimodal-3 embeddings for image-based defect pattern matching</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>
                <Icon glyph="Folder" size="large" />
              </span>
              <div>
                <strong>Flexible Schema</strong>
                <Description>Schema-less design adapts to diverse manufacturing data without migrations</Description>
              </div>
            </div>

            <div className={styles.mongoFeature}>
              <span className={styles.mongoIcon}>
                <Icon glyph="Save" size="large" />
              </span>
              <div>
                <strong>LangGraph Checkpointing</strong>
                <Description>Persistent AI agent memory storage for multi-turn RCA conversations using MongoDB backend</Description>
              </div>
            </div>
          </div>
        </Card>
      </section>

    </div>
  );
};

export default HomepageClient;