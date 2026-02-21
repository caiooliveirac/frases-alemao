import logging
import time


logger = logging.getLogger("request_timing")


class RequestTimingLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "request_timing method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.path,
            getattr(response, "status_code", "-"),
            elapsed_ms,
        )
        return response