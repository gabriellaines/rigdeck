"""Game monitor: summaries, MangoHud logs and frame statistics."""
import os
import time

from rigdeck import sessions


def test_summary_stats_and_game():
    samples = [{"t": i, "cpu": c, "gpu": 90, "gpuTemp": 60 + i, "top": "cs2" if i else "steam",
                "disks": {"nvme0n1": {"r": 1000, "w": 0, "temp": 40}}} for i, c in enumerate([10, 20, 30, 40, 50])]
    s = sessions.summarize(samples)
    assert s["duration"] == 4 and s["game"] == "cs2"
    assert s["metrics"]["cpu"] == {"avg": 30.0, "min": 10, "max": 50, "p95": 50, "p5": 10}
    assert s["disks"]["nvme0n1"]["read"] == 5000 and s["disks"]["nvme0n1"]["temp"]["max"] == 40


def test_frame_stats_capframex_style():
    st = sessions.frame_stats([16.6] * 980 + [33.3] * 15 + [50.0] * 5)
    assert (st["avgFps"], st["low1"], st["low01"], st["ftMax"]) == (58.8, 30.0, 20.0, 50.0)
    assert sessions.frame_stats([16.6] * 5) is None          # too few frames to mean anything


def write_log(folder, name, start, frametimes):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}_{time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(start))}.csv")
    with open(path, "w") as f:
        f.write("os,cpu,gpu,ram,kernel,driver,cpuscheduler\nArch,x,y,32,7.2,mesa,eevdf\n")
        f.write("fps,frametime,cpu_load,cpu_power,gpu_load,cpu_temp,gpu_temp,gpu_core_clock,gpu_mem_clock,"
                "gpu_vram_used,gpu_power,ram_used,swap_used,process_rss,elapsed\n")
        e = 0.0
        for ft in frametimes:
            e += ft / 1000
            f.write(f"{1000 / ft:.1f},{ft},0,0,0,0,0,0,0,0,0,0,0,0,{int(e * 1e9)}\n")
    return path


def test_mangohud_log_matched_to_session(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions, "FRAMES_DIR", str(tmp_path))
    start = time.mktime(time.strptime("2026-10-01 22:00:00", "%Y-%m-%d %H:%M:%S"))
    write_log(str(tmp_path), "cs2", start + 2, [10.0] * 500)              # 5 s of 100 fps, starting 2 s in
    write_log(str(tmp_path), "other", start + 3600, [10.0] * 500)         # an hour later: another session
    fr = sessions.frames_for("x", "2026-10-01 22:00:00", 30)
    assert fr["game"] == "cs2" and fr["frames"] == 500 and fr["avgFps"] == 100.0
    assert set(fr["fps"]) == {100.0} and len(fr["fps"]) in (5, 6)          # one value per second (2.01 s … 7.00 s)


def test_mangohud_config_never_overwritten(tmp_path, monkeypatch):
    conf = tmp_path / "MangoHud.conf"
    monkeypatch.setattr(sessions, "MANGOHUD_CONF", str(conf))
    monkeypatch.setattr(sessions, "FRAMES_DIR", str(tmp_path / "frames"))
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)
    assert sessions.mangohud_state() == "setup"
    sessions.setup_mangohud()
    assert sessions.mangohud_state() == "ready"
    conf.write_text("fps_limit=144\n")                                  # the user's own config
    assert sessions.mangohud_state() == "conflict"
    try:
        sessions.setup_mangohud()
        raise AssertionError("must not overwrite")
    except RuntimeError:
        pass
    assert conf.read_text() == "fps_limit=144\n"
