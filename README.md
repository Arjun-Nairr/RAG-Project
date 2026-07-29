# RAG Study Assistant

A retrieval-augmented generation pipeline built from scratch — upload PDFs (research papers, lecture notes, textbook chapters), and ask questions grounded in that material. Built as a learning project to understand every stage of a RAG system, not just wire together a managed service.

Every component below (chunking, embedding, retrieval, generation) is custom code, not a framework like LangChain/LlamaIndex — deliberately, so the mechanics are visible and understood rather than hidden behind an abstraction.

**Live demo:** [rag-project-dun.vercel.app](https://rag-project-dun.vercel.app) — click "✨ Try a demo" to try it with no setup. The backend runs on a free hosting tier that sleeps after 15 minutes of no traffic, so the first request after a while can take 30-50s to wake up; it recovers gracefully (a longer wait, not a failure).

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python) | async-native, standard for ML/AI services |
| Frontend | React (Vite) | component-based, standard for chat-style UIs |
| Embeddings | pluggable — local (`sentence-transformers`) or hosted (Hugging Face Inference API) | see "Local mode vs. hosted mode" below |
| Vector store | Chroma, embedded | no separate service to run, no cold-start delay, persists to disk |
| Generation | Groq (`llama-3.3-70b-versatile`) | fast free-tier hosted inference, swappable via a single interface |
| PDF parsing | `pypdf` | plain-text extraction |
| Question history | Neon (Postgres) | optional — the app runs fine without it, history just won't persist |

## Local mode vs. hosted mode

The embedding step is the one place the pipeline actually runs a neural network locally rather than calling an API, and it turned out to be expensive: loading `sentence-transformers`/`torch` costs real memory (~580MB measured peak on a small real upload) just to run one small model — enough to blow past the RAM ceiling on most free hosting tiers. Rather than pick one and lose the other, `backend/app/embedding.py` is a small dispatcher that routes to one of two interchangeable implementations based on an `EMBEDDING_PROVIDER` environment variable, so switching is a config change, not a rewrite:

- **`local`** (default, `embedding_local.py`) — runs `all-MiniLM-L6-v2` on your own machine. No API key needed beyond Groq. What you get by cloning this repo and running it as-is.
- **`huggingface`** (`embedding_huggingface.py`) — calls the *same model*, hosted via Hugging Face's Inference API. What the live deployed link runs.

Deliberately using the identical model in both cases isolates the comparison to one variable — does moving the compute off the server cost anything — rather than conflating a hosting change with a model-quality change:

| | Local | Hosted (Hugging Face) |
|---|---|---|
| Retrieval — hit rate | 100% | 100% |
| Retrieval — MRR | 0.9533 | 0.9533 (identical per-question ranks) |
| Peak RAM (real upload) | ~592.6MB (2-page excerpt, 18 chunks) | ~123.8MB (full 15-page paper, 95 chunks — a *larger* input) |
| API key required | No | Yes (free, no credit card) |

Same retrieval quality, a fraction of the memory, even measured against a larger document on the hosted side. That gap is what actually made free-tier hosting viable — not a hosting-platform workaround, a root-cause fix.

**Also evaluated and dropped:** Voyage AI was the first hosted option tried — genuinely fast (~0.32s typical latency) and a generous 200M-token free allowance, but its free tier without a payment method on file throttles to 3 requests/minute, which would cause real request failures under any concurrent traffic on the live app. `embedding_voyage.py` still exists and works (same interface, same dispatcher) but isn't what's deployed, kept as a record of the investigation rather than deleted once it stopped being the answer.

## Pipeline

```
PDF upload → text extraction → chunking → embedding → vector store index
                                                              ↓
                                          question → embed → retrieve → generate → answer
```

**Ingestion** — `pypdf` extracts raw text per page, joined into one string per document. Known limitation: tables get flattened/garbled (no structural awareness), and images are invisible entirely (text-only extraction). Not yet handled — logged as a known gap, not a hidden one.

**Chunking** — recursive splitter: tries paragraph breaks first, falls back to sentence breaks, then spaces, only going finer when a piece exceeds the size cap. Target range: 150–500 characters, with small pieces merged upward and a 50-character sentence-boundary-safe overlap between neighboring chunks (never a mid-word cut). Two real bugs were found and fixed during development: lost sentence-ending punctuation from Python's `str.split()` consuming the separator, and an overlap function that sliced through words at an arbitrary character offset instead of a sentence boundary.

**Text-quality detection** — computed once per upload, before anything gets embedded. A cheap heuristic (not an ML model) scores the extracted text on common-word density and a fused-word signal (words ≥16 characters, since PDFs that position text via glyph offsets instead of literal spaces — common with math notation or certain scanned/handwritten sources — extract with words glued together, e.g. `andisboundedbybelow`). Classifies as `ok`, `low`, or `unreadable`:
- **`unreadable`** (effectively no usable text, or a score below a hard floor) blocks asking entirely, both server- and client-side — there's nothing to search or answer from.
- **`low`** shows a dismissible warning (a real popup requiring acknowledgment, not a passive banner) but doesn't block — asking still works, and the rubric itself often self-corrects on genuinely garbled context rather than confidently hallucinating.

**Embedding** — each chunk (and each user question) is embedded with the same model (`all-MiniLM-L6-v2`, 384 dimensions — local or hosted, see above), so they live in a comparable vector space. Similarity is cosine similarity.

**Vector store** — Chroma, one collection per uploaded study set (so one user's documents never leak into another's retrieval results).

**Async upload pipeline** — uploading a study set returns immediately (`status: "uploaded"`); a background task (FastAPI `BackgroundTasks`) does the actual chunk → embed → index work, updating status to `"processing"` then `"ready"` (or `"error"`). The frontend polls for status rather than blocking on upload.

**Generation** — retrieved chunks + the question get assembled into a prompt and sent to Groq, streamed token-by-token to the frontend. Two prompt strategies exist side by side (see Evaluation below): a naive baseline (context + question, no instructions) and a rubric-guided version. The live `/ask` endpoint defaults to the rubric prompt; the naive one is kept for comparison in the eval tooling.

## Demo mode

A "✨ Try a demo" button opens a picker with three pre-selected documents, so a visitor can try the real pipeline without their own PDF:

- **Clear document** — the *Attention Is All You Need* paper, for clean, well-grounded answers.
- **Semi-clear document** — my own handwritten calculus notes (real, not synthetic), scanned to PDF with genuinely garbled text-extraction (glyph-offset fusion). Scores 0.2503 on the quality heuristic — lands correctly in the `low` bucket. A real example of exactly the failure mode the fused-word detection was built to catch.
- **Unreadable document** — a synthetic near-empty PDF, to demonstrate the hard-block path.

The picker itself is pure frontend (the three options are static — nothing about them changes at runtime), so it renders instantly regardless of whether the backend is awake. Only actually picking a document touches the backend — it goes through the exact same upload-and-process path a real PDF would, just fed from a bundled file instead of one you dragged in.

## Mobile support

Below an 820px viewport, the two-pane desktop layout (drag-resizable chat + PDF viewer) switches to a tab-based layout instead of trying to force a drag-to-resize split onto a touch screen. Both panes stay mounted underneath (toggled via CSS, not conditional rendering), so switching tabs never reloads the PDF or loses scroll position.

## Evaluation

Two separate evals, because they measure two different things and need different methodologies — retrieval correctness is objectively checkable, generation quality is not. **Both are dev-only tooling** (`backend/evals/`), run manually from the command line to validate/compare pipeline configurations — a real user's upload or question never triggers either of these; the live `/ask` endpoint does exactly one retrieval + one generation call, no eval loop involved.

### Corpus

5 papers, downloaded from arXiv, chosen for topical overlap so retrieval has to actually discriminate between them rather than trivially matching on unique vocabulary:

| File | Paper |
|---|---|
| `attention_is_all_you_need.pdf` | *Attention Is All You Need* (Vaswani et al., 2017) — arXiv:1706.03762 |
| `bert.pdf` | *BERT: Pre-training of Deep Bidirectional Transformers* (Devlin et al., 2018) — arXiv:1810.04805 |
| `rag_paper.pdf` | *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (Lewis et al., 2020) — arXiv:2005.11401 |
| `gpt3_few_shot.pdf` | *Language Models are Few-Shot Learners* (Brown et al., 2020) — arXiv:2005.14165 |
| `lora.pdf` | *LoRA: Low-Rank Adaptation of Large Language Models* (Hu et al., 2021) — arXiv:2106.09685 |

Indexed as a Chroma collection (`test_corpus`, 1,193 chunks) per embedding provider — a second collection (`test_corpus_huggingface`) was built the same way to get the hosted-mode numbers in the comparison table above, via `backend/evals/build_corpus.py` (see Eval harness below). Both are separate from the ephemeral per-upload study-set collections the live app creates.

### Models used, precisely

| Role | Model | Notes |
|---|---|---|
| Embedding (chunks + queries) | `all-MiniLM-L6-v2` — local or hosted (see above) | 384-dim, cosine similarity |
| Generation (the answer being evaluated) | `llama-3.3-70b-versatile` (Groq) | same model used by the live app |
| Judge (grading the generated answers) | `llama-3.3-70b-versatile` (Groq) | **same model as generation** — a known limitation, see below |

Using the same model as both generator and judge is a real, documented weakness (self-preference bias — a model tends to rate its own reasoning style more favorably than an independent judge would). This was one of two reasons the automated judge was ultimately abandoned in favor of a manual review (the other being Groq free-tier rate limits) — see the Generation evaluation section below. A stronger automated version would swap the judge to a model from a different lineage (e.g. `openai/gpt-oss-120b`, also available on Groq) — noted here as a known next step, not silently glossed over.

### Retrieval evaluation — hit rate + MRR

**Method:** 25 fixed test questions spanning all 5 papers in the corpus (15 phrased close to the papers' own terminology, 10 phrased the way a student would actually ask while studying — paraphrased, conceptual "why" questions, not just definitions). Each question is tagged with the source document that should be retrieved. For each question: embed it, retrieve the top-5 chunks, check whether the correct source document appears among them. Full question set: `backend/evals/eval_set.py`.

**Metrics:**
- **Hit rate** — % of questions where the correct source appeared anywhere in the top 5 results.
- **MRR (Mean Reciprocal Rank)** — average of `1/rank` of the correct source's first appearance (rewards ranking it 1st over merely being present at rank 5).

**Result:** **100% hit rate, 0.9533 MRR** (25/25 questions retrieved the correct source; 24/25 at rank 1, one at rank 3) — reproduced identically against the hosted-embedding corpus, same per-question ranks (see "Local mode vs. hosted mode" above).

Honest caveat: this is a 5-document corpus. 100% hit rate reflects that retrieval is not being asked to discriminate between hundreds of similar documents — it's a real, correctly-measured result, but the ceiling is easier to reach at this corpus size than it would be at scale.

### Generation evaluation — naive vs. rubric

Unlike retrieval, generation quality has no objective ground truth to check against, so this eval is qualitative. The methodology below reflects what was actually done, including a course-correction worth being honest about.

**What was originally built (and why it was abandoned):** a fully automated LLM-as-judge A/B — run all 25 questions through both a naive and a rubric prompt, then have a second LLM call grade every answer on two binary criteria (**grounded**: every claim supported by the retrieved context; **relevant**: actually answers the question). The code exists — `backend/evals/judge.py` (judge prompt + parsing) and `backend/evals/run_generation_eval.py` (runner) — but it was **abandoned in practice**: it needs ~100 Groq calls per run (50 generate + 50 judge), and the free tier's rate limits (30 req/min, 12k tokens/min) made a full batch unreliably slow to complete. It also had a real methodological weakness regardless of speed — the judge used the *same* model as the generator (self-preference bias; see the models table above).

**What was actually done instead:** a manual, human-in-the-loop review. Real question + retrieved-context pairs were exported **without** any generation (`qa.retrieve()` only — fast, local, no Groq quota spent), then a naive vs. rubric comparison was reviewed by hand across those cases, and the rubric was iteratively tightened based on the failures that surfaced. This traded a quantitative score for the ability to actually inspect *why* one prompt beat the other, which is what drove the rubric's final wording.

**The final rubric** (now the live default in `qa.py` — the `/ask` endpoint uses it):
1. Base the answer only on the provided context — no outside knowledge, even if the model "knows" the answer another way.
2. Some retrieved passages may be irrelevant (from an unrelated section or a different paper) — ignore any passage that doesn't actually help, even though it's in the context.
3. If the context only partially answers, answer the supported part and note what's missing; if nothing is relevant, say so instead of guessing.
4. Be concise and direct — no restating the question, no filler, no inline source citations (sources are shown separately by the app, per-chunk).

Rules 2 and 3 came directly from the manual review: one real test case retrieved an off-topic chunk from a different paper mixed into an on-topic question's context, and the naive prompt got pulled off by it — rule 2 targets exactly that. Rule 3 replaced a cruder binary "answer / say you can't" with graceful handling of *partial* coverage. Rule 4 originally asked the model to inline-cite `[filename]` after each claim; dropped after real use showed it added no value for single-source answers (the app's sources panel already shows exactly which file/chunk was used) and looked repetitive when the whole answer came from one document.

**Evidence (honest about its size):**
- One concrete before/after from the manual review — for *"How does positional encoding work in the Transformer?"*, the naive answer hallucinated (unsupported claim), while the rubric answer stayed grounded. A single data point, not a percentage.
- Live end-to-end verification on the real 5-paper corpus: asked *"Why did the Transformer get rid of recurrence?"* — retrieval came back noisy (chunks from `lora.pdf`, `gpt3_few_shot.pdf`, `bert.pdf` mixed in with the correct `attention_is_all_you_need.pdf`), and the rubric answer correctly used and cited **only** the relevant source, ignoring the off-topic chunks. Rule 2 working on a real, uncherry-picked case.
- Live on the real semi-clear demo document (genuinely garbled handwritten-notes extraction): asked "Summarize the key points" and got a coherent, accurate summary (sequences, convergence, the Squeeze Theorem) despite the underlying extracted text being fused-together and hard to read even for a human. Rules 1 and 3 holding up against messy real input, not just clean papers.

No aggregate grounded/relevant percentages are claimed for generation — that would require the automated judge that was abandoned, and inventing numbers would be dishonest. The retrieval eval above (100% / 0.9533) is the quantitative, defensible result; generation quality is supported qualitatively.

## Known limitations

- Tables and images in source PDFs are not handled — text-only extraction (see Ingestion above).
- Storage is ephemeral by design (in-memory study-set metadata, ungitignored local Chroma data) — a server restart clears uploaded study sets. Deliberate scope decision to keep the system simple while the core pipeline was being built; documented as a next step, not an oversight.
- Retrieval eval corpus is 5 documents — strong result, but not yet stress-tested at the scale where retrieval actually gets hard (hundreds+ of documents).
- SSL verification is disabled (`verify=False`) for the Groq, Hugging Face, and Voyage HTTP clients, due to this development machine's network intercepting HTTPS traffic in a way that broke standard certificate verification — a known, explicit tradeoff for local dev.

## Running locally (local embedding mode)

Clone the repo and run both halves. This uses local embedding mode by default — no API key needed beyond Groq's.

```bash
git clone https://github.com/Arjun-Nairr/RAG-Project.git
cd RAG-Project
```

**1. Backend**

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and fill in `GROQ_API_KEY` (free at [console.groq.com/keys](https://console.groq.com/keys)). `DATABASE_URL` is optional — leave it out and the app still runs, question history just won't persist across a restart. Leave `EMBEDDING_PROVIDER` unset entirely to use local mode.

```bash
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. First upload will be a bit slower than later ones — the embedding model (~80MB) loads once and stays cached in memory for the life of the process.

**2. Frontend** (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. No env vars needed for local dev — it defaults to talking to `localhost:8000`.

On Windows, `start.bat` in the repo root does both of the above in one double-click (after the one-time `.env` setup).

## Deploying (hosted mode)

The live demo runs frontend on Vercel and backend on Render, in hosted embedding mode. Env vars beyond what local mode needs:

| Var | Where | Purpose |
|---|---|---|
| `EMBEDDING_PROVIDER=huggingface` | backend host | switches the dispatcher off the local model |
| `HUGGINGFACE_API_KEY` | backend host | Hugging Face Inference API token (free, no card) |
| `FRONTEND_ORIGIN` | backend host | your deployed frontend's URL, for CORS |
| `VITE_API_BASE` | frontend host, build-time | your deployed backend's URL |

## Eval harness

```bash
cd backend
python -m evals.run_retrieval_eval [collection_name] [top_k]
python -m evals.run_generation_eval [collection_name] [top_k]   # automated judge — kept but not the final methodology (see Generation evaluation); needs Groq quota headroom to finish a full run
python -m evals.build_corpus [collection_name]                 # (re)build the eval corpus under whichever EMBEDDING_PROVIDER is active - needed once per provider, since vectors from different models can't share a collection
```
