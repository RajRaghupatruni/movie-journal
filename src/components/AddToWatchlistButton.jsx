import { useState } from "react";
import {
  collection,
  addDoc,
  getDocs,
  query,
  where,
  Timestamp,
} from "firebase/firestore";
import { db } from "../firebase";

function AddToWatchlistButton({ movie, onToast, triggerClass }) {
  const [loading, setLoading] = useState(false);

  const handleAddToWatchlist = async () => {
    setLoading(true);

    try {
      // Prevent duplicates by checking TMDB ID
      const q = query(collection(db, "watchlistMovies"), where("tmdbId", "==", movie.id));
      const snapshot = await getDocs(q);

      if (!snapshot.empty) {
        onToast("⚠️ Movie already in Watchlist!");
        setLoading(false);
        return;
      }

      const newMovie = {
        tmdbId: movie.id,
        title: movie.title,
        poster: `https://image.tmdb.org/t/p/w500${movie.poster_path}`,
        year: movie.release_date?.slice(0, 4) || "N/A",
        addedAt: Timestamp.now(),
      };

      await addDoc(collection(db, "watchlistMovies"), newMovie);
      onToast("🎯 Added to Watchlist!");
    } catch (error) {
      console.error("Error adding to watchlist:", error);
      onToast("❌ Failed to add movie.");
    }

    setLoading(false);
  };

  return (
    <button
      onClick={handleAddToWatchlist}
      className={`${triggerClass} ${loading ? "opacity-60 cursor-not-allowed" : ""}`}
      disabled={loading}
    >
      {loading ? "Adding..." : "Add to Watchlist"}
    </button>
  );
}

export default AddToWatchlistButton;
