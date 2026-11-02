import React, { useState } from 'react'
import { Search, X, Cpu, AlertTriangle, BookOpen, ArrowRight } from 'lucide-react'
import type { Machine, Alert } from '../types/dashboard'

interface SearchDialogProps {
  isOpen: boolean
  onClose: () => void
  machines: Machine[]
  alerts: Alert[]
  onSelectMachine: (machine: Machine) => void
  onSelectAlert: (alert: Alert) => void
}

export const SearchDialog: React.FC<SearchDialogProps> = ({
  isOpen,
  onClose,
  machines,
  alerts,
  onSelectMachine,
  onSelectAlert,
}) => {
  const [query, setQuery] = useState('')

  if (!isOpen) return null

  const filteredMachines = machines.filter(
    (m) =>
      m.name.toLowerCase().includes(query.toLowerCase()) ||
      m.code.toLowerCase().includes(query.toLowerCase()) ||
      m.type.toLowerCase().includes(query.toLowerCase())
  )

  const filteredAlerts = alerts.filter(
    (a) =>
      a.title.toLowerCase().includes(query.toLowerCase()) ||
      a.machineName.toLowerCase().includes(query.toLowerCase()) ||
      a.severity.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-slate-900/40 backdrop-blur-sm p-4 animate-in fade-in duration-150 select-none"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-2xl border border-slate-300/80 bg-white/95 backdrop-blur-2xl p-4 shadow-2xl animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 border-b border-slate-200/80 pb-3">
          <Search className="h-5 w-5 text-blue-600 shrink-0" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type machine name, code, or alert..."
            className="flex-1 text-sm font-semibold text-slate-800 placeholder-slate-400 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="apple-press rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results */}
        <div className="mt-3 max-h-80 overflow-y-auto space-y-3.5 custom-scrollbar text-xs">
          {/* Machines */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2">
              Machines ({filteredMachines.length})
            </span>
            <div className="mt-1 space-y-1">
              {filteredMachines.map((m) => (
                <div
                  key={m.id}
                  onClick={() => {
                    onSelectMachine(m)
                    onClose()
                  }}
                  className="apple-press flex items-center justify-between rounded-xl p-2.5 hover:bg-blue-50/70 cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <Cpu className="h-4 w-4 text-blue-600" />
                    <span className="font-bold text-slate-900">{m.name}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.2 text-[10px] font-semibold text-slate-600">
                      {m.code}
                    </span>
                    <span className="text-slate-400 text-[11px]">• {m.location}</span>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
                </div>
              ))}
            </div>
          </div>

          {/* Active Alerts */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2">
              Active Alerts ({filteredAlerts.length})
            </span>
            <div className="mt-1 space-y-1">
              {filteredAlerts.map((a) => (
                <div
                  key={a.id}
                  onClick={() => {
                    onSelectAlert(a)
                    onClose()
                  }}
                  className="apple-press flex items-center justify-between rounded-xl p-2.5 hover:bg-rose-50/70 cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <AlertTriangle className="h-4 w-4 text-rose-500" />
                    <div>
                      <span className="font-semibold text-slate-800">{a.title}</span>
                      <span className="text-[10px] text-slate-400 ml-2">
                        {a.machineName}
                      </span>
                    </div>
                  </div>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                      a.severity === 'Critical'
                        ? 'bg-rose-50 text-rose-600'
                        : 'bg-amber-50 text-amber-600'
                    }`}
                  >
                    {a.severity}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Manuals Reference */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2">
              Knowledge Manuals
            </span>
            <div className="mt-1 space-y-1">
              <div className="apple-press flex items-center justify-between rounded-xl p-2.5 hover:bg-slate-50 cursor-pointer">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold text-slate-800">
                    ISO 10816 Vibration Severity Standards Reference
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-medium">PDF • 4.2 MB</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
