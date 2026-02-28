/**
 * Reusable advanced filter toolbar: date range, status, category, user (director only), clear.
 * Use for Alerts, Audit, Purchases pages with consistent layout and RTL support.
 */
import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface FilterToolbarDateRange {
  from: string;
  to: string;
}
export interface FilterToolbarStatusOption {
  value: string;
  label: string;
}
export interface FilterToolbarUserOption {
  id: string;
  email: string;
  role?: string;
}

export interface FilterToolbarProps {
  className?: string;
  /** Search query (optional) */
  search?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  /** Date range (optional) */
  dateRange?: FilterToolbarDateRange;
  onDateRangeChange?: (from: string, to: string) => void;
  /** Status filter (optional) */
  statusOptions?: FilterToolbarStatusOption[];
  status?: string;
  onStatusChange?: (value: string) => void;
  statusPlaceholder?: string;
  /** Category filter (optional) */
  categoryOptions?: string[];
  category?: string;
  onCategoryChange?: (value: string) => void;
  categoryPlaceholder?: string;
  /** User filter — show only for director/admin (optional) */
  userOptions?: FilterToolbarUserOption[];
  userId?: string;
  onUserChange?: (value: string) => void;
  showUserFilter?: boolean;
  /** Clear all filters */
  onClear?: () => void;
  clearLabel?: string;
  /** Extra: result count, export buttons, etc. */
  children?: React.ReactNode;
}

export function FilterToolbar({
  className,
  search,
  onSearchChange,
  searchPlaceholder,
  dateRange,
  onDateRangeChange,
  statusOptions,
  status,
  onStatusChange,
  statusPlaceholder,
  categoryOptions,
  category,
  onCategoryChange,
  categoryPlaceholder,
  userOptions = [],
  userId,
  onUserChange,
  showUserFilter = false,
  onClear,
  clearLabel = "مسح الفلاتر",
  children,
}: FilterToolbarProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end gap-3 p-1",
        className
      )}
    >
      {onSearchChange && (
        <div className="space-y-1 min-w-[180px]">
          <Input
            className="rounded-xl"
            placeholder={searchPlaceholder ?? "بحث..."}
            value={search ?? ""}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
      )}

      {dateRange && onDateRangeChange && (
        <>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground block">من</span>
            <Input
              type="date"
              className="rounded-xl"
              value={dateRange.from}
              onChange={(e) => onDateRangeChange(e.target.value, dateRange.to)}
            />
          </div>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground block">إلى</span>
            <Input
              type="date"
              className="rounded-xl"
              value={dateRange.to}
              onChange={(e) => onDateRangeChange(dateRange.from, e.target.value)}
            />
          </div>
        </>
      )}

      {statusOptions && status !== undefined && onStatusChange && (
        <div className="space-y-1 w-40">
          <Select value={status} onValueChange={onStatusChange}>
            <SelectTrigger className="rounded-xl">
              <SelectValue placeholder={statusPlaceholder ?? "الحالة"} />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {categoryOptions && category !== undefined && onCategoryChange && (
        <div className="space-y-1 w-44">
          <Select value={category} onValueChange={onCategoryChange}>
            <SelectTrigger className="rounded-xl">
              <SelectValue placeholder={categoryPlaceholder ?? "التصنيف"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">الكل</SelectItem>
              {categoryOptions.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {showUserFilter && userOptions.length > 0 && userId !== undefined && onUserChange && (
        <div className="space-y-1 w-48">
          <Select value={userId} onValueChange={onUserChange}>
            <SelectTrigger className="rounded-xl">
              <SelectValue placeholder="المستخدم" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">الكل</SelectItem>
              {userOptions.map((u) => (
                <SelectItem key={u.id} value={u.id}>
                  {u.email} {u.role ? `(${u.role})` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {onClear && (
        <Button variant="outline" size="sm" className="rounded-xl" onClick={onClear}>
          {clearLabel}
        </Button>
      )}

      {children}
    </div>
  );
}
