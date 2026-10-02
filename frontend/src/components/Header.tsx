export default function Header() {
  return (
    <header className="sticky top-0 z-30 bg-white/80 backdrop-blur border-b border-navy-900/5">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden>
            <circle cx="6" cy="26" r="3" fill="#0F2740" />
            <circle cx="26" cy="6" r="3" fill="#14B8A6" />
            <path d="M8 23 C 14 22, 12 10, 24 8" stroke="#14B8A6" strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" />
          </svg>
          <span className="font-bold text-navy-900 text-lg tracking-tight">AI Travel Planner</span>
        </div>
        <span className="text-xs font-medium text-navy-800/60 bg-navy-900/5 rounded-full px-3 py-1">
          DAA Hackathon
        </span>
      </div>
    </header>
  )
}
