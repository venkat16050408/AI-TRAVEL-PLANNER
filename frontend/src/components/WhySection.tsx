import { useState } from 'react'

export default function WhySection() {
  const [open, setOpen] = useState(false)
  return (
    <section className="bg-white rounded-2xl border border-navy-900/5 shadow-sm p-6">
      <button onClick={() => setOpen(o => !o)} className="flex w-full items-center justify-between">
        <h3 className="text-base font-bold text-navy-900">Why this itinerary?</h3>
        <span className="text-navy-800/50">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="mt-4 text-sm text-navy-800/70 space-y-2">
          <p>Your trip was optimized around your budget, available time, and selected interests. Candidate places were retrieved from OpenStreetMap, then filtered with dynamic programming (budget × time), routed with Nearest Neighbour + 2-opt, and timed with Dijkstra shortest paths.</p>
          <div className="flex flex-wrap gap-2 pt-1">
            {['Dynamic Programming', 'Route Optimization', 'Shortest Path'].map(b => (
              <span key={b} className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-teal-500/10 text-teal-600">{b}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
