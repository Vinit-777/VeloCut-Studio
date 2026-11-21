import sys
import shutil
from pathlib import Path
from typing import List


def _find_js_runtime_args() -> List[str]:
    try:
        import deno
        deno_bin = deno.find_deno_bin()
        if deno_bin and Path(deno_bin).exists():
            return ["--js-runtimes", f"deno:{deno_bin}"]
    except Exception:
        pass
    deno_path = shutil.which("deno")
    if deno_path:
        return ["--js-runtimes", f"deno:{deno_path}"]
    node_path = shutil.which("node") or shutil.which("nodejs")
    if node_path:
        return ["--js-runtimes", f"node:{node_path}"]
    return []


def ytdlp_base_cmd() -> List[str]:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        "--sleep-requests", "0.4",
        *_find_js_runtime_args(),
    ]
    for cand in (Path("cookies.txt"), Path("assets/cookies.txt")):
        if cand.exists() and cand.stat().st_size > 100:
            cmd += ["--cookies", str(cand.resolve())]
            break
    return cmd
