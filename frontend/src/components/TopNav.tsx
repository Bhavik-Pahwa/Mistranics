import React, { useState } from 'react'
import {
  Bell,
  Search,
  AlertTriangle,
  Menu,
} from 'lucide-react'

interface TopNavProps {
  onToggleSidebar: () => void
  isSidebarExpanded: boolean
  onOpenSearch: () => void
  unreadAlertCount: number
}

export const TopNav: React.FC<TopNavProps> = ({
  onToggleSidebar,
  isSidebarExpanded,
  onOpenSearch,
  unreadAlertCount,
}) => {
  const [showNotifications, setShowNotifications] = useState(false)
  const [showProfileMenu, setShowProfileMenu] = useState(false)

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-slate-200/80 bg-white px-4 transition-colors lg:px-5">
      {/* Left: Brand Identity & Single Sidebar Toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label={isSidebarExpanded ? 'Collapse navigation sidebar' : 'Expand navigation sidebar'}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors cursor-pointer"
          title={isSidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Brand Badge */}
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 font-bold text-white shadow-xs">
            <span className="text-[11px] font-black tracking-wider">M1</span>
          </div>
          <span className="text-sm font-bold tracking-tight text-slate-900">
            MISTRANICS
          </span>
        </div>

        <div className="mx-2 hidden h-4 w-px bg-slate-200 lg:block" />

        <span className="hidden text-xs font-semibold text-slate-600 lg:inline-block">
          Dashboard
        </span>
      </div>

      {/* Center: Global Search Field */}
      <div className="mx-4 flex max-w-lg flex-1 items-center justify-center">
        <div
          onClick={onOpenSearch}
          className="group relative flex w-full max-w-md cursor-pointer items-center rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-1.5 transition-all hover:border-slate-300 hover:bg-white focus-within:border-blue-600 focus-within:bg-white"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onOpenSearch()
            }
          }}
          aria-label="Search machines, alerts, investigations"
        >
          <Search className="h-3.5 w-3.5 text-slate-400 transition-colors group-hover:text-blue-600" />
          <input
            type="text"
            readOnly
            placeholder="Search machines, alerts, investigations..."
            className="w-full bg-transparent px-2.5 text-xs text-slate-700 placeholder-slate-400 focus:outline-none cursor-pointer"
          />
          <div className="hidden items-center gap-1 sm:flex">
            <kbd className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[9px] font-medium text-slate-400 shadow-xs">
              Ctrl K
            </kbd>
          </div>
        </div>
      </div>

      {/* Right Controls: Notifications & User Profile */}
      <div className="relative flex items-center gap-2">
        {/* Notification Button */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowNotifications(!showNotifications)}
            aria-label={`Notifications, ${unreadAlertCount} active alerts`}
            className="relative inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors cursor-pointer"
            title="Active Operational Notifications"
          >
            <Bell className="h-4 w-4" />
            {unreadAlertCount > 0 && (
              <span className="absolute top-1 right-1 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-rose-500 px-1 text-[8px] font-bold text-white shadow-xs">
                {unreadAlertCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-2.5 shadow-xl z-50 animate-in fade-in zoom-in-95 duration-100">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2 px-1">
                <span className="text-xs font-bold text-slate-800">
                  Alerts ({unreadAlertCount})
                </span>
                <button
                  type="button"
                  onClick={() => setShowNotifications(false)}
                  className="text-[10px] font-medium text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  Close
                </button>
              </div>
              <div className="mt-1.5 space-y-1.5 max-h-56 overflow-y-auto custom-scrollbar">
                <div className="flex gap-2 rounded-lg p-2 text-xs hover:bg-slate-50 transition-colors">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500 mt-0.5" />
                  <div>
                    <p className="font-semibold text-slate-800">
                      Compressor #3: Bearing Vibration Limit Exceeded
                    </p>
                    <span className="text-[10px] text-slate-400">8 mins ago • Critical</span>
                  </div>
                </div>
                <div className="flex gap-2 rounded-lg p-2 text-xs hover:bg-slate-50 transition-colors">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500 mt-0.5" />
                  <div>
                    <p className="font-semibold text-slate-800">
                      Cooling Pump P-7: Cavitation Signature Observed
                    </p>
                    <span className="text-[10px] text-slate-400">24 mins ago • High</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User Profile Avatar (JD) */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            aria-label="User profile John Doe"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 font-semibold text-slate-700 ring-1 ring-slate-200 hover:ring-blue-500 transition-all cursor-pointer"
            title="John Doe (Reliability Lead)"
          >
            <span className="text-[11px] font-bold">JD</span>
          </button>

          {/* Profile Menu Dropdown */}
          {showProfileMenu && (
            <div className="absolute right-0 mt-2 w-52 rounded-xl border border-slate-200 bg-white p-2 shadow-xl z-50 animate-in fade-in zoom-in-95 duration-100">
              <div className="border-b border-slate-100 px-2.5 py-1.5">
                <p className="text-xs font-bold text-slate-900">John Doe</p>
                <p className="text-[11px] text-slate-500">Lead Reliability Engineer</p>
              </div>
              <div className="py-1 text-xs text-slate-700">
                <div className="px-2.5 py-1 hover:bg-slate-50 rounded cursor-pointer">
                  Plant Alpha (Bay 4)
                </div>
              </div>
              <div className="border-t border-slate-100 pt-1">
                <button
                  type="button"
                  onClick={() => setShowProfileMenu(false)}
                  className="w-full text-left px-2.5 py-1 text-xs text-rose-600 hover:bg-rose-50 rounded cursor-pointer"
                >
                  Log out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
