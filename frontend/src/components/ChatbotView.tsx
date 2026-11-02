import React, { useState, useRef, useEffect } from 'react'
import {
  Send,
  Paperclip,
  Mic,
  Copy,
  Check,
  Sparkles,
  User,
  RotateCcw,
  ExternalLink,
  ArrowLeft,
  Activity,
  ArrowRight,
  Gauge,
  Radio,
} from 'lucide-react'
import { AI_PERSONAS, INITIAL_CHAT_SESSIONS } from '../data/chatbotData'
import type { ChatMessage, ChatSession, ChatTone, PersonaId } from '../types/chatbot'
import type { Machine } from '../types/dashboard'

interface ChatbotViewProps {
  machines: Machine[]
  onOpenMachineAnalytics?: (machine: Machine) => void
  onNavigateToDashboard?: () => void
}

export const ChatbotView: React.FC<ChatbotViewProps> = ({
  machines,
  onOpenMachineAnalytics,
  onNavigateToDashboard,
}) => {
  // Session State (Starts with empty messages for clean modern initial prompt screen)
  const [sessions, setSessions] = useState<ChatSession[]>(INITIAL_CHAT_SESSIONS)
  const [activeSessionId] = useState<string>('sess-01')
  const [activePersonaId, setActivePersonaId] = useState<PersonaId>('reliability')
  const [selectedMachineId, setSelectedMachineId] = useState<string>('mach-cmp-03')
  const [chatTone, setChatTone] = useState<ChatTone>('Analytical')
  const [inputPrompt, setInputPrompt] = useState<string>('')
  const [isTyping, setIsTyping] = useState<boolean>(false)
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const currentSession = sessions.find((s) => s.id === activeSessionId) || sessions[0]
  const currentPersona = AI_PERSONAS.find((p) => p.id === activePersonaId) || AI_PERSONAS[0]
  const currentMachine = machines.find((m) => m.id === selectedMachineId) || machines[0]

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [currentSession?.messages, isTyping])

  // Reset/Clear to empty prompt screen
  const handleResetChat = () => {
    setSessions((prev) =>
      prev.map((sess) =>
        sess.id === activeSessionId
          ? { ...sess, messages: [] }
          : sess
      )
    )
    setInputPrompt('')
    setIsTyping(false)
  }

  // Interactive dynamic message dispatch
  const handleSendMessage = (textToSend?: string) => {
    const messageText = textToSend || inputPrompt.trim()
    if (!messageText) return

    const userMessageId = `msg-user-${Date.now()}`
    const now = new Date()
    const timestamp = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    const newUserMessage: ChatMessage = {
      id: userMessageId,
      sender: 'user',
      timestamp,
      text: messageText,
    }

    setSessions((prev) =>
      prev.map((sess) =>
        sess.id === activeSessionId
          ? { ...sess, messages: [...sess.messages, newUserMessage] }
          : sess
      )
    )

    setInputPrompt('')
    setIsTyping(true)

    // Realistic condition-monitoring diagnostic response generator
    setTimeout(() => {
      const assistantMessageId = `msg-ai-${Date.now()}`
      const queryLower = messageText.toLowerCase()
      const isVibration =
        queryLower.includes('vibration') ||
        queryLower.includes('harmonic') ||
        queryLower.includes('fft') ||
        queryLower.includes('compressor')
      const isISO =
        queryLower.includes('iso') ||
        queryLower.includes('limit') ||
        queryLower.includes('severity') ||
        queryLower.includes('standard')
      const isThermal =
        queryLower.includes('cavitation') ||
        queryLower.includes('pump') ||
        queryLower.includes('temp') ||
        queryLower.includes('heat')
      const isSOP =
        queryLower.includes('sop') ||
        queryLower.includes('procedure') ||
        queryLower.includes('torque') ||
        queryLower.includes('repair')

      let replyText = ''
      let evidenceList = undefined
      let actionLinks = undefined

      if (isVibration) {
        replyText = `Based on the latest tri-axial telemetry feed for **${currentMachine.name}**, the emergence of pronounced 2X (2.14X running speed) and 4X rotational frequency harmonics combined with a rapid rise in RMS amplitude from 2.6 to 9.5 mm/s points directly to **drive-end inner raceway fatigue spalling** with secondary coupling angular misalignment.\n\n### Critical Observations:\n1. **ISO 10816-3 Alarm Limit**: Current level of 9.5 mm/s severely breaches the Zone C/D boundary (> 7.1 mm/s Alarm limit).\n2. **Thermal Elevation**: Bearing housing temperature has risen to 78.4°C (+13.4°C over baseline), confirming frictional heating from raceway micro-welds.\n3. **Cascade Risk**: Upstream vibration instability is transmitting resonant vibration into connected pipe headers.\n\n### Immediate Action Protocol:\n- **Step 1**: Throttle ${currentMachine.name} throughput to 50% load immediately to relieve hydrodynamic load.\n- **Step 2**: Check differential pressure across lube filter.\n- **Step 3**: Stage replacement SKF bearing assembly and prepare load handover to redundant unit.`
        evidenceList = [
          { metric: 'Vibration RMS (DE)', value: '9.5 mm/s (Alarm > 7.1)', status: 'critical' as const },
          { metric: 'Bearing Temp', value: '78.4°C (+13.4°C)', status: 'warning' as const },
          { metric: 'Harmonic Order', value: '2.14X & 4.02X', status: 'critical' as const },
        ]
        actionLinks = [
          { label: `View ${currentMachine.name} Analytics`, action: 'view_machine' },
        ]
      } else if (isISO) {
        replyText = `Under **ISO 10816-3 (Class II industrial machinery on flexible/rigid supports)**:\n\n- **Zone A (Good)**: < 1.4 mm/s RMS (Newly commissioned condition)\n- **Zone B (Acceptable)**: 1.4 – 2.8 mm/s RMS (Unrestricted long-term continuous operation)\n- **Zone C (Advisory / Unsatisfactory)**: 2.8 – 7.1 mm/s RMS (Action required, maintenance scheduling)\n- **Zone D (Unacceptable / Alarm)**: > 7.1 mm/s RMS (Immediate trip / damage hazard)\n\n**Assessment for ${currentMachine.name} (${currentMachine.code})**:\nCurrent telemetry registers **9.5 mm/s RMS**, placing the machine deep within **Zone D (Unacceptable)**. An automated trip warning has been elevated to the plant control room.`
        evidenceList = [
          { metric: 'Current RMS Velocity', value: '9.5 mm/s', status: 'critical' as const },
          { metric: 'Zone C/D Threshold', value: '7.1 mm/s', status: 'warning' as const },
          { metric: 'Compliance Status', value: 'Zone D Non-Compliant', status: 'critical' as const },
        ]
        actionLinks = [
          { label: `Open ${currentMachine.name} Telemetry`, action: 'view_machine' },
        ]
      } else if (isThermal) {
        replyText = `Thermal and fluid-system diagnosis for **${currentMachine.name}** indicates abnormal thermal gradients:\n\n- **Suction NPSH**: Net positive suction head margin has shrunk to 1.1 bar (minimum recommended: 1.8 bar), triggering localized micro-cavitation along the impeller inlet.\n- **Discharge Temperature**: 73.8°C (+11.2°C above baseline steady-state).\n\n**Recommended Procedure**: Transition suction line to auxiliary reservoir feed to restore 2.2 bar header pressure immediately.`
        evidenceList = [
          { metric: 'Suction Head (NPSHa)', value: '1.1 bar (Fault < 1.8)', status: 'critical' as const },
          { metric: 'Discharge Temp', value: '73.8°C', status: 'warning' as const },
          { metric: 'Cavitation Index', value: 'High Risk', status: 'critical' as const },
        ]
        actionLinks = [
          { label: `Inspect ${currentMachine.name}`, action: 'view_machine' },
        ]
      } else if (isSOP) {
        replyText = `### Standard Operating Procedure (SOP): ${currentMachine.name} Bearing Inspection & Replacement\n\n**Prerequisites & PPE**:\n- Lock-Out / Tag-Out (LOTO) breaker #CB-402\n- Calibrated torque wrench (range 40-120 Nm)\n- Spares: 1x SKF 7312 bearing assembly, 2x Viton O-rings\n\n**Execution Steps**:\n1. De-energize and lock out main 400V feed; verify zero-energy state with multimeter.\n2. Disconnect flexible coupling bolts (M12 grade 10.9; re-torque to 85 Nm on reassembly).\n3. Mount dial indicator on shaft stub; measure radial runout (tolerance < 0.025 mm).\n4. Pull bearing housing using hydraulic puller; clean journal with lint-free solvent.\n5. Heat replacement bearing inductively to 110°C; seat firmly against shaft shoulder.`
        evidenceList = [
          { metric: 'Coupling Bolt Torque', value: '85 Nm', status: 'normal' as const },
          { metric: 'Radial Runout Spec', value: '< 0.025 mm', status: 'normal' as const },
          { metric: 'Bearing Induction Temp', value: '110°C Max', status: 'warning' as const },
        ]
        actionLinks = [
          { label: 'View Machine Analytics', action: 'view_machine' },
        ]
      } else {
        replyText = `Analysis complete for **${currentMachine.name}** under **${currentPersona.name}** mode:\n\nCurrent operational parameters show continuous monitoring status. All diagnostic routines indicate ${
          currentMachine.healthPercentage > 70 ? 'nominal conditions' : 'elevated wear requiring preventative maintenance'
        }.\n\n- **Health Score**: ${currentMachine.healthPercentage.toFixed(1)}%\n- **Operating Speed**: ${currentMachine.metrics.rpm} RPM\n- **Recommendation**: Continue standard vibration logging cycle.`
        evidenceList = [
          {
            metric: 'Health Index',
            value: `${currentMachine.healthPercentage.toFixed(1)}%`,
            status: (currentMachine.healthPercentage > 70 ? 'normal' : 'warning') as 'normal' | 'warning',
          },
          { metric: 'Running RPM', value: `${currentMachine.metrics.rpm}`, status: 'normal' as const },
        ]
        actionLinks = [
          { label: `Open ${currentMachine.name} Details`, action: 'view_machine' },
        ]
      }

      const newAssistantMessage: ChatMessage = {
        id: assistantMessageId,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        personaId: activePersonaId,
        machineContext: `${currentMachine.name} (${currentMachine.code})`,
        text: replyText,
        evidence: evidenceList,
        actionLinks,
        feedback: null,
      }

      setSessions((prev) =>
        prev.map((sess) =>
          sess.id === activeSessionId
            ? { ...sess, messages: [...sess.messages, newAssistantMessage] }
            : sess
        )
      )
      setIsTyping(false)
    }, 700)
  }

  const handleFeedback = (messageId: string, type: 'up' | 'down') => {
    setSessions((prev) =>
      prev.map((sess) =>
        sess.id === activeSessionId
          ? {
              ...sess,
              messages: sess.messages.map((m) =>
                m.id === messageId
                  ? { ...m, feedback: m.feedback === type ? null : type }
                  : m
              ),
            }
          : sess
      )
    )
  }

  const handleCopyMessage = (text: string, messageId: string) => {
    navigator.clipboard.writeText(text)
    setCopiedMessageId(messageId)
    setTimeout(() => setCopiedMessageId(null), 2000)
  }

  // Active machine telemetry data
  const latestVib = currentMachine.telemetry[currentMachine.telemetry.length - 1]?.vibration || 2.4
  const latestTemp = currentMachine.telemetry[currentMachine.telemetry.length - 1]?.temperature || 45.0
  const isVibAlert = latestVib > 7.1

  return (
    <div className="flex h-full w-full overflow-hidden select-none">
      {/* 1. LEFT PANEL: Live Asset Context (Replaced the left-side section; right section is kept empty) */}
      <div className="flex w-72 lg:w-80 flex-col border-r border-slate-300/60 bg-white/70 backdrop-blur-xl p-3.5 shrink-0 overflow-y-auto custom-scrollbar justify-between">
        <div className="space-y-3.5">
          {/* Header & Status */}
          <div className="flex items-center justify-between pb-2 border-b border-slate-200/60">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-600" />
              <h4 className="text-xs font-bold text-slate-900 tracking-tight">
                Live Asset Context
              </h4>
            </div>
            <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200/80 px-2 py-0.5 rounded-full">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Synced
            </span>
          </div>

          {/* Optional Back to Dashboard Navigation */}
          {onNavigateToDashboard && (
            <button
              type="button"
              onClick={onNavigateToDashboard}
              className="apple-press flex w-full items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer shadow-2xs"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to Dashboard</span>
            </button>
          )}

          {/* Machine Selector Dropdown */}
          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Pinned Machine
            </label>
            <select
              value={selectedMachineId}
              onChange={(e) => setSelectedMachineId(e.target.value)}
              className="apple-press w-full rounded-xl border border-slate-200/90 bg-white px-3 py-2 text-xs font-bold text-slate-800 shadow-2xs focus:outline-none focus:border-blue-500 cursor-pointer transition-all"
            >
              {machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.code})
                </option>
              ))}
            </select>
          </div>

          {/* Telemetry Snapshot Card */}
          <div className="apple-card rounded-2xl p-3.5 space-y-3 bg-white/95 border border-slate-200/80 shadow-2xs">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-900 block">
                  {currentMachine.name}
                </span>
                <span className="text-[10px] text-slate-400">
                  {currentMachine.type}
                </span>
              </div>
              <span
                className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                  currentMachine.healthStatus === 'Poor health'
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : currentMachine.healthStatus === 'Attention needed'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {currentMachine.healthStatus}
              </span>
            </div>

            {/* 2x2 Telemetry Grid */}
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded-xl bg-slate-50/90 p-2.5 border border-slate-100">
                <span className="text-slate-400 text-[10px] font-medium block">Vibration</span>
                <span className={`font-bold text-xs ${isVibAlert ? 'text-rose-600' : 'text-slate-800'}`}>
                  {latestVib} mm/s
                </span>
                <span className="text-[9px] text-slate-400 block mt-0.5">
                  {isVibAlert ? 'Zone D Breach' : 'ISO Zone B'}
                </span>
              </div>

              <div className="rounded-xl bg-slate-50/90 p-2.5 border border-slate-100">
                <span className="text-slate-400 text-[10px] font-medium block">Temperature</span>
                <span className="font-bold text-xs text-blue-600">
                  {latestTemp}°C
                </span>
                <span className="text-[9px] text-slate-400 block mt-0.5">
                  Thermal Head
                </span>
              </div>

              <div className="rounded-xl bg-slate-50/90 p-2.5 border border-slate-100">
                <span className="text-slate-400 text-[10px] font-medium block">Health Score</span>
                <span className="font-bold text-xs text-emerald-600">
                  {currentMachine.healthPercentage.toFixed(1)}%
                </span>
                <span className="text-[9px] text-slate-400 block mt-0.5">
                  Degradation Ind.
                </span>
              </div>

              <div className="rounded-xl bg-slate-50/90 p-2.5 border border-slate-100">
                <span className="text-slate-400 text-[10px] font-medium block">Operating Speed</span>
                <span className="font-bold text-xs text-slate-800">
                  {currentMachine.metrics.rpm} RPM
                </span>
                <span className="text-[9px] text-slate-400 block mt-0.5">
                  Rotational
                </span>
              </div>
            </div>

            {/* Machine Analytics Launch Button */}
            <button
              type="button"
              onClick={() => onOpenMachineAnalytics?.(currentMachine)}
              className="apple-press w-full flex items-center justify-center gap-1.5 rounded-xl bg-slate-100 py-2 text-center text-[11px] font-bold text-blue-700 hover:bg-blue-50 hover:text-blue-800 transition-colors cursor-pointer border border-slate-200/60"
            >
              <Gauge className="h-3.5 w-3.5 text-blue-600" />
              <span>Open Machine Analytics</span>
            </button>
          </div>

          {/* Context Pinning Info Box */}
          <div className="text-[10px] text-slate-500 space-y-1 leading-relaxed bg-slate-100/60 p-3 rounded-2xl border border-slate-200/50">
            <div className="flex items-center gap-1.5 font-bold text-slate-700">
              <Radio className="h-3 w-3 text-blue-500" />
              <span>AI Context Pinning</span>
            </div>
            <p className="text-slate-500">
              Diagnostic queries automatically reference real-time telemetry, ISO 10816 limits, and vibration spectra for <span className="font-semibold text-slate-700">{currentMachine.name}</span>.
            </p>
          </div>

          {/* AI Specialist Selector in Left Panel */}
          <div>
            <div className="flex items-center justify-between pb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
              <span>Diagnostic Specialist</span>
              <Sparkles className="h-3 w-3 text-blue-500" />
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {AI_PERSONAS.map((persona) => {
                const isSelected = activePersonaId === persona.id
                return (
                  <button
                    key={persona.id}
                    type="button"
                    onClick={() => setActivePersonaId(persona.id)}
                    className={`apple-press flex flex-col items-start p-2 rounded-xl border text-left transition-all cursor-pointer ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50/80 shadow-2xs ring-1 ring-blue-400/30'
                        : 'border-slate-200/80 bg-white/80 hover:border-slate-300 hover:bg-white'
                    }`}
                  >
                    <span className="text-sm mb-0.5">{persona.avatar}</span>
                    <span className="text-[10px] font-bold text-slate-800 leading-tight">
                      {persona.name}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="pt-3 border-t border-slate-200/60 text-[10px] text-slate-400 flex items-center justify-between">
          <span>Mistranics Copilot</span>
          <span>v2.4 Ready</span>
        </div>
      </div>

      {/* 2. MAIN CHAT WORKSPACE (Right section is kept completely empty: clean breathing room!) */}
      <div className="flex flex-1 min-h-0 flex-col overflow-hidden bg-transparent">
        {/* Workspace Header */}
        <div className="flex h-14 items-center justify-between border-b border-slate-300/60 bg-white/70 backdrop-blur-xl px-4 sm:px-6 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white text-base shadow-sm">
              {currentPersona.avatar}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xs sm:text-sm font-bold text-slate-900">
                  {currentPersona.name}
                </h3>
                <span className="rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 px-2 py-0.2 text-[9px] font-bold">
                  Active
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                {currentPersona.title} • Target: <span className="font-semibold text-slate-600">{currentMachine.name}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Tone Selector */}
            <div className="flex items-center gap-1.5 rounded-xl border border-slate-200/80 bg-white/90 px-2.5 py-1 text-xs shadow-2xs">
              <span className="text-slate-400 font-medium text-[11px]">Tone:</span>
              <select
                value={chatTone}
                onChange={(e) => setChatTone(e.target.value as ChatTone)}
                className="bg-transparent font-bold text-slate-700 focus:outline-none cursor-pointer text-xs"
              >
                <option value="Analytical">Analytical</option>
                <option value="Concise">Concise</option>
                <option value="Step-by-Step SOP">Step-by-Step SOP</option>
              </select>
            </div>

            {/* Reset / Clear Chat Button (returns to empty modern prompt screen) */}
            <button
              type="button"
              onClick={handleResetChat}
              className="apple-press inline-flex items-center gap-1.5 rounded-xl border border-slate-200/80 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer shadow-2xs"
              title="Reset conversation to initial prompt screen"
            >
              <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
              <span className="hidden sm:inline">New Prompt</span>
            </button>
          </div>
        </div>

        {/* Chat Feed / Messages Area */}
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 sm:p-6 space-y-4">
          {currentSession.messages.length === 0 ? (
            /* INITIAL STATE: Empty Modern & Minimal Chatbot Prompt Screen */
            <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto text-center px-4 py-8 animate-in fade-in duration-300">
              {/* Glowing Hero Icon Badge */}
              <div className="relative mb-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 text-white text-3xl shadow-lg shadow-blue-500/20 ring-4 ring-blue-100">
                  {currentPersona.avatar}
                </div>
                <Sparkles className="absolute -top-1.5 -right-1.5 h-5 w-5 text-amber-400 fill-amber-400 drop-shadow-sm animate-pulse" />
              </div>

              {/* Minimal Headline & Subtitle */}
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
                How can I assist with {currentMachine.name}?
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 max-w-md mt-2 leading-relaxed">
                Directly query real-time vibration spectra, ISO 10816 alarm thresholds, or step-by-step troubleshooting SOPs.
              </p>

              {/* Persona Switcher Chips */}
              <div className="flex flex-wrap items-center justify-center gap-1.5 mt-5">
                {AI_PERSONAS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setActivePersonaId(p.id)}
                    className={`apple-press inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                      activePersonaId === p.id
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'bg-white/80 text-slate-600 border border-slate-200/80 hover:bg-white hover:text-slate-900'
                    }`}
                  >
                    <span>{p.avatar}</span>
                    <span>{p.name}</span>
                  </button>
                ))}
              </div>

              {/* 4 Modern Diagnostic Prompt Suggestion Cards (2x2 Grid) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mt-7 text-left">
                {currentPersona.suggestedPrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSendMessage(prompt)}
                    className="apple-press group flex flex-col justify-between p-3.5 rounded-2xl border border-slate-200/90 bg-white/90 shadow-2xs hover:border-blue-400 hover:shadow-xs hover:bg-white transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-semibold text-slate-800 group-hover:text-blue-700 transition-colors leading-snug">
                        {prompt}
                      </span>
                      <ArrowRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-blue-600 group-hover:translate-x-0.5 shrink-0 mt-0.5 transition-all" />
                    </div>
                    <span className="text-[10px] text-slate-400 mt-2.5 font-medium group-hover:text-blue-500 transition-colors">
                      Run Diagnostic Routine →
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Active Working Prototype Message Bubbles */
            currentSession.messages.map((message) => {
              const isUser = message.sender === 'user'

              return (
                <div
                  key={message.id}
                  className={`flex gap-3 max-w-2xl ${
                    isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'
                  }`}
                >
                  {/* Avatar */}
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-bold shadow-xs ${
                      isUser
                        ? 'bg-slate-800 text-white'
                        : 'bg-blue-600 text-white'
                    }`}
                  >
                    {isUser ? <User className="h-4 w-4" /> : currentPersona.avatar}
                  </div>

                  {/* Message Bubble Card */}
                  <div
                    className={`apple-card rounded-2xl p-4 shadow-2xs text-xs leading-relaxed ${
                      isUser
                        ? 'bg-blue-600 text-white border-blue-600 shadow-blue-500/10'
                        : 'bg-white/95 text-slate-800 border border-slate-200/80'
                    }`}
                  >
                    {/* Assistant Metadata */}
                    {!isUser && message.machineContext && (
                      <div className="flex items-center gap-2 pb-2 mb-2 border-b border-slate-100 text-[10px] text-slate-400 font-medium">
                        <span className="font-bold text-slate-700">
                          {message.machineContext}
                        </span>
                        <span>•</span>
                        <span>{message.timestamp}</span>
                      </div>
                    )}

                    {/* Text Body */}
                    <div className="whitespace-pre-wrap font-medium">
                      {message.text}
                    </div>

                    {/* Telemetry Evidence Box */}
                    {!isUser && message.evidence && (
                      <div className="mt-3 rounded-xl border border-slate-200/80 bg-slate-50/80 p-2.5 space-y-1.5">
                        <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                          Telemetry Evidence
                        </span>
                        {message.evidence.map((ev, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between bg-white px-2.5 py-1 rounded-lg text-[11px] border border-slate-200/40"
                          >
                            <span className="text-slate-600 font-medium">{ev.metric}</span>
                            <span
                              className={`font-bold ${
                                ev.status === 'critical'
                                  ? 'text-rose-600'
                                  : ev.status === 'warning'
                                  ? 'text-amber-600'
                                  : 'text-emerald-600'
                              }`}
                            >
                              {ev.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Action Links */}
                    {!isUser && message.actionLinks && (
                      <div className="mt-3 pt-2 border-t border-slate-100 flex items-center gap-2">
                        {message.actionLinks.map((link, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              if (link.action === 'view_machine') {
                                onOpenMachineAnalytics?.(currentMachine)
                              }
                            }}
                            className="apple-press inline-flex items-center gap-1.5 rounded-lg bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700 hover:bg-blue-100 cursor-pointer"
                          >
                            <span>{link.label}</span>
                            <ExternalLink className="h-3 w-3" />
                          </button>
                        ))}
                      </div>
                    )}

                    {/* BotBuzz Reaction Toolbar (Thumbs Up, Down, Copy) */}
                    {!isUser && (
                      <div className="flex items-center justify-between pt-2.5 mt-2 border-t border-slate-100/80 text-slate-400">
                        <div className="flex items-center gap-1.5">
                          {/* BotBuzz Thumbs Up Icon */}
                          <button
                            type="button"
                            onClick={() => handleFeedback(message.id, 'up')}
                            className={`apple-press rounded-md p-1 hover:bg-slate-100 transition-colors cursor-pointer ${
                              message.feedback === 'up'
                                ? 'text-blue-600 bg-blue-50'
                                : 'text-slate-400'
                            }`}
                            title="Helpful response"
                          >
                            <svg
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                            </svg>
                          </button>

                          {/* BotBuzz Thumbs Down Icon */}
                          <button
                            type="button"
                            onClick={() => handleFeedback(message.id, 'down')}
                            className={`apple-press rounded-md p-1 hover:bg-slate-100 transition-colors cursor-pointer ${
                              message.feedback === 'down'
                                ? 'text-rose-600 bg-rose-50'
                                : 'text-slate-400'
                            }`}
                            title="Unhelpful response"
                          >
                            <svg
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
                            </svg>
                          </button>

                          {/* Copy Response Button */}
                          <button
                            type="button"
                            onClick={() => handleCopyMessage(message.text, message.id)}
                            className="apple-press rounded-md p-1 hover:bg-slate-100 transition-colors cursor-pointer"
                            title="Copy response"
                          >
                            {copiedMessageId === message.id ? (
                              <Check className="h-3.5 w-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="h-3.5 w-3.5 text-slate-400" />
                            )}
                          </button>
                        </div>

                        <span className="text-[10px] text-slate-400">
                          {message.timestamp}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })
          )}

          {/* Typing Indicator */}
          {isTyping && (
            <div className="flex gap-3 max-w-xl animate-in fade-in duration-150">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-600 text-white text-xs shadow-xs">
                {currentPersona.avatar}
              </div>
              <div className="apple-card rounded-2xl px-4 py-2.5 bg-white flex items-center gap-1.5 shadow-2xs border border-slate-200/80">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-bounce" />
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-bounce [animation-delay:0.2s]" />
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-bounce [animation-delay:0.4s]" />
                <span className="text-[11px] text-slate-500 font-semibold ml-1.5">
                  Synthesizing telemetry & ISO standards...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Bottom Search Prompt Bar */}
        <div className="p-3 sm:p-4 border-t border-slate-300/60 bg-white/70 backdrop-blur-xl shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSendMessage()
            }}
            className="flex items-center gap-2 rounded-2xl border border-slate-300/80 bg-white/95 px-3 py-1.5 shadow-xs focus-within:border-blue-500 focus-within:shadow-md transition-all max-w-4xl mx-auto"
          >
            {/* Attachment Button */}
            <button
              type="button"
              className="apple-press rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
              title="Attach telemetry log or screenshot"
            >
              <Paperclip className="h-4 w-4" />
            </button>

            {/* Input Field */}
            <input
              ref={inputRef}
              type="text"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              placeholder={`Ask ${currentPersona.name} about ${currentMachine.name} vibrations, ISO limits, or SOPs...`}
              className="flex-1 bg-transparent px-2 text-xs font-semibold text-slate-800 placeholder-slate-400 focus:outline-none"
            />

            {/* Microphone Button */}
            <button
              type="button"
              className="apple-press rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
              title="Voice prompt"
            >
              <Mic className="h-4 w-4" />
            </button>

            {/* Send Button */}
            <button
              type="submit"
              disabled={!inputPrompt.trim() || isTyping}
              className="apple-press flex h-7.5 w-7.5 items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs hover:bg-blue-700 disabled:opacity-40 transition-all cursor-pointer"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
