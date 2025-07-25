import { useEffect, useState } from "react";
import AddMovieModal from "./AddMovieModal";

const TMDB_API_KEY = import.meta.env.VITE_TMDB_API_KEY;

function MovieSearch({ onAdd }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [showToast, setShowToast] = useState(false);

  useEffect(() => {
    const fetchMovies = async () => {
      if (!query) {
        setResults([]);
        return;
      }

      try {
        const res = await fetch(
          `https://api.themoviedb.org/3/search/movie?api_key=${TMDB_API_KEY}&query=${query}`
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

  const handleSave = async (movie) => {
    await onAdd(movie);
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
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
          {results.slice(0, 6).map((movie) => (
            <AddMovieModal key={movie.id} movie={movie} onSave={handleSave} />
          ))}
        </div>
      )}

      {showToast && (
        <div className="absolute top-0 right-0 mt-2 mr-2 px-4 py-2 bg-green-600 text-white text-sm rounded-lg shadow-lg z-20 animate-fadeInOut">
          ✅ Added to Watchlist!
        </div>
      )}
    </div>
  );
}

export default MovieSearch;
