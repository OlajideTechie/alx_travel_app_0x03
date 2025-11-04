from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import Throttled

class CustomScopedRateThrottle(ScopedRateThrottle):
    """Custom throttle to return a friendly message when rate limit is exceeded."""

    def throttle_failure(self):
        wait = self.wait()
        detail = (
            f"Too many requests. Please try again after {int(wait)} seconds."
            if wait
            else "You are sending requests too quickly. Please wait a bit."
        )
        raise Throttled(detail=detail)