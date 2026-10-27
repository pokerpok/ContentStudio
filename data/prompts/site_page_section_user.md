Write or improve ONE section of the page. Other sections are out of scope.

## OUTPUT LANGUAGE (mandatory)
- Target: **{Language_Name}** / {Language_Label} (`{Language}`)
- Existing copy may be in another language — still write THIS section only in {Language_Name}.

{Language_Lock}

## Page context
- page_id: {Page_Id}
- url: {Page_Url}
- source_url: {Page_Source_Url}
- action: {Page_Action}
- page_job: {Page_Page_Job}
- primary_keyword: {Page_Primary_Keyword}
- audience: {Page_Audience}
- cta_primary: {Page_Cta_Primary}
- cta_secondary: {Page_Cta_Secondary}
- length: {Page_Length}
- tone_shift: {Page_Tone_Shift}
- page.locale field (IA hint only, NOT output language): {Page_Locale}

## Full outline (roles — do not write other sections)
{Page_Outline_Md}

## This section only
- section_id: {Section_Id}
- heading: {Section_Heading}
- role: {Section_Role}
- mode: {Section_Mode}

## Prior sections already written (COVERED — do not restate)
{Prior_Sections_Coverage}

## Immediate previous section (continuity only — do not rewrite it)
{Immediate_Previous_Section}

## Later sections’ jobs (do not steal)
{Later_Section_Jobs}

## Constraints
must_include (page-level — cover only what belongs in THIS section AND is not already covered above):
{Page_Must_Include}

must_exclude:
{Page_Must_Exclude}

sibling_urls:
{Page_Sibling_Urls}

verified_facts:
{Page_Verified_Facts}

## Existing page copy (rewrite/improve from this when relevant)
{Page_Existing_Copy}

## Previous draft of THIS section (improve if mode=improve; else may ignore body but still obey notes)
{Section_Previous_Draft}

## Edit history (avoid circling — do not restore rejected Before phrasings)
{Edit_History}

## ⚠️ Revision notes for THIS section — MANDATORY (do every bullet/request)
{Section_Notes}

## Page-level revision notes — MANDATORY when relevant to this section
{Page_Notes}

## Editor inputs
{Page_Editor_Inputs}

## Output
Follow SYSTEM: only this section's Markdown under `## {Section_Heading}`.
You MUST satisfy Section_Notes / Page_Notes above when they are not `(none)`.
Anti-AI rules are mandatory — rewrite any sentence that sounds like generic LLM marketing.
Anti-overlap is mandatory — if an idea is in Prior_Sections_Coverage, do not explain it again.
If the section has Pros/Cons or other lists, keep them as Markdown `- item` lines (one item per line), never join into one paragraph.
output_extra: {Page_Output_Extra}

Topic: {Poker_Term}
