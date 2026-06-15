-- Toy Sorting Game database setup for your current schema.
-- Run this only if toy_sorting_game is not already correctly set up.

BEGIN TRANSACTION;

-- If toy_sorting_game does not exist, make space immediately before toy_trivia_game.
UPDATE activity
SET activity_order = activity_order + 1
WHERE scene_id = (
    SELECT scene_id
    FROM activity
    WHERE activity_name = 'toy_trivia_game'
    LIMIT 1
)
AND activity_order >= (
    SELECT activity_order
    FROM activity
    WHERE activity_name = 'toy_trivia_game'
    LIMIT 1
)
AND NOT EXISTS (
    SELECT 1
    FROM activity
    WHERE activity_name = 'toy_sorting_game'
);

-- Insert Toy Sorting Game immediately before Toy Trivia Game if missing.
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
    'toy_sorting_game',
    'Sort toys with the Librarian while the Toy Store Worker slowly joins the conversation.',
    activity_order - 1,
    level_of_realism,
    1,
    8,
    'Librarian + Toy Store Worker',
    total_levels_of_realism,
    'toy_sorting_game.html'
FROM activity
WHERE activity_name = 'toy_trivia_game'
AND NOT EXISTS (
    SELECT 1
    FROM activity
    WHERE activity_name = 'toy_sorting_game'
)
LIMIT 1;

-- If toy_sorting_game already exists, just make sure it points at the right template.
UPDATE activity
SET
    description = 'Sort toys with the Librarian while the Toy Store Worker slowly joins the conversation.',
    is_active = 1,
    time_recommended = 8,
    character_active = 'Librarian + Toy Store Worker',
    template_file = 'toy_sorting_game.html'
WHERE activity_name = 'toy_sorting_game';

-- Existing users need a progress row for the activity.
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
WHERE a.activity_name = 'toy_sorting_game';

COMMIT;

-- Check the result.
SELECT activity_id, scene_id, activity_order, activity_name, template_file, is_active
FROM activity
ORDER BY scene_id ASC, activity_order ASC;
