import React from "react";
import classNames from "classnames";

const Badge = ({ children, variant = "default", className = "" }) => {
  const baseStyles =
    "inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold";

  const variants = {
    default: "bg-zinc-700 text-white",
    purple: "bg-purple-700 text-white",
    blue: "bg-blue-700 text-white",
    green: "bg-green-700 text-white",
    yellow: "bg-yellow-600 text-black",
    red: "bg-red-700 text-white",
    outline: "border border-zinc-400 text-zinc-300",
  };

  return (
    <span className={classNames(baseStyles, variants[variant], className)}>
      {children}
    </span>
  );
};

export { Badge };

