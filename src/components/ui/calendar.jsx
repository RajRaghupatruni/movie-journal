// src/components/ui/calendar.jsx
import React from "react";
import { format } from "date-fns";

const Calendar = ({ date, onSelect }) => {
  return (
    <input
      type="date"
      value={format(date, "yyyy-MM-dd")}
      onChange={(e) => onSelect(new Date(e.target.value))}
      className="bg-zinc-800 text-white p-2 rounded w-full"
    />
  );
};

export { Calendar };
