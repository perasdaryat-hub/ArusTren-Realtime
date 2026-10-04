export default async (req) => {
  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "content-type": "application/json", "allow": "GET" }
    });
  }

  const url = new URL(req.url);
  const q = (url.searchParams.get("q") || "novel").trim().slice(0, 120);
  const page = Math.max(1, Math.min(5000, Number(url.searchParams.get("page")) || 1));
  const limit = Math.max(1, Math.min(20, Number(url.searchParams.get("limit")) || 20));

  const params = new URLSearchParams({
    q: q + " ebook_access:public",
    page: String(page),
    limit: String(limit),
    fields: "key,title,author_name,first_publish_year,cover_i,ebook_access,has_fulltext,public_scan_b"
  });

  try {
    const upstream = await fetch("https://openlibrary.org/search.json?" + params.toString(), {
      headers: {
        "Accept": "application/json",
        "User-Agent": "ArusTren-Library/1.0 (public book discovery)"
      }
    });

    const body = await upstream.text();
    if (!upstream.ok) {
      return new Response(JSON.stringify({ error: "Open Library mengembalikan HTTP " + upstream.status }), {
        status: 502,
        headers: { "content-type": "application/json", "cache-control": "no-store" }
      });
    }

    return new Response(body, {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "public, max-age=300, s-maxage=900"
      }
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: "Katalog buku sedang tidak tersedia." }), {
      status: 502,
      headers: { "content-type": "application/json", "cache-control": "no-store" }
    });
  }
};

export const config = {
  path: "/.netlify/functions/book-catalog"
};
