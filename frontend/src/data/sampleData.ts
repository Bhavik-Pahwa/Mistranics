import type { Alert, InvestigationRecord, Machine, MachineAlertCount } from '../types/dashboard'

/**
 * ============================================================================
 * PROTOTYPE SAMPLE DATA (DEMO / MOCK ONLY)
 * ============================================================================
 * NOTICE: As specified in PRD Section 8 & 15, all telemetry, alert statistics,
 * and machine health scores below are clearly identified prototype sample data.
 * No live backend connection or real telemetry stream is claimed.
 * ============================================================================
 */

export const SAMPLE_MACHINES: Machine[] = [
  {
    id: 'mach-cmp-03',
    code: 'CMP-003',
    name: 'Compressor #3',
    type: 'Industrial Rotary Screw Compressor',
    location: 'Bay 4 — Primary Chill Loop',
    priority: 1, // Highest priority: synchronous intervention required
    healthPercentage: 54.2,
    healthStatus: 'Poor health',
    color: '#3b82f6', // Cobalt blue
    telemetry: [
      { time: '00:00', vibration: 2.6, temperature: 56.4, health: 88 },
      { time: '04:00', vibration: 3.1, temperature: 62.1, health: 84 },
      { time: '08:00', vibration: 2.2, temperature: 53.8, health: 82 },
      { time: '12:00', vibration: 1.8, temperature: 51.5, health: 80 },
      { time: '16:00', vibration: 2.9, temperature: 55.0, health: 78 },
      { time: '20:00', vibration: 7.4, temperature: 61.2, health: 60 },
      { time: '24:00', vibration: 9.5, temperature: 66.8, health: 54 },
    ],
    subsystems: [
      { name: 'Drive Motor & Inverter', health: 91, status: 'Normal' },
      { name: 'Twin Rotor Bearing Assembly', health: 48, status: 'Warning' },
      { name: 'Oil Separation & Cooling Loop', health: 62, status: 'Degraded' },
      { name: 'Discharge Check Valve', health: 85, status: 'Normal' },
    ],
    metrics: {
      rpm: 3450,
      pressureBar: 8.4,
      runtimeHours: 4210,
      lubeOilTemp: 78.4,
    },
  },
  {
    id: 'mach-pmp-07',
    code: 'PMP-007',
    name: 'Cooling Pump P-7',
    type: 'High-Volume Centrifugal Water Pump',
    location: 'Bay 4 — Heat Exchanger Feed',
    priority: 2, // Second priority: thermal cascading risk
    healthPercentage: 72.8,
    healthStatus: 'Attention needed',
    color: '#06b6d4', // Cyan
    telemetry: [
      { time: '00:00', vibration: 3.2, temperature: 58.0, health: 80 },
      { time: '04:00', vibration: 3.8, temperature: 61.0, health: 78 },
      { time: '08:00', vibration: 3.5, temperature: 59.2, health: 76 },
      { time: '12:00', vibration: 4.1, temperature: 63.5, health: 75 },
      { time: '16:00', vibration: 5.6, temperature: 67.0, health: 73 },
      { time: '20:00', vibration: 6.8, temperature: 71.4, health: 71 },
      { time: '24:00', vibration: 7.9, temperature: 73.8, health: 68 },
    ],
    subsystems: [
      { name: 'Impeller & Casing', health: 74, status: 'Degraded' },
      { name: 'Mechanical Seal', health: 65, status: 'Degraded' },
      { name: 'Thrust Bearings', health: 70, status: 'Degraded' },
      { name: 'Coupling Element', health: 92, status: 'Normal' },
    ],
    metrics: {
      rpm: 1780,
      pressureBar: 5.2,
      runtimeHours: 6890,
      lubeOilTemp: 64.1,
    },
  },
  {
    id: 'mach-mil-08',
    code: 'MIL-008',
    name: 'CNC Milling Center M-08',
    type: '5-Axis Precision Machining Center',
    location: 'Cell B — High Precision Line',
    priority: 3, // Third priority
    healthPercentage: 81.5,
    healthStatus: 'Healthy',
    color: '#8b5cf6', // Violet
    telemetry: [
      { time: '00:00', vibration: 1.2, temperature: 52.0, health: 92 },
      { time: '04:00', vibration: 1.4, temperature: 53.5, health: 91 },
      { time: '08:00', vibration: 1.8, temperature: 55.2, health: 88 },
      { time: '12:00', vibration: 2.1, temperature: 57.0, health: 85 },
      { time: '16:00', vibration: 2.4, temperature: 58.4, health: 83 },
      { time: '20:00', vibration: 2.2, temperature: 56.1, health: 82 },
      { time: '24:00', vibration: 2.0, temperature: 54.8, health: 82 },
    ],
    subsystems: [
      { name: 'Main High-Speed Spindle', health: 88, status: 'Normal' },
      { name: 'X/Y/Z Linear Guideways', health: 84, status: 'Normal' },
      { name: 'Automatic Tool Changer', health: 96, status: 'Normal' },
      { name: 'Internal Coolant Chiller', health: 79, status: 'Normal' },
    ],
    metrics: {
      rpm: 12000,
      pressureBar: 6.8,
      runtimeHours: 3120,
      lubeOilTemp: 44.5,
    },
  },
  {
    id: 'mach-prs-02',
    code: 'PRS-002',
    name: 'Hydraulic Press P-2',
    type: 'Heavy Stamping 500-Ton Press',
    location: 'Stamping Hall — Section A',
    priority: 4,
    healthPercentage: 63.4,
    healthStatus: 'Attention needed',
    color: '#f59e0b', // Amber
    telemetry: [
      { time: '00:00', vibration: 4.0, temperature: 59.0, health: 75 },
      { time: '04:00', vibration: 4.5, temperature: 62.0, health: 73 },
      { time: '08:00', vibration: 5.2, temperature: 65.0, health: 70 },
      { time: '12:00', vibration: 5.8, temperature: 68.2, health: 67 },
      { time: '16:00', vibration: 6.3, temperature: 71.0, health: 64 },
      { time: '20:00', vibration: 5.9, temperature: 69.5, health: 64 },
      { time: '24:00', vibration: 5.4, temperature: 67.0, health: 63 },
    ],
    subsystems: [
      { name: 'Hydraulic Ram Cylinder', health: 62, status: 'Degraded' },
      { name: 'Proportional Servo Valves', health: 71, status: 'Degraded' },
      { name: 'Oil Filtration Manifold', health: 58, status: 'Warning' },
      { name: 'Safety Interlock Light Curtains', health: 98, status: 'Normal' },
    ],
    metrics: {
      rpm: 950,
      pressureBar: 210.0,
      runtimeHours: 8420,
      lubeOilTemp: 68.2,
    },
  },
  {
    id: 'mach-tbn-01',
    code: 'TBN-001',
    name: 'Turbine Generator T-1',
    type: 'Auxiliary Steam Turbine Co-Gen',
    location: 'Power Generation Building',
    priority: 5,
    healthPercentage: 92.0,
    healthStatus: 'Healthy',
    color: '#10b981', // Emerald
    telemetry: [
      { time: '00:00', vibration: 1.1, temperature: 54.0, health: 96 },
      { time: '04:00', vibration: 1.2, temperature: 54.8, health: 95 },
      { time: '08:00', vibration: 1.3, temperature: 55.5, health: 94 },
      { time: '12:00', vibration: 1.4, temperature: 56.0, health: 93 },
      { time: '16:00', vibration: 1.5, temperature: 56.4, health: 93 },
      { time: '20:00', vibration: 1.3, temperature: 55.2, health: 92 },
      { time: '24:00', vibration: 1.2, temperature: 54.9, health: 92 },
    ],
    subsystems: [
      { name: 'Steam Inflow Governor', health: 95, status: 'Normal' },
      { name: 'Rotor Balancing Journal', health: 91, status: 'Normal' },
      { name: 'Stator Core Windings', health: 94, status: 'Normal' },
      { name: 'Labyrinth Shaft Seals', health: 89, status: 'Normal' },
    ],
    metrics: {
      rpm: 3600,
      pressureBar: 42.0,
      runtimeHours: 11450,
      lubeOilTemp: 52.0,
    },
  },
  {
    id: 'mach-mtr-12',
    code: 'MTR-012',
    name: 'Feed Motor M-12',
    type: 'Variable Frequency Conveyor Drive',
    location: 'Packaging Line #2',
    priority: 6,
    healthPercentage: 88.6,
    healthStatus: 'Healthy',
    color: '#ec4899', // Pink
    telemetry: [
      { time: '00:00', vibration: 0.9, temperature: 51.0, health: 95 },
      { time: '04:00', vibration: 1.0, temperature: 51.8, health: 94 },
      { time: '08:00', vibration: 1.1, temperature: 52.4, health: 92 },
      { time: '12:00', vibration: 1.3, temperature: 53.0, health: 90 },
      { time: '16:00', vibration: 1.4, temperature: 53.6, health: 89 },
      { time: '20:00', vibration: 1.2, temperature: 52.5, health: 89 },
      { time: '24:00', vibration: 1.1, temperature: 52.0, health: 88 },
    ],
    subsystems: [
      { name: 'Stator Insulated Phase Rings', health: 93, status: 'Normal' },
      { name: 'End Shield Drive Bearings', health: 87, status: 'Normal' },
      { name: 'Inverter IGBT Module', health: 90, status: 'Normal' },
      { name: 'Shaft Grounding Ring', health: 95, status: 'Normal' },
    ],
    metrics: {
      rpm: 1450,
      pressureBar: 1.0,
      runtimeHours: 5100,
      lubeOilTemp: 47.3,
    },
  },
]

export const SAMPLE_ALERT_COUNTS: MachineAlertCount[] = [
  {
    machineId: 'mach-cmp-03',
    machineName: 'Compressor #3',
    machineCode: 'CMP-03',
    color: '#3b82f6',
    counts: {
      '24h': 7,
      week: 19,
      month: 46,
    },
  },
  {
    machineId: 'mach-pmp-07',
    machineName: 'Cooling Pump P-7',
    machineCode: 'PMP-07',
    color: '#06b6d4',
    counts: {
      '24h': 5,
      week: 14,
      month: 32,
    },
  },
  {
    machineId: 'mach-mil-08',
    machineName: 'CNC Mill M-08',
    machineCode: 'MIL-08',
    color: '#8b5cf6',
    counts: {
      '24h': 2,
      week: 8,
      month: 18,
    },
  },
  {
    machineId: 'mach-prs-02',
    machineName: 'Press P-2',
    machineCode: 'PRS-02',
    color: '#f59e0b',
    counts: {
      '24h': 4,
      week: 11,
      month: 27,
    },
  },
  {
    machineId: 'mach-tbn-01',
    machineName: 'Turbine T-1',
    machineCode: 'TBN-01',
    color: '#10b981',
    counts: {
      '24h': 1,
      week: 3,
      month: 9,
    },
  },
  {
    machineId: 'mach-mtr-12',
    machineName: 'Feed Motor M-12',
    machineCode: 'MTR-12',
    color: '#ec4899',
    counts: {
      '24h': 2,
      week: 5,
      month: 12,
    },
  },
]

export const INITIAL_ACTIVE_ALERTS: Alert[] = [
  {
    id: 'alt-001',
    machineId: 'mach-cmp-03',
    machineName: 'Compressor #3',
    machineCode: 'CMP-003',
    title: 'Twin Rotor Bearing Vibration Exceeds ISO 10816 Limit',
    description: 'Radial vibration instability detected on drive-end bearing. Upstream excitation triggering thermal cascading across cooling manifold.',
    severity: 'Critical',
    detectedTime: '8 mins ago',
    detectedTimestamp: '2026-11-02T16:19:00Z',
    whatToCheckPreview: 'Inspect drive-end bearing journal, oil pressure bypass valve, and shaft alignment.',
    detailedExplanation:
      'High-frequency harmonic spectrum analysis indicates 2X and 4X rotational frequency harmonics consistent with inner raceway spalling. Current vibration amplitude has climbed from baseline 2.1 mm/s to 9.5 mm/s over a 4-hour window.',
    evidence: [
      {
        metric: 'Vibration RMS (DE)',
        observed: '9.5 mm/s',
        threshold: '> 7.1 mm/s (Alarm)',
        timestamp: '16:19 UTC',
      },
      {
        metric: 'Bearing Housing Temp',
        observed: '78.4°C',
        threshold: '> 75.0°C (Warn)',
        timestamp: '16:21 UTC',
      },
      {
        metric: 'Harmonic Peak Order',
        observed: '2.14X running speed',
        threshold: '< 0.5X',
        timestamp: '16:18 UTC',
      },
    ],
    whatToCheck: [
      'Perform acoustic strobe inspection on drive coupling guard for physical backlash.',
      'Measure lube oil viscosity and check differential pressure across line filter #FLT-03.',
      'Verify accelerometer mounting stud torque (spec: 14 Nm).',
    ],
    troubleshootingSteps: [
      {
        step: 1,
        instruction: 'Throttle load to 50% capacity via secondary bypass loop',
        detail: 'Reduces radial bearing force while maintaining minimum line pressure for downstream processes.',
      },
      {
        step: 2,
        instruction: 'Collect tri-axial spectrum capture via port CMP-VIB-02',
        detail: 'Determines whether vibration is pure rotational unbalance or sub-synchronous oil whirl.',
      },
      {
        step: 3,
        instruction: 'Inspect oil reservoir sight glass for cavitation bubbles',
        detail: 'Foaming in the return reservoir can starve the hydrodynamic wedge.',
      },
    ],
    recommendedActions: [
      'Dispatch mechanical reliability technician to Bay 4 immediately.',
      'Stage spare SKF 7312 bearing set from plant crib B.',
      'Prepare load handover to redundant compressor unit CMP-004.',
    ],
    investigationId: 'INV-2026-089',
    investigationTitle: 'Compressor #3 Drive-End Bearing Anomaly & Cascade Risk',
    status: 'active',
  },
  {
    id: 'alt-002',
    machineId: 'mach-pmp-07',
    machineName: 'Cooling Pump P-7',
    machineCode: 'PMP-007',
    title: 'Discharge Manifold Cavitation & Thermal Elevation',
    description: 'Cavitation acoustic signature combined with discharge temperature rise of 12.8°C over 90 minutes.',
    severity: 'High',
    detectedTime: '24 mins ago',
    detectedTimestamp: '2026-11-02T16:03:00Z',
    whatToCheckPreview: 'Check suction strainer differential pressure and NPSH margin on heat exchanger loop.',
    detailedExplanation:
      'Suction pressure dropped to 1.1 bar absolute, reducing Net Positive Suction Head below the critical 1.8 bar threshold. Impeller vapor bubble collapse is creating high-frequency micro-jets.',
    evidence: [
      {
        metric: 'Suction Head (NPSHa)',
        observed: '1.1 bar',
        threshold: '< 1.8 bar (Fault)',
        timestamp: '16:02 UTC',
      },
      {
        metric: 'Discharge Fluid Temp',
        observed: '73.8°C',
        threshold: '> 68.0°C (Warn)',
        timestamp: '16:15 UTC',
      },
    ],
    whatToCheck: [
      'Examine suction strainer DP indicator for debris blockage.',
      'Check position transmitter on upstream butterfly valve V-402.',
    ],
    troubleshootingSteps: [
      {
        step: 1,
        instruction: 'Switch cooling intake to secondary reservoir header',
        detail: 'Restores suction hydrostatic head to 2.4 bar.',
      },
      {
        step: 2,
        instruction: 'Verify mechanical seal flush flow meter reading',
        detail: 'Ensure Plan 11 flush piping is not vapor-bound.',
      },
    ],
    recommendedActions: [
      'Cycle upstream intake strainer blowdown valve.',
      'Verify water basin supply level on chiller tower CT-02.',
    ],
    investigationId: 'INV-2026-084',
    investigationTitle: 'Cooling Pump P-7 Suction Head Loss Investigation',
    status: 'active',
  },
  {
    id: 'alt-003',
    machineId: 'mach-prs-02',
    machineName: 'Hydraulic Press P-2',
    machineCode: 'PRS-002',
    title: 'Servo Valve Response Delay on Downstroke Cycle',
    description: 'Cycle stroke lag exceeding 220ms during tonnage build phase, suggesting valve spool siltation.',
    severity: 'Moderate',
    detectedTime: '1 hour ago',
    detectedTimestamp: '2026-11-02T15:27:00Z',
    whatToCheckPreview: 'Sample hydraulic fluid ISO cleanliness code and inspect return line magnet plug.',
    detailedExplanation:
      'Electro-hydraulic proportional valve SV-2 command current is lagging pilot spool displacement. Potential particulate contamination in oil manifold.',
    evidence: [
      {
        metric: 'Spool Response Time',
        observed: '224 ms',
        threshold: '> 140 ms (Warn)',
        timestamp: '15:26 UTC',
      },
      {
        metric: 'Filter DP Pressure',
        observed: '2.4 bar',
        threshold: '> 2.0 bar (Warn)',
        timestamp: '15:30 UTC',
      },
    ],
    whatToCheck: [
      'Take oil bottle sample from sampling port SP-3 for patch count test.',
      'Check calibration offset on LVDT position sensor.',
    ],
    troubleshootingSteps: [
      {
        step: 1,
        instruction: 'Execute valve spool purge routine from HMI maintenance screen',
        detail: 'Exercises valve full stroke 5 times to dislodge micro-silt.',
      },
      {
        step: 2,
        instruction: 'Inspect bypass pop-up pin on kidney loop filtration cart',
        detail: 'Verifies off-line fluid polishing is active.',
      },
    ],
    recommendedActions: [
      'Schedule filter element cartridge replacement during next shift change.',
      'Log fluid particle count in maintenance database.',
    ],
    investigationId: 'INV-2026-077',
    investigationTitle: 'Hydraulic Press P-2 Servo Spool Dynamic Lag',
    status: 'active',
  },
]

export const SAMPLE_INVESTIGATIONS: InvestigationRecord[] = [
  {
    id: 'INV-2026-089',
    machineId: 'mach-cmp-03',
    machineName: 'Compressor #3',
    title: 'Compressor #3 Drive-End Bearing Anomaly & Cascade Risk',
    status: 'In Progress',
    createdAt: '2026-11-02 16:20',
    lastUpdated: '2026-11-02 16:25',
    resolutionLog: ['Alert #alt-001 created automatically by anomaly engine.'],
  },
  {
    id: 'INV-2026-084',
    machineId: 'mach-pmp-07',
    machineName: 'Cooling Pump P-7',
    title: 'Cooling Pump P-7 Suction Head Loss Investigation',
    status: 'In Progress',
    createdAt: '2026-11-02 16:04',
    lastUpdated: '2026-11-02 16:15',
    resolutionLog: ['Alert #alt-002 created from edge pump sensor feed.'],
  },
  {
    id: 'INV-2026-077',
    machineId: 'mach-prs-02',
    machineName: 'Hydraulic Press P-2',
    title: 'Hydraulic Press P-2 Servo Spool Dynamic Lag',
    status: 'Open',
    createdAt: '2026-11-02 15:28',
    lastUpdated: '2026-11-02 15:32',
    resolutionLog: ['Alert #alt-003 initialized by hydraulic telemetry monitor.'],
  },
]
