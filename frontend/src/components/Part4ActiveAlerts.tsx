import React, { useState } from 'react'
import {
  AlertOctagon,
  AlertTriangle,
  Info,
  CheckCircle2,
  X,
  ExternalLink,
  ChevronDown,
  Wrench,
  CheckSquare,
  ClipboardList,
} from 'lucide-react'
import type { Alert, AlertSeverity } from '../types/dashboard'

interface Part4ActiveAlertsProps {
  alerts: Alert[]
  onResolveAlert: (alertId: string) => void
  onOpenInvestigation: (investigationId: string, alert: Alert) => void
}

export const Part4ActiveAlerts: React.FC<Part4ActiveAlertsProps> = ({
  alerts,
  onResolveAlert,
  onOpenInvestigation,
}) => {
  const [expandedAlertId, setExpandedAlertId] = useState<string | null>(null)

  const activeAlerts = alerts.filter((a) => a.status === 'active')

  const toggleExpand = (alertId: string) => {
    setExpandedAlertId((prev) => (prev === alertId ? null : alertId))
  }

  const getSeverityStyle = (severity: AlertSeverity) => {
    switch (severity) {
      case 'Critical':
        return {
          border: 'border-l-4 border-l-rose-500',
          badge: 'bg-rose-50 text-rose-700 border-rose-200/80',
          icon: AlertOctagon,
          iconColor: 'text-rose-500',
        }
      case 'High':
        return {
          border: 'border-l-4 border-l-amber-500',
          badge: 'bg-amber-50 text-amber-700 border-amber-200/80',
          icon: AlertTriangle,
          iconColor: 'text-amber-500',
        }
      case 'Moderate':
        return {
          border: 'border-l-4 border-l-blue-500',
          badge: 'bg-blue-50 text-blue-700 border-blue-200/80',
          icon: Info,
          iconColor: 'text-blue-500',
        }
    }
  }

  return (
    <div className="apple-card relative flex h-full flex-col rounded-2xl p-4 shadow-sm transition-all overflow-hidden select-none">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-200/70 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">
            Active Alerts & Triage
          </h2>
          <span className="flex h-5 items-center rounded-full bg-rose-50 px-2 text-[10px] font-bold text-rose-600 ring-1 ring-rose-200">
            {activeAlerts.length} OPEN
          </span>
        </div>

        <span className="text-[11px] text-slate-400 font-medium">
          Priority Queue
        </span>
      </div>

      {/* Full-Height Scrollable Alerts List */}
      <div className="flex-1 min-h-0 space-y-2.5 py-3 overflow-y-auto custom-scrollbar pr-1">
        {activeAlerts.length === 0 ? (
          <div className="flex h-full min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300/80 bg-white/40 p-6 text-center animate-in fade-in duration-200">
            <CheckCircle2 className="h-8 w-8 text-emerald-500 mb-2" />
            <p className="text-xs font-bold text-slate-700">
              All Active Alerts Resolved
            </p>
            <p className="text-[11px] text-slate-400 max-w-xs mt-1">
              Zero active anomaly events requiring engineering intervention.
            </p>
          </div>
        ) : (
          activeAlerts.map((alert) => {
            const isExpanded = expandedAlertId === alert.id
            const severity = getSeverityStyle(alert.severity)
            const SeverityIcon = severity.icon

            return (
              <div
                key={alert.id}
                className={`group rounded-xl border border-slate-200/80 bg-white/90 shadow-2xs transition-all duration-200 ${
                  severity.border
                } ${
                  isExpanded
                    ? 'ring-2 ring-blue-500/20 shadow-md bg-white'
                    : 'hover:border-slate-300 hover:shadow-xs hover:-translate-y-0.2'
                }`}
              >
                {/* Collapsed Alert Header / Preview */}
                {!isExpanded ? (
                  <div
                    onClick={() => toggleExpand(alert.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        toggleExpand(alert.id)
                      }
                    }}
                    className="apple-press cursor-pointer p-3 focus:outline-none"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                          {alert.machineName}
                        </span>
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-600">
                          {alert.machineCode}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold ${severity.badge}`}
                        >
                          <SeverityIcon className="h-3 w-3" />
                          {alert.severity}
                        </span>
                        <span className="text-[10px] font-medium text-slate-400">
                          {alert.detectedTime}
                        </span>
                      </div>
                    </div>

                    <p className="mt-1.5 text-xs font-semibold text-slate-800 leading-snug">
                      {alert.title}
                    </p>

                    <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                      <span className="truncate max-w-[88%] text-slate-600">
                        <strong className="text-slate-700">Check:</strong>{' '}
                        {alert.whatToCheckPreview}
                      </span>
                      <ChevronDown className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:translate-y-0.5" />
                    </div>
                  </div>
                ) : (
                  /* Expanded Alert View */
                  <div className="p-3.5 animate-in fade-in zoom-in-98 duration-200 text-xs">
                    {/* Expanded Header Controls */}
                    <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
                      <button
                        type="button"
                        onClick={() => onResolveAlert(alert.id)}
                        className="apple-press inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1 text-xs font-bold text-white hover:bg-emerald-700 shadow-xs transition-colors cursor-pointer"
                        title="Dismiss alert immediately"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Resolved
                      </button>

                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-800">
                          {alert.machineName}
                        </span>
                        <span
                          className={`rounded-md border px-2 py-0.5 text-[10px] font-bold ${severity.badge}`}
                        >
                          {alert.severity}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleExpand(alert.id)}
                        aria-label="Close expanded view"
                        className="apple-press rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>

                    {/* Problem Description */}
                    <div className="mt-2.5">
                      <h4 className="font-bold text-slate-900 text-xs">
                        {alert.title}
                      </h4>
                      <p className="mt-1 text-[11px] text-slate-600 leading-relaxed">
                        {alert.detailedExplanation}
                      </p>
                    </div>

                    {/* Supporting Telemetry Evidence */}
                    {alert.evidence && alert.evidence.length > 0 && (
                      <div className="mt-2.5 rounded-xl border border-slate-200/80 bg-slate-50/70 p-2.5">
                        <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                          Sensor Evidence
                        </span>
                        <div className="mt-1 space-y-1">
                          {alert.evidence.map((ev, idx) => (
                            <div
                              key={idx}
                              className="flex items-center justify-between text-[11px] text-slate-700 bg-white px-2.5 py-1 rounded-lg border border-slate-200/50"
                            >
                              <span className="font-medium text-slate-800">
                                {ev.metric}
                              </span>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-rose-600">
                                  {ev.observed}
                                </span>
                                <span className="text-slate-400 text-[10px]">
                                  (Threshold: {ev.threshold})
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* What to Check */}
                    <div className="mt-2.5">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900 mb-1">
                        <CheckSquare className="h-3.5 w-3.5 text-blue-600" />
                        <span>What to Check</span>
                      </div>
                      <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-600 pl-1">
                        {alert.whatToCheck.map((item, idx) => (
                          <li key={idx} className="leading-snug">
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Troubleshooting Steps */}
                    <div className="mt-2.5">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900 mb-1">
                        <Wrench className="h-3.5 w-3.5 text-blue-600" />
                        <span>Troubleshooting Steps</span>
                      </div>
                      <div className="space-y-1.5">
                        {alert.troubleshootingSteps.map((step) => (
                          <div
                            key={step.step}
                            className="flex items-start gap-2 rounded-lg bg-slate-50 p-2 text-[11px]"
                          >
                            <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-blue-600 text-[9px] font-bold text-white">
                              {step.step}
                            </span>
                            <div>
                              <p className="font-semibold text-slate-800">
                                {step.instruction}
                              </p>
                              <p className="text-slate-500 text-[10px] mt-0.5">
                                {step.detail}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Recommended Actions */}
                    <div className="mt-2.5">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900 mb-1">
                        <ClipboardList className="h-3.5 w-3.5 text-blue-600" />
                        <span>Recommended Actions</span>
                      </div>
                      <div className="space-y-1">
                        {alert.recommendedActions.map((action, idx) => (
                          <div
                            key={idx}
                            className="rounded-lg bg-blue-50/70 px-2.5 py-1 text-[11px] font-medium text-blue-900 border border-blue-100"
                          >
                            • {action}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Investigation Link */}
                    <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px]">
                      <span className="text-slate-400 font-medium">
                        Investigation #{alert.investigationId}
                      </span>
                      <button
                        type="button"
                        onClick={() => onOpenInvestigation(alert.investigationId, alert)}
                        className="apple-press inline-flex items-center gap-1 font-bold text-blue-600 hover:text-blue-800 cursor-pointer"
                      >
                        <span>Open Investigation</span>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
