try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    from app.core.config import REDIS_URL

    _limiter_kwargs: dict = {"key_func": get_remote_address}
    if REDIS_URL:
        _limiter_kwargs["storage_uri"] = REDIS_URL

    limiter = Limiter(**_limiter_kwargs)

except ImportError:
    # Fallback no-op limiter when slowapi is not installed
    import functools

    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f):
                @functools.wraps(f)
                def wrapper(*a, **kw):
                    return f(*a, **kw)
                return wrapper
            return decorator

    limiter = _NoopLimiter()  # type: ignore
