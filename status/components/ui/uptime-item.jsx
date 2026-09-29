"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UptimeGraph } from "@/components/ui/uptime-graph";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

export function UptimeItem({
  title,
  description,
  uptimePercentage = "100.00%",
  latency,
  currentLatency = "~99ms",
  avgLatency,
  isOperational = true,
  status,
  historyData = [],
  startLabel = "30 days ago",
  endLabel = "Today",
  className,
}) {
  const displayCurrentLatency = currentLatency || latency || null;

  const currentStatus = status || (isOperational ? "Operational" : "Down");
  const isDown = currentStatus.toLowerCase() === "down";
  const isDegraded = currentStatus.toLowerCase() === "degraded";
  const isOp = !isDown && !isDegraded;

  return (
    <Card className={cn("transition-all hover:border-muted-foreground/30 bg-card/60 backdrop-blur-sm", className)}>
      <CardContent className="p-5 flex flex-col gap-4">
        {/* Title row with percentage stat & latency stats on the right */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            {isOp ? (
              <CheckCircle2 className="h-4 w-4 text-[#00D26A] shrink-0" />
            ) : isDegraded ? (
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
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
                isOp ? "text-[#00D26A]" : isDegraded ? "text-amber-400" : "text-rose-400"
              )}>
                {uptimePercentage}
              </span>
              <Badge
                variant={isOp ? "success" : isDegraded ? "warning" : "destructive"}
                className="text-[11px] px-2.5 py-0.5 font-medium"
              >
                {currentStatus}
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
