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

## Step 7: Preserve metadata

Each chunk must keep track of where it came from, so answers can cite the right policy section. The logic is in [metadata.py](metadata.py) and is called from [load_pdf.py](load_pdf.py) after cleaning.

Every page (and therefore every chunk, because the text splitter copies page metadata onto its chunks) carries:

- `source`: the file name only, for example `insurance_policy.pdf` (not the local path).
- `page`: zero-based page index from the loader, and `page_label`: the human page number.
- `total_pages`.
- `policy_type`, `document_version`, `product_id` and `access_level` (the extra fields; `access_level` can later be used as a search filter for permissions).

The default values for the sample policy are set at the top of [metadata.py](metadata.py) and should be changed per document when ingesting real policies. Noisy PDF fields such as `producer` and `creationdate` are dropped to keep the stored index small.

Verified: after a test split into 20 chunks, every chunk had all of these fields.

Run it:

```powershell
python load_pdf.py
```

## Step 8: Create embeddings

**Direction note:** the diagram used Azure OpenAI embeddings, but these notes use `OpenAIEmbeddings` with an OpenAI API key. The code below follows the OpenAI version. Azure OpenAI can be swapped in later by using `AzureOpenAIEmbeddings`.

Key ideas:

- An embedding model turns text into a list of numbers (an embedding vector).
- `embed_documents()` converts a list of chunk texts into vectors.
- `embed_query()` converts the user's question into a vector for similarity search.
- Chunk vectors are stored in a vector store next to their text; at query time the question vector is compared with them to find relevant context.

Setup:

```powershell
pip install langchain-openai
pip freeze > requirements.txt
```

Put your key in a `.env` file (already ignored by git). Use [.env.example](.env.example) as the template:

```
OPENAI_API_KEY=your-key-here
```

Or set it for the current PowerShell session only:

```powershell
$env:OPENAI_API_KEY="your-key"
```

The code is in [embeddings_demo.py](embeddings_demo.py). It uses the `text-embedding-3-large` model, embeds two sample sentences and one query, and prints the first document vector and the query vector length.

Run it:

```powershell
python embeddings_demo.py
```

Without a key, `OpenAIEmbeddings` raises an error when it is created. Note: your pasted code created `embedding_model` but then called `embeddings.embed_documents(...)`, which would fail with a `NameError`; the file uses `embedding_model` throughout.
