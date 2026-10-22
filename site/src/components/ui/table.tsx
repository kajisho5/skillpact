import * as React from "react";
import { cn } from "@/lib/utils";
export const Table = React.forwardRef<HTMLTableElement, React.HTMLAttributes<HTMLTableElement>>(({ className, ...p }, ref) => (
  <div className="tbl-wrap"><table ref={ref} className={cn("w-full caption-bottom text-sm", className)} {...p} /></div>));
Table.displayName = "Table";
export const TableHeader = (p: React.HTMLAttributes<HTMLTableSectionElement>) => <thead {...p} className={cn("[&_tr]:border-b", p.className)} />;
export const TableBody = (p: React.HTMLAttributes<HTMLTableSectionElement>) => <tbody {...p} className={cn("[&_tr:last-child]:border-0", p.className)} />;
export const TableRow = (p: React.HTMLAttributes<HTMLTableRowElement>) => <tr {...p} className={cn("border-b align-top", p.className)} />;
export const TableHead = (p: React.ThHTMLAttributes<HTMLTableCellElement>) => <th scope="col" {...p} className={cn("h-9 px-3 text-left align-middle text-xs font-medium uppercase tracking-wide text-muted-foreground first:pl-0", p.className)} />;
export const TableCell = (p: React.TdHTMLAttributes<HTMLTableCellElement>) => <td {...p} className={cn("px-3 py-2.5 first:pl-0", p.className)} />;
