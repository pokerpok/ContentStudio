Second-pass Anti-AI edit for ONE section. Surgical rewrite only.

## OUTPUT LANGUAGE
**{Language_Name}** (`{Language}`) — do not switch languages.

## Section
- section_id: {Section_Id}
- heading: {Section_Heading}
- role: {Section_Role}

## Detected AI patterns in current draft (must neutralize each)
{Detected_AI_Patterns}

## Current draft (edit this; do not invent a new page)
{Section_Previous_Draft}

## Prior sections already written (strip any rehash of these)
{Prior_Sections_Coverage}

## Later sections’ jobs (do not pull their content into this section)
{Later_Section_Jobs}

## Edit history (avoid circling — do not restore Before phrasings)
{Edit_History}

## Page notes (if any)
{Page_Notes}

## Section notes (if any)
{Section_Notes}

## Rules
- Keep facts, links, placeholders, FAQ structure, CTA intent.
- IGTL: judge filler in context; do not synonym-swap; replace with a real fact or cut / `[PLACEHOLDER]`.
- Kill LLM cadence: mirrored openings, filler transitions, marketing foam, iGaming clichés.
- Prefer shorter, blunter product-editor prose.
- If Edit_History shows prior passes, take a different angle; cut filler instead of synonym loops.
- Strip cross-section rehash: if this draft repeats Prior_Sections_Coverage, cut or replace with a new angle for THIS role only.
- **Lists:** Pros / Cons / Additional info / bullet blocks must stay as Markdown lists — one `- item` per line. Never flatten a list into one prose sentence or one long line.
- Return ONLY the revised section Markdown under the same heading.
