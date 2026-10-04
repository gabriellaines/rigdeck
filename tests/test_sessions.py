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
    assert len(fr["fps"]) == 31                                           # one value per session second
    assert set(fr["fps"][2:7]) == {100.0} and fr["fps"][0] == 0 and fr["fps"][10] == 0


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


def test_mangohud_no_display_config_is_repaired(tmp_path, monkeypatch):
    conf = tmp_path / "MangoHud.conf"
    monkeypatch.setattr(sessions, "MANGOHUD_CONF", str(conf))
    monkeypatch.setattr(sessions, "FRAMES_DIR", str(tmp_path / "frames"))
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)
    lines = "\n".join(sessions.MANGOHUD_LINES) + "\n"
    conf.write_text(sessions.MARKER + "\n" + lines + "# Hide the overlay\nno_display\n")   # what 0.6/0.7 wrote
    assert sessions.mangohud_state() == "outdated"                    # no_display stops MangoHud logging
    sessions.setup_mangohud()                                         # RigDeck's own file: rewritten
    assert sessions.mangohud_state() == "ready" and "no_display" not in conf.read_text()
    conf.write_text(lines + "no_display=1\n")                         # the user's own: left alone
    assert sessions.mangohud_state() == "conflict"
    conf.write_text(lines + "no_display=0  # off\n")
    assert sessions.mangohud_state() == "ready"


GAME = {"pid": 40, "proc": "Diablo IV.exe", "app": "steam_app_2344520", "title": "Diablo IV"}
BROWSER = {"pid": 77, "proc": "firefox", "app": "firefox", "title": "build guide"}


def test_away_periods_from_focus_changes():
    events = [{**GAME, "t": 0.2}, {"pid": 0, "proc": "", "app": "", "title": "", "t": 10.0},   # alt-tab switcher
              {**BROWSER, "t": 10.3}, {**GAME, "t": 40.0},
              {**BROWSER, "t": 50.0}, {**GAME, "t": 50.4}]                                     # a blip: ignored
    away = sessions.away_periods(events, 60, "Diablo IV")
    assert away == [{"start": 10.0, "end": 40.0, "to": "firefox — build guide"}]
    assert sessions.away_periods(events, 100, None) == away               # no game name: longest-held window
    assert sessions.away_periods([], 60, "Diablo IV") == []


def test_export_has_fps_and_alt_tabs(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions, "DIR", str(tmp_path))
    monkeypatch.setattr(sessions, "FRAMES_DIR", str(tmp_path / "frames"))
    monkeypatch.setattr(sessions, "recording", lambda: None)
    started = "2026-10-01 22:00:00"
    t0 = time.mktime(time.strptime(started, "%Y-%m-%d %H:%M:%S"))
    write_log(str(tmp_path / "frames"), "Diablo IV", t0, [10.0] * 1000 + [20.0] * 500 + [10.0] * 1000)  # 10 s at 50 fps
    samples = [{"t": float(i), "cpu": 10, "top": "Diablo IV.exe", "disks": {}} for i in range(36)]
    (tmp_path / "s.jsonl").write_text("".join(__import__("json").dumps(x) + "\n" for x in samples))
    (tmp_path / "s.json").write_text(__import__("json").dumps({"started": started, "name": "D4",
                                                               "summary": sessions.summarize(samples)}))
    (tmp_path / "s.focus").write_text("".join(__import__("json").dumps(e) + "\n" for e in
                                              [{**GAME, "t": 0.0}, {**BROWSER, "t": 10.0}, {**GAME, "t": 20.0}]))
    d = sessions.details("s")
    assert d["away"] == [{"start": 10.0, "end": 20.0, "to": "firefox — build guide"}]
    assert d["frames"]["inGame"]["avgFps"] == 100.0 and d["frames"]["avgFps"] < 100
    text = open(sessions.export_csv("s", str(tmp_path / "out.csv"))).read()
    head = [l for l in text.splitlines() if l.startswith("#")]
    assert any("in game only" in l and "average 100.0" in l for l in head)
    assert any("alt-tab 1: 0:00:10 – 0:00:20 (10 s) → firefox — build guide" in l for l in head)
    rows = [l.split(",") for l in text.splitlines() if not l.startswith("#")]
    cols = rows[0]
    row = lambda t: dict(zip(cols, rows[1 + t]))
    assert row(5)["fps"] == "100.0" and row(15)["fps"] == "50.0" and row(33)["fps"] == ""
    assert (row(5)["focused_window"], row(5)["in_game"]) == ("steam_app_2344520", "1")
    assert (row(15)["focused_window"], row(15)["in_game"]) == ("firefox", "0")
    sessions.delete("s")
    assert not (tmp_path / "s.focus").exists()
