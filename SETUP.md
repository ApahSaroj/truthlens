# Setting up TruthLens

TruthLens checks the facts, figures and citations in a draft (for example a policy note) against official Indian
statistics and other sources, and gives you a report that highlights each sentence as supported, wrong, or "couldn't
check". You do not need an account, an API key or any programming. These steps take about 10 minutes the first time.

**Want to see a finished report first?** Open `samples/sample_report_v05.html` in the TruthLens folder by
double-clicking it. It opens in your web browser and needs no internet and no installation.

---

## Windows

### Step 1. Install Python (once)

1. Go to <https://www.python.org/downloads/> and click the yellow **Download Python 3.12** (or newer) button.
2. Open the downloaded file. On the first screen, **tick "Add python.exe to PATH"** at the bottom, then click
   **Install Now**.
3. When it says "Setup was successful", close it.

If your office laptop does not let you install programs, ask your IT team to install "Python 3.12 from python.org"
for you. Python is free and widely used.

### Step 2. Get TruthLens

1. Download the TruthLens zip file and save it somewhere easy to find, such as your Documents folder.
2. Right-click the zip file and choose **Extract All…**, then **Extract**. You now have a folder named `truthlens`
   (or similar).

### Step 3. Start TruthLens

1. Open the `truthlens` folder.
2. Double-click **`start_truthlens.bat`**.
   - If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**. (This appears for any
     file downloaded from the internet that is not a signed app.)
3. A black window opens. **The first time**, it sets TruthLens up; this needs internet and takes a few minutes. You
   will see lines of text scrolling past. That is normal.
4. Your web browser then opens the TruthLens page at `http://127.0.0.1:8765`. This page runs on your own computer;
   your draft is not uploaded anywhere else.
5. **Keep the black window open** while you use TruthLens. Close it when you are done.

Next time, just double-click `start_truthlens.bat` again. It starts in a few seconds.

### Step 4. Check a draft

- Drag your `.docx`, `.pdf`, `.txt` or `.md` file onto the page, or paste text. TruthLens first runs a **Quick
  check**, which takes a few seconds.
- **Quick check** compares your draft with the official figures TruthLens already keeps on your computer. It does not
  go on the internet. Some claims need a website to answer them; those are marked "not checked in Quick mode". That
  is not a verdict, just "not looked up yet".
- If some claims were not checked, a **Deep check (about 1 min)** button appears. Click it to look those claims up on
  the government and research websites. The claims already checked stay as they are. The page shows "Checking claims:
  12 of 48" and the time elapsed while it works.
- If a website is down during the Deep check, the yellow banner says which one, and its claims show "couldn't check".
  You can try the Deep check again later.
- Or click **Try the sample policy note** to see a check run, or **Open sample report** to see a finished report
  straight away (works without internet).
- Click any highlighted sentence to see the verdict, the evidence (with a link to the official source) and, where the
  draft is wrong, a suggested correction.
- **Download report** saves an HTML file you can share or print to PDF.

### Step 5 (optional). Keep the data up to date, add a source, report a wrong verdict

- **Update now.** At the top of the TruthLens page you will see "Last updated" with a date, and an **Update now**
  button. Click it about once a week (it needs internet and runs in the background for a minute or two; you can keep
  working). It fetches the latest government press releases, reports, Parliament answers, MoSPI and NDAP listings
  and RBI rates, so TruthLens knows about recent figures. If the date turns orange, the data is more than 7 days old.
- **Add a source.** TruthLens can also use other data services (for example the World Bank or the IMF). Ask someone
  comfortable with a command window to run, inside the TruthLens folder, `.venv\Scripts\truthlens sources add
  worldbank-wdi` (Mac/Linux: `.venv/bin/truthlens sources add worldbank-wdi`) and then `... sources test
  worldbank-wdi`. Restart TruthLens (close the black window, double-click the launcher again) to use it. Only add
  sources from people you trust. Details: `docs/PLUGINS.md`.
- **This verdict is wrong.** Under each finding there is a **This verdict is wrong** button. Choose the right
  verdict and, if you can, paste a link to the official source. It is saved on your own computer for review; it does
  not change anything by itself.

---

## Mac and Linux

1. Install Python 3.10 or later from <https://www.python.org/downloads/> (Mac) or your package manager (Linux:
   `python3` and `python3-venv`).
2. Unzip TruthLens.
3. Mac: right-click **`start_truthlens.sh`** → **Open With** → **Terminal** (the first time macOS may ask you to
   confirm). Linux: open a terminal in the folder and run `./start_truthlens.sh`.
4. The browser opens at `http://127.0.0.1:8765`. Close the terminal window to stop TruthLens.

---

## How to read the report

The top line (v0.5.3) says how many claims were checked against official data, how many of those are wrong, and how
many need a source, for example **"12 claims checked against official data · 1 wrong · 40 need a source you should
cite"**. The line under it gives the full split ("1 wrong · 11 supported · 40 couldn't check · 300 skipped").

- **Wrong (contradicted):** the official source says something different. The report names the part that failed
  (for example "2025-26 Real GDP growth: draft 7.7%, official 7.8% (revised)") and suggests a fix.
- **Partly supported:** part of the sentence is backed up, or the figure is an earlier estimate that has since been
  revised.
- **Supported:** the source says the same thing.
- **Needs a source:** TruthLens has no official dataset that covers the claim yet. **This does not mean the claim is
  wrong.** Click **Claims to cite (CSV)** to download the list, and give each one a source in your document.
- **Couldn't check:** a source did not answer during this run (or Quick mode did not ask it). Run a Deep check, or
  check those claims yourself.
- **Not a checkable fact:** a sentence that only describes a programme, its aims, duties or procedures ("The Gram
  Panchayat is responsible for operation and maintenance"); since v0.5.3 also headings and contents entries, rows of
  figures from a table, rules ("shall", "should", "must"), plans, targets and projections ("by 2030", "will be"),
  and contact details. Nothing a dataset can confirm, so they are not counted.
- **Skipped:** an opinion or recommendation ("the government should…"). If an opinion-worded sentence contains a
  checkable fact ("In my view, the fiscal deficit has been rising every year"), the fact is checked and labelled
  "contains a factual claim".

The **verified score** is the share of checked claims that are supported (couldn't-check claims are not counted).
A yellow banner lists any source that could not be reached during the run, and how many claims that affected.
Evidence marked **"unverified source"** comes from a source that has never answered our test network, so it has only
been tested on made-up sample data (data.gov.in, Semantic Scholar, Shodhganga); open the link and confirm it.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| "Python is not installed" | Do Step 1, making sure "Add python.exe to PATH" is ticked. If you already installed Python, restart the computer and try again. |
| "pip is not recognized" or pip is blocked by your organisation | You do not need pip on its own: the launcher always uses `python -m pip`, which works where `pip.exe` is blocked. If you type commands yourself, write `python -m pip install …` instead of `pip install …`. |
| "The install did not finish" | Usually no internet or a proxy blocking `pypi.org`. Try on another network, or ask IT to allow `pypi.org` and `files.pythonhosted.org`. The sample report opens anyway. |
| The browser did not open | Open your browser and go to `http://127.0.0.1:8765` yourself. |
| "Address already in use" | TruthLens is already running in another black window. Use that one, or close it and start again. |
| Many claims show "couldn't check" | You may be offline, or an official website was down. The banner at the top says which. Run the check again later. |
| Windows blocks the `.bat` file | Right-click it → **Properties** → tick **Unblock** → **OK**, then double-click again. |

---

## Optional extras

None of these are needed.

- **Your own AI key (Anthropic or OpenAI):** sharper verdicts on sentences without numbers. On the TruthLens page,
  open "Optional: your own AI key…", choose the provider and paste the key. It is used for that one check only and is
  never stored.
- **data.gov.in key:** lets TruthLens read rows from data.gov.in resources you map yourself. Paste it in the same
  box. Untested: data.gov.in has never answered our test network. (Versions before v0.5.3 also asked for an "NDAP
  token"; that was never verified and has been removed.)
- **Command line, for those who want it** (in the TruthLens folder, after the launcher has run once):

  ```
  .venv\Scripts\python -m truthlens.cli check mydraft.docx -f html -o report.html      (Windows)
  .venv/bin/python -m truthlens.cli check mydraft.docx -f html -o report.html          (Mac/Linux)
  .venv\Scripts\python -m truthlens.cli doctor                                         (which sources are active)
  ```

- **Older launchers** (`Start TruthLens (Windows).bat`, `start-truthlens.sh`) still work the same way.

TruthLens is a checking aid, not an authority. Open the linked source before relying on a verdict.
