-- Drawing Game database setup
-- First, inspect your current journey order:
SELECT activity_id, scene_id, activity_order, activity_name, template_file, is_active
FROM activity
ORDER BY scene_id ASC, activity_order ASC;

-- If book_guessing_game already exists, Drawing Game should go immediately BEFORE it.
-- Replace values like description/time_recommended/character_active if your table uses different naming.
-- This assumes activity has these columns:
-- scene_id, activity_name, description, activity_order, level_of_realism,
-- total_levels_of_realism, time_recommended, character_active, template_file, is_active

UPDATE activity
SET activity_order = activity_order + 1
WHERE scene_id = (
    SELECT scene_id
    FROM activity
    WHERE activity_name = 'book_guessing_game'
    LIMIT 1
)
AND activity_order >= (
    SELECT activity_order
    FROM activity
    WHERE activity_name = 'book_guessing_game'
    LIMIT 1
);

INSERT INTO activity (
    scene_id,
    activity_name,
    description,
    activity_order,
    level_of_realism,
    total_levels_of_realism,
    time_recommended,
    character_active,
    template_file,
    is_active
)
SELECT
    scene_id,
    'drawing_game',
    'Draw simple pictures with Star while the Librarian slowly joins the conversation.',
    activity_order - 1,
    level_of_realism,
    total_levels_of_realism,
    '5-8 min',
    'Star + Librarian',
    'drawing_game.html',
    1
FROM activity
WHERE activity_name = 'book_guessing_game'
LIMIT 1;

-- For existing users, this creates a locked progress row for Drawing Game.
INSERT OR IGNORE INTO progress (
    user_id,
    activity_id,
    is_unlocked,
    is_completed,
    words_spoken,
    minutes_spoken,
    active_minutes,
    time_spent_on_activity
)
SELECT
    u.user_id,
    a.activity_id,
    0,
    0,
    0,
    0,
    0,
    0
FROM users u
CROSS JOIN activity a
WHERE a.activity_name = 'drawing_game';
