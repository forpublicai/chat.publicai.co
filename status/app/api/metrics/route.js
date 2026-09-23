import { NextResponse } from "next/server";

const PROMETHEUS_URL = process.env.PROMETHEUS_URL || "http://localhost:9090";
const TOTAL_30_DAYS_SLOTS = 30 * 24 * 12; // 8,640 5-minute slots in 30 days

async function fetchPrometheusInstant(query) {
  try {
    const url = `${PROMETHEUS_URL}/api/v1/query?query=${encodeURIComponent(query)}`;
    const res = await fetch(url, { cache: "no-store" });
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
    const res = await fetch(url, { cache: "no-store" });
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

  return successInstant.map((item) => {
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
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const source = searchParams.get("source") || "all";

  const now = Math.floor(Date.now() / 1000);
  const thirtyDaysAgo = now - 30 * 24 * 3600;

  try {
    if (source === "publicai_router") {
      const [pubSuccess, pubTtft, pubRange, pubTtftRange] = await Promise.all([
        fetchPrometheusInstant("publicai_router_model_test_success"),
        fetchPrometheusInstant("publicai_router_model_ttft_seconds"),
        fetchPrometheusRange("publicai_router_model_test_success", thirtyDaysAgo, now, 300),
        fetchPrometheusRange("publicai_router_model_ttft_seconds", thirtyDaysAgo, now, 300),
      ]);
      const publicAiItems = processMetricData(pubSuccess, pubTtft, pubRange, pubTtftRange);
      return NextResponse.json({ items: publicAiItems });
    }

    if (source === "currentai_router") {
      const [curSuccess, curTtft, curRange, curTtftRange] = await Promise.all([
        fetchPrometheusInstant("currentai_router_model_test_success"),
        fetchPrometheusInstant("currentai_router_model_ttft_seconds"),
        fetchPrometheusRange("currentai_router_model_test_success", thirtyDaysAgo, now, 300),
        fetchPrometheusRange("currentai_router_model_ttft_seconds", thirtyDaysAgo, now, 300),
      ]);
      const currentAiItems = processMetricData(curSuccess, curTtft, curRange, curTtftRange);
      return NextResponse.json({ items: currentAiItems });
    }

    // Fetch all
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

    return NextResponse.json({
      publicai_router: publicAiItems,
      currentai_router: currentAiItems,
      supply_model: supplierItems,
      supply_supplier: supplierItems,
    });
  } catch (error) {
    console.error("Error in /api/metrics:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
