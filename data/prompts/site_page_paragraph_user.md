Write the NEXT paragraph only for this section (ensemble step).

## OUTPUT LANGUAGE (mandatory — non-negotiable)
- Target: **{Language_Name}** / {Language_Label} (`{Language}`)
- Existing copy, notes, and outline headings may be in another language — still write THIS paragraph only in {Language_Name}.

{Language_Lock}

## Ensemble
- paragraph_index: {Paragraph_Index} (0-based)
- writing_model: {Ensemble_Model}
- partner_hint: {Ensemble_Hint}

## Section
- id: {Section_Id}
- heading: {Section_Heading}
- role: {Section_Role}

## Page job / constraints
- page_job: {Page_Page_Job}
- must_include (cover only what belongs here AND is not already covered):
{Page_Must_Include}
- must_exclude:
{Page_Must_Exclude}
- verified_facts:
{Page_Verified_Facts}
- cta_primary: {Page_Cta_Primary}

## Prior sections already written (do NOT restate these claims)
{Prior_Sections_Coverage}

## Later sections’ jobs (do not steal)
{Later_Section_Jobs}

## Existing page excerpt (optional reference — translate ideas, do not copy language)
{Page_Existing_Copy}

## Already written in THIS section (continue; do not repeat)
{Written_So_Far}

## Target paragraph to rewrite (if any — rewrite THIS, do not copy verbatim)
{Target_Paragraph}

## Full previous section draft (reference for improve / Anti-AI)
{Section_Previous_Draft}

## Edit history (avoid circling — do not restore rejected Before phrasings)
{Edit_History}

## Notes
- page: {Page_Notes}
- section: {Section_Notes}
- editor: {Page_Editor_Inputs}

## Mode
- section_mode: {Section_Mode}

## FINAL CHECK
Return one paragraph in **{Language_Name}** (`{Language}`), or DONE.
If the paragraph is not in {Language_Name}, rewrite it into {Language_Name} before answering.
If Target paragraph is not `(none)`, rewrite that paragraph only (keep facts; apply notes / Anti-AI rules).
