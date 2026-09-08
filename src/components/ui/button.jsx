// src/components/ui/button.jsx
import * as React from "react";

export const Button = React.forwardRef(({ className = "", ...props }, ref) => (
  <button
    ref={ref}
    className={`inline-flex items-center justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50 ${className}`}
    {...props}
  />
));

Button.displayName = "Button";
