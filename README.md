<div align="center">

# 📋 Leave Policy Assistant

### An HR assistant that answers from **one leave policy** — and cites the section every time.

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Tests](https://img.shields.io/badge/tests-86_passing-0F7A4F?style=for-the-badge&logo=pytest&logoColor=white)](#-tests)
[![Setup](https://img.shields.io/badge/setup-one_command-054F9F?style=for-the-badge)](#-run-it)

</div>

---

> [!IMPORTANT]
> **One command to run it. No API key, no account, no configuration file.**
> `python run.py` builds its own virtual environment on the first run, and the policy text is read
> on your own machine, so nothing leaves it and there is nothing for you to supply.

---

## 🚀 Run it

**You need:** Python **3.9 or newer**, and `git`. Nothing else.

### Step 0 — Do you have Python?

```bash
python3 --version
```

If that prints `Python 3.9` or higher, skip to Step 1. If it says *command not found*, install it:

| 💻 Operating system | Install command |
| :--- | :--- |
| 🍎 **macOS** (with [Homebrew](https://brew.sh)) | `brew install python` |
| 🍎 **macOS** (no Homebrew) | Download the installer from [python.org/downloads](https://www.python.org/downloads/) |
| 🪟 **Windows** | `winget install -e --id Python.Python.3.12` |
| 🪟 **Windows** (no winget) | Download from [python.org/downloads](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** |
| 🐧 **Ubuntu / Debian** | `sudo apt update && sudo apt install python3 python3-venv python3-pip` |
| 🐧 **Fedora / RHEL** | `sudo dnf install python3 python3-pip` |
| 🐧 **Arch** | `sudo pacman -S python python-pip` |

> [!WARNING]
> On **Ubuntu and Debian**, `python3-venv` is a separate package and is easy to miss. Without it the
> app cannot build its environment. The command in the table above installs it for you.

### Step 1 — Clone the repository

```bash
git clone https://github.com/Rakib-cloud/AI-Solution-Specialist-Home-Assessment-Reneta-PLC.git
```

### Step 2 — Go into the folder

```bash
cd AI-Solution-Specialist-Home-Assessment-Reneta-PLC
```

### Step 3 — Start it

| 💻 Your system | Command |
| :--- | :--- |
| 🍎 **macOS** / 🐧 **Linux** | `python3 run.py` |
| 🪟 **Windows** | `python run.py` |

> [!WARNING]
> macOS and most Linux systems have **no `python` command, only `python3`**. If you see
> `command not found: python`, that is all this is — run `python3 run.py` instead.

**That is the whole setup.** There is no separate install step, because `run.py` does it for you.
On the first run it:

| | What happens | Takes |
| :--- | :--- | :--- |
| **1** | Creates a virtual environment in `.venv` | a few seconds |
| **2** | Installs everything in `requirements.txt` into it | about a minute |
| **3** | Hands over to that environment and starts the app | instant |

You will see this:

```
Creating a virtual environment in .venv ...
Installing dependencies, this takes a minute the first time ...
Starting the app ...

  Leave Policy Assistant  ->  http://127.0.0.1:5050
```

> [!NOTE]
> Steps 1 and 2 only happen once. **Every later run starts in about a second**, because `run.py`
> checks the environment first and skips straight to the app.

### Step 4 — Open it in your browser

### 👉 **http://127.0.0.1:5050**

> [!TIP]
> The sample leave policy is **already loaded and published**, so there is nothing to upload first.
> Open **Assistant**, click the policy chip at the top to select it, and start asking.

<details>
<summary><b>Prefer to set the environment up yourself?</b></summary>

<br>

Set `SKIP_BOOTSTRAP=1` and `run.py` will not touch your environment:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
SKIP_BOOTSTRAP=1 python run.py     # `python` works here, the venv provides it
```

</details>

<details>
<summary><b>Optional settings</b> — only to change the port or the secret key</summary>

<br>

Every setting has a working default, so this is **not** required. To override one, create a `.env`
file next to `run.py`:

```bash
FLASK_SECRET_KEY=any-long-random-string
PORT=5050
```

</details>

---

## ✅ Check the three requirements

On the **Assistant** page, click the tags above the message box, or type these three questions.

| # | Ask this | What should happen |
| :--- | :--- | :--- |
| **1️⃣** | *How many casual leave days do I get in a year?* | **Casual Leave: 8 working days per year. It is paid.** — shown with **Section 4.0** and **Section 4.2** as the source |
| **2️⃣** | *Can I take study leave?* | exactly `I don't know, please contact HR.` — **with no citation** |
| **3️⃣** | *How many leave days has Rahim taken?* | a **polite refusal** that points to HR and cites **Section 9**, the confidentiality section |

> [!NOTE]
> The tags on that page cover more cases, including *"Why is my colleague on medical leave?"*.
> **Hover a tag** to read the full question before you send it.

---

## 🧠 How it works

The PDF is split into **numbered sections**, and its entitlements table is read separately. A question
is matched against those sections, and the matching sentences come back with the section number.

**Three checks run before any answer reaches the screen:**

| Check | Rule |
| :--- | :--- |
| 🔖 **Citation** | The answer must name a section that exists. *No section, no answer.* |
| 🔢 **Figures** | Every number in the answer must appear in the policy, so a figure **cannot be invented**. |
| 🔒 **Privacy** | A question about another person is refused **before any lookup happens**. |

**Two decisions worth calling out:**

- **The subject of a question must be in the policy.** *"Can I take leave for jury duty?"* shares the
  words *leave* and *take* with the document, but *jury duty* is nowhere in it — so the reply is
  `I don't know`.
- **Where the checks disagree, the assistant says it does not know.** A missed answer is cheaper than
  a confident wrong one.

---

## 🧪 Tests

`run.py` builds the environment but does not activate it in your shell, so call pytest from inside
`.venv`:

```bash
.venv/bin/pytest                              # 86 tests
.venv/bin/pytest tests/test_requirements.py   # the three required behaviours, 69 questions
```

On Windows that is `.venv\Scripts\pytest`. If you would rather activate the environment first:

```bash
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pytest
```

`tests/test_requirements.py` runs against the sample policy and covers **in-policy questions paired
with the section each answer must cite**, **questions the policy does not cover**, and **requests for
another employee's data**.

A failure names the question and what came back, so a wrong citation reads as:

```
'Who can see my leave records?' cited ['4.3'], expected 9.2
```

---

## 🗂️ Managing policies

**Policies** lists every policy with its number, version and status, plus a search box and a status
filter. Row icons **view**, **edit**, **download**, **publish**, **hand to the assistant** or
**delete** — publishing and deleting ask for confirmation first.

**Create policy** builds a new one in three steps: *pick the template → fill the header → set the
leave types*. The editor then opens **one section at a time**. A new policy is marked
**`Not saved yet`** until you press **Save draft**.

---

## 📁 Project layout

```
app/routes.py                 upload, policy editor, and questions
app/services/extractor.py     PDF text, sections, and tables
app/services/reader.py        finds the answer in the policy text
app/services/grounded.py      citation, figure, and privacy checks
app/services/authored.py      draft, publish, and section numbering
app/services/pdf_export.py    policy PDF in the sample layout
app/templates/, app/static/   pages, styles, and scripts
tests/test_requirements.py    the three required behaviours
run.py                        start the app
```

---

## ⚠️ Known limitation

The assistant **matches the words** of a question against the words of the policy — it does not
understand them. Where a question uses vocabulary the policy never uses, it answers `I don't know`
even though the fact is in the document. Synonyms are handled by a small table in
`services/reader.py`, which has to be maintained by hand rather than generalising on its own.

**With more time** I would replace the matcher with **sentence embeddings** over the same sections,
and keep the three checks unchanged. They are what make the answers trustworthy, and they do not
depend on how the passages are found.

---

## 🛠️ If something goes wrong

| What you see | What it means | Fix |
| :--- | :--- | :--- |
| `command not found: python` | macOS and Linux only ship `python3` | Run `python3 run.py` |
| `No module named venv` | Debian and Ubuntu split this into its own package | `sudo apt install python3-venv` |
| `Address already in use` | Port 5050 is taken | `PORT=5051 python3 run.py` |
| `pytest: command not found` | The environment is not activated in your shell | Use `.venv/bin/pytest` |

Deleting the `.venv` folder is safe at any time. The next run rebuilds it.

---

## 📝 Notes

- The sample policy is a **dummy document** created for this assessment. Please do not upload real
  employee or company data into the app.
- A **scanned PDF with no text layer is rejected**. This app reads the text inside the file; it does
  not run OCR.
- Uploading a different policy starts a **fresh analysis**. Earlier questions are not reused as facts.
