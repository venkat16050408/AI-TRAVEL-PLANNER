import { useState } from 'react'
import type { Plan, Stop, PriceLabel } from '../types'

interface Props {
  plan: Plan
  dayIndex: number
  onDayChange: (i: number) => void
  selectedName: string | null
  onSelect: (name: string) => void
  onHover: (name: string) => void
}

const fmtMin = (m: number) => (m >= 60 ? `${Math.floor(m / 60)}h ${Math.round(m % 60)}m` : `${Math.round(m)}m`)
const fmtRs = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`

const LABEL_TONE: Record<PriceLabel, string> = {
  Verified: 'text-teal-700 bg-teal-500/10',
  Estimated: 'text-navy-800 bg-navy-900/5',
  Unavailable: 'text-navy-800/50 bg-navy-900/[0.04]',
}

function PriceTag({ label }: { label: PriceLabel }) {
  return (
    <span className={`text-[9px] font-bold uppercase tracking-wider px-1 py-px rounded ${LABEL_TONE[label]}`}>
      {label}
    </span>
  )
}

function Thumb({ stop }: { stop: Stop }) {
  const [failed, setFailed] = useState(false)
  const showImage = Boolean(stop.photo_url) && !failed
  return (
    <div className="relative shrink-0 w-24 h-24 rounded-lg overflow-hidden bg-navy-900/[0.05] border border-navy-900/5 flex items-center justify-center">
      {showImage ? (
        <img
          src={stop.photo_url as string}
          alt={stop.name}
          loading="lazy"
          decoding="async"
          className="absolute inset-0 w-full h-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 text-navy-900/25" aria-hidden>
          <path d="M12 21s-6.5-5.4-6.5-10a6.5 6.5 0 1 1 13 0c0 4.6-6.5 10-6.5 10Z" stroke="currentColor" strokeWidth="1.6" />
          <circle cx="12" cy="11" r="2.4" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      )}
    </div>
  )
}

export default function Itinerary({ plan, dayIndex, onDayChange, selectedName, onSelect, onHover }: Props) {
  const days = plan.itinerary
  const visible = dayIndex === -1 ? days : [days[dayIndex]]
  // Continuous numbering so timeline numbers match the map's route markers.
  let running = 0
  const numbered = visible.map(day => {
    const stops = day.stops.map(s => ({ stop: s, n: ++running }))
    return { day, stops }
  })
  const spendOf = (d: number) => plan.daily_spend?.find(x => x.day === d)?.amount ?? 0

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-navy-900 tracking-tight">Your itinerary</h3>
        <div className="flex flex-wrap gap-1.5 justify-end">
          <button
            onClick={() => onDayChange(-1)}
            className={`px-3 py-1 rounded-full text-xs font-semibold border transition ${dayIndex === -1 ? 'bg-navy-900 text-white border-navy-900' : 'border-navy-900/15 text-navy-800/70'}`}
          >
            All
          </button>
          {days.map((d, i) => (
            <button
              key={d.day}
              onClick={() => onDayChange(i)}
              className={`px-3 py-1 rounded-full text-xs font-semibold border transition ${dayIndex === i ? 'bg-navy-900 text-white border-navy-900' : 'border-navy-900/15 text-navy-800/70'}`}
            >
              Day {d.day}
            </button>
          ))}
        </div>
      </div>

      {numbered.map(({ day, stops }) => (
        <div key={day.day} className="mb-6">
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-teal-600">Day {String(day.day).padStart(2, '0')}</p>
            <p className="text-[11px] font-semibold text-navy-800/60 tabular-nums">spend {fmtRs(spendOf(day.day))}</p>
          </div>
          {stops.length === 0 && <p className="text-sm text-navy-800/50 py-2">No stops fit this day within the constraints.</p>}
          <ol className="relative border-l-2 border-navy-900/10 ml-2 space-y-4">
            {stops.map(({ stop: s, n }) => (
              <li key={s.name + n} className="ml-6">
                <span className="absolute -left-[11px] flex h-5 w-5 items-center justify-center rounded-full bg-navy-900 text-white text-[10px] font-bold">{n}</span>
                <button
                  onClick={() => onSelect(s.name)}
                  onMouseEnter={() => onHover(s.name)}
                  className={`w-full text-left rounded-xl border p-4 transition ${selectedName === s.name ? 'border-teal-500 bg-teal-500/5' : 'border-navy-900/10 bg-white hover:border-navy-900/25'}`}
                >
                  <div className="flex gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline justify-between gap-2">
                        <h4 className="font-semibold text-navy-900 truncate">{s.name}</h4>
                        <span className="text-[11px] font-medium text-teal-600 uppercase tracking-wide shrink-0">{s.category}</span>
                      </div>
                      <p className="text-xs text-navy-800/60 mt-1 line-clamp-2">{s.description}</p>
                      <p className="text-xs text-navy-800/70 mt-2">{fmtMin(s.duration_minutes)} visit</p>

                      <div className="mt-2 space-y-1">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-navy-800/70">
                          <span className="inline-flex items-center gap-1">
                            Entry {fmtRs(s.entry_cost)} <PriceTag label={s.entry_price_label} />
                          </span>
                          {s.food_cost > 0 && (
                            <span className="inline-flex items-center gap-1">
                              Food {fmtRs(s.food_cost)} <PriceTag label={s.food_price_label} />
                            </span>
                          )}
                          <span className="inline-flex items-center gap-1">
                            Transport {fmtRs(s.transport_cost)} <PriceTag label={s.transport_price_label} />
                          </span>
                        </div>
                        <p className="text-[11px] font-semibold text-navy-900 tabular-nums">
                          Stop total {fmtRs(s.stop_total)}
                        </p>
                      </div>

                      {s.distance_from_previous_km > 0 ? (
                        <p className="text-[11px] text-navy-800/50 mt-1.5">
                          {s.distance_from_previous_km} km · {fmtMin(s.travel_time_from_previous_minutes)} from previous stop
                        </p>
                      ) : null}
                    </div>
                    <Thumb stop={s} />
                  </div>
                </button>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}
