Drawing Game v3 fixed package

Replace the previous Drawing Game files with these:

templates/drawing_game.html
static/css/drawing_game.css
static/js/drawing_game.js

If you already pasted the Drawing Game backend block into app.py, you do not strictly need to replace it, because this version keeps the same backend routes:
- /api/drawing-game/tts
- /api/drawing-game/transcribe
- /api/drawing-game/complete

But drawing_game_backend_block.py is included again in case you want the newest backend block too.

Fixes included:
1. Fixed the speech queue deadlock.
   The child can answer Star/Librarian and the character now responds immediately.

2. Fixed Done Drawing progression.
   The Done button no longer depends on the stuck speech queue, so it should trigger comments and move to the next round.

3. Fixed Librarian mouth image names.
   The JS now uses:
   - librarian-mouth-closed.png
   - librarian-mouth-small.png
   - librarian-mouth-medium.png
   - librarian-mouth-wide-open.png

4. Fixed Librarian face crop.
   The Librarian is moved down and resized so her face should appear in the video tile.

5. Fixed Star double-mouth overlap during transition.
   The side panel is hidden until the intro split-screen disappears, so the intro Star and main Star do not overlap.

6. Removed exact captions.
   Only a tiny status like "Star is talking" is shown, not the words being spoken.
