"""Custom theme files: validation, round-tripping through DIR, and the exported template."""
import json

import pytest

from rigdeck import customtheme

VALID = {"name": "My Theme", "window": "#101214", "panel": "#1c1e21", "raised": "#282c2f",
         "text": "#e2e5e8", "muted": "#90969c", "border": "#3a3e42", "accent": "#42a1f3"}


def test_a_valid_theme_parses():
    t = customtheme.parse(json.dumps(VALID))
    assert t["name"] == "My Theme"
    assert t["window"] == "#101214"
    assert t["dark"] is True  # a near-black window


def test_dark_is_worked_out_from_window_brightness():
    light = customtheme.parse(json.dumps({**VALID, "window": "#fcfdff"}))
    assert light["dark"] is False


def test_every_problem_is_reported_with_where_it_is():
    bad = {"name": "", "window": "not-a-color", "accent": "#42a1f3", "sparkle": True}
    with pytest.raises(customtheme.ThemeFileError) as e:
        customtheme.parse(json.dumps(bad))
    p = e.value.problems
    assert any(x.startswith("name:") for x in p)
    assert any(x.startswith("window:") for x in p)
    assert any(x.startswith("panel:") and "missing" in x for x in p)  # not in `bad` at all
    assert any("sparkle" in x for x in p)


def test_not_json_says_where():
    with pytest.raises(customtheme.ThemeFileError, match="line 1 column"):
        customtheme.parse("{not json")


def test_colors_are_normalized_to_lowercase_hash_rrggbb():
    t = customtheme.parse(json.dumps({**VALID, "accent": "FF79C6"}))
    assert t["accent"] == "#ff79c6"


def test_save_list_and_delete_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(customtheme, "DIR", str(tmp_path / "themes"))
    slug, theme = customtheme.save(json.dumps(VALID))
    assert slug == "my-theme"
    assert theme["name"] == "My Theme"

    themes = customtheme.list_themes()
    assert list(themes) == ["my-theme"]
    assert themes["my-theme"]["accent"] == "#42a1f3"

    customtheme.delete(slug)
    assert customtheme.list_themes() == {}


def test_saving_the_same_name_again_replaces_it(monkeypatch, tmp_path):
    monkeypatch.setattr(customtheme, "DIR", str(tmp_path / "themes"))
    customtheme.save(json.dumps(VALID))
    customtheme.save(json.dumps({**VALID, "accent": "#ff0000"}))
    themes = customtheme.list_themes()
    assert len(themes) == 1
    assert themes["my-theme"]["accent"] == "#ff0000"


def test_a_broken_file_on_disk_is_skipped_not_raised(monkeypatch, tmp_path):
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "broken.json").write_text("{not json")
    (themes_dir / "fine.json").write_text(json.dumps(VALID))
    monkeypatch.setattr(customtheme, "DIR", str(themes_dir))
    assert list(customtheme.list_themes()) == ["fine"]


def test_template_includes_the_given_tokens_and_a_placeholder_name():
    tokens = {k: VALID[k] for k in customtheme.TOKEN_KEYS}
    text = customtheme.template(tokens, name="Starting Point")
    data = json.loads(text)
    assert data["name"] == "Starting Point"
    assert data["window"] == VALID["window"]
    customtheme.parse(text)  # the template itself must be a valid theme file
