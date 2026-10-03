// All backend calls live here. Types mirror backend/schemas.py.

export type ProviderType = 'carer' | 'driver'

export interface Competency {
  code: string
  label: string
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
  competencies: Competency[]
}

export interface SearchFilter {
  provider_type: ProviderType | null
  required_competencies: string[]
  location: string | null
}

export interface SearchResponse {
  query: string
  filter: SearchFilter
  filter_parsed: boolean
  results: Provider[]
}

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
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
    throw new Error(`The request failed (error ${response.status}). Please try again.`)
  }
  return response.json() as Promise<T>
}

export function searchProviders(query: string, signal?: AbortSignal) {
  return request<SearchResponse>('/search', {
    method: 'POST',
    body: JSON.stringify({ query }),
    signal,
  })
}

export function listCompetencies() {
  return request<Competency[]>('/competencies')
}
