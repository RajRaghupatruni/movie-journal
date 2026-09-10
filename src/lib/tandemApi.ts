export type MemoryCategory = 'movie' | 'place' | 'trip' | 'activity' | 'custom'

export interface ApiUser {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  timezone?: string
}

export interface ApiPreferences {
  timezone: string
  anniversary_notifications_enabled: boolean
  anniversary_email_enabled: boolean
  notification_hour: number
}

export interface ApiTandem {
  id: string
  name: string
  created_by: string
  timezone: string
  created_at: string
  updated_at: string
}

export interface ApiMember {
  user_id: string
  email: string
  display_name: string
  avatar_url: string | null
  role: string
  joined_at: string
}

export interface ApiMemory {
  id: string
  tandem_id: string
  category: MemoryCategory
  title: string
  local_date: string
  occurred_at: string | null
  timezone: string
  notes: string | null
  rating: number | null
  created_by: string
  created_at: string
  updated_at: string
  version: number
  nostalgia_eligible: boolean
  schema_version: number
  metadata: Record<string, unknown>
  participants: Array<Pick<ApiMember, 'user_id' | 'display_name' | 'email' | 'avatar_url'>>
  tags: string[]
  media: ApiMedia[]
}

export interface ApiAnniversary {
  memory: ApiMemory
  years_ago: number
  original_date: string
  anniversary_date: string
}

export interface ApiOnThisDay {
  today: string
  timezone: string
  anniversaries: ApiAnniversary[]
  fallback: ApiMemory | null
}

export interface ApiMedia {
  id: string
  memory_id: string
  content_type: string
  byte_size: number
  width: number
  height: number
  original_filename: string | null
  created_by: string
  created_at: string
  display_order: number
  url: string | null
}

export interface ApiMovieSearchResult {
  tmdb_id: number
  title: string
  original_title: string | null
  release_date: string | null
  release_year: number | null
  poster_url: string | null
  backdrop_url: string | null
  overview: string | null
  genres: string[]
  runtime_minutes: number | null
}

export interface ApiPlaceSearchResult {
  provider: 'geoapify'
  provider_place_id: string
  name: string
  formatted_address: string | null
  city: string | null
  region: string | null
  country: string | null
  latitude: number | null
  longitude: number | null
  category: string | null
}

export interface MemoryListParams {
  category?: MemoryCategory
  from_date?: string
  to_date?: string
  year?: number
  participant?: string
  rating_min?: number
  rating_max?: number
  tag?: string
  q?: string
  offset?: number
  limit?: number
}

export type MemoryInput = Omit<ApiMemory, 'id' | 'tandem_id' | 'created_by' | 'created_at' | 'updated_at' | 'version' | 'schema_version' | 'participants' | 'tags'> & {
  participant_ids: string[]
  tags: string[]
}

export type MemoryPatchInput = Partial<Omit<MemoryInput, 'category'>> & {
  expected_version: number
  category?: MemoryCategory
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : 'Request failed')
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    const isMultipart = typeof FormData !== 'undefined' && options.body instanceof FormData
    response = await fetch(path, { ...options, credentials: 'include', headers: { ...(isMultipart ? {} : { 'Content-Type': 'application/json' }), ...options.headers } })
  } catch {
    throw new ApiError(0, 'Network error. Check your connection and try again.')
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null)
  if (response.status === 401 && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('tandem:session-expired'))
  }
  if (!response.ok) throw new ApiError(response.status, body?.detail || 'Request failed')
  return body as T
}

export const tandemApi = {
  me: () => request<ApiUser>('/api/me'),
  tandems: () => request<ApiTandem[]>('/api/me/tandems'),
  createTandem: (input: { name: string; timezone: string }) => request<ApiTandem>('/api/tandems', { method: 'POST', body: JSON.stringify(input) }),
  preferences: () => request<ApiPreferences>('/api/me/preferences'),
  updatePreferences: (input: Partial<ApiPreferences>) => request<ApiPreferences>('/api/me/preferences', { method: 'PATCH', body: JSON.stringify(input) }),
  invitation: (reference: string) => request<{ id: string; tandem_id: string; tandem_name: string; invited_email: string; status: string; expires_at: string; inviter_name?: string | null }>(`/api/invitations/${encodeURIComponent(reference)}`),
  acceptInvitation: (reference: string) => request<{ tandem_id: string; tandem_name: string; status: string }>(`/api/invitations/${encodeURIComponent(reference)}/accept`, { method: 'POST' }),
  members: (tandemId: string) => request<ApiMember[]>(`/api/tandems/${tandemId}/members`),
  onThisDay: (tandemId: string) => request<ApiOnThisDay>(`/api/tandems/${tandemId}/on-this-day`),
  memories: (tandemId: string, params: MemoryListParams = {}) => {
    const search = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') search.set(key, String(value)) })
    return request<{ items: ApiMemory[]; offset: number; limit: number; next_offset: number | null }>(`/api/tandems/${tandemId}/memories${search.size ? `?${search}` : ''}`)
  },
  memory: (tandemId: string, memoryId: string) => request<ApiMemory>(`/api/tandems/${tandemId}/memories/${memoryId}`),
  createMemory: (tandemId: string, input: MemoryInput) => request<ApiMemory>(`/api/tandems/${tandemId}/memories`, { method: 'POST', body: JSON.stringify(input) }),
  updateMemory: (tandemId: string, memoryId: string, input: MemoryPatchInput) => request<ApiMemory>(`/api/tandems/${tandemId}/memories/${memoryId}`, { method: 'PATCH', body: JSON.stringify(input) }),
  deleteMemory: (tandemId: string, memoryId: string, expectedVersion?: number) => request<void>(`/api/tandems/${tandemId}/memories/${memoryId}${expectedVersion ? `?expected_version=${expectedVersion}` : ''}`, { method: 'DELETE' }),
  searchMovies: (query: string) => request<{ items: ApiMovieSearchResult[] }>(`/api/integrations/movies/search?q=${encodeURIComponent(query)}`),
  movie: (tmdbId: number) => request<ApiMovieSearchResult>(`/api/integrations/movies/${tmdbId}`),
  searchPlaces: (query: string) => request<{ items: ApiPlaceSearchResult[] }>(`/api/integrations/places/search?q=${encodeURIComponent(query)}`),
  memoryMedia: (tandemId: string, memoryId: string) => request<ApiMedia[]>(`/api/tandems/${tandemId}/memories/${memoryId}/media`),
  uploadMemoryMedia: (tandemId: string, memoryId: string, files: File[]) => {
    const body = new FormData()
    files.forEach((file) => body.append('files', file, file.name))
    return request<ApiMedia[]>(`/api/tandems/${tandemId}/memories/${memoryId}/media`, { method: 'POST', body })
  },
  deleteMemoryMedia: (tandemId: string, memoryId: string, mediaId: string) => request<void>(`/api/tandems/${tandemId}/memories/${memoryId}/media/${mediaId}`, { method: 'DELETE' }),
}
