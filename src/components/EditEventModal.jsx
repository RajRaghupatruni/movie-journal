// components/EditEventModal.jsx
import React, { useState } from "react";
import { Dialog, DialogContent, DialogTrigger } from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Calendar } from "../components/ui/calendar";
import { Textarea } from "../components/ui/textarea";
import { Timestamp, doc, updateDoc } from "firebase/firestore";
import { db } from "../firebase";

const EditEventModal = ({ event, tandemId }) => {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(event.title || "");
  const [date, setDate] = useState(event.date.toDate());
  const [participants, setParticipants] = useState(
    (event.participants || []).join(", ")
  );
  const [rating, setRating] = useState(event.rating || "");
  const [review, setReview] = useState(event.review || "");
  const [notes, setNotes] = useState(event.notes || "");

  const handleSave = async () => {
    const eventRef = doc(db, "tandems", tandemId, "events", event.id);

    await updateDoc(eventRef, {
      title,
      date: Timestamp.fromDate(date),
      participants: participants.split(",").map((p) => p.trim()),
      rating: rating ? parseInt(rating) : null,
      review,
      notes,
      updatedAt: Timestamp.now(),
    });

    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" className="text-sm text-zinc-400 hover:text-white">
          ✏️ Edit
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-zinc-900 text-white max-w-2xl">
        <div className="space-y-4">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title"
            className="w-full bg-zinc-800 p-2 rounded"
          />

          <Calendar date={date} onSelect={setDate} />

          <input
            type="text"
            value={participants}
            onChange={(e) => setParticipants(e.target.value)}
            placeholder="Participants (comma separated)"
            className="w-full bg-zinc-800 p-2 rounded"
          />

          <input
            type="number"
            value={rating}
            min="1"
            max="10"
            onChange={(e) => setRating(e.target.value)}
            placeholder="Rating"
            className="w-full bg-zinc-800 p-2 rounded"
          />

          <Textarea
            value={review}
            onChange={(e) => setReview(e.target.value)}
            placeholder="Review"
          />

          <Textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes"
          />

          <Button onClick={handleSave} className="w-full mt-4">
            Save Changes
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EditEventModal;
