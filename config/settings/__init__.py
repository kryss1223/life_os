import os


if os.environ.get("DJANGO_ENV") == "production" or os.environ.get("RENDER"):
    from .production import *  # noqa: F401,F403
else:
    from .development import *  # noqa: F401,F403
