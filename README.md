# Agentic Yield Analytics for Semiconductor Manufacturing

A MongoDB-powered system for semiconductor manufacturing yield optimization that demonstrates real-time defect detection, AI-powered root cause analysis, and semantic search capabilities. The system reduces defect detection time from hours to seconds, addressing critical industry challenges where yield loss costs $50B+ annually.

## Features

- **Real-Time Monitoring** - MongoDB Change Streams monitor sensor data with automatic threshold detection and WebSocket-based live dashboard updates
- **AI-Powered Defect Detection** - Multimodal embeddings using Voyage AI to process wafer images and text descriptions with Atlas Vector Search for similar defect pattern matching
- **Intelligent Root Cause Analysis** - AI-generated RCA hints based on correlation patterns and semantic search across historical knowledge
- **Correlation Engine** - Links sensor anomalies to wafer defects over time, identifies problematic batches and recipes
- **Agentic AI Workflow** - LangGraph-orchestrated multi-step analysis with MongoDB-backed persistent memory and natural language interface

## Architecture

The system architecture integrates multiple components for real-time manufacturing intelligence:

![System Architecture](assets/architecture-diagram.png)

**Key Components:**

- **Machine Telemetry** - Sensor data streams from manufacturing equipment
- **Excursion Detection System** - Monitors thresholds and generates alerts
- **LangGraph Root Cause Agent** - Multi-step AI workflow for defect analysis with three main tools:
  - Query Wafer Defects (multimodal embeddings)
  - Query Historical Knowledge (semantic search)
  - Query Time Series Data (sensor correlation)
- **AWS Bedrock** - LLM inference for natural language analysis
- **Agentic Data Layer** - MongoDB Atlas storing:
  - Time Series telemetry data
  - Alerts and process context
  - Wafer defect images with embeddings
  - Historical reports and operation logs
  - Quality and material logs
  - Agent checkpoints and memory
- **Search Capabilities** - Vector Search, Hybrid Search, and Full Text Search powered by Voyage AI embeddings
- **Live Monitoring Dashboard** - Real-time visualization for operators

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB Atlas cluster
- AWS account with Bedrock access
- Voyage AI API key

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/your-org/smf-yield-defect-detection.git
   cd smf-yield-defect-detection
   ```

2. Backend Setup
   ```bash
   cd backend

   # Install UV package manager
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies
   uv sync

   # Configure environment
   cp .env.example .env
   # Edit .env with your credentials:
   # MONGODB_URI, MDB_DATABASE_NAME, VOYAGE_API_KEY,
   # AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
   ```

3. Frontend Setup
   ```bash
   cd frontend
   npm install
   ```

4. Initialize Database and Start Services
   ```bash
   cd backend

   # Start API server
   uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. Start Frontend (in a new terminal)
   ```bash
   cd frontend
   npm run dev
   ```

6. Access the Application
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

---