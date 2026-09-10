// DEPRECATED MIGRATION REFERENCE: the active Keepsake Add Memory flow is in App.jsx.
import React, { useState } from "react";
import { Dialog, DialogContent, DialogTrigger } from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Calendar } from "../components/ui/calendar";
import { Textarea } from "../components/ui/textarea";
import { db } from "../firebase";
import { addDoc, Timestamp, collection } from "firebase/firestore";
import FoursquareSearch from "./FoursquareSearch";

const AddEventModal = ({ tandemId = "test-tandem" }) => {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("Movie");
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState(null);
  const [date, setDate] = useState(new Date());
  const [participants, setParticipants] = useState("");
  const [rating, setRating] = useState("");
  const [review, setReview] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = async () => {
    if (!title || !category || !date) {
      alert("Please fill in title, category and date.");
      return;
    }

    const eventData = {
      title,
      category,
      location: location || null,
      date: Timestamp.fromDate(date),
      participants: participants
        ? participants.split(",").map((p) => p.trim())
        : [],
      rating: rating ? parseInt(rating) : null,
      review,
      notes,
      source: location
        ? "foursquare"
        : category === "Movie"
        ? "tmdb"
        : "manual",
      createdAt: Timestamp.now(),
    };

    try {
      await addDoc(collection(db, "tandems", tandemId, "events"), eventData);
      alert("Event saved!");

      // Reset form
      setTitle("");
      setLocation(null);
      setCategory("Movie");
      setDate(new Date());
      setParticipants("");
      setRating("");
      setReview("");
      setNotes("");
      setOpen(false);
    } catch (err) {
      console.error("Error adding event:", err);
      alert("Failed to save event. Please try again.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Add Event</Button>
      </DialogTrigger>
      <DialogContent className="bg-zinc-900 text-white max-w-2xl">
        <div className="space-y-4">
          {/* Category Buttons */}
          <div className="flex gap-2">
            {["Movie", "Place", "Trip", "Activity"].map((type) => (
              <Button
                key={type}
                variant={category === type ? "default" : "ghost"}
                onClick={() => setCategory(type)}
              >
                {type}
              </Button>
            ))}
          </div>

          {/* Title or Place Search */}
          {category === "Place" ? (
            <FoursquareSearch onSelect={setLocation} />
          ) : (
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter title"
              className="w-full bg-zinc-800 p-2 rounded"
            />
          )}

          {/* Date Picker */}
          <Calendar date={date} onSelect={setDate} />

          {/* Participants */}
          <input
            type="text"
            value={participants}
            onChange={(e) => setParticipants(e.target.value)}
            placeholder="Participants (comma separated)"
            className="w-full bg-zinc-800 p-2 rounded"
          />

          {/* Rating */}
          <input
            type="number"
            min="1"
            max="10"
            value={rating}
            onChange={(e) => setRating(e.target.value)}
            placeholder="Rating (1–10)"
            className="w-full bg-zinc-800 p-2 rounded"
          />

          {/* Review */}
          <Textarea
            value={review}
            onChange={(e) => setReview(e.target.value)}
            placeholder="Write a short review..."
          />

          {/* Notes */}
          <Textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes"
          />

          {/* Submit */}
          <Button onClick={handleSubmit} className="w-full mt-4">
            Save Event
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AddEventModal;
