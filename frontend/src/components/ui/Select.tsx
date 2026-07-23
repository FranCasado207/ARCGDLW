import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  className?: string;
}

/**
 * A fully CSS-styled dropdown, deliberately not backed by a native <select>.
 * WebKitGTK renders a native <select>'s open popup list via the system GTK
 * theme, completely ignoring page CSS - on hosts without a properly
 * configured dark GTK theme this shows up as unreadable white-on-white
 * text. Building our own popup avoids native rendering entirely.
 */
export function Select({ value, onChange, options, className = "" }: SelectProps) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<{ top: number; left: number; width: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const update = () => {
      const r = buttonRef.current?.getBoundingClientRect();
      if (r) setRect({ top: r.bottom + 4, left: r.left, width: r.width });
    };
    update();

    function onDocMouseDown(e: MouseEvent) {
      if (!buttonRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open]);

  const current = options.find((o) => o.value === value);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex w-full cursor-pointer items-center justify-between rounded-lg border border-app-border bg-app-bg px-3 py-1.5 text-left text-sm text-app-text outline-none focus:border-app-accent ${className}`}
      >
        <span className="truncate">{current?.label ?? value}</span>
        <span className="ml-2 shrink-0 text-app-muted">▾</span>
      </button>

      {open &&
        rect &&
        createPortal(
          <div
            className="fixed z-50 max-h-64 overflow-y-auto rounded-lg border border-app-border bg-app-surface py-1 shadow-2xl"
            style={{ top: rect.top, left: rect.left, width: rect.width }}
          >
            {options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={`block w-full px-3 py-1.5 text-left text-sm hover:bg-app-accent/15 ${
                  opt.value === value ? "font-medium text-app-accent" : "text-app-text"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}
