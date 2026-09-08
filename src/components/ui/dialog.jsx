// src/components/ui/dialog.jsx
import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;

export const DialogContent = React.forwardRef(({ children, className, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
    <DialogPrimitive.Content
      ref={ref}
      className={`fixed left-1/2 top-1/2 w-full max-w-lg translate-x-[-50%] translate-y-[-50%] rounded-xl bg-zinc-900 p-6 shadow-lg focus:outline-none ${className}`}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 text-zinc-400 hover:text-white">
        <X className="h-5 w-5" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));

DialogContent.displayName = "DialogContent";
