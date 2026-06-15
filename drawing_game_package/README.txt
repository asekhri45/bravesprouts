Drawing Game package for BraveSprouts

Files:
1. drawing_game.html
   Put in: templates/drawing_game.html

2. drawing_game.css
   Put in: static/css/drawing_game.css

3. drawing_game.js
   Put in: static/js/drawing_game.js

4. drawing_game_backend_block.py
   Copy/paste this block into app.py after the matching-game backend block.

5. db_insert_drawing_game.sql
   Run only after checking your actual activity table schema.

Assets assumed:
- static/images/starpfp.png
- static/images/matching-star.png
- static/images/mouth-closed.png
- static/images/mouth-small.png
- static/images/mouth-medium.png
- static/images/mouth-wide-open.png
- static/images/roombg.png
- static/images/librarybg.png
- static/images/librarian.png
- static/images/librarianpfp.png
- static/images/ringtone.mp3
- static/images/call_accepted.mp3

If your librarian files have different names, change them in drawing_game.html and drawing_game.css.

Progression:
Round 1: Star leads. Librarian only cheers.
Round 2: Star asks the child a tiny answer.
Round 3: Librarian asks the group; Star redirects to the child.
Round 4: Librarian asks the child directly.
Ending: Librarian asks for one more drawing round, then the app completes the activity and redirects to the next activity in journey order.
