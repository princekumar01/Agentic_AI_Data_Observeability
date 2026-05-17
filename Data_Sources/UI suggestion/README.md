# 🏥 Clinical Trial AI Data Observability Platform

### Modern AI Operations Command Center — UI/UX Design Specification

Hosted Prototype: https://clad-stylus-62805487.figma.site/

---

# 🎨 Design System

## Theme & Visual Language

The platform follows a modern enterprise AI observability aesthetic inspired by:

* Linear
* Datadog
* Vercel Analytics
* Azure AI Studio

The design shifts away from traditional Streamlit dashboard layouts toward a workspace-oriented AI Operations Command Center experience.

---

## Color Palette

### Backgrounds

| Element          | Color                    |
| ---------------- | ------------------------ |
| Main Background  | `#0B1020`                |
| Surface          | `#111827`                |
| Elevated Surface | `#172033`                |
| Glass Panels     | `rgba(255,255,255,0.04)` |

### Accent Colors

| Purpose       | Color     |
| ------------- | --------- |
| AI Blue       | `#4F8CFF` |
| Success Green | `#10B981` |
| Warning Amber | `#F59E0B` |
| Error Red     | `#EF4444` |
| Violet Accent | `#8B5CF6` |

### Typography Colors

| Type           | Color     |
| -------------- | --------- |
| Primary Text   | `#F8FAFC` |
| Secondary Text | `#94A3B8` |
| Muted Text     | `#64748B` |

---

## Typography

* Font Family: **Inter**
* Modern enterprise typography hierarchy
* Large metric-focused headings
* Compact observability labels
* Clean dashboard readability

---

## Motion & Animation

Animations are implemented using:

* Framer Motion
* Smooth hover transitions
* Fade-up section reveals
* Animated status pulses
* Live streaming indicators
* Progress transitions
* Confetti approval animation

---

# 🧭 Layout & Navigation

## Navigation Rail

The application uses a collapsible left-side navigation rail instead of a traditional sidebar.

### Features

* Workspace-style navigation
* Active run status indicator
* Animated status glow
* FDA compliance badge
* Real-time workflow visibility

### Navigation Sections

* Home
* Pipeline
* Review
* Dashboard
* Audit Trail

---

## Workspace Layout

The platform replaces vertically stacked layouts with:

* Split-panel workspaces
* Sticky insight rails
* Floating control surfaces
* Interactive data regions
* Grid-based information density

---

# 🏠 Landing Page (Home)

## Hero Section

The landing experience introduces the platform as a modern AI observability command center.

### Features

* Animated gradient background
* Enterprise AI visual identity
* Dynamic motion effects
* Large observability-focused hero text

---

## Live System Metrics

Real-time operational statistics displayed prominently:

* 98.7% Pipeline Reliability
* Active AI Agents
* Approved Runs Today
* Compliance Health Status

Metrics use animated counters and glowing status indicators.

---

## Workflow Timeline

Interactive horizontal workflow visualization:

```text
Ingest → Validate → AI Analyze → Review → Dashboard
```

### Features

* Animated workflow progression
* Hover expansion interactions
* AI pipeline visualization
* Gradient-linked stage connectors

---

## Five Pillars of Observability

Displayed using interactive honeycomb-style cards instead of traditional tables.

### Pillars

* Freshness
* Volume
* Schema
* Distribution
* Lineage

### Features

* Interactive hover states
* Mini metric previews
* Animated anomaly indicators
* Glassmorphism card surfaces

---

# 🔬 Pipeline Page

## Command Bar

The pipeline workspace begins with a top-level operational command center.

### Includes

* Dataset information
* Compliance status
* Current environment
* Run controls
* Active pipeline state

---

## Animated DAG Visualization

The traditional step-by-step list is replaced with a live animated pipeline DAG.

### Pipeline Stages

1. Input Discovery
2. Entry Validation
3. Preprocessing
4. PII/PHI Masking
5. AI Agents
6. Incident Report
7. Awaiting Review

### Visual States

| State    | Visual              |
| -------- | ------------------- |
| Idle     | Gray Node           |
| Running  | Animated Blue Pulse |
| Complete | Green Glow          |
| Failed   | Red Alert State     |

---

## Real-Time Progress Tracking

Circular radial progress indicators replace standard progress bars.

### Features

* Stage-aware progress
* Animated completion transitions
* Real-time pipeline state visibility
* Live execution tracking

---

## Live Insights Rail

Sticky right-side intelligence panel displaying:

* Records processed
* Anomalies detected
* PHI masking counts
* Active AI agents
* Estimated completion time

---

## Streaming Event Console

Terminal-inspired live event console.

### Features

* Auto-scrolling logs
* Severity highlighting
* Timestamped execution events
* Real-time monitoring aesthetic

Example:

```text
[12:42:01] Validation started
[12:42:03] Schema mismatch detected
[12:42:05] PHI masking complete
```

---

# 📋 Review Page (HITL Gate)

## Incident Severity Banner

Large contextual banner summarizing review urgency.

### Displays

* Health score
* Anomaly count
* Risk severity
* Approval requirement state

### Visual Style

* Gradient alert surfaces
* Animated border glow
* Contextual severity coloring

---

## AI Report Reader

The markdown report viewer is redesigned into a Notion-style AI report workspace.

### Features

* Collapsible sections
* Structured evidence blocks
* Inline compliance badges
* Styled anomaly callouts
* Scrollable report experience

---

## Floating Metric Capsules

Glassmorphism metric capsules replace traditional flat cards.

### Metrics

* Health Score
* Anomalies
* Freshness Status
* Volume Status
* Schema Status

---

## Sticky Decision Panel

Persistent floating review controls remain visible during report review.

### Approval Workflow

* Reviewer ID validation
* Review notes
* Approval action
* Rejection workflow

### Features

* Sticky positioning
* Smooth modal interactions
* Approval success animations
* Confetti transition effect

---

## AI Agent Trace Timeline

Horizontal AI execution timeline showing:

* Agent execution order
* Runtime metrics
* Agent outputs
* Token usage
* AI reasoning flow

Agents include:

* Data Quality Agent
* Log Analysis Agent
* RCA Agent
* Recommendation Agent
* Compliance Agent

---

# 📊 Analytics Dashboard

## Executive KPI Header

Sticky executive overview panel providing:

* Radial health score visualization
* Drift status
* Compliance status
* Approval state
* Last updated timestamp

---

## AI Findings Feed Rail

Real-time AI insight stream displayed in a pinned side rail.

### Example Events

```text
⚠ Drift detected in glucose_level
🟡 Null spike in patient_age
🟢 Schema validation passed
```

---

## Five Pillar Status Cards

Interactive observability status system for:

* Freshness
* Volume
* Schema
* Distribution
* Lineage

Each card includes:

* Status indicators
* Color-coded alerts
* Hover interactions
* Live operational summaries

---

# 📈 Interactive Visualizations

Charts are implemented using Recharts for modern enterprise analytics.

## Included Visualizations

### Patient Severity Pie Chart

* Interactive segmented chart
* Severity distribution analysis
* Animated transitions

---

### Side Effects Bar Chart

* Frequency-based analysis
* Ranked side effect visualization
* Interactive hover insights

---

### Null Rate Column Chart

* Column-wise null monitoring
* Threshold indicators
* Compliance-aware highlighting

---

### Distribution Drift Detection Grid

Interactive drift analysis table with:

* KS statistic
* p-values
* Drift thresholds
* Stability indicators

---

# 📤 Export Functionality

The platform supports operational exports for compliance and reporting.

### Export Formats

* PDF Reports
* JSON Audit Trails
* CSV Metrics

### UX Features

* Floating export action button
* Context-aware downloads
* Quick-access export menu

---

# 🧾 Compliance & Audit Experience

## FDA 21 CFR Part 11 Compliance

Compliance tracking is integrated throughout the entire application experience.

### Features

* Approval traceability
* Audit event logging
* Reviewer identity tracking
* Immutable approval workflows
* Compliance status indicators

---

## Audit Timeline

Audit data is visualized using an activity timeline instead of traditional tables.

### Includes

* Event timestamps
* Agent activity
* Approval actions
* Pipeline transitions
* Compliance checkpoints

---

# 🚀 Design Transformation Summary

The redesigned platform transforms the application from:

* Traditional Streamlit dashboard layouts
* Vertically stacked analytics pages
* Static operational reporting

Into:

* A modern AI Operations Command Center
* Enterprise observability workspace
* AI-native monitoring experience
* Real-time compliance intelligence platform

The final experience emphasizes:

* Operational awareness
* Real-time intelligence
* Enterprise-grade AI monitoring
* Workspace-driven productivity
* FDA-compliant observability workflows
