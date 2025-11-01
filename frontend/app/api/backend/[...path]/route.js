/**
 * Universal Backend Proxy Route for Single-Pod Kanopy Deployment
 *
 * This route proxies ALL backend API calls through Next.js server-side
 * to enable loopback communication in single-pod deployment.
 *
 * Architecture:
 * - Browser calls: /api/backend/sensors/realtime
 * - Next.js (server-side) proxies to: http://127.0.0.1:8000/sensors/realtime
 * - Backend responds
 * - Next.js returns response to browser
 *
 * This works because Next.js API routes run SERVER-SIDE in the frontend container,
 * which shares the same network namespace as the backend sidecar container.
 * Loopback (127.0.0.1) communication works within the pod!
 */

// Backend URL - uses loopback in Kanopy, localhost in local development
const BACKEND_URL = process.env.INTERNAL_API_URL ||
                    process.env.NEXT_PUBLIC_API_URL ||
                    'http://localhost:8000';

console.log(`[Backend Proxy] Configured with backend URL: ${BACKEND_URL}`);

/**
 * Handle GET requests
 */
export async function GET(request, { params }) {
  return proxyRequest(request, params, 'GET');
}

/**
 * Handle POST requests
 */
export async function POST(request, { params }) {
  return proxyRequest(request, params, 'POST');
}

/**
 * Handle PUT requests
 */
export async function PUT(request, { params }) {
  return proxyRequest(request, params, 'PUT');
}

/**
 * Handle DELETE requests
 */
export async function DELETE(request, { params }) {
  return proxyRequest(request, params, 'DELETE');
}

/**
 * Handle PATCH requests
 */
export async function PATCH(request, { params }) {
  return proxyRequest(request, params, 'PATCH');
}

/**
 * Universal proxy function that forwards requests to backend
 */
async function proxyRequest(request, params, method) {
  try {
    // Extract path segments from dynamic route (e.g., ['sensors', 'realtime'])
    const pathSegments = params.path || [];
    const backendPath = `/${pathSegments.join('/')}`;

    // Preserve query parameters from original request
    const url = new URL(request.url);
    const queryString = url.search;

    // Build full backend URL
    const backendFullUrl = `${BACKEND_URL}${backendPath}${queryString}`;

    console.log(`[Backend Proxy] ${method} ${backendPath}${queryString}`);

    // Prepare request options
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
        // Forward authorization header if present
        ...(request.headers.get('authorization') && {
          'Authorization': request.headers.get('authorization')
        }),
      },
    };

    // Include body for POST/PUT/PATCH requests
    if (['POST', 'PUT', 'PATCH'].includes(method)) {
      try {
        const contentType = request.headers.get('content-type');

        if (contentType?.includes('application/json')) {
          const body = await request.json();
          options.body = JSON.stringify(body);
        } else {
          // Handle other content types (form data, etc.)
          options.body = await request.text();
          if (contentType) {
            options.headers['Content-Type'] = contentType;
          }
        }
      } catch (e) {
        // No body or invalid format, continue without body
        console.log('[Backend Proxy] No valid body to forward');
      }
    }

    // Make request to backend via loopback
    const response = await fetch(backendFullUrl, options);

    // Get response data
    const contentType = response.headers.get('content-type');

    // Handle SSE (Server-Sent Events) - stream directly without buffering
    if (contentType?.includes('text/event-stream')) {
      console.log('[Backend Proxy] Streaming SSE response');
      return new Response(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    }

    let data;

    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else if (contentType?.includes('text/')) {
      data = await response.text();
    } else {
      // Handle binary data (images, files, etc.)
      const buffer = await response.arrayBuffer();
      return new Response(buffer, {
        status: response.status,
        headers: {
          'Content-Type': contentType || 'application/octet-stream',
        },
      });
    }

    // Return JSON/text response with same status code
    if (typeof data === 'string') {
      return new Response(data, {
        status: response.status,
        headers: {
          'Content-Type': contentType || 'text/plain',
        },
      });
    }

    return Response.json(data, {
      status: response.status,
      headers: {
        'Content-Type': 'application/json',
      },
    });

  } catch (error) {
    console.error('[Backend Proxy] Error:', error);

    return Response.json(
      {
        error: 'Backend proxy error',
        message: error.message,
        details: `Failed to connect to backend at ${BACKEND_URL}`,
        hint: 'Check if backend container is running and INTERNAL_API_URL is configured correctly',
      },
      {
        status: 503,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
  }
}
