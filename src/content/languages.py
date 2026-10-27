"""Языки генерации контента."""

from __future__ import annotations

from typing import TypedDict


class LanguageOption(TypedDict):
    code: str
    label: str
    name_en: str
    instruction: str
    article_structure: str


_STRUCTURE_RU = """
# Понимание {Poker_Term}

## Введение
2–3 предложения: что это и почему важно, с живым примером.

## Как это работает
Суть термина и нюансы. Короткий конкретный пример.

## Примеры рук
Если применимо — 3 разных примера. Для каждого:
- Ваша рука: ...
- Оппонент: ... (если есть)
- Флоп: ...
- Тёрн: ...
- Ривер: ...
- Пояснение по термину

## {Poker_Term} в стратегии
Практические выводы для решений за столом.

## Связанные понятия
Только полезные связи.

## FAQ
1–3 частых вопроса с ответами.
""".strip()

_STRUCTURE_EN = """
# Understanding {Poker_Term}

## Introduction
2–3 sentences: what it is and why it matters, with a concrete example.

## How it works
Core definition and nuances. One short concrete example.

## Example hands
If applicable — 3 different examples. For each:
- Your Hand: ...
- Opponent: ... (if any)
- Flop: ...
- Turn: ...
- River: ...
- Explanation tied to the term

## {Poker_Term} in strategy
Practical takeaways for table decisions.

## Related concepts
Only useful links.

## FAQ
1–3 common questions with answers.
""".strip()

_STRUCTURE_UK = """
# Розуміння {Poker_Term}

## Вступ
2–3 речення: що це і чому важливо, з живим прикладом.

## Як це працює
Суть терміна та нюанси. Короткий конкретний приклад.

## Приклади рук
Якщо застосовно — 3 різні приклади. Для кожного:
- Ваша рука: ...
- Опонент: ... (якщо є)
- Флоп: ...
- Терн: ...
- Рівер: ...
- Пояснення щодо терміна

## {Poker_Term} у стратегії
Практичні висновки для рішень за столом.

## Пов’язані поняття
Лише корисні зв’язки.

## FAQ
1–3 поширені питання з відповідями.
""".strip()

_STRUCTURE_ES = """
# Comprender {Poker_Term}

## Introducción
2–3 frases: qué es y por qué importa, con un ejemplo concreto.

## Cómo funciona
Definición y matices. Un ejemplo breve y concreto.

## Manos de ejemplo
Si aplica — 3 ejemplos distintos. Para cada uno:
- Tu mano: ...
- Oponente: ... (si hay)
- Flop: ...
- Turn: ...
- River: ...
- Explicación ligada al término

## {Poker_Term} en la estrategia
Conclusiones prácticas para decisiones en la mesa.

## Conceptos relacionados
Solo vínculos útiles.

## FAQ
1–3 preguntas frecuentes con respuestas.
""".strip()

_STRUCTURE_DE = """
# {Poker_Term} verstehen

## Einführung
2–3 Sätze: was es ist und warum es zählt, mit konkretem Beispiel.

## So funktioniert es
Kern und Nuancen. Ein kurzes konkretes Beispiel.

## Beispielhände
Falls relevant — 3 unterschiedliche Beispiele. Für jedes:
- Deine Hand: ...
- Gegner: ... (falls vorhanden)
- Flop: ...
- Turn: ...
- River: ...
- Erklärung zum Begriff

## {Poker_Term} in der Strategie
Praktische Ableitungen für Tischentscheidungen.

## Verwandte Begriffe
Nur nützliche Verbindungen.

## FAQ
1–3 häufige Fragen mit Antworten.
""".strip()

_STRUCTURE_IT = """
# Capire {Poker_Term}

## Introduzione
2–3 frasi: cos’è e perché conta, con un esempio concreto.

## Come funziona
Definizione e sfumature. Un esempio breve e concreto.

## Mani di esempio
Se applicabile — 3 esempi diversi. Per ciascuno:
- La tua mano: ...
- Avversario: ... (se c’è)
- Flop: ...
- Turn: ...
- River: ...
- Spiegazione legata al termine

## {Poker_Term} nella strategia
Takeaway pratici per le decisioni al tavolo.

## Concetti correlati
Solo collegamenti utili.

## FAQ
1–3 domande frequenti con risposte.
""".strip()

_STRUCTURE_PL = """
# Zrozumieć {Poker_Term}

## Wprowadzenie
2–3 zdania: czym to jest i dlaczego ma znaczenie, z konkretnym przykładem.

## Jak to działa
Definicja i niuanse. Krótki konkretny przykład.

## Przykładowe ręce
Jeśli dotyczy — 3 różne przykłady. Dla każdego:
- Twoja ręka: ...
- Przeciwnik: ... (jeśli jest)
- Flop: ...
- Turn: ...
- River: ...
- Wyjaśnienie powiązane z terminem

## {Poker_Term} w strategii
Praktyczne wnioski do decyzji przy stole.

## Pojęcia powiązane
Tylko przydatne powiązania.

## FAQ
1–3 częste pytania z odpowiedziami.
""".strip()

_STRUCTURE_PT = """
# Compreender {Poker_Term}

## Introdução
2–3 frases: o que é e por que importa, com um exemplo concreto.

## Como funciona
Definição e nuances. Um exemplo curto e concreto.

## Mãos de exemplo
Se aplicável — 3 exemplos diferentes. Para cada um:
- A tua mão: ...
- Oponente: ... (se houver)
- Flop: ...
- Turn: ...
- River: ...
- Explicação ligada ao termo

## {Poker_Term} na estratégia
Conclusões práticas para decisões à mesa.

## Conceitos relacionados
Apenas ligações úteis.

## FAQ
1–3 perguntas frequentes com respostas.
""".strip()

_STRUCTURE_PT_BR = """
# Entender {Poker_Term}

## Introdução
2–3 frases: o que é e por que importa, com um exemplo concreto.

## Como funciona
Definição e nuances. Um exemplo curto e concreto.

## Mãos de exemplo
Se aplicável — 3 exemplos diferentes. Para cada um:
- Sua mão: ...
- Oponente: ... (se houver)
- Flop: ...
- Turn: ...
- River: ...
- Explicação ligada ao termo

## {Poker_Term} na estratégia
Conclusões práticas para decisões na mesa.

## Conceitos relacionados
Só links úteis.

## FAQ
1–3 perguntas frequentes com respostas.
""".strip()

_STRUCTURE_FI = """
# {Poker_Term} lyhyesti

## Johdanto
2–3 lausetta: mitä se on ja miksi se merkitsee, konkreettisella esimerkillä.

## Miten se toimii
Ydin ja nyanssit. Lyhyt konkreettinen esimerkki.

## Esimerkkikädet
Jos sopii — 3 erilaista esimerkkiä. Jokaiselle:
- Kätesi: ...
- Vastustaja: ... (jos on)
- Flop: ...
- Turn: ...
- River: ...
- Selitys termiin sidottuna

## {Poker_Term} strategiassa
Käytännön otteet pöytäpäätöksiin.

## Liittyvät käsitteet
Vain hyödylliset linkit.

## FAQ
1–3 yleistä kysymystä vastauksineen.
""".strip()

_STRUCTURE_HU = """
# {Poker_Term} megértése

## Bevezető
2–3 mondat: mi ez és miért számít, konkrét példával.

## Hogyan működik
Lényeg és árnyalatok. Rövid, konkrét példa.

## Példa kezek
Ha releváns — 3 különböző példa. Mindegyikhez:
- A te kezed: ...
- Ellenfél: ... (ha van)
- Flop: ...
- Turn: ...
- River: ...
- Magyarázat a fogalomhoz kötve

## {Poker_Term} a stratégiában
Gyakorlati tanulságok asztali döntésekhez.

## Kapcsolódó fogalmak
Csak hasznos kapcsolatok.

## FAQ
1–3 gyakori kérdés válasszal.
""".strip()


def _latin_instruction(name_en: str, label: str, *, extra: str = "") -> str:
    base = (
        f"OUTPUT LANGUAGE = {name_en} ({label}) ONLY. "
        f"Write the ENTIRE final text in {name_en}: headings, body, FAQ, CTAs, meta. "
        f"If existing_copy / outline / notes are in Russian, English, or another language — "
        f"TRANSLATE into {name_en}. "
        f"Do NOT write Russian (Cyrillic). Do NOT leave Russian sentences in the draft. "
        f"Brand and product proper nouns from the brief may stay as-is."
    )
    if extra:
        return f"{base} {extra}"
    return base


LANGUAGES: dict[str, LanguageOption] = {
    "en": {
        "code": "en",
        "label": "English",
        "name_en": "English",
        "instruction": _latin_instruction("English", "English"),
        "article_structure": _STRUCTURE_EN,
    },
    "ru": {
        "code": "ru",
        "label": "Русский",
        "name_en": "Russian",
        "instruction": (
            "OUTPUT LANGUAGE = Russian ONLY. "
            "Пиши ВЕСЬ итоговый текст по-русски: заголовки, абзацы, FAQ, CTA, meta. "
            "Если исходник на английском или другом языке — переведи на русский. "
            "Не оставляй английские абзацы в публикуемом драфте "
            "(покерные термины вроде flop, all-in допустимы)."
        ),
        "article_structure": _STRUCTURE_RU,
    },
    "uk": {
        "code": "uk",
        "label": "Українська",
        "name_en": "Ukrainian",
        "instruction": (
            "OUTPUT LANGUAGE = Ukrainian ONLY. "
            "Write the ENTIRE final text in Ukrainian, including ALL headings. "
            "If the source is in another language, translate into Ukrainian."
        ),
        "article_structure": _STRUCTURE_UK,
    },
    "es": {
        "code": "es",
        "label": "Español",
        "name_en": "Spanish",
        "instruction": _latin_instruction("Spanish", "Español"),
        "article_structure": _STRUCTURE_ES,
    },
    "de": {
        "code": "de",
        "label": "Deutsch",
        "name_en": "German",
        "instruction": _latin_instruction("German", "Deutsch"),
        "article_structure": _STRUCTURE_DE,
    },
    "it": {
        "code": "it",
        "label": "Italiano",
        "name_en": "Italian",
        "instruction": _latin_instruction("Italian", "Italiano"),
        "article_structure": _STRUCTURE_IT,
    },
    "pl": {
        "code": "pl",
        "label": "Polski",
        "name_en": "Polish",
        "instruction": _latin_instruction("Polish", "Polski"),
        "article_structure": _STRUCTURE_PL,
    },
    "pt": {
        "code": "pt",
        "label": "Português",
        "name_en": "Portuguese",
        "instruction": _latin_instruction(
            "Portuguese",
            "Português",
            extra=(
                "Use European Portuguese wording (Portugal), not Brazilian slang "
                "or 'você'-heavy BR style, unless the user selected pt-BR."
            ),
        ),
        "article_structure": _STRUCTURE_PT,
    },
    "pt-BR": {
        "code": "pt-BR",
        "label": "Português (Brasil)",
        "name_en": "Brazilian Portuguese",
        "instruction": _latin_instruction(
            "Brazilian Portuguese",
            "Português (Brasil)",
            extra=(
                "Use Brazilian Portuguese (pt-BR): natural BR wording, "
                "'você' where appropriate — not European Portuguese."
            ),
        ),
        "article_structure": _STRUCTURE_PT_BR,
    },
    "fi": {
        "code": "fi",
        "label": "Suomi",
        "name_en": "Finnish",
        "instruction": _latin_instruction("Finnish", "Suomi"),
        "article_structure": _STRUCTURE_FI,
    },
    "hu": {
        "code": "hu",
        "label": "Magyar",
        "name_en": "Hungarian",
        "instruction": _latin_instruction("Hungarian", "Magyar"),
        "article_structure": _STRUCTURE_HU,
    },
}

DEFAULT_LANGUAGE = "ru"

# алиасы UI / файлов
_LANGUAGE_ALIASES: dict[str, str] = {
    "pt_br": "pt-BR",
    "ptbr": "pt-BR",
    "pt-br": "pt-BR",
    "br": "pt-BR",
    "brazilian": "pt-BR",
    "deu": "de",
    "ger": "de",
    "ita": "it",
    "pol": "pl",
    "por": "pt",
    "fin": "fi",
    "hun": "hu",
    "spa": "es",
    "eng": "en",
}

CYRILLIC_LANGUAGE_CODES = frozenset({"ru", "uk"})
LATIN_SCRIPT_LANGUAGE_CODES = frozenset(
    code for code in LANGUAGES if code not in CYRILLIC_LANGUAGE_CODES
)


def normalize_language_code(code: str) -> str:
    raw = (code or "").strip()
    if not raw:
        return DEFAULT_LANGUAGE
    if raw in LANGUAGES:
        return raw
    key = raw.lower().replace(" ", "")
    aliased = _LANGUAGE_ALIASES.get(key) or _LANGUAGE_ALIASES.get(raw.lower())
    if aliased and aliased in LANGUAGES:
        return aliased
    # case-insensitive match on known codes
    for known in LANGUAGES:
        if known.lower() == raw.lower():
            return known
    return DEFAULT_LANGUAGE


def get_language(code: str) -> LanguageOption:
    return LANGUAGES.get(normalize_language_code(code)) or LANGUAGES[DEFAULT_LANGUAGE]


def is_cyrillic_language(code: str) -> bool:
    return normalize_language_code(code) in CYRILLIC_LANGUAGE_CODES


def is_latin_script_language(code: str) -> bool:
    return normalize_language_code(code) in LATIN_SCRIPT_LANGUAGE_CODES


def language_choices() -> list[tuple[str, str]]:
    return [(opt["code"], opt["label"]) for opt in LANGUAGES.values()]


def prompt_vars_for_language(code: str) -> dict[str, str]:
    opt = get_language(code)
    lock = (
        f"OUTPUT LANGUAGE LOCK (non-negotiable):\n"
        f"- Target language code: `{opt['code']}`\n"
        f"- Write ALL user-facing text in **{opt['name_en']}** ({opt['label']}).\n"
        f"- This includes: Meta title/description/H1, Outline headings, section bodies, "
        f"FAQ questions/answers, CTAs, Editor notes meant for publish.\n"
        f"- If existing_copy / editor inputs / outline headings / neighbor drafts / "
        f"source page are in another language (often Russian) — "
        f"TRANSLATE and rewrite into {opt['name_en']}. Do NOT copy the source language.\n"
        f"- Do NOT mix languages in the publishable draft. "
        f"Brand and product proper nouns from the brief may stay as-is.\n"
        f"- If you drift into another language, rewrite that sentence into {opt['name_en']} "
        f"before finishing.\n"
    )
    if is_latin_script_language(opt["code"]):
        lock += (
            f"- HARD BAN: Cyrillic / Russian / Ukrainian body text is forbidden. "
            f"If a draft appears in Cyrillic, rewrite the whole draft into {opt['name_en']}.\n"
            f"- Outline headings in Russian are NOT a license to write the body in Russian — "
            f"translate headings and body into {opt['name_en']}."
        )
    else:
        lock += (
            f"- If the source is English/Spanish/other Latin script, translate into "
            f"{opt['name_en']}; do not leave long Latin-only paragraphs in the publishable draft."
        )
    return {
        "Language": opt["code"],
        "Language_Name": opt["name_en"],
        "Language_Label": opt["label"],
        "Language_Instruction": opt["instruction"],
        "Language_Lock": lock,
        "Article_Structure": opt["article_structure"],
    }
