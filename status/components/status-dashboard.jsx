"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { UptimeItem } from "@/components/ui/uptime-item";
import {
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Cpu,
  Boxes,
} from "lucide-react";

export function StatusDashboard({ initialData }) {
  const [data, setData] = useState(
    initialData || {
      publicai_router: [],
      currentai_router: [],
      supply_model: [],
      supply_supplier: [],
    }
  );
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    if (initialData?.fetchedAt) {
      setLastUpdated(new Date(initialData.fetchedAt));
    } else {
      setLastUpdated(new Date());
    }
  }, [initialData]);

  const fetchMetrics = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      // If manual refresh, pass refresh=true to prompt fresh data check
      const url = isManual ? "/api/metrics?refresh=true" : "/api/metrics";
      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        setData({
          publicai_router: json.publicai_router || [],
          currentai_router: json.currentai_router || [],
          supply_model: json.supply_model || [],
          supply_supplier: json.supply_supplier || [],
        });
        setLastUpdated(json.fetchedAt ? new Date(json.fetchedAt) : new Date());
      }
    } catch (err) {
      console.error("Failed to fetch live Prometheus metrics:", err);
    } finally {
      setLoading(false);
      if (isManual) setRefreshing(false);
    }
  };

  useEffect(() => {
    // Client-side background poll every 60s to sync with server cache
    const interval = setInterval(() => {
      fetchMetrics(false);
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Compute global operational status across router and supply checks
  const allCurrentItems = [
    ...(data.publicai_router || []),
    ...(data.currentai_router || []),
    ...(data.supply_model || []),
  ];
  const hasOutages = allCurrentItems.some((item) => !item.isOperational);
  const operationalPercentage =
    allCurrentItems.length > 0
      ? (
          (allCurrentItems.filter((i) => i.isOperational).length /
            allCurrentItems.length) *
          100
        ).toFixed(1)
      : "100.0";

  // Standard flat list renderer for Router tabs
  const renderUptimeList = (items, emptyMessage = "No metrics available") => {
    if (loading) {
      return (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm">Fetching metrics...</p>
        </div>
      );
    }

    if (!items || items.length === 0) {
      return (
        <Card className="border-dashed bg-card/40">
          <CardContent className="p-8 text-center text-muted-foreground text-sm">
            {emptyMessage}
          </CardContent>
        </Card>
      );
    }

    return (
      <div className="space-y-3">
        {items.map((item) => (
          <UptimeItem
            key={item.rawTarget || item.title}
            title={item.title}
            description={item.description}
            uptimePercentage={item.uptimePercentage}
            currentLatency={item.currentLatency}
            avgLatency={item.avgLatency}
            status={item.status}
            isOperational={item.isOperational}
            historyData={item.historyData}
            startLabel={item.startLabel || "30 days ago"}
            endLabel={item.endLabel || "Today"}
          />
        ))}
      </div>
    );
  };

  // Grouped by Model Name for supply(model) tab
  const renderGroupedByModel = (items) => {
    if (loading) {
      return (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm">Fetching metrics...</p>
        </div>
      );
    }

    if (!items || items.length === 0) {
      return (
        <Card className="border-dashed bg-card/40">
          <CardContent className="p-8 text-center text-muted-foreground text-sm">
            No supply(model) metrics found in Prometheus.
          </CardContent>
        </Card>
      );
    }

    // Group items by modelName
    const grouped = items.reduce((acc, item) => {
      const model = item.modelName || "Other Models";
      if (!acc[model]) acc[model] = [];
      acc[model].push(item);
      return acc;
    }, {});

    const sortedModelNames = Object.keys(grouped).sort((a, b) => a.localeCompare(b));

    return (
      <div className="space-y-8">
        {sortedModelNames.map((modelName) => {
          const supplierItems = grouped[modelName];
          return (
            <div key={modelName} className="space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-border">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-emerald-400" />
                  <h2 className="text-base font-semibold tracking-tight text-foreground">
                    {modelName}
                  </h2>
                </div>
                <Badge variant="outline" className="text-xs text-muted-foreground font-mono">
                  {supplierItems.length} {supplierItems.length === 1 ? "supplier" : "suppliers"}
                </Badge>
              </div>

              <div className="space-y-3">
                {supplierItems.map((item) => (
                  <UptimeItem
                    key={item.rawTarget}
                    title={item.supplierName}
                    uptimePercentage={item.uptimePercentage}
                    currentLatency={item.currentLatency}
                    avgLatency={item.avgLatency}
                    status={item.status}
                    isOperational={item.isOperational}
                    historyData={item.historyData}
                    startLabel={item.startLabel || "30 days ago"}
                    endLabel={item.endLabel || "Today"}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // Grouped by Supplier Name for supply(supplier) tab
  const renderGroupedBySupplier = (items) => {
    if (loading) {
      return (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm">Fetching metrics...</p>
        </div>
      );
    }

    if (!items || items.length === 0) {
      return (
        <Card className="border-dashed bg-card/40">
          <CardContent className="p-8 text-center text-muted-foreground text-sm">
            No supply(supplier) metrics found in Prometheus.
          </CardContent>
        </Card>
      );
    }

    // Group items by supplierName
    const grouped = items.reduce((acc, item) => {
      const supplier = item.supplierName || "Other Suppliers";
      if (!acc[supplier]) acc[supplier] = [];
      acc[supplier].push(item);
      return acc;
    }, {});

    const sortedSupplierNames = Object.keys(grouped).sort((a, b) => a.localeCompare(b));

    return (
      <div className="space-y-8">
        {sortedSupplierNames.map((supplierName) => {
          const modelItems = grouped[supplierName];
          return (
            <div key={supplierName} className="space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-border">
                <div className="flex items-center gap-2">
                  <Boxes className="h-4 w-4 text-emerald-400" />
                  <h2 className="text-base font-semibold tracking-tight text-foreground uppercase tracking-wide">
                    {supplierName}
                  </h2>
                </div>
                <Badge variant="outline" className="text-xs text-muted-foreground font-mono">
                  {modelItems.length} {modelItems.length === 1 ? "model" : "models"}
                </Badge>
              </div>

              <div className="space-y-3">
                {modelItems.map((item) => (
                  <UptimeItem
                    key={item.rawTarget}
                    title={item.modelName}
                    uptimePercentage={item.uptimePercentage}
                    currentLatency={item.currentLatency}
                    avgLatency={item.avgLatency}
                    status={item.status}
                    isOperational={item.isOperational}
                    historyData={item.historyData}
                    startLabel={item.startLabel || "30 days ago"}
                    endLabel={item.endLabel || "Today"}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="min-h-screen flex flex-col justify-between bg-background text-foreground">
      <main className="max-w-4xl w-full mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-8 border-b border-border pb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Inference API Status</h1>
            <p className="text-muted-foreground mt-1">30 day uptime and realtime service availability</p>
          </div>
          <div className="flex items-center gap-3">
            {!hasOutages ? (
              <Badge variant="success" className="w-fit text-sm py-1.5 px-3 flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                All Systems Operational
              </Badge>
            ) : (
              <Badge variant="destructive" className="w-fit text-sm py-1.5 px-3 flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4" />
                {operationalPercentage}% Operational
              </Badge>
            )}
          </div>
        </header>

        {/* Status Category Tabs */}
        <Tabs defaultValue="publicai-router" className="w-full">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <TabsList className="grid w-full sm:w-auto grid-cols-2 md:grid-cols-4 h-auto p-1 gap-1">
              <TabsTrigger value="publicai-router" className="py-2 text-xs sm:text-sm font-medium">
                publicai router
              </TabsTrigger>
              <TabsTrigger value="current-ai-router" className="py-2 text-xs sm:text-sm font-medium">
                current ai router
              </TabsTrigger>
              <TabsTrigger value="supply-model" className="py-2 text-xs sm:text-sm font-medium">
                supply(model)
              </TabsTrigger>
              <TabsTrigger value="supply-supplier" className="py-2 text-xs sm:text-sm font-medium">
                supply(supplier)
              </TabsTrigger>
            </TabsList>

            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchMetrics(true)}
              disabled={refreshing}
              className="gap-2 shrink-0 self-end sm:self-auto text-xs"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
              {refreshing ? "Updating..." : "Refresh"}
            </Button>
          </div>

          <TabsContent value="publicai-router">
            {renderUptimeList(
              data.publicai_router,
              "No publicai_router_model_test_success metrics found in Prometheus."
            )}
          </TabsContent>

          <TabsContent value="current-ai-router">
            {renderUptimeList(
              data.currentai_router,
              "No currentai_router_model_test_success metrics found in Prometheus."
            )}
          </TabsContent>

          <TabsContent value="supply-model">
            {renderGroupedByModel(data.supply_model)}
          </TabsContent>

          <TabsContent value="supply-supplier">
            {renderGroupedBySupplier(data.supply_supplier)}
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
