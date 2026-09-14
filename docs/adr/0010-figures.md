# ADR-010: Figures — triage by kind, describe, index beside the text

- **Status:** Accepted, amended after the first full run (2026-09-13): a blank image is never
  shown to the model, and a figure description never verifies a number (decisions 5 and 6)
- **Date:** 2026-09-12
- **Evidence:** [`notebooks/16_figures.ipynb`](../../notebooks/16_figures.ipynb),
  [`results/leaderboard.md`](../../results/leaderboard.md) (`dense+expand[ctx+figures]`),
  `tests/test_vision.py`, `tests/test_agent.py`

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
5. **A blank image is never shown to the model.** `vision.is_blank` labels an image `blank`
   when every pixel channel's standard deviation is under 1: one flat colour, nothing to
   read. *(Added after the first full run.)*
6. **A figure description never verifies a number.** The agent's verifier counts only figures
   printed in the filing's own text, and never cites a `figure` chunk as the source of a
   figure. *(Added after the first full run.)*

## Why

- **Ask for a kind, not for a judgement.** On the four samples, gemma3:4b's `kind` was right
  4 of 4. Its yes/no "informative" flag was wrong 2 of 4: it called the QR code and the CSR
  photo informative. That held on real images. On blank ones it did not (Results), hence
  decisions 5 and 6.
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

- **A figure taken from a description could pass the agent's verifier.** Listed here as a
  risk, then measured in the first full run (Results). Decision 6 closes it. A narrative
  answer may still cite a figure chunk, and the UI labels its description as model-written.
- **Photos and adverts still pass as infographics.** By their own descriptions, several of the
  16 indexed figures are a desk photo, adverts and film posters, and one is a blurred photo
  background described as a revenue chart (HDFC Bank p.10, std-dev 22.9, out of reach of any
  safe blank cut). Their numbers cannot reach an answer; they can still take a retrieval slot.
- **There is no ground truth for figures.** Figure retrieval is shown qualitatively only. The
  one measured control is whether adding figure chunks costs the benchmark any recall.
- **Vector-drawn charts stay invisible** to this system.

## Results

### Full run — `ollama/gemma3:4b`, all 418 figures (notebook 16, 2026-09-13)

| kind | figures | indexed |
|---|---|---|
| photo | 236 | no |
| decorative | 102 | no |
| qr_code | 37 | no |
| logo | 19 | no |
| diagram | 9 | yes |
| infographic | 8 | yes |
| chart | 7 | yes |
| **total** | **418** | **24 (5.7%)** |

No image was labelled `table`. The last 63 images took 363 s (5.8 s each). The batch
completed over three runs, so its total wall time was not measured.

**Control: adding the figure chunks cost the benchmark nothing.** `dense+expand[ctx+figures]`
(10,205 points) equals `dense+expand[ctx]` (10,181) on R@1, R@3, R@5, R@10, MRR and every
depth to @200. Only page-recall@5 moved, 0.364 → 0.386 (one question), and the figures are
not the cause (see the correction below).

### ⚠️ The descriptions of blank images are invented

Checked, not assumed: five indexed images opened by eye, then the pixel standard deviation of
all 418.

| measured | |
|---|---|
| indexed figures whose image is **perfectly blank** (std-dev 0.0: plain white, or solid black) | **8 of 24** |
| blank images in the whole set (every channel's std-dev < 1) that the model called a chart or diagram | **8 of 12** |
| an indexed "chart" that is a blurred photo background (HDFC Bank p.10, std-dev 22.9) | 1 |
| the one real diagram opened (HDFC Bank p.230, "Three Lines of Defense") | described correctly |

None of the 418 files has an alpha channel, so the flat ones are flat in the file, not shapes
hidden in a transparency mask.

The invented descriptions carry specific numbers. Four blank Reliance p.1 images became
"Revenue (INR Crores) 2018: 1200 … 2022: 2500". A blank ICICI Bank FY2025 p.39 image became
"₹ 1,500 Cr … ₹ 3,500 Cr". HDFC Bank p.10 and Reliance p.1 were both given
"₹ 1,387.x Cr, ₹ 1,633.68 Cr": the same invented series for two companies.

**They reached the agent.** With the ledger's retriever, 1 of 44 benchmark questions had a
figure chunk in its top-10 evidence: ICICI Bank FY2025 total revenue, rank 4, the blank p.39
image. 2 of 44 did at the top-20 retry depth. Every invented number has at least four
significant digits, which is all the verifier's length rule asks (`MIN_DIGITS = 4`), and the
verifier did not check a chunk's type. So the risk listed under Consequences was real: nothing
stopped an invented figure being accepted as printed in the evidence.

**The qualitative look in notebook 16 §5 was misleading.** Sun Pharma's top three hits for
"revenue trend chart" (p.133–134) were the three blank images. It looked like figure retrieval
working; it was retrieval of invented text.

### After the fix — decisions 5 and 6 (notebook 16 re-run, 2026-09-13)

The 24 figure points were deleted, the 12 blank images re-triaged by the filter (no model
call), and the figure chunks indexed again.

| | first run | after the fix |
|---|---|---|
| labelled `blank`, never sent to the model | — | 12 |
| indexed: chart / infographic / diagram | 24: 7 / 8 / 9 | **16: 3 / 8 / 5** |
| collection points | 10,205 | 10,197 |
| R@1–R@10, MRR, recall to @200 | same as `[ctx]` | same as `[ctx]` |
| benchmark questions with a figure chunk in top-10 / top-20 evidence | 1 / 2 | **0 / 0** |

**The cut at 1 is measured, not chosen for comfort.** 12 images fall under it: 11 perfectly
flat and one at 0.8. The next image up is at 1.8, and the model had labelled it decorative. A
higher cut changes nothing on this corpus and would risk faint real content on another.

**Correction: the page-recall gain is unexplained.** This section first attributed it to the
blank ICICI Bank p.39 chunk sitting on an answer page. That was wrong: after the fix no figure
chunk is in any question's top 20, yet page-recall@5 is still 0.386. The query-expansion
refactor made between the `[ctx]` baseline runs and these ones is ruled out as well: the old
and new expansion give 0.386 on today's index. One question moved, and the cause is not
established.
