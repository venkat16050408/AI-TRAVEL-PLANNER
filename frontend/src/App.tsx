import { useState, useCallback } from 'react'
import Header from './components/Header'
import PlannerForm from './components/PlannerForm'
import LoadingStages from './components/LoadingStages'
import MapView from './components/MapView'
import Itinerary from './components/Itinerary'
import WhySection from './components/WhySection'
import type { Plan, PlanRequest } from './types'

const fmtMin = (m: number) => (m >= 60 ? `${Math.floor(m / 60)}h ${Math.round(m % 60)}m` : `${Math.round(m)}m`)

export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(false)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [dayIndex, setDayIndex] = useState(-1)
  const [selectedName, setSelectedName] = useState<string | null>(null)

  const handleSubmit = async (req: PlanRequest) => {
    setLoading(true)
    setError(null)
    setPlan(null)
    setStage(0)
    const timers = [1, 2, 3].map(i => setTimeout(() => setStage(i), 700))
    try {
      const res = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      })
      const data = await res.json()
      timers.forEach(clearTimeout)
      if (!res.ok) {
        setError(data.detail || 'Something went wrong while building your trip. Please try again.')
        return
      }
      setPlan(data)
      setDayIndex(-1)
      setSelectedName(null)
    } catch {
      timers.forEach(clearTimeout)
      setError('Could not reach the planning service. Make sure the backend is running on port 8000.')
    } finally {
      timers.forEach(clearTimeout)
      setLoading(false)
    }
  }

  const onSelect = useCallback((name: string) => setSelectedName(name), [])

  return (
    <div className="min-h-screen">
      <Header />

      {!plan && !loading && (
        <main className="max-w-6xl mx-auto px-4 pt-14 pb-20">
          <div className="max-w-2xl mb-10">
            <p className="text-sm font-semibold text-teal-600 uppercase tracking-widest">AI Travel Planner</p>
            <h1 className="mt-3 text-4xl sm:text-5xl font-extrabold text-navy-900 tracking-tight leading-tight">
              Plan smarter.<br />Travel better.
            </h1>
            <p className="mt-4 text-navy-800/60 text-lg">
              Where will your next journey take you? Enter a city and get a day-wise itinerary optimized for your budget, time and interests.
            </p>
          </div>
          <PlannerForm onSubmit={handleSubmit} loading={loading} />
          {error && <ErrorCard message={error} onRetry={() => setError(null)} />}
        </main>
      )}

      {loading && (
        <main className="max-w-6xl mx-auto px-4 pt-14">
          <LoadingStages stage={stage} />
        </main>
      )}

      {plan && !loading && (
        <main className="max-w-6xl mx-auto px-4 pt-8 pb-20">
          <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-teal-600">Your trip</p>
              <h1 className="text-3xl font-extrabold text-navy-900 tracking-tight">{plan.destination}</h1>
              <p className="text-sm text-navy-800/60 mt-1">
                {plan.days} {plan.days === 1 ? 'day' : 'days'} · from {plan.origin.name}
              </p>
            </div>
            <button
              onClick={() => setPlan(null)}
              className="text-sm font-semibold px-4 py-2 rounded-xl border border-navy-900/15 text-navy-900 hover:bg-navy-900 hover:text-white transition"
            >
              Plan a new trip
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            {[
              { label: 'Distance', value: `${plan.total_distance_km} km` },
              { label: 'Travel time', value: fmtMin(plan.total_travel_time_minutes) },
              { label: 'Estimated cost', value: `₹${plan.total_estimated_cost}` },
              { label: 'Places', value: String(plan.selected_places.length) },
            ].map(s => (
              <div key={s.label} className="bg-white rounded-xl border border-navy-900/5 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-navy-800/50">{s.label}</p>
                <p className="text-lg sm:text-xl font-bold text-navy-900 mt-0.5 tabular-nums">{s.value}</p>
              </div>
            ))}
          </div>

          <BudgetBar plan={plan} />
          {plan.warning && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">{plan.warning}</p>
          )}
          {plan.origin_note && (
            <p className="text-xs text-navy-800/70 bg-navy-900/5 border border-navy-900/10 rounded-lg px-3 py-2 mb-4">{plan.origin_note}</p>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            <div className="bg-white rounded-2xl border border-navy-900/5 shadow-sm p-5 lg:sticky lg:top-20">
              <MapView plan={plan} dayIndex={dayIndex} selectedName={selectedName} onSelect={onSelect} />
              <p className="text-[11px] text-navy-800/50 mt-3">H = origin · numbered markers follow your itinerary order.</p>
            </div>
            <div>
              <Itinerary plan={plan} dayIndex={dayIndex} onDayChange={setDayIndex} selectedName={selectedName} onSelect={onSelect} onHover={setSelectedName} />
              <WhySection />
            </div>
          </div>
        </main>
      )}

      {plan && (
        <footer className="border-t border-navy-900/5 bg-white">
          <div className="max-w-6xl mx-auto px-4 py-5 text-xs text-navy-800/50 flex flex-wrap gap-4 justify-between">
            <span>Places from OpenStreetMap · Route optimized with Dynamic Programming, Nearest Neighbour, 2-opt & Dijkstra</span>
            <span>AI Travel Planner · DAA Hackathon</span>
          </div>
        </footer>
      )}
    </div>
  )
}

function BudgetBar({ plan }: { plan: Plan }) {
  const pct = Math.max(0, Math.min(100, (plan.total_estimated_cost / Math.max(plan.budget, 1)) * 100))
  const over = plan.over_budget
  return (
    <div className="bg-white rounded-xl border border-navy-900/5 px-4 py-3 mb-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-xs">
        <span className="font-semibold text-navy-900">
          Budget ₹{plan.budget.toLocaleString('en-IN')} · Estimated ₹{plan.total_estimated_cost.toLocaleString('en-IN')}
        </span>
        <span className={`font-semibold tabular-nums ${over ? 'text-red-600' : 'text-teal-600'}`}>
          {over
            ? `₹${Math.abs(plan.remaining_budget).toLocaleString('en-IN')} over budget`
            : `₹${plan.remaining_budget.toLocaleString('en-IN')} remaining`}
        </span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-navy-900/5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${over ? 'bg-red-500' : 'bg-teal-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-navy-800/60">
        {(plan.daily_spend || []).map(d => (
          <span key={d.day} className="tabular-nums">Day {d.day}: ₹{d.amount.toLocaleString('en-IN')}</span>
        ))}
      </div>
    </div>
  )
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mt-8 bg-white rounded-2xl border border-red-200 p-6 max-w-xl">
      <h3 className="font-bold text-navy-900">Couldn't build this itinerary</h3>
      <p className="text-sm text-navy-800/70 mt-1">{message}</p>
      <button onClick={onRetry} className="mt-4 text-sm font-semibold px-4 py-2 rounded-xl bg-navy-900 text-white hover:bg-navy-800 transition">
        Try Again
      </button>
    </div>
  )
}
