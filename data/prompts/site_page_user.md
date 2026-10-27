Generate official site copy for one internal page.

## OUTPUT LANGUAGE (mandatory)
- Target: **{Language_Name}** / {Language_Label} (`{Language}`)
- Ignore source-language of existing_copy when producing the draft — output must be {Language_Name}.

{Language_Lock}

## Page
- page_id: {Page_Id}
- term / output slug basis: {Page_Term}
- url: {Page_Url}
- page.locale field (IA hint only, NOT output language): {Page_Locale}
- page_type: {Page_Type}
- action: {Page_Action}
- parent_url: {Page_Parent_Url}
- length: {Page_Length}
- tone_shift: {Page_Tone_Shift}

## Job & SEO intent
- primary_job: {Page_Primary_Job}
- primary_keyword: {Page_Primary_Keyword}
- secondary_keywords: {Page_Secondary_Keywords}
- audience: {Page_Audience}
- funnel_stage: {Page_Funnel_Stage}
- cta_primary: {Page_Cta_Primary}
- cta_secondary: {Page_Cta_Secondary}

## Structure constraints

must_include:
{Page_Must_Include}

must_exclude:
{Page_Must_Exclude}

sibling_urls (link to these; do not steal their job):
{Page_Sibling_Urls}

objections_to_handle_indirectly:
{Page_Objections}

## Verified facts (do not invent beyond this)
{Page_Verified_Facts}

## Package / IA excerpt for this page
{Page_Package_Excerpts}

## Source / existing copy
- source_url: {Page_Source_Url}
- existing_copy (use if action=rewrite or improve; else ignore):
{Page_Existing_Copy}

## Editor inputs
{Page_Editor_Inputs}

## Page-level revision notes (must address)
{Page_Notes}

## Output
Follow the SYSTEM output contract. Full draft must be complete publishable copy, not outline stubs.
output_extra: {Page_Output_Extra}

Topic label for files: {Poker_Term}
