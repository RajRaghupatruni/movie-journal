import { useState, useEffect } from "react";
import MovieSearch from "./components/MovieSearch";
import WatchedList from "./components/WatchedList";
import Watchlist from "./components/Watchlist";
import AddEventModal from "./components/AddEventModal";
import Timeline from "./components/Timeline";
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
  const [watchlistMovies, setWatchlistMovies] = useState([]);
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
      <header className="bg-zinc-900/70 backdrop-blur-lg shadow-md py-6 px-6 sticky top-0 z-10 border-b border-zinc-700">
        <h1 className="text-4xl sm:text-5xl text-center tracking-tight text-white drop-shadow-md font-title">
          Tandem
        </h1>
        <p className="text-center text-base sm:text-lg text-zinc-400 mt-2 font-light tracking-wide italic font-sans">
          From watchlist to watched. Together.
        </p>
      </header>

      {/* 🎯 Add Event Button */}
      <div className="flex justify-center mt-6">
        <AddEventModal tandemId="test-tandem-id" />
      </div>

      {/* 🔁 Tab navigation */}
      <div className="flex justify-center space-x-4 mt-6">
        <button
          onClick={() => setActiveTab("search")}
          className={`px-4 py-2 rounded-md transition ${
            activeTab === "search"
              ? "bg-indigo-600 text-white"
              : "bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
          }`}
        >
          Search
        </button>
        <button
          onClick={() => setActiveTab("watched")}
          className={`px-4 py-2 rounded-md transition ${
            activeTab === "watched"
              ? "bg-indigo-600 text-white"
              : "bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
          }`}
        >
          Watched
        </button>
        <button
          onClick={() => setActiveTab("watchlist")}
          className={`px-4 py-2 rounded-md transition ${
            activeTab === "watchlist"
              ? "bg-indigo-600 text-white"
              : "bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
          }`}
        >
          Watchlist
        </button>
        <button
          onClick={() => setActiveTab("timeline")}
          className={`px-4 py-2 rounded-md transition ${
            activeTab === "timeline"
              ? "bg-indigo-600 text-white"
              : "bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
          }`}
        >
          Timeline
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

      {activeTab === "timeline" && (
        <div className="mt-8">
          <Timeline tandemId="test-tandem-id" />
        </div>
      )}
    </div>
  );
}

export default App;
