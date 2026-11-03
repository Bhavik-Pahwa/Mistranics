import React from 'react'
import { Search } from 'lucide-react'

interface FloatingSearchBarProps {
  onOpenSearch: () => void
  totalMachines: number
  activeAlertsCount: number
}

export const FloatingSearchBar: React.FC<FloatingSearchBarProps> = ({
  onOpenSearch,
  totalMachines,
  activeAlertsCount,
}) => {
  return (
    <div className="global-search-bar flex items-center justify-between gap-4 w-full pb-2.5 select-none">
      {/* Left: Quick System Status Chip */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 rounded-full bg-white/70 backdrop-blur-md border border-slate-200/80 px-3 py-1 shadow-2xs">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[11px] font-semibold text-slate-700 tracking-tight">
            Plant Alpha
          </span>
          <span className="text-slate-300">•</span>
          <span className="text-[11px] text-slate-500 font-medium">
            {totalMachines} Assets Monitored
          </span>
        </div>
      </div>

      {/* Center: Apple-style Floating Spotlight Search Pill */}
      <div
        onClick={onOpenSearch}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpenSearch()
          }
        }}
        aria-label="Search machines, alerts, investigations"
        className="apple-press group flex w-full max-w-md items-center justify-between rounded-full bg-white/80 backdrop-blur-xl border border-slate-300/70 px-3.5 py-1.5 shadow-xs hover:border-blue-400 hover:shadow-md hover:bg-white transition-all cursor-pointer"
      >
        <div className="flex items-center gap-2.5 flex-1">
          <Search className="h-3.5 w-3.5 text-slate-400 group-hover:text-blue-600 transition-colors" />
          <span className="text-xs text-slate-500 font-medium">
            Search machines, telemetry, alerts...
          </span>
        </div>

        <div className="flex items-center gap-1">
          <kbd className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[9px] font-semibold text-slate-400 shadow-2xs group-hover:border-blue-200 group-hover:text-blue-600 transition-colors">
            Ctrl K
          </kbd>
        </div>
      </div>

      {/* Right: Active Priority Status indicator */}
      <div className="flex items-center gap-2">
        <div
          className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold border backdrop-blur-md shadow-2xs transition-all ${
            activeAlertsCount > 0
              ? 'bg-rose-50/80 text-rose-700 border-rose-200'
              : 'bg-emerald-50/80 text-emerald-700 border-emerald-200'
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              activeAlertsCount > 0 ? 'bg-rose-500 animate-ping' : 'bg-emerald-500'
            }`}
          />
          <span>{activeAlertsCount} Active {activeAlertsCount === 1 ? 'Alert' : 'Alerts'}</span>
        </div>
      </div>
    </div>
  )
}
