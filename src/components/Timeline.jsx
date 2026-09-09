import React, { useEffect, useState } from "react";
import { sanitizeReviewHtml } from "../lib/reviewHtml";
import {
  collection,
  onSnapshot,
  query,
  orderBy,
  deleteDoc,
  doc,
} from "firebase/firestore";
import { db } from "../firebase";
import { format } from "date-fns";
import { Badge } from "../components/ui/badge";
import EditEventModal from "./EditEventModal"; // ✅ NEW
import { Button } from "../components/ui/button";

const Timeline = ({ tandemId = "test-tandem-id" }) => {
  const [events, setEvents] = useState([]);
  const [editingEvent, setEditingEvent] = useState(null);
  const [sortOrder, setSortOrder] = useState("desc");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [monthFilter, setMonthFilter] = useState("all");

  useEffect(() => {
    const q = query(
      collection(db, "tandems", tandemId, "events"),
      orderBy("date", "desc")
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const fetched = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }));
      setEvents(fetched);
    });

    return () => unsubscribe();
  }, [tandemId]);

  const handleDelete = async (eventId) => {
    const confirm = window.confirm("Are you sure you want to delete this event?");
    if (!confirm) return;
    await deleteDoc(doc(db, "tandems", tandemId, "events", eventId));
  };

  const filteredEvents = events
    .filter((event) => {
      if (categoryFilter !== "all" && event.category !== categoryFilter) return false;
      if (monthFilter !== "all") {
        const eventMonth = format(event.date.toDate(), "yyyy-MM");
        return eventMonth === monthFilter;
      }
      return true;
    })
    .sort((a, b) => {
      const dateA = a.date.toDate();
      const dateB = b.date.toDate();
      return sortOrder === "asc" ? dateA - dateB : dateB - dateA;
    });

  const uniqueMonths = [
    ...new Set(events.map((event) => format(event.date.toDate(), "yyyy-MM"))),
  ];

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <select
          className="bg-zinc-800 text-white p-2 rounded"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="all">All Categories</option>
          <option value="Movie">Movie</option>
          <option value="Place">Place</option>
          <option value="Trip">Trip</option>
          <option value="Activity">Activity</option>
        </select>

        <select
          className="bg-zinc-800 text-white p-2 rounded"
          value={monthFilter}
          onChange={(e) => setMonthFilter(e.target.value)}
        >
          <option value="all">All Months</option>
          {uniqueMonths.map((month) => (
            <option key={month} value={month}>
              {format(new Date(month), "MMMM yyyy")}
            </option>
          ))}
        </select>

        <select
          className="bg-zinc-800 text-white p-2 rounded"
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value)}
        >
          <option value="desc">Newest → Oldest</option>
          <option value="asc">Oldest → Newest</option>
        </select>
      </div>

      {filteredEvents.length === 0 ? (
        <p className="text-center text-zinc-400 mt-10">No events found.</p>
      ) : (
        filteredEvents.map((event) => (
          <div
            key={event.id}
            className="bg-zinc-800 border border-zinc-700 rounded-2xl p-5 shadow-md"
          >
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                {event.category === "Activity" && <span>🎮</span>}
                {event.category === "Movie" && <span>🎥</span>}
                {event.category === "Trip" && <span>🧳</span>}
                {event.category === "Place" && <span>📍</span>}
                {event.title}
              </h2>
              <Badge variant="purple" className="capitalize">
                {event.category}
              </Badge>
            </div>

            <p className="text-sm text-zinc-400 mb-1">
              🗓️ {format(event.date.toDate(), "MMMM d, yyyy")}
            </p>

            {event.rating && (
              <p className="text-sm text-yellow-400 mb-1">
                ⭐ Rating: {event.rating}/10
              </p>
            )}

            {event.review && (
              <div
                className="prose prose-sm text-zinc-200 max-w-none mb-2"
                dangerouslySetInnerHTML={{ __html: sanitizeReviewHtml(event.review) }}
              />
            )}

            {event.notes && (
              <p className="text-sm italic text-zinc-400 mb-2">📝 {event.notes}</p>
            )}

            {event.location?.name && (
              <p className="text-sm text-zinc-400 mb-2">📍 {event.location.name}</p>
            )}

            <div className="text-xs text-right text-zinc-500 italic">
              {event.source === "foursquare"
                ? "🕘 Foursquare"
                : event.source === "tmdb"
                ? "🎥 TMDb"
                : "✍️ Manual Entry"}
            </div>

            {/* ✏️ Edit & ❌ Delete Buttons */}
            <div className="mt-3 flex justify-end gap-3">
              <Button variant="ghost" size="sm" onClick={() => setEditingEvent(event)}>
                ✏️ Edit
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleDelete(event.id)}
              >
                ❌ Delete
              </Button>
            </div>
          </div>
        ))
      )}

      {/* 🔧 Edit Modal */}
      {editingEvent && (
        <EditEventModal
          event={editingEvent}
          tandemId={tandemId}
          onClose={() => setEditingEvent(null)}
        />
      )}
    </div>
  );
};

export default Timeline;
