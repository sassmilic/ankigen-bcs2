PROMPT_WORD_METADATA = """
You'll receive a list of BCS words (may contain misspellings).
For each word in the input list, return a JSON object containing
the original `word` and the following fields: `canonical_form`,
`part_of_speech`, `word_type`, and `translation`.

1.  **`word`**: The original word from the input list.
2.  **`canonical_form`**: Correct spelling, lowercase unless it's a proper noun. Use the dictionary base form:
    *   Noun → nominative singular
    *   Verb → infinitive
    *   Adjective → masculine nominative singular
    *   Other → standard dictionary form
3.  **`part_of_speech`**: Classify into one of:
    *   "imenica"
    *   "glagol"
    *   "pridjev"
    *   "prilog"
    *   "zamjenica"
    *   "prijedlog"
    *   "veznik"
    *   "uzvik"
4.  **`word_type`**: This is for deciding image generation strategy. Classify the word as:
    *   "SIMPLE": a clearly visible, concrete object likely to yield useful photo results (e.g., "jabuka", "kuća").
    *   "COMPLEX": an abstract concept, action, quality, or emotion better suited to symbolic or AI-generated imagery (e.g., "ljubav", "misliti", "sloboda").
    If unsure, choose "COMPLEX".
5.  **`translation`**: Translate the core meaning of the word into English. Use only one or two words — the most relevant translation for a language learner.

---

Return your output as a single **JSON array**, one object per word.
Your response must be *only* the JSON array. It must start with `[` and end with `]`.
Do not include any other text, explanations, or markdown formatting (like `json` or ```) before or after the JSON array.

**Example Output Format:**
[
  {{
    "word": "prodrijes", // original input word
    "canonical_form": "prodrijeti",
    "part_of_speech": "glagol",
    "word_type": "COMPLEX",
    "translation": "penetrate"
  }},
  {{
    "word": "vrijedan",
    "canonical_form": "vrijedan",
    "part_of_speech": "pridjev",
    "word_type": "COMPLEX",
    "translation": "valuable"
  }}
  // ... more objects for other words in the list
]

Word list: {word_list}
"""

PROMPT_WORD_DEFINITION = """
You'll receive a list of BCS words. For each word in the input list, return a JSON object containing the original `word` and its `definition`.

1.  **`word`**: The original word from the input list.
2.  **`definition`**:
    *   Write a definition suitable for language learners using Anki.
    *   It should be short and clear.
    *   If the word has multiple distinct senses, list them separately using numbered entries like `1. ...`, `2. ...`. 
    *   - Keep each sense short and clear. 
    *   - If the meanings are subtle variations, combine them into a single sentence. 
    *   - Do not force multiple senses if only one is appropriate.
    *   Use natural, conversational language. Avoid overly academic phrasing.
    *   If possible, include both literal and abstract meanings.
    *   Start the definition with the word in cloze brackets: `{{{{c1::word}}}}`. If the word appears multiple times in the definition, use cloze brackets for each instance.
    *   Include key grammatical info in parentheses within the definition:
        *   Verbs: (glagol, [aspect], {{{{c1::1st person present}}}})
        *   Nouns: (imenica); add gender only if irregular, and note if uncountable
        *   Adjectives: (pridjev, [degree])
    *   If regional usage is notable (e.g. only in Croatia, archaic, dialectal), briefly mention it at the end.
    *   Use standard ijekavian.

---

Return your output as a single **JSON array**, one object per word.
Your response must be *only* the JSON array. It must start with `[` and end with `]`.
Do not include any other text, explanations, or markdown formatting (like `json` or ```) before or after the JSON array.

**Example Definitions:**
- `{{{{c1::Prodrijeti}}}} (glagol, svršeni vid, {{{{c1::prodrijem}}}}) znači proći kroz neku prepreku ili ući duboko u nešto — fizički (kao svjetlost kroz tamu), emocionalno (dirnuti nekoga), ili mentalno (dokučiti neku ideju).`
- `{{{{c1::Blagostanje}}}} (imenica, nebrojivo) označava stanje u kojem osoba ili zajednica ima dovoljno sredstava za udoban, siguran i zadovoljavajući život.`
- `{{{{c1::Najvažniji}}}} (pridjev, superlativ) opisuje ono što ima najveći značaj ili prioritet u odnosu na sve druge stvari u određenom kontekstu.`
- `{{{{c1::Ćuprija}}}} (imenica, turcizam) označava most; riječ je arhaična i danas se uglavnom koristi u Bosni.`

**Example Output Format:**
[
  {{ 
    "word": "prodrijes", // original input word
    "definition": "{{{{c1::Prodrijeti}}}} (glagol, svršeni vid, {{{{c1::prodrijem}}}}) znači proći kroz neku prepreku ili ući duboko u nešto — fizički (kao svjetlost kroz tamu), emocionalno (dirnuti nekoga), ili mentalno (dokučiti neku ideju)."
  }},
  {{
  "word": "vrijedan",
    "definition": "{{{{c1::Vrijedan}}}} (pridjev, pozitivan) može imati više značenja: 1. Opisuje osobu koja marljivo i odgovorno radi. 2. Označava nešto što ima visoku vrijednost ili važnost."
  }},
  // ... more objects for other words in the list
]

Word list: {word_list}
"""

PROMPT_EXAMPLE_SENTENCES = """
You'll receive a list of BCS words. For each word in the input list, return a JSON object containing the original `word` and a list of three `example_sentences`.

1.  **`word`**: The original word from the input list.
2.  **`example_sentences`**:
    *   Generate exactly 3 example sentences in BCS (ijekavian variant) using the target word.
    *   Use different grammatical forms of the word (e.g., for verbs: vary tense, person, or mood; for nouns: vary case or number).
    *   Wrap all inflected forms of the word in cloze brackets: `{{{{c1::...}}}}`
    *   Each sentence should be ~10 words for easy memorization.
    *   Use vivid imagery or strong emotional content to make the sentence memorable. Think: scenes that evoke touch, smell, light, feeling, surprise, or desire.
    *   Use a positive or life-affirming tone when appropriate.

---

Return your output as a single **JSON array**, one object per word.
Your response must be *only* the JSON array. It must start with `[` and end with `]`.
Do not include any other text, explanations, or markdown formatting (like `json` or ```) before or after the JSON array.

**Example Sentences Sets:**

For "neovisnost":
[
  "{{{{c1::Neovisnost}}}} jedne zemlje vrijedi više od zlata.",
  "Putujući sama, osjetila je moć {{{{c1::neovisnosti}}}}.",
  "Njena {{{{c1::neovisnost}}}} plašila je one koji su voljeli kontrolu."
]

For "prozvati":
[
  "Majka me {{{{c1::prozvala}}}} jer sam ukrao smokve.",
  "Publika ga je {{{{c1::prozvala}}}} herojem nakon govora.",
  "Starac ju je {{{{c1::prozvao}}}} anđelom u posljednjem dahu."
]

**Example Output Format:**
[
  {{
    "word": "prodrijes", // original input word
    "example_sentences": [
      "Sunčeva svjetlost je uspjela {{{{c1::prodrijeti}}}} kroz guste oblake.",
      "Njene riječi su duboko {{{{c1::prodrle}}}} u moje misli.",
      "Nakon dugog razmišljanja, konačno sam uspio {{{{c1::prodrijeti}}}} do suštine problema."
    ]
  }}, 
  {{
    "word": "vrijedan",
    "example_sentences": [
      "Tvoj savjet bio je {{{{c1::vrijedan}}}} svakog truda i vremena.", // Ensured consistent quadrupled braces
      "Ona je {{{{c1::vrijedna}}}} djevojka koja stalno pomaže drugima.", // Ensured consistent quadrupled braces
      "Na sastanku je predložio {{{{c1::vrijednu}}}} i praktičnu ideju." // Ensured consistent quadrupled braces
    ]
  }}
  // ... more objects for other words in the list
]

Word list: {word_list}
"""

IMAGE_GENERATION_PROMPT = """
Create a visually clear and educational image to illustrate the meaning of the word:
"{word}" (a word in Bosnian/Croatian/Serbian).
The image should help a language learner remember the word.
Avoid text or writing in the image.
"""

PROMPT_IMAGE_PROMPT_GENERATOR = """
You will receive a vocabulary word, its part of speech, and a short list of its core definitions or senses. 
Your task is to generate a prompt for an AI image generation model that will produce a pedagogically useful image 
for a language learning flashcard.

The image should visually communicate the meaning(s) of the word **without any text**, and must be suitable for learners 
to infer meaning from context.

Instructions for image generation prompt:
- If the word has multiple distinct meanings, depict them using separate comic panels or a single symbolic integration.
- Be specific and concrete about the visual scenes or scenarios that should appear.
- Choose a visual style appropriate to the word (e.g., cartoon for verbs and actions, diagram or metaphor for abstract nouns, photorealistic for common objects).
- Focus on clarity and pedagogical usefulness.

Return only the image generation prompt as a string. Do not include any extra text, comments, or formatting.

Example input:
{{
  "word": "spring",
  "pos": "noun",
  "definitions": [
    "a season between winter and summer",
    "a coiled object that bounces back when compressed",
    "a natural source of water coming from the ground"
  ]
}}

Expected output (image generation prompt):
"A three-panel cartoon showing: (1) blooming trees and people enjoying warm weather, (2) a hand pressing a metal coil that rebounds, and (3) water bubbling out of a rocky hillside in a forest. No text or labels. Clear, educational style suitable for language learning flashcards."

Now generate the image prompt for the following word:
{input_json}
"""
