# image-picker-automation

Streamlit app + CLI script that takes a list of image names, searches for them in a source folder, and copies any matches into an output folder.

- Source folder: `\\MBC-NT01\Documents\Ammar - Anuja\Image Fetch Tool\Images`
- Output folder: `\\MBC-NT01\Documents\Ammar - Anuja\Image Fetch Tool\Out`

Matching is case-insensitive and works whether or not you include the file extension (e.g. `IMG_0001` matches `img_0001.JPG`). The source folder is scanned recursively, including subfolders.

## Setup (Windows)

Create and activate a virtual environment, then install dependencies.

**PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If activation is blocked by the execution policy, run this once (current user only) and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Command Prompt (cmd.exe):**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

To leave the virtual environment later, run `deactivate`.

## Streamlit app

```bash
streamlit run app.py --server.port 8508
```

1. Confirm the source/output folders in the sidebar (defaults to the paths above) and click **Build / Refresh index**.
2. Paste image names (one per line) or upload a `.txt`/`.csv` list.
3. Click **Search & Copy**. Results are shown in a table (found / not found / multiple matches / errors) and can be downloaded as CSV.

## Run the Streamlit app automatically at startup

Running the app via `streamlit run app.py` in a VS Code terminal ties its lifetime to VS Code — closing VS Code (or a PC restart) kills it, requiring someone to manually reopen it. `run_streamlit.bat` launches Streamlit directly from `.venv`, independent of VS Code:

```bat
@echo off
cd /d "%~dp0"
".venv\Scripts\streamlit.exe" run app.py --server.port 8508 --server.headless true
```

`--server.headless true` stops Streamlit from trying to auto-open a browser window, which wouldn't work in a non-interactive Task Scheduler session anyway.

**This does not install anything.** It assumes `.venv` already exists with `requirements.txt` already installed — see [Setup](#setup-windows) above. Run that setup once per machine; after that, the startup task just launches what's already there. If `.venv` doesn't exist yet, `.venv\Scripts\streamlit.exe` won't exist either and the task will fail silently (no console to show an error in, since it's non-interactive) — check **Last Run Result** in Task Scheduler if it doesn't come up.

### Setup steps

1. Open **Task Scheduler** → **Create Task** (not "Basic Task" — the extra options below aren't available there).
2. **General** tab:
   - Name it (e.g. `Image Picker Streamlit App`)
   - Check **Run whether user is logged on or not**
   - Set the account to your own Windows user, not `SYSTEM` (needed for access to the `\\MBC-NT01\Documents` network share)
3. **Triggers** tab → New:
   - Begin the task: **At startup** (no time/day settings needed — fires once per boot)
4. **Actions** tab → New:
   - Program/script: full path to `run_streamlit.bat` (e.g. `C:\Users\<you>\...\image-picker-automation\run_streamlit.bat`)
   - Start in: the repo folder
5. **Settings** tab: uncheck **"Stop the task if it runs longer than: 3 days"** (or set it far longer). Streamlit is meant to run indefinitely — left at the default, Task Scheduler silently kills it after 3 days.
6. Click **OK**, enter your password when prompted (Windows needs it once to store credentials for the unattended login).

Verify by restarting the PC and checking `http://localhost:8508` comes up without touching VS Code.

## Command line

```bash
python automation.py --names names.txt
python automation.py --names "IMG_0001,IMG_0002,product_photo_15"
```

Optional flags: `--source`, `--output`, `--overwrite` (overwrite files already present in the output folder).
