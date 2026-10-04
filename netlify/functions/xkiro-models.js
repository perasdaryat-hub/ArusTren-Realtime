export default async (request) => {
  if (request.method !== "GET" && request.method !== "OPTIONS") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "content-type": "application/json", "allow": "GET, OPTIONS" }
    });
  }

  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, OPTIONS"
      }
    });
  }

  try {
    const upstream = await fetch("https://api.xkiro.com/v1/models", {
      headers: { "accept": "application/json" }
    });
    const text = await upstream.text();

    return new Response(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json",
        "cache-control": "public, max-age=300"
      }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      error: { message: "Tidak dapat terhubung ke xKiro: " + (error?.message || "network error") }
    }), {
      status: 502,
      headers: { "content-type": "application/json" }
    });
  }
};