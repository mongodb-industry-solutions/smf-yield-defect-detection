"use client";

import React, { useState } from "react";
import { H2, Subtitle, Body } from "@leafygreen-ui/typography";
import { Tabs, Tab } from "@leafygreen-ui/tabs";
import Icon from "@leafygreen-ui/icon";
import styles from "./page.module.css";

const sections = [
  {
    heading: "Overview",
    content: [
      {
        heading: "The Challenge",
        body: "Yield issues remain one of the largest cost drivers in semiconductor manufacturing. Traditional monitoring detects problems hours or days late, and manual root cause analysis is slow, inconsistent, and hampered by siloed data.",
      },
      {
        heading: "What This Demo Shows",
        body: [
          "Real-time sensor monitoring with instant anomaly alerts",
          "AI-powered root cause analysis using vector search",
          "Multimodal defect matching with Voyage AI embeddings",
          "Unified data layer for time-series, vectors, and documents",
        ],
      },
      {
        image: {
          src: "/architecture-diagram.png",
          alt: "Architecture Diagram",
          width: 700,
        },
      },
    ],
  },
  {
    heading: "Architecture",
    content: [
      {
        heading: "Solution Architecture",
        body: "MongoDB Atlas serves as the unified data layer — storing time-series telemetry, vector embeddings, and operational documents in one platform. Change Streams push real-time alerts to the frontend, while LangGraph agents query the knowledge base for autonomous root cause analysis.",
      },
      {
        image: {
          src: "/solution-architecture.png",
          alt: "Solution Architecture Diagram",
          width: 700,
        },
      },
      {
        heading: "Data Flow",
        body: [
          "Machine telemetry streams into MongoDB Time Series Collections",
          "Excursion Detection System monitors thresholds and pushes alerts to MongoDB",
          "LangGraph Root Cause Agent queries wafer defects, historical knowledge, and time-series data",
          "AWS Bedrock provides LLM inference for autonomous analysis",
          "Agent memory and checkpoints persist in MongoDB for conversation continuity",
        ],
      },
      {
        heading: "MongoDB Capabilities Used",
        body: [
          "Vector Search & Hybrid Search for semantic pattern matching",
          "Aggregation Framework for complex data transformations",
          "Voyage AI multimodal embeddings for defect images and manuals",
          "Full Text Search across operation logs and reports",
        ],
      },
    ],
  },
  {
    heading: "Why MongoDB?",
    content: [
      {
        heading: "Unified Agentic Data Layer",
        body: [
          "One platform for time-series telemetry, vector embeddings, and documents",
          "No ETL pipelines between siloed databases",
          "AI agents query all data types with a single connection",
          "Agent memory and checkpoints persist for audit and resume",
        ],
      },
      {
        heading: "Real-Time Excursion Detection",
        body: [
          "Change Streams push threshold violations to the frontend in near real-time",
          "Time Series Collections handle high-frequency sensor ingestion at scale",
          "Push-based alerts trigger autonomous agent investigation without polling",
        ],
      },
      {
        heading: "Multimodal Defect Search",
        body: [
          "Vector Search finds similar defects using image + text embeddings",
          "Discover patterns regardless of how defects were originally described",
          "Voyage AI multimodal embeddings capture visual and textual context",
        ],
      },
      {
        heading: "Production-Ready at Scale",
        body: [
          "Time Series Collections optimized for high-volume sensor data ingestion",
          "Flexible document model adapts to diverse manufacturing data",
          "Built-in replication and sharding for high availability",
        ],
      },
    ],
  },
];

export default function DocumentationPage() {
  const [selected, setSelected] = useState(0);
  const [enlargedImage, setEnlargedImage] = useState(null);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <H2>Documentation</H2>
        <Body className={styles.subtitle}>
          Learn about the architecture, capabilities, and how to demo this application.
        </Body>
      </div>

      <div className={styles.content}>
        <Tabs aria-label="documentation tabs" setSelected={setSelected} selected={selected}>
          {sections.map((tab, tabIndex) => (
            <Tab key={tabIndex} name={tab.heading}>
              <div className={styles.tabContent}>
                {tab.content.map((section, sectionIndex) => (
                  <div key={sectionIndex} className={styles.section}>
                    {section.heading && (
                      <Subtitle className={styles.sectionHeading}>{section.heading}</Subtitle>
                    )}
                    {section.body && Array.isArray(section.body) ? (
                      <ul className={styles.list}>
                        {section.body.map((item, idx) =>
                          typeof item === "object" ? (
                            <li key={idx}>
                              {item.heading}
                              <ul className={styles.list}>
                                {item.body.map((subItem, subIdx) => (
                                  <li key={subIdx}>
                                    <Body>{subItem}</Body>
                                  </li>
                                ))}
                              </ul>
                            </li>
                          ) : (
                            <li key={idx}>
                              <Body>{item}</Body>
                            </li>
                          )
                        )}
                      </ul>
                    ) : section.body ? (
                      <Body>{section.body}</Body>
                    ) : null}

                    {section.image && (
                      <div
                        className={styles.imageContainer}
                        onClick={() => setEnlargedImage(section.image)}
                      >
                        <img
                          src={section.image.src}
                          alt={section.image.alt}
                          width={section.image.width || 550}
                          className={styles.image}
                        />
                        <div className={styles.zoomOverlay}>
                          <Icon glyph="FullScreenEnter" size="large" />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Tab>
          ))}
        </Tabs>
      </div>

      {/* Lightbox for enlarged images */}
      {enlargedImage && (
        <div className={styles.lightbox} onClick={() => setEnlargedImage(null)}>
          <div className={styles.lightboxContent} onClick={(e) => e.stopPropagation()}>
            <button
              className={styles.lightboxClose}
              onClick={() => setEnlargedImage(null)}
              aria-label="Close enlarged image"
            >
              <Icon glyph="X" size="large" />
            </button>
            <img
              src={enlargedImage.src}
              alt={enlargedImage.alt}
              className={styles.lightboxImage}
            />
          </div>
        </div>
      )}
    </div>
  );
}
