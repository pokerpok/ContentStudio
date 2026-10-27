Judge each ZeroGPT-highlighted span. Rewrite only when the meaning must stay; otherwise delete or compress.

## OUTPUT LANGUAGE (mandatory — non-negotiable)
- Target: **{Language_Name}** / {Language_Label} (`{Language}`)
- Every `new` string MUST be in {Language_Name}.
- Flagged / draft text may be Russian or mixed — that is reference only. Translate kept meaning into {Language_Name}.
- Do NOT return Cyrillic `new` when target is a Latin-script language (`en`/`es`/`de`/…).

{Language_Lock}

## Section
- id: {Section_Id}
- heading: {Section_Heading}
- role: {Section_Role}

## Page job / constraints (use these to decide if the meaning is needed)
- page_job: {Page_Page_Job}
- must_include:
{Page_Must_Include}
- must_exclude:
{Page_Must_Exclude}
- verified_facts:
{Page_Verified_Facts}
- cta_primary: {Page_Cta_Primary}

## Full section (context — edit ONLY flagged spans; keep heading structure)
{Section_Previous_Draft}

## Edit history (avoid circling — do not restore rejected Before phrasings)
{Edit_History}

## Flagged sentences (each needs one editorial decision)
{ZeroGPT_Highlights}

## Notes
- page: {Page_Notes}
- section: {Section_Notes}

## FINAL CHECK
All `new` values in {Language_Name} (`{Language}`), or empty for delete.

Return JSON only:
{"edits":[{"old":"...","action":"delete|compress|rewrite|keep","flag_reason":"...","meaning_job":"...","decision":"...","new":"..."}]}
