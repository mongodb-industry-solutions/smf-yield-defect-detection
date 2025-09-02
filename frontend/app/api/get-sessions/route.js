export async function GET(request) {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      const apiEndpoint = `${apiUrl}/get-sessions`;
      const res = await fetch(apiEndpoint);
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }
  }