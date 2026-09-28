"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UptimeGraph } from "@/components/ui/uptime-graph";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle } from "lucide-react";

export function UptimeItem({
  title,
  description,
  uptimePercentage = "100.00%",
  latency,
  currentLatency = "~99ms",
  avgLatency,
  isOperational = true,
  status = "Operational",
  historyData = [],
  startLabel = "30 days ago",
  endLabel = "Today",
  className,
}) {
  const displayCurrentLatency = currentLatency || latency || null;

  return (
    <Card className={cn("transition-all hover:border-muted-foreground/30 bg-card/60 backdrop-blur-sm", className)}>
      <CardContent className="p-5 flex flex-col gap-4">
        {/* Title row with percentage stat & latency stats on the right */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            {isOperational ? (
              <CheckCircle2 className="h-4 w-4 text-[#00D26A] shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 text-rose-500 shrink-0" />
            )}
            <div>
              <h3 className="text-base font-semibold tracking-tight text-foreground">{title}</h3>
              {description && (
                <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 self-end sm:self-auto">
            {/* Current latency & 30-day average latency */}
            <div className="flex items-center gap-1.5 text-xs font-mono">
              {displayCurrentLatency && (
                <span className="text-muted-foreground" title="Current Latency (TTFT)">
                  {displayCurrentLatency}
                </span>
              )}
              {avgLatency && (
                <span
                  className="text-[11px] text-muted-foreground/70 hidden sm:inline-block font-mono"
                  title="30-day Average Latency (TTFT)"
                >
                  (avg {avgLatency})
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <span className={cn(
                "text-sm font-semibold font-mono",
                isOperational ? "text-[#00D26A]" : "text-rose-400"
              )}>
                {uptimePercentage}
              </span>
              <Badge
                variant={isOperational ? "success" : "destructive"}
                className="text-[11px] px-2.5 py-0.5 font-medium"
              >
                {isOperational ? "Operational" : "Down"}
              </Badge>
            </div>
          </div>
        </div>

        {/* Uptime Bar Graph */}
        <UptimeGraph
          data={historyData}
          startLabel={startLabel}
          endLabel={endLabel}
        />
      </CardContent>
    </Card>
  );
}
