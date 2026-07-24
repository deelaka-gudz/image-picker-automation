# image-picker-automation

Streamlit app + CLI script that takes a list of image names, searches for them in a source folder, and copies any matches into an output folder.

- Source folder: `S:\Ammar - Anuja\Image Fetch Tool\Images`
- Output folder: `S:\Ammar - Anuja\Image Fetch Tool\Out`

Matching is case-insensitive and works whether or not you include the file extension (e.g. `IMG_0001` matches `img_0001.JPG`). The source folder is scanned recursively, including subfolders.

## Setup (Windows)

Create and activate a virtual environment, then install dependencies.

**PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If activation is blocked by the execution policy, run this once (current user only) and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Command Prompt (cmd.exe):**

```cmd
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

To leave the virtual environment later, run `deactivate`.

## Streamlit app

```bash
streamlit run app.py
```

1. Confirm the source/output folders in the sidebar (defaults to the paths above) and click **Build / Refresh index**.
2. Paste image names (one per line) or upload a `.txt`/`.csv` list.
3. Click **Search & Copy**. Results are shown in a table (found / not found / multiple matches / errors) and can be downloaded as CSV.

## Command line

```bash
python automation.py --names names.txt
python automation.py --names "IMG_0001,IMG_0002,product_photo_15"
```

Optional flags: `--source`, `--output`, `--overwrite` (overwrite files already present in the output folder).
