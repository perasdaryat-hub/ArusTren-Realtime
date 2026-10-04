export default async (request) => {
  if (request.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "content-type": "application/json", "allow": "POST" }
    });
  }

  try {
    const body = await request.json();
    const apiKey = String(body?.apiKey || "").trim();

    if (!apiKey) {
      return new Response(JSON.stringify({
        error: { message: "API key xKiro belum diisi." }
      }), {
        status: 400,
        headers: { "content-type": "application/json" }
      });
    }

    // API key hanya diteruskan ke xKiro untuk request ini dan tidak disimpan.
    const upstreamBody = {
      model: body.model,
      messages: body.messages,
      temperature: body.temperature,
      max_tokens: body.max_tokens
    };

    const upstream = await fetch("https://api.xkiro.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "authorization": "Bearer " + apiKey,
        "content-type": "application/json",
        "accept": "application/json"
      },
      body: JSON.stringify(upstreamBody)
    });

    const text = await upstream.text();

    return new Response(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") || "application/json"
      }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      error: { message: "Proxy xKiro gagal: " + (error?.message || "network error") }
    }), {
      status: 502,
      headers: { "content-type": "application/json" }
    });
  }
};