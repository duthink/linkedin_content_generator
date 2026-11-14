# Journal

One short entry per change, newest first: the date, what changed, and why, in plain words.

- 2026-11-14: Removed the compiled Python cache files (`src/__pycache__/*.pyc`) that had been committed by mistake. They are generated automatically when the code runs, are already listed in `.gitignore`, and only cause noise in changes. Requested in issue #7.
