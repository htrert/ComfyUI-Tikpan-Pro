import type { ReactNode } from "react";
import { cn } from "../lib";

export function GlassCard({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("liquid-glass rounded-2xl p-4", className)}>{children}</section>;
}
