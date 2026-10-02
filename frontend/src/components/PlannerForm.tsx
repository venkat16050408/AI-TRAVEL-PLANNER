import { useState } from 'react'
import type { PlanRequest } from '../types'

const INTERESTS = ['Historical', 'Food', 'Nature', 'Shopping', 'Adventure', 'Culture']

const PRESETS = [
  { name: 'Paris', tag: 'City of light', img: 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=400&q=60' },
  { name: 'Tokyo', tag: 'Neon & temples', img: 'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=400&q=60' },
  { name: 'Delhi', tag: 'Capital of India', img: 'https://images.unsplash.com/photo-1587474260584-136574528ed5?w=400&q=60' },
  { name: 'Hyderabad', tag: 'Pearls & biryani', img: 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/71/Charminar_Hyderabad_1.jpg/500px-Charminar_Hyderabad_1.jpg' },
]

interface Props {
  onSubmit: (req: PlanRequest) => void
  loading: boolean
}

export default function PlannerForm({ onSubmit, loading }: Props) {
  const [destination, setDestination] = useState('')
  const [origin, setOrigin] = useState('')
  const [days, setDays] = useState(3)
  const [travelers, setTravelers] = useState(2)
  const [budget, setBudget] = useState(15000)
  const [interests, setInterests] = useState<string[]>(['Historical', 'Food'])
  const [error, setError] = useState('')

  const toggleInterest = (i: string) =>
    setInterests(prev => (prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]))

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!destination.trim()) return setError('Please enter a destination city.')
    if (!origin.trim()) return setError('Please enter your origin / hotel.')
    if (days < 1 || days > 14) return setError('Days must be between 1 and 14.')
    if (budget <= 0) return setError('Budget must be greater than zero.')
    if (interests.length === 0) return setError('Select at least one interest.')
    setError('')
    onSubmit({ destination: destination.trim(), origin: origin.trim(), days, travelers, budget, interests })
  }

  return (
    <section className="bg-white rounded-2xl border border-navy-900/5 shadow-sm p-6 sm:p-8">
      <h2 className="text-xl font-bold text-navy-900 tracking-tight">Plan your trip</h2>
      <p className="text-sm text-navy-800/60 mt-1 mb-6">Tell us where, for how long, and what you love.</p>

      <form onSubmit={submit} className="space-y-6">
        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-navy-800/50">Where</label>
          <div className="mt-1.5 flex items-center gap-2 rounded-xl border border-navy-900/10 focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-500/20 transition">
            <svg className="ml-3 w-4 h-4 text-navy-800/40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
            <input
              className="flex-1 py-3 pr-3 outline-none bg-transparent text-navy-900 placeholder:text-navy-800/30"
              placeholder="Destination city, e.g. Hyderabad"
              value={destination}
              onChange={e => setDestination(e.target.value)}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-navy-800/50">From · Hotel / Origin</label>
            <input
              className="mt-1.5 w-full rounded-xl border border-navy-900/10 px-3 py-3 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 placeholder:text-navy-800/30"
              placeholder="e.g. Charminar"
              value={origin}
              onChange={e => setOrigin(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-navy-800/50">Days</label>
              <input type="number" min={1} max={14} className="mt-1.5 w-full rounded-xl border border-navy-900/10 px-3 py-3 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20" value={days} onChange={e => setDays(Number(e.target.value))} />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-navy-800/50">Travelers</label>
              <input type="number" min={1} max={20} className="mt-1.5 w-full rounded-xl border border-navy-900/10 px-3 py-3 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20" value={travelers} onChange={e => setTravelers(Number(e.target.value))} />
            </div>
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-navy-800/50">Total budget (₹ INR)</label>
          <input type="number" min={1} className="mt-1.5 w-full rounded-xl border border-navy-900/10 px-3 py-3 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20" value={budget} onChange={e => setBudget(Number(e.target.value))} />
        </div>

        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-navy-800/50">Interests</label>
          <div className="mt-2 flex flex-wrap gap-2">
            {INTERESTS.map(i => (
              <button
                type="button"
                key={i}
                onClick={() => toggleInterest(i)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium border transition ${
                  interests.includes(i)
                    ? 'bg-navy-900 text-white border-navy-900'
                    : 'bg-white text-navy-800/70 border-navy-900/15 hover:border-navy-900/40'
                }`}
              >
                {i}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          disabled={loading}
          className="w-full rounded-xl bg-navy-900 text-white font-semibold py-3.5 hover:bg-navy-800 active:scale-[0.99] transition disabled:opacity-50"
        >
          {loading ? 'Optimizing…' : 'Optimize My Trip'}
        </button>
      </form>

      <div className="mt-8">
        <p className="text-xs font-semibold uppercase tracking-wider text-navy-800/50 mb-3">Quick destinations</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {PRESETS.map(p => (
            <button
              type="button"
              key={p.name}
              onClick={() => setDestination(p.name)}
              className="text-left rounded-xl overflow-hidden border border-navy-900/10 hover:border-teal-500 hover:shadow-md transition group"
            >
              <img src={p.img} alt={p.name} className="h-16 w-full object-cover group-hover:scale-105 transition duration-300" />
              <div className="px-2.5 py-2">
                <p className="text-sm font-semibold text-navy-900 leading-tight">{p.name}</p>
                <p className="text-[11px] text-navy-800/50">{p.tag}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
