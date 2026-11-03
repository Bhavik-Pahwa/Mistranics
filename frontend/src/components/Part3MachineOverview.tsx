import React, { useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  AlertTriangle,
  Flame,
} from 'lucide-react'
import type { Machine, MachineHealthStatus } from '../types/dashboard'

interface Part3MachineOverviewProps {
  machines: Machine[]
  onOpenMachineAnalytics: (machine: Machine) => void
}

/**
 * Animated SVG Circular Gauge for machine health indicator
 * Dynamically scales up in 3-card mode to occupy empty container space
 */
const CircularHealthIndicator: React.FC<{
  percentage: number
  isLarge?: boolean
}> = ({ percentage, isLarge = true }) => {
  const radius = isLarge ? 42 : 24
  const strokeWidth = isLarge ? 7 : 4.5
  const viewBoxSize = isLarge ? 100 : 60
  const center = viewBoxSize / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  const getColor = () => {
    if (percentage >= 80) return '#10b981' // Emerald
    if (percentage >= 60) return '#f59e0b' // Amber
    return '#f43f5e' // Rose
  }

  const strokeColor = getColor()

  return (
    <div className="relative flex items-center justify-center shrink-0">
      <svg
        className={`${
          isLarge ? 'h-26 w-26 sm:h-28 sm:w-28' : 'h-14 w-14'
        } -rotate-90 transform drop-shadow-2xs`}
        viewBox={`0 0 ${viewBoxSize} ${viewBoxSize}`}
      >
        {/* Subtle background track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          stroke="#f1f5f9"
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Animated active progress arc */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          fill="none"
          className="transition-all duration-1000 ease-[cubic-bezier(0.16,1,0.3,1)]"
        />
      </svg>

      {/* Central percentage display */}
      <div className="absolute flex flex-col items-center justify-center text-center">
        <span
          className={`${
            isLarge ? 'text-lg sm:text-xl font-black' : 'text-xs font-bold'
          } text-slate-800 tracking-tight`}
        >
          {percentage.toFixed(1)}%
        </span>
        {isLarge && (
          <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest -mt-0.5">
            Health
          </span>
        )}
      </div>
    </div>
  )
}

export const Part3MachineOverview: React.FC<Part3MachineOverviewProps> = ({
  machines,
  onOpenMachineAnalytics,
}) => {
  const [showAll, setShowAll] = useState(false)

  const sortedMachines = [...machines].sort((a, b) => a.priority - b.priority)
  const displayedMachines = showAll ? sortedMachines : sortedMachines.slice(0, 3)

  const getStatusBadge = (status: MachineHealthStatus) => {
    switch (status) {
      case 'Awaiting data':
        return { bg: 'bg-slate-50 text-slate-500 border-slate-200', icon: AlertTriangle, label: 'Awaiting data' }
      case 'Healthy':
        return {
          bg: 'bg-emerald-50 text-emerald-700 border-emerald-200/90',
          icon: ShieldCheck,
          label: 'Healthy',
        }
      case 'Attention needed':
        return {
          bg: 'bg-amber-50 text-amber-700 border-amber-200/90',
          icon: AlertTriangle,
          label: 'Attention',
        }
      case 'Poor health':
        return {
          bg: 'bg-rose-50 text-rose-700 border-rose-200/90',
          icon: Flame,
          label: 'Critical',
        }
    }
  }

  return (
    <div className="apple-card relative flex h-full flex-col rounded-2xl p-4 shadow-sm transition-all overflow-hidden select-none">
      {/* Header */}
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-200/70 shrink-0">
        <h2 className="text-sm font-bold text-slate-900 tracking-tight">
          Priority Machines
        </h2>

        <button
          type="button"
          onClick={() => setShowAll(!showAll)}
          className="apple-press inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold text-blue-600 hover:bg-blue-50/80 transition-all cursor-pointer"
        >
          {showAll ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              Top 3
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              All ({sortedMachines.length})
            </>
          )}
        </button>
      </div>

      {/* Cards Container */}
      <div className="flex-1 min-h-0 py-2 overflow-y-auto custom-scrollbar flex flex-col justify-center">
        <div
          className={`grid ${
            showAll ? 'grid-cols-1 sm:grid-cols-3 gap-2.5' : 'grid-cols-1 sm:grid-cols-3 gap-3.5'
          } h-full`}
        >
          {displayedMachines.map((machine) => {
            const badge = getStatusBadge(machine.healthStatus)
            const BadgeIcon = badge.icon
            const isLarge = !showAll

            return (
              <div
                key={machine.id}
                onClick={() => onOpenMachineAnalytics(machine)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onOpenMachineAnalytics(machine)
                  }
                }}
                className={`apple-press group relative flex flex-col justify-between rounded-xl border border-slate-200/80 border-t-2 border-t-blue-600 bg-white/90 p-3.5 shadow-2xs transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:border-blue-400/80 cursor-pointer ${
                  isLarge ? 'items-center text-center' : ''
                }`}
              >
                {/* Top: Name, Code & Priority Badge */}
                <div className="w-full flex items-start justify-between gap-1.5 shrink-0">
                  <div className="min-w-0 flex-1 text-left">
                    <h3 className="text-xs font-bold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                      {machine.name}
                    </h3>
                    <p className="text-[10px] text-slate-400 truncate mt-0.5">
                      {machine.code} · {machine.location.split('—')[0].trim()}
                    </p>
                  </div>

                  <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-600 shrink-0">
                    P{machine.priority}
                  </span>
                </div>

                {/* Middle: Prominently Scaled Circular Health Indicator */}
                <div
                  className={`my-auto py-1 flex items-center justify-center ${
                    isLarge ? 'w-full' : 'w-full justify-between'
                  }`}
                >
                  {machine.id === 'simulation-01' || !machine.telemetry.length ? <div className="motor-detection-status"><BadgeIcon size={28}/><strong>{machine.streamStatus || 'Awaiting data'}</strong><small>{machine.id === 'simulation-01' ? 'Statistical detection' : 'Registered machine'}</small></div> : <CircularHealthIndicator percentage={machine.healthPercentage} isLarge={isLarge}/>}

                  {!isLarge && (
                    <div className="flex flex-col items-end">
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold border ${badge.bg}`}
                      >
                        <BadgeIcon className="h-3 w-3" />
                        {badge.label}
                      </span>
                    </div>
                  )}
                </div>

                {/* Bottom: Centered Status Badge in 3-Card Mode */}
                {isLarge && (
                  <div className="w-full pt-1 flex items-center justify-center shrink-0">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-semibold border ${badge.bg} shadow-2xs`}
                    >
                      <BadgeIcon className="h-3 w-3" />
                      {badge.label}
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
