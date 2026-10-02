import { useEffect, useMemo, useRef, useState } from 'react'
import type { Plan, Stop } from '../types'

declare global {
  interface Window { google: any; gm_authFailure?: () => void }
}

interface Props {
  plan: Plan
  dayIndex: number // -1 = all days
  selectedName: string | null
  onSelect: (name: string) => void
}

type Status = 'loading' | 'google' | 'osm'

let mapsPromise: Promise<void> | null = null
let authErrorHandler: ((msg: string) => void) | null = null

function loadMaps(key: string): Promise<void> {
  if (mapsPromise) return mapsPromise
  mapsPromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Google Maps load timeout')), 12000)
    window.gm_authFailure = () => {
      clearTimeout(timer)
      authErrorHandler?.('Google Maps rejected the API key')
      reject(new Error('Google Maps auth failure'))
    }
    const s = document.createElement('script')
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&loading=async`
    s.async = true
    s.onload = () => { clearTimeout(timer); resolve() }
    s.onerror = () => { clearTimeout(timer); reject(new Error('Failed to load Google Maps')) }
    document.head.appendChild(s)
  })
  return mapsPromise
}

function useStops(plan: Plan, dayIndex: number): Stop[] {
  return useMemo(() => {
    const stops: Stop[] = []
    plan.itinerary.forEach((d, i) => {
      if (dayIndex === -1 || i === dayIndex) stops.push(...d.stops)
    })
    return stops
  }, [plan, dayIndex])
}

/* -------------------------------------------------------------------------- */
/* Google Maps path                                                           */
/* -------------------------------------------------------------------------- */
function useGoogleMap(
  ref: React.RefObject<HTMLDivElement>,
  status: Status,
  plan: Plan,
  stops: Stop[],
  selectedName: string | null,
  onSelect: (name: string) => void,
) {
  const mapRef = useRef<any>(null)
  const markersRef = useRef<Array<{ name: string; marker: any }>>([])

  useEffect(() => {
    if (status !== 'google' || !ref.current) return
    const g = window.google?.maps
    if (!g) return
    const points = [{ lat: plan.origin.lat, lng: plan.origin.lng }, ...stops.map(s => ({ lat: s.lat, lng: s.lng }))]

    let map = mapRef.current
    if (!map) {
      map = new g.Map(ref.current, {
        center: points[0],
        zoom: 12,
        mapTypeControl: false,
        streetViewControl: false,
        zoomControl: true,
        styles: [{ featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] }],
      })
      mapRef.current = map
    }

    // Clear previous overlays (markers + polyline) for this itinerary/day.
    markersRef.current.forEach(m => m.marker.setMap(null))
    markersRef.current = []
    if (map.__polyline) { map.__polyline.setMap(null); map.__polyline = null }

    const bounds = new g.LatLngBounds()
    points.forEach(p => bounds.extend(p))

    new g.Marker({ position: points[0], map, label: { text: 'H', color: '#fff', fontWeight: 'bold' }, title: plan.origin.name })

    stops.forEach((s, i) => {
      const marker = new g.Marker({
        position: { lat: s.lat, lng: s.lng },
        map,
        label: { text: String(i + 1), color: '#fff', fontWeight: 'bold' },
        title: s.name,
      })
      marker.addListener('click', () => onSelect(s.name))
      marker.addListener('mouseover', () => onSelect(s.name))
      markersRef.current.push({ name: s.name, marker })
    })

    if (points.length > 1) {
      map.__polyline = new g.Polyline({ path: points, map, strokeColor: '#0D9488', strokeWeight: 4, strokeOpacity: 0.9 })
    }
    if (points.length > 1) map.fitBounds(bounds, 48)
    else map.setCenter(points[0])
  }, [status, plan, stops, onSelect, ref])

  // Highlight selected marker without rebuilding.
  useEffect(() => {
    if (status !== 'google') return
    const g = window.google?.maps
    if (!g) return
    markersRef.current.forEach(({ name, marker }) => {
      const selected = name === selectedName
      marker.setIcon(selected
        ? { path: g.SymbolPath.CIRCLE, scale: 12, fillColor: '#0D9488', fillOpacity: 1, strokeColor: '#0F2740', strokeWeight: 3 }
        : null)
      marker.setZIndex(selected ? 10 : 1)
    })
  }, [status, selectedName])

  return mapRef
}

/* -------------------------------------------------------------------------- */
/* OSM fallback: a real slippy map (tiles from openstreetmap.org)             */
/* -------------------------------------------------------------------------- */
function OsmFallbackMap({ plan, stops, selectedName, onSelect }: {
  plan: Plan
  stops: Stop[]
  selectedName: string | null
  onSelect: (name: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 640, h: 400 })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setSize({ w: el.clientWidth || 640, h: el.clientHeight || 400 })
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const mercY = (lat: number) =>
    (1 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 180 / 2)) / Math.PI) / 2

  const view = useMemo(() => {
    const points = [
      { lat: plan.origin.lat, lng: plan.origin.lng, name: plan.origin.name, n: 0, isOrigin: true },
      ...stops.map((s, i) => ({ lat: s.lat, lng: s.lng, name: s.name, n: i + 1, isOrigin: false })),
    ]
    if (points.length === 0) return null
    const lats = points.map(p => p.lat)
    const lngs = points.map(p => p.lng)
    const minLat = Math.min(...lats), maxLat = Math.max(...lats)
    const minLng = Math.min(...lngs), maxLng = Math.max(...lngs)
    const lngSpan = Math.max(maxLng - minLng, 1e-4)
    const y1 = mercY(maxLat), y2 = mercY(minLat)
    const ySpan = Math.max(y1 - y2, 1e-6)
    const zx = Math.log2((Math.max(size.w, 200) * 360) / (lngSpan * 256)) - 0.7
    const zy = Math.log2((Math.max(size.h, 200) * 360) / (ySpan * 256)) - 0.7
    const zoom = Math.max(2, Math.min(18, Math.floor(Math.min(zx, zy))))
    const world = 256 * 2 ** zoom
    const yc = (y1 + y2) / 2
    const centerLat = (2 * Math.atan(Math.exp(Math.PI * (1 - 2 * yc))) - Math.PI / 2) * 180 / Math.PI
    const centerLng = (minLng + maxLng) / 2
    const cx = ((centerLng + 180) / 360) * world
    const cy = mercY(centerLat) * world
    const project = (lat: number, lng: number) => ({
      x: ((lng + 180) / 360) * world - cx + size.w / 2,
      y: mercY(lat) * world - cy + size.h / 2,
    })

    // Visible tile grid
    const topLeftX = cx - size.w / 2
    const topLeftY = cy - size.h / 2
    const n = 2 ** zoom
    const tiles: Array<{ key: string; src: string; left: number; top: number }> = []
    const minTx = Math.floor(topLeftX / 256), maxTx = Math.floor((topLeftX + size.w) / 256)
    const minTy = Math.floor(topLeftY / 256), maxTy = Math.floor((topLeftY + size.h) / 256)
    for (let tx = minTx; tx <= maxTx; tx++) {
      for (let ty = Math.max(0, minTy); ty <= Math.min(n - 1, maxTy); ty++) {
        const wrapped = ((tx % n) + n) % n
        tiles.push({
          key: `${tx}-${ty}`,
          src: `https://tile.openstreetmap.org/${zoom}/${wrapped}/${ty}.png`,
          left: tx * 256 - topLeftX,
          top: ty * 256 - topLeftY,
        })
      }
    }

    return { points, project, tiles }
  }, [plan, stops, size])

  if (!view) return <div ref={ref} className="h-80 lg:h-full min-h-[360px]" />

  return (
    <div ref={ref} className="relative h-80 lg:h-full min-h-[360px] rounded-xl border border-navy-900/10 overflow-hidden bg-[#e8ecef]">
      {view.tiles.map(t => (
        <img
          key={t.key}
          src={t.src}
          alt=""
          aria-hidden
          loading="lazy"
          draggable={false}
          className="absolute select-none"
          style={{ left: t.left, top: t.top, width: 256, height: 256 }}
        />
      ))}

      {/* Route polyline through origin → stops */}
      {view.points.length > 1 && (
        <svg className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden>
          <polyline
            points={view.points.map(p => { const q = view.project(p.lat, p.lng); return `${q.x},${q.y}` }).join(' ')}
            fill="none"
            stroke="#0D9488"
            strokeWidth="4"
            strokeOpacity="0.9"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      )}

      {view.points.map(p => {
        const q = view.project(p.lat, p.lng)
        const selected = !p.isOrigin && p.name === selectedName
        return (
          <button
            key={p.name + p.n}
            type="button"
            title={p.name}
            onClick={() => !p.isOrigin && onSelect(p.name)}
            onMouseEnter={() => !p.isOrigin && onSelect(p.name)}
            className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full flex items-center justify-center text-[11px] font-bold text-white shadow-md transition-transform ${p.isOrigin
              ? 'bg-navy-900 h-7 w-7'
              : selected
                ? 'bg-teal-500 h-8 w-8 ring-4 ring-teal-500/30 scale-110 z-10'
                : 'bg-teal-600 h-7 w-7 hover:scale-110'}`}
            style={{ left: q.x, top: q.y, cursor: p.isOrigin ? 'default' : 'pointer' }}
          >
            {p.isOrigin ? 'H' : p.n}
          </button>
        )
      })}

      <span className="absolute bottom-1 right-1 bg-white/85 text-[10px] text-navy-800/70 px-1.5 py-0.5 rounded">
        © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline">OpenStreetMap</a>
      </span>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Public component                                                           */
/* -------------------------------------------------------------------------- */
export default function MapView({ plan, dayIndex, selectedName, onSelect }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<Status>('loading')
  const stops = useStops(plan, dayIndex)

  const raw = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  const key = !raw || raw === 'YOUR_GOOGLE_MAPS_KEY' ? '' : raw

  useEffect(() => {
    if (!key) {
      setStatus('osm') // no key yet → OSM fallback (real map, no key needed)
      return
    }
    let cancelled = false
    authErrorHandler = () => { if (!cancelled) setStatus('osm') }
    setStatus('loading')
    loadMaps(key)
      .then(() => { if (!cancelled) setStatus('google') })
      .catch(() => { if (!cancelled) setStatus('osm') })
    return () => { cancelled = true; authErrorHandler = null }
  }, [key])

  const mapRef = useGoogleMap(ref, status, plan, stops, selectedName, onSelect)

  // Pan to the selected stop on the Google map.
  useEffect(() => {
    if (status !== 'google') return
    const g = window.google?.maps
    if (!g || !mapRef.current) return
    const hit = stops.find(s => s.name === selectedName)
    if (hit) mapRef.current.panTo({ lat: hit.lat, lng: hit.lng })
  }, [selectedName, status, stops, mapRef])

  if (status === 'osm') {
    return <OsmFallbackMap plan={plan} stops={stops} selectedName={selectedName} onSelect={onSelect} />
  }

  if (status === 'loading') {
    return (
      <div className="h-80 lg:h-full min-h-[360px] rounded-xl border border-navy-900/10 bg-navy-900/[0.03] flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-6 w-6 rounded-full border-2 border-teal-500 border-t-transparent animate-spin" />
          <p className="text-xs text-navy-800/50 mt-3">Loading map…</p>
        </div>
      </div>
    )
  }

  return <div ref={ref} className="h-80 lg:h-full min-h-[360px] rounded-xl border border-navy-900/10 overflow-hidden" />
}
