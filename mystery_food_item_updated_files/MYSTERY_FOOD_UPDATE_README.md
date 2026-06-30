# Mystery Food Item update

Files included:

- `app_updated.py` — full copy of your uploaded `app.py` with the Mystery Food Item section replaced.
- `mystery_food_item_app_section.py` — only the replaceable Mystery Food Item section, starting at `# Mystery Food Item — Leo restaurant guessing game` and ending right before `def generate_librarian_voice_elevenlabs(text):`.
- `mystery_food_item.html` — updated template reference version numbers.
- `mystery_food_item.css` — cleaned restaurant page CSS.
- `mystery_food_item.js` — updated restaurant JS with `guess_reaction` timing support.

Use either:

1. Replace your whole `app.py` with `app_updated.py`, then rename it to `app.py`, or
2. Paste `mystery_food_item_app_section.py` over the matching Mystery Food Item section in your current `app.py`.

Place the frontend files here:

- `templates/mystery_food_item.html`
- `static/css/mystery_food_item.css`
- `static/js/mystery_food_item.js`

Main behavior changes:

- 9 total rounds.
- Rounds 1–3 use forced-choice prompts only.
- Rounds 4–6 use easy short-answer prompts.
- Rounds 7–9 use open clue prompts.
- Leo does not ask the child yes/no questions.
- Guessing now uses: “Say [food] if I got it, or give Leo one more clue if I missed it.”
- The food profile list and tag scoring were expanded so Leo has a better chance of narrowing foods down accurately.
