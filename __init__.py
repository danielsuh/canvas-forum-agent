"""Hermes plugin entry point. Registers four tools under the toolset canvas_forum."""
from pathlib import Path

try:
    from . import schemas, tools
except ImportError:
    import schemas, tools

TOOLSET = "canvas_forum"


def register(ctx):
    ctx.register_tool(name="canvas_forum_check", toolset=TOOLSET, schema=schemas.CHECK, handler=tools.check)
    ctx.register_tool(name="canvas_forum_post", toolset=TOOLSET, schema=schemas.POST, handler=tools.post)
    ctx.register_tool(name="canvas_forum_skip", toolset=TOOLSET, schema=schemas.SKIP, handler=tools.skip)
    ctx.register_tool(name="canvas_forum_status", toolset=TOOLSET, schema=schemas.STATUS, handler=tools.status)
    try:
        ctx.register_skill("forum-participation", str(Path(__file__).parent / "skills" / "forum-participation"))
    except Exception:
        # If skill registration is unavailable, copy skills/forum-participation to ~/.hermes/skills/
        pass
