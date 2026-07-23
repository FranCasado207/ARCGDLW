import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

const CONTROL_CLASSES =
  "w-full rounded-lg border border-app-border bg-app-bg px-3 py-1.5 text-sm text-app-text outline-none focus:border-app-accent disabled:opacity-60";

export function FieldLabel({ children }: { children: ReactNode }) {
  return <label className="mb-1.5 block text-sm font-medium text-app-text">{children}</label>;
}

export function TextField(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL_CLASSES} ${props.className ?? ""}`} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${CONTROL_CLASSES} resize-none ${props.className ?? ""}`} />;
}

interface CheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  title?: string;
}

export function Checkbox({ checked, onChange, label, disabled, title }: CheckboxProps) {
  return (
    <label
      className={`flex cursor-pointer items-center gap-2 text-sm text-app-text ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
      title={title}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-app-accent"
      />
      {label}
    </label>
  );
}
