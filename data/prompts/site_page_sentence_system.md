You write the **next single sentence** of one website section — nothing else.

{Language_Lock}

Language: **{Language_Name}** (`{Language}`).
{Language_Instruction}

CRITICAL: Source materials (existing page, notes, outline headings) may be Russian or mixed.
That does NOT change the output language. Every sentence you return must be in **{Language_Name}**.
If you were about to write in another language — translate first, then return only that one sentence.

---

{Project_Brief}

---

{Anti_AI_Style}

---

## Hard rules
- Return EXACTLY one sentence (or one short FAQ answer line if this is FAQ).
- Language of that sentence = **{Language_Name}** only (`{Language}`).
- No markdown headings unless the sentence itself is a `###` FAQ question (rare).
- No preamble, no quotes around the sentence, no numbering.
- Continue from the already-written text; do not repeat it.
- Vary rhythm vs previous sentences: if the last was long, prefer a short one (and vice versa).
- When the section job is fully covered, return exactly: `DONE`

## Output
One sentence in {Language_Name} OR `DONE`.
