// All backend calls live here. Types mirror backend/schemas.py.

export type ProviderType = 'carer' | 'driver'

export interface Competency {
  code: string
  label: string
}

export interface ProviderCompetency extends Competency {
  /** An uploaded document backs this competency. */
  verified: boolean
}

export interface VerificationSummary {
  verification_id: number
  confidence: number
  /** confidence is at or above the Verified threshold (decided by the backend). */
  verified: boolean
  verified_at: string
}

export interface Provider {
  id: number
  name: string
  provider_type: ProviderType
  bio: string | null
  location: string | null
  latitude: number | null
  longitude: number | null
  created_at: string
  updated_at: string
  competencies: ProviderCompetency[]
  verification: VerificationSummary | null
}

export interface SearchFilter {
  provider_type: ProviderType | null
  required_competencies: string[]
  location: string | null
}

/** Why a result is ranked where it is. Each part is 0-1 (see backend/ranking.py). */
export interface RankingBreakdown {
  competency_match: number
  verification_confidence: number
  availability: number
  distance: number
  distance_km: number | null
  /** 0.40, 0.25, 0.20 and 0.15 times the parts above. */
  score: number
}

export interface RankedProvider extends Provider {
  ranking: RankingBreakdown
}

export interface SearchResponse {
  query: string
  /** What the LLM understood from the query alone. These filter the results. */
  query_filter: SearchFilter
  /** Everything considered: the query's requirements plus the saved profile's. */
  filter: SearchFilter
  filter_parsed: boolean
  profile_applied: boolean
  /** Saved needs used for ranking (they don't filter). */
  added_from_profile: string[]
  /** Location the distance score is measured from, or null if unknown. */
  ranked_from: string | null
  /** Sorted by ranking.score, highest first. */
  results: RankedProvider[]
}

export type MobilityDevice =
  | 'none'
  | 'manual_wheelchair'
  | 'powered_wheelchair'
  | 'mobility_scooter'
  | 'walking_aid'
  | 'other'

export type CommunicationNeed = 'bsl' | 'lip_reading' | 'written' | 'easy_read' | 'extra_time'

export interface Profile {
  mobility_device: MobilityDevice | null
  communication_needs: CommunicationNeed[]
  required_competencies: string[]
  location: string | null
}

export interface Me {
  user: { id: number; email: string; created_at: string }
  profile: (Profile & { updated_at: string }) | null
}

export interface Slot {
  id: number
  provider_id: number
  starts_at: string
  ends_at: string
  booked: boolean
}

export type VerificationStatus = 'corroborated' | 'self_reported' | 'documented_only'

/** A frozen copy of the provider's verification at the moment of booking. */
export interface VerificationSnapshot {
  captured_at: string
  provider: { id: number; name: string; provider_type: ProviderType; location: string | null }
  verification: {
    verification_id: number
    confidence: number
    verified: boolean
    threshold: number
    verified_at: string
  } | null
  competencies: {
    code: string
    label: string
    held: boolean
    relevant: boolean
    verified: boolean
    status: VerificationStatus | null
    confidence: number | null
    verified_at: string | null
    bio_evidence: string | null
    document_evidence: string | null
  }[]
}

export interface Booking {
  id: number
  provider_id: number | null
  slot_id: number | null
  starts_at: string
  ends_at: string
  pickup: string
  dropoff: string | null
  notes: string | null
  verification_snapshot: VerificationSnapshot
  status: 'confirmed' | 'cancelled'
  cancelled_at: string | null
  created_at: string
}

export interface BookingRequest {
  provider_id: number
  requested_time: string
  pickup: string
  dropoff: string | null
  notes: string | null
}

/** The session is missing or expired; the user needs to log in again. */
export class AuthError extends Error {}

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'
const TOKEN_KEY = 'vouch.token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage unavailable (e.g. private mode): stay logged in for this page only.
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
    })
  } catch (error) {
    if (init?.signal?.aborted) throw error
    throw new Error("Couldn't reach the server. Check your connection and try again.", {
      cause: error,
    })
  }

  if (response.status >= 500) {
    throw new Error('Something went wrong on our side. Please try again in a moment.')
  }
  if (!response.ok) {
    const detail = await errorDetail(response)
    if (response.status === 401 && token) {
      throw new AuthError('Your session has expired. Please log in again.')
    }
    throw new Error(detail ?? `The request failed (error ${response.status}). Please try again.`)
  }
  return response.json() as Promise<T>
}

/** The backend's human-readable message, when it sent one. */
async function errorDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg
  } catch {
    // Not JSON.
  }
  return null
}

interface SearchOptions {
  useProfile?: boolean
  skipProfileCompetencies?: string[]
  signal?: AbortSignal
}

export function searchProviders(query: string, options: SearchOptions = {}) {
  return request<SearchResponse>('/search', {
    method: 'POST',
    body: JSON.stringify({
      query,
      use_profile: options.useProfile ?? true,
      skip_profile_competencies: options.skipProfileCompetencies ?? [],
    }),
    signal: options.signal,
  })
}

export function listCompetencies() {
  return request<Competency[]>('/competencies')
}

export async function signUp(email: string, password: string) {
  const { access_token } = await request<{ access_token: string }>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setToken(access_token)
}

export async function logIn(email: string, password: string) {
  // The login endpoint uses the standard OAuth2 form format, not JSON.
  const { access_token } = await request<{ access_token: string }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: email, password }),
  })
  setToken(access_token)
}

export function logOut() {
  setToken(null)
}

export function getMe() {
  return request<Me>('/me')
}

export function listAvailability(providerId: number, availableOnly = true) {
  return request<Slot[]>(`/providers/${providerId}/availability?available_only=${availableOnly}`)
}

export function createBooking(booking: BookingRequest) {
  return request<Booking>('/bookings', { method: 'POST', body: JSON.stringify(booking) })
}

export function listBookings() {
  return request<Booking[]>('/bookings')
}

export function getBooking(id: number) {
  return request<Booking>(`/bookings/${id}`)
}

export function cancelBooking(id: number) {
  return request<Booking>(`/bookings/${id}/cancel`, { method: 'POST' })
}

export function saveProfile(profile: Profile) {
  return request<Me['profile']>('/me/profile', {
    method: 'PUT',
    body: JSON.stringify(profile),
  })
}
