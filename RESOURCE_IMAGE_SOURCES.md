# Parent Resources Image Sources

The Parent Resources / Parent Academy article pages use the existing
`static/images/sm_*.png` illustrations that already ship with MyBraveSprout
(added in commit `06a3e1c`, "resource lib + chat feature"). These are the
app's own custom-made illustrations, not third-party stock photography, so
no external sourcing was needed for this pass and no third-party license
applies.

Each article's image is wired up explicitly in `app.py` via
`PARENT_ACADEMY_CATEGORIES`, one illustration per topic (e.g.
`sm_brain_question.png` for "What Is Selective Mutism?",
`sm_whisper.png` for "Why Does My Child Whisper?"). The same mapping is
reused for the listing-page card art, the category-page card art, and the
individual article's hero image, so there is a single owned asset per
article rather than duplicated or externally hotlinked images.

## Compression pass

A handful of these illustrations were shipped at 1536x1024 (700KB-1.5MB
each) despite only ever being displayed at small thumbnail sizes (~90x70px)
or a capped ~340px-tall article hero. They were resized to a 900px max
dimension and re-saved as optimized PNG, cutting the combined size of the
9 largest files from ~11.5MB to ~5.8MB with no visible quality loss at
their display sizes. No image content was otherwise altered.

## Article hero photos (`static/images/resources/`)

The individual article pages (`templates/parent_academy_article.html`) were
redesigned into an editorial layout that intentionally does **not** reuse the
`sm_*.png` card illustrations for the hero image -- those stay on the listing
and category cards only. Instead, each article's hero uses one of 7 real
photos downloaded from Unsplash, all confirmed under the free **Unsplash
License** (free for commercial and non-commercial use, no attribution
required, though it's given here anyway) at the time of download. Each was
cropped to a consistent 3:2 landscape ratio, resized to 1600px wide, and
re-saved as compressed WebP (70-166KB each, down from multi-megabyte
originals).

Two candidates were reviewed and rejected before this final set: a
window-lit child portrait carrying refugee-camp context tags (not relevant
to this app and could read as exploitative if repurposed), a "child sitting
on a bed" photo that turned out to be a National Cancer Institute chemotherapy
photo, and a parent-and-child hand-holding photo that was actually
Unsplash+ (paid), not the free Unsplash License. None of these were used.

| File | Unsplash photo | Photographer | Used for theme |
|---|---|---|---|
| `classroom_bright.webp` | [A classroom filled with lots of desks and chairs](https://unsplash.com/photos/a-classroom-filled-with-lots-of-desks-and-chairs-Qw6wa96IvvQ) | Nathan Cima | School / classroom settings |
| `parent_child_conversation.webp` | [Mother and daughter are having a conversation](https://unsplash.com/photos/mother-and-daughter-are-having-a-conversation-E5hnL4kDBOc) | Vitaly Gariev | Quiet conversation, whispering, trusted people |
| `parent_child_reading.webp` | [Mother and son reading a book together on the couch](https://unsplash.com/photos/mother-and-son-reading-a-book-together-on-the-couch-bQz9R-K_Q40) | Vitaly Gariev | Home, comfort, parent-child bonding |
| `family_board_game.webp` | [Family playing board games](https://unsplash.com/photos/VJVsEnR_vNE) | Getty Images / Unsplash | Practice opportunities, praise vs. pressure |
| `family_walk_woods.webp` | [Family walking on a path through the woods](https://unsplash.com/photos/family-walking-on-a-path-through-the-woods-3dauJqwwvwQ) | Emma | Parent support, reducing pressure, setbacks |
| `child_thoughtful_table.webp` | [A little girl sitting at a table with her arms crossed](https://unsplash.com/photos/a-little-girl-sitting-at-a-table-with-her-arms-crossed-oGld087zm5M) | Evgeniy Alyoshin | Anxiety, freezing, withdrawal, science topics |
| `children_playing_field.webp` | [Children playing together outdoors in a field](https://unsplash.com/photos/children-playing-together-outdoors-in-a-field-EgKxEDymG2s) | Seljan Salimova | Peers, other children, social settings |

The slug-to-photo mapping lives in `app.py` as `ARTICLE_HERO_PHOTO_KEY` /
`RESOURCE_HERO_PHOTOS`. Photos are reused thoughtfully across articles that
share a theme rather than sourcing 31 individual images -- see the mapping in
`app.py` for exactly which article uses which photo.

## Homepage activity carousel (`static/images/*_home_optimized.webp`)

The homepage carousel uses cropped/compressed derivatives of the app's own
real gameplay screenshots (`static/images/<activity>_home_img.png`, left
untouched). Each was cropped to remove dashboard chrome (the "Back to
Dashboard" control bar) and, for Match Cards specifically, the child-name
turn-indicator panel ("Ivanka's Turn") was cropped out entirely -- the
optimized version shows only the card grid, with no name visible. Resized to
1200px max width and saved as WebP (23-71KB each, versus 1.7-7.2MB for the
source screenshots). See `HOMEPAGE_ACTIVITY_IMAGES` in `app.py`.

## If new images are needed later

If a future article needs an image that doesn't yet have a dedicated
illustration or photo, prefer:

- Unsplash, Pexels, Pixabay, or Wikimedia Commons (all offer royalty-free
  images compatible with commercial use without attribution, though citing
  the source here is still good practice).
- Gentle, neutral subject matter: learning, family support, communication,
  play, books, calm environments. Avoid identifiable photographs of
  distressed children, and double-check any photo's tags/description for
  unrelated sensitive context before reusing it here.
- Verify the license is the free tier (plain Unsplash License), not a paid
  "Unsplash+"/premium photo -- the page will say so explicitly.
- Download the file locally with a descriptive filename, compress/resize it
  before committing, and add an entry to this file recording the exact
  source URL, photographer, and license name.
