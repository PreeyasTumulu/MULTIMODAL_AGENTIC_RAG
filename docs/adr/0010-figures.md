# ADR-010: Figures — triage by kind, describe, index beside the text

- **Status:** Proposed — accepted once notebook 16 has run in full
- **Date:** 2026-09-12
- **Evidence:** [`notebooks/16_figures.ipynb`](../../notebooks/16_figures.ipynb),
  [`results/leaderboard.md`](../../results/leaderboard.md) (`dense+expand[ctx+figures]`)

## Context

The parser ([ADR-004](0004-pdf-parser.md)) wrote 418 images to `data/figures/` and stored
each as a `figure` element with no text. Chunking skipped them. Nothing the project name
calls *multimodal* had ever been read.

Two measurements came before any code:

| Question | Measured |
|---|---|
| Are the extracted images charts? | Four samples: a building photo, near-blank line art, a CSR photo, a QR code. **None is a chart.** |
| Are the charts hiding as vector drawings? | The pages with the most drawing paths (3,619 on Sun Pharma FY2025 p.14) turned out to be a leadership photo grid, icon-heavy text pages and ruled statement tables. **Path count does not detect charts.** |

## Decision

1. A local vision model (`gemma3:4b` via Ollama) gives every extracted image a **kind**
   (chart, table, infographic, diagram, photo, logo, qr_code, decorative) and a short
   description.
2. Only chart, table, infographic and diagram are indexed (`vision.KEEP`).
3. Descriptions live in their own table, `figure_descriptions` (element, model, kind,
   description). They are **never** written into `elements.text`.
4. Each kept figure becomes one `figure` chunk in the same `ctx` collection, so the agent
   retrieves it like any other evidence. The UI shows the image and labels the
   description as model-written.

## Why

- **Ask for a kind, not for a judgement.** On the four samples, gemma3:4b's `kind` was right
  4 of 4. Its yes/no "informative" flag was wrong 2 of 4: it called the QR code and the CSR
  photo informative.
- **The model has to fit the GPU.** gemma3:4b is 3.1 GB and fits in 4 GB of VRAM. qwen3-vl
  is 5.7 GB and spills to the CPU. At ~9 s an image, the batch is about an hour. It is
  resumable, with one commit per image.
- **JPEG 2000.** 50 of the 418 images are `.jpx`, which Ollama cannot decode. Every image is
  sent as RGB PNG, which also covers CMYK images.
- **Generated text stays separable.** A citation must never present a model's words as the
  filing's own. ADR-008 applied the same rule to chunk prefixes.

## Alternatives considered

| Option | Rejected because |
|---|---|
| **Render and describe every page** | 2,056 pages × ~9 s ≈ 5 hours. And every page already has a text layer (ADR-004), so a chart's printed labels are probably extracted as text already. That last point is unmeasured. |
| **qwen3-vl** | Does not fit the GPU. Spilling to the CPU turns the batch into many hours. |
| **CLIP-style image embeddings** | Matches a text query to an image by appearance. It cannot read the labels and figures that make a chart useful here. |
| **Descriptions in `elements.text`** | Would make generated text indistinguishable from the filing's own words. |
| **A Groq vision model** | No key yet, and it would spend the daily token budget the answer evaluation needs. |

## Consequences

- ⚠️ **A figure taken from a description can pass the agent's verifier.** The verifier checks
  what is printed *in the evidence*, and a description counts as evidence. So a figure
  citation carries `type: figure`, and the UI says the description was written by a model.
- **There is no ground truth for figures.** Figure retrieval is shown qualitatively only. The
  one measured control is whether adding figure chunks costs the benchmark any recall.
- **Vector-drawn charts stay invisible** to this system.

## Results

_To be filled from notebook 16 after the full run. No number is written here before it is
measured._
