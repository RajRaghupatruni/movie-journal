import EditMovieModal from "./EditMovieModal";
import { Trash2 } from "lucide-react";
import { Check } from "lucide-react";

function WatchlistCard({ movie, onWatched, onRemove }) {
  return (
    <div
      className="relative bg-zinc-800 rounded-md shadow-md overflow-hidden group transition hover:scale-[1.02]"
    >
      <img
        src={movie.poster ? `https://image.tmdb.org/t/p/w500${movie.poster}` : "https://via.placeholder.com/200x300?text=No+Image"}
        alt={movie.title}
        className="w-full h-[225px] sm:h-[250px] object-cover rounded-md"
      />

      <div className="p-2 text-white text-sm space-y-0.5 bg-zinc-900">
        <div className="font-semibold truncate">{movie.title}</div>
        {movie.year && (
          <div className="text-xs text-zinc-400">{movie.year}</div>
        )}
      </div>

      {/* Hover Actions */}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-4 transition-opacity">
        <EditMovieModal
          movie={{ ...movie, fromWatchlist: true }}
          triggerClass="bg-green-600 hover:bg-green-700 p-2 rounded-full text-white"
          onComplete={() => onWatched(movie.id)}
        >
          <Check className="w-4 h-4" />
        </EditMovieModal>

        <button
          onClick={() => onRemove(movie.id)}
          title="Remove from Watchlist"
          className="bg-red-600 hover:bg-red-700 p-2 rounded-full text-white"
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

export default WatchlistCard;
