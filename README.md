# AIAgent

A step-by-step log of how this project was set up. Commands are for Windows PowerShell, run from the project root.

**Current direction:** a RAG project over PDF policy documents (LangChain + Azure OpenAI + Azure AI Search), managed with **pip** and `requirements.txt`.

## Step 1: Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Step 2: Install RAG dependencies with pip

```powershell
pip install langchain langchain-community
pip install langchain-community pypdf
pip freeze > requirements.txt
```

To recreate the environment elsewhere:

```powershell
pip install -r requirements.txt
```

## Step 3: Load a PDF with PyPDFLoader

Put your policy PDF next to the script as `insurance_policy.pdf`. The code is in [load_pdf.py].

```powershell
pip install langchain-community pypdf
pip freeze > requirements.txt
```

Run it:

```powershell
python load_pdf.py
```

## Step 4: Sample insurance policy PDF

A fictional sample policy was generated at [insurance_policy.pdf](insurance_policy.pdf) so the pipeline has data to work with. It has 14 pages and covers:

- Definitions, scope of cover and the underwriting process (pages 1-4)
- Underwriting decision matrix by age, BMI and smoking (page 5)
- Outcomes for medical conditions such as hypertension, diabetes, asthma and cancer (page 6)
- Mental health, occupation and lifestyle underwriting (pages 7-8)
- General exclusions, waiting periods, premiums and loadings, claims (pages 9-12)
- Appeals and review of underwriting decisions (page 13) and contact details (page 14)

Verified with `python load_pdf.py`: it loads the PDF and prints page 13 (the appeals section).

## Step 5: Clean and prepare the extracted text

Before splitting, the extracted page text is cleaned so that poor extraction does not produce poor chunks. The logic is in [clean_text.py](clean_text.py) and is called from [load_pdf.py](load_pdf.py) right after loading.

What it does:

- Collapses repeated spaces and repeated blank lines, keeping paragraph breaks.
- Removes bare page numbers ("Page 3 of 14") and short lines repeated at the top or bottom of many pages (headers and footers).
- Skips empty or near-empty pages (extraction errors) and prints which pages were skipped.

What it deliberately does not touch, so policy accuracy is protected:

- Wording, capitalisation, numbers and punctuation.
- Headings and section numbers (for example "4. Underwriting Decision Matrix").
- Long lines (over 80 characters), which are treated as policy wording, never as headers or footers.
- Very short pages, which are never stripped of lines.

Verified: the sample PDF still has 14 pages after cleaning (it has no headers or footers). A synthetic test with fake headers, footers and an empty page removed only those and kept every numbered clause.

Run it:

```powershell
python load_pdf.py
```

## Step 6: Add a .gitignore

Created [.gitignore](.gitignore) so generated and sensitive files stay out of git:

- The virtual environment (`.venv/`).
- The `.env` file, which will hold Azure keys.
- Python cache (`__pycache__/`, `*.pyc`).
- Tool caches (`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`).

Check what git will track:

```powershell
git status --short
```
