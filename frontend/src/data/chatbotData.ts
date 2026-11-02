import type { AIPersona, ChatSession } from '../types/chatbot'

export const AI_PERSONAS: AIPersona[] = [
  {
    id: 'reliability',
    name: 'Reliability Expert',
    title: 'Vibration & Dynamics Diagnostician',
    description: 'Specializes in ISO 10816 standards, FFT harmonic spectrums, and bearing degradation patterns.',
    avatar: '⚡',
    color: '#2563eb', // Blue
    suggestedPrompts: [
      'Diagnose 2X and 4X harmonic vibration on Compressor #3',
      'What are the ISO 10816-3 alarm limits for flexible foundation machines?',
      'Calculate defect frequencies for SKF 7312 bearing',
      'Explain difference between oil whirl vs mechanical unbalance',
    ],
  },
  {
    id: 'thermal',
    name: 'Thermal Specialist',
    title: 'Fluid Systems & Heat Transfer Lead',
    description: 'Expertise in pump cavitation, heat exchanger fouling, Net Positive Suction Head (NPSH), and thermal cascading.',
    avatar: '🌡️',
    color: '#0891b2', // Cyan
    suggestedPrompts: [
      'Evaluate suction cavitation risk on Cooling Pump P-7',
      'How to calculate NPSHa with suction reservoir at 1.1 bar?',
      'Check thermal cascading risk between Compressor #3 and loop P-7',
      'Recommended delta-T across shell-and-tube heat exchangers',
    ],
  },
  {
    id: 'maintenance',
    name: 'SOP Navigator',
    title: 'Field Maintenance Procedures Guide',
    description: 'Provides step-by-step repair checklists, lock-out/tag-out rules, torque values, and spares staging.',
    avatar: '🛠️',
    color: '#7c3aed', // Purple
    suggestedPrompts: [
      'Provide bearing replacement SOP for rotary screw compressor',
      'Check coupling bolt torque spec for 120kW motor',
      'List mandatory PPE and safety lockout steps for Bay 4',
      'Hydraulic oil flush procedure for servo proportional valve',
    ],
  },
  {
    id: 'investigator',
    name: 'Root Cause Analyst',
    title: 'Failure Mode & Risk Specialist',
    description: 'Root cause analysis, 5-Whys, fault trees, and preventing line-halt chain reactions.',
    avatar: '🔍',
    color: '#d97706', // Amber
    suggestedPrompts: [
      'Construct 5-Whys analysis for Compressor #3 vibration spike',
      'Assess line-halt probability if Cooling Pump P-7 trips',
      'Generate investigation report draft for anomaly #INV-2026-089',
      'Review historical failure patterns for stamping press servo valves',
    ],
  },
]

export const INITIAL_CHAT_SESSIONS: ChatSession[] = [
  {
    id: 'sess-01',
    title: 'New Diagnostic Session',
    timestamp: 'Just now',
    category: 'Today',
    personaId: 'reliability',
    machineId: 'mach-cmp-03',
    messages: [], // Empty initial state: displays the modern and minimal chatbot prompt screen
  },
]

