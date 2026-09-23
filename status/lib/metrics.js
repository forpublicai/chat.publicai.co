import fs from "fs";
import path from "path";

const PROMETHEUS_URL = process.env.PROMETHEUS_URL || "http://localhost:9090";
const TOTAL_30_DAYS_SLOTS = 30 * 24 * 12; // 8,640 5-minute slots in 30 days
export const METRICS_REVALIDATE_SECONDS = 300; // 5 minutes

// In-memory cache fallback to deduplicate in-flight and server-side queries
let memoryCache = {
  timestamp: 0,
  data: null,
  promise: null,
};

function getIgnoredModels() {
  const possiblePaths = [
    process.env.IGNORED_MODELS_FILE,
    path.join(process.cwd(), "ignored-models.txt"),
    path.join(process.cwd(), "status", "ignored-models.txt"),
  ].filter(Boolean);

  for (const filePath of possiblePaths) {
    try {
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, "utf-8");
        return content
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line && !line.startsWith("#"))
          .map((name) => name.toLowerCase());
      }
    } catch (e) {
      console.warn(`Could not read ignore file at ${filePath}:`, e);
    }
  }
  return [];
}

function isModelIgnored(item, ignoredList) {
  if (!ignoredList || ignoredList.length === 0) return false;

  const rawTargetLower = (item.rawTarget || "").toLowerCase();
  const modelNameLower = (item.modelName || "").toLowerCase();
  const titleLower = (item.title || "").toLowerCase();

  for (const ignored of ignoredList) {
    if (
      rawTargetLower === ignored ||
      modelNameLower === ignored ||
      titleLower === ignored ||
      rawTargetLower.startsWith(ignored + ":") ||
      titleLower.startsWith(ignored + ":")
    ) {
      return true;
    }
  }
  return false;
}

function filterIgnoredItems(items) {
  const ignoredList = getIgnoredModels();
  if (ignoredList.length === 0) return items;
  return items.filter((item) => !isModelIgnored(item, ignoredList));
}

async function fetchPrometheusInstant(query) {
  try {
    const url = `${PROMETHEUS_URL}/api/v1/query?query=${encodeURIComponent(query)}`;
    const res = await fetch(url, {
      next: { revalidate: METRICS_REVALIDATE_SECONDS, tags: ["prometheus-metrics"] },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.data?.result || [];
  } catch (err) {
    console.error(`Error querying Prometheus instant (${query}):`, err);
    return [];
  }
}

async function fetchPrometheusRange(query, start, end, step = 300) {
  try {
    const url = `${PROMETHEUS_URL}/api/v1/query_range?query=${encodeURIComponent(
      query
    )}&start=${start}&end=${end}&step=${step}`;
    const res = await fetch(url, {
      next: { revalidate: METRICS_REVALIDATE_SECONDS, tags: ["prometheus-metrics"] },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.data?.result || [];
  } catch (err) {
    console.error(`Error querying Prometheus range (${query}):`, err);
    return [];
  }
}

function parseModelSupplier(str) {
  if (!str) return { modelName: "Unknown", supplierName: "Unknown" };
  const lastColonIndex = str.lastIndexOf(":");
  if (lastColonIndex === -1) {
    return { modelName: str, supplierName: "default" };
  }
  return {
    modelName: str.substring(0, lastColonIndex),
    supplierName: str.substring(lastColonIndex + 1),
  };
}

function processMetricData(successInstant, ttftInstant, successRange, ttftRange) {
  // Map instant TTFT values by metric target string
  const instantTtftMap = new Map();
  for (const item of ttftInstant || []) {
    const rawTarget = item.metric?.model;
    const val = parseFloat(item.value?.[1]);
    if (rawTarget && !isNaN(val) && val > 0) {
      instantTtftMap.set(rawTarget, Math.round(val * 1000));
    }
  }

  // Map 30-day Range TTFT values and compute 30-day average
  const avgTtftMap = new Map();
  const latestRangeTtftMap = new Map();
  for (const item of ttftRange || []) {
    const rawTarget = item.metric?.model;
    if (rawTarget && item.values && Array.isArray(item.values)) {
      const validNumbers = item.values
        .map((v) => parseFloat(v[1]))
        .filter((val) => !isNaN(val) && val > 0);

      if (validNumbers.length > 0) {
        const sum = validNumbers.reduce((acc, v) => acc + v, 0);
        const avgMs = Math.round((sum / validNumbers.length) * 1000);
        avgTtftMap.set(rawTarget, avgMs);
        const lastVal = validNumbers[validNumbers.length - 1];
        latestRangeTtftMap.set(rawTarget, Math.round(lastVal * 1000));
      }
    }
  }

  // Map Range success values by metric target string
  const rangeMap = new Map();
  for (const item of successRange || []) {
    const rawTarget = item.metric?.model;
    if (rawTarget) {
      rangeMap.set(rawTarget, item.values || []);
    }
  }

  const now = Math.floor(Date.now() / 1000);
  const thirtyDaysAgo = now - 30 * 24 * 3600;
  const VISUAL_BARS = 60; // 60 slim bars across 30 days
  const barDuration = (30 * 24 * 3600) / VISUAL_BARS;

  const processed = successInstant.map((item) => {
    const rawTarget = item.metric?.model || "Unknown Model";
    const { modelName, supplierName } = parseModelSupplier(rawTarget);
    const rawSuccessValues = rangeMap.get(rawTarget) || [];

    // Current latency
    const currentLatencyMs =
      instantTtftMap.get(rawTarget) ?? latestRangeTtftMap.get(rawTarget) ?? null;
    const currentLatency = currentLatencyMs !== null ? `~${currentLatencyMs}ms` : null;

    // 30-day average latency
    const avgLatencyMs = avgTtftMap.get(rawTarget) ?? currentLatencyMs ?? null;
    const avgLatency = avgLatencyMs !== null ? `~${avgLatencyMs}ms` : null;

    let successfulCount = 0;
    for (const v of rawSuccessValues) {
      if (v[1] === "1") {
        successfulCount++;
      }
    }

    // Last received bar determines operational status
    let lastReceivedSuccess = item.value?.[1] === "1";
    if (rawSuccessValues.length > 0) {
      const lastBar = rawSuccessValues[rawSuccessValues.length - 1];
      lastReceivedSuccess = lastBar[1] === "1";
    }

    // Exact formula: number of test success = 1 / 8640 * 100
    const percentageVal = (successfulCount / TOTAL_30_DAYS_SLOTS) * 100;
    const uptimePercentage = `${percentageVal.toFixed(2)}%`;

    const isOperational = lastReceivedSuccess;
    const status = isOperational ? "Operational" : "Down";

    // Build the 30-day timeline across visual bars
    const historyBars = [];
    for (let i = 0; i < VISUAL_BARS; i++) {
      const barStart = thirtyDaysAgo + i * barDuration;
      const barEnd = barStart + barDuration;

      const samplesInBar = rawSuccessValues.filter((v) => v[0] >= barStart && v[0] < barEnd);

      let barStatus = "no-data";
      let barSuccessCount = 0;
      if (samplesInBar.length > 0) {
        barSuccessCount = samplesInBar.filter((v) => v[1] === "1").length;
        if (barSuccessCount === samplesInBar.length) {
          barStatus = "operational";
        } else if (barSuccessCount === 0) {
          barStatus = "down";
        } else {
          barStatus = "degraded";
        }
      }

      const dateLabel = new Date(barStart * 1000).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });

      historyBars.push({
        status: barStatus,
        value: barStatus === "operational" ? 1 : barStatus === "down" ? 0 : null,
        samplesCount: samplesInBar.length,
        timestamp: `${dateLabel}: ${
          samplesInBar.length > 0
            ? `${barSuccessCount}/${samplesInBar.length} checks operational (5m interval)`
            : "No data recorded"
        }`,
        latency: currentLatencyMs || (barStatus === "operational" ? 90 : 0),
      });
    }

    return {
      rawTarget,
      title: rawTarget,
      modelName,
      supplierName,
      status,
      isOperational,
      uptimePercentage,
      successfulCount,
      totalCount: TOTAL_30_DAYS_SLOTS,
      recordedCount: rawSuccessValues.length,
      currentLatency,
      avgLatency,
      historyData: historyBars,
      startLabel: "30 days ago",
      endLabel: "Today",
    };
  });

  return filterIgnoredItems(processed);
}

export async function fetchAllMetrics() {
  const now = Math.floor(Date.now() / 1000);
  const thirtyDaysAgo = now - 30 * 24 * 3600;

  const [
    pubSuccess,
    pubTtft,
    pubRange,
    pubTtftRange,
    curSuccess,
    curTtft,
    curRange,
    curTtftRange,
    supSuccess,
    supTtft,
    supRange,
    supTtftRange,
  ] = await Promise.all([
    fetchPrometheusInstant("publicai_router_model_test_success"),
    fetchPrometheusInstant("publicai_router_model_ttft_seconds"),
    fetchPrometheusRange("publicai_router_model_test_success", thirtyDaysAgo, now, 300),
    fetchPrometheusRange("publicai_router_model_ttft_seconds", thirtyDaysAgo, now, 300),
    fetchPrometheusInstant("currentai_router_model_test_success"),
    fetchPrometheusInstant("currentai_router_model_ttft_seconds"),
    fetchPrometheusRange("currentai_router_model_test_success", thirtyDaysAgo, now, 300),
    fetchPrometheusRange("currentai_router_model_ttft_seconds", thirtyDaysAgo, now, 300),
    fetchPrometheusInstant("suppliers_model_test_success"),
    fetchPrometheusInstant("suppliers_model_ttft_seconds"),
    fetchPrometheusRange("suppliers_model_test_success", thirtyDaysAgo, now, 300),
    fetchPrometheusRange("suppliers_model_ttft_seconds", thirtyDaysAgo, now, 300),
  ]);

  const publicAiItems = processMetricData(pubSuccess, pubTtft, pubRange, pubTtftRange);
  const currentAiItems = processMetricData(curSuccess, curTtft, curRange, curTtftRange);
  const supplierItems = processMetricData(supSuccess, supTtft, supRange, supTtftRange);

  return {
    publicai_router: publicAiItems,
    currentai_router: currentAiItems,
    supply_model: supplierItems,
    supply_supplier: supplierItems,
    fetchedAt: new Date().toISOString(),
  };
}

export async function getCachedMetrics(forceRefresh = false) {
  const now = Date.now();
  const cacheTtlMs = METRICS_REVALIDATE_SECONDS * 1000;

  if (
    !forceRefresh &&
    memoryCache.data &&
    now - memoryCache.timestamp < cacheTtlMs
  ) {
    return memoryCache.data;
  }

  // Deduplicate concurrent fetch promises
  if (!memoryCache.promise) {
    memoryCache.promise = fetchAllMetrics()
      .then((data) => {
        memoryCache.data = data;
        memoryCache.timestamp = Date.now();
        memoryCache.promise = null;
        return data;
      })
      .catch((err) => {
        memoryCache.promise = null;
        console.error("Failed to fetch Prometheus metrics:", err);
        // Fallback to stale data if available
        if (memoryCache.data) {
          return memoryCache.data;
        }
        return {
          publicai_router: [],
          currentai_router: [],
          supply_model: [],
          supply_supplier: [],
          fetchedAt: new Date().toISOString(),
        };
      });
  }

  return memoryCache.promise;
}
