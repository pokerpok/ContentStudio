Write the NEXT sentence only for this section.

## OUTPUT LANGUAGE (mandatory — non-negotiable)
- Target: **{Language_Name}** / {Language_Label} (`{Language}`)
- Existing copy, notes, and outline headings may be in another language — still write THIS sentence only in {Language_Name}.
- Do not continue in the source language just because the heading or previous draft is Russian/other.

{Language_Lock}

## Section
- id: {Section_Id}
- heading: {Section_Heading}
- role: {Section_Role}
- sentence_index: {Sentence_Index} (0-based)
- target_temperature_hint: {Temp_Hint}

## Page job / constraints
- page_job: {Page_Page_Job}
- must_include (cover only what belongs here): 
{Page_Must_Include}
- must_exclude:
{Page_Must_Exclude}
- verified_facts:
{Page_Verified_Facts}
- cta_primary: {Page_Cta_Primary}

## Existing page excerpt (optional reference — translate ideas, do not copy language)
{Page_Existing_Copy}

## Already written in THIS section (continue; do not repeat; match TARGET language even if heading differs)
{Written_So_Far}

## Notes
- page: {Page_Notes}
- section: {Section_Notes}
- editor: {Page_Editor_Inputs}

## FINAL CHECK
Return one sentence in **{Language_Name}** (`{Language}`), or DONE.
If the sentence is not in {Language_Name}, rewrite it into {Language_Name} before answering.
