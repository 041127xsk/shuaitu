"""
http_utils.py - 统一 HTTP 请求封装
===================================
提供带重试、指数退避、超时的请求函数。
供 article_extractor.py 和 hero_catalog.py 共用。
"""
from __future__ import annotations

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

# 从环境变量读取配置，有默认值
DEFAULT_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
BASE_DELAY = float(os.getenv("HTTP_BASE_DELAY", "1.0"))
USER_AGENT = os.getenv("HTTP_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

# 可重试的 HTTP 状态码
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_with_retry(
    url: str,
    *,
    params: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    headers: dict | None = None,
    as_json: bool = True,
) -> requests.Response:
    """
    带重试和指数退避的 HTTP GET 请求。

    参数:
        url:         请求地址
        params:      查询参数
        timeout:     超时秒数
        max_retries: 最大重试次数
        base_delay:  基础退避秒数（实际等待 = base_delay * 2^attempt）
        headers:     自定义请求头（默认带 User-Agent）
        as_json:     是否尝试解析 JSON（仅用于判断响应是否正常）

    返回:
        requests.Response 对象

    异常:
        最终失败时抛出 requests.RequestException
    """
    if headers is None:
        headers = {"User-Agent": USER_AGENT}
    elif "User-Agent" not in headers:
        headers["User-Agent"] = USER_AGENT

    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout, headers=headers)

            # 429 Too Many Requests — 退避重试
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    # 429 时优先用 Retry-After 头
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = max(delay, float(retry_after))
                            except ValueError:
                                pass
                    logger.warning(
                        "HTTP %d for %s, retry %d/%d after %.1fs",
                        response.status_code, url, attempt + 1, max_retries, delay,
                    )
                    time.sleep(delay)
                    continue
                response.raise_for_status()

            response.raise_for_status()
            return response

        except requests.ConnectionError as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Connection error for %s: %s, retry %d/%d after %.1fs",
                    url, exc, attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                continue
            raise

        except requests.Timeout as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Timeout for %s, retry %d/%d after %.1fs",
                    url, attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                continue
            raise

    # 不应到这里，但以防万一
    if last_exc:
        raise last_exc
    raise RuntimeError(f"fetch_with_retry: unexpected exit for {url}")
