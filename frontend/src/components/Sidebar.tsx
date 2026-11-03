import React, { useState } from 'react'
import {
  LayoutDashboard,
  MessageSquare,
  SearchCheck,
  BookOpen,
  Settings,
  LogOut,
  Menu,
} from 'lucide-react'

export type NavItemKey =
  | 'dashboard'
  | 'chatbot'
  | 'investigations'
  | 'manuals'
  | 'admin'

interface SidebarProps {
  isExpanded: boolean
  onExit: () => void
  onToggle: () => void
  activeNav: NavItemKey
  onSelectNav: (key: NavItemKey) => void
}

interface NavDestination {
  key: NavItemKey
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

const NAV_ITEMS: NavDestination[] = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
  },
  {
    key: 'chatbot',
    label: 'Chatbot',
    icon: MessageSquare,
  },
  {
    key: 'investigations',
    label: 'Investigations',
    icon: SearchCheck,

  },
  {
    key: 'manuals',
    label: 'Knowledge Manuals',
    icon: BookOpen,
  },
  {
    key: 'admin',
    label: 'Admin',
    icon: Settings,
  },
]

export const Sidebar: React.FC<SidebarProps> = ({
  isExpanded,
  onToggle,
  onExit,
  activeNav,
  onSelectNav,
}) => {
  const [hoveredItem, setHoveredItem] = useState<string | null>(null)

  return (
    <aside
      className={`relative z-30 flex flex-col border-r border-slate-300/60 bg-white/80 backdrop-blur-xl transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] select-none shadow-xs ${
        isExpanded ? 'w-56' : 'w-16'
      }`}
      aria-label="Main sidebar navigation"
    >
      {/* Top Header: Hamburger Toggle + Brand Badge */}
      <div className="flex h-15 items-center justify-between px-3 border-b border-slate-200/60">
        <button
          type="button"
          onClick={onToggle}
          aria-label={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
          className="apple-press inline-flex h-9 w-9 items-center justify-center rounded-xl text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 transition-colors cursor-pointer"
          title={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <Menu className="h-5 w-5" />
        </button>

        {isExpanded && (
          <div className="flex items-center gap-2 pr-1 animate-in fade-in duration-200">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-blue-600 font-black text-white text-[10px] shadow-xs">
              M1
            </div>
            <span className="text-xs font-bold tracking-tight text-slate-900">
              MISTRANICS
            </span>
          </div>
        )}
      </div>

      {/* Main Navigation Items */}
      <nav className="flex-1 space-y-1.5 p-2 pt-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive = activeNav === item.key

          return (
            <div
              key={item.key}
              className="relative"
              onMouseEnter={() => setHoveredItem(item.key)}
              onMouseLeave={() => setHoveredItem(null)}
            >
              <button
                type="button"
                onClick={() => onSelectNav(item.key)}
                className={`apple-press group flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-xs font-semibold transition-all cursor-pointer ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                    : 'text-slate-600 hover:bg-slate-100/70 hover:text-slate-900'
                } ${!isExpanded ? 'justify-center' : ''}`}
                aria-current={isActive ? 'page' : undefined}
                aria-label={item.label}
              >
                <Icon
                  className={`h-4.5 w-4.5 shrink-0 transition-transform group-hover:scale-105 ${
                    isActive ? 'text-white' : 'text-slate-500 group-hover:text-slate-800'
                  }`}
                />

                {isExpanded && (
                  <span className="truncate flex-1 text-left">{item.label}</span>
                )}

                {isExpanded && item.badge && (
                  <span
                    className={`ml-auto rounded-full px-1.5 py-0.2 text-[9px] font-bold ${
                      isActive
                        ? 'bg-white/20 text-white'
                        : 'bg-slate-200/80 text-slate-700'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>

              {/* Tooltip for collapsed mode */}
              {!isExpanded && hoveredItem === item.key && (
                <div className="absolute left-full top-1/2 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg bg-slate-900/90 backdrop-blur-md px-2.5 py-1 text-[11px] font-medium text-white shadow-xl z-50 animate-in fade-in zoom-in-95 duration-100">
                  {item.label}
                </div>
              )}
            </div>
          )
        })}
      </nav>

      {/* Bottom: Log Out Action */}
      <div className="border-t border-slate-200/60 p-2">
        <div
          className="relative"
          onMouseEnter={() => setHoveredItem('logout')}
          onMouseLeave={() => setHoveredItem(null)}
        >
          <button
            type="button"
            onClick={onExit}
            className={`apple-press group flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-xs font-semibold text-slate-500 hover:bg-rose-50 hover:text-rose-600 transition-all cursor-pointer ${
              !isExpanded ? 'justify-center' : ''
            }`}
            aria-label="Return to workspace selection"
          >
            <LogOut className="h-4.5 w-4.5 shrink-0 text-slate-400 group-hover:text-rose-600 transition-colors" />
            {isExpanded && <span className="truncate">Workspaces</span>}
          </button>

          {!isExpanded && hoveredItem === 'logout' && (
            <div className="absolute left-full top-1/2 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg bg-slate-900/90 backdrop-blur-md px-2.5 py-1 text-[11px] font-medium text-white shadow-xl z-50">
              Workspaces
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
