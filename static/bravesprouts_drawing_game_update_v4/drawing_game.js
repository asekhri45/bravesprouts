document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".drawing-page");
  const activityId = Number(page?.dataset.activityId || 7);
  const childName = (page?.dataset.childName || "there").trim() || "there";

  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const introScreen = document.getElementById("introScreen");
  const zoomStage = document.getElementById("zoomStage");

  const promptTitle = document.getElementById("promptTitle");
  const promptText = document.getElementById("promptText");
  const roundNumber = document.getElementById("roundNumber");
  const quietStatusText = document.getElementById("quietStatusText");

  const starVideoTile = document.getElementById("starVideoTile");
  const librarianVideoTile = document.getElementById("librarianVideoTile");
  const introStarTile = document.getElementById("introStarTile");
  const introLibrarianTile = document.getElementById("introLibrarianTile");

  const micControl = document.getElementById("micControl");
  const hangupButton = document.getElementById("hangupButton");

  const canvas = document.getElementById("drawingCanvas");
  const ctx = canvas.getContext("2d");
  const doneDrawingBtn = document.getElementById("doneDrawingBtn");
  const clearCanvasBtn = document.getElementById("clearCanvasBtn");

  const toolButtons = document.querySelectorAll("[data-tool]");
  const colorButtons = document.querySelectorAll("[data-color]");

  /*
    Drawing Game redesign:
    - Star is the familiar safety partner.
    - The Teacher uses the existing "librarian" backend/voice/assets internally.
    - Four scenes build gradually: flower garden, house, tree, school.
    - Each scene is one round. Each round has four drawing parts.
    - Speech is encouraged, never required. Silence never blocks the activity.
  */

  const TEACHER_ACTOR = "librarian";
  const TARGET_SOCIAL_ROUNDS = 4;

  const COLOR_NAMES = {
    "#7c3aed": "purple",
    "#2563eb": "blue",
    "#0ea5e9": "sky blue",
    "#14b8a6": "teal",
    "#16a34a": "green",
    "#84cc16": "light green",
    "#facc15": "yellow",
    "#f97316": "orange",
    "#ef4444": "red",
    "#ec4899": "pink",
    "#a855f7": "violet",
    "#92400e": "brown",
    "#6b7280": "gray",
    "#111827": "black"
  };

  const COLORS = {
    purple: "#7c3aed",
    blue: "#2563eb",
    skyBlue: "#0ea5e9",
    teal: "#14b8a6",
    green: "#16a34a",
    lime: "#84cc16",
    yellow: "#facc15",
    orange: "#f97316",
    red: "#ef4444",
    pink: "#ec4899",
    violet: "#a855f7",
    brown: "#92400e",
    gray: "#6b7280",
    black: "#111827"
  };

  const drawingScenes = [
    {
      id: "flower_garden",
      name: "Flower Garden",
      sceneIntro: "Let's make a flower garden together.",
      newSceneLine: "First, let's make a flower garden.",
      completeLine: "The flower garden is finished.",
      stages: [
        {
          id: "flower",
          spokenName: "flower",
          title: "Draw a flower",
          text: "Draw one simple flower first.",
          partText: "Part 1 of 4",
          palette: [COLORS.pink, COLORS.yellow, COLORS.green],
          colorIdeas: {
            [COLORS.green]: "the stem or leaves",
            [COLORS.pink]: "the petals",
            [COLORS.yellow]: "the middle of the flower"
          },
          starLead: [
            "Let's draw the flower first. You can use pink, yellow, or green.",
            "We'll start with one flower. You can put it anywhere on the page.",
            "First, let's make the flower. You can start with the stem, middle, or petals."
          ],
          starChoice: [
            "You can choose any flower part first.",
            "Start with whichever part feels easiest.",
            "I'll stay here while you make the flower."
          ],
          teacherComment: [
            "I will watch while you and Star make the flower, {child}.",
            "I like seeing how you and Star start the flower, {child}.",
            "This is a nice first part for a garden, {child}."
          ],
          teacherWonder: [
            "I wonder what color this flower will be, {child}.",
            "Maybe the flower will have a bright middle, {child}.",
            "I wonder if this flower will have a tall stem, {child}."
          ],
          teacherToStar: [
            "Star, do you think the flower should have petals first?",
            "Star, do you think the stem should be tall or short?",
            "Star, what color might fit the flower?"
          ],
          teacherDirect: [
            "{child}, what color should the flower be?",
            "{child}, should the flower have big petals or little petals?",
            "What should we add to the flower first, {child}?"
          ],
          donePraise: [
            "That flower looks sweet, {child}.",
            "Nice flower, {child}.",
            "I like that flower, {child}."
          ]
        },
        {
          id: "grass",
          spokenName: "grass",
          title: "Add grass",
          text: "Add grass under or around the flower.",
          partText: "Part 2 of 4",
          palette: [COLORS.green, COLORS.lime],
          colorIdeas: {
            [COLORS.green]: "darker grass",
            [COLORS.lime]: "light green grass"
          },
          starLead: [
            "Now let's add grass. The flower needs somewhere to grow.",
            "Next, we can put grass under the flower.",
            "Let's give the flower some grass around it."
          ],
          starChoice: [
            "You can make a little grass or a lot of grass.",
            "The grass can go anywhere near the flower.",
            "I'll stay with you while you add the grass."
          ],
          teacherComment: [
            "Grass is a good next part for the flower, {child}.",
            "I like that the flower is getting a place to grow, {child}.",
            "This is starting to look like a garden, {child}."
          ],
          teacherWonder: [
            "I wonder if the grass will be light green or dark green, {child}.",
            "Maybe the grass can go right under the flower, {child}.",
            "I wonder how much grass this flower needs, {child}."
          ],
          teacherToStar: [
            "Star, do you think the grass should go under the flower?",
            "Star, should the grass be small or go across the page?",
            "Star, where should the grass go?"
          ],
          teacherDirect: [
            "{child}, should the grass be little or big?",
            "Where should the grass go, {child}?",
            "{child}, should the grass go across the picture?"
          ],
          donePraise: [
            "The flower has grass now, {child}.",
            "Nice grass, {child}.",
            "That makes the flower look like it is growing, {child}."
          ]
        },
        {
          id: "sun",
          spokenName: "sun",
          title: "Add a sun",
          text: "Add a sun near the flower garden.",
          partText: "Part 3 of 4",
          palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {
            [COLORS.yellow]: "the sun",
            [COLORS.orange]: "warm sun rays"
          },
          starLead: [
            "Now let's add the sun. Flowers like sunshine.",
            "Next, we can draw a sun for the flower.",
            "Let's put a sunny part in the garden."
          ],
          starChoice: [
            "You can make the sun big or small.",
            "The sun can go wherever you want.",
            "I'll stay here while you add the sun."
          ],
          teacherComment: [
            "A sun is a nice idea for the garden, {child}.",
            "Flowers do like sunshine, {child}.",
            "The picture is getting bright, {child}."
          ],
          teacherWonder: [
            "I wonder if the sun will be yellow or orange, {child}.",
            "Maybe the sun can have little rays, {child}.",
            "I wonder where the sun will go, {child}."
          ],
          teacherToStar: [
            "Star, do you think the sun should be big or small?",
            "Star, should the sun have rays?",
            "Star, where might the sun fit?"
          ],
          teacherDirect: [
            "{child}, should the sun be big or small?",
            "Where should the sun go, {child}?",
            "{child}, should the sun have rays?"
          ],
          donePraise: [
            "That sun makes the garden bright, {child}.",
            "Nice sun, {child}.",
            "I like the sunshine in the picture, {child}."
          ]
        },
        {
          id: "butterfly",
          spokenName: "butterfly",
          title: "Add a butterfly",
          text: "Add a simple butterfly near the flower.",
          partText: "Part 4 of 4",
          palette: [COLORS.purple, COLORS.blue, COLORS.pink, COLORS.yellow],
          colorIdeas: {
            [COLORS.purple]: "butterfly wings",
            [COLORS.blue]: "butterfly wings",
            [COLORS.pink]: "a colorful butterfly",
            [COLORS.yellow]: "a bright butterfly"
          },
          starLead: [
            "For the last part, let's add a butterfly near the flower.",
            "Now we can add a little butterfly by the flower.",
            "Let's finish the garden with a butterfly."
          ],
          starChoice: [
            "You can make the butterfly any color here.",
            "The butterfly can be near the flower.",
            "I'll stay with you while you add the butterfly."
          ],
          teacherComment: [
            "A butterfly is a sweet final part, {child}.",
            "I like butterflies near flowers, {child}.",
            "That will make the garden feel friendly, {child}."
          ],
          teacherWonder: [
            "I wonder what color the butterfly will be, {child}.",
            "Maybe the butterfly will have bright wings, {child}.",
            "I wonder if the butterfly will be close to the flower, {child}."
          ],
          teacherToStar: [
            "Star, do you think the butterfly should be close to the flower?",
            "Star, what color could the butterfly be?",
            "Star, should the butterfly have big wings or little wings?"
          ],
          teacherDirect: [
            "{child}, what color should the butterfly be?",
            "{child}, should the butterfly be near the flower?",
            "Should the butterfly have big wings or little wings, {child}?"
          ],
          donePraise: [
            "The butterfly looks nice near the flower, {child}.",
            "Nice butterfly, {child}.",
            "That butterfly makes the garden feel finished, {child}."
          ]
        }
      ]
    },
    {
      id: "house_yard",
      name: "House Scene",
      sceneIntro: "Let's make a house scene together.",
      newSceneLine: "Now let's make a house scene.",
      completeLine: "The house scene is finished.",
      stages: [
        {
          id: "house",
          spokenName: "house",
          title: "Draw a house",
          text: "Draw a simple complete house.",
          partText: "Part 1 of 4",
          palette: [COLORS.red, COLORS.brown, COLORS.blue],
          colorIdeas: {
            [COLORS.red]: "the roof or door",
            [COLORS.brown]: "the house walls",
            [COLORS.blue]: "the windows"
          },
          starLead: [
            "Let's start this scene with a house. You can make the whole house your way.",
            "First, let's draw a house. It can be simple.",
            "We'll make a house first, with any shape you want."
          ],
          starChoice: [
            "You can start with the roof, walls, door, or windows.",
            "Start with the part of the house that feels easiest.",
            "I'll stay here while you make the house."
          ],
          teacherComment: [
            "I like starting with the whole house, {child}.",
            "A house is a clear first part for this scene, {child}.",
            "I will watch while you and Star make the house, {child}."
          ],
          teacherWonder: [
            "I wonder what color the house will be, {child}.",
            "Maybe this house will have a bright door, {child}.",
            "I wonder if the house will have windows, {child}."
          ],
          teacherToStar: [
            "Star, do you think the house should have a red roof?",
            "Star, should the house have one window or two?",
            "Star, where might the door go?"
          ],
          teacherDirect: [
            "{child}, what color should the house be?",
            "{child}, should the house have a door?",
            "Where should the windows go, {child}?"
          ],
          donePraise: [
            "That house looks good, {child}.",
            "Nice house, {child}.",
            "I like the house you made, {child}."
          ]
        },
        {
          id: "yard",
          spokenName: "grass",
          title: "Add grass",
          text: "Add grass around the house.",
          partText: "Part 2 of 4",
          palette: [COLORS.green, COLORS.lime],
          colorIdeas: {
            [COLORS.green]: "the yard",
            [COLORS.lime]: "light green grass"
          },
          starLead: [
            "Now let's add grass around the house.",
            "The house can have a yard now.",
            "Let's give the house some grass."
          ],
          starChoice: [
            "You can put grass under or around the house.",
            "The yard can be small or big.",
            "I'll stay with you while you add the grass."
          ],
          teacherComment: [
            "A yard is a good next part, {child}.",
            "The house is getting a place outside, {child}.",
            "That grass can make the house feel cozy, {child}."
          ],
          teacherWonder: [
            "I wonder if the yard will be light green or dark green, {child}.",
            "Maybe the grass can go around the house, {child}.",
            "I wonder how big the yard will be, {child}."
          ],
          teacherToStar: [
            "Star, should the yard go under the house?",
            "Star, do you think the grass should be light or dark green?",
            "Star, where should the yard go?"
          ],
          teacherDirect: [
            "{child}, should the yard be little or big?",
            "Where should the grass go, {child}?",
            "{child}, should the grass go around the house?"
          ],
          donePraise: [
            "The house has grass now, {child}.",
            "Nice yard, {child}.",
            "That makes the house feel outside, {child}."
          ]
        },
        {
          id: "sun",
          spokenName: "sun",
          title: "Add a sun",
          text: "Add a sun for the house scene.",
          partText: "Part 3 of 4",
          palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {
            [COLORS.yellow]: "the sun",
            [COLORS.orange]: "sun rays"
          },
          starLead: [
            "Now let's add a sun for the house.",
            "The house scene can have sunshine now.",
            "Let's put a sun somewhere in the picture."
          ],
          starChoice: [
            "You can make the sun big or small.",
            "The sun can go wherever you want.",
            "I'll stay here while you add it."
          ],
          teacherComment: [
            "A sunny house scene sounds nice, {child}.",
            "The sun will brighten the house, {child}.",
            "I like adding sunshine here, {child}."
          ],
          teacherWonder: [
            "I wonder where the sun will go, {child}.",
            "Maybe the sun will have orange rays, {child}.",
            "I wonder if the sun will be big or small, {child}."
          ],
          teacherToStar: [
            "Star, do you think the sun should be big or small?",
            "Star, should the sun be near the house?",
            "Star, should the sun have rays?"
          ],
          teacherDirect: [
            "{child}, where should the sun go?",
            "Should the sun be big or small, {child}?",
            "{child}, should the sun have rays?"
          ],
          donePraise: [
            "The house has sunshine now, {child}.",
            "Nice sun, {child}.",
            "That sun looks warm, {child}."
          ]
        },
        {
          id: "tree",
          spokenName: "tree",
          title: "Add a tree",
          text: "Add a simple tree near the house.",
          partText: "Part 4 of 4",
          palette: [COLORS.brown, COLORS.green, COLORS.lime],
          colorIdeas: {
            [COLORS.brown]: "the tree trunk",
            [COLORS.green]: "tree leaves",
            [COLORS.lime]: "light green leaves"
          },
          starLead: [
            "For the last part, let's add a tree near the house.",
            "Now we can put a tree by the house.",
            "Let's finish the house scene with a tree."
          ],
          starChoice: [
            "You can make the tree tall or small.",
            "The tree can go near the house or far away.",
            "I'll stay with you while you add the tree."
          ],
          teacherComment: [
            "A tree is a nice final part for the yard, {child}.",
            "I like trees near houses, {child}.",
            "That will make the scene feel fuller, {child}."
          ],
          teacherWonder: [
            "I wonder if the tree will be tall or short, {child}.",
            "Maybe the tree will have lots of leaves, {child}.",
            "I wonder where the tree will go, {child}."
          ],
          teacherToStar: [
            "Star, should the tree go next to the house?",
            "Star, should the tree be tall or short?",
            "Star, do you think the tree needs lots of leaves?"
          ],
          teacherDirect: [
            "{child}, should the tree be tall or short?",
            "Where should the tree go, {child}?",
            "{child}, should the tree have lots of leaves?"
          ],
          donePraise: [
            "The tree looks nice by the house, {child}.",
            "Nice tree, {child}.",
            "That tree finishes the house scene, {child}."
          ]
        }
      ]
    },
    {
      id: "tree_park",
      name: "Tree Scene",
      sceneIntro: "Let's make a tree scene together.",
      newSceneLine: "Now let's make a tree scene.",
      completeLine: "The tree scene is finished.",
      stages: [
        {
          id: "tree",
          spokenName: "tree",
          title: "Draw a tree",
          text: "Draw one complete tree first.",
          partText: "Part 1 of 4",
          palette: [COLORS.brown, COLORS.green, COLORS.lime],
          colorIdeas: {
            [COLORS.brown]: "the trunk or branches",
            [COLORS.green]: "leaves",
            [COLORS.lime]: "light green leaves"
          },
          starLead: [
            "Let's start with one full tree. You can draw the trunk and leaves your way.",
            "First, let's draw a tree. It can be simple.",
            "We'll make one tree first, with a trunk and leaves."
          ],
          starChoice: [
            "You can start with the trunk or the leaves.",
            "Start with whichever tree part feels easiest.",
            "I'll stay here while you make the tree."
          ],
          teacherComment: [
            "I like starting with the whole tree, {child}.",
            "A tree is a nice first part for this scene, {child}.",
            "I will watch while you and Star make the tree, {child}."
          ],
          teacherWonder: [
            "I wonder if the tree will be tall or short, {child}.",
            "Maybe this tree will have lots of leaves, {child}.",
            "I wonder what color the leaves will be, {child}."
          ],
          teacherToStar: [
            "Star, do you think the tree should be tall or short?",
            "Star, should the tree have lots of leaves?",
            "Star, should the trunk be big or small?"
          ],
          teacherDirect: [
            "{child}, should the tree be tall or short?",
            "{child}, should the tree have lots of leaves?",
            "What should we draw first on the tree, {child}?"
          ],
          donePraise: [
            "That tree looks good, {child}.",
            "Nice tree, {child}.",
            "I like the tree you made, {child}."
          ]
        },
        {
          id: "grass",
          spokenName: "grass",
          title: "Add grass",
          text: "Add grass under or around the tree.",
          partText: "Part 2 of 4",
          palette: [COLORS.green, COLORS.lime],
          colorIdeas: {
            [COLORS.green]: "grass",
            [COLORS.lime]: "light green grass"
          },
          starLead: [
            "Now let's add grass under the tree.",
            "The tree can have grass around it now.",
            "Let's give the tree some ground."
          ],
          starChoice: [
            "The grass can be small or go across the page.",
            "You can put the grass anywhere under the tree.",
            "I'll stay with you while you add the grass."
          ],
          teacherComment: [
            "Grass fits nicely with a tree, {child}.",
            "The tree is getting a place to grow, {child}.",
            "That grass will help the scene, {child}."
          ],
          teacherWonder: [
            "I wonder if the grass will be light or dark green, {child}.",
            "Maybe the grass can sit under the tree, {child}.",
            "I wonder how much grass the tree needs, {child}."
          ],
          teacherToStar: [
            "Star, should the grass go under the tree?",
            "Star, do you think the grass should be light or dark green?",
            "Star, where should the grass go?"
          ],
          teacherDirect: [
            "Where should the grass go, {child}?",
            "{child}, should the grass be little or big?",
            "Should the grass go under the tree, {child}?"
          ],
          donePraise: [
            "The tree has grass now, {child}.",
            "Nice grass, {child}.",
            "That makes the tree look like it is growing, {child}."
          ]
        },
        {
          id: "sun",
          spokenName: "sun",
          title: "Add a sun",
          text: "Add a sun near the tree.",
          partText: "Part 3 of 4",
          palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {
            [COLORS.yellow]: "the sun",
            [COLORS.orange]: "sun rays"
          },
          starLead: [
            "Now let's add a sun for the tree.",
            "The tree can have sunshine now.",
            "Let's put a sun somewhere near the tree."
          ],
          starChoice: [
            "You can make the sun big or small.",
            "The sun can go wherever you want.",
            "I'll stay here while you add the sun."
          ],
          teacherComment: [
            "Sunshine is nice for a tree, {child}.",
            "The tree scene is getting bright, {child}.",
            "I like adding a sun here, {child}."
          ],
          teacherWonder: [
            "I wonder where the sun will go, {child}.",
            "Maybe the sun can have orange rays, {child}.",
            "I wonder if the sun will be big or small, {child}."
          ],
          teacherToStar: [
            "Star, do you think the sun should be big or small?",
            "Star, should the sun be near the tree?",
            "Star, should the sun have rays?"
          ],
          teacherDirect: [
            "Where should the sun go, {child}?",
            "{child}, should the sun be big or small?",
            "Should the sun have rays, {child}?"
          ],
          donePraise: [
            "The tree has sunshine now, {child}.",
            "Nice sun, {child}.",
            "That sun looks warm, {child}."
          ]
        },
        {
          id: "birds",
          spokenName: "birds",
          title: "Add birds",
          text: "Add simple birds near the tree.",
          partText: "Part 4 of 4",
          palette: [COLORS.black, COLORS.blue, COLORS.gray],
          colorIdeas: {
            [COLORS.black]: "little bird shapes",
            [COLORS.blue]: "blue birds",
            [COLORS.gray]: "soft gray birds"
          },
          starLead: [
            "For the last part, let's add a few simple birds near the tree.",
            "Now we can draw little birds by the tree.",
            "Let's finish the tree scene with birds."
          ],
          starChoice: [
            "Birds can be very simple, even little curved lines.",
            "You can put the birds anywhere near the tree.",
            "I'll stay with you while you add the birds."
          ],
          teacherComment: [
            "Birds are a nice final part near a tree, {child}.",
            "I like birds around trees, {child}.",
            "That will make the tree scene feel alive, {child}."
          ],
          teacherWonder: [
            "I wonder where the birds will go, {child}.",
            "Maybe the birds will be small, {child}.",
            "I wonder how many birds there will be, {child}."
          ],
          teacherToStar: [
            "Star, should the birds be close to the tree?",
            "Star, do you think the birds should be small?",
            "Star, where could the birds go?"
          ],
          teacherDirect: [
            "{child}, where should the birds go?",
            "{child}, should the birds be big or small?",
            "How many birds should we add, {child}?"
          ],
          donePraise: [
            "The birds look nice near the tree, {child}.",
            "Nice birds, {child}.",
            "That finishes the tree scene, {child}."
          ]
        }
      ]
    },
    {
      id: "school_scene",
      name: "School Scene",
      sceneIntro: "Let's make a school scene together.",
      newSceneLine: "Now let's make a school scene.",
      completeLine: "The school scene is finished.",
      stages: [
        {
          id: "school",
          spokenName: "school",
          title: "Draw a school",
          text: "Draw a simple complete school building.",
          partText: "Part 1 of 4",
          palette: [COLORS.red, COLORS.brown, COLORS.blue],
          colorIdeas: {
            [COLORS.red]: "the school roof or door",
            [COLORS.brown]: "the school building",
            [COLORS.blue]: "school windows"
          },
          starLead: [
            "Let's start this scene with a school. It can be a simple building.",
            "First, let's draw a school. You can make it your way.",
            "We'll make a school first, with a door or windows if you want."
          ],
          starChoice: [
            "You can start with the building, door, roof, or windows.",
            "Start with whichever school part feels easiest.",
            "I'll stay here while you make the school."
          ],
          teacherComment: [
            "I like starting with the school building, {child}.",
            "This is a nice first part for a school scene, {child}.",
            "I will watch while you and Star make the school, {child}."
          ],
          teacherWonder: [
            "I wonder what color the school will be, {child}.",
            "Maybe the school will have windows, {child}.",
            "I wonder where the door will go, {child}."
          ],
          teacherToStar: [
            "Star, do you think the school should have a door?",
            "Star, should the school have windows?",
            "Star, where might the school door go?"
          ],
          teacherDirect: [
            "{child}, what color should the school be?",
            "{child}, should the school have windows?",
            "Where should the door go, {child}?"
          ],
          donePraise: [
            "That school looks nice, {child}.",
            "Nice school building, {child}.",
            "I like the school you made, {child}."
          ]
        },
        {
          id: "school_grass",
          spokenName: "grass",
          title: "Add grass",
          text: "Add grass outside the school.",
          partText: "Part 2 of 4",
          palette: [COLORS.green, COLORS.lime],
          colorIdeas: {
            [COLORS.green]: "the school grass",
            [COLORS.lime]: "light green grass"
          },
          starLead: [
            "Now let's add grass outside the school.",
            "The school can have grass around it now.",
            "Let's give the school some outside space."
          ],
          starChoice: [
            "You can put the grass under or around the school.",
            "The grass can be small or go across the page.",
            "I'll stay with you while you add the grass."
          ],
          teacherComment: [
            "Grass outside the school is a good next part, {child}.",
            "The school is getting a place outside, {child}.",
            "I like the school scene growing, {child}."
          ],
          teacherWonder: [
            "I wonder if the grass will be light green or dark green, {child}.",
            "Maybe the grass can go in front of the school, {child}.",
            "I wonder how much grass the school needs, {child}."
          ],
          teacherToStar: [
            "Star, should the grass go in front of the school?",
            "Star, do you think the grass should be light or dark green?",
            "Star, where should the grass go?"
          ],
          teacherDirect: [
            "Where should the grass go, {child}?",
            "{child}, should the grass be little or big?",
            "Should the grass go in front of the school, {child}?"
          ],
          donePraise: [
            "The school has grass now, {child}.",
            "Nice grass, {child}.",
            "That makes the school scene feel outside, {child}."
          ]
        },
        {
          id: "school_sun",
          spokenName: "sun",
          title: "Add a sun",
          text: "Add a sun near the school.",
          partText: "Part 3 of 4",
          palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {
            [COLORS.yellow]: "the sun",
            [COLORS.orange]: "sun rays"
          },
          starLead: [
            "Now let's add a sun for the school scene.",
            "The school can have sunshine now.",
            "Let's put a sun somewhere near the school."
          ],
          starChoice: [
            "You can make the sun big or small.",
            "The sun can go wherever you want.",
            "I'll stay here while you add the sun."
          ],
          teacherComment: [
            "A sunny school scene feels cheerful, {child}.",
            "The school is getting bright, {child}.",
            "I like adding sunshine here, {child}."
          ],
          teacherWonder: [
            "I wonder where the sun will go, {child}.",
            "Maybe the sun can have orange rays, {child}.",
            "I wonder if the sun will be big or small, {child}."
          ],
          teacherToStar: [
            "Star, do you think the sun should be near the school?",
            "Star, should the sun be big or small?",
            "Star, should the sun have rays?"
          ],
          teacherDirect: [
            "Where should the sun go, {child}?",
            "Should the sun be big or small, {child}?",
            "{child}, should the sun have rays?"
          ],
          donePraise: [
            "The school has sunshine now, {child}.",
            "Nice sun, {child}.",
            "That sun makes the school scene bright, {child}."
          ]
        },
        {
          id: "children",
          spokenName: "children outside the school",
          title: "Add children",
          text: "Add simple children outside the school.",
          partText: "Part 4 of 4",
          palette: [COLORS.blue, COLORS.pink, COLORS.purple, COLORS.green, COLORS.red, COLORS.brown, COLORS.black],
          colorIdeas: {
            [COLORS.blue]: "clothes for a child",
            [COLORS.pink]: "clothes for a child",
            [COLORS.purple]: "clothes for a child",
            [COLORS.green]: "clothes or grass details",
            [COLORS.red]: "clothes for a child",
            [COLORS.brown]: "hair or shoes",
            [COLORS.black]: "hair, shoes, or outlines"
          },
          starLead: [
            "For the last part, let's add a few children outside the school.",
            "Now we can draw simple children near the school.",
            "Let's finish the school scene with children outside."
          ],
          starChoice: [
            "The children can be simple stick figures if you want.",
            "You can put them near the school door or on the grass.",
            "I'll stay with you while you add the children."
          ],
          teacherComment: [
            "Children outside the school make sense for this scene, {child}.",
            "I like seeing the school feel friendly, {child}.",
            "That is a nice final part for the school, {child}."
          ],
          teacherWonder: [
            "I wonder where the children will stand, {child}.",
            "Maybe the children can be playing outside, {child}.",
            "I wonder what colors their clothes will be, {child}."
          ],
          teacherToStar: [
            "Star, should the children stand near the door?",
            "Star, do you think the children should be on the grass?",
            "Star, what colors could their clothes be?"
          ],
          teacherDirect: [
            "{child}, where should the children stand?",
            "{child}, what color clothes should they have?",
            "Should the children be near the school or on the grass, {child}?"
          ],
          donePraise: [
            "The children look nice outside the school, {child}.",
            "Nice children, {child}.",
            "That finishes the school scene, {child}."
          ]
        }
      ]
    }
  ];
  let state = freshState();

  let currentTool = "pen";
  let currentColor = COLORS.purple;
  let isDrawing = false;
  let lastPoint = null;
  let hasDrawnThisStage = false;
  let strokeCountThisStage = 0;

  let activeAudio = null;
  let activeMouthActor = null;
  let audioContext = null;
  let analyser = null;
  let sourceNode = null;
  let mouthAnimationFrame = null;

  let mediaStream = null;
  let mediaRecorder = null;
  let recordingChunks = [];
  let recordingTimeout = null;

  let responseAudioContext = null;
  let responseAnalyser = null;
  let responseMicSource = null;
  let responseMonitorFrame = null;
  let heardSpeechInWindow = false;
  let lastSpeechTime = 0;

  let speechQueue = Promise.resolve();
  let stageCheckTimer = null;
  let colorReactionTimer = null;
  let doneSpeechRecognition = null;
  let doneListenerRestartTimer = null;
  let doneListenerStageToken = null;
  let doneListenerActive = false;
  let doneDetectedLocked = false;

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.45;

  let ringtoneStarted = false;

  function freshState() {
    return {
      sessionStart: Date.now(),

      sceneIndex: 0,
      stageIndex: 0,
      socialRound: 1,
      roundsCompleted: 0,
      stagesCompleted: 0,
      scenesCompleted: 0,

      spokenResponses: 0,
      spokenWords: 0,
      silentWindows: 0,

      starQuestionsAsked: 0,
      teacherQuestionsAsked: 0,
      teacherDirectResponses: 0,
      redirectedQuestions: 0,

      isSpeaking: false,
      isListening: false,
      waitingForResponse: false,
      currentQuestion: null,

      recentLines: [],
      recentColorLines: [],
      totalColorSelections: 0,
      teacherLinesSpoken: 0,
      teacherNameMentions: 0,

      stageStartedAt: 0,
      drawingCommentsThisStage: 0,
      colorCommentsThisStage: 0,
      doneChecksThisStage: 0,
      noSpeechDoneChecksThisStage: 0,
      lastGuidanceAt: 0,
      lastColorCommentAt: 0,
      stageAdvanceLocked: false,
      doneListenerStartedAt: 0,
      doneListenerSupported: false,
      stageReminderCount: 0,

      finalCompletionStarted: false,
      gameCompleted: false,

      micReady: false,
      micDenied: false
    };
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function fillLine(template) {
    return String(template || "").replaceAll("{child}", childName);
  }

  function cleanLine(text) {
    return String(text || "")
      .replace(/!/g, ".")
      .replace(/\booo\b/gi, "")
      .replace(/\boh my\b/gi, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function removeChildNameFromLine(line) {
    if (!childName || childName.toLowerCase() === "there") return line;

    const escaped = childName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

    return String(line || "")
      .replace(new RegExp(`^${escaped},\\s*`, "i"), "")
      .replace(new RegExp(`,\\s*${escaped}(?=[.?!])`, "gi"), "")
      .replace(new RegExp(`,\\s*${escaped}\\b`, "gi"), "")
      .replace(new RegExp(`\\b${escaped},\\s*`, "gi"), "")
      .replace(/\s+/g, " ")
      .replace(/\s+([.?!])/g, "$1")
      .trim();
  }

  function balanceTeacherNameUse(line) {
    if (!line || !childName || childName.toLowerCase() === "there") return line;

    const escaped = childName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const hasName = new RegExp(`\\b${escaped}\\b`, "i").test(line);

    if (!hasName) return line;

    state.teacherLinesSpoken += 1;

    const shouldKeepName = state.teacherNameMentions === 0 || state.teacherLinesSpoken % 4 === 0;

    if (shouldKeepName) {
      state.teacherNameMentions += 1;
      return line;
    }

    return removeChildNameFromLine(line);
  }

  function prepareLineForActor(actor, text) {
    let line = String(text || "");

    if (actor === TEACHER_ACTOR) {
      line = balanceTeacherNameUse(line);
    }

    return cleanLine(line);
  }

  function rememberLine(line) {
    if (!line) return;

    state.recentLines.push(line);

    if (state.recentLines.length > 28) {
      state.recentLines.shift();
    }
  }

  function pickLine(options) {
    const filled = (options || []).map(fillLine).filter(Boolean);
    const fresh = filled.filter(line => !state.recentLines.includes(line));
    const choices = fresh.length ? fresh : filled;

    if (!choices.length) return "";

    return choices[Math.floor(Math.random() * choices.length)];
  }

  function actorLabel(actor) {
    return actor === TEACHER_ACTOR ? "Teacher" : "Star";
  }

  function currentScene() {
    return drawingScenes[Math.min(state.sceneIndex, drawingScenes.length - 1)];
  }

  function currentStage() {
    const scene = currentScene();
    return scene.stages[Math.min(state.stageIndex, scene.stages.length - 1)];
  }

  function stageSpokenName(stage = currentStage()) {
    return stage.spokenName || stage.id.replaceAll("_", " ");
  }

  function getStageToken() {
    return `${state.sceneIndex}:${state.stageIndex}:${state.stagesCompleted}`;
  }

  function getSocialRound() {
    return Math.max(1, Math.min(TARGET_SOCIAL_ROUNDS, state.sceneIndex + 1));
  }

  function getProgressMode() {
    const round = getSocialRound();

    if (round === 1) return "star_leads";
    if (round === 2) return "teacher_wonders_star_bridges";
    if (round === 3) return "teacher_to_star_to_child";
    return "teacher_direct_with_star_support";
  }

  function setPrompt(stage) {
    if (promptTitle) promptTitle.textContent = stage.title;
    if (promptText) {
      const scene = currentScene();
      promptText.textContent = `${scene.name} • ${stage.partText}. ${stage.text} Tell us when this part is done.`;
    }
  }

  function updateRoundDisplay() {
    state.socialRound = getSocialRound();

    if (roundNumber) {
      roundNumber.textContent = String(state.socialRound);
    }
  }

  function updateQuietStatus(text) {
    if (quietStatusText) {
      quietStatusText.textContent = text;
    }
  }

  function startRingtone() {
    if (ringtoneStarted) return;

    ringtone.play()
      .then(function () {
        ringtoneStarted = true;
      })
      .catch(function () {
        console.log("Ringtone waiting for user interaction.");
      });
  }

  function stopRingtone() {
    ringtone.pause();
    ringtone.currentTime = 0;
    ringtoneStarted = false;
  }

  function playCallAcceptedSound() {
    callAcceptedSound.currentTime = 0;
    return callAcceptedSound.play().catch(function () {});
  }

  function queueSpeak(actor, text, options = {}) {
    speechQueue = speechQueue
      .then(() => speakNow(actor, text, options))
      .catch(error => {
        console.error("Drawing speak queue error:", error);
      });

    return speechQueue;
  }

  async function speakNow(actor, text, options = {}) {
    const hadDoneListener = doneListenerActive;
    if (hadDoneListener) stopContinuousDoneListener({ keepMicClass: false });

    const calmText = prepareLineForActor(actor, text);

    if (!calmText || state.gameCompleted) return;

    rememberLine(calmText);
    updateQuietStatus(`${actorLabel(actor)} is talking`);

    const tile = getTile(actor);

    if (tile) tile.classList.add("speaking");

    try {
      state.isSpeaking = true;

      const response = await fetch("/api/drawing-game/tts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          speaker: actor,
          text: calmText
        })
      });

      const data = await response.json();

      if (data.success && data.audio) {
        await playCharacterAudio(actor, data.audio);
      } else {
        await sleep(750);
      }
    } catch (error) {
      console.error("Drawing game TTS error:", error);
      await sleep(750);
    } finally {
      state.isSpeaking = false;

      if (tile) tile.classList.remove("speaking");

      stopMouthAnimation();
      updateQuietStatus("Drawing time");
    }

    if (options.expectsResponse) {
      await askForResponse(actor, calmText, options);
    } else if (hadDoneListener && !state.gameCompleted && !state.stageAdvanceLocked) {
      startContinuousDoneListener({ retryLater: true });
    }
  }

  async function ensureMicPermission() {
    if (state.micDenied) return null;
    if (mediaStream) return mediaStream;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      state.micDenied = true;
      return null;
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.micReady = true;
      return mediaStream;
    } catch (error) {
      console.warn("Mic permission unavailable:", error);
      state.micDenied = true;
      return null;
    }
  }

  function introIsVisible() {
    return introScreen && !introScreen.classList.contains("hidden") && introScreen.style.display !== "none";
  }

  function getTile(actor) {
    if (introIsVisible()) {
      return actor === TEACHER_ACTOR ? introLibrarianTile : introStarTile;
    }

    return actor === TEACHER_ACTOR ? librarianVideoTile : starVideoTile;
  }

  function getMouth(actor) {
    if (introIsVisible()) {
      return actor === TEACHER_ACTOR
        ? document.getElementById("introLibrarianMouth")
        : document.getElementById("introStarMouth");
    }

    return actor === TEACHER_ACTOR
      ? document.getElementById("librarianMouth")
      : document.getElementById("starMouth");
  }

  function getMouthSrc(actor, size) {
    const safeSize = size || "closed";

    if (actor === TEACHER_ACTOR) {
      const teacherFiles = {
        closed: "/static/images/librarian-mouth-closed.png",
        small: "/static/images/librarian-mouth-small.png",
        medium: "/static/images/librarian-mouth-medium.png",
        wide: "/static/images/librarian-mouth-wide.png"
      };

      return teacherFiles[safeSize] || teacherFiles.closed;
    }

    const starFiles = {
      closed: "/static/images/mouth-closed.png",
      small: "/static/images/mouth-small.png",
      medium: "/static/images/mouth-medium.png",
      wide: "/static/images/mouth-wide-open.png"
    };

    return starFiles[safeSize] || starFiles.closed;
  }

  function setMouth(actor, size, scaleX = 1, scaleY = 1) {
    const mouth = getMouth(actor);
    if (!mouth) return;

    mouth.src = getMouthSrc(actor, size);
    mouth.style.transform = `translateX(-50%) scale(${scaleX}, ${scaleY})`;
  }

  function closeAllMouths() {
    setMouth("star", "closed", 1, 1);
    setMouth(TEACHER_ACTOR, "closed", 1, 1);
  }

  function playCharacterAudio(actor, audioSrc) {
    return new Promise(resolve => {
      if (!audioSrc) {
        resolve();
        return;
      }

      if (activeAudio) {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      }

      activeAudio = new Audio(audioSrc);
      activeMouthActor = actor;

      activeAudio.addEventListener("play", function () {
        startMouthAnimation(actor, activeAudio);
      });

      activeAudio.addEventListener("ended", function () {
        stopMouthAnimation();
        resolve();
      });

      activeAudio.addEventListener("error", function () {
        stopMouthAnimation();
        resolve();
      });

      activeAudio.play().catch(function () {
        stopMouthAnimation();
        resolve();
      });
    });
  }

  function startMouthAnimation(actor, audioElement) {
    stopMouthAnimation();
    activeMouthActor = actor;

    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;

      sourceNode = audioContext.createMediaElementSource(audioElement);
      sourceNode.connect(analyser);
      analyser.connect(audioContext.destination);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      function animate() {
        analyser.getByteFrequencyData(dataArray);

        let sum = 0;

        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }

        const average = sum / dataArray.length;
        const normalized = Math.min(1, average / 80);
        const scaleX = 1 + normalized * 0.10;
        const scaleY = 1 + normalized * 0.18;

        if (average < 14) {
          setMouth(actor, "closed", 1, 1);
        } else if (average < 34) {
          setMouth(actor, "small", scaleX, scaleY);
        } else if (average < 58) {
          setMouth(actor, "medium", scaleX, scaleY);
        } else {
          setMouth(actor, "wide", scaleX, scaleY);
        }

        mouthAnimationFrame = requestAnimationFrame(animate);
      }

      animate();
    } catch (error) {
      console.warn("Could not animate mouth:", error);
    }
  }

  function stopMouthAnimation() {
    if (mouthAnimationFrame) {
      cancelAnimationFrame(mouthAnimationFrame);
      mouthAnimationFrame = null;
    }

    if (sourceNode) {
      try { sourceNode.disconnect(); } catch (error) {}
      sourceNode = null;
    }

    if (analyser) {
      try { analyser.disconnect(); } catch (error) {}
      analyser = null;
    }

    if (audioContext) {
      audioContext.close().catch(function () {});
      audioContext = null;
    }

    activeMouthActor = null;
    closeAllMouths();
  }

  async function askForResponse(actor, message, options = {}) {
    if (state.isListening || state.gameCompleted) return;

    state.waitingForResponse = true;

    state.currentQuestion = {
      actor,
      message,
      askType: options.askType || "one_word",
      intent: options.intent || null,
      source: options.source || actor,
      stageId: currentStage().id,
      sceneId: currentScene().id,
      socialRound: getSocialRound()
    };

    if (actor === TEACHER_ACTOR) {
      state.teacherQuestionsAsked += 1;
    } else {
      state.starQuestionsAsked += 1;
    }

    await startResponseWindow(state.currentQuestion, options.responseSeconds || 5.2);
  }

  function getSupportedMimeType() {
    const options = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4"
    ];

    for (const option of options) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(option)) {
        return option;
      }
    }

    return "";
  }

  async function startResponseWindow(question, seconds) {
    const stream = await ensureMicPermission();

    if (!stream) {
      state.waitingForResponse = false;
      state.currentQuestion = null;
      await handleNoSpeech(question);
      return;
    }

    const tile = getTile(question.actor || "star");

    if (tile) tile.classList.add("soft-listening");
    if (micControl) micControl.classList.add("quiet-listening");

    updateQuietStatus("Listening quietly");

    recordingChunks = [];
    state.isListening = true;

    return new Promise(resolve => {
      try {
        const mimeType = getSupportedMimeType();

        mediaRecorder = mimeType
          ? new MediaRecorder(stream, { mimeType })
          : new MediaRecorder(stream);
      } catch (error) {
        mediaRecorder = new MediaRecorder(stream);
      }

      mediaRecorder.addEventListener("dataavailable", function (event) {
        if (event.data && event.data.size > 0) {
          recordingChunks.push(event.data);
        }
      });

      mediaRecorder.addEventListener("stop", function () {
        handleRecordingStop(question).then(resolve);
      });

      heardSpeechInWindow = false;
      lastSpeechTime = 0;

      mediaRecorder.start();

      const maxWindowMs = seconds * 1000;
      startSpeechEndDetector(stream, maxWindowMs);

      recordingTimeout = setTimeout(stopResponseWindow, maxWindowMs);
    });
  }

  function startSpeechEndDetector(stream, maxWindowMs) {
    stopSpeechEndDetector();

    try {
      responseAudioContext = new (window.AudioContext || window.webkitAudioContext)();
      responseAnalyser = responseAudioContext.createAnalyser();
      responseAnalyser.fftSize = 512;

      responseMicSource = responseAudioContext.createMediaStreamSource(stream);
      responseMicSource.connect(responseAnalyser);

      const dataArray = new Uint8Array(responseAnalyser.frequencyBinCount);
      const startedAt = Date.now();

      function monitorSpeech() {
        if (!responseAnalyser || !mediaRecorder || mediaRecorder.state === "inactive") {
          stopSpeechEndDetector();
          return;
        }

        responseAnalyser.getByteTimeDomainData(dataArray);

        let sum = 0;

        for (let i = 0; i < dataArray.length; i++) {
          const value = dataArray[i] - 128;
          sum += value * value;
        }

        const volume = Math.sqrt(sum / dataArray.length);
        const now = Date.now();
        const speechThreshold = 9;

        if (volume > speechThreshold) {
          heardSpeechInWindow = true;
          lastSpeechTime = now;
        }

        const hasRecordedLongEnough = now - startedAt > 850;
        const silenceAfterSpeech = heardSpeechInWindow && now - lastSpeechTime > 850;
        const maxTimeReached = now - startedAt > maxWindowMs;

        if ((hasRecordedLongEnough && silenceAfterSpeech) || maxTimeReached) {
          stopResponseWindow();
          return;
        }

        responseMonitorFrame = requestAnimationFrame(monitorSpeech);
      }

      monitorSpeech();
    } catch (error) {
      console.warn("Could not start speech detector:", error);
    }
  }

  function stopSpeechEndDetector() {
    if (responseMonitorFrame) {
      cancelAnimationFrame(responseMonitorFrame);
      responseMonitorFrame = null;
    }

    if (responseMicSource) {
      try { responseMicSource.disconnect(); } catch (error) {}
      responseMicSource = null;
    }

    if (responseAudioContext) {
      responseAudioContext.close().catch(function () {});
      responseAudioContext = null;
    }

    responseAnalyser = null;
  }

  function stopResponseWindow() {
    stopSpeechEndDetector();

    if (recordingTimeout) {
      clearTimeout(recordingTimeout);
      recordingTimeout = null;
    }

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  }

  async function handleRecordingStop(question) {
    state.isListening = false;
    state.waitingForResponse = false;
    state.currentQuestion = null;

    const tile = getTile(question.actor || "star");

    if (tile) tile.classList.remove("soft-listening");
    if (micControl) micControl.classList.remove("quiet-listening");

    updateQuietStatus("Drawing time");

    if (!recordingChunks.length) {
      await handleNoSpeech(question);
      return null;
    }

    const blob = new Blob(recordingChunks, {
      type: recordingChunks[0]?.type || "audio/webm"
    });

    recordingChunks = [];

    try {
      const formData = new FormData();
      formData.append("audio", blob, "drawing-response.webm");

      const response = await fetch("/api/drawing-game/transcribe", {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      if (!data.success) {
        await handleNoSpeech(question);
        return null;
      }

      const transcript = cleanTranscript(data.text || "");

      if (!transcript) {
        await handleNoSpeech(question);
        return null;
      }

      await handleSpeech(transcript, question);
      return transcript;
    } catch (error) {
      console.error("Drawing transcription error:", error);
      await handleNoSpeech(question);
      return null;
    }
  }

  function cleanTranscript(text) {
    const cleaned = String(text || "")
      .replace(/[“”]/g, "")
      .replace(/\s+/g, " ")
      .trim();

    const lower = cleaned.toLowerCase();

    const emptyLike = new Set([
      "",
      "you",
      "thank you",
      "thanks for watching",
      "bye",
      "goodbye",
      "subscribe"
    ]);

    if (emptyLike.has(lower)) return "";
    if (cleaned.length < 2) return "";

    return cleaned;
  }

  function countWords(text) {
    return String(text || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .length;
  }

  function normalizedWords(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9' ]/g, " ")
      .split(/\s+/)
      .filter(Boolean);
  }

  function classifyStageDoneResponse(text) {
    const lower = String(text || "").toLowerCase();
    const words = new Set(normalizedWords(lower));

    const doneWords = [
      "done", "finished", "finish", "next", "ready", "completed",
      "complete", "move on", "go on", "all done", "that's it", "that is it"
    ];

    const keepWords = [
      "no", "not yet", "more", "keep", "continue", "wait", "still",
      "again", "add more", "not done", "not finished"
    ];

    if (doneWords.some(word => lower.includes(word))) return "done";
    if (keepWords.some(word => lower.includes(word))) return "keep";

    if (words.has("yes") || words.has("yeah") || words.has("yep") || words.has("okay") || words.has("ok")) {
      return "done";
    }

    return "unclear";
  }

  function transcriptSoundsLikeDone(text) {
    return classifyStageDoneResponse(text) === "done";
  }

  async function handleSpeech(transcript, question) {
    const words = countWords(transcript);
    const mode = getProgressMode();

    state.spokenResponses += 1;
    state.spokenWords += words;

    if (question?.source === "teacher-direct") {
      state.teacherDirectResponses += 1;
    }

    if (question?.source === "teacher-redirect") {
      state.redirectedQuestions += 1;
    }

    if (question?.intent === "scene_choice") {
      await handleSceneChoiceResponse(transcript);
      return;
    }

    if (question?.intent === "stage_done") {
      await handleStageDoneResponse(transcript, question);
      return;
    }

    if (hasDrawnThisStage && transcriptSoundsLikeDone(transcript)) {
      await speakNow("star", pickLine([
        "Okay. Let's move to the next part.",
        "Got it. We can go to the next part.",
        "Okay, this part can be finished."
      ]));
      await advanceStage();
      return;
    }

    if (question?.source === "teacher-direct") {
      await speakNow(TEACHER_ACTOR, pickLine([
        "Nice choice.",
        "Good choice.",
        "Thanks for telling me.",
        "Okay. I like that idea.",
        "That sounds good."
      ]));

      await sleep(180);

      await speakNow("star", pickLine([
        "You can add that.",
        "That works for your picture.",
        "Good idea. Keep going.",
        "That could look nice in your picture."
      ]));

      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(12000);
      return;
    }

    if (question?.source === "teacher-redirect") {
      await speakNow("star", pickLine([
        "Good idea.",
        "Nice. You can add that.",
        "Okay. Let's use that.",
        "That works.",
        "That sounds good."
      ]));

      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(12000);
      return;
    }

    if (mode === "teacher_wonders_star_bridges" && Math.random() < 0.35) {
      await speakNow(TEACHER_ACTOR, pickLine([
        "I like that idea.",
        "That sounds nice for the picture.",
        "That will fit the scene."
      ]));
    }

    await speakNow("star", pickLine([
      "Good idea.",
      "Nice. Let's keep drawing.",
      "Okay. You can add that.",
      "That sounds good.",
      "You can try that.",
      "That will look nice."
    ]));

    startContinuousDoneListener({ retryLater: true });
    scheduleStageCheck(12000);
  }

  async function handleStageDoneResponse(transcript) {
    const choice = classifyStageDoneResponse(transcript);

    if (choice === "done") {
      await speakNow("star", pickLine([
        "Okay. Let's move to the next part.",
        "Great. This part is done.",
        "Okay, we can go to the next part."
      ]));

      await advanceStage();
      return;
    }

    if (choice === "keep") {
      await speakNow("star", pickLine([
        "Okay. We can keep working on this part.",
        "Sure. You can add a little more.",
        "Okay, we can keep drawing."
      ]));

      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(12000);
      return;
    }

    await speakNow("star", pickLine([
      "Okay. We can keep drawing for a little bit.",
      "That's okay. We can add a little more.",
      "No rush. We can keep working on this part."
    ]));

    startContinuousDoneListener({ retryLater: true });
    scheduleStageCheck(12000);
  }

  async function handleNoSpeech(question) {
    state.silentWindows += 1;

    if (!question) return;

    if (question.intent === "scene_choice") {
      await speakNow("star", pickLine([
        "That's okay. We can make another picture.",
        "No rush. We'll keep going to the next picture.",
        "That's okay. Let's try the next picture."
      ]));
      beginNextScene();
      return;
    }

    if (question.intent === "stage_done") {
      await speakNow("star", pickLine([
        "That's okay. We can keep drawing.",
        "No rush. We can keep working on this part.",
        "That's okay. You can keep adding more."
      ]));

      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(12000);
      return;
    }

    if (question.source === "teacher-direct") {
      await speakNow(TEACHER_ACTOR, pickLine([
        "That's okay. We can keep drawing.",
        "No rush. Star can help.",
        "That's okay. We can still make the picture."
      ]));

      await sleep(160);

      await speakNow("star", pickLine([
        "I'll stay here while you keep drawing.",
        "You can just keep going.",
        "That's okay. Keep drawing."
      ]));

      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(12000);
      return;
    }

    await speakNow("star", pickLine([
      "That's okay. We can keep drawing.",
      "No rush. I'll stay here with you.",
      "That's okay. You can just keep going."
    ]));

    startContinuousDoneListener({ retryLater: true });
    scheduleStageCheck(12000);
  }

  function resizeCanvasForDisplay() {
    const rect = canvas.getBoundingClientRect();

    const old = document.createElement("canvas");
    old.width = canvas.width;
    old.height = canvas.height;
    old.getContext("2d").drawImage(canvas, 0, 0);

    canvas.width = Math.max(1, Math.floor(rect.width * window.devicePixelRatio));
    canvas.height = Math.max(1, Math.floor(rect.height * window.devicePixelRatio));

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(old, 0, 0, canvas.width, canvas.height);

    setupCanvasStyle();
  }

  function setupCanvasStyle() {
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }

  function getCanvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    const source = event.touches ? event.touches[0] : event;

    return {
      x: (source.clientX - rect.left) * window.devicePixelRatio,
      y: (source.clientY - rect.top) * window.devicePixelRatio
    };
  }

  function startDrawing(event) {
    event.preventDefault();

    isDrawing = true;
    hasDrawnThisStage = true;
    lastPoint = getCanvasPoint(event);

    if (doneDrawingBtn) doneDrawingBtn.disabled = false;

    maybeReactToDrawingStart();
    scheduleStageCheck(16000);
  }

  function draw(event) {
    if (!isDrawing || !lastPoint) return;

    event.preventDefault();

    const point = getCanvasPoint(event);

    ctx.globalCompositeOperation = currentTool === "eraser" ? "destination-out" : "source-over";
    ctx.strokeStyle = currentColor;
    ctx.lineWidth = currentTool === "eraser" ? 26 : 8;

    ctx.beginPath();
    ctx.moveTo(lastPoint.x, lastPoint.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();

    lastPoint = point;
    strokeCountThisStage += 1;

    maybeReactDuringDrawing();

    if (strokeCountThisStage >= 15) {
      scheduleStageCheck(14000);
    }
  }

  function stopDrawing() {
    isDrawing = false;
    lastPoint = null;
  }

  function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    resetStageDrawingState();
  }

  function resetStageDrawingState() {
    hasDrawnThisStage = false;
    strokeCountThisStage = 0;

    if (doneDrawingBtn) {
      doneDrawingBtn.disabled = true;
    }
  }

  function resetStageConversationState() {
    clearStageCheckTimer();

    state.stageStartedAt = Date.now();
    state.drawingCommentsThisStage = 0;
    state.colorCommentsThisStage = 0;
    state.doneChecksThisStage = 0;
    state.noSpeechDoneChecksThisStage = 0;
    state.lastGuidanceAt = 0;
    state.lastColorCommentAt = 0;
    state.stageAdvanceLocked = false;
    state.stageReminderCount = 0;
    doneDetectedLocked = false;

    resetStageDrawingState();
  }

  function setTool(tool) {
    currentTool = tool;

    toolButtons.forEach(button => {
      button.classList.toggle("active", button.dataset.tool === tool);
    });
  }

  function setPalette(colors) {
    const allowed = new Set(colors || []);

    colorButtons.forEach(button => {
      const isAllowed = allowed.has(button.dataset.color);

      button.classList.toggle("palette-hidden", !isAllowed);
      button.disabled = !isAllowed;
      button.setAttribute("aria-hidden", isAllowed ? "false" : "true");
    });

    const firstColor = colors?.[0];

    if (firstColor) {
      setColor(firstColor, { silent: true });
    }
  }

  function setColor(color, options = {}) {
    currentColor = color;
    currentTool = "pen";

    colorButtons.forEach(button => {
      button.classList.toggle("active", button.dataset.color === color);
    });

    setTool("pen");

    if (!options.silent) {
      maybeReactToColorChange(color);
    }
  }

  function colorName(color) {
    return COLOR_NAMES[color] || "that color";
  }

  function colorNameForStage(color) {
    const stage = currentStage();

    if (stage.id === "grass") {
      if (color === COLORS.green) return "dark green";
      if (color === COLORS.lime) return "light green";
    }

    return colorName(color);
  }

  function colorIdeaForStage(color) {
    const stage = currentStage();
    return stage.colorIdeas?.[color] || "this part of the picture";
  }

  function buildStageColorSuggestion(stage = currentStage()) {
    const palette = (stage.palette || []).slice(0, 4);
    const pairs = palette.map(color => {
      const label = colorNameForStage(color);
      const idea = stage.colorIdeas?.[color] || stageSpokenName(stage);
      return `${label} could be good for ${idea}`;
    });

    if (!pairs.length) return "You can choose any color you want for this part.";
    if (pairs.length === 1) return `For this part, ${pairs[0]}.`;
    if (pairs.length === 2) return `For this part, ${pairs[0]}, and ${pairs[1]}.`;

    const last = pairs.pop();
    return `For this part, ${pairs.join(", ")}, and ${last}.`;
  }

  function doneGuidanceLine(partName) {
    return pickLine([
      `Just tell me whenever you're done with the ${partName}.`,
      `Whenever the ${partName} feels finished, you can tell me.`,
      `No rush. Tell me when this part is done.`,
      `Keep going until the ${partName} feels finished, then tell me.`
    ]);
  }

  function canCharacterChimeIn(minGap = 7600) {
    if (state.isSpeaking || state.isListening || state.waitingForResponse || state.gameCompleted) {
      return false;
    }

    if (Date.now() - state.lastGuidanceAt < minGap) {
      return false;
    }

    return true;
  }

  function buildTeacherColorLine(colorLabel, idea, isMilestone = false) {
    const colorLines = [
      `I can see that you selected ${colorLabel}, ${childName}. That's a great choice for ${idea}.`,
      `${childName}, I notice that you are using ${colorLabel} now. That's a great choice for ${idea}.`,
      `I see that you are using ${colorLabel} now, ${childName}.`,
      `I can see that you selected ${colorLabel}. That works nicely for ${idea}.`,
      `I notice that you are using ${colorLabel} now. That's a good choice for ${idea}.`
    ];

    const praiseLines = [
      `Your drawing is looking great so far.`,
      `Great job. Your picture is looking really nice.`,
      `You are doing a great job with this drawing.`,
      `You are a great artist. This is looking nice.`
    ];

    if (!isMilestone) {
      return pickLine(colorLines);
    }

    return `${pickLine(colorLines)} ${pickLine(praiseLines)}`;
  }

  function maybeReactToColorChange(color) {
    if (state.gameCompleted || state.stageAdvanceLocked || state.isListening || state.waitingForResponse) return;

    const now = Date.now();
    const idea = colorIdeaForStage(color);
    const colorLabel = colorNameForStage(color);

    state.totalColorSelections += 1;
    const isMilestone = state.totalColorSelections > 0 && state.totalColorSelections % 4 === 0;

    if (!isMilestone && now - state.lastColorCommentAt < 2100) return;

    state.colorCommentsThisStage += 1;
    state.lastColorCommentAt = now;
    state.lastGuidanceAt = now;

    queueSpeak(TEACHER_ACTOR, buildTeacherColorLine(colorLabel, idea, isMilestone));
  }

  function maybeReactToDrawingStart() {
    if (state.drawingCommentsThisStage > 0) return;
    if (!canCharacterChimeIn(3300)) return;

    state.drawingCommentsThisStage += 1;
    state.lastGuidanceAt = Date.now();

    const mode = getProgressMode();
    const stage = currentStage();
    const partName = stageSpokenName(stage);

    if (mode === "star_leads") {
      queueSpeak("star", pickLine([
        `Good start. You can put the ${partName} anywhere you want.`,
        `Take your time with the ${partName}.`,
        `Start wherever it feels easiest.`,
        `You can make the ${partName} your own way.`
      ]));
      return;
    }

    if (mode === "teacher_wonders_star_bridges") {
      queueSpeak("star", pickLine([
        `Take your time with this part, ${childName}.`,
        `You can choose where this part goes, ${childName}.`,
        `Start wherever you want. I am right here.`
      ]));
      return;
    }

    if (mode === "teacher_to_star_to_child") {
      queueSpeak(TEACHER_ACTOR, pickLine([
        `I like how this starts.`,
        `That is a nice beginning.`,
        `This part is starting nicely.`,
        `Great job starting this part.`
      ]));
      return;
    }

    queueSpeak(TEACHER_ACTOR, pickLine([
      `That is a good start.`,
      `I like how you started that.`,
      `Your picture is starting nicely.`,
      `Great job starting this part.`
    ]));
  }

  function maybeReactDuringDrawing() {
    if (strokeCountThisStage < 14) return;
    if (state.drawingCommentsThisStage >= 2) return;
    if (!canCharacterChimeIn(8500)) return;

    state.drawingCommentsThisStage += 1;
    state.lastGuidanceAt = Date.now();

    const mode = getProgressMode();

    if (mode === "star_leads") {
      queueSpeak("star", pickLine([
        "This is coming along.",
        "You can add as much or as little as you want.",
        "That part is looking good.",
        "Keep going until it feels finished."
      ]));
      return;
    }

    if (mode === "teacher_wonders_star_bridges") {
      queueSpeak(TEACHER_ACTOR, pickLine([
        `That is looking good so far.`,
        `I like how this picture is growing.`,
        `That part is coming along nicely.`,
        `Great job. This is looking nice.`
      ]));
      return;
    }

    if (mode === "teacher_to_star_to_child") {
      queueSpeak(TEACHER_ACTOR, pickLine([
        `Star, ${childName}'s picture is coming together.`,
        `Star, I like how this part is looking.`,
        `Star, this is turning into a nice scene.`
      ]));
      return;
    }

    queueSpeak(TEACHER_ACTOR, pickLine([
      `That is looking good.`,
      `I like how your scene is coming together.`,
      `You are adding nice details.`,
      `You are a great artist.`
    ]));
  }

  async function beginStage(options = {}) {
    stopContinuousDoneListener({ keepMicClass: false });

    const scene = currentScene();
    const stage = currentStage();
    const mode = getProgressMode();
    const partName = stageSpokenName(stage);

    updateRoundDisplay();
    setPrompt(stage);
    setPalette(stage.palette);
    resetStageConversationState();

    if (options.clearCanvas) {
      clearCanvas();
    }

    updateQuietStatus("Drawing time");

    if (state.stageIndex === 0) {
      await queueSpeak("star", scene.newSceneLine);
      await sleep(180);
    }

    if (mode === "star_leads") {
      await queueSpeak("star", pickLine(stage.starLead));
      await sleep(120);
      await queueSpeak("star", buildStageColorSuggestion(stage));
      await sleep(120);
      await queueSpeak("star", doneGuidanceLine(partName));
      await sleep(120);
      await queueSpeak(TEACHER_ACTOR, pickLine(stage.teacherComment));
      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(22000);
      return;
    }

    if (mode === "teacher_wonders_star_bridges") {
      await queueSpeak("star", pickLine(stage.starLead));
      await sleep(120);
      await queueSpeak("star", buildStageColorSuggestion(stage));
      await sleep(120);
      await queueSpeak(TEACHER_ACTOR, pickLine(stage.teacherWonder));
      await sleep(120);
      await queueSpeak("star", doneGuidanceLine(partName));
      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(23000);
      return;
    }

    if (mode === "teacher_to_star_to_child") {
      await queueSpeak(TEACHER_ACTOR, pickLine(stage.teacherToStar));
      await sleep(120);
      await queueSpeak("star", pickLine([
        "That sounds like a good idea.",
        "That could work for this picture.",
        "You can add that part now.",
        "That part can go wherever you want."
      ]));
      await sleep(120);
      await queueSpeak("star", buildStageColorSuggestion(stage));
      await sleep(120);
      await queueSpeak("star", doneGuidanceLine(partName));
      startContinuousDoneListener({ retryLater: true });
      scheduleStageCheck(23000);
      return;
    }

    await queueSpeak("star", pickLine([
      "The Teacher can help guide this part now.",
      "The Teacher can ask one small question now.",
      "You can answer the Teacher with just one word if you want."
    ]));

    await sleep(140);

    await queueSpeak(TEACHER_ACTOR, buildStageColorSuggestion(stage));
    await sleep(120);

    await queueSpeak(TEACHER_ACTOR, pickLine(stage.teacherDirect), {
      expectsResponse: true,
      askType: "choice",
      source: "teacher-direct",
      intent: "stage_choice",
      responseSeconds: 5.7
    });

    await sleep(120);
    await queueSpeak("star", doneGuidanceLine(partName));
    startContinuousDoneListener({ retryLater: true });
    scheduleStageCheck(23000);
  }

  function browserSpeechRecognitionConstructor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function donePhraseHeard(text) {
    const lower = String(text || "").toLowerCase();
    return [
      "i'm done", "im done", "i am done", "all done", "i'm finished", "im finished",
      "i am finished", "finished", "done", "done drawing", "i finished", "we are done",
      "we're done", "we done", "next part", "move on"
    ].some(phrase => lower.includes(phrase));
  }

  function stopContinuousDoneListener(options = {}) {
    if (doneListenerRestartTimer) {
      clearTimeout(doneListenerRestartTimer);
      doneListenerRestartTimer = null;
    }

    doneListenerActive = false;
    doneListenerStageToken = null;

    if (!options.keepMicClass && micControl) {
      micControl.classList.remove("background-listening");
    }

    if (doneSpeechRecognition) {
      try {
        doneSpeechRecognition.onresult = null;
        doneSpeechRecognition.onerror = null;
        doneSpeechRecognition.onend = null;
        doneSpeechRecognition.stop();
      } catch (error) {}

      doneSpeechRecognition = null;
    }
  }

  function startContinuousDoneListener(options = {}) {
    if (state.gameCompleted || state.stageAdvanceLocked || state.isSpeaking || state.isListening || state.waitingForResponse) {
      if (options.retryLater) {
        doneListenerRestartTimer = setTimeout(function () {
          startContinuousDoneListener({ retryLater: true });
        }, 900);
      }
      return;
    }

    const Recognition = browserSpeechRecognitionConstructor();

    if (!Recognition) {
      state.doneListenerSupported = false;
      if (micControl) micControl.classList.remove("background-listening");
      return;
    }

    const token = getStageToken();

    if (doneListenerActive && doneListenerStageToken === token && doneSpeechRecognition) {
      if (micControl) micControl.classList.add("background-listening");
      return;
    }

    stopContinuousDoneListener({ keepMicClass: true });

    state.doneListenerSupported = true;
    state.doneListenerStartedAt = Date.now();
    doneListenerActive = true;
    doneListenerStageToken = token;

    if (micControl) micControl.classList.add("background-listening");

    try {
      const recognition = new Recognition();
      doneSpeechRecognition = recognition;
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onresult = function (event) {
        if (state.gameCompleted || state.stageAdvanceLocked) return;
        if (doneListenerStageToken !== getStageToken()) return;

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = Array.from(event.results[i])
            .map(result => result.transcript || "")
            .join(" ")
            .trim();

          if (!transcript) continue;

          if (hasDrawnThisStage && donePhraseHeard(transcript) && !doneDetectedLocked) {
            doneDetectedLocked = true;
            const words = countWords(transcript);
            state.spokenResponses += 1;
            state.spokenWords += words;

            stopContinuousDoneListener({ keepMicClass: false });

            speechQueue = speechQueue.then(async function () {
              await speakNow("star", pickLine([
                "Okay. Let's move to the next part.",
                "Got it. We can go to the next part.",
                "Okay, this part is finished."
              ]));
              await advanceStage();
            });

            return;
          }
        }
      };

      recognition.onerror = function () {
        if (micControl) micControl.classList.remove("background-listening");
      };

      recognition.onend = function () {
        if (state.gameCompleted || state.stageAdvanceLocked) return;
        if (doneListenerStageToken !== getStageToken()) return;
        if (state.isSpeaking || state.isListening || state.waitingForResponse) return;

        if (micControl) micControl.classList.remove("background-listening");

        doneListenerRestartTimer = setTimeout(function () {
          doneListenerActive = false;
          startContinuousDoneListener({ retryLater: true });
        }, 700);
      };

      recognition.start();
    } catch (error) {
      console.warn("Continuous done listener unavailable:", error);
      stopContinuousDoneListener({ keepMicClass: false });
    }
  }

  function clearStageCheckTimer() {
    if (stageCheckTimer) {
      clearTimeout(stageCheckTimer);
      stageCheckTimer = null;
    }
  }

  function scheduleStageCheck(delayMs = 8000) {
    if (state.gameCompleted || state.stageAdvanceLocked) return;
    if (!hasDrawnThisStage) return;

    clearStageCheckTimer();

    stageCheckTimer = setTimeout(function () {
      maybeAskStageDone();
    }, delayMs);
  }

  async function maybeAskStageDone() {
    if (state.gameCompleted || state.stageAdvanceLocked) return;

    if (!hasDrawnThisStage || strokeCountThisStage < 8) {
      scheduleStageCheck(9000);
      return;
    }

    if (state.isSpeaking || state.isListening || state.waitingForResponse) {
      scheduleStageCheck(6500);
      return;
    }

    if (Date.now() - state.stageStartedAt < 15000) {
      scheduleStageCheck(9000);
      return;
    }

    if (state.stageReminderCount >= 2) {
      scheduleStageCheck(16000);
      return;
    }

    state.stageReminderCount += 1;
    state.doneChecksThisStage += 1;
    state.lastGuidanceAt = Date.now();

    const stage = currentStage();
    const partName = stageSpokenName(stage);
    const mode = getProgressMode();

    if (mode === "teacher_direct_with_star_support" && state.stageReminderCount === 2) {
      await queueSpeak(TEACHER_ACTOR, pickLine([
        `When the ${partName} is finished, you can tell us.`,
        `You can let us know when the ${partName} is ready.`,
        `No rush. Tell us whenever this part is done.`
      ]));
    } else {
      await queueSpeak("star", pickLine([
        `Just tell me whenever you're finished with the ${partName}.`,
        `No rush. When the ${partName} is ready, you can tell me.`,
        `You can keep drawing. Tell me when this part is done.`
      ]));
    }

    startContinuousDoneListener({ retryLater: true });
    scheduleStageCheck(16000);
  }

  async function advanceStage() {
    if (state.stageAdvanceLocked || state.gameCompleted) return;

    state.stageAdvanceLocked = true;
    stopContinuousDoneListener({ keepMicClass: false });
    clearStageCheckTimer();

    const stage = currentStage();

    state.stagesCompleted += 1;
    state.roundsCompleted = Math.max(state.roundsCompleted, getSocialRound());

    await speakNow(TEACHER_ACTOR, pickLine(stage.donePraise));

    const scene = currentScene();
    const isLastStageInScene = state.stageIndex >= scene.stages.length - 1;
    const isLastScene = state.sceneIndex >= drawingScenes.length - 1;

    if (isLastStageInScene) {
      state.scenesCompleted += 1;

      if (!isLastScene) {
        await sleep(220);
        await speakNow("star", scene.completeLine);
        await askContinueAfterScene(scene);
        return;
      }

      await finishFullActivity();
      return;
    }

    state.stageIndex += 1;

    setTimeout(function () {
      beginStage({ clearCanvas: false });
    }, 650);
  }

  function classifySceneChoice(text) {
    const lower = String(text || "").toLowerCase();
    const words = new Set(normalizedWords(lower));

    const stopPhrases = ["stop", "end", "all done", "done for today", "finish", "finished", "dashboard", "no more", "no thanks"];
    const continuePhrases = ["another", "again", "next", "keep going", "keep drawing", "more", "yes", "yeah", "yep", "sure", "okay", "ok", "play", "round"];

    if (stopPhrases.some(phrase => lower.includes(phrase)) || words.has("no") || words.has("nope")) return "stop";
    if (continuePhrases.some(phrase => lower.includes(phrase))) return "continue";

    return "unclear";
  }

  async function askContinueAfterScene(scene) {
    await sleep(180);

    if (getProgressMode() === "teacher_to_star_to_child" || getProgressMode() === "teacher_direct_with_star_support") {
      await speakNow(TEACHER_ACTOR, pickLine([
        "That picture looks great.",
        "Great job finishing that picture.",
        "You did a great job with that scene."
      ]));
      await sleep(140);
    }

    await speakNow("star", pickLine([
      "Do you want to make another picture, or are you all done for today?",
      "Should we make another picture, or do you want to stop here?",
      "You can keep going to the next picture, or we can stop here for today."
    ]), {
      expectsResponse: true,
      askType: "choice",
      source: "star",
      intent: "scene_choice",
      responseSeconds: 5.8
    });
  }

  async function handleSceneChoiceResponse(transcript) {
    const choice = classifySceneChoice(transcript);

    if (choice === "stop") {
      await speakNow("star", pickLine([
        "Okay. We can stop here for today.",
        "Okay. We can be all done for now.",
        "That's okay. We can stop the drawing game here."
      ]));
      window.location.href = "/dashboard";
      return;
    }

    await speakNow("star", pickLine([
      "Okay. Let's make another picture.",
      "Great. Let's go to the next picture.",
      "Okay. We'll try the next drawing."
    ]));
    beginNextScene();
  }

  function beginNextScene() {
    state.sceneIndex += 1;
    state.stageIndex = 0;

    setTimeout(function () {
      beginStage({ clearCanvas: true });
    }, 650);
  }

  async function finishFullActivity() {
    if (state.finalCompletionStarted || state.gameCompleted) return;

    state.finalCompletionStarted = true;

    await sleep(220);

    await speakNow("star", pickLine([
      "You finished all four pictures.",
      "That was a lot of drawing.",
      "You helped make every scene."
    ]));

    await sleep(180);

    await speakNow(TEACHER_ACTOR, pickLine([
      "Thank you for showing me your drawing. I liked seeing the school scene you made.",
      "I liked watching your drawings with Star today.",
      "That was a nice school scene. I am glad I got to see your drawing."
    ]));

    await completeAndGoNext();
  }

  async function completeAndGoNext() {
    if (state.gameCompleted) return;

    state.gameCompleted = true;
    stopContinuousDoneListener({ keepMicClass: false });
    clearStageCheckTimer();

    const minutesPlayed = Math.max(0, (Date.now() - state.sessionStart) / 60000);

    try {
      const response = await fetch("/api/drawing-game/complete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          activity_id: activityId,
          words_spoken: state.spokenWords,
          minutes_spoken: Math.max(0, state.spokenResponses * 0.08),
          active_minutes: minutesPlayed,
          time_spent_on_activity: minutesPlayed,
          spoken_responses: state.spokenResponses,
          silent_windows: state.silentWindows,
          rounds_completed: TARGET_SOCIAL_ROUNDS,
          stages_completed: state.stagesCompleted,
          scenes_completed: state.scenesCompleted,
          librarian_direct_responses: state.teacherDirectResponses
        })
      });

      const data = await response.json();

      if (data.success && data.next_activity_id) {
        window.location.href = `/activity/${data.next_activity_id}`;
        return;
      }
    } catch (error) {
      console.error("Could not save drawing game completion:", error);
    }

    window.location.href = "/dashboard";
  }

  async function playIntro() {
    await queueSpeak("star", "Hey again. It's me, Star. Today, I'll help you know what to draw next.");
    await queueSpeak(TEACHER_ACTOR, "Hi. I'm the Teacher. I'll watch your drawing, notice your colors, and cheer you on.");
    await queueSpeak("star", "I'll share my screen so we can use the drawing board.");
    shrinkIntroToGame();
  }

  function shrinkIntroToGame() {
    stopMouthAnimation();

    requestAnimationFrame(function () {
      introScreen.classList.add("shrink");
    });

    setTimeout(function () {
      zoomStage.classList.remove("call-hidden");
    }, 1050);

    setTimeout(function () {
      introScreen.style.display = "none";
      introScreen.classList.add("hidden");
      zoomStage.classList.remove("side-panel-hidden");
      closeAllMouths();
      beginStage({ clearCanvas: true });
    }, 1500);
  }

  async function startGameAfterCall() {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    stopRingtone();
    playCallAcceptedSound();
    ensureMicPermission();

    introScreen.classList.remove("hidden");

    requestAnimationFrame(function () {
      incomingCallScreen.classList.add("hide");
    });

    setTimeout(function () {
      incomingCallScreen.style.display = "none";
    }, 450);

    setTimeout(playIntro, 850);
  }

  function cleanupMedia() {
    stopContinuousDoneListener({ keepMicClass: false });
    clearStageCheckTimer();

    if (colorReactionTimer) {
      clearTimeout(colorReactionTimer);
      colorReactionTimer = null;
    }

    stopResponseWindow();
    stopMouthAnimation();

    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }
  }

  canvas.addEventListener("mousedown", startDrawing);
  canvas.addEventListener("mousemove", draw);
  window.addEventListener("mouseup", stopDrawing);

  canvas.addEventListener("touchstart", startDrawing, { passive: false });
  canvas.addEventListener("touchmove", draw, { passive: false });
  window.addEventListener("touchend", stopDrawing);

  toolButtons.forEach(button => {
    button.addEventListener("click", function () {
      setTool(button.dataset.tool);
    });
  });

  colorButtons.forEach(button => {
    button.addEventListener("click", function () {
      if (button.disabled) return;
      setColor(button.dataset.color);
    });
  });

  if (clearCanvasBtn) {
    clearCanvasBtn.addEventListener("click", function () {
      clearCanvas();
      scheduleStageCheck(9000);
    });
  }

  if (doneDrawingBtn) {
    doneDrawingBtn.addEventListener("click", function () {
      if (!hasDrawnThisStage) return;
      advanceStage();
    });
  }

  acceptCall.addEventListener("click", startGameAfterCall);

  declineCall.addEventListener("click", function () {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    stopRingtone();
    playCallAcceptedSound();
    cleanupMedia();

    setTimeout(function () {
      window.location.href = "/dashboard";
    }, 300);
  });

  if (hangupButton) {
    hangupButton.addEventListener("click", function () {
      cleanupMedia();
      window.location.href = "/dashboard";
    });
  }

  window.addEventListener("resize", resizeCanvasForDisplay);
  window.addEventListener("beforeunload", cleanupMedia);

  resizeCanvasForDisplay();
  setupCanvasStyle();
  updateRoundDisplay();
  setPalette(currentStage().palette);
  if (doneDrawingBtn) doneDrawingBtn.disabled = true;
  closeAllMouths();

  setTimeout(startRingtone, 400);
});
