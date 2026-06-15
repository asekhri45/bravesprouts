-- Drawing Game database setup for your current schema.
-- Run this only once.

BEGIN TRANSACTION;

-- Move Book Guessing Game and any later activities down by 1,
-- but only if drawing_game does not already exist.
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
)
AND NOT EXISTS (
    SELECT 1
    FROM activity
    WHERE activity_name = 'drawing_game'
);

-- Insert Drawing Game immediately before Book Guessing Game.
INSERT INTO activity (
    scene_id,
    activity_name,
    description,
    activity_order,
    level_of_realism,
    is_active,
    time_recommended,
    character_active,
    total_levels_of_realism,
    template_file
)
SELECT
    scene_id,
    'drawing_game',
    'Draw simple pictures with Star while the Librarian slowly joins the conversation.',
    activity_order - 1,
    level_of_realism,
    1,
    8,
    'Star + Librarian',
    total_levels_of_realism,
    'drawing_game.html'
FROM activity
WHERE activity_name = 'book_guessing_game'
AND NOT EXISTS (
    SELECT 1
    FROM activity
    WHERE activity_name = 'drawing_game'
)
LIMIT 1;

-- Existing users need a progress row for the new activity.
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

COMMIT;

-- Check the result.
SELECT activity_id, scene_id, activity_order, activity_name, template_file, is_active
FROM activity
ORDER BY scene_id ASC, activity_order ASC;
