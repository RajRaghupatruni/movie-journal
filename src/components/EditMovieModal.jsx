import * as Dialog from "@radix-ui/react-dialog";
import { sanitizeReviewHtml, pasteReviewText, preventReviewDrop } from "../lib/reviewHtml";
import { useState, useRef, useEffect } from "react";
import {
  Pencil,
  X,
  Smile,
  Bold,
  Italic,
  Underline,
  Strikethrough,
  List,
} from "lucide-react";
import { doc, updateDoc, Timestamp } from "firebase/firestore";
import { db } from "../firebase";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import EmojiPicker from "emoji-picker-react";
import { addDoc, collection } from "firebase/firestore";

function EditMovieModal({ movie, triggerClass, onComplete, children }) {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(movie.rating || "");
  const [review, setReview] = useState(movie.review || "");
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [dateWatched, setDateWatched] = useState(() => {
    try {
      return movie.dateWatched?.toDate?.() || movie.dateWatched || new Date();
    } catch {
      return new Date();
    }
  });

  const editorRef = useRef(null);

  useEffect(() => {
    if (open) {
      setRating(movie.rating || "");
      setReview(movie.review || "");
      setDateWatched(() => {
        try {
          return movie.dateWatched?.toDate?.() || movie.dateWatched || new Date();
        } catch {
          return new Date();
        }
      });

      requestAnimationFrame(() => {
        if (editorRef.current) {
          editorRef.current.innerHTML = sanitizeReviewHtml(movie.review);
        }
      });
    }
  }, [open]);

  const handleUpdate = async () => {
    if (!rating || !dateWatched) return;

    const newData = {
      tmdbId: movie.tmdbId || movie.id,
      title: movie.title,
      poster: movie.poster,
      rating,
      review: sanitizeReviewHtml(review),
      dateWatched: Timestamp.fromDate(dateWatched),
    };

    if (movie.id && movie.fromWatchlist) {
      // If coming from watchlist, add to watchedMovies
      await addDoc(collection(db, "watchedMovies"), newData);

      // Remove from watchlist (caller handles this via onComplete)
      if (onComplete) await onComplete(movie.id);

    } else {
      // Editing existing watched movie
      await updateDoc(doc(db, "watchedMovies", movie.id), newData);
    }

    setOpen(false);
  };

  const applyFormat = (command) => {
    document.execCommand(command, false, null);
    setReview(editorRef.current.innerHTML);
  };

  const insertEmoji = (emoji) => {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(document.createTextNode(emoji));
    setReview(editorRef.current.innerHTML);
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button className={triggerClass}>
          {children || "Edit"}
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40" />
        <Dialog.Content className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-zinc-900 text-white p-6 rounded-xl w-full max-w-md border border-zinc-700 shadow-lg space-y-4">
          <div className="flex justify-between items-center">
            <Dialog.Title className="text-lg font-bold">
              {movie.fromWatchlist ? `Mark as Watched: ${movie.title}` : `Edit ${movie.title}`}
            </Dialog.Title>
            <Dialog.Close>
              <X className="w-5 h-5 text-zinc-500 hover:text-white" />
            </Dialog.Close>
          </div>

          {/* Date Picker */}
          <div>
            <label className="block text-sm font-medium mb-1">Date Watched</label>
            <DatePicker
              selected={dateWatched}
              onChange={(date) => setDateWatched(date)}
              className="w-full bg-zinc-800 border border-zinc-600 rounded-md px-3 py-2 text-sm text-zinc-100"
              dateFormat="MMMM d, yyyy"
              maxDate={new Date()}
              showYearDropdown
              showMonthDropdown
              calendarClassName="!bg-zinc-800 !text-white !border-zinc-600"
              dayClassName={() => "!text-white hover:!bg-zinc-700"}
            />
          </div>

          {/* Rating Input */}
          <div>
            <label className="block text-sm font-medium mb-2">Your Rating</label>
            <div className="grid grid-cols-5 gap-2">
              {[...Array(10)].map((_, i) => {
                const val = (i + 1).toString();
                return (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setRating(val)}
                    className={`px-3 py-2 text-sm font-medium rounded-md border transition ${
                      rating === val
                        ? "bg-indigo-600 text-white border-indigo-600"
                        : "bg-zinc-800 text-zinc-100 border-zinc-600 hover:bg-zinc-700"
                    }`}
                  >
                    {val}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Review Editor */}
          <div>
            <label className="block text-sm font-medium mb-1">Your Review</label>
            <div className="flex items-center gap-2 mb-2">
              <button onClick={() => applyFormat("bold")} title="Bold">
                <Bold className="w-4 h-4 text-zinc-300 hover:text-white" />
              </button>
              <button onClick={() => applyFormat("italic")} title="Italic">
                <Italic className="w-4 h-4 text-zinc-300 hover:text-white" />
              </button>
              <button onClick={() => applyFormat("underline")} title="Underline">
                <Underline className="w-4 h-4 text-zinc-300 hover:text-white" />
              </button>
              <button onClick={() => applyFormat("strikeThrough")} title="Strikethrough">
                <Strikethrough className="w-4 h-4 text-zinc-300 hover:text-white" />
              </button>
              <button onClick={() => applyFormat("insertUnorderedList")} title="Bullet List">
                <List className="w-4 h-4 text-zinc-300 hover:text-white" />
              </button>
              <button onClick={() => setShowEmojiPicker((prev) => !prev)} title="Emoji">
                <Smile className="w-4 h-4 text-zinc-300 hover:text-white" />
              </button>
            </div>

            <div
              contentEditable
              onPaste={pasteReviewText}
              onDrop={preventReviewDrop}
              ref={editorRef}
              onInput={() => setReview(editorRef.current.innerHTML)}
              className="w-full min-h-[90px] max-h-[200px] overflow-y-auto bg-zinc-800 border border-zinc-600 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none"
              suppressContentEditableWarning
            ></div>

            {showEmojiPicker && (
              <div className="mt-2 max-h-64 overflow-y-auto rounded-md shadow border border-zinc-700 bg-zinc-800">
                <EmojiPicker
                  onEmojiClick={(emojiData) => insertEmoji(emojiData.emoji)}
                  emojiStyle="native"
                  lazyLoadEmojis
                  theme="dark"
                  width="100%"
                  height={300}
                  searchDisabled
                />
              </div>
            )}
          </div>

          {/* Save Button */}
          <button
            onClick={handleUpdate}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2 rounded-md"
          >
            {movie.fromWatchlist ? "Mark as Watched" : "Save Changes"}
          </button>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default EditMovieModal;
