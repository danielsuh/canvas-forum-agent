"""Tool handlers. Each returns a JSON string and never raises, never returns the token."""
import json

try:
    from . import core
except ImportError:  # running from the repo root in tests
    import core


def _forum():
    return core.Forum(core.Config.from_env())


def _safe(fn):
    def wrapper(params, **kwargs):
        try:
            return json.dumps(fn(params or {}))
        except core.ConfigError as e:
            return json.dumps({"ok": False, "error": "config", "message": str(e)})
        except core.CanvasError as e:
            return json.dumps({"ok": False, "error": e.kind, "message": str(e)})
        except Exception as e:  # last resort, message only, no traceback with env
            return json.dumps({"ok": False, "error": "internal", "message": type(e).__name__})
    return wrapper


@_safe
def check(params):
    return _forum().check_new()


@_safe
def post(params):
    return _forum().post(params.get("body", ""), params.get("parent_entry_id"))


@_safe
def skip(params):
    return _forum().skip(params.get("reason", ""))


@_safe
def status(params):
    return _forum().status()
