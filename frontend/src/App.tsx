import React, { useState, useEffect, useRef } from 'react'
import { Sidebar } from './components/Sidebar'
import type { NavItemKey } from './components/Sidebar'
import { FloatingSearchBar } from './components/FloatingSearchBar'
import { Part1SensorTrends } from './components/Part1SensorTrends'
import { Part3MachineOverview } from './components/Part3MachineOverview'
import { Part4ActiveAlerts } from './components/Part4ActiveAlerts'
import { ChatbotView } from './components/ChatbotView'
import { MachineAnalyticsModal } from './components/MachineAnalyticsModal'
import { SearchDialog } from './components/SearchDialog'

import {
  SAMPLE_MACHINES,
  INITIAL_ACTIVE_ALERTS,
  SAMPLE_INVESTIGATIONS,
} from './data/sampleData'
import type {
  Machine,
  Alert,
  InvestigationRecord,
} from './types/dashboard'
import { Sparkles } from 'lucide-react'

export const App: React.FC = () => {
  // Shell Navigation State (Default collapsed)
  const [isSidebarExpanded, setIsSidebarExpanded] = useState<boolean>(false)
  const [activeNav, setActiveNav] = useState<NavItemKey>('dashboard')
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false)

  // Core Data State
  const [machines] = useState<Machine[]>(SAMPLE_MACHINES)
  const [alerts, setAlerts] = useState<Alert[]>(INITIAL_ACTIVE_ALERTS)
  const [, setInvestigations] = useState<InvestigationRecord[]>(
    SAMPLE_INVESTIGATIONS
  )

  // Part 1: Carousel State
  const [selectedMachineIndex, setSelectedMachineIndex] = useState<number>(0)
  const [isAutoCycling, setIsAutoCycling] = useState<boolean>(true)
  const autoCycleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Machine Analytics Modal State
  const [selectedMachineForAnalytics, setSelectedMachineForAnalytics] =
    useState<Machine | null>(null)

  // Tactile Toast Feedback State
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  const showToast = (message: string) => {
    setToastMessage(message)
    setTimeout(() => {
      setToastMessage(null)
    }, 2800)
  }

  // Auto-advance telemetry carousel every 5s until manual interaction (only when on dashboard)
  useEffect(() => {
    if (!isAutoCycling || machines.length <= 1 || activeNav !== 'dashboard') {
      if (autoCycleTimerRef.current) {
        clearInterval(autoCycleTimerRef.current)
        autoCycleTimerRef.current = null
      }
      return
    }

    autoCycleTimerRef.current = setInterval(() => {
      setSelectedMachineIndex((prev) => (prev + 1) % machines.length)
    }, 5000)

    return () => {
      if (autoCycleTimerRef.current) {
        clearInterval(autoCycleTimerRef.current)
        autoCycleTimerRef.current = null
      }
    }
  }, [isAutoCycling, machines.length, activeNav])

  // Manual navigation permanently stops auto-cycling for the session
  const handleManualNavigate = (direction: 'prev' | 'next') => {
    if (isAutoCycling) {
      setIsAutoCycling(false)
    }

    setSelectedMachineIndex((prev) => {
      if (direction === 'prev') {
        return prev === 0 ? machines.length - 1 : prev - 1
      } else {
        return (prev + 1) % machines.length
      }
    })
  }

  // Global Keyboard Shortcuts (Ctrl+K / Cmd+K for Spotlight search)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setIsSearchOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Alert Resolution: immediate dismissal, logs to investigation
  const handleResolveAlert = (alertId: string) => {
    const alertToResolve = alerts.find((a) => a.id === alertId)
    if (!alertToResolve) return

    setAlerts((prev) =>
      prev.map((a) =>
        a.id === alertId
          ? {
              ...a,
              status: 'resolved',
              resolvedAt: new Date().toISOString(),
            }
          : a
      )
    )

    setInvestigations((prev) =>
      prev.map((inv) =>
        inv.id === alertToResolve.investigationId
          ? {
              ...inv,
              status: 'Closed',
              lastUpdated: new Date().toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              }),
              resolutionLog: [
                ...inv.resolutionLog,
                `Resolved by technician: "${alertToResolve.title}" at ${new Date().toLocaleTimeString()}.`,
              ],
            }
          : inv
      )
    )

    showToast(`Alert resolved. Logged to #${alertToResolve.investigationId}`)
  }

  const handleOpenInvestigation = (investigationId: string, alert: Alert) => {
    showToast(`Opening Investigation #${investigationId} (${alert.machineName})`)
  }

  const activeAlertsCount = alerts.filter((a) => a.status === 'active').length

  return (
    <div className="dashboard-ambient-bg flex h-screen max-h-screen w-screen overflow-hidden font-sans text-slate-800 select-none">
      {/* Collapsible Sidebar with Integrated Hamburger Button */}
      <Sidebar
        isExpanded={isSidebarExpanded}
        onToggle={() => setIsSidebarExpanded((prev) => !prev)}
        activeNav={activeNav}
        onSelectNav={(key) => {
          setActiveNav(key)
          if (key === 'dashboard') {
            showToast('Switched to Operational Dashboard')
          } else if (key === 'chatbot') {
            showToast('Switched to Mistranics AI Diagnostic Chat')
          } else {
            showToast(`Navigated to ${key.toUpperCase()}`)
          }
        }}
      />

      {/* Main Full-Height Workspace (Strict 100vh Single Sight) */}
      <main className="flex-1 min-h-0 p-3 sm:p-4 overflow-hidden flex flex-col">
        {/* Floating Spotlight Search Bar on top */}
        <FloatingSearchBar
          onOpenSearch={() => setIsSearchOpen(true)}
          totalMachines={machines.length}
          activeAlertsCount={activeAlertsCount}
        />

        {/* View Switcher: Dashboard View vs Chatbot View */}
        {activeNav === 'chatbot' ? (
          <div className="flex-1 min-h-0 h-full pt-1 overflow-hidden">
            <ChatbotView
              machines={machines}
              onOpenMachineAnalytics={(m) => setSelectedMachineForAnalytics(m)}
              onNavigateToDashboard={() => setActiveNav('dashboard')}
            />
          </div>
        ) : (
          /* Operational Dashboard Layout */
          <div className="flex flex-col lg:flex-row gap-3 sm:gap-4 flex-1 min-h-0 h-full pt-1">
            {/* Left Column (60% width): Sensor Trends (50%) + Priority Machines (50%) */}
            <div className="flex flex-col gap-3 sm:gap-4 w-full lg:w-[60%] h-full min-h-0">
              {/* Part 1: Upper-left (50% height) */}
              <div className="flex-1 min-h-0 h-1/2">
                <Part1SensorTrends
                  machines={machines}
                  selectedMachineIndex={selectedMachineIndex}
                  onSelectMachineIndex={(idx) => {
                    setIsAutoCycling(false)
                    setSelectedMachineIndex(idx)
                  }}
                  onManualNavigate={handleManualNavigate}
                />
              </div>

              {/* Part 3: Lower-left (50% height) */}
              <div className="flex-1 min-h-0 h-1/2">
                <Part3MachineOverview
                  machines={machines}
                  onOpenMachineAnalytics={(machine) =>
                    setSelectedMachineForAnalytics(machine)
                  }
                />
              </div>
            </div>

            {/* Right Column (40% width): Full-Height Active Alerts & Triage */}
            <div className="w-full lg:w-[40%] h-full min-h-0">
              <Part4ActiveAlerts
                alerts={alerts}
                onResolveAlert={handleResolveAlert}
                onOpenInvestigation={handleOpenInvestigation}
              />
            </div>
          </div>
        )}
      </main>

      {/* Machine Analytics Floating Workspace */}
      <MachineAnalyticsModal
        machine={selectedMachineForAnalytics}
        onClose={() => setSelectedMachineForAnalytics(null)}
        onOpenInvestigation={(name) => {
          showToast(`Opening investigation dossier for ${name}...`)
        }}
      />

      {/* Interactive Global Search Dialog */}
      <SearchDialog
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        machines={machines}
        alerts={alerts}
        onSelectMachine={(m) => setSelectedMachineForAnalytics(m)}
        onSelectAlert={(a) => {
          showToast(`Selected alert: ${a.title}`)
        }}
      />

      {/* Tactile Micro-Toast */}
      {toastMessage && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-900/90 px-3.5 py-1.5 text-xs font-semibold text-white shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-bottom-2 duration-200">
          <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  )
}

export default App
