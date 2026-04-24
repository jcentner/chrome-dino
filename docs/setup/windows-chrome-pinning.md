# Pinning Chrome + ChromeDriver on Windows for chrome-dino

This is a one-time-per-workstation setup. Done once, slice-1+ eval runs are
reproducible against a fixed Chrome version that does not auto-update.

> **Why pin?** AC-DEPLOYABILITY requires the eval to be re-runnable on a fresh
> Windows machine. The user's daily-driver Chrome auto-updates, which makes
> any `chrome://dino` evaluation non-reproducible across days. We install a
> dedicated `chrome-for-testing` build at `C:\chrome-dino-runtime\` and refuse
> to run against anything else.

## Pinned versions

> **OPERATOR: fill these in after running the install steps below.**

| Field | Value |
|---|---|
| Chrome version (full) | `148.0.7778.56` |
| Chrome major version | `148` |
| Chrome SHA256 | `1BCB7A338AEEB27DFECE8B46E4ADEA6C7DB4E5A32430679F550FFF6F0D7A7CAC` |
| ChromeDriver version (full) | `148.0.7778.56` |
| ChromeDriver SHA256 | `E6D398D25FFC997C92EFD90B93A2C1FCE5F9D9DCC7553A17039B5D631A75AA88` |
| Date pinned | 2026-04-23 |
| Pinned by | jakce |

> Note: `chrome.exe --version` returned blank on Windows for this Chrome-for-Testing build. Version was confirmed via `chromedriver.exe --version` (versions are paired in the chrome-for-testing release row) and via `navigator.userAgent` at runtime — `Browser.version_check()` enforces the major against `PINNED_CHROME_MAJOR` on every eval.

After filling these in, also set `PINNED_CHROME_MAJOR` in
[`src/browser.py`](../../src/browser.py) to the major number above.

## Install steps

1. Open <https://googlechromelabs.github.io/chrome-for-testing/> and pick the
   current Stable row. Note the full version string (e.g. `137.0.7151.55`).
   Both `chrome` and `chromedriver` for `win64` are needed.
2. Run the PowerShell block below in `pwsh` (replace `$VER`):

   ```powershell
   $VER = "PASTE_VERSION_HERE"
   $RUNTIME = "C:\chrome-dino-runtime"
   New-Item -ItemType Directory -Force $RUNTIME | Out-Null

   $CHROME_URL = "https://storage.googleapis.com/chrome-for-testing-public/$VER/win64/chrome-win64.zip"
   $DRIVER_URL = "https://storage.googleapis.com/chrome-for-testing-public/$VER/win64/chromedriver-win64.zip"

   Invoke-WebRequest $CHROME_URL -OutFile "$RUNTIME\chrome-win64.zip"
   Invoke-WebRequest $DRIVER_URL -OutFile "$RUNTIME\chromedriver-win64.zip"

   Expand-Archive "$RUNTIME\chrome-win64.zip" -DestinationPath $RUNTIME -Force
   Expand-Archive "$RUNTIME\chromedriver-win64.zip" -DestinationPath $RUNTIME -Force

   # Copy chromedriver into the repo (chromedriver/ is gitignored except .gitkeep):
   Copy-Item "$RUNTIME\chromedriver-win64\chromedriver.exe" `
             "$PSScriptRoot\..\..\chromedriver\chromedriver.exe" -Force
   ```

3. Capture SHA256s and the runtime-reported versions, then paste them into the
   table at the top of this file:

   ```powershell
   $CHROME_EXE = "$RUNTIME\chrome-win64\chrome.exe"
   $DRIVER_EXE = "$RUNTIME\chromedriver-win64\chromedriver.exe"

   (Get-FileHash $CHROME_EXE -Algorithm SHA256).Hash
   (Get-FileHash $DRIVER_EXE -Algorithm SHA256).Hash
   & $CHROME_EXE --version
   & $DRIVER_EXE --version
   ```

4. Edit `src/browser.py` and set `PINNED_CHROME_MAJOR` to the major version
   (the `137` in `137.0.7151.55`).

5. Smoke-test: un-skip `test_one_short_episode` in `tests/test_browser.py`
   (remove the `@pytest.mark.skip` decorator, keep `@pytest.mark.browser`),
   then:

   ```powershell
   .venv\Scripts\python.exe -m pytest -m browser -q
   ```

   Expect: one test passes; a Chrome window briefly opens, plays ~100
   heuristic steps, and closes.

## Re-pinning

Treat re-pinning as a phase-level event:

- Bump the pinned version in this file.
- Update `PINNED_CHROME_MAJOR` in `src/browser.py` if the major changed.
- Re-run AC-HARNESS (5-episode manual spot-check) to confirm score readout
  still exact-matches the page's displayed score under the new version.
- Note the change in `roadmap/CURRENT-STATE.md` `## Context` — eval artifacts
  produced before and after the re-pin should not be combined into a single
  MET claim without the spot-check confirming continuity.
