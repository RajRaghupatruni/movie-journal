import EmojiPicker from "emoji-picker-react";
import { sanitizeReviewHtml, pasteReviewText, preventReviewDrop } from "../lib/reviewHtml";
import * as Dialog from "@radix-ui/react-dialog";
import { useState, useRef } from "react";
import {
  Star, X, Smile, Bold, Italic, Underline,
  Strikethrough, List,
} from "lucide-react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { Timestamp } from "firebase/firestore";

function AddMovieModal({ movie, onSave, triggerClass, children }) {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState("");
  const [review, setReview] = useState("");
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [dateWatched, setDateWatched] = useState(new Date());
  const editorRef = useRef(null);

  const handleSubmit = () => {
    if (!rating || !dateWatched) return;

    const watchedMovie = {
      id: movie.id,
      title: movie.title,
      poster: movie.poster_path,
      dateWatched: Timestamp.fromDate(dateWatched),
      rating,
      review: sanitizeReviewHtml(review),
    };

    onSave(watchedMovie);
    setRating("");
    setReview("");
    setDateWatched(new Date());
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
        {triggerClass ? (
          <button className={triggerClass}>
            {children || "Add to Watched List"}
          </button>
        ) : (
          <button className="w-full text-left">
            <div className="flex gap-4 bg-zinc-900/70 text-white backdrop-blur-lg border border-zinc-700 rounded-xl shadow-md p-3 hover:bg-zinc-800/80 transition">
              <img
                src={
                  movie.poster_path
                    ? `https://image.tmdb.org/t/p/w200${movie.poster_path}`
                    : "https://via.placeholder.com/100x150?text=No+Image"
                }
                alt={movie.title}
                className="w-20 h-auto rounded-md object-cover"
              />
              <div>
                <div className="font-semibold">{movie.title}</div>
                <div className="text-sm text-gray-400">
                  {movie.release_date?.slice(0, 4)}
                </div>
              </div>
            </div>
          </button>
        )}
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-zinc-900/90 text-zinc-100 backdrop-blur-xl border border-zinc-700 p-6 rounded-2xl shadow-xl w-full max-w-md space-y-4">
          <div className="flex justify-between items-center">
            <Dialog.Title className="text-lg font-bold">{movie.title}</Dialog.Title>
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
              className="w-full bg-zinc-800 border border-zinc-600 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder-zinc-400"
              dateFormat="MMMM d, yyyy"
              maxDate={new Date()}
              showYearDropdown
              showMonthDropdown
              calendarClassName="bg-zinc-900 text-white border border-zinc-700"
              dayClassName={() => "text-white"}
              popperClassName="dark-theme-datepicker"
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
              <button onClick={() => applyFormat("strikeThrough")} title="Strike Through">
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
              dir="ltr"
              ref={editorRef}
              onInput={() => setReview(editorRef.current.innerHTML)}
              className="w-full min-h-[100px] max-h-[200px] overflow-y-auto bg-zinc-800 border border-zinc-600 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none break-words"
              suppressContentEditableWarning
            ></div>

            {showEmojiPicker && (
              <div className="mt-2 z-50 bg-zinc-800 rounded-md shadow-lg p-2">
                <EmojiPicker
                  onEmojiClick={(emojiData) => insertEmoji(emojiData.emoji)}
                  emojiStyle="native"
                  theme="dark"
                  lazyLoadEmojis
                />
              </div>
            )}
          </div>

          {/* Save Button */}
          <button
            onClick={handleSubmit}
            className="w-full bg-indigo-600 text-white py-2 rounded-md hover:bg-indigo-700 flex items-center justify-center gap-2"
          >
            <Star className="w-4 h-4" />
            Save to Watched List
          </button>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default AddMovieModal;
