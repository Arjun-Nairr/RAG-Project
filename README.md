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

**Generation** — retrieved chunks + the question get assembled into a prompt and sent to Groq. Two prompt strategies exist side by side (see Evaluation below): a naive baseline (context + question, no instructions) and a rubric-guided version.

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

Using the same model as both generator and judge is a real, documented weakness (self-preference bias — a model tends to rate its own reasoning style more favorably than an independent judge would). The honest framing: these generation-eval numbers are a first-pass signal, not a rigorously validated one. A stronger version of this eval would swap the judge to a model from a different lineage (e.g. `openai/gpt-oss-120b`, also available on Groq) — noted here as a known next step, not silently glossed over.

### Retrieval evaluation — hit rate + MRR

**Method:** 25 fixed test questions spanning all 5 papers in the corpus (15 phrased close to the papers' own terminology, 10 phrased the way a student would actually ask while studying — paraphrased, conceptual "why" questions, not just definitions). Each question is tagged with the source document that should be retrieved. For each question: embed it, retrieve the top-5 chunks, check whether the correct source document appears among them. Full question set: `backend/evals/eval_set.py`.

**Metrics:**
- **Hit rate** — % of questions where the correct source appeared anywhere in the top 5 results.
- **MRR (Mean Reciprocal Rank)** — average of `1/rank` of the correct source's first appearance (rewards ranking it 1st over merely being present at rank 5).

**Result:** **100% hit rate, 0.9533 MRR** (25/25 questions retrieved the correct source; 24/25 at rank 1, one at rank 3).

Honest caveat: this is a 5-document corpus. 100% hit rate reflects that retrieval is not being asked to discriminate between hundreds of similar documents — it's a real, correctly-measured result, but the ceiling is easier to reach at this corpus size than it would be at scale.

### Generation evaluation — LLM-as-judge, naive vs. rubric

**Method:** the same 25 questions, run twice — once through a naive prompt (just the retrieved context and the question, no instructions), once through a rubric-guided prompt. Every generated answer is then scored by a second LLM call (the judge — see model table above) against two binary criteria. Judge prompt and parsing logic: `backend/evals/judge.py`. Comparison runner: `backend/evals/run_generation_eval.py`.

Criteria the judge is explicitly instructed to check, verbatim from the judge prompt:

- **Grounded** — true if every factual claim in the answer is supported by the retrieved context; false if the answer includes information not present in the context, or makes claims the context doesn't support. This is the core RAG-specific failure mode (hallucination) — an answer can be well-written and still fail this.
- **Relevant** — true if the answer actually addresses the question asked; false if it's off-topic, evasive, or doesn't engage with the question.

**The rubric being tested** (four rules, given to the model as explicit instructions before the naive baseline is run again with them added):
1. Base the answer only on the provided context — no outside knowledge, even if the model "knows" the answer another way.
2. If the context doesn't contain the answer, say so explicitly instead of guessing.
3. Attribute claims to their source document.
4. Be concise — no restating the question, no filler.

**Result:** _pending — being run now, will be filled in below._

| Prompt style | Grounded | Relevant |
|---|---|---|
| Naive (baseline) | TBD | TBD |
| Rubric | TBD | TBD |

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
python -m evals.run_generation_eval [collection_name] [top_k]
```
