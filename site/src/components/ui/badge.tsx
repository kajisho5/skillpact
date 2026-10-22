import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
const badgeVariants = cva("inline-flex items-center rounded-sm border px-1.5 py-px font-mono text-[0.72rem] font-medium leading-5", {
  variants: { variant: { default: "border-transparent bg-primary text-primary-foreground", outline: "text-muted-foreground", ink: "border-[hsl(var(--ink)/0.35)] text-ink" } },
  defaultVariants: { variant: "outline" },
});
export function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
