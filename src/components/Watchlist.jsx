import { useEffect, useState } from "react";
import { db } from "../firebase";
import {
  collection,
  onSnapshot,
  deleteDoc,
  doc,
  orderBy,
  query,
  setDoc,
  serverTimestamp,
} from "firebase/firestore";
import { Trash2, ChevronDown, Search, BookmarkX } from "lucide-react";
import toast from "react-hot-toast";
import EditMovieModal from "./EditMovieModal";
import WatchlistCard from "./WatchlistCard";


function Watchlist() {
  const [watchlist, setWatchlist] = useState([]);
  const [sortBy, setSortBy] = useState("recent");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const q = query(collection(db, "watchlistMovies"), orderBy("addedAt", "desc"));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const movies = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }));
      setWatchlist(movies);
    });

    return () => unsubscribe();
  }, []);

  const handleRemove = async (movieId) => {
    const movieToDelete = watchlist.find((m) => m.id === movieId);
    if (!movieToDelete) return;

    await deleteDoc(doc(db, "watchlistMovies", movieId));

    toast.custom((t) => (
      <div
        className={`px-4 py-2 rounded-lg shadow-lg border border-zinc-700 bg-zinc-900 text-white text-sm flex items-center justify-between gap-4 ${
          t.visible ? "animate-fadeInUp" : "opacity-0"
        }`}
      >
        <span>❌ Removed from Watchlist.</span>
        <button
          onClick={async () => {
            await setDoc(doc(db, "watchlistMovies", movieToDelete.id), {
              ...movieToDelete,
              addedAt: serverTimestamp(),
            });
            toast.dismiss(t.id);
            toast.success("Undo successful ✅", {
              style: {
                background: "#1e1e1e",
                color: "#fff",
                border: "1px solid #444",
              },
            });
          }}
          className="text-indigo-400 underline hover:text-indigo-300"
        >
          Undo
        </button>
      </div>
    ));
  };

  const handleMarkAsWatchedComplete = async (movieId) => {
    await deleteDoc(doc(db, "watchlistMovies", movieId));
    toast.success("Moved to Watched!", {
      style: {
        background: "#1e1e1e",
        color: "#fff",
        border: "1px solid #444",
      },
    });
  };

  const filteredMovies = watchlist.filter((movie) =>
    movie.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedMovies = [...filteredMovies].sort((a, b) => {
    if (sortBy === "title-asc") return a.title.localeCompare(b.title);
    if (sortBy === "title-desc") return b.title.localeCompare(a.title);
    return 0;
  });

  return (
    <div className="max-w-6xl mx-auto mt-10 px-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <h2 className="text-xl font-semibold">🎯 Your Watchlist</h2>

        <div className="flex flex-col sm:flex-row gap-3 sm:items-center w-full sm:w-auto sm:ml-auto">
          {/* 🔍 Search Input */}
          <div className="relative w-full sm:w-64">
            <input
              type="text"
              placeholder="Search Watchlist..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-600 text-sm text-white rounded-md pl-9 pr-3 py-2 shadow focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-400" />
          </div>

          {/* ⏳ Sort Dropdown */}
          <div className="relative w-full sm:w-auto">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="appearance-none bg-zinc-800 border border-zinc-600 text-sm text-white rounded-md pl-3 pr-8 py-2 shadow focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="recent">Sort: Recently Added</option>
              <option value="title-asc">Sort: Title A-Z</option>
              <option value="title-desc">Sort: Title Z-A</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-400 pointer-events-none" />
          </div>
        </div>
      </div>

      {sortedMovies.length === 0 ? (
        <div className="flex flex-col items-center text-center text-zinc-400 mt-20">
          <BookmarkX className="w-12 h-12 mb-4 text-zinc-500" />
          <p className="text-lg font-semibold">Nothing to see here yet!</p>
          <p className="text-sm">Add movies to your Watchlist to track them.</p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {sortedMovies.map((movie) => (
            <WatchlistCard
                key={movie.id}
                movie={movie}
                onWatched={handleMarkAsWatchedComplete}
                onRemove={handleRemove}
            />
            ))}
        </div>
      )}
    </div>
  );
}

export default Watchlist;
