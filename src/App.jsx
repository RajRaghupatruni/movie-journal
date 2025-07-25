import { useState, useEffect } from "react";
import MovieSearch from "./components/MovieSearch";
import WatchedList from "./components/WatchedList";
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
  const [selectedMonthYear, setSelectedMonthYear] = useState("all");
  const [activeTab, setActiveTab] = useState("search");
  const [displayCount, setDisplayCount] = useState(20);
  const [inlineSearch, setInlineSearch] = useState("");

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

      <div className="flex justify-center space-x-4 mt-6">
        <button
          onClick={() => setActiveTab("search")}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === "search"
              ? "bg-zinc-700 text-white"
              : "bg-zinc-800 text-zinc-400 hover:text-white"
          }`}
        >
          Search
        </button>
        <button
          onClick={() => setActiveTab("watched")}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === "watched"
              ? "bg-zinc-700 text-white"
              : "bg-zinc-800 text-zinc-400 hover:text-white"
          }`}
        >
          Watched
        </button>
      </div>

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
    </div>
  );
}

export default App;
