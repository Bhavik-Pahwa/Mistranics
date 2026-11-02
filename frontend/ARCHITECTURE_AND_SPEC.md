# MISTRANICS Dashboard — Architecture & Technical Specification

This document provides a comprehensive technical overview of the Mistranics Dashboard prototype implementation, incorporating Apple Design foundations from `SKILL.md` (fluid motion, tactile micro-animations, optical sizing, and translucent depth materials).

---

## 1. Project Structure

```
FRONTEND/
├── index.html                   # HTML entry point with system fonts & viewport configuration
├── package.json                 # Dependency manifests and build scripts
├── vite.config.ts               # Vite bundler configuration with React & Tailwind plugins
├── tsconfig.json                # TypeScript project configuration
├── src/
│   ├── main.tsx                 # React application mounting point with StrictMode
│   ├── index.css                # Apple design tokens, tactile micro-animations, neutral background
│   ├── App.tsx                  # Root layout, 60/40 grid layout, and global state orchestration
│   ├── types/
│   │   └── dashboard.ts         # Central TypeScript interfaces (Machine, Alert, TelemetryPoint, etc.)
│   ├── data/
│   │   └── sampleData.ts        # Clearly labeled mock telemetry and event records (isolated from UI)
│   └── components/
│       ├── Sidebar.tsx          # Full-height sidebar with integrated hamburger toggle
│       ├── FloatingSearchBar.tsx # Apple Spotlight-inspired floating frosted search pill
│       ├── Part1SensorTrends.tsx # Upper-left: Dual-axis smooth curves, carousel arrows, manual stop
│       ├── Part3MachineOverview.tsx # Lower-left: Priority machine cards, circular health indicators
│       ├── Part4ActiveAlerts.tsx # Right Column: FULL-HEIGHT active alerts triage and evidence resolution
│       ├── MachineAnalyticsModal.tsx # Centered floating workspace shell with blurred background
│       └── SearchDialog.tsx     # Full modal search interface triggered via floating pill or Ctrl+K
└── ARCHITECTURE_AND_SPEC.md     # This technical specification
```

---

## 2. Apple Design Language & Micro-Animations

In accordance with `SKILL.md`:
1. **Immediate Physical Response (`.apple-press`)**:
   - Responds on pointer-down / active state: `transform: scale(0.97)` with `transition: transform 120ms cubic-bezier(0.2, 0, 0, 1)`.
   - Applied to all buttons, carousel arrows, cards, and segmented pills.
2. **Spring Settle**:
   - Card transitions and hover elevations use Apple's critically damped spring curve: `cubic-bezier(0.16, 1, 0.3, 1)`.
3. **Translucent Frosted Materials**:
   - Cards use `backdrop-filter: blur(16px) saturate(180%)` with semi-translucent fills (`rgba(255, 255, 255, 0.88)`) and delicate borders (`rgba(203, 213, 225, 0.7)`).
4. **Eye-Friendly Studio Neutral Canvas**:
   - Replaced flat white with a soothing, eye-friendly slate/neutral gradient mesh (`#e7ebf2` to `#edf1f6`) with ambient radial illumination.

---

## 3. Layout Architecture (100vh Single-Sight)

- **Floating Spotlight Search**: The traditional full-width top navbar has been removed. A floating frosted search pill sits at the top of the canvas, saving vertical space.
- **Sidebar-Integrated Menu**: The hamburger button is integrated into the top of the sidebar.
- **Left Column (60% width)**:
  - Upper Quadrant: **Part 1 — Machine Sensor Trends** (50% height). Smooth Bézier telemetry curves with dual Y-axes (red vibration, blue temperature, green health) and carousel navigation.
  - Lower Quadrant: **Part 3 — Priority Machines Overview** (50% height). Compact asset cards with animated circular health indicators.
- **Right Column (40% width)**:
  - **Part 4 — Active Alerts & Troubleshooting (FULL HEIGHT)**. Occupies 100% of the column height, providing technicians with an expansive triage workspace for evidence review, checklists, troubleshooting steps, and one-click resolution.
- **Zero Page Scroll**: The layout fits strictly in `100vh` without window-level scrollbars.
