export type MachineHealthStatus = 'Healthy' | 'Attention needed' | 'Poor health'

export type AlertSeverity = 'Critical' | 'High' | 'Moderate'

export type TimeRange = '24h' | 'week' | 'month'

export type ApplicationState = 'normal' | 'loading' | 'empty' | 'disconnected' | 'error'

export interface TelemetryPoint {
  time: string // e.g. "00:00", "04:00"
  vibration: number // mm/s
  temperature: number // °C
  health: number // %
}

export interface Machine {
  id: string
  code: string // e.g. "CMP-003"
  name: string // e.g. "Compressor #3"
  type: string // e.g. "Rotary Screw Compressor"
  location: string // e.g. "Bay 4 - Primary Cooling Loop"
  priority: number // 1 = highest operational priority
  healthPercentage: number // e.g. 72.8
  healthStatus: MachineHealthStatus
  color: string // consistent color for bar chart and legends
  telemetry: TelemetryPoint[]
  subsystems: {
    name: string
    health: number
    status: 'Normal' | 'Degraded' | 'Warning'
  }[]
  metrics: {
    rpm: number
    pressureBar: number
    runtimeHours: number
    lubeOilTemp: number
  }
}

export interface TroubleshootingStep {
  step: number
  instruction: string
  detail: string
}

export interface Alert {
  id: string
  machineId: string
  machineName: string
  machineCode: string
  title: string
  description: string
  severity: AlertSeverity
  detectedTime: string // e.g. "12m ago"
  detectedTimestamp: string // ISO string
  whatToCheckPreview: string
  detailedExplanation: string
  evidence: {
    metric: string
    observed: string
    threshold: string
    timestamp: string
  }[]
  whatToCheck: string[]
  troubleshootingSteps: TroubleshootingStep[]
  recommendedActions: string[]
  investigationId: string
  investigationTitle: string
  status: 'active' | 'resolved'
  resolvedAt?: string
}

export interface MachineAlertCount {
  machineId: string
  machineName: string
  machineCode: string
  color: string
  counts: {
    '24h': number
    week: number
    month: number
  }
}

export interface InvestigationRecord {
  id: string
  machineId: string
  machineName: string
  title: string
  status: 'Open' | 'In Progress' | 'Closed'
  createdAt: string
  lastUpdated: string
  resolutionLog: string[]
}

