import os
import tempfile

# Must run before `app` is imported: config and engine read these at import time.
_tmp = tempfile.mkdtemp(prefix="signforge-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SIGNFORGE_DATA_DIR"] = f"{_tmp}/processed"
os.environ["SIGNFORGE_CHECKPOINT_DIR"] = f"{_tmp}/checkpoints"
