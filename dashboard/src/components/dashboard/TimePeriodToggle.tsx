import { Calendar, CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";

interface TimePeriodToggleProps {
  value: "7d" | "mtd";
  onChange: (period: "7d" | "mtd") => void;
}

export function TimePeriodToggle({ value, onChange }: TimePeriodToggleProps) {
  return (
    <div className="flex items-center gap-2 bg-muted rounded-lg p-1">
      <Button
        variant={value === "7d" ? "default" : "ghost"}
        size="sm"
        onClick={() => onChange("7d")}
        className={value === "7d" ? "bg-[var(--turkish-blue)]" : ""}
      >
        <CalendarDays className="h-4 w-4 mr-1" />
        7 Days
      </Button>
      <Button
        variant={value === "mtd" ? "default" : "ghost"}
        size="sm"
        onClick={() => onChange("mtd")}
        className={value === "mtd" ? "bg-[var(--turkish-blue)]" : ""}
      >
        <Calendar className="h-4 w-4 mr-1" />
        MTD
      </Button>
    </div>
  );
}
