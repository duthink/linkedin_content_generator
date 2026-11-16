# Journal

One short entry per change, newest first: the date, what changed, and why, in plain words.

- 2026-11-16: Rewrote `readme.md` so it matches what the tool actually does today. It now has the right install step (`pip install -r requirements.txt`), the real command-line options and defaults (video length is in minutes, not seconds; topic and type are asked for if left out), the files each run saves, how to run the tests, and a short list of known limitations (for example, `--slides` currently fails from the command line). Sections that described features the code doesn't have were removed. No app code changed. Requested in issue #9.

- 2026-11-15: Added the project's first automated tests, in a new `tests/` folder. They check config loading, the content checks, how each content type is laid out and saved to files, and the command-line tool, using a made-up API key and a fake stand-in for OpenAI so no real key or network is needed. The app's own code is unchanged. Run them with `pip install -r requirements-dev.txt` then `pytest`. Requested in issue #11.

- 2026-11-14: Removed the compiled Python cache files (`src/__pycache__/*.pyc`) that had been committed by mistake. They are generated automatically when the code runs, are already listed in `.gitignore`, and only cause noise in changes. Requested in issue #7.
