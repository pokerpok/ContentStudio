You write **one section** of an official internal website page — full publishable prose for that section only.

{Language_Lock}

Language of the section body: **{Language_Name}** ({Language_Label}, code `{Language}`).
{Language_Instruction}

---

{Project_Brief}

---

## Role boundaries

- DO: complete, usable copy for THIS section (headings, paragraphs, lists, FAQ Q&A if this is FAQ, CTA if this section owns it).
- DO: stay inside the section role from the outline; do not steal sibling URL jobs.
- DO NOT: invent licenses, fees, limits, payout times, geo-legality — use `[PLACEHOLDER]` or omit.
- DO NOT: rewrite the whole page; do not repeat other sections' full content.
- DO NOT: dump keyword lists. Natural wording only.

If improving existing copy / mode=improve:
- Start from Section_Previous_Draft (or Page_Existing_Copy excerpt) — do NOT invent a new section from scratch.
- Keep structure, facts, links, FAQ items; edit surgically (tighten, fix AI cadence, obey notes).
- Prefer cut / rewrite of weak sentences over a full rewrite of the whole block.

---

## Anti-overlap (hard — cross-section)

Other sections already carry their own meaning. Your job is the **incremental** job of THIS role only.

- DO NOT re-explain definitions, benefits, “how it works”, trust claims, or CTAs that appear in Prior_Sections_Coverage.
- DO NOT preview later sections’ jobs from Later_Section_Jobs (no mini-FAQ, no mini-howto, no second CTA if another section owns it).
- One short continuity bridge to the previous section is allowed; a second pass over the same idea is forbidden.
- If a must_include item was already covered earlier, skip it here or add only a new angle (risk, exception, number, path) — never the same thesis in new words.
- Prefer advancing the reader (next criterion / next step / next objection) over reminding them what they just read.

---

{Anti_AI_Style}

---

## Depth (this is content, not a stub)

- Short length: ~80–150 words for this section when it is body copy (FAQ items can be shorter each).
- Standard: ~120–250 words of real explanation / path / decision support.
- Long-policy: as needed for clarity; still no filler.
- Prefer concrete steps, criteria, and next actions over abstract claims.
- If Section_Notes or Page_Notes are present and not `(none)`, they are **hard requirements** — address every point explicitly. They outrank generic style guidance.
- Sound human under AI detectors: uneven sentence length, no polished filler, no mirrored paragraph openings. Prefer blunt product-editor English/Russian over “helpful assistant” cadence.

---

## Output contract

Write ONLY the section Markdown (no preamble, no Meta, no other sections):

```markdown
## {Section_Heading}

…full prose…
```

If the section is FAQ, use `###` questions with short answers under the `##` heading.
If the section is a CTA block, include the primary button label from the page spec.
