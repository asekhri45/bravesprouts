Toy Sorting Game package

Put these files here:
- toy_sorting_game.html -> templates/toy_sorting_game.html
- toy_sorting_game.css -> static/css/toy_sorting_game.css
- toy_sorting_game.js -> static/js/toy_sorting_game.js
- toy_sorting_game_backend_block.py -> paste into app.py near your other game backend blocks
- db_insert_or_update_toy_sorting_game.sql -> run only if your activity table does not already point toy_sorting_game to toy_sorting_game.html

Premise:
- Librarian is the main speaker.
- Librarian introduces the Toy Store Worker.
- The child sorts toys by clicking a toy, then clicking the right bin.
- Toy Store Worker gradually participates more.
- Later Toy Store Worker asks the child directly.
- After the final round, completion redirects to the next activity in the database order, which should be Toy Trivia Game if this activity is placed before toy_trivia_game.

Assets assumed:
- static/images/librarianpfp.png
- static/images/librarian.png
- static/images/librarian-mouth-closed.png
- static/images/librarian-mouth-small.png
- static/images/librarian-mouth-medium.png
- static/images/librarian-mouth-wide.png
- static/images/librarybg.png

- static/images/toy-store-worker-pfp.png
- static/images/toy-store-worker.png
- static/images/toy-store-worker-mouth-closed.png
- static/images/toy-store-worker-mouth-small.png
- static/images/toy-store-worker-mouth-medium.png
- static/images/toy-store-worker-mouth-wide.png
- static/images/toy-store-bg.png

- static/images/ringtone.mp3
- static/images/call_accepted.mp3

If your Toy Store Worker files use different names, update:
- toy_sorting_game.html image src paths
- toy_sorting_game.css background url paths
- getMouthSrc() in toy_sorting_game.js

Voice env vars:
- LIBRARIAN_VOICE_ID or BOOK_GUESSING_VOICE_ID for Librarian
- TOY_WORKER_VOICE_ID or TOY_TRIVIA_VOICE_ID for Toy Store Worker
