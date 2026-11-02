import React from 'react'
import {
  Layers,
  Loader2,
  Database,
  WifiOff,
  AlertOctagon,
  CheckCircle,
} from 'lucide-react'
import type { ApplicationState } from '../types/dashboard'

interface StateSwitcherProps {
  currentState: ApplicationState
  onChangeState: (state: ApplicationState) => void
}

export const StateSwitcher: React.FC<StateSwitcherProps> = ({
  currentState,
  onChangeState,
}) => {
  const states: { id: ApplicationState; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'normal', label: 'Normal Data', icon: CheckCircle },
    { id: 'loading', label: 'Loading', icon: Loader2 },
    { id: 'empty', label: 'Empty State', icon: Database },
    { id: 'disconnected', label: 'Disconnected', icon: WifiOff },
    { id: 'error', label: 'Error State', icon: AlertOctagon },
  ]

  return (
    <div className="fixed bottom-4 right-4 z-40 hidden sm:flex items-center gap-1 rounded-full border border-slate-300/80 bg-white/95 p-1.5 shadow-xl backdrop-blur-md text-xs select-none">
      <div className="flex items-center gap-1 px-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-r border-slate-200">
        <Layers className="h-3 w-3 text-blue-600" />
        <span>PRD State:</span>
      </div>

      <div className="flex items-center gap-1">
        {states.map((st) => {
          const Icon = st.icon
          const isActive = currentState === st.id

          return (
            <button
              key={st.id}
              type="button"
              onClick={() => onChangeState(st.id)}
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold transition-all cursor-pointer ${
                isActive
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
              title={`Switch prototype view to ${st.label} state (PRD Section 16)`}
            >
              <Icon className={`h-3 w-3 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span>{st.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
