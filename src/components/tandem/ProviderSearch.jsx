import { useEffect, useState } from 'react'
import { LoaderCircle, MapPin, Search } from 'lucide-react'
import { ApiError, tandemApi } from '../../lib/tandemApi'

function useProviderSearch(query, search) {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const clean = query.trim()
    if (clean.length < 2) { setResults([]); setError(''); setLoading(false); return undefined }
    let active = true
    const timer = window.setTimeout(async () => {
      setLoading(true); setError('')
      try {
        const response = await search(clean)
        if (active) setResults(response.items)
      } catch (caught) {
        if (active) {
          setResults([])
          setError(caught instanceof ApiError && caught.status === 503 ? 'Search is temporarily unavailable. You can enter this memory manually.' : 'We could not search right now. Try again.')
        }
      } finally { if (active) setLoading(false) }
    }, 350)
    return () => { active = false; window.clearTimeout(timer) }
  }, [query, search])
  return { results, loading, error }
}

export function MovieSearchPicker({ selected, onSelect }) {
  const [query, setQuery] = useState(selected?.title || '')
  const { results, loading, error } = useProviderSearch(query, tandemApi.searchMovies)
  return <div className="provider-picker"><label>Search for a movie<span className="form-hint">TMDb</span><div className="provider-input"><Search size={16} /><input value={query} onChange={(event) => { setQuery(event.target.value); if (selected) onSelect(null) }} placeholder="Search by title…" aria-label="Search for a movie" /></div></label>{loading && <p className="provider-status"><LoaderCircle size={15} className="spin" /> Searching movies…</p>}{error && <p className="provider-error" role="status">{error}</p>}{!loading && !error && query.trim().length >= 2 && !results.length && <p className="provider-status">No movies found. You can enter a title manually below.</p>}{results.length > 0 && !selected && <div className="provider-results" role="listbox" aria-label="Movie results">{results.map((movie) => <button type="button" key={movie.tmdb_id} className="provider-result" onClick={() => { onSelect(movie); setQuery(movie.title) }}><img src={movie.poster_url || '/placeholder-movie.svg'} alt="" loading="lazy" /><span><strong>{movie.title}</strong><small>{movie.release_year || 'Release year unknown'}</small></span></button>)}</div>}{selected && <div className="selected-provider"><img src={selected.poster_url || '/placeholder-movie.svg'} alt="" /><span><strong>{selected.title}</strong><small>{selected.release_year || 'Release year unknown'} · Saved TMDb snapshot</small></span><button type="button" className="text-action" onClick={() => { onSelect(null); setQuery('') }}>Change</button></div>}</div>
}

export function PlaceSearchPicker({ selected, onSelect }) {
  const [query, setQuery] = useState(selected?.name || '')
  const { results, loading, error } = useProviderSearch(query, tandemApi.searchPlaces)
  return <div className="provider-picker"><label>Where did this happen?<span className="form-hint">Geoapify</span><div className="provider-input"><MapPin size={16} /><input value={query} onChange={(event) => { setQuery(event.target.value); if (selected) onSelect(null) }} placeholder="Search for a place…" aria-label="Search for a place" /></div></label>{loading && <p className="provider-status"><LoaderCircle size={15} className="spin" /> Searching places…</p>}{error && <p className="provider-error" role="status">{error}</p>}{!loading && !error && query.trim().length >= 2 && !results.length && <p className="provider-status">No places found. Enter a place name manually below.</p>}{results.length > 0 && !selected && <div className="provider-results" role="listbox" aria-label="Place results">{results.map((place) => <button type="button" key={place.provider_place_id} className="provider-result provider-place-result" onClick={() => { onSelect(place); setQuery(place.name) }}><span className="provider-result-icon"><MapPin size={17} /></span><span><strong>{place.name}</strong><small>{place.formatted_address || [place.city, place.region, place.country].filter(Boolean).join(', ')}</small></span></button>)}</div>}{selected && <div className="selected-provider selected-place"><span className="provider-result-icon"><MapPin size={17} /></span><span><strong>{selected.name}</strong><small>{selected.formatted_address || [selected.city, selected.region, selected.country].filter(Boolean).join(', ')}</small></span><button type="button" className="text-action" onClick={() => { onSelect(null); setQuery('') }}>Change</button></div>}</div>
}
