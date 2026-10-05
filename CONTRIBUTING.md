# Working on RigDeck

The process every change follows, from first edit to published release. It applies to people and
to AI assistants alike; the [rules for AI assistants](#rules-for-ai-assistants) at the end are the
short version.

## The flow at a glance

```
feature work ──► develop ──(CI)──► pull request develop → main ──(CI)──► merge
                                                                           │
  app users get "Update available" ◄── GitHub release vX.Y.Z ◄── release.yml: version,
                                                                 changelog, tag (automatic)
```

| Branch | What it holds | Who writes to it |
|---|---|---|
| `develop` | Work in progress. Every push runs CI. | Commits (directly, or via short-lived feature branches merged into it) |
| `main` | Exactly the latest release. Never committed to directly. | Only pull requests from `develop` (and the release workflow's `vX.Y.Z` commit) |

Every merge into `main` **becomes a public release**, and everyone
running RigDeck is offered the update. Treat a merge into `main` as shipping.

## 1. Set up

```sh
git clone git@github.com:gabriellaines/rigdeck.git
cd rigdeck
git switch develop
```

Run the code straight from the checkout (from the repository root):

```sh
python -m rigdeck --help
python -c 'from rigdeck.gui import main; main()'      # the app; add `--page gpu` etc. via sys.argv if needed
```

**The installed app does not see your changes.** `rigdeck-gui` from the app menu runs a copy in
`~/.local/share/rigdeck/venv`. To try a change in the real app, reinstall the checkout into it:

```sh
rm -rf build rigdeck.egg-info && ~/.local/share/rigdeck/venv/bin/pip install -q . && rm -rf build rigdeck.egg-info
```

## 2. Make the change

- Follow the style of the surrounding code (see *Adding hardware* in the [README](README.md) for
  how modules are structured).
- **New QML, icon or other data files** must be covered by `[tool.setuptools.package-data]` in
  `pyproject.toml`, or they're missing from installs. `scripts/check.sh` catches this.
- Never bump the version or edit release sections of `CHANGELOG.md`; the release does that (step 5).

## 3. Commit

One logical change per commit. Message format:

```
Short summary in the imperative (≤ 72 chars)

Optional body for developers: what changed and why, technical details.

Changelog: One plain sentence for users describing what they will notice
```

### Release notes and versions are automatic

There is no hand-maintained changelog and no version to bump. When `develop` is merged into
`main`, the release workflow writes the notes from the commits since the last release, **shown to
users in the app's update dialog**:

- a commit's `Changelog:` lines, if it has any — the best notes, written for users;
- otherwise its **summary line** — so write summaries a user would understand;
- nothing for commits that only touch internal files (`.github/`, `scripts/`, `tests/`, `docs/`,
  Markdown files).

`Changelog:` lines are optional but recommended when the summary is technical. Write for someone
who doesn't code: what they'll see or can now do, not how it was built. Several user-visible
effects → several lines.

| ✅ Good | ❌ Bad |
|---|---|
| `Changelog: GPU fans can now stay on when the card is cool (Zero RPM off)` | `Changelog: add zero_rpm to pmfw dict in set_fan` |
| `Changelog: The power-limit slider now shows the current limit when the page opens` | `Changelog: fix signal emission order in _got()` |

The version goes up by a **patch** (0.7.1 → 0.7.2), or a **minor** (0.7.1 → 0.8.0) when a new
hardware module (`rigdeck/modules/<name>/`) was added. To override, give any commit a
`Release: minor` or `Release: major` trailer.

Preview the next release at any time:

```sh
scripts/unreleased.sh       # the notes
scripts/release-level.sh    # patch, minor or major
```

### Other commit rules

- No AI attribution in commits or pull requests (no `Co-Authored-By: Claude …`, no "Generated
  with …" lines).
- Don't rewrite history that's already pushed.

## 4. Check and push

```sh
scripts/check.sh          # the same validations CI runs
git push origin develop
```

`scripts/check.sh` verifies: version consistency, shell scripts, Python compiles, the installed
package contains every QML/icon file, every CLI command starts, release notes exist for the
current version, and tests (once `tests/` exists). CI runs it on Python 3.11 (the oldest
supported) and the newest Python, with ShellCheck. Keep `develop` green: fix a red CI run before
doing anything else.

## 5. Release

Open a **pull request `develop → main`** on GitHub (its *Release preview* check says which version
it will publish) and, once CI is green, **merge it with a merge commit** (not squash or rebase —
that would make old release notes reappear). That's all. The Release workflow then:

1. runs the checks again,
2. picks the next version and writes its section in `CHANGELOG.md` (see *Release notes and
   versions are automatic*), commits `vX.Y.Z` to `main`,
3. tags and publishes the GitHub release, which the app offers as an update,
4. merges `main` back into `develop`, so run `git pull` there afterwards.

A merge with only internal commits still releases, with the note "Small internal improvements".

**A specific version** (e.g. 1.0.0): on `develop` run `scripts/bump-version.sh 1.0.0`, commit
`v1.0.0` and merge as above; a version with no tag yet is published as it is.

The workflow pushes to `main` and `develop` with its own token, so those branches must allow
GitHub Actions to push (no branch protection rule that blocks it).

### Urgent fixes

Same path, just faster: fix on `develop`, pull request, merge. There is
no separate hotfix branch, so `main` never drifts from `develop`.

## When something goes wrong

| Problem | What to do |
|---|---|
| Release workflow failed after the merge | Fix on `develop` → merge again, or re-run it: GitHub → Actions → Release → *Run workflow* on `main`. It does nothing when `main` is already tagged, so re-running is safe. |
| It couldn't push the version bump to `main` | A branch protection rule blocks GitHub Actions: allow it to push (Settings → Rules), then re-run. |
| Its merge back into `develop` failed (warning in the run) | `git switch develop && git pull && git merge origin/main`, fix conflicts, push. |
| A file is missing from installs | Add its pattern to `package-data` in `pyproject.toml`; `scripts/check.sh` names the file. |
| Release notes have a mistake after publishing | Edit the release text on GitHub, and fix the same section in `CHANGELOG.md` on `develop`. |

## Rules for AI assistants

When working on this repository:

1. Work on `develop` (`git switch develop`). Never commit to or push `main`; it changes only by
   merging a pull request on GitHub, which the maintainer does.
2. Write commit summaries a user would understand, and add `Changelog:` line(s) (plain sentences
   for end users) to commits with user-visible changes; they become the release notes. Internal
   commits get none. Check with `scripts/unreleased.sh`.
3. No AI attribution in commits or pull requests.
4. Run `scripts/check.sh` before committing; don't push with failing checks.
5. Don't edit the version or `CHANGELOG.md` releases by hand; the release workflow does both. Run
   `scripts/bump-version.sh` only when the maintainer asks for a specific version.
6. Before asking the maintainer to try a GUI change in the app, reinstall into
   `~/.local/share/rigdeck/venv` (step 1), or they'll be looking at the old version.
7. New data files (QML, icons) → `package-data` in `pyproject.toml`.
8. Push only when asked to. Pushing `develop` is routine; a merge into `main` publishes to all users.
