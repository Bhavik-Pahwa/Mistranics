import React, { useState } from 'react'
import type { MachineAlertCount, TimeRange } from '../types/dashboard'

interface Part2AlertActivityProps {
  alertCounts: MachineAlertCount[]
  selectedRange: TimeRange
  onChangeRange: (range: TimeRange) => void
  onSelectMachine?: (machineId: string) => void
}

export const Part2AlertActivity: React.FC<Part2AlertActivityProps> = ({
  alertCounts,
  selectedRange,
  onChangeRange,
  onSelectMachine,
}) => {
  const [hoveredMachine, setHoveredMachine] = useState<MachineAlertCount | null>(null)
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null)

  const maxCount = Math.max(
    ...alertCounts.map((m) => m.counts[selectedRange]),
    10
  )
  const yCeil = Math.ceil((maxCount + 2) / 5) * 5
  const yTicks = [0, Math.round(yCeil * 0.25), Math.round(yCeil * 0.5), Math.round(yCeil * 0.75), yCeil]

  const width = 450
  const height = 210
  const padLeft = 30
  const padRight = 16
  const padTop = 18
  const padBottom = 26

  const chartW = width - padLeft - padRight
  const chartH = height - padTop - padBottom

  const barWidth = 16
  const totalSlots = alertCounts.length
  const slotWidth = chartW / Math.max(totalSlots, 1)

  return (
    <div className="relative flex h-full flex-col rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-xs transition-all overflow-hidden select-none">
      {/* Header: Title & Time Filter (Clean and professional) */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <h2 className="text-sm font-bold text-slate-900 tracking-tight">
          Alert Activity
        </h2>

        {/* Time Filter Pills: 24H, 7D, 30D */}
        <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
          <button
            type="button"
            onClick={() => onChangeRange('24h')}
            className={`rounded px-2.5 py-0.5 text-[10px] font-semibold transition-all cursor-pointer ${
              selectedRange === '24h'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            24H
          </button>
          <button
            type="button"
            onClick={() => onChangeRange('week')}
            className={`rounded px-2.5 py-0.5 text-[10px] font-semibold transition-all cursor-pointer ${
              selectedRange === 'week'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            7D
          </button>
          <button
            type="button"
            onClick={() => onChangeRange('month')}
            className={`rounded px-2.5 py-0.5 text-[10px] font-semibold transition-all cursor-pointer ${
              selectedRange === 'month'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            30D
          </button>
        </div>
      </div>

      {/* Bar Chart Area (Takes remaining quadrant height with breathing room) */}
      <div className="relative flex-1 min-h-0 w-full pt-1">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-full w-full select-none"
          preserveAspectRatio="none"
        >
          {/* Horizontal Gridlines & Y-axis Labels */}
          {yTicks.map((tick) => {
            const y = padTop + chartH - (tick / yCeil) * chartH
            return (
              <g key={`y-tick-${tick}`}>
                <line
                  x1={padLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  stroke="#f8fafc"
                  strokeWidth="1"
                />
                <text
                  x={padLeft - 6}
                  y={y + 3}
                  fill="#94a3b8"
                  fontSize="9"
                  fontFamily="system-ui, sans-serif"
                  fontWeight="600"
                  textAnchor="end"
                >
                  {tick}
                </text>
              </g>
            )
          })}

          {/* Machine Bars */}
          {alertCounts.map((item, idx) => {
            const count = item.counts[selectedRange]
            const barH = (count / yCeil) * chartH
            const slotCenter = padLeft + idx * slotWidth + slotWidth / 2
            const barX = slotCenter - barWidth / 2
            const barY = padTop + chartH - barH
            const isHovered = hoveredMachine?.machineId === item.machineId

            return (
              <g
                key={item.machineId}
                className="cursor-pointer transition-opacity"
                onClick={() => onSelectMachine && onSelectMachine(item.machineId)}
                onMouseEnter={() => {
                  setHoveredMachine(item)
                  setTooltipPos({ x: slotCenter, y: barY })
                }}
                onMouseLeave={() => {
                  setHoveredMachine(null)
                  setTooltipPos(null)
                }}
              >
                {/* Column highlight on hover */}
                {isHovered && (
                  <rect
                    x={slotCenter - slotWidth / 2 + 1}
                    y={padTop}
                    width={slotWidth - 2}
                    height={chartH}
                    fill="#f8fafc"
                    rx="4"
                  />
                )}

                {/* Narrow Bar with Rounded Top */}
                <rect
                  x={barX}
                  y={barY}
                  width={barWidth}
                  height={Math.max(barH, 3)}
                  rx="3"
                  fill={item.color}
                  className="transition-all duration-200"
                  style={{
                    filter: isHovered
                      ? 'drop-shadow(0px 3px 4px rgba(0,0,0,0.12))'
                      : 'none',
                  }}
                />

                {/* Count value directly above bar */}
                <text
                  x={slotCenter}
                  y={barY - 4}
                  fill={item.color}
                  fontSize="9"
                  fontFamily="system-ui, sans-serif"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  {count}
                </text>

                {/* X-axis Machine Label */}
                <text
                  x={slotCenter}
                  y={height - 6}
                  fill={isHovered ? '#0f172a' : '#64748b'}
                  fontSize="9"
                  fontFamily="system-ui, sans-serif"
                  fontWeight={isHovered ? 'bold' : '500'}
                  textAnchor="middle"
                >
                  {item.machineCode}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredMachine && tooltipPos && (
          <div
            className="pointer-events-none absolute z-30 rounded-lg border border-slate-200 bg-white/95 px-2.5 py-1.5 shadow-md text-[10px] transition-all -translate-x-1/2 -translate-y-full mb-2"
            style={{
              left: `${(tooltipPos.x / width) * 100}%`,
              top: `${(tooltipPos.y / height) * 100}%`,
            }}
          >
            <div className="flex items-center gap-1.5 font-bold text-slate-900 border-b border-slate-100 pb-0.5 mb-0.5">
              <span
                className="h-1.5 w-1.5 rounded-full inline-block"
                style={{ backgroundColor: hoveredMachine.color }}
              />
              <span>{hoveredMachine.machineName}</span>
              <span className="text-slate-400">({hoveredMachine.machineCode})</span>
            </div>
            <div className="font-semibold text-slate-700">
              {hoveredMachine.counts[selectedRange]} alerts logged
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
