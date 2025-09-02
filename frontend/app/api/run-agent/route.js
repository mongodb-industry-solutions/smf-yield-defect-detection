export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const query_reported = searchParams.get("query_reported");
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    const apiEndpoint = `${apiUrl}/run-agent?query_reported=${encodeURIComponent(query_reported)}`;
    console.log("API Endpoint:", apiEndpoint); // Debugging log
    const res = await fetch(apiEndpoint);

    const contentType = res.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      throw new Error(`Unexpected response type: ${contentType}`);
    }

    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error in API call:", error.message); // Log error
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}