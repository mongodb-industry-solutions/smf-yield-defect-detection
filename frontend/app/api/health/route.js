/**
 * Frontend Health Check Endpoint
 * Used by Kanopy for liveness and readiness probes
 */

export async function GET(request) {
  try {
    // Basic health check - frontend is responsive
    const healthData = {
      status: "healthy",
      service: "smf-yield-defect-frontend",
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };

    // Optional: Check backend connectivity via loopback
    // Uncomment if you want to verify backend is also healthy
    /*
    try {
      const backendUrl = process.env.INTERNAL_API_URL || 'http://127.0.0.1:8000';
      const backendResponse = await fetch(`${backendUrl}/monitoring/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(2000), // 2 second timeout
      });

      if (backendResponse.ok) {
        const backendHealth = await backendResponse.json();
        healthData.backend = {
          status: "healthy",
          ...backendHealth
        };
      } else {
        healthData.backend = {
          status: "degraded",
          statusCode: backendResponse.status
        };
      }
    } catch (backendError) {
      healthData.backend = {
        status: "unreachable",
        error: backendError.message
      };
    }
    */

    return Response.json(healthData, {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      }
    });
  } catch (error) {
    return Response.json(
      {
        status: "unhealthy",
        service: "smf-yield-defect-frontend",
        error: error.message,
        timestamp: new Date().toISOString(),
      },
      {
        status: 503,
        headers: {
          'Content-Type': 'application/json',
        }
      }
    );
  }
}
