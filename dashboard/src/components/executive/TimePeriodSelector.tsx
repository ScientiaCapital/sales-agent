import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "lucide-react";

export type TimePeriod = "7d" | "mtd" | "qtd";

interface TimePeriodSelectorProps {
  value: TimePeriod;
  onChange: (period: TimePeriod) => void;
}

export function TimePeriodSelector({ value, onChange }: TimePeriodSelectorProps) {
  const periods: { value: TimePeriod; label: string }[] = [
    { value: "7d", label: "7 Days" },
    { value: "mtd", label: "MTD" },
    { value: "qtd", label: "QTD" },
  ];

  return (
    <div className="flex items-center gap-2">
      <Calendar className="h-4 w-4 text-gray-400" />
      <div className="inline-flex rounded-lg border border-purple-500/30 bg-gradient-to-r from-slate-900/90 to-purple-900/20 p-1">
        {periods.map((period) => (
          <Button
            key={period.value}
            variant={value === period.value ? "default" : "ghost"}
            size="sm"
            onClick={() => onChange(period.value)}
            className={`
              px-4 py-1 text-sm font-medium transition-all duration-200
              ${
                value === period.value
                  ? "bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg shadow-purple-500/50"
                  : "text-gray-400 hover:text-white hover:bg-purple-500/10"
              }
            `}
          >
            {period.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
