"""Background jobs: Construct runs that may outlast Hermes's tool deadline (420 s).

Every Construct run that can take long (a build, a review, an export, a film, a long command) starts as a
job: a detached child in its own process group, writing its output to jobs/<id>/log.txt and how it ended
to jobs/<id>/exit.json. The tool that started it waits for it a while; a job that finishes in that time
answers at once, one that does not is reported by `construct_job` (and finished there: the result is
made once and kept in result.json).

Children are stopped when the plugin unloads (`stop_all`, from `ctx.on_unload`).
"""

import contextvars
import json
import os
import secrets
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import runtime

LOST_AFTER = 6 * 3600        # a job without an end record after this long is reported lost
_procs = {}                  # job id -> Popen, for the jobs this process started
_lock = threading.Lock()
_finishers = {}              # kind -> function(job record, exit record) -> result dict
_watch = {"post": None, "event": None}


def register_finisher(kind, fn):
    _finishers[kind] = fn


def set_reporters(post=None, event=None):
    """How a running job reports: `post(text)` -> a handle with `edit(text)` (a chat status message),
    `event(name, payload)` (an event to the Desktop half). Either may be None."""
    _watch.update(post=post, event=event)


def folder(job_id):
    if not isinstance(job_id, str) or not runtime.JOB.match(job_id):
        raise runtime.ConstructError("job_id must be a job id as a tool returned it (12 hexadecimal characters)")
    path = runtime.jobs_root() / job_id
    if not (path / "job.json").is_file():
        raise runtime.ConstructError("no job %s" % job_id)
    return path


def record(job_id):
    return json.loads((folder(job_id) / "job.json").read_text(encoding="utf-8"))


def start(kind, op, args=(), *, project=None, label="", finish=None, cwd=None, spec=None):
    """Start a job: `op` and `args` for child.py; a `spec` dict is written beside the job and passed as its path
    (a film's work folder, `work`, defaults to the job's own). `finish` is kept for the kind's finisher."""
    job_id = secrets.token_hex(6)
    path = runtime.jobs_root() / job_id
    path.mkdir(parents=True)
    args = list(args)
    if spec is not None:
        spec = dict(spec)
        spec.setdefault("work", str(path / "work"))
        runtime.write_json(path / "spec.json", spec)
        args.append(str(path / "spec.json"))
    rec = {"id": job_id, "kind": kind, "label": label, "project": project, "op": op, "created": time.time(),
           "finish": finish or {}}
    runtime.write_json(path / "job.json", rec)
    log = open(path / "log.txt", "w", encoding="utf-8")
    try:
        kw = {"start_new_session": True} if os.name == "posix" else {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
        proc = subprocess.Popen(runtime.child_argv("job", path, op, *args), stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, cwd=str(cwd) if cwd else None, **kw)
    finally:
        log.close()
    rec["pid"] = proc.pid
    runtime.write_json(path / "job.json", rec)
    with _lock:
        _procs[job_id] = proc
    return job_id


def _alive(rec):
    proc = _procs.get(rec["id"])
    if proc is not None:
        return proc.poll() is None
    pid = rec.get("pid")
    if not pid or time.time() - rec.get("created", 0) > LOST_AFTER:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ended(job_id):
    """The job's end record, or None while it runs. A child that died without one ended with a failure."""
    path = folder(job_id)
    exit_file = path / "exit.json"
    if exit_file.is_file():
        try:
            return json.loads(exit_file.read_text(encoding="utf-8"))
        except ValueError:
            pass
    rec = record(job_id)
    if _alive(rec):
        return None
    if exit_file.is_file():   # it ended between the two looks
        return json.loads(exit_file.read_text(encoding="utf-8"))
    return {"code": None, "error": "stopped before it finished (cancelled, the plugin was unloaded or Hermes restarted)",
            "ended": time.time()}


def wait(job_id, seconds):
    """Wait up to `seconds` for the job to end; its end record, or None if it still runs."""
    deadline = time.time() + max(0.0, seconds)
    proc = _procs.get(job_id)
    if proc is not None:
        try:
            proc.wait(timeout=max(0.0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            return None
        # the child writes exit.json just before it exits; give the file system a moment
        for _ in range(20):
            done = ended(job_id)
            if done is not None:
                return done
            time.sleep(0.05)
        return ended(job_id)
    while time.time() < deadline:
        done = ended(job_id)
        if done is not None:
            return done
        time.sleep(0.5)
    return ended(job_id)


def log_tail(job_id, lines=40, chars=6000):
    try:
        text = (folder(job_id) / "log.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    tail = "\n".join(text.splitlines()[-lines:])
    return tail[-chars:]


def progress(job_id):
    """{"done", "total", "percent", "unit"} when the job's kind can be counted, else {}."""
    path = folder(job_id)
    try:
        spec = json.loads((path / "work" / "progress.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    frames = path / "work" / "frames"
    if isinstance(spec.get("done"), (int, float)):   # a job that counts for itself (a NetLogo run's ticks)
        done = int(spec["done"])
    else:
        done = sum(1 for _ in frames.glob("frame-*.png")) if frames.is_dir() else 0
    total = int(spec.get("total") or 0)
    if not total:
        return {}
    done = min(done, total)
    encoding = done >= total and not (path / "exit.json").is_file()
    return {"done": done, "total": total, "unit": spec.get("unit", "frames"), "percent": round(100.0 * done / total),
            "stage": "encoding" if encoding else ("rendering" if done else "preparing")}


def status(job_id):
    """The job as the model sees it: running (with progress), or ended (with its result, made once)."""
    rec = record(job_id)
    done = ended(job_id)
    out = {"job_id": job_id, "kind": rec["kind"], "label": rec.get("label", ""), "project": rec.get("project"),
           "elapsed_s": round(((done or {}).get("ended") or time.time()) - rec["created"], 1)}
    if done is None:
        out.update(state="running", progress=progress(job_id),
                   next="call construct_job again in a while (a film renders about 1-2 frames a second)")
        return out
    return dict(out, **finish(job_id, rec, done))


def finish(job_id, rec, done):
    """The job's result, made by its kind's finisher the first time and kept in result.json."""
    path = folder(job_id)
    keep = path / "result.json"
    with _lock:
        if keep.is_file():
            try:
                return json.loads(keep.read_text(encoding="utf-8"))
            except ValueError:
                pass
        fn = _finishers.get(rec["kind"])
        try:
            result = fn(rec, done, log_tail(job_id)) if fn else {"state": "done" if done.get("code") == 0 else "failed",
                                                              "exit": done.get("code"), "log": log_tail(job_id)}
        except runtime.ConstructError as exc:
            result = {"state": "failed", "error": str(exc), "log": log_tail(job_id)}
        result.setdefault("state", "done" if done.get("code") == 0 else "failed")
        runtime.write_json(keep, result)
        return result


def cancel(job_id):
    rec = record(job_id)
    if ended(job_id) is not None:
        return False
    _kill(rec.get("pid"), _procs.get(job_id))
    return True


def _kill(pid, proc=None):
    try:
        if os.name == "posix" and pid:
            os.killpg(pid, signal.SIGTERM)   # the job's own group: its browser and encoder go with it
        elif proc is not None:
            proc.terminate()
    except OSError:
        pass


def stop_all():
    """Stop every job this process started that still runs (the plugin is unloading)."""
    with _lock:
        procs = list(_procs.items())
    for job_id, proc in procs:
        if proc.poll() is None:
            _kill(proc.pid, proc)
    for _, proc in procs:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass


def recent(limit=12):
    """The newest jobs, newest first, in brief."""
    rows = []
    root = runtime.jobs_root()
    for path in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        if not runtime.JOB.match(path.name) or not (path / "job.json").is_file():
            continue
        try:
            rec = json.loads((path / "job.json").read_text(encoding="utf-8"))
            done = ended(path.name)
        except (OSError, ValueError, runtime.ConstructError):
            continue
        rows.append({"job_id": path.name, "kind": rec["kind"], "label": rec.get("label", ""), "project": rec.get("project"),
                     "state": "running" if done is None else ("done" if done.get("code") == 0 else "failed")})
    return rows


def watch(job_id, label, every=2.0, post_every=15.0):
    """Report a job that keeps running after its tool call: a status message in the chat, edited as it goes,
    and progress events for the Desktop half. Runs in a thread started with the call's context."""
    post, event = _watch["post"], _watch["event"]
    handle = None
    if post is not None:
        try:
            handle = post("Construct: %s started (job %s)." % (label, job_id))
        except Exception:   # a surface without status messages: progress still reaches the Desktop
            handle = None

    def loop():
        nonlocal handle
        last_post = time.time()
        while True:
            try:
                done = ended(job_id)
                prog = progress(job_id)
            except runtime.ConstructError:
                return
            state = "running" if done is None else ("done" if done.get("code") == 0 else "failed")
            payload = {"job_id": job_id, "label": label, "state": state, "percent": prog.get("percent"),
                       "done": prog.get("done"), "total": prog.get("total"), "stage": prog.get("stage")}
            if event is not None:
                try:
                    event("job.progress", payload)
                except Exception:   # no Desktop connected: nothing to tell
                    pass
            now = time.time()
            if handle is not None and (done is not None or now - last_post >= post_every):
                last_post = now
                if done is None:
                    text = "Construct: %s, %s%s (job %s)." % (
                        label, prog.get("stage", "running"),
                        " %d of %d %s, %d%%" % (prog["done"], prog["total"], prog["unit"], prog["percent"]) if prog else "",
                        job_id)
                else:
                    text = "Construct: %s %s (job %s). Ask for the result, or the agent reads it with construct_job." % (
                        label, "finished" if state == "done" else "failed", job_id)
                try:
                    handle.edit(text)
                except Exception:
                    handle = None
            if done is not None:
                return
            time.sleep(every)

    # the thread keeps the call's context, so its message edits reach the conversation that started the job
    context = contextvars.copy_context()
    t = threading.Thread(target=context.run, args=(loop,), name="construct-job-%s" % job_id, daemon=True)
    t.start()
    return t
