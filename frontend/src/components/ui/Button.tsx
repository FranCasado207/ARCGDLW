import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-app-accent text-white hover:opacity-90 disabled:opacity-50",
  secondary:
    "bg-transparent border border-app-border text-app-text hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-50",
  danger: "bg-transparent text-red-500 hover:bg-red-500/10 disabled:opacity-50",
  ghost: "bg-transparent text-app-muted hover:text-app-text hover:bg-black/5 dark:hover:bg-white/5",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = "secondary", className = "", ...rest }: ButtonProps) {
  return (
    <button
      className={`cursor-pointer rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  );
}
