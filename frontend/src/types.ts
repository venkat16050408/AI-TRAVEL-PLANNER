export type PriceLabel = 'Verified' | 'Estimated' | 'Unavailable'

export interface Stop {
  name: string
  category: string
  description: string
  duration_minutes: number
  cost: number
  entry_cost: number
  entry_price_label: PriceLabel
  food_cost: number
  food_price_label: PriceLabel
  transport_cost: number
  transport_price_label: PriceLabel
  stop_total: number
  photo_url?: string | null
  lat: number
  lng: number
  distance_from_previous_km: number
  travel_time_from_previous_minutes: number
}

export interface DayPlan {
  day: number
  stops: Stop[]
}

export interface DailySpend {
  day: number
  amount: number
}

export interface Plan {
  destination: string
  origin: { name: string; lat: number; lng: number }
  destination_center: { name: string; lat: number; lng: number }
  candidates: any[]
  selected_places: any[]
  optimized_route: string[]
  days: number
  itinerary: DayPlan[]
  total_distance_km: number
  total_travel_time_minutes: number
  total_visit_minutes: number
  total_cost: number
  budget: number
  total_estimated_cost: number
  remaining_budget: number
  over_budget: boolean
  daily_spend: DailySpend[]
  warning?: string | null
  origin_note?: string | null
  algorithm_summary: {
    candidates_found: number
    selected_by_dp: number
    nn_route_distance_km: number
    two_opt_route_distance_km: number
    dijkstra_used: boolean
  }
}

export interface PlanRequest {
  destination: string
  origin: string
  days: number
  travelers: number
  budget: number
  interests: string[]
}
