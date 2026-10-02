const STAGES = ['Finding places', 'Evaluating your budget', 'Optimizing your route', 'Building your itinerary']

export default function LoadingStages({ stage }: { stage: number }) {
  return (
    <div className="bg-white rounded-2xl border border-navy-900/5 shadow-sm p-8 text-center">
      <div className="mx-auto w-10 h-10 rounded-full border-4 border-navy-900/10 border-t-teal-500 animate-spin" />
      <ul className="mt-6 space-y-2 text-left max-w-xs mx-auto">
        {STAGES.map((s, i) => (
          <li key={s} className={`text-sm flex items-center gap-2 ${i <= stage ? 'text-navy-900 font-medium' : 'text-navy-800/30'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${i <= stage ? 'bg-teal-500' : 'bg-navy-900/20'}`} />
            {s}
          </li>
        ))}
      </ul>
    </div>
  )
}
