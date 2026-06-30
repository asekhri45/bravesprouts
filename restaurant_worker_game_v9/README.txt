Restaurant Worker Game v9

Replace these files in your project:
- static/js/restaurant_worker_game.js
- static/css/restaurant_worker_game.css

Changes in v9:
- Toned down Leo's casual prompts in rounds 5 and 6 to one preference prompt per order.
- Teacher now keeps giving gentle “let me know when you’re done” reminders in later rounds too.
- Removed standalone Ready/Check stages globally, including grilled cheese and kids meal.
- Leo no longer asks the move-on choice after every single step in rounds 5-8; he alternates between asking and simply moving to the next step.
- At the end of orders in rounds 5-8, Leo asks whether to help with another order or be done for the day.
- No app.py patch is included.
