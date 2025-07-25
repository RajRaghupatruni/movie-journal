import { useState, useEffect } from "react";
import { db } from "../firebase";
import {
  collection,
  onSnapshot,
  deleteDoc,
  doc,
  query,
  orderBy,
} from "firebase/firestore";
import { format } from "date-fns";
import { Transition } from "@headlessui/react";
import * as Dialog from "@radix-ui/react-dialog";
import { MoreVertical, Trash2, X } from "lucide-react";
import EditMovieModal from "./EditMovieModal";

function DeleteConfirmDialog({ movie, onDelete, onCancel }) {
  return (
    <Dialog.Root open onOpenChange={onCancel}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40" />
        <Dialog.Content className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-zinc-900 text-white p-6 rounded-xl w-full max-w-md border border-zinc-700 shadow-lg space-y-4">
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-lg font-bold flex items-center gap-2">
              <Trash2 className="text-red-400 w-5 h-5" />
              Confirm Delete
            </Dialog.Title>
            <Dialog.Close asChild>
              <button>
                <X className="text-zinc-500 hover:text-white w-5 h-5" />
              </button>
            </Dialog.Close>
          </div>
          <p className="text-zinc-300 text-sm">
            Are you sure you want to delete <strong>{movie.title}</strong> from your watched list?
          </p>
          <div className="flex justify-end gap-3 pt-4">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm bg-zinc-700 hover:bg-zinc-600 text-white rounded-md"
            >
              Cancel
            </button>
            <button
              onClick={() => onDelete(movie.id)}
              className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-md"
            >
              Yes, Delete
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function WatchedList() {
  const [watchedMovies, setWatchedMovies] = useState([]);
  const [selectedMonthYear, setSelectedMonthYear] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [visibleCount, setVisibleCount] = useState(20);
  const [modalContent, setModalContent] = useState(null);
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [deleteConfirmMovie, setDeleteConfirmMovie] = useState(null);

  useEffect(() => {
    const q = query(collection(db, "watchedMovies"), orderBy("dateWatched", "desc"));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const movies = snapshot.docs.map((doc) => {
        const data = doc.data();
        let date = data.dateWatched;

        if (date?.toDate) {
          date = date.toDate();
        } else if (typeof date === "string") {
          const [month, day, year] = date.split("/");
          date = new Date(`${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`);
        } else {
          date = new Date();
        }

        return {
          id: doc.id,
          ...data,
          dateWatched: date,
        };
      });
      setWatchedMovies(movies);
    });
    return () => unsubscribe();
  }, []);

  const handleRemoveMovie = async (id) => {
    await deleteDoc(doc(db, "watchedMovies", id));
  };

  const getUniqueMonthYears = () => {
    const months = new Set();
    watchedMovies.forEach((movie) => {
      const monthYear = format(movie.dateWatched, "yyyy-MM");
      months.add(monthYear);
    });
    return Array.from(months).sort().reverse();
  };

  const filteredMovies = watchedMovies
    .filter((movie) => {
      if (selectedMonthYear === "all") return true;
      return format(movie.dateWatched, "yyyy-MM") === selectedMonthYear;
    })
    .filter((movie) =>
      movie.title.toLowerCase().includes(searchTerm.toLowerCase())
    );

  const visibleMovies = filteredMovies.slice(0, visibleCount);

  return (
    <div className="space-y-6 max-w-5xl mx-auto px-4 py-6">
      {/* Filter Controls */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
        <select
          value={selectedMonthYear}
          onChange={(e) => setSelectedMonthYear(e.target.value)}
          className="border border-zinc-600 bg-zinc-800 text-zinc-100 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
        >
          <option value="all">📅 All Months</option>
          {getUniqueMonthYears().map((monthYear) => {
            const [year, month] = monthYear.split("-");
            const label = format(new Date(year, parseInt(month) - 1), "MMMM yyyy");
            return (
              <option key={monthYear} value={monthYear}>
                {label}
              </option>
            );
          })}
        </select>

        <input
          type="text"
          placeholder="🔍 Search watched movies..."
          className="px-3 py-2 rounded-md bg-zinc-800 text-white placeholder-zinc-400 border border-zinc-700 focus:ring-2 focus:ring-indigo-500 w-full sm:w-64"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {/* Watched Movie Grid */}
      {visibleMovies.length === 0 ? (
        <div className="h-72 bg-zinc-800/50 backdrop-blur-sm rounded-2xl shadow-inner flex flex-col items-center justify-center text-zinc-400 border border-dashed border-zinc-600">
          <span className="text-xl">No movies found...</span>
          <span className="text-sm">Try another month or search 🎥</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {visibleMovies.map((movie) => (
            <Transition
              key={movie.id}
              appear
              show={true}
              enter="transition duration-300 ease-out"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
            >
              <div className="relative flex gap-3 bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-3 shadow-md hover:shadow-lg transition-transform hover:scale-[1.01] h-48">
                <img
                  src={
                    movie.poster
                      ? `https://image.tmdb.org/t/p/w200${movie.poster}`
                      : "https://via.placeholder.com/100x150?text=No+Image"
                  }
                  alt={movie.title}
                  className="w-20 h-32 object-cover rounded-lg"
                />
                <div className="flex-1 text-sm text-zinc-200 space-y-1 overflow-hidden">
                  <h2 className="text-base font-semibold text-white">{movie.title}</h2>
                  <p className="text-zinc-400 text-xs">
                    Watched on {format(movie.dateWatched, "MMMM d, yyyy")}
                  </p>
                  <p className="text-yellow-400 font-medium text-sm">Rating: {movie.rating}/10</p>
                  <div
                    className="text-zinc-300 text-xs line-clamp-3 prose prose-sm prose-invert max-w-none"
                    dangerouslySetInnerHTML={{ __html: movie.review || "" }}
                  />
                </div>

                {/* Burger menu */}
                <div className="absolute top-3 right-3">
                  <div className="relative">
                    <button
                      onClick={() =>
                        setMenuOpenId((prev) => (prev === movie.id ? null : movie.id))
                      }
                      className="p-1 rounded hover:bg-zinc-700 text-white"
                    >
                      <MoreVertical className="w-4 h-4" />
                    </button>

                    {menuOpenId === movie.id && (
                      <div className="absolute right-0 mt-2 w-32 bg-zinc-800 border border-zinc-600 rounded-md shadow-lg z-50 text-sm">
                        <ul className="py-1">
                          {movie.review?.length > 0 && (
                            <li>
                              <button
                                onClick={() => {
                                  setModalContent(movie);
                                  setMenuOpenId(null);
                                }}
                                className="w-full text-left px-4 py-2 hover:bg-zinc-700 text-indigo-400"
                              >
                                Read
                              </button>
                            </li>
                          )}
                          <li>
                            <EditMovieModal
                              movie={movie}
                              triggerClass="w-full text-left px-4 py-2 hover:bg-zinc-700 text-white"
                            />
                          </li>
                          <li>
                            <button
                              onClick={() => {
                                setDeleteConfirmMovie(movie);
                                setMenuOpenId(null);
                              }}
                              className="w-full text-left px-4 py-2 hover:bg-zinc-700 text-red-400"
                            >
                              Delete
                            </button>
                          </li>
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </Transition>
          ))}
        </div>
      )}

      {/* Load More */}
      {visibleCount < filteredMovies.length && (
        <div className="text-center mt-4">
          <button
            onClick={() => setVisibleCount((prev) => prev + 20)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md shadow"
          >
            Load More
          </button>
        </div>
      )}

      {/* Read Modal */}
      {modalContent && (
        <Dialog.Root open={!!modalContent} onOpenChange={() => setModalContent(null)}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40" />
            <Dialog.Content className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-zinc-900 text-white p-6 rounded-xl w-full max-w-md border border-zinc-700 shadow-lg space-y-4">
              <Dialog.Title className="text-xl font-bold">{modalContent.title}</Dialog.Title>
              <p className="text-sm text-zinc-400">
                Watched on {format(modalContent.dateWatched, "MMMM d, yyyy")}
              </p>
              <p className="text-yellow-400">Rating: {modalContent.rating}/10</p>
              <div
                className="text-zinc-300 text-sm prose prose-invert max-w-none"
                dangerouslySetInnerHTML={{ __html: modalContent.review || "" }}
              />
              <button
                onClick={() => setModalContent(null)}
                className="mt-4 w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2 rounded-md"
              >
                Close
              </button>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirmMovie && (
        <DeleteConfirmDialog
          movie={deleteConfirmMovie}
          onDelete={async (id) => {
            await handleRemoveMovie(id);
            setDeleteConfirmMovie(null);
          }}
          onCancel={() => setDeleteConfirmMovie(null)}
        />
      )}
    </div>
  );
}

export default WatchedList;
