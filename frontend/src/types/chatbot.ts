export type PersonaId = 'reliability' | 'thermal' | 'maintenance' | 'investigator'

export type ChatTone = 'Analytical' | 'Concise' | 'Step-by-Step SOP'

export interface AIPersona {
  id: PersonaId
  name: string
  title: string
  description: string
  avatar: string
  color: string
  suggestedPrompts: string[]
}

export interface ChatMessage {
  id: string
  sender: 'user' | 'assistant'
  timestamp: string
  text: string
  personaId?: PersonaId
  machineContext?: string
  evidence?: {
    metric: string
    value: string
    status: 'normal' | 'warning' | 'critical'
  }[]
  actionLinks?: {
    label: string
    action: string
  }[]
  feedback?: 'up' | 'down' | null
}

export interface ChatSession {
  id: string
  title: string
  timestamp: string
  category: 'Today' | 'Yesterday' | 'Previous 7 Days'
  personaId: PersonaId
  machineId?: string
  messages: ChatMessage[]
}

