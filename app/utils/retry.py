from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
import requests

class RetryableHTTPError(Exception):
    pass

retry_policy = retry(
    reraise=True,
    stop=stop_after_attempt(6),
    wait=wait_exponential_jitter(initial=0.5, max=30),
    retry=retry_if_exception_type((RetryableHTTPError, requests.exceptions.RequestException)),
)
