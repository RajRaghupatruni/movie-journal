import { useEffect, useState } from "react";
import AddMovieModal from "./AddMovieModal";
import AddToWatchlistButton from "./AddToWatchlistButton";

const TMDB_API_KEY = import.meta.env.VITE_TMDB_API_KEY;

function MovieSearch({ onAdd }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  useEffect(() => {
    const fetchMovies = async () => {
      if (!query) {
        setResults([]);
        return;
      }

      try {
        const res = await fetch(
          `https://api.themoviedb.org/3/search/movie?api_key=${TMDB_API_KEY}&query=${encodeURIComponent(query)}`
        );
        const data = await res.json();
        setResults(data.results || []);
      } catch (err) {
        console.error("Error fetching TMDb movies:", err);
      }
    };

    const delay = setTimeout(fetchMovies, 500); // debounce
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
      <input
        type="text"
        placeholder="Search for a movie..."
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

              {/* Hover buttons */}
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
