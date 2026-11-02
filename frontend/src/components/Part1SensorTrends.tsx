import React, { useState, useRef } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Activity,
  Layers,
} from 'lucide-react'
import type { Machine, TelemetryPoint } from '../types/dashboard'
import { LiveTemperature } from './LiveTemperature'

interface Part1SensorTrendsProps {
  machines: Machine[]
  selectedMachineIndex: number
  onSelectMachineIndex: (index: number) => void
  onManualNavigate: (direction: 'prev' | 'next') => void
}

/**
 * Generates an ultra-smooth cubic bezier SVG path from coordinate points
 */
function generateSmoothCurve(points: { x: number; y: number }[]): string {
  if (points.length === 0) return ''
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`

  let path = `M ${points[0].x} ${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[i + 2 < points.length ? i + 2 : i + 1]

    const tension = 0.2
    const cp1x = p1.x + (p2.x - p0.x) * tension
    const cp1y = p1.y + (p2.y - p0.y) * tension
    const cp2x = p2.x - (p3.x - p1.x) * tension
    const cp2y = p2.y - (p3.y - p1.y) * tension

    path += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`
  }
  return path
}

export const Part1SensorTrends: React.FC<Part1SensorTrendsProps> = (props) => {
  const [live, setLive] = useState(true)
  return <div className="flex h-full min-h-0 flex-col gap-1">
    <div className="flex shrink-0 gap-2 text-[11px]">
      <button type="button" aria-pressed={live} onClick={() => setLive(true)}
        className={`rounded-md px-2 py-1 ${live ? 'bg-blue-100 font-bold text-blue-800' : 'text-slate-600'}`}>Live temperature</button>
      <button type="button" aria-pressed={!live} onClick={() => setLive(false)}
        className={`rounded-md px-2 py-1 ${!live ? 'bg-blue-100 font-bold text-blue-800' : 'text-slate-600'}`}>Demo machine trends</button>
    </div>
    <div className="min-h-0 flex-1">{live ? <LiveTemperature /> : <DemoSensorTrends {...props} />}</div>
  </div>
}

const DemoSensorTrends: React.FC<Part1SensorTrendsProps> = ({
  machines,
  selectedMachineIndex,
  onSelectMachineIndex,
  onManualNavigate,
}) => {
  const [chartMode, setChartMode] = useState<'area' | 'line'>('area')
  const [timeWindow, setTimeWindow] = useState<'24h' | '48h'>('24h')
  const [hoveredPoint, setHoveredPoint] = useState<TelemetryPoint | null>(null)
  const [hoverPos, setHoverPos] = useState<{ x: number; y: number } | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)

  const currentMachine = machines[selectedMachineIndex] || machines[0]
  const telemetry = currentMachine?.telemetry || []

  // Chart dimensions & scaling
  const width = 640
  const height = 210
  const padLeft = 38
  const padRight = 38
  const padTop = 18
  const padBottom = 26

  const chartW = width - padLeft - padRight
  const chartH = height - padTop - padBottom

  const minVib = 0
  const maxVib = 14
  const minTemp = 50
  const maxTemp = 75

  const points = telemetry.map((pt, idx) => {
    const x = padLeft + (idx / Math.max(telemetry.length - 1, 1)) * chartW
    const yVib = padTop + chartH - ((pt.vibration - minVib) / (maxVib - minVib)) * chartH
    const yTemp = padTop + chartH - ((pt.temperature - minTemp) / (maxTemp - minTemp)) * chartH
    const yHealth = padTop + chartH - ((pt.health - minTemp) / (maxTemp - minTemp)) * chartH

    return { x, yVib, yTemp, yHealth, pt }
  })

  const vibCurve = generateSmoothCurve(points.map((p) => ({ x: p.x, y: p.yVib })))
  const tempCurve = generateSmoothCurve(points.map((p) => ({ x: p.x, y: p.yTemp })))
  const healthCurve = generateSmoothCurve(points.map((p) => ({ x: p.x, y: p.yHealth })))

  const vibArea =
    points.length > 0
      ? `${vibCurve} L ${points[points.length - 1].x} ${padTop + chartH} L ${points[0].x} ${padTop + chartH} Z`
      : ''

  const tempTicks = [50, 55, 60, 65, 70, 75]
  const vibTicks = [0, 2, 4, 6, 8, 10, 12, 14]

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current || points.length === 0) return
    const rect = svgRef.current.getBoundingClientRect()
    const mouseX = ((e.clientX - rect.left) / rect.width) * width

    let closest = points[0]
    let minDist = Math.abs(points[0].x - mouseX)
    for (let i = 1; i < points.length; i++) {
      const dist = Math.abs(points[i].x - mouseX)
      if (dist < minDist) {
        minDist = dist
        closest = points[i]
      }
    }
    setHoveredPoint(closest.pt)
    setHoverPos({ x: closest.x, y: closest.yVib })
  }

  const handleMouseLeave = () => {
    setHoveredPoint(null)
    setHoverPos(null)
  }

  return (
    <div className="apple-card relative flex h-full flex-col rounded-2xl p-4 shadow-sm transition-all overflow-hidden select-none">
      {/* Header: Machine Identity & Segmented Controls */}
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-200/70 shrink-0">
        <div className="flex items-center gap-2.5">
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">
            {currentMachine.name}
          </h2>
          <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-700 border border-blue-200/60">
            {currentMachine.code}
          </span>
          <span className="text-xs text-slate-400 font-normal">
            • {currentMachine.type}
          </span>
        </div>

        {/* Segmented Controls */}
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200/80 bg-slate-100/80 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setChartMode('area')}
              className={`apple-press flex items-center gap-1 rounded-md px-2.5 py-1 text-[10px] font-semibold transition-all cursor-pointer ${
                chartMode === 'area'
                  ? 'bg-white text-blue-700 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <Layers className="h-3 w-3" />
              Area
            </button>
            <button
              type="button"
              onClick={() => setChartMode('line')}
              className={`apple-press flex items-center gap-1 rounded-md px-2.5 py-1 text-[10px] font-semibold transition-all cursor-pointer ${
                chartMode === 'line'
                  ? 'bg-white text-blue-700 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <Activity className="h-3 w-3" />
              Line
            </button>
          </div>

          <select
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value as '24h' | '48h')}
            className="apple-press rounded-lg border border-slate-200/80 bg-white/90 px-2.5 py-1 text-[10px] font-semibold text-slate-700 shadow-2xs focus:outline-none cursor-pointer"
            aria-label="Sensor trend time window"
          >
            <option value="24h">24H</option>
            <option value="48h">48H</option>
          </select>
        </div>
      </div>

      {/* Legend & Carousel Indicator */}
      <div className="flex items-center justify-between pt-2 pb-1 text-[10px] text-slate-600 shrink-0">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 font-semibold text-rose-600">
            <span className="h-0.5 w-2.5 rounded-full bg-rose-500 inline-block" />
            Avg Vib (mm/s)
          </span>
          <span className="flex items-center gap-1 font-semibold text-blue-600">
            <span className="h-0.5 w-2.5 rounded-full bg-blue-600 inline-block" />
            Avg Temp (°C)
          </span>
          <span className="flex items-center gap-1 font-semibold text-emerald-600">
            <span className="h-0.5 w-2.5 border-t border-dashed border-emerald-500 inline-block" />
            Health %
          </span>
        </div>

        {/* Carousel Position Indicator */}
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">
            {selectedMachineIndex + 1} / {machines.length}
          </span>
          <div className="flex gap-1">
            {machines.map((m, idx) => (
              <button
                key={m.id}
                onClick={() => onSelectMachineIndex(idx)}
                aria-label={`Select ${m.name}`}
                className={`apple-press h-1 rounded-full transition-all cursor-pointer ${
                  idx === selectedMachineIndex
                    ? 'w-3.5 bg-blue-600'
                    : 'w-1 bg-slate-300 hover:bg-slate-400'
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Responsive SVG Chart with Carousel Buttons */}
      <div className="relative flex-1 min-h-0 w-full">
        {/* Left Carousel Arrow Button */}
        <button
          type="button"
          onClick={() => onManualNavigate('prev')}
          aria-label="Previous machine in telemetry carousel"
          className="apple-press group absolute -left-2 top-1/2 -translate-y-1/2 z-20 flex h-7.5 w-7.5 items-center justify-center rounded-full border border-slate-300/80 bg-white/90 text-slate-700 shadow-sm backdrop-blur-md transition-all hover:scale-105 hover:border-blue-500 hover:text-blue-700 focus:outline-none cursor-pointer"
        >
          <ChevronLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
        </button>

        {/* Right Carousel Arrow Button */}
        <button
          type="button"
          onClick={() => onManualNavigate('next')}
          aria-label="Next machine in telemetry carousel"
          className="apple-press group absolute -right-2 top-1/2 -translate-y-1/2 z-20 flex h-7.5 w-7.5 items-center justify-center rounded-full border border-slate-300/80 bg-white/90 text-slate-700 shadow-sm backdrop-blur-md transition-all hover:scale-105 hover:border-blue-500 hover:text-blue-700 focus:outline-none cursor-pointer"
        >
          <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </button>

        {/* SVG Chart Element */}
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          className="h-full w-full select-none"
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="vibGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Gridlines */}
          {tempTicks.map((val) => {
            const y = padTop + chartH - ((val - minTemp) / (maxTemp - minTemp)) * chartH
            return (
              <g key={`grid-temp-${val}`}>
                <line
                  x1={padLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  stroke="#edf2f7"
                  strokeWidth="1"
                />
                <text
                  x={width - padRight + 7}
                  y={y + 3}
                  fill="#93c5fd"
                  fontSize="9"
                  fontFamily="system-ui, sans-serif"
                  fontWeight="600"
                  textAnchor="start"
                >
                  {val}
                </text>
              </g>
            )
          })}

          {/* Left Axis Labels */}
          {vibTicks.map((val) => {
            const y = padTop + chartH - ((val - minVib) / (maxVib - minVib)) * chartH
            return (
              <text
                key={`label-vib-${val}`}
                x={padLeft - 7}
                y={y + 3}
                fill="#f87171"
                fontSize="9"
                fontFamily="system-ui, sans-serif"
                fontWeight="600"
                textAnchor="end"
              >
                {val}
              </text>
            )
          })}

          {/* X Axis Timestamps */}
          {points.map((p, idx) => (
            <text
              key={`x-axis-${idx}`}
              x={p.x}
              y={height - 6}
              fill="#94a3b8"
              fontSize="9"
              fontFamily="system-ui, sans-serif"
              fontWeight="500"
              textAnchor="middle"
            >
              {p.pt.time}
            </text>
          ))}

          {/* Shaded Area under Vibration Curve */}
          {chartMode === 'area' && vibArea && (
            <path
              d={vibArea}
              fill="url(#vibGradient)"
              className="transition-all duration-300"
            />
          )}

          {/* Health % Line (Dashed Green) */}
          {healthCurve && (
            <path
              d={healthCurve}
              fill="none"
              stroke="#10b981"
              strokeWidth="1.8"
              strokeDasharray="3,3"
              className="transition-all duration-300"
            />
          )}

          {/* Temperature Line (Smooth Blue) */}
          {tempCurve && (
            <path
              d={tempCurve}
              fill="none"
              stroke="#2563eb"
              strokeWidth="2.2"
              strokeLinecap="round"
              className="transition-all duration-300"
            />
          )}

          {/* Vibration Line (Smooth Red) */}
          {vibCurve && (
            <path
              d={vibCurve}
              fill="none"
              stroke="#ef4444"
              strokeWidth="2.2"
              strokeLinecap="round"
              className="transition-all duration-300"
            />
          )}

          {/* Hover Crosshair & Point */}
          {hoverPos && (
            <>
              <line
                x1={hoverPos.x}
                y1={padTop}
                x2={hoverPos.x}
                y2={padTop + chartH}
                stroke="#cbd5e1"
                strokeWidth="1"
                strokeDasharray="2,2"
              />
              <circle
                cx={hoverPos.x}
                cy={hoverPos.y}
                r="4.5"
                fill="#ef4444"
                stroke="#ffffff"
                strokeWidth="2"
              />
            </>
          )}
        </svg>

        {/* Frosted Apple-style Tooltip Overlay */}
        {hoveredPoint && hoverPos && (
          <div
            className="pointer-events-none absolute z-30 rounded-xl bg-slate-900/90 text-white backdrop-blur-md px-3 py-1.5 shadow-xl text-[10px] transition-all -translate-x-1/2 -translate-y-full mb-2 animate-in fade-in zoom-in-95 duration-100"
            style={{
              left: `${(hoverPos.x / width) * 100}%`,
              top: `${(hoverPos.y / height) * 100}%`,
            }}
          >
            <div className="font-bold text-slate-200 border-b border-slate-700/60 pb-0.5 mb-1">
              Time: {hoveredPoint.time}
            </div>
            <div className="flex gap-3 font-semibold">
              <span className="text-rose-400">Vib: {hoveredPoint.vibration} mm/s</span>
              <span className="text-blue-400">Temp: {hoveredPoint.temperature}°C</span>
              <span className="text-emerald-400">Health: {hoveredPoint.health}%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
