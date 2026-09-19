# Local engineering knowledge base

The five supplied Markdown documents were compared with `references/` on
2026-09-19. Their text matches the existing copies after CRLF/LF normalisation;
no duplicate copies or changes to the originals were necessary.

Indexed sources include:

- `references/ACV/ACV_Subsystem_Info_Kit.md`
- `references/Door/Door_Subsystem_Info_Kit.md`
- `references/Door/Door Data Headers.md`
- `references/Rail_Corrugation/Rail_Corrugation_Info_Kit.md`
- `references/SHM/SHM_Info_Kit.md`
- The explicit implementation/reference allowlist in `assistant/service.py`.

## Retrieval design

`assistant/knowledge.py` creates heading-aware, bounded passages with source file,
section, exact line range and a SHA-256 of normalised source text. Large blocks
are split instead of discarded. Formulas and tables remain source text. Images
linked by Markdown are not indexed or fetched.

Search combines TF-IDF word/bigram cosine similarity (70%) and local latent
semantic analysis vectors (30%, at most 32 dimensions, fixed seed). Reviewed
query expansions connect DCSR/DLSL to switch names, S–N to stress-life, ripples
to corrugation, and related terminology. Keyword anchors and minimum relevance
thresholds prevent arbitrary nearest-neighbour matches. Subsystem filters are
applied before selecting the returned top four. General implementation docs may
be relevant across subsystems. Scores measure relevance, never confidence.

This is **LSA semantic retrieval, not pretrained neural sentence embeddings**.
It uses the existing scikit-learn runtime: no vector-database service, new dependency,
API key, remote embedding request or model download. See the official
[TruncatedSVD documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html)
for the underlying LSA method. Vocabulary expansions and the small corpus limit
paraphrase coverage; this is not unrestricted scientific question answering.

The index is lazily cached in process (maximum four corpus versions), keyed by
source content rather than mtime. Editing/removing an allowlisted file invalidates
the next request's index automatically. There are no pickled indexes or writable
model artifacts. Only static reference text is cached—not user recordings, keys,
notes or conversation history. Symlinks, paths outside the repository and files
above 2 MB are refused. Missing/unreadable sources produce visible warnings.

## Agent and dashboard integration

Definition requests first use `assistant/terminology.py`, not approximate passage
ranking. This index extracts explicit full-name/acronym pairs in either direction
and glossary table rows from allowlisted reference text, checking that expansion
initials match the acronym. Each entry retains its defining quote, source hash and
line range. Both the acronym and full name are lookup aliases. Source removal also
removes its definitions; expansions are not guessed from filenames or repeated mentions.

Exact documented terms (SHM, ACV and the Door switch abbreviations) return the same
short answer with or without an API key. These requests do not invoke the provider,
and the UI labels them **Verified definition**. Existing reviewed glossary templates
remain available for other concepts. Unknown acronym expansions explicitly abstain;
conflicting expansions require scope or clarification. Mixed operational requests
still pass through safety checks. This is conservative pattern extraction, not a
claim that every possible definition in prose is automatically understood.

The assistant calls `search_reference_docs(question, subsystem)` for reference
questions and supplements reviewed glossary answers with relevant passages.
Physics explanations are routed to documentation rather than asking for a
recording merely because the question starts with “why”. Ambiguous intent still
clarifies, and operational claims still hit the existing safety/data boundaries.

The read-only tool endpoint is:

```http
POST /api/assistant/knowledge/search
Content-Type: application/json

{"question":"What does DCSR mean?","subsystem":"door"}
```

It returns passages, citation metadata, relevance details, corpus hash and warnings.
It accepts no file paths, API keys or arbitrary tool instructions, and makes no
external requests. The same localhost/origin restrictions as the prototype apply;
production deployment still requires authentication and session ownership.

No-key answers show a focused extract: an exact matching glossary/table row when
available, otherwise one relevant complete paragraph from the top passage.
Adjacent tables, JSON/code blocks and other retrieved passages stay in expandable
source evidence. Ordinary source caveats are collapsed there; the SHM theoretical
threshold warning remains visible. Provider failures use the same compact fallback.
This is deterministic extraction, not an LLM-generated summary.
With provider consent, only retrieved text
and its caveats enter the existing cited-explanation adapter; raw files are not
uploaded. Document content is untrusted reference data, never executable policy.
Canonical prediction/validation records remain separate from background theory.
AI paraphrases still require source verification; structural/numeric checks cannot
prove semantic correctness. The API context reports the active retrieval version,
document count and passage count. Restart the backend after this code update.

## Source caveats

- SHM's idealised Miner failure criterion is not an approved threshold for the
  fitted proxy, and does not establish remaining life. AW0/AW4 are named but not
  defined in the kit; the assistant must not invent their definitions from it.
- Rail's scoring narrative has inconsistent approximate training counts and an
  illustrative all-Normal F1 of 1.0. Use the dataset section/verified labels and
  actual metric calculations instead of those illustrative statements.
- The Door glossary includes identifier fields beyond the released 17-column
  stream. It is not authority to change the loader schema. Its reference to other
  subsystems' “plain accuracy” is not their actual scoring contract.
- ACV industry percentages are attributed background claims, not replay findings
  or calibrated fault probabilities.

These caveats accompany retrieved evidence and are included in provider context.
The index does not silently rewrite source files to hide their inconsistencies.

## Verification

`tests/test_assistant_knowledge.py` covers all five sources, top-hit relevance on
seven terminology/physics queries, source-line integrity, unknown-query abstention,
subsystem isolation, cache invalidation, symlink rejection, long blocks, provider
payload separation and operational boundaries. API tests cover the read-only tool
and reject arbitrary paths/oversized requests. This regression set is not a broad
semantic-retrieval benchmark; extend it with engineers' real questions over time.
