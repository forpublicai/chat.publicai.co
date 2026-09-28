import { NextResponse } from "next/server";
import { getCachedMetrics, METRICS_REVALIDATE_SECONDS } from "@/lib/metrics";

export const revalidate = 300;

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const source = searchParams.get("source") || "all";
  const refresh = searchParams.get("refresh") === "true";

  try {
    const data = await getCachedMetrics(refresh);

    if (source === "publicai_router") {
      return NextResponse.json(
        { items: data.publicai_router },
        {
          headers: {
            "Cache-Control": `public, s-maxage=${METRICS_REVALIDATE_SECONDS}, stale-while-revalidate=60`,
          },
        }
      );
    }

    if (source === "currentai_router") {
      return NextResponse.json(
        { items: data.currentai_router },
        {
          headers: {
            "Cache-Control": `public, s-maxage=${METRICS_REVALIDATE_SECONDS}, stale-while-revalidate=60`,
          },
        }
      );
    }

    return NextResponse.json(data, {
      headers: {
        "Cache-Control": `public, s-maxage=${METRICS_REVALIDATE_SECONDS}, stale-while-revalidate=60`,
      },
    });
  } catch (error) {
    console.error("Error in /api/metrics:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
