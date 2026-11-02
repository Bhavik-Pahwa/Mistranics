import React, { useEffect, useState } from 'react'
import {
  X,
  Gauge,
  Thermometer,
  Zap,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Flame,
  CheckCircle2,
  PlayCircle,
} from 'lucide-react'
import type { Machine } from '../types/dashboard'

interface MachineAnalyticsModalProps {
  machine: Machine | null
  onClose: () => void
  onOpenInvestigation?: (machineName: string) => void
}

export const MachineAnalyticsModal: React.FC<MachineAnalyticsModalProps> = ({
  machine,
  onClose,
  onOpenInvestigation,
}) => {
  const [activeTab, setActiveTab] = useState<'telemetry' | 'subsystems' | 'diagnostics'>('telemetry')
  const [isRunningDiagnostic, setIsRunningDiagnostic] = useState(false)
  const [diagnosticResult, setDiagnosticResult] = useState<string | null>(null)

  useEffect(() => {
    if (!machine) return

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = originalOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [machine, onClose])

  if (!machine) return null

  const handleRunDiagnostics = () => {
    setIsRunningDiagnostic(true)
    setDiagnosticResult(null)
    setTimeout(() => {
      setIsRunningDiagnostic(false)
      setDiagnosticResult(
        `Dynamic self-test complete for ${machine.name}: Inverter phase balance OK (99.2%). Radial bearing vibration RMS within elevated advisory zone (${machine.telemetry[machine.telemetry.length - 1]?.vibration || 6.2} mm/s). Recommended lubrication inspection.`
      )
    }, 1000)
  }

  const getStatusBadge = () => {
    switch (machine.healthStatus) {
      case 'Healthy':
        return {
          bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
          icon: ShieldCheck,
          label: 'Healthy Operation',
        }
      case 'Attention needed':
        return {
          bg: 'bg-amber-50 text-amber-700 border-amber-200',
          icon: AlertTriangle,
          label: 'Attention Needed',
        }
      case 'Poor health':
        return {
          bg: 'bg-rose-50 text-rose-700 border-rose-200',
          icon: Flame,
          label: 'Critical Intervention',
        }
    }
  }

  const statusBadge = getStatusBadge()
  const StatusIcon = statusBadge.icon

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-md p-4 sm:p-6 animate-in fade-in duration-200 select-none"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-machine-title"
      onClick={onClose}
    >
      {/* Floating Workspace Shell with Apple-style Material */}
      <div
        className="relative flex flex-col w-full max-w-4xl max-h-[85vh] rounded-3xl border border-slate-300/80 bg-white/95 backdrop-blur-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200/80 bg-slate-50/60 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white shadow-sm font-bold text-sm">
              {machine.code.slice(0, 3)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2
                  id="modal-machine-title"
                  className="text-base font-bold text-slate-900"
                >
                  {machine.name}
                </h2>
                <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-bold text-slate-700">
                  {machine.code}
                </span>
                <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-[10px] font-bold text-blue-700">
                  P{machine.priority}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {machine.type} • {machine.location}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold border ${statusBadge.bg}`}
            >
              <StatusIcon className="h-3.5 w-3.5" />
              {machine.healthPercentage.toFixed(1)}% ({statusBadge.label})
            </span>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close machine analytics workspace"
              className="apple-press inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-slate-200 hover:text-slate-800 transition-colors cursor-pointer"
              title="Close workspace (Esc)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Workspace Navigation Tabs */}
        <div className="flex border-b border-slate-200 bg-white/50 px-6">
          <button
            type="button"
            onClick={() => setActiveTab('telemetry')}
            className={`apple-press border-b-2 py-3 px-4 text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'telemetry'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Telemetry & Sensor Stream
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('subsystems')}
            className={`apple-press border-b-2 py-3 px-4 text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'subsystems'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Subsystem Health
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('diagnostics')}
            className={`apple-press border-b-2 py-3 px-4 text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'diagnostics'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Diagnostics
          </button>
        </div>

        {/* Scrollable Content Area */}
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar bg-slate-50/40">
          {activeTab === 'telemetry' && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
                <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="text-[11px] font-semibold">Drive Speed</span>
                    <Zap className="h-4 w-4 text-amber-500" />
                  </div>
                  <div className="text-lg font-bold text-slate-900">
                    {machine.metrics.rpm.toLocaleString()}{' '}
                    <span className="text-xs font-normal text-slate-400">RPM</span>
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="text-[11px] font-semibold">Discharge Pressure</span>
                    <Gauge className="h-4 w-4 text-blue-500" />
                  </div>
                  <div className="text-lg font-bold text-slate-900">
                    {machine.metrics.pressureBar.toFixed(1)}{' '}
                    <span className="text-xs font-normal text-slate-400">bar</span>
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="text-[11px] font-semibold">Lube Oil Temp</span>
                    <Thermometer className="h-4 w-4 text-rose-500" />
                  </div>
                  <div className="text-lg font-bold text-slate-900">
                    {machine.metrics.lubeOilTemp.toFixed(1)}{' '}
                    <span className="text-xs font-normal text-slate-400">°C</span>
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="text-[11px] font-semibold">Service Hours</span>
                    <Clock className="h-4 w-4 text-indigo-500" />
                  </div>
                  <div className="text-lg font-bold text-slate-900">
                    {machine.metrics.runtimeHours.toLocaleString()}{' '}
                    <span className="text-xs font-normal text-slate-400">hrs</span>
                  </div>
                </div>
              </div>

              {/* Telemetry Snapshot Table */}
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                <h3 className="text-xs font-bold text-slate-900 mb-3">
                  Telemetry Snapshot Log
                </h3>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-100 text-[10px] font-bold uppercase text-slate-400">
                        <th className="py-2 px-3">Time</th>
                        <th className="py-2 px-3">Vibration (mm/s)</th>
                        <th className="py-2 px-3">Temperature (°C)</th>
                        <th className="py-2 px-3">Health Score</th>
                        <th className="py-2 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-medium">
                      {machine.telemetry.map((pt, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/80">
                          <td className="py-2 px-3 text-slate-600">{pt.time}</td>
                          <td className="py-2 px-3 text-rose-600 font-bold">{pt.vibration} mm/s</td>
                          <td className="py-2 px-3 text-blue-600 font-bold">{pt.temperature} °C</td>
                          <td className="py-2 px-3 text-emerald-600 font-bold">{pt.health}%</td>
                          <td className="py-2 px-3">
                            {pt.vibration > 6 ? (
                              <span className="rounded bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-600">
                                Warning
                              </span>
                            ) : (
                              <span className="rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-600">
                                Nominal
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'subsystems' && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-4">
              <h3 className="text-xs font-bold text-slate-900">
                Subassembly Degradation Indices
              </h3>
              <div className="space-y-3.5">
                {machine.subsystems.map((sub, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-800">{sub.name}</span>
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                            sub.status === 'Normal'
                              ? 'bg-emerald-50 text-emerald-700'
                              : sub.status === 'Degraded'
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-rose-50 text-rose-700'
                          }`}
                        >
                          {sub.status}
                        </span>
                        <span className="font-bold text-slate-900">{sub.health}%</span>
                      </div>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          sub.health >= 80
                            ? 'bg-emerald-500'
                            : sub.health >= 60
                            ? 'bg-amber-500'
                            : 'bg-rose-500'
                        }`}
                        style={{ width: `${sub.health}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'diagnostics' && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-900">
                  Live Anomaly Self-Test
                </h3>
                <button
                  type="button"
                  onClick={handleRunDiagnostics}
                  disabled={isRunningDiagnostic}
                  className="apple-press inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 shadow-xs cursor-pointer"
                >
                  <PlayCircle className="h-4 w-4" />
                  {isRunningDiagnostic ? 'Testing...' : 'Run Diagnostics'}
                </button>
              </div>

              {diagnosticResult && (
                <div className="rounded-lg border border-blue-200 bg-blue-50/80 p-3 text-xs text-blue-900 animate-in fade-in">
                  <div className="flex items-center gap-1.5 font-bold mb-1">
                    <CheckCircle2 className="h-4 w-4 text-blue-600" />
                    Self-Test Results
                  </div>
                  <p>{diagnosticResult}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50/80 px-6 py-3 text-xs">
          <button
            type="button"
            onClick={onClose}
            className="apple-press rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer"
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => {
              onClose()
              if (onOpenInvestigation) onOpenInvestigation(machine.name)
            }}
            className="apple-press rounded-lg bg-blue-600 px-3.5 py-1.5 font-semibold text-white hover:bg-blue-700 shadow-xs cursor-pointer"
          >
            Open Investigation
          </button>
        </div>
      </div>
    </div>
  )
}
