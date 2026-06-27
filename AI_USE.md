# AI Use

This research uses large language models (LLMs) as one component of its
methodology, alongside human coding and rule-based extraction. We disclose this
plainly: the goal is honest reporting, not avoidance.

## Where LLMs are used

LLMs are used in the *citation-context classification* stage: a deterministic
prompt + JSON schema sends each citation context to a model that returns a
structured classification. The schema, prompt, model identifier and version,
temperature, and complete prompting / parsing protocol for each release of the
method are documented in the corresponding manuscript and its supplementary
materials.

LLMs are NOT used for: corpus assembly, retrieval, deduplication, hashing,
sampling, annotation gold labels, reliability statistics, or the contents of
the public README. Those stages are deterministic and scripted.

## Where the full disclosure lives

The complete model / version / prompt / schema disclosure for each method
release lives in the respective manuscript and its supplementary materials.
This export is the *reproducibility scaffold* (corpus IDs, hashes, scripts,
annotation protocol, summary tables); it is not the methods narrative.

## What you can do with this export

You can re-fetch the corpus from the published IDs + SHA-256 hashes using the
scripts in `scripts/corpus/`, re-run the annotation pipeline with the codebook
in `docs/annotation/`, and reproduce the reliability and summary tables from
the included R helpers. Replicating the LLM classification stage requires the
prompts, schemas, and model details disclosed in the manuscript.
