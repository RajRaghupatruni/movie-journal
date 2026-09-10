import { useEffect, useState } from "react";
import AddMovieModal from "./AddMovieModal";
import AddToWatchlistButton from "./AddToWatchlistButton";
// DEPRECATED MIGRATION REFERENCE: the active Keepsake form uses the backend TMDb picker.
import { legacyProviderRequest, legacyProviderSearchEnabled } from "../lib/legacyProviders";

function MovieSearch({ onAdd }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  useEffect(() => {
    const fetchMovies = async () => {
      if (!legacyProviderSearchEnabled || !query) {
        setResults([]);
        return;
      }

      try {
        // 1. Try searching by movie title
        const movieRes = await legacyProviderRequest(
          `/search/movie?query=${encodeURIComponent(query)}`
        );
        const movieData = await movieRes.json();
        let combinedResults = movieData.results || [];

        // 2. If very few results (0–1), try treating query as actor name
        if (combinedResults.length <= 1) {
          const personRes = await legacyProviderRequest(
            `/search/person?query=${encodeURIComponent(query)}`
          );
          const personData = await personRes.json();
          const person = personData.results?.[0];

          if (person) {
            const creditsRes = await legacyProviderRequest(
              `/person/${person.id}/movie_credits`
            );
            const creditsData = await creditsRes.json();
            const actorMovies = creditsData.cast || [];

            // Merge without duplicates (based on movie ID)
            const movieIds = new Set(combinedResults.map((m) => m.id));
            actorMovies.forEach((m) => {
              if (!movieIds.has(m.id)) {
                combinedResults.push(m);
              }
            });
          }
        }

        setResults(combinedResults);
      } catch (err) {
        console.error("Error fetching TMDb data:", err);
      }
    };

    const delay = setTimeout(fetchMovies, 500);
    return () => clearTimeout(delay);
  }, [query]);

  const handleWatched = async (movie) => {
    await onAdd(movie);
    setToastMessage("✅ Added to Watched List!");
    setShowToast(true);
    setTimeout(() => setShowToast(false), 2000);
  };

  const handleWatchlistAdded = (message) => {
    setToastMessage(message);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 2000);
  };

  return (
    <div className="space-y-4 relative">
      {!legacyProviderSearchEnabled && <p role="status" className="text-sm text-zinc-400">Movie search is temporarily unavailable. Your saved movies and watchlist remain available.</p>}
      <input
        disabled={!legacyProviderSearchEnabled}
        type="text"
        placeholder="Search for a movie or actor..."
        className="w-full px-4 py-3 rounded-xl bg-zinc-800 text-white placeholder-zinc-400 border border-zinc-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-md backdrop-blur-sm"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {results.length > 0 && (
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3">
          {results.slice(0, 6).map((movie) => (
            <div key={movie.id} className="relative group bg-zinc-900 rounded-lg overflow-hidden shadow-md">
              <img
                src={
                  movie.poster_path
                    ? `https://image.tmdb.org/t/p/w500${movie.poster_path}`
                    : "https://via.placeholder.com/200x300?text=No+Image"
                }
                alt={movie.title}
                className="w-full h-[225px] sm:h-[250px] object-cover"
              />

              <div className="p-2 text-white text-sm space-y-0.5 bg-zinc-900">
                <div className="font-semibold truncate">{movie.title}</div>
                <div className="text-zinc-400 text-xs">{movie.release_date?.slice(0, 4)}</div>
              </div>

              <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center space-y-2 px-2">
                <AddMovieModal
                  movie={movie}
                  onSave={handleWatched}
                  triggerClass="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded text-xs font-medium"
                />
                <AddToWatchlistButton
                  movie={movie}
                  onToast={handleWatchlistAdded}
                  triggerClass="bg-zinc-700 hover:bg-zinc-800 text-white px-3 py-1 rounded text-xs font-medium"
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {showToast && (
        <div className="absolute top-0 right-0 mt-2 mr-2 px-4 py-2 bg-green-600 text-white text-sm rounded-lg shadow-lg z-20 animate-fadeInOut">
          {toastMessage}
        </div>
      )}
    </div>
  );
}

export default MovieSearch;
