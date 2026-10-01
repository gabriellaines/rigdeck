# Working on RigDeck

The process every change follows, from first edit to published release. It applies to people and
to AI assistants alike; the [rules for AI assistants](#rules-for-ai-assistants) at the end are the
short version.

## The flow at a glance

```
feature work ──► develop ──(CI)──► pull request develop → main ──(CI + version check)──► merge
                                                                                          │
         app users get "Update available" ◄── GitHub release vX.Y.Z ◄── release.yml ◄────┘
```

| Branch | What it holds | Who writes to it |
|---|---|---|
| `develop` | Work in progress. Every push runs CI. | Commits (directly, or via short-lived feature branches merged into it) |
| `main` | Exactly the latest release. Never committed to directly. | Only pull requests from `develop` |

Every merge into `main` whose version has no tag yet **becomes a public release**, and everyone
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
- Never bump the version by hand while working; that happens only at release time (step 5).

## 3. Commit

One logical change per commit. Message format:

```
Short summary in the imperative (≤ 72 chars)

Optional body for developers: what changed and why, technical details.

Changelog: One plain sentence for users describing what they will notice
```

### The `Changelog:` line — this is how release notes are made

There is no hand-maintained changelog. At release time, `scripts/bump-version.sh` collects every
`Changelog:` line since the last release into `CHANGELOG.md`, and that text becomes the GitHub
release notes, **shown to users in the app's update dialog**.

- **Add one** to every commit that changes something a user can notice: a feature, a fix, a
  visible UI change, installer behavior.
- **Add several** if the commit has several user-visible effects (one `Changelog:` line each).
- **Add none** to internal commits: refactors, CI, tests, developer docs.
- Write for someone who doesn't code: what they'll see or can now do, not how it was built.

| ✅ Good | ❌ Bad |
|---|---|
| `Changelog: GPU fans can now stay on when the card is cool (Zero RPM off)` | `Changelog: add zero_rpm to pmfw dict in set_fan` |
| `Changelog: The power-limit slider now shows the current limit when the page opens` | `Changelog: fix signal emission order in _got()` |
| `Changelog: Install with one line, no git needed` | `Changelog: misc fixes` |

Forgot one? Before pushing, `git commit --amend` adds it. After pushing, write the sentence under
`## Unreleased` in `CHANGELOG.md` instead; hand-written text there is included too.

Preview the next release's notes at any time:

```sh
scripts/unreleased.sh
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

When `develop` has something worth shipping and CI is green:

```sh
git switch develop && git pull
scripts/unreleased.sh                 # read the notes users will see; fix wording if needed
scripts/bump-version.sh X.Y.Z         # sets the version everywhere, writes CHANGELOG.md
git diff                              # review; reword CHANGELOG.md freely
git commit -am "vX.Y.Z"               # no Changelog line on this one
git push origin develop
```

Then on GitHub: **open a pull request `develop → main`** and, once CI is green, **merge it with
a merge commit** (not squash or rebase — that would make old release notes reappear). The Release
workflow runs the checks again, tags `vX.Y.Z` and publishes the release. Done.

**Choosing the version** (`MAJOR.MINOR.PATCH`):
- `PATCH` (0.3.0 → 0.3.1): fixes and small improvements only.
- `MINOR` (0.3.1 → 0.4.0): new features or new supported hardware.
- `MAJOR`: reserved for 1.0 and later breaking changes (config format, removed commands).

`bump-version.sh` refuses when the version isn't newer, or when there are no release notes
(no `Changelog:` lines and nothing under *Unreleased*).

### Urgent fixes

Same path, just faster: fix on `develop` (with a `Changelog:` line), bump the patch version,
pull request, merge. There is no separate hotfix branch, so `main` never drifts from `develop`.

## When something goes wrong

| Problem | What to do |
|---|---|
| Pull request into `main` fails *Version is new* | You forgot step 5's bump. Run `scripts/bump-version.sh`, commit, push to `develop`; the PR updates. |
| Release workflow failed after the merge | Fix on `develop` → merge again, or re-run it: GitHub → Actions → Release → *Run workflow* on `main`. It only publishes versions that have no tag yet, so re-running is safe. |
| Merged into `main` without bumping | Nothing is published (the version already has a tag). Bump on `develop` and merge again. |
| A file is missing from installs | Add its pattern to `package-data` in `pyproject.toml`; `scripts/check.sh` names the file. |
| Release notes have a mistake after publishing | Edit the release text on GitHub, and fix the same section in `CHANGELOG.md` on `develop`. |

## Rules for AI assistants

When working on this repository:

1. Work on `develop` (`git switch develop`). Never commit to or push `main`; it changes only by
   merging a pull request on GitHub, which the maintainer does.
2. Every commit with a user-visible change ends with `Changelog:` line(s): plain sentences for
   end users. Internal commits get none. Check with `scripts/unreleased.sh`.
3. No AI attribution in commits or pull requests.
4. Run `scripts/check.sh` before committing; don't push with failing checks.
5. Don't edit the version by hand. Run `scripts/bump-version.sh` only when the maintainer asks
   for a release.
6. Before asking the maintainer to try a GUI change in the app, reinstall into
   `~/.local/share/rigdeck/venv` (step 1), or they'll be looking at the old version.
7. New data files (QML, icons) → `package-data` in `pyproject.toml`.
8. Push only when asked to. Pushing `develop` is routine; a merge into `main` publishes to all users.
