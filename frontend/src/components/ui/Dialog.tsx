import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}

export function Dialog({ open, onClose, title, children, footer, width = "540px" }: DialogProps) {
  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="flex max-h-[85vh] w-full flex-col rounded-xl border border-app-border bg-app-surface p-6 shadow-2xl"
        style={{ maxWidth: width }}
      >
        <h2 className="mb-4 text-lg font-semibold text-app-text">{title}</h2>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        {footer && <div className="mt-5 flex justify-end gap-2 border-t border-app-border pt-4">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
