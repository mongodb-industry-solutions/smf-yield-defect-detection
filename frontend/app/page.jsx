"use client";

import { useState, useEffect } from "react";
import Button from "@leafygreen-ui/button";
import Card from "@leafygreen-ui/card";
import ReactMarkdown from "react-markdown";

import {
  H1,
  H3,
  H2,
  Body,
  Subtitle,
  Description,
  Link,
  Label,
} from "@leafygreen-ui/typography";
import Code from "@leafygreen-ui/code";
import InfoWizard from "@/components/InfoWizard/InfoWizard";
import TextInput from "@leafygreen-ui/text-input";
import { agenticPageTalkTrack } from "@/lib/talkTrack";

export default function HomePage() {
  const [selectedOption, setSelectedOption] = useState("new"); // "new", "resume", or "list"
  const [query, setQuery] = useState(`${process.env.NEXT_PUBLIC_INITIAL_QUERY}`);
  const [threadId, setThreadId] = useState("");
  const [workflow, setWorkflow] = useState(null);
  const [sessions, setSessions] = useState(null);
  const [runDocuments, setRunDocuments] = useState(null); // Documents for current run
  const [loading, setLoading] = useState(false);
  const [openHelpModal, setOpenHelpModal] = useState(false);

  // Clear old data when view changes
  const handleViewChange = (view) => {
    setSelectedOption(view);
    setWorkflow(null);
    setThreadId("");
    setSessions(null);
    setRunDocuments(null);
  };

  // Run agent via normal API call
  const runAgent = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/run-agent?query_reported=${encodeURIComponent(query)}`);
      const text = await res.text(); // Read raw response as text
      console.log("Raw Response:", text);
      const data = JSON.parse(text); // Parse JSON if valid
      setWorkflow(data);
    } catch (err) {
      console.error("Error running agent:", err);
    }
    setLoading(false);
  };

  // Resume agent using API call
  const resumeAgent = async () => {
    if (!threadId) return;
    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/resume-agent?thread_id=${encodeURIComponent(threadId)}`);
      const data = await res.json();
      setWorkflow(data);
    } catch (err) {
      console.error("Error resuming agent:", err);
    }
    setLoading(false);
  };

  // Get sessions for "list" view
  const getSessions = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/get-sessions`);
      const data = await res.json();
      setSessions(data);
    } catch (err) {
      console.error("Error fetching sessions:", err);
    }
  };

  // Fetch run documents once workflow is complete and has a thread_id.
  useEffect(() => {
    if (workflow && workflow.thread_id) {
      const fetchRunDocs = async () => {
        try {
          const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/get-run-documents?thread_id=${encodeURIComponent(workflow.thread_id)}`);
          const data = await res.json();
          setRunDocuments(data);
        } catch (err) {
          console.error("Error fetching run documents:", err);
        }
      };
      fetchRunDocs();
    }
  }, [workflow]);

  // when view is "list", fetch sessions.
  useEffect(() => {
    if (selectedOption === "list") {
      getSessions();
    }
  }, [selectedOption]);

  return (
    <div style={{ position: "relative", width: "100%", minHeight: "100vh" }}>

      <div
        style={{
          position: "absolute",
          top: "20px",
          right: "20px",
          zIndex: 9999,
        }}
      >
        <div className="infowizard-container">
          <InfoWizard
            open={openHelpModal}
            setOpen={setOpenHelpModal}
            tooltipText="Tell me more!"
            iconGlyph="Wizard"
            sections={agenticPageTalkTrack}
          />
        </div>
      </div>
      <div style={{ padding: "20px", fontFamily: "Arial, sans-serif", width: "100%" }}>

        <div style={{ marginLeft: "30px" }}>
          <H1 style={{ marginBottom: "5px" }}>Agentic Framework</H1>
          <Body style={{ width: "50%" }}>The Agentic Framework serves as a versatile AI-driven recommendation assistant capable of comprehending your data, performing a multi-step diagnostic workflow using <b>LangGraph</b>, and generating actionable recommendations. </Body>
          <Body style={{ width: "50%", paddingTop: "15px" }}> The backend reads timeseries data from a CSV file or MongoDB, generates text embeddings using the <b>Cohere English V3 model</b>, performs vector searches to identify similar past queries using <b>MongoDB Atlas Vector Search</b>, persists session and run data, and finally generates a diagnostic recommendation. <b>MongoDB</b> stores agent profiles, historical recommendations, timeseries data, session logs, and more.</Body>
          <Body style={{ width: "50%", paddingTop: "15px" }}> This persistent storage not only logs every step of the diagnostic process for traceability but also enables efficient querying and reusability of past data.</Body>

          <H3 style={{ marginBottom: "20px", marginTop: "20px" }}>Please choose one of the following options</H3>

          {/* Option Buttons */}
          <div style={{ marginBottom: "20px" }}>
            <Button onClick={() => handleViewChange("new")} style={{ marginRight: "10px" }} variant="default">
              New Diagnosis
            </Button>

            <Button onClick={() => handleViewChange("resume")} style={{ marginRight: "10px" }} variant="default">
              Resume Diagnosis
            </Button>
            <Button onClick={() => handleViewChange("list")} variant="default">
              List Sessions
            </Button>
          </div>

        </div>

        <div style={{ display: "flex", width: "100%" }}>
          {/* Left Column: Agent Workflow Output */}
          <div style={{ flex: 1, maxWidth: "50%", padding: "20px", borderRight: "1px solid #ccc", overflowX: "auto", marginLeft: "10px" }}>
            {selectedOption === "new" && (
              <>
                <Subtitle style={{ marginBottom: "10px" }}>New Diagnosis</Subtitle>

                <TextInput
                  label="Query Reported"
                  placeholder="Undefined"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}

                />

                {/**
                <Label style={{ display: "block", marginTop: "10px" }}>
                  Query Reported
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    style={{ width: "100%", padding: "8px", marginTop: "6px" }}
                  />
                </Label>
                 */}

                <Button onClick={runAgent} disabled={loading} variant="baseGreen" style={{ marginTop: "20px", padding: "8px 12px" }}>
                  Run Agent
                </Button>
              </>
            )}

            {selectedOption === "resume" && (
              <>
                <Subtitle style={{ marginBottom: "10px" }}>Resume Diagnosis</Subtitle>

                <TextInput
                  label="Thread ID"
                  placeholder="Input Thread ID"
                  value={threadId}
                  onChange={(e) => setThreadId(e.target.value)}
                />

                {/**
                <Label style={{ display: "block", marginTop: "10px" }}>
                  Thread ID:
                  <input
                    type="text"
                    value={threadId}
                    onChange={(e) => setThreadId(e.target.value)}
                    style={{ width: "100%", padding: "8px", marginTop: "6px" }}
                  />
                </Label>

                 */}
                <Button onClick={resumeAgent} disabled={loading} variant="baseGreen" style={{ marginTop: "20px", padding: "8px 12px" }}>
                  Resume Agent
                </Button>
              </>
            )}

            {(selectedOption === "new" || selectedOption === "resume") && (
              <>
                {loading && <Body style={{ fontStyle: "italic", marginTop: "10px" }}>Processing... The agent is thinking...</Body>}
                {workflow && (
                  <div style={{ marginTop: "20px" }}>
                    <Subtitle>Agent Workflow</Subtitle>
                    {workflow.updates && workflow.updates.length > 0 ? (
                      <ul style={{ background: "#E3FCF7", padding: "10px", borderRadius: "20px" }}>
                        {workflow.updates.map((msg, idx) => (
                          <li key={idx} style={{ marginBottom: "6px", marginLeft: "10px" }}>
                            <Body>{msg}</Body>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <Body>No updates available.</Body>
                    )}
                    {workflow.chain_of_thought && (
                      <>
                        <Subtitle style={{ marginTop: "20px" }}>Chain-of-Thought</Subtitle>
                        <Card>
                          <ReactMarkdown>{workflow.chain_of_thought}</ReactMarkdown>
                        </Card>
                      </>
                    )}
                    {workflow.recommendation_text && (
                      <div style={{ marginTop: "30px" }}>
                        <Subtitle>Final Recommendation</Subtitle>
                        <Card style={{ background: "#F9EBFF" }}>
                          <ReactMarkdown>{workflow.recommendation_text}</ReactMarkdown>
                        </Card>

                        {workflow.thread_id && <Body style={{ marginTop: "20px" }}>Thread ID: {workflow.thread_id}</Body>}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Right Column: Documents */}
          <div style={{ flex: 1, maxWidth: "50%", padding: "20px", overflowX: "auto" }}>
            {selectedOption === "list" ? (
              <>
                <Subtitle>Session Documents</Subtitle>
                {sessions ? (
                  sessions.length > 0 ? (
                    sessions.map((doc, index) => (
                      <div
                        key={index}
                        style={{
                          border: "1px solid #ddd",
                          padding: "15px",
                          marginBottom: "15px",
                          borderRadius: "4px",
                        }}
                      >
                        <Label>Session Document #{index + 1}</Label>
                        <Code language="js" style={{ overflowWrap: "break-word", whiteSpace: "pre-wrap" }}>
                          {JSON.stringify(doc, null, 2)}
                        </Code>
                      </div>
                    ))
                  ) : (
                    <Body>No sessions found.</Body>
                  )
                ) : (
                  <Body>Loading sessions...</Body>
                )}
              </>
            ) : (
              <>
                <Subtitle>Agent Run Documents</Subtitle>
                {workflow && workflow.thread_id ? (
                  runDocuments ? (
                    Object.entries(runDocuments).map(([collection, doc], index) => (
                      <div
                        key={index}
                        style={{
                          border: "1px solid #ddd",
                          padding: "15px",
                          marginBottom: "15px",
                          borderRadius: "4px",
                        }}
                      >
                        <Label>{collection}</Label>
                        <Code language="js" style={{ overflowWrap: "break-word", whiteSpace: "pre-wrap" }}>
                          {JSON.stringify(doc, null, 2)}
                        </Code>
                      </div>
                    ))
                  ) : (
                    <Body>Loading run documents...</Body>
                  )
                ) : (
                  <Body>Run an agent to see inserted documents.</Body>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}