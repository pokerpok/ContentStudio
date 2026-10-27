You write the **structure package** for one internal website page — Meta + Page job + Outline only.

You do NOT write the full page body in this pass. Section prose comes later, one section at a time.

{Language_Lock}

Language of Meta, Page job, and Outline headings/roles: **{Language_Name}** ({Language_Label}, code `{Language}`).
{Language_Instruction}

---

{Project_Brief}

---

## Role boundaries

- DO: Meta title/description/H1, clear page job, H2 outline with a one-line role per section.
- DO: Reflect must_include as concrete sections; push must_exclude / sibling jobs out of scope.
- DO NOT: invent licenses, fees, limits, payout times, geo-legality, certificates.
- DO NOT: invent a new URL — obey `{Page_Url}`.
- DO NOT: write long body copy, FAQ answers, or CTAs beyond naming them in the outline.

If `action=rewrite` and existing copy is present: improve the IA/outline of that page; keep useful headings, drop filler.

---

{Anti_AI_Style}

---

## Output contract

Write ONLY Markdown (no chain-of-thought):

```markdown
## Meta
- Title:
- Description:
- URL:
- H1:

## Page job (1–2 lines)

## Outline
- **Section heading** — one-line role (what this block must achieve for the user)
- **…** — …
```

Outline rules:
- 5–10 sections for standard length; fewer for short; more only for long-policy.
- Each bullet MUST use the form: `- **Heading** — role`
- Roles must be **non-overlapping**: each section owns a distinct job (define / path / criteria / risk / FAQ / CTA…). Do not give two sections the same thesis.
- First content section after H1 context; include FAQ as its own section when must_include asks for it.
- Primary CTA appears as a dedicated section or as role inside the closing section — do not omit.

Length target: {Page_Length}.
