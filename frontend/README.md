# MISTRANICS — Industrial Condition Monitoring Dashboard

A high-performance, single-sight industrial condition monitoring dashboard designed with Apple Design foundations (fluidity, tactile micro-animations, frosted depth materials, and optical restraint).

The dashboard fits strictly within a **100vh fullscreen layout** with zero window-level scrollbars, presenting real-time telemetry, asset priority rankings, and a full-height diagnostic alert triage queue in a single, balanced view.

---

## Quick Start

### Prerequisites
- **Node.js** (v18+ recommended; tested on v24.16.0)
- **npm** (v9+; tested on v11.13.0)

### Installation & Run

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm run dev
   ```
   Open your browser to the local URL displayed (typically `http://localhost:5173`).

3. **Production Build & Verification:**
   ```bash
   npm run build
   npm run preview
   ```

---

## Architectural & Design Highlights

- **Strict 100vh Fullscreen Single-Sight**: The entire dashboard renders within `100vh` without page scrolling.
- **Apple-Inspired Design Language (WWDC)**:
  - **Tactile Micro-Animations**: Immediate physical press feedback on pointer-down (`scale(0.97)`), spring settles (`cubic-bezier(0.16, 1, 0.3, 1)`), and smooth hover lifts.
  - **Eye-Friendly Studio Neutral Canvas**: Replaced harsh flat white with a soothing, eye-friendly slate/neutral gradient mesh (`#e7ebf2` to `#edf1f6`) with ambient radial illumination.
  - **Frosted Depth Materials**: Translucent surfaces with `backdrop-filter: blur(16px)` and delicate highlight borders.
- **Restructured Layout & Full-Height Active Alerts**:
  - **Floating Spotlight Search**: Traditional top navbar removed in favor of a floating glass search island (`Ctrl+K`).
  - **Sidebar-Integrated Menu**: Sidebar header houses the main expand/collapse hamburger button.
  - **Full-Height Active Alerts**: The "Alert Activity" section has been removed, elevating Active Alerts & Triage into a dedicated full-height command column (40% width).
  - **Left Column (60% width)**: Houses Machine Sensor Trends (50% height) with smooth Bézier telemetry curves, and Priority Machines Overview (50% height) with circular health gauges.
- **Machine Analytics Floating Workspace**: Contextual modal workspace triggered by selecting any asset card, featuring subsystem health index and live diagnostic runs.

---

## Documentation

For full architectural details, component data flows, and integration guidelines:
- [`ARCHITECTURE_AND_SPEC.md`](./ARCHITECTURE_AND_SPEC.md)
