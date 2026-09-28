"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * UptimeGraph component renders the 30-day timeline uptime bar chart.
 */
export function UptimeGraph({
  data = [],
  startLabel = "30 days ago",
  endLabel = "Today",
  centerLabel,
  className,
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const getStatusColor = (status, value) => {
    if (status === "operational" || value === 1) {
      return "bg-[#00D26A] hover:bg-[#00FF80]";
    }
    if (status === "down" || value === 0) {
      return "bg-rose-500 hover:bg-rose-400";
    }
    if (status === "degraded") {
      return "bg-amber-500 hover:bg-amber-400";
    }
    // No data for unmonitored historical period
    return "bg-zinc-800/80 hover:bg-zinc-700";
  };

  return (
    <div className={cn("w-full flex flex-col gap-2 relative", className)}>
      {/* Bars row - slim vertical rounded pills with tight gap */}
      <div className="flex items-center justify-between gap-[2px] sm:gap-[2.5px] h-7 sm:h-8 w-full overflow-hidden py-0.5">
        {data.map((bar, idx) => {
          const isHovered = hoveredIndex === idx;
          const isOperational = bar.status === "operational" || bar.value === 1;
          const isDown = bar.status === "down" || bar.value === 0;

          return (
            <div
              key={idx}
              onMouseEnter={() => setHoveredIndex(idx)}
              onMouseLeave={() => setHoveredIndex(null)}
              className={cn(
                "flex-1 min-w-[2px] max-w-[5px] h-full rounded-full transition-all duration-150 cursor-pointer",
                getStatusColor(bar.status, bar.value),
                isHovered
                  ? "scale-y-115 opacity-100 ring-2 ring-white/60 z-10"
                  : isOperational || isDown
                  ? "opacity-95"
                  : "opacity-60"
              )}
              title={bar.timestamp || `Period #${idx + 1}`}
            />
          );
        })}
      </div>

      {/* Footer labels */}
      <div className="flex items-center justify-between text-[11px] sm:text-xs text-muted-foreground font-medium">
        <span>{startLabel}</span>
        {centerLabel && (
          <span className="hidden sm:inline-block text-[11px] text-muted-foreground/80">
            {centerLabel}
          </span>
        )}
        <span>{endLabel}</span>
      </div>
    </div>
  );
}
