import { useState, useEffect } from "react";
import MovieSearch from "./components/MovieSearch";
import WatchedList from "./components/WatchedList";
import Watchlist from "./components/Watchlist"; // ⬅️ New component
import { db } from "./firebase";
import {
  collection,
  onSnapshot,
  addDoc,
  deleteDoc,
  doc,
  query,
  orderBy,
} from "firebase/firestore";

function App() {
  const [watchedMovies, setWatchedMovies] = useState([]);
  const [watchlistMovies, setWatchlistMovies] = useState([]); // ⬅️ New state
  const [selectedMonthYear, setSelectedMonthYear] = useState("all");
  const [activeTab, setActiveTab] = useState("search");
  const [displayCount, setDisplayCount] = useState(20);
  const [inlineSearch, setInlineSearch] = useState("");

  // 🔁 Firestore listener for watched movies
  useEffect(() => {
    const q = query(
      collection(db, "watchedMovies"),
      orderBy("dateWatched", "desc")
    );
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const movies = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }));
      setWatchedMovies(movies);
    });
    return () => unsubscribe();
  }, []);

  // 🔁 Firestore listener for watchlist
  useEffect(() => {
    const unsubscribe = onSnapshot(collection(db, "watchlistMovies"), (snapshot) => {
      const movies = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }));
      setWatchlistMovies(movies);
    });
    return () => unsubscribe();
  }, []);

  const handleAddMovie = async (movie) => {
    const exists = watchedMovies.some((m) => m.tmdbId === movie.id);
    if (exists) return;

    const newMovie = {
      tmdbId: movie.id,
      title: movie.title,
      poster: movie.poster,
      dateWatched: movie.dateWatched,
      rating: movie.rating,
      review: movie.review,
    };

    await addDoc(collection(db, "watchedMovies"), newMovie);
  };

  const handleRemoveMovie = async (id) => {
    await deleteDoc(doc(db, "watchedMovies", id));
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-900 to-zinc-800 text-zinc-100 font-sans">
      <header className="bg-zinc-900/70 backdrop-blur-lg shadow-md py-4 px-6 sticky top-0 z-10 border-b border-zinc-700">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-center tracking-tight text-white">
          🎬 Movie Journal
        </h1>
        <p className="text-center text-sm text-zinc-400 mt-1">
          Track what you watch. Remember what you feel.
        </p>
      </header>

      {/* 🔁 Tab navigation */}
      <div className="flex justify-center space-x-4 mt-6">
        <button
          onClick={() => setActiveTab("search")}
          className={`tab-button ${
            activeTab === "search"
              ? "tab-button-active"
              : "tab-button-inactive"
          }`}
        >
          Search
        </button>
        <button
          onClick={() => setActiveTab("watched")}
          className={`tab-button ${
            activeTab === "watched"
              ? "tab-button-active"
              : "tab-button-inactive"
          }`}
        >
          Watched
        </button>
        <button
          onClick={() => setActiveTab("watchlist")}
          className={`tab-button ${
            activeTab === "watchlist"
              ? "tab-button-active"
              : "tab-button-inactive"
          }`}
        >
          Watchlist
        </button>
      </div>

      {/* 🔁 Render based on tab */}
      {activeTab === "search" && (
        <div className="max-w-2xl mx-auto mt-10 px-4">
          <MovieSearch onAdd={handleAddMovie} />
        </div>
      )}

      {activeTab === "watched" && (
        <WatchedList
          watchedMovies={watchedMovies}
          handleRemoveMovie={handleRemoveMovie}
          selectedMonthYear={selectedMonthYear}
          setSelectedMonthYear={setSelectedMonthYear}
          inlineSearch={inlineSearch}
          setInlineSearch={setInlineSearch}
          displayCount={displayCount}
          setDisplayCount={setDisplayCount}
        />
      )}

      {activeTab === "watchlist" && (
        <Watchlist watchlistMovies={watchlistMovies} />
      )}
    </div>
  );
}

export default App;
