// src/components/ui/textarea.jsx
import * as React from "react";

export const Textarea = React.forwardRef(({ className = "", ...props }, ref) => (
  <textarea
    ref={ref}
    className={`w-full rounded-md border border-zinc-700 bg-zinc-800 p-2 text-sm text-white placeholder-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 ${className}`}
    {...props}
  />
));

Textarea.displayName = "Textarea";
