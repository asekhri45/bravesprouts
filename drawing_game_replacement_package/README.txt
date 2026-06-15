Drawing Game replacement package v2

This replaces the earlier Drawing Game package completely.

Put these files here:
- drawing_game.html -> templates/drawing_game.html
- drawing_game.css -> static/css/drawing_game.css
- drawing_game.js -> static/js/drawing_game.js
- drawing_game_backend_block.py -> paste into app.py
- db_insert_drawing_game.sql -> run once if drawing_game is not already in your activity table

What changed from the first version:
- Removed the visible How to Play card.
- Removed visible captions/speech bubble text for Star/Librarian.
- Librarian introduces every round: flower, silly face, book cover, animal, final picture.
- Star is active during the drawing: asks small natural questions like color, part, what to add next.
- No "you can say yes/no" pressure line after "What do you think, [child]?"
- Librarian asks "Do you two want to play again?"
- Star redirects that question to the child with "What do you think, [child]?"
- Later, Librarian directly asks the child by name.
- Ending sends the child to the next activity after one final round.

Assets assumed:
- static/images/starpfp.png
- static/images/matching-star.png
- static/images/librarianpfp.png
- static/images/librarian.png
- static/images/librarybg.png
- static/images/roombg.png
- static/images/mouth-closed.png
- static/images/mouth-small.png
- static/images/mouth-medium.png
- static/images/mouth-wide-open.png
- static/images/ringtone.mp3
- static/images/call_accepted.mp3

If your librarian files have different names, update drawing_game.html and drawing_game.css.
