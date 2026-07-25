# RAG Study Assistant

A retrieval-augmented generation pipeline built from scratch — upload PDFs (research papers, lecture notes, textbook chapters), and ask questions grounded in that material. Built as a learning project to understand every stage of a RAG system, not just wire together a managed service.

Every component below (chunking, embedding, retrieval, generation) is custom code, not a framework like LangChain/LlamaIndex — deliberately, so the mechanics are visible and understood rather than hidden behind an abstraction.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python) | async-native, standard for ML/AI services |
| Frontend | React (Vite) | component-based, standard for chat-style UIs |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), local | free, private, no API cost — runs on CPU |
| Vector store | Chroma, embedded | no separate service to run, no cold-start delay, persists to disk |
| Generation | Groq (`llama-3.3-70b-versatile`) | fast free-tier hosted inference, swappable via a single interface |
| PDF parsing | `pypdf` | plain-text extraction |

## Pipeline

```
PDF upload → text extraction → chunking → embedding → vector store index
                                                              ↓
                                          question → embed → retrieve → generate → answer
```

**Ingestion** — `pypdf` extracts raw text per page, joined into one string per document. Known limitation: tables get flattened/garbled (no structural awareness), and images are invisible entirely (text-only extraction). Not yet handled — logged as a known gap, not a hidden one.

**Chunking** — recursive splitter: tries paragraph breaks first, falls back to sentence breaks, then spaces, only going finer when a piece exceeds the size cap. Target range: 150–500 characters, with small pieces merged upward and a 50-character sentence-boundary-safe overlap between neighboring chunks (never a mid-word cut). Two real bugs were found and fixed during development: lost sentence-ending punctuation from Python's `str.split()` consuming the separator, and an overlap function that sliced through words at an arbitrary character offset instead of a sentence boundary.

**Embedding** — each chunk (and each user question) is embedded with the same local model (`all-MiniLM-L6-v2`, 384 dimensions), so they live in a comparable vector space. Similarity is cosine similarity.

**Vector store** — Chroma, one collection per uploaded study set (so one user's documents never leak into another's retrieval results).

**Async upload pipeline** — uploading a study set returns immediately (`status: "uploaded"`); a background task (FastAPI `BackgroundTasks`) does the actual chunk → embed → index work, updating status to `"processing"` then `"ready"` (or `"error"`). The frontend polls for status rather than blocking on upload.

**Generation** — retrieved chunks + the question get assembled into a prompt and sent to Groq. Two prompt strategies exist side by side (see Evaluation below): a naive baseline (context + question, no instructions) and a rubric-guided version. The live `/ask` endpoint defaults to the rubric prompt; the naive one is kept for comparison in the eval tooling.

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

Indexed as a single Chroma collection (`test_corpus`, 1,193 chunks total) — separate from the ephemeral per-upload study-set collections the live app creates.

### Models used, precisely

| Role | Model | Notes |
|---|---|---|
| Embedding (chunks + queries) | `all-MiniLM-L6-v2` (`sentence-transformers`, local) | 384-dim, cosine similarity |
| Generation (the answer being evaluated) | `llama-3.3-70b-versatile` (Groq) | same model used by the live app |
| Judge (grading the generated answers) | `llama-3.3-70b-versatile` (Groq) | **same model as generation** — a known limitation, see below |

Using the same model as both generator and judge is a real, documented weakness (self-preference bias — a model tends to rate its own reasoning style more favorably than an independent judge would). This was one of two reasons the automated judge was ultimately abandoned in favor of a manual review (the other being Groq free-tier rate limits) — see the Generation evaluation section below. A stronger automated version would swap the judge to a model from a different lineage (e.g. `openai/gpt-oss-120b`, also available on Groq) — noted here as a known next step, not silently glossed over.

### Retrieval evaluation — hit rate + MRR

**Method:** 25 fixed test questions spanning all 5 papers in the corpus (15 phrased close to the papers' own terminology, 10 phrased the way a student would actually ask while studying — paraphrased, conceptual "why" questions, not just definitions). Each question is tagged with the source document that should be retrieved. For each question: embed it, retrieve the top-5 chunks, check whether the correct source document appears among them. Full question set: `backend/evals/eval_set.py`.

**Metrics:**
- **Hit rate** — % of questions where the correct source appeared anywhere in the top 5 results.
- **MRR (Mean Reciprocal Rank)** — average of `1/rank` of the correct source's first appearance (rewards ranking it 1st over merely being present at rank 5).

**Result:** **100% hit rate, 0.9533 MRR** (25/25 questions retrieved the correct source; 24/25 at rank 1, one at rank 3).

Honest caveat: this is a 5-document corpus. 100% hit rate reflects that retrieval is not being asked to discriminate between hundreds of similar documents — it's a real, correctly-measured result, but the ceiling is easier to reach at this corpus size than it would be at scale.

### Generation evaluation — naive vs. rubric

Unlike retrieval, generation quality has no objective ground truth to check against, so this eval is qualitative. The methodology below reflects what was actually done, including a course-correction worth being honest about.

**What was originally built (and why it was abandoned):** a fully automated LLM-as-judge A/B — run all 25 questions through both a naive and a rubric prompt, then have a second LLM call grade every answer on two binary criteria (**grounded**: every claim supported by the retrieved context; **relevant**: actually answers the question). The code exists — `backend/evals/judge.py` (judge prompt + parsing) and `backend/evals/run_generation_eval.py` (runner) — but it was **abandoned in practice**: it needs ~100 Groq calls per run (50 generate + 50 judge), and the free tier's rate limits (30 req/min, 12k tokens/min) made a full batch unreliably slow to complete. It also had a real methodological weakness regardless of speed — the judge used the *same* model as the generator (self-preference bias; see the models table above).

**What was actually done instead:** a manual, human-in-the-loop review. Real question + retrieved-context pairs were exported **without** any generation (`qa.retrieve()` only — fast, local, no Groq quota spent), then a naive vs. rubric comparison was reviewed by hand across those cases, and the rubric was iteratively tightened based on the failures that surfaced. This traded a quantitative score for the ability to actually inspect *why* one prompt beat the other, which is what drove the rubric's final wording.

**The final rubric** (now the live default in `qa.py` — the `/ask` endpoint uses it):
1. Base the answer only on the provided context — no outside knowledge, even if the model "knows" the answer another way.
2. Some retrieved passages may be irrelevant (from an unrelated section or a different paper) — ignore any passage that doesn't actually help, even though it's in the context.
3. If the context only partially answers, answer the supported part and note what's missing; if nothing is relevant, say so instead of guessing.
4. Cite the source document per claim as `[filename]`; be concise — no restating the question, no filler.

Rules 2 and 3 came directly from the manual review: one real test case retrieved an off-topic chunk from a different paper mixed into an on-topic question's context, and the naive prompt got pulled off by it — rule 2 targets exactly that. Rule 3 replaced a cruder binary "answer / say you can't" with graceful handling of *partial* coverage.

**Evidence (honest about its size):**
- One concrete before/after from the manual review — for *"How does positional encoding work in the Transformer?"*, the naive answer hallucinated (unsupported claim), while the rubric answer stayed grounded. A single data point, not a percentage.
- Live end-to-end verification on the real 5-paper corpus: asked *"Why did the Transformer get rid of recurrence?"* — retrieval came back noisy (chunks from `lora.pdf`, `gpt3_few_shot.pdf`, `bert.pdf` mixed in with the correct `attention_is_all_you_need.pdf`), and the rubric answer correctly used and cited **only** the relevant source, ignoring the off-topic chunks. Rule 2 working on a real, uncherry-picked case.

No aggregate grounded/relevant percentages are claimed for generation — that would require the automated judge that was abandoned, and inventing numbers would be dishonest. The retrieval eval above (100% / 0.9533) is the quantitative, defensible result; generation quality is supported qualitatively.

## Known limitations

- Tables and images in source PDFs are not handled — text-only extraction (see Ingestion above).
- Storage is ephemeral by design (in-memory study-set metadata, ungitignored local Chroma data) — a server restart clears uploaded study sets. Deliberate scope decision to keep the system simple while the core pipeline was being built; documented as a next step, not an oversight.
- Retrieval eval corpus is 5 documents — strong result, but not yet stress-tested at the scale where retrieval actually gets hard (hundreds+ of documents).
- SSL verification is disabled for the Groq client (`verify=False`) due to this development machine's network intercepting HTTPS traffic in a way that broke standard certificate verification — a known, explicit tradeoff for local dev, not appropriate for a production deployment talking to arbitrary hosts.

## Running locally

```bash
# backend
cd backend
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in your GROQ_API_KEY
uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev
```

## Eval harness

```bash
cd backend
python -m evals.run_retrieval_eval [collection_name] [top_k]
python -m evals.run_generation_eval [collection_name] [top_k]   # automated judge — kept but not the final methodology (see Generation evaluation); needs Groq quota headroom to finish a full run
```
