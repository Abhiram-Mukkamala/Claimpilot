import os

# Vision models (SAM2 / DSINE / Depth Anything) download weights on first use.
# Keep the existing backend tests offline and fast; test_vision_integration.py
# exercises the vision stages with stubs instead.
os.environ.setdefault("VISION_PIPELINE_ENABLED", "false")
