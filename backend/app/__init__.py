"""GridSignal Mini - Utility Incident Analytics Platform"""
__version__ = "1.0.0"

# Starlette 1.x compatibility shim for FastAPI <= 0.115
try:
    import starlette.routing
    _orig_router_init = starlette.routing.Router.__init__
    def _compat_router_init(self, *args, **kwargs):
        kwargs.pop("on_startup", None)
        kwargs.pop("on_shutdown", None)
        return _orig_router_init(self, *args, **kwargs)
    starlette.routing.Router.__init__ = _compat_router_init
except Exception:
    pass
