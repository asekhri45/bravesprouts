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
    - Each scene has four drawing parts, but the social progression stays in 12 Match-Cards-style rounds.
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
    "#84cc16": "lime green",
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
      id: "flower_scene",
      name: "Flower Scene",
      sceneIntro: "First, let's make an outdoor scene.",
      newSceneLine: "First, let's make an outdoor scene.",
      completeLine: "The outdoor picture is finished.",
      stages: [
        {
          id: "flower",
          title: "Draw one pink flower",
          text: "Start with one pink flower.",
          partText: "Part 1 of 4",
          palette: [COLORS.pink, COLORS.yellow, COLORS.green],
          colorIdeas: {
            [COLORS.green]: "the stem or leaves",
            [COLORS.pink]: "the petals",
            [COLORS.yellow]: "the middle of the flower"
          },
          colorSuggestion: "Use any colors you want. Pink can be a nice flower color.",
          starLead: [
            "Let's start with one pink flower.",
            "First, make one pink flower anywhere on the page.",
            "Start with one pink flower first."
          ],
          starChoice: [
            "You can choose the stem, the petals, or the middle first.",
            "Pick any part of the flower to start.",
            "Start with whichever flower part feels easiest."
          ],
          teacherComment: [
            "That is a nice first part for the picture.",
            "A flower is a good place to start.",
            "I like starting with one clear flower."
          ],
          teacherWonder: [
            "I wonder what color this flower will be.",
            "Maybe this flower will have a bright middle.",
            "I wonder if this flower will have a tall stem."
          ],
          teacherToStar: [
            "Star, I wonder which part of the flower will come first.",
            "Star, maybe the flower could start with petals.",
            "Star, the flower might need a stem too."
          ],
          teacherDirect: [
            "What color should the flower be?",
            "Should the flower have big petals or little petals?",
            "What should go on the flower first?"
          ],
          donePraise: [
            "Great job. That flower looks sweet.",
            "Nice flower. You are a great artist.",
            "Good job. I like that flower."
          ]
        },
        {
          id: "grass",
          title: "Add grass",
          text: "Give the flower somewhere to grow.",
          partText: "Part 2 of 4",
          palette: [COLORS.green, COLORS.lime],
          colorIdeas: {
            [COLORS.green]: "darker grass",
            [COLORS.lime]: "lighter grass"
          },
          colorSuggestion: "For the grass, dark green can make deeper grass and light green can make brighter grass.",
          starLead: [
            "Now add grass under the flower.",
            "Next, put some grass near the flower.",
            "Now give the flower some grass."
          ],
          starChoice: [
            "The grass can be small, or it can go across the bottom.",
            "You can put the grass under the flower.",
            "Choose where the grass should go."
          ],
          teacherComment: [
            "Grass helps the flower look like it is outside.",
            "That is a good next part for the flower.",
            "The flower has somewhere to grow now."
          ],
          teacherWonder: [
            "I wonder if the grass will be light or dark green.",
            "Maybe the grass can go under the flower.",
            "I wonder how much grass this picture needs."
          ],
          teacherToStar: [
            "Star, I wonder where the grass should go.",
            "Star, maybe the grass could go under the flower.",
            "Star, light green and dark green could both work here."
          ],
          teacherDirect: [
            "Should the grass be little or big?",
            "Where should the grass go?",
            "Should the grass go across the picture?"
          ],
          donePraise: [
            "Great job. The grass looks nice.",
            "Good job adding grass.",
            "The flower has grass now. Nice work."
          ]
        },
        {
          id: "sun",
          title: "Add the sun",
          text: "Add sunshine to the picture.",
          partText: "Part 3 of 4",
          palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {
            [COLORS.yellow]: "the sun",
            [COLORS.orange]: "sun rays"
          },
          colorSuggestion: "For the sun, yellow can work well for the circle and orange can work well for the rays.",
          starLead: [
            "Now add a sun.",
            "Next, put a sun somewhere in the picture.",
            "Now the flower can have sunshine."
          ],
          starChoice: [
            "The sun can be big or small.",
            "You can put the sun in any open spot.",
            "Choose where the sun should go."
          ],
          teacherComment: [
            "Sunshine is a nice part for this picture.",
            "A sun will make the picture feel brighter.",
            "That is a bright next part."
          ],
          teacherWonder: [
            "I wonder if the sun will have rays.",
            "Maybe the sun can sit near the top.",
            "I wonder if this sun will be big."
          ],
          teacherToStar: [
            "Star, I wonder where the sun should go.",
            "Star, maybe the sun could have rays.",
            "Star, yellow and orange could both work here."
          ],
          teacherDirect: [
            "Should the sun be big or small?",
            "Where should the sun go?",
            "Should the sun have rays?"
          ],
          donePraise: [
            "Great job. That sun looks bright.",
            "Nice sun. Your picture is looking great.",
            "Good job adding sunshine."
          ]
        },
        {
          id: "butterfly",
          title: "Add a butterfly",
          text: "Finish the picture with a simple butterfly.",
          partText: "Part 4 of 4",
          palette: [COLORS.purple, COLORS.blue, COLORS.pink, COLORS.yellow],
          colorIdeas: {
            [COLORS.purple]: "butterfly wings",
            [COLORS.blue]: "butterfly wings",
            [COLORS.pink]: "butterfly wings",
            [COLORS.yellow]: "small butterfly details"
          },
          colorSuggestion: "For the butterfly, purple, blue, or pink can work well for wings, and yellow can work well for little details.",
          starLead: [
            "Let's finish this picture with a butterfly.",
            "Now add a small butterfly somewhere near the flower.",
            "One more part: add a butterfly."
          ],
          starChoice: [
            "The butterfly can go near the flower.",
            "You can make the butterfly any size.",
            "Choose where the butterfly should go."
          ],
          teacherComment: [
            "A butterfly is a sweet final part.",
            "That will make the picture feel friendly.",
            "I like that final detail."
          ],
          teacherWonder: [
            "I wonder what color the butterfly will be.",
            "Maybe the butterfly can fly near the flower.",
            "I wonder if the butterfly will have bright wings."
          ],
          teacherToStar: [
            "Star, I wonder where the butterfly should go.",
            "Star, maybe the butterfly could be near the flower.",
            "Star, the butterfly could have colorful wings."
          ],
          teacherDirect: [
            "What color should the butterfly be?",
            "Where should the butterfly go?",
            "Should the butterfly be big or small?"
          ],
          donePraise: [
            "Great job. The butterfly looks nice.",
            "Good job. This flower picture looks great.",
            "Nice work. You made a lovely picture."
          ]
        }
      ]
    },
    {
      id: "house_scene",
      name: "House Scene",
      sceneIntro: "Now let's make a house picture.",
      newSceneLine: "Now let's make a house picture.",
      completeLine: "The house picture is finished.",
      stages: [
        {
          id: "house",
          title: "Draw a house",
          text: "Start with one complete house.",
          partText: "Part 1 of 4",
          palette: [COLORS.red, COLORS.brown, COLORS.blue],
          colorIdeas: {
            [COLORS.red]: "the roof or door",
            [COLORS.brown]: "the walls or door",
            [COLORS.blue]: "the windows"
          },
          colorSuggestion: "For the house, red can work well for a roof or door, brown can work well for walls, and blue can work well for windows.",
          starLead: ["Start with one house.", "First, draw a complete house.", "Make the house first."],
          starChoice: ["The house can be big or small.", "You can choose where the door and windows go.", "Start with whichever house part feels easiest."],
          teacherComment: ["A house is a nice next picture.", "That is a clear thing to draw.", "I like starting with the main house."],
          teacherWonder: ["I wonder what color the house will be.", "Maybe the house will have windows.", "I wonder where the door will go."],
          teacherToStar: ["Star, I wonder what part of the house will come first.", "Star, maybe the house could have blue windows.", "Star, the house might need a door."],
          teacherDirect: ["What color should the house be?", "Where should the door go?", "Should the house be big or small?"],
          donePraise: ["Great job. That house looks good.", "Nice house. You are doing a great job.", "Good job making the house."]
        },
        {
          id: "yard",
          title: "Add a yard",
          text: "Add grass around the house.",
          partText: "Part 2 of 4",
          palette: [COLORS.green, COLORS.lime],
          colorIdeas: {[COLORS.green]: "darker grass", [COLORS.lime]: "lighter grass"},
          colorSuggestion: "For the yard, dark green can make deeper grass and light green can make brighter grass.",
          starLead: ["Now add a yard around the house.", "Next, add grass near the house.", "Now the house can have a yard."],
          starChoice: ["The yard can go under the house.", "You can make a little yard or a big yard.", "Choose where the grass should go."],
          teacherComment: ["A yard helps the house feel outside.", "That is a nice next part.", "The house has somewhere to sit now."],
          teacherWonder: ["I wonder if the yard will be light or dark green.", "Maybe the yard can go across the bottom.", "I wonder how much grass the house needs."],
          teacherToStar: ["Star, I wonder where the yard should go.", "Star, maybe the grass could go under the house.", "Star, both greens could work here."],
          teacherDirect: ["Should the yard be little or big?", "Where should the grass go?", "Should the yard go across the picture?"],
          donePraise: ["Great job adding the yard.", "Nice work. The house has grass now.", "Good job. The yard looks nice."]
        },
        {
          id: "sun",
          title: "Add the sun",
          text: "Add sunshine to the house picture.",
          partText: "Part 3 of 4",
          palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {[COLORS.yellow]: "the sun", [COLORS.orange]: "sun rays"},
          colorSuggestion: "For the sun, yellow can work well for the circle and orange can work well for the rays.",
          starLead: ["Now add a sun.", "Next, add sunshine above the house.", "The house can have a sun now."],
          starChoice: ["The sun can go in any open spot.", "The sun can be big or small.", "Choose where the sun should go."],
          teacherComment: ["A sun brightens the house picture.", "That is a nice sunny part.", "The picture is getting brighter."],
          teacherWonder: ["I wonder if the sun will have rays.", "Maybe the sun can go near the top.", "I wonder if the sun will be yellow or orange."],
          teacherToStar: ["Star, I wonder where the sun should go.", "Star, maybe the sun could have rays.", "Star, yellow and orange could both work here."],
          teacherDirect: ["Where should the sun go?", "Should the sun have rays?", "Should the sun be big or small?"],
          donePraise: ["Great job. That sun looks bright.", "Nice work adding sunshine.", "Good job. The house picture looks brighter now."]
        },
        {
          id: "tree",
          title: "Add a tree",
          text: "Finish the house picture with a tree.",
          partText: "Part 4 of 4",
          palette: [COLORS.brown, COLORS.green, COLORS.lime],
          colorIdeas: {[COLORS.brown]: "the tree trunk", [COLORS.green]: "tree leaves", [COLORS.lime]: "lighter leaves"},
          colorSuggestion: "For the tree, brown can work well for the trunk, and green or light green can work well for leaves.",
          starLead: ["Let's finish this picture with a tree.", "Now add a tree near the house.", "One more part: add a tree."],
          starChoice: ["The tree can go beside the house.", "You can make the tree tall or short.", "Choose where the tree should go."],
          teacherComment: ["A tree is a nice final part.", "That will make the house picture feel complete.", "I like that final detail."],
          teacherWonder: ["I wonder if the tree will be tall.", "Maybe the tree can go beside the house.", "I wonder how many leaves it will have."],
          teacherToStar: ["Star, I wonder where the tree should go.", "Star, maybe the tree could go beside the house.", "Star, brown and green could both help here."],
          teacherDirect: ["Where should the tree go?", "Should the tree be tall or short?", "What color should the leaves be?"],
          donePraise: ["Great job. The tree looks nice.", "Good job. The house picture looks complete.", "Nice work. You made a great house picture."]
        }
      ]
    },
    {
      id: "tree_scene",
      name: "Tree Scene",
      sceneIntro: "Now let's make a tree picture.",
      newSceneLine: "Now let's make a tree picture.",
      completeLine: "The tree picture is finished.",
      stages: [
        {
          id: "tree", title: "Draw a tree", text: "Start with one complete tree.", partText: "Part 1 of 4", palette: [COLORS.brown, COLORS.green, COLORS.lime],
          colorIdeas: {[COLORS.brown]: "the tree trunk", [COLORS.green]: "tree leaves", [COLORS.lime]: "lighter leaves"},
          colorSuggestion: "For the tree, brown can work well for the trunk, and green or light green can work well for leaves.",
          starLead: ["Start with one tree.", "First, draw a complete tree.", "Make the tree first."],
          starChoice: ["The tree can be tall or short.", "You can start with the trunk or the leaves.", "Start with whichever tree part feels easiest."],
          teacherComment: ["A tree is a good main part.", "That is a nice thing to draw.", "I like starting with the whole tree."],
          teacherWonder: ["I wonder if the tree will be tall.", "Maybe the tree will have lots of leaves.", "I wonder where the trunk will go."],
          teacherToStar: ["Star, I wonder what part of the tree will come first.", "Star, maybe the tree could have lots of leaves.", "Star, the tree might need a trunk too."],
          teacherDirect: ["Should the tree be tall or short?", "What color should the leaves be?", "Where should the trunk go?"],
          donePraise: ["Great job. That tree looks good.", "Nice tree. You are a great artist.", "Good job making the tree."]
        },
        {
          id: "grass", title: "Add grass", text: "Add grass under the tree.", partText: "Part 2 of 4", palette: [COLORS.green, COLORS.lime],
          colorIdeas: {[COLORS.green]: "darker grass", [COLORS.lime]: "lighter grass"},
          colorSuggestion: "For the grass, dark green can make deeper grass and light green can make brighter grass.",
          starLead: ["Now add grass under the tree.", "Next, put some grass near the tree.", "Now the tree can have grass."],
          starChoice: ["The grass can go under the tree.", "You can make a little grass or a lot of grass.", "Choose where the grass should go."],
          teacherComment: ["Grass is a good next part for the tree.", "The tree has somewhere to grow now.", "That makes the tree feel outside."],
          teacherWonder: ["I wonder if the grass will be light or dark green.", "Maybe the grass can go under the tree.", "I wonder how much grass the tree needs."],
          teacherToStar: ["Star, I wonder where the grass should go.", "Star, maybe the grass could go under the tree.", "Star, both greens could work here."],
          teacherDirect: ["Should the grass be little or big?", "Where should the grass go?", "Should the grass go across the picture?"],
          donePraise: ["Great job adding grass.", "Nice grass. The tree picture is looking good.", "Good job. The grass looks nice."]
        },
        {
          id: "sun", title: "Add the sun", text: "Add sunshine to the tree picture.", partText: "Part 3 of 4", palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {[COLORS.yellow]: "the sun", [COLORS.orange]: "sun rays"},
          colorSuggestion: "For the sun, yellow can work well for the circle and orange can work well for the rays.",
          starLead: ["Now add a sun.", "Next, add sunshine near the tree.", "The tree can have a sun now."],
          starChoice: ["The sun can go in any open spot.", "The sun can be big or small.", "Choose where the sun should go."],
          teacherComment: ["A sun is a bright next part.", "That will make the tree picture feel warm.", "The picture is getting brighter."],
          teacherWonder: ["I wonder if the sun will have rays.", "Maybe the sun can go near the top.", "I wonder if the sun will be yellow or orange."],
          teacherToStar: ["Star, I wonder where the sun should go.", "Star, maybe the sun could have rays.", "Star, yellow and orange could both work here."],
          teacherDirect: ["Where should the sun go?", "Should the sun have rays?", "Should the sun be big or small?"],
          donePraise: ["Great job. That sun looks bright.", "Nice work adding the sun.", "Good job. The tree picture looks brighter now."]
        },
        {
          id: "bird", title: "Add a bird", text: "Finish the tree picture with a small bird.", partText: "Part 4 of 4", palette: [COLORS.blue, COLORS.red, COLORS.yellow],
          colorIdeas: {[COLORS.blue]: "bird wings", [COLORS.red]: "the bird body", [COLORS.yellow]: "the beak"},
          colorSuggestion: "For the bird, blue can work well for wings, red can work well for the body, and yellow can work well for the beak.",
          starLead: ["Let's finish this picture with a bird.", "Now add a small bird near the tree.", "One more part: add a bird."],
          starChoice: ["The bird can sit near the tree or fly nearby.", "You can make the bird small.", "Choose where the bird should go."],
          teacherComment: ["A bird is a nice final part.", "That will make the tree picture feel friendly.", "I like that final detail."],
          teacherWonder: ["I wonder where the bird will go.", "Maybe the bird can sit near the tree.", "I wonder what color the bird will be."],
          teacherToStar: ["Star, I wonder where the bird should go.", "Star, maybe the bird could sit near the tree.", "Star, blue, red, and yellow could all help here."],
          teacherDirect: ["Where should the bird go?", "What color should the bird be?", "Should the bird be flying or sitting?"],
          donePraise: ["Great job. The bird looks nice.", "Good job. The tree picture looks complete.", "Nice work. You made a great tree picture."]
        }
      ]
    },
    {
      id: "school_scene",
      name: "School Scene",
      sceneIntro: "Now let's make a school picture.",
      newSceneLine: "Now let's make a school picture.",
      completeLine: "The school picture is finished.",
      stages: [
        {
          id: "school", title: "Draw a school", text: "Start with one school building.", partText: "Part 1 of 4", palette: [COLORS.red, COLORS.brown, COLORS.blue, COLORS.gray],
          colorIdeas: {[COLORS.red]: "the roof or door", [COLORS.brown]: "the school walls or door", [COLORS.blue]: "the windows", [COLORS.gray]: "the sidewalk or roof"},
          colorSuggestion: "For the school, red can work well for a roof or door, brown can work well for walls, blue can work well for windows, and gray can work well for a sidewalk or roof.",
          starLead: ["Start with one school building.", "First, draw the school.", "Make the school building first."],
          starChoice: ["The school can be big or small.", "You can choose where the door and windows go.", "Start with whichever school part feels easiest."],
          teacherComment: ["A school is a good final picture.", "That is a nice main part.", "I like starting with the school building."],
          teacherWonder: ["I wonder what color the school will be.", "Maybe the school will have windows.", "I wonder where the door will go."],
          teacherToStar: ["Star, I wonder what part of the school will come first.", "Star, maybe the school could have blue windows.", "Star, the school might need a door."],
          teacherDirect: ["What color should the school be?", "Where should the school door go?", "Should the school be big or small?"],
          donePraise: ["Great job. That school looks good.", "Nice school. You are doing a great job.", "Good job making the school."]
        },
        {
          id: "grass", title: "Add grass", text: "Add grass outside the school.", partText: "Part 2 of 4", palette: [COLORS.green, COLORS.lime],
          colorIdeas: {[COLORS.green]: "darker grass", [COLORS.lime]: "lighter grass"},
          colorSuggestion: "For the grass, dark green can make deeper grass and light green can make brighter grass.",
          starLead: ["Now add grass outside the school.", "Next, put grass near the school.", "Now the school can have grass outside."],
          starChoice: ["The grass can go near the school.", "You can make a little grass or a lot of grass.", "Choose where the grass should go."],
          teacherComment: ["Grass makes the school picture feel outside.", "That is a nice next part.", "The school has space outside now."],
          teacherWonder: ["I wonder if the grass will be light or dark green.", "Maybe the grass can go outside the school.", "I wonder how much grass the school needs."],
          teacherToStar: ["Star, I wonder where the grass should go.", "Star, maybe the grass could go outside the school.", "Star, both greens could work here."],
          teacherDirect: ["Should the grass be little or big?", "Where should the grass go?", "Should the grass go across the picture?"],
          donePraise: ["Great job adding grass.", "Nice grass. The school picture is looking good.", "Good job. The grass looks nice."]
        },
        {
          id: "sun", title: "Add the sun", text: "Add sunshine to the school picture.", partText: "Part 3 of 4", palette: [COLORS.yellow, COLORS.orange],
          colorIdeas: {[COLORS.yellow]: "the sun", [COLORS.orange]: "sun rays"},
          colorSuggestion: "For the sun, yellow can work well for the circle and orange can work well for the rays.",
          starLead: ["Now add a sun.", "Next, add sunshine near the school.", "The school can have a sun now."],
          starChoice: ["The sun can go in any open spot.", "The sun can be big or small.", "Choose where the sun should go."],
          teacherComment: ["A sun is a bright next part.", "That will make the school picture feel warm.", "The picture is getting brighter."],
          teacherWonder: ["I wonder if the sun will have rays.", "Maybe the sun can go near the top.", "I wonder if the sun will be yellow or orange."],
          teacherToStar: ["Star, I wonder where the sun should go.", "Star, maybe the sun could have rays.", "Star, yellow and orange could both work here."],
          teacherDirect: ["Where should the sun go?", "Should the sun have rays?", "Should the sun be big or small?"],
          donePraise: ["Great job. That sun looks bright.", "Nice work adding the sun.", "Good job. The school picture looks brighter now."]
        },
        {
          id: "children", title: "Add children", text: "Finish the school picture with children outside.", partText: "Part 4 of 4", palette: [COLORS.red, COLORS.blue, COLORS.pink, COLORS.purple, COLORS.yellow],
          colorIdeas: {[COLORS.red]: "a child's shirt", [COLORS.blue]: "a child's shirt or pants", [COLORS.pink]: "a child's shirt", [COLORS.purple]: "a child's shirt", [COLORS.yellow]: "hair or a shirt"},
          colorSuggestion: "For the children, red, blue, pink, purple, or yellow can work well for clothes or small details.",
          starLead: ["Let's finish this picture with children outside the school.", "Now add some children near the school.", "One more part: add children outside."],
          starChoice: ["The children can be simple stick figures.", "You can put the children outside the school.", "Choose where the children should go."],
          teacherComment: ["Children outside make the school picture feel friendly.", "That is a nice final part.", "I like that final detail."],
          teacherWonder: ["I wonder where the children will stand.", "Maybe the children can be outside the school.", "I wonder what colors their clothes will be."],
          teacherToStar: ["Star, I wonder where the children should go.", "Star, maybe the children could stand outside the school.", "Star, those colors could work for clothes."],
          teacherDirect: ["Where should the children go?", "What colors should their clothes be?", "Should the children be next to the school?"],
          donePraise: ["Great job. The children look nice.", "Good job. The school picture looks complete.", "Nice work. You made a great school picture."]
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
  let passiveDoneTimer = null;
  let passiveDoneEnabled = false;
  let passiveMediaRecorder = null;
  let passiveRecordingChunks = [];
  let passiveRecordingTimer = null;
  let passiveRestartTimer = null;
  let passiveIgnoreNextStop = false;
  let passiveTranscribing = false;

  // Primary always-listening path for Chrome/Edge.
  // This gives immediate text events instead of waiting for short audio chunks
  // to finish uploading/transcribing. MediaRecorder remains as a fallback.
  let passiveSpeechRecognition = null;
  let passiveSpeechRestartTimer = null;
  let passiveSpeechManuallyStopped = false;
  let passiveLastDetectedText = "";
  let passiveLastDetectedAt = 0;

  const PASSIVE_DONE_CHUNK_MS = 2300;
  let colorReactionTimer = null;
  let canvasSaveTimer = null;
  let savedCanvasDataToRestore = "";
  let restoredCanvasData = false;

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
      totalStrokeCount: 0,
      teacherNameMentions: 0,
      teacherColorLineCount: 0,
      sceneChoiceAsked: false,
      sideQuestionSceneIndex: -1,
      lastSpontaneousQuestionAt: 0,
      lastDoneHeardAt: 0,
      pendingDoneConfirmation: false,
      teacherSupportForStarCount: 0,

      stageStartedAt: 0,
      drawingCommentsThisStage: 0,
      colorCommentsThisStage: 0,
      doneChecksThisStage: 0,
      doneRemindersThisStage: 0,
      noSpeechDoneChecksThisStage: 0,
      lastGuidanceAt: 0,
      lastColorCommentAt: 0,
      lastColorCommentedColor: null,
      sameColorCommentStreak: 0,
      stageAdvanceLocked: false,

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

  function getSocialRound() {
    return Math.max(1, Math.min(TARGET_SOCIAL_ROUNDS, state.sceneIndex + 1));
  }

  function getProgressMode() {
    if (state.sceneIndex <= 0) return "star_leads";
    if (state.sceneIndex === 1) return "teacher_wonders_star_bridges";
    if (state.sceneIndex === 2) return "teacher_to_star_to_child";
    return "teacher_direct_with_star_support";
  }

  function setPrompt(stage) {
    if (promptTitle) promptTitle.textContent = stage.title;
    if (promptText) {
      const scene = currentScene();
      promptText.textContent = `${scene.name} • ${stage.partText}. ${stage.text} Tell us whenever this part feels done.`;
    }
  }

  function updateRoundDisplay() {
    state.socialRound = getSocialRound();

    if (roundNumber) {
      roundNumber.textContent = String(state.socialRound);
    }
  }

  function updateQuietStatus(text) {
    // Intentionally hidden from the child UI.
    if (quietStatusText) {
      quietStatusText.textContent = "";
    }
  }

  async function loadSavedDrawingProgress() {
    try {
      const response = await fetch(`/api/drawing-game/state?activity_id=${activityId}`);

      if (!response.ok) return;

      const data = await response.json();

      if (!data.success || !data.state) return;

      const saved = data.state;
      const maxScene = drawingScenes.length - 1;

      state.sceneIndex = Math.max(0, Math.min(maxScene, Number(saved.scene_index || 0)));
      state.stageIndex = Math.max(0, Math.min(currentScene().stages.length - 1, Number(saved.stage_index || 0)));
      state.scenesCompleted = Math.max(0, Number(saved.scenes_completed || 0));
      state.stagesCompleted = Math.max(0, Number(saved.stages_completed || 0));
      state.roundsCompleted = Math.max(0, Number(saved.rounds_completed || 0));
      state.spokenResponses = Math.max(0, Number(saved.spoken_responses || 0));
      state.silentWindows = Math.max(0, Number(saved.silent_windows || 0));
      state.totalColorSelections = Math.max(0, Number(saved.total_color_selections || 0));
      savedCanvasDataToRestore = String(saved.canvas_data || "");

      if (!savedCanvasDataToRestore && state.stageIndex > 0) {
        state.stageIndex = 0;
      }

      updateRoundDisplay();
      setPrompt(currentStage());
      setPalette(currentStage().palette);
    } catch (error) {
      console.warn("Could not load drawing progress:", error);
    }
  }

  async function saveDrawingProgress(extra = {}) {
    if (state.gameCompleted) return;

    const payload = {
      activity_id: activityId,
      scene_index: state.sceneIndex,
      stage_index: state.stageIndex,
      scenes_completed: state.scenesCompleted,
      stages_completed: state.stagesCompleted,
      rounds_completed: state.roundsCompleted,
      spoken_responses: state.spokenResponses,
      silent_windows: state.silentWindows,
      total_color_selections: state.totalColorSelections,
      canvas_data: Object.prototype.hasOwnProperty.call(extra, "canvas_data") ? extra.canvas_data : getCanvasData(),
      ...extra
    };

    try {
      await fetch("/api/drawing-game/save-progress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } catch (error) {
      console.warn("Could not save drawing progress:", error);
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
    if (typeof options.shouldStart === "function" && !options.shouldStart()) {
      return;
    }

    const rawText = typeof text === "function" ? text() : text;
    const calmText = cleanLine(rawText);

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

      if (typeof options.shouldPlay === "function" && !options.shouldPlay()) {
        return;
      }

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
      updateQuietStatus("Drawing together");
    }

    if (options.expectsResponse) {
      await askForResponse(actor, calmText, options);
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
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      state.micReady = true;
      return mediaStream;
    } catch (error) {
      console.warn("Mic permission unavailable:", error);
      state.micDenied = true;
      return null;
    }
  }

  function isExplicitRecorderActive() {
    return Boolean(mediaRecorder && mediaRecorder.state && mediaRecorder.state !== "inactive");
  }

  function isPassiveRecorderActive() {
    return Boolean(passiveMediaRecorder && passiveMediaRecorder.state && passiveMediaRecorder.state !== "inactive");
  }

  function updateMicIndicator() {
    if (!micControl) return;

    const shouldShowListening = Boolean(
      state.isListening
      || state.waitingForResponse
      || passiveDoneEnabled
      || isPassiveRecorderActive()
    );

    micControl.classList.toggle("quiet-listening", shouldShowListening);
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

      let resolvedAudio = false;

      function resolveAudioPlayback() {
        if (resolvedAudio) return;
        resolvedAudio = true;
        stopMouthAnimation();
        resolve();
      }

      activeAudio.addEventListener("ended", resolveAudioPlayback);
      activeAudio.addEventListener("pause", function () {
        if (activeAudio && activeAudio.currentTime > 0) {
          resolveAudioPlayback();
        }
      });

      activeAudio.addEventListener("error", resolveAudioPlayback);

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
    const shouldResumePassiveAfterResponse = passiveDoneEnabled && question?.intent !== "passive_stage_done";

    if (shouldResumePassiveAfterResponse) {
      pausePassiveDoneListenForResponse();
    }

    const stream = await ensureMicPermission();

    if (!stream) {
      state.waitingForResponse = false;
      state.currentQuestion = null;
      if (shouldResumePassiveAfterResponse) schedulePassiveDoneListen(400);
      await handleNoSpeech(question);
      updateMicIndicator();
      return;
    }

    question.resumePassiveAfterResponse = shouldResumePassiveAfterResponse;

    const tile = getTile(question.actor || "star");

    if (tile) tile.classList.add("soft-listening");
    if (micControl) micControl.classList.add("quiet-listening");
    updateMicIndicator();

    updateQuietStatus("Listening quietly");

    recordingChunks = [];
    state.isListening = true;
    updateMicIndicator();

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
    updateMicIndicator();

    updateQuietStatus("Drawing together");

    try {
      if (!recordingChunks.length) {
        await handleNoSpeech(question);
        return null;
      }

      const blob = new Blob(recordingChunks, {
        type: recordingChunks[0]?.type || "audio/webm"
      });

      recordingChunks = [];

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
    } finally {
      recordingChunks = [];
      mediaRecorder = null;

      if (question?.resumePassiveAfterResponse
          && !state.gameCompleted
          && !state.stageAdvanceLocked
          && !state.pendingDoneConfirmation) {
        schedulePassiveDoneListen(350);
      }

      updateMicIndicator();
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

  function interruptCurrentCharacterAudio() {
    if (activeAudio) {
      try {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      } catch (error) {}
    }

    stopMouthAnimation();
    state.isSpeaking = false;
    speechQueue = Promise.resolve();
  }

  async function handleDoneIntentFromSpeech() {
    const now = Date.now();

    if (now - state.lastDoneHeardAt < 1200) return;

    state.lastDoneHeardAt = now;
    interruptCurrentCharacterAudio();
    await askStarConfirmStageDone();
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

  function transcriptHasExplicitDoneIntent(text) {
    const lower = String(text || "").toLowerCase();

    const explicitDonePhrases = [
      "i'm done", "im done", "i am done", "all done", "i'm finished",
      "im finished", "i am finished", "finished", "done", "this is done",
      "it is done", "it's done", "its done", "next part", "move on",
      "go to the next", "ready for the next", "ready to move", "that's it",
      "that is it"
    ];

    return explicitDonePhrases.some(phrase => lower.includes(phrase));
  }

  function transcriptHasPassiveDoneIntent(text) {
    const lower = String(text || "").toLowerCase();

    const keepPhrases = [
      "not done", "not finished", "i'm not done", "im not done",
      "i am not done", "more time", "keep drawing", "keep working",
      "wait", "not yet", "a little more"
    ];

    if (keepPhrases.some(phrase => lower.includes(phrase))) {
      return false;
    }

    const nextPart = nextStageNameForSpeech().toLowerCase();
    const nextScene = nextSceneNameForSpeech().toLowerCase();

    const donePhrases = [
      "i'm done", "im done", "i am done", "all done",
      "i'm finished", "im finished", "i am finished",
      "this is done", "it is done", "it's done", "its done",
      "i'm ready", "im ready", "i am ready",
      "move on", "next part", "next stage", "go to the next",
      "ready for the next", "ready to move", "let's move on", "lets move on",
      "that's it", "that is it"
    ];

    if (donePhrases.some(phrase => lower.includes(phrase))) {
      return true;
    }

    if (nextPart && nextPart !== "the next part") {
      const nextPartPhrases = [
        `draw the ${nextPart}`,
        `drawing the ${nextPart}`,
        `add the ${nextPart}`,
        `start the ${nextPart}`,
        `do the ${nextPart}`,
        `let's do the ${nextPart}`,
        `lets do the ${nextPart}`,
        `go to the ${nextPart}`
      ];

      if (nextPartPhrases.some(phrase => lower.includes(phrase))) {
        return true;
      }
    }

    if (nextScene && nextScene !== "the next picture") {
      const sceneName = nextScene.replace(/^the /, "");
      const nextScenePhrases = [
        `draw the ${sceneName}`,
        `start the ${sceneName}`,
        `do the ${sceneName}`,
        `go to the ${sceneName}`
      ];

      if (nextScenePhrases.some(phrase => lower.includes(phrase))) {
        return true;
      }
    }

    return false;
  }

  function classifyStageDoneResponse(text) {
    const lower = String(text || "").toLowerCase();
    const words = new Set(normalizedWords(lower));
    const nextPart = nextStageNameForSpeech().toLowerCase();
    const nextScene = nextSceneNameForSpeech().toLowerCase();

    const stopPhrases = [
      "done for the day", "be done for the day", "stop for today",
      "stop now", "i want to stop", "go back", "dashboard", "no more"
    ];

    const moveWords = [
      "draw", "drawing", "add", "start", "go", "move", "next",
      "ready", "continue", "let's", "lets", "want"
    ];

    const keepPhrases = [
      "keep adding", "keep working", "continue working", "add more",
      "more details", "not yet", "not done", "not finished",
      "keep going", "stay here", "wait", "more time", "a little more"
    ];

    const mentionsNextPart = nextPart && nextPart !== "the next part" && lower.includes(nextPart);
    const mentionsNextScene = nextScene && nextScene !== "the next picture" && lower.includes(nextScene.replace(/^the /, ""));
    const hasMoveWord = moveWords.some(word => lower.includes(word));
    const asksForMoreDrawingTime = lower.includes("more time") || lower.includes("a little more") || lower.includes("more details");

    if (stopPhrases.some(phrase => lower.includes(phrase))) return "stop";

    // After Star offers the next part/scene, answers like "draw the grass" or even
    // just "grass" should count as moving on, not as unclear or "keep drawing."
    if ((mentionsNextPart || mentionsNextScene) && !lower.includes("not ") && !asksForMoreDrawingTime) {
      if (hasMoveWord || words.size <= 4) return "done";
    }

    if (lower.includes("move on") || lower.includes("next part") || lower.includes("next stage")) return "done";
    if (keepPhrases.some(phrase => lower.includes(phrase))) return "keep";
    if (words.has("no") || words.has("nope") || words.has("nah")) return "keep";
    if (transcriptHasExplicitDoneIntent(text)) return "done";

    if (words.has("yes") || words.has("yeah") || words.has("yep") || words.has("okay") || words.has("ok")) {
      return "done";
    }

    return "unclear";
  }

  function transcriptSoundsLikeDone(text) {
    return transcriptHasExplicitDoneIntent(text);
  }

  function isLikelyChildQuestion(text) {
    const lower = String(text || "").toLowerCase().trim();
    if (!lower) return false;

    const starters = [
      "how", "what", "why", "where", "when", "can", "could",
      "should", "do you", "does", "did", "is", "are", "am i"
    ];

    return lower.includes("?") || starters.some(starter => lower.startsWith(starter + " "));
  }

  function transcriptAsksAboutFinished(text) {
    const lower = String(text || "").toLowerCase();
    return (
      lower.includes("ready")
      || lower.includes("finish")
      || lower.includes("finished")
      || lower.includes("done")
      || lower.includes("move on")
      || lower.includes("next")
    );
  }

  function transcriptAsksAboutDrawing(text) {
    const lower = String(text || "").toLowerCase();
    return (
      lower.includes("drawing")
      || lower.includes("picture")
      || lower.includes("look")
      || lower.includes("looks")
      || lower.includes("good")
      || lower.includes("nice")
      || lower.includes("color")
    );
  }

  async function handleSpontaneousQuestion(transcript) {
    const now = Date.now();

    if (now - state.lastSpontaneousQuestionAt < 5000) {
      schedulePassiveDoneListen(1800);
      return;
    }

    state.lastSpontaneousQuestionAt = now;

    if (transcriptAsksAboutFinished(transcript)) {
      await speakNow(TEACHER_ACTOR, pickLine([
        "It looks close to ready to me. You can tell Star when this part is done, or add a little more.",
        "I think this part is looking good. If it feels finished, you can tell Star that you are done.",
        "It is looking ready. You can keep adding details, or tell Star when you are done."
      ]));
      schedulePassiveDoneListen(1200);
      return;
    }

    if (transcriptAsksAboutDrawing(transcript)) {
      await speakNow(TEACHER_ACTOR, pickLine([
        "It is looking good so far. Nice work.",
        "I like how your picture is coming together. Great job.",
        "Your drawing is looking really nice so far."
      ]));
      schedulePassiveDoneListen(1200);
      return;
    }

    await speakNow("star", pickLine([
      "Good question. You can keep drawing, and the Teacher can help notice the picture.",
      "That's a good question. Keep going when you're ready.",
      "Good question. You can keep working on this part."
    ]));

    schedulePassiveDoneListen(1200);
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

    if (question?.intent === "passive_stage_done") {
      if (transcriptHasPassiveDoneIntent(transcript)) {
        await handleDoneIntentFromSpeech();
        return;
      }

      if (isLikelyChildQuestion(transcript)) {
        await handleSpontaneousQuestion(transcript);
        return;
      }

      schedulePassiveDoneListen(1600);
      return;
    }

    if (question?.intent === "scene_choice") {
      await handleSceneChoiceResponse(transcript);
      return;
    }

    if (question?.intent === "stage_done") {
      await handleStageDoneResponse(transcript, question);
      return;
    }

    if (question?.intent === "side_question") {
      await speakNow("star", pickLine([
        "Thanks for telling me.",
        "That sounds nice.",
        "I like hearing about that.",
        "That makes sense."
      ]));

      if (getProgressMode() !== "star_leads" && drawingHasBase()) {
        await sleep(120);
        await speakNow(TEACHER_ACTOR, pickLine([
          "I liked hearing that.",
          "That was nice to hear.",
          "Thank you for sharing that."
        ]));
      }

      scheduleStageCheck(6500);
      schedulePassiveDoneListen(1400);
      return;
    }

    if (hasDrawnThisStage && transcriptSoundsLikeDone(transcript)) {
      await handleDoneIntentFromSpeech();
      return;
    }

    if (isLikelyChildQuestion(transcript) && (!question || question.intent === "side_question" || question.source === "passive-stage-done")) {
      await handleSpontaneousQuestion(transcript);
      return;
    }

    if (question?.source === "teacher-direct") {
      await speakNow(TEACHER_ACTOR, pickLine([
        "Nice choice.",
        "Good choice.",
        "Thanks for telling me. Good job.",
        "Okay. I like that idea.",
        "That sounds good."
      ]));

      await sleep(180);

      await speakNow("star", pickLine([
        "Let's use that idea.",
        "That works for this picture.",
        "Keep going when you're ready.",
        "That sounds good for this part."
      ]));

      scheduleStageCheck(6500);
      return;
    }

    if (question?.source === "teacher-redirect") {
      await speakNow("star", pickLine([
        "Okay. Let's use that.",
        "That works.",
        "That sounds good.",
        "Let's try that.",
        "Keep going when you're ready."
      ]));

      scheduleStageCheck(6500);
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
      "Okay. Let's add that.",
      "That sounds good.",
      "Let's try that.",
      "That will look nice."
    ]));

    scheduleStageCheck(6500);
  }

  function friendlyStageNameForSpeech(stage = currentStage()) {
    const names = {
      flower: "flower",
      grass: "grass",
      sun: "sun",
      butterfly: "butterfly",
      house: "house",
      yard: "yard",
      tree: "tree",
      school: "school",
      children: "children"
    };

    return names[stage.id] || stage.title.replace(/^Add\s+/i, "").replace(/^Draw\s+/i, "").toLowerCase();
  }

  function friendlySceneNameForSpeech(scene = currentScene()) {
    const names = {
      flower_scene: "flower picture",
      house_scene: "house picture",
      tree_scene: "tree picture",
      school_scene: "school picture"
    };

    return names[scene.id] || String(scene.name || "picture").toLowerCase();
  }

  function nextStageNameForSpeech() {
    const scene = currentScene();
    const nextStage = scene.stages[state.stageIndex + 1];

    if (!nextStage) return "the next part";

    return friendlyStageNameForSpeech(nextStage);
  }

  function nextSceneNameForSpeech() {
    const nextScene = drawingScenes[state.sceneIndex + 1];

    if (!nextScene) return "the next picture";

    return friendlySceneNameForSpeech(nextScene);
  }

  function isLastStageInCurrentScene() {
    const scene = currentScene();
    return state.stageIndex >= scene.stages.length - 1;
  }

  function isLastSceneInGame() {
    return state.sceneIndex >= drawingScenes.length - 1;
  }

  async function askStarConfirmStageDone() {
    if (state.pendingDoneConfirmation || state.stageAdvanceLocked || state.gameCompleted) return;

    state.pendingDoneConfirmation = true;
    clearStageCheckTimer();
    clearPassiveDoneTimer();

    const stage = currentStage();
    const partName = friendlyStageNameForSpeech();
    const sceneName = friendlySceneNameForSpeech();

    await speakNow(TEACHER_ACTOR, pickLine([
      `Your ${partName} is looking great so far.`,
      `I like how your ${partName} is coming together.`,
      `This is looking really nice so far.`
    ]));

    await sleep(140);

    let options;

    if (isLastStageInCurrentScene() && !isLastSceneInGame()) {
      const nextSceneName = nextSceneNameForSpeech();

      options = [
        `Do you want to be done with this ${sceneName} and draw the ${nextSceneName} now, or keep adding details?`,
        `Should we start the ${nextSceneName} now, or do you want more time with this ${sceneName}?`,
        `Do you want to move on to drawing the ${nextSceneName}, or keep working on this ${sceneName}?`
      ];
    } else if (isLastStageInCurrentScene() && isLastSceneInGame()) {
      options = [
        `Do you want to finish drawing for today, or keep adding details to this ${sceneName}?`,
        `Should we be done drawing for today, or do you want more time with this ${sceneName}?`,
        `Do you want to finish for today, or keep working on this ${sceneName}?`
      ];
    } else {
      const nextPartName = nextStageNameForSpeech();

      options = [
        `Do you want to continue adding details to the ${partName}, or move on to drawing the ${nextPartName} now?`,
        `Should we draw the ${nextPartName} now, or do you want more time with the ${partName}?`,
        `Do you want to move on to drawing the ${nextPartName}, or keep working on the ${partName}?`
      ];
    }

    await queueSpeak("star", pickLine(options), {
      expectsResponse: true,
      askType: "choice",
      source: "star-done-confirm",
      intent: "stage_done",
      responseSeconds: 8.5
    });
  }

  async function handleStageDoneResponse(transcript) {
    const choice = classifyStageDoneResponse(transcript);
    const shouldMoveStraightToNextScene = isLastStageInCurrentScene() && !isLastSceneInGame();
    const shouldFinishGame = isLastStageInCurrentScene() && isLastSceneInGame();

    state.pendingDoneConfirmation = false;

    if (choice === "stop") {
      await speakNow("star", pickLine([
        "Okay. We can be done for the day.",
        "Okay, we can stop here for today.",
        "Sure. We can be done for the day."
      ]));
      await saveDrawingProgress();
      cleanupMedia();
      window.location.href = "/dashboard";
      return;
    }

    if (choice === "done") {
      if (shouldFinishGame) {
        await speakNow("star", pickLine([
          "Okay. We can finish drawing for today.",
          "Got it. This picture is ready.",
          "Okay. We can be done drawing for today."
        ]));
      } else if (shouldMoveStraightToNextScene) {
        await speakNow("star", pickLine([
          `Okay. Let's move on to drawing the ${nextSceneNameForSpeech()}.`,
          `Got it. We can start the ${nextSceneNameForSpeech()} now.`,
          `Okay. This ${friendlySceneNameForSpeech()} is ready, so we can go to the ${nextSceneNameForSpeech()}.`
        ]));
      } else {
        await speakNow("star", pickLine([
          `Okay. Let's move to the ${nextStageNameForSpeech()}.`,
          `Got it. We can go to the ${nextStageNameForSpeech()}.`,
          `Okay, this part is ready. Let's add the ${nextStageNameForSpeech()}.`
        ]));
      }

      await advanceStage({
        skipSceneChoice: shouldMoveStraightToNextScene,
        skipTeacherPraise: true
      });
      return;
    }

    if (choice === "keep") {
      await speakNow("star", pickLine([
        "Okay. Keep working on this part.",
        "Sure. Add a little more when you want.",
        "Okay, keep going with this part."
      ]));

      scheduleStageCheck(11000);
      schedulePassiveDoneListen(1600);
      return;
    }

    await speakNow("star", pickLine([
      "That's okay. Keep working on this part for now.",
      "No rush. You can keep going.",
      "That's okay. Add more when you are ready."
    ]));

    scheduleStageCheck(11000);
    schedulePassiveDoneListen(1600);
  }

  function classifySceneChoice(text) {
    const lower = String(text || "").toLowerCase();
    const words = new Set(normalizedWords(lower));

    const stopPhrases = [
      "be done", "done for the day", "all done", "i'm done", "im done",
      "i am done", "stop", "finish", "finished", "no more", "go back",
      "dashboard", "that's enough", "that is enough", "i want to stop"
    ];

    const continuePhrases = [
      "another", "next", "more", "keep going", "continue", "keep drawing",
      "play another", "draw another", "one more", "yes", "yeah", "yep", "sure", "okay", "ok"
    ];

    if (stopPhrases.some(phrase => lower.includes(phrase))) return "stop";
    if (continuePhrases.some(phrase => lower.includes(phrase))) return "continue";

    if (words.has("no") || words.has("nope") || words.has("nah")) return "stop";

    return "unclear";
  }

  async function handleSceneChoiceResponse(transcript) {
    const choice = classifySceneChoice(transcript);

    if (choice === "stop") {
      await speakNow("star", pickLine([
        "Okay. We can be done for the day.",
        "Okay, we can stop here for today.",
        "Sure. We can be done for the day."
      ]));
      await saveDrawingProgress();
      cleanupMedia();
      window.location.href = "/dashboard";
      return;
    }

    if (choice === "continue") {
      await speakNow("star", pickLine([
        `Okay. Let's move on to drawing the ${nextSceneNameForSpeech()}.`,
        `Great. We can start the ${nextSceneNameForSpeech()} now.`,
        `Okay, let's go to the ${nextSceneNameForSpeech()}.`
      ]));
      await continueToNextScene();
      return;
    }

    await speakNow("star", pickLine([
      "That's okay. We can pause here for a moment.",
      "No worries. You can tell me if you want another picture or if you are done for the day.",
      "That's okay. We can wait here."
    ]));
    await offerContinueAfterScene();
  }

  async function handleNoSpeech(question) {
    state.silentWindows += 1;

    if (!question) return;

    if (question.intent === "passive_stage_done") {
      schedulePassiveDoneListen(1600);
      return;
    }

    if (question.intent === "scene_choice") {
      await speakNow("star", pickLine([
        "That's okay. We can wait here.",
        "No rush. You can tell me if you want another picture or if you are done for the day.",
        "That's okay. We do not have to decide right away."
      ]));
      await offerContinueAfterScene();
      return;
    }

    if (question.intent === "stage_done") {
      state.pendingDoneConfirmation = false;
      state.noSpeechDoneChecksThisStage += 1;

      await speakNow("star", pickLine([
        "That's okay. Keep working on this part for now.",
        "No rush. You can add more when you want.",
        "That's okay. Keep going when you're ready."
      ]));

      scheduleStageCheck(9000);
      schedulePassiveDoneListen(1600);
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
        "That's okay. Keep going when you're ready.",
        "No rush. You can add more when you want.",
        "That's okay. Take your time."
      ]));

      scheduleStageCheck(6500);
      return;
    }

    await speakNow("star", pickLine([
      "That's okay. Keep going when you're ready.",
      "No rush. You can add more when you want.",
      "That's okay. Take your time."
    ]));

    scheduleStageCheck(6500);
  }

  function getCanvasData() {
    if (!canvas) return "";

    try {
      return canvas.toDataURL("image/png");
    } catch (error) {
      console.warn("Could not read drawing canvas:", error);
      return "";
    }
  }

  function restoreCanvasFromData(canvasData) {
    return new Promise(resolve => {
      if (!canvasData || restoredCanvasData) {
        resolve(false);
        return;
      }

      const image = new Image();

      image.onload = function () {
        try {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
          restoredCanvasData = true;
          resolve(true);
        } catch (error) {
          console.warn("Could not restore drawing canvas:", error);
          resolve(false);
        }
      };

      image.onerror = function () {
        resolve(false);
      };

      image.src = canvasData;
    });
  }

  function scheduleCanvasSave(delayMs = 1800) {
    if (state.gameCompleted) return;

    if (canvasSaveTimer) {
      clearTimeout(canvasSaveTimer);
    }

    canvasSaveTimer = setTimeout(function () {
      canvasSaveTimer = null;
      saveDrawingProgress();
    }, delayMs);
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
    scheduleStageCheck(12000);
    schedulePassiveDoneListen(1800);
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
    state.totalStrokeCount += 1;

    maybeReactDuringDrawing();

    if (strokeCountThisStage >= 15) {
      scheduleStageCheck(10000);
      schedulePassiveDoneListen(1200);
    }

    scheduleCanvasSave(1800);
  }

  function stopDrawing() {
    isDrawing = false;
    lastPoint = null;

    if (hasDrawnThisStage) {
      scheduleCanvasSave(400);
    }
  }

  function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    resetStageDrawingState();
    saveDrawingProgress({ canvas_data: "" });
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
    clearPassiveDoneTimer();

    state.stageStartedAt = Date.now();
    state.drawingCommentsThisStage = 0;
    state.colorCommentsThisStage = 0;
    state.doneChecksThisStage = 0;
    state.doneRemindersThisStage = 0;
    state.noSpeechDoneChecksThisStage = 0;
    state.lastGuidanceAt = 0;
    state.lastColorCommentAt = 0;
    state.lastColorCommentedColor = null;
    state.sameColorCommentStreak = 0;
    state.stageAdvanceLocked = false;
    state.pendingDoneConfirmation = false;

    if (colorReactionTimer) {
      clearTimeout(colorReactionTimer);
      colorReactionTimer = null;
    }

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
    const previousColor = currentColor;
    currentColor = color;
    currentTool = "pen";

    colorButtons.forEach(button => {
      button.classList.toggle("active", button.dataset.color === color);
    });

    setTool("pen");

    if (!options.silent && previousColor !== color) {
      state.totalColorSelections += 1;
      maybeReactToColorChange(color);
      saveDrawingProgress({ total_color_selections: state.totalColorSelections });
    }
  }

  function colorName(color) {
    return COLOR_NAMES[color] || "that color";
  }

  function colorIdeaForStage(color) {
    const stage = currentStage();
    return stage.colorIdeas?.[color] || "this part of the picture";
  }

  function drawingHasBase() {
    return state.totalStrokeCount >= 22 || strokeCountThisStage >= 12;
  }

  function shouldUseChildNameInTeacherLine() {
    if (!childName || childName.toLowerCase() === "there") return false;

    return state.teacherColorLineCount === 1 || state.teacherColorLineCount % 4 === 0;
  }

  function addTeacherPraiseToColorLine(line) {
    if (!drawingHasBase()) return line;

    const everyFourthColor = state.totalColorSelections > 0 && state.totalColorSelections % 4 === 0;

    if (everyFourthColor) {
      const praise = pickLine([
        " Great job. Your drawing is looking great so far.",
        " Nice work. This picture is really coming together.",
        " Good job. I can see how much you have added."
      ]);
      return `${line}${praise}`;
    }

    if (Math.random() < 0.62) {
      const praise = pickLine([
        " Good job.",
        " Nice work.",
        " That is a great choice.",
        " Your drawing is looking good so far.",
        " You are doing a great job."
      ]);
      return `${line}${praise}`;
    }

    return line;
  }

  function buildTeacherColorComment(color) {
    const label = colorName(color);
    const idea = colorIdeaForStage(color);
    const isSameColorAgain = state.lastColorCommentedColor === color;

    state.teacherColorLineCount += 1;

    if (isSameColorAgain) {
      state.sameColorCommentStreak += 1;
    } else {
      state.sameColorCommentStreak = 0;
    }

    state.lastColorCommentedColor = color;

    const includeName = shouldUseChildNameInTeacherLine();

    if (includeName) {
      state.teacherNameMentions += 1;
    }

    // For repeated comments on the same color within the same stage, avoid
    // saying the same "great for stem/leaves" type recommendation each time.
    // First same-color repeat becomes an observation; occasional later repeats
    // may mention the stage idea again, but most stay general.
    if (isSameColorAgain) {
      const shouldMentionIdeaAgain = state.sameColorCommentStreak >= 3 && Math.random() < 0.25;

      const repeatOptions = includeName
        ? [
            `I see that you are still using ${label}, ${childName}. Your drawing is coming along really nicely.`,
            `${childName}, I notice you are still using ${label}. Nice work so far.`,
            `You are still working with ${label}, ${childName}. This part is looking good.`
          ]
        : [
            `I see that you are still using ${label}. Your drawing is coming along really nicely.`,
            `I notice you are still using ${label}. Nice work so far.`,
            `You are still working with ${label}. This part is looking good.`,
            `That ${label} is helping the picture come together. Good job.`,
            `I can see more ${label} now. It is looking good so far.`
          ];

      const repeatIdeaOptions = includeName
        ? [
            `I see that you are still using ${label}, ${childName}. It can keep working well for ${idea}.`,
            `${childName}, you are using more ${label}. That can still help with ${idea}.`
          ]
        : [
            `I see that you are still using ${label}. It can keep working well for ${idea}.`,
            `You are using more ${label}. That can still help with ${idea}.`
          ];

      return pickLine(shouldMentionIdeaAgain ? repeatIdeaOptions : repeatOptions);
    }

    const baseOptions = includeName
      ? [
          `I can see that you selected ${label}, ${childName}. That's a great choice for ${idea}.`,
          `${childName}, I notice that you are using ${label} now. That's a great choice for ${idea}.`,
          `I see that you are using ${label} now, ${childName}. That can work well for ${idea}.`
        ]
      : [
          `I can see that you selected ${label}. That's a great choice for ${idea}.`,
          `I notice that you are using ${label} now. That's a great choice for ${idea}.`,
          `I see that you are using ${label} now. That can work well for ${idea}.`
        ];

    return addTeacherPraiseToColorLine(pickLine(baseOptions));
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

  function maybeReactToColorChange(color) {
    if (state.colorCommentsThisStage >= 4) return;
    if (Date.now() - state.stageStartedAt < 900) return;

    const stageId = currentStage().id;
    const sceneId = currentScene().id;

    if (colorReactionTimer) {
      clearTimeout(colorReactionTimer);
      colorReactionTimer = null;
    }

    colorReactionTimer = setTimeout(function () {
      colorReactionTimer = null;

      if (currentColor !== color) return;
      if (currentStage().id !== stageId || currentScene().id !== sceneId) return;
      if (state.stageAdvanceLocked || state.gameCompleted) return;
      if (state.isSpeaking || state.isListening || state.waitingForResponse) {
        maybeReactToColorChange(color);
        return;
      }
      if (Date.now() - state.lastColorCommentAt < 3600) return;

      state.colorCommentsThisStage += 1;
      state.lastColorCommentAt = Date.now();
      state.lastGuidanceAt = Date.now();

      queueSpeak(TEACHER_ACTOR, function () {
        return buildTeacherColorComment(currentColor);
      }, {
        shouldStart: function () {
          return currentStage().id === stageId
            && currentScene().id === sceneId
            && !state.stageAdvanceLocked
            && !state.gameCompleted
            && Boolean(currentColor);
        },
        shouldPlay: function () {
          return currentStage().id === stageId
            && currentScene().id === sceneId
            && !state.stageAdvanceLocked
            && !state.gameCompleted;
        }
      });
    }, 700);
  }

  function maybeReactToDrawingStart() {
    if (state.drawingCommentsThisStage > 0) return;
    if (!canCharacterChimeIn(3600)) return;
    if (!currentColor) return;

    const stageId = currentStage().id;
    const sceneId = currentScene().id;

    state.drawingCommentsThisStage += 1;
    state.lastColorCommentAt = Date.now();
    state.lastGuidanceAt = Date.now();

    queueSpeak(TEACHER_ACTOR, function () {
      return buildTeacherColorComment(currentColor);
    }, {
      shouldStart: function () {
        return currentStage().id === stageId
          && currentScene().id === sceneId
          && !state.stageAdvanceLocked
          && !state.gameCompleted
          && Boolean(currentColor);
      },
      shouldPlay: function () {
        return currentStage().id === stageId
          && currentScene().id === sceneId
          && !state.stageAdvanceLocked
          && !state.gameCompleted;
      }
    });
  }

  function pickStarSideQuestion() {
    const scene = currentScene();

    const questionsByScene = {
      flower_scene: [
        "What do you like seeing outside?",
        "What would you bring to a picnic?",
        "What kinds of flowers have you seen before?",
        "What would you put in a park?"
      ],
      house_scene: [
        "What could someone do outside on a sunny day?",
        "What would you put in a backyard?",
        "What makes a house feel cozy?",
        "What could be near a house outside?"
      ],
      tree_scene: [
        "What animals might visit a tree?",
        "What would you do under a big tree?",
        "What do you like seeing at a park?",
        "What could grow near a tree?"
      ],
      school_scene: [
        "What might kids do outside before school starts?",
        "What would make a school yard fun?",
        "What do you like seeing outside at school?",
        "What could children play outside?"
      ]
    };

    return pickLine(questionsByScene[scene.id] || [
      "What do you like about this kind of place?",
      "What would you add outside?",
      "What could happen in this scene?"
    ]);
  }

  function maybeAskStarSideQuestion() {
    if (!hasDrawnThisStage) return;
    if (strokeCountThisStage < 28) return;
    if (state.sideQuestionSceneIndex === state.sceneIndex) return;
    if (!canCharacterChimeIn(9500)) return;
    if (state.stageAdvanceLocked || state.gameCompleted) return;

    state.sideQuestionSceneIndex = state.sceneIndex;
    state.lastGuidanceAt = Date.now();

    queueSpeak("star", pickStarSideQuestion(), {
      expectsResponse: true,
      askType: "easy_topic",
      source: "star-side-question",
      intent: "side_question",
      responseSeconds: 5.0
    });
  }

  function maybeReactDuringDrawing() {
    if (strokeCountThisStage < 18) return;
    if (state.drawingCommentsThisStage >= 2) return;
    if (!canCharacterChimeIn(10500)) return;
    if (!drawingHasBase()) return;
    if (!currentColor) return;

    state.drawingCommentsThisStage += 1;
    maybeReactToColorChange(currentColor);
  }

  async function giveStageGuidance(stage, mode) {
    await queueSpeak("star", pickLine(stage.starLead));
    await sleep(120);

    await queueSpeak("star", pickLine([
      "Use any colors you want. Tell me when this part feels ready.",
      "You can draw it your way. Tell me whenever this part feels ready.",
      "Take your time. Just tell me when this part feels ready."
    ]));

    await maybeTeacherSupportStarGuidance();
  }

  async function beginStage(options = {}) {
    const scene = currentScene();
    const stage = currentStage();
    const mode = getProgressMode();

    updateRoundDisplay();
    setPrompt(stage);
    setPalette(stage.palette);
    resetStageConversationState();

    if (options.clearCanvas) {
      clearCanvas();
    }

    updateQuietStatus("");

    if (state.stageIndex === 0) {
      await queueSpeak("star", scene.newSceneLine);
      await sleep(180);
    }

    await giveStageGuidance(stage, mode);

    scheduleStageCheck(15000);
    schedulePassiveDoneListen(800);
  }

  function clearStageCheckTimer() {
    if (stageCheckTimer) {
      clearTimeout(stageCheckTimer);
      stageCheckTimer = null;
    }
  }

  function clearPassiveDoneTimer() {
    stopContinuousPassiveDoneListen({ discard: true });
  }

  function schedulePassiveDoneListen(delayMs = 1800) {
    if (state.gameCompleted || state.stageAdvanceLocked) return;
    startContinuousPassiveDoneListen(delayMs);
  }

  async function startPassiveDoneListen() {
    startContinuousPassiveDoneListen(0);
  }

  function getPassiveSpeechRecognitionConstructor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function supportsPassiveSpeechRecognition() {
    return Boolean(getPassiveSpeechRecognitionConstructor());
  }

  function stopPassiveSpeechRecognition(options = {}) {
    const manual = options.manual !== false;

    if (passiveSpeechRestartTimer) {
      clearTimeout(passiveSpeechRestartTimer);
      passiveSpeechRestartTimer = null;
    }

    passiveSpeechManuallyStopped = manual;

    if (passiveSpeechRecognition) {
      const recognition = passiveSpeechRecognition;
      passiveSpeechRecognition = null;

      try {
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.onend = null;
        recognition.stop();
      } catch (error) {}
    }

    updateMicIndicator();
  }

  function startPassiveSpeechRecognition(delayMs = 0) {
    if (!supportsPassiveSpeechRecognition()) return false;

    passiveDoneEnabled = true;
    updateMicIndicator();

    if (passiveSpeechRecognition || passiveSpeechRestartTimer) {
      return true;
    }

    passiveSpeechManuallyStopped = false;

    passiveSpeechRestartTimer = setTimeout(function () {
      passiveSpeechRestartTimer = null;

      if (!passiveDoneEnabled || state.gameCompleted || state.stageAdvanceLocked) {
        updateMicIndicator();
        return;
      }

      if (state.isListening || state.waitingForResponse || isExplicitRecorderActive()) {
        startPassiveSpeechRecognition(350);
        return;
      }

      const Recognition = getPassiveSpeechRecognitionConstructor();
      if (!Recognition) {
        startPassiveDoneRecorderChunk();
        return;
      }

      let recognition;

      try {
        recognition = new Recognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";
      } catch (error) {
        startPassiveDoneRecorderChunk();
        return;
      }

      passiveSpeechRecognition = recognition;

      recognition.onresult = function (event) {
        if (!passiveDoneEnabled || state.gameCompleted || state.stageAdvanceLocked) return;

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const transcript = cleanTranscript(result[0]?.transcript || "");

          if (!transcript) continue;

          const now = Date.now();
          const lower = transcript.toLowerCase();

          // Debounce repeated interim transcripts from the browser engine.
          if (lower === passiveLastDetectedText && now - passiveLastDetectedAt < 900) {
            continue;
          }

          passiveLastDetectedText = lower;
          passiveLastDetectedAt = now;

          if (transcriptHasPassiveDoneIntent(transcript)) {
            stopPassiveSpeechRecognition({ manual: true });
            handleDoneIntentFromSpeech();
            return;
          }
        }
      };

      recognition.onerror = function () {
        if (!passiveDoneEnabled || passiveSpeechManuallyStopped) return;

        passiveSpeechRecognition = null;
        startPassiveSpeechRecognition(600);
      };

      recognition.onend = function () {
        passiveSpeechRecognition = null;
        updateMicIndicator();

        if (passiveDoneEnabled && !passiveSpeechManuallyStopped && !state.gameCompleted && !state.stageAdvanceLocked) {
          startPassiveSpeechRecognition(250);
        }
      };

      try {
        recognition.start();
        updateMicIndicator();
      } catch (error) {
        passiveSpeechRecognition = null;
        startPassiveSpeechRecognition(600);
      }
    }, Math.max(0, delayMs));

    return true;
  }

  function startContinuousPassiveDoneListen(delayMs = 0) {
    if (state.gameCompleted || state.stageAdvanceLocked) return;

    passiveDoneEnabled = true;
    updateMicIndicator();

    if (startPassiveSpeechRecognition(delayMs)) {
      return;
    }

    if (passiveRestartTimer) {
      clearTimeout(passiveRestartTimer);
      passiveRestartTimer = null;
    }

    passiveRestartTimer = setTimeout(function () {
      passiveRestartTimer = null;
      startPassiveDoneRecorderChunk();
    }, Math.max(0, delayMs));
  }

  function pausePassiveDoneListenForResponse() {
    stopPassiveSpeechRecognition({ manual: true });

    if (passiveRestartTimer) {
      clearTimeout(passiveRestartTimer);
      passiveRestartTimer = null;
    }

    if (passiveRecordingTimer) {
      clearTimeout(passiveRecordingTimer);
      passiveRecordingTimer = null;
    }

    if (passiveMediaRecorder && passiveMediaRecorder.state !== "inactive") {
      passiveIgnoreNextStop = true;
      try {
        passiveMediaRecorder.stop();
      } catch (error) {}
    }

    passiveMediaRecorder = null;
    passiveRecordingChunks = [];
    updateMicIndicator();
  }

  function stopContinuousPassiveDoneListen(options = {}) {
    const discard = options.discard !== false;

    passiveDoneEnabled = false;
    stopPassiveSpeechRecognition({ manual: true });

    if (passiveDoneTimer) {
      clearTimeout(passiveDoneTimer);
      passiveDoneTimer = null;
    }

    if (passiveRestartTimer) {
      clearTimeout(passiveRestartTimer);
      passiveRestartTimer = null;
    }

    if (passiveRecordingTimer) {
      clearTimeout(passiveRecordingTimer);
      passiveRecordingTimer = null;
    }

    if (passiveMediaRecorder && passiveMediaRecorder.state !== "inactive") {
      passiveIgnoreNextStop = discard;
      try {
        passiveMediaRecorder.stop();
      } catch (error) {}
    }

    passiveMediaRecorder = null;
    passiveRecordingChunks = [];
    updateMicIndicator();
  }

  async function startPassiveDoneRecorderChunk() {
    if (!passiveDoneEnabled || state.gameCompleted || state.stageAdvanceLocked) {
      updateMicIndicator();
      return;
    }

    if (isExplicitRecorderActive() || state.isListening || state.waitingForResponse || passiveTranscribing) {
      startContinuousPassiveDoneListen(300);
      return;
    }

    const stream = await ensureMicPermission();

    if (!stream) {
      passiveDoneEnabled = false;
      updateMicIndicator();
      return;
    }

    const stageId = currentStage().id;
    const sceneId = currentScene().id;

    passiveRecordingChunks = [];
    passiveIgnoreNextStop = false;

    try {
      const mimeType = getSupportedMimeType();

      passiveMediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
    } catch (error) {
      passiveMediaRecorder = new MediaRecorder(stream);
    }

    passiveMediaRecorder.addEventListener("dataavailable", function (event) {
      if (event.data && event.data.size > 0) {
        passiveRecordingChunks.push(event.data);
      }
    });

    passiveMediaRecorder.addEventListener("stop", function () {
      handlePassiveDoneRecordingStop(stageId, sceneId);
    }, { once: true });

    try {
      passiveMediaRecorder.start();
      updateMicIndicator();
    } catch (error) {
      passiveMediaRecorder = null;
      startContinuousPassiveDoneListen(700);
      return;
    }

    passiveRecordingTimer = setTimeout(function () {
      passiveRecordingTimer = null;

      if (passiveMediaRecorder && passiveMediaRecorder.state !== "inactive") {
        passiveIgnoreNextStop = false;
        try {
          passiveMediaRecorder.stop();
        } catch (error) {
          startContinuousPassiveDoneListen(250);
        }
      }
    }, PASSIVE_DONE_CHUNK_MS);
  }

  async function handlePassiveDoneRecordingStop(stageId, sceneId) {
    if (passiveRecordingTimer) {
      clearTimeout(passiveRecordingTimer);
      passiveRecordingTimer = null;
    }

    const chunks = passiveRecordingChunks.slice();
    passiveRecordingChunks = [];
    passiveMediaRecorder = null;

    if (passiveIgnoreNextStop) {
      passiveIgnoreNextStop = false;
      updateMicIndicator();
      return;
    }

    if (!passiveDoneEnabled || state.gameCompleted || state.stageAdvanceLocked) return;

    if (!chunks.length) {
      startContinuousPassiveDoneListen(250);
      return;
    }

    if (currentStage().id !== stageId || currentScene().id !== sceneId) {
      startContinuousPassiveDoneListen(250);
      return;
    }

    if (state.pendingDoneConfirmation) {
      startContinuousPassiveDoneListen(500);
      return;
    }

    const blob = new Blob(chunks, {
      type: chunks[0]?.type || "audio/webm"
    });

    passiveTranscribing = true;

    try {
      const formData = new FormData();
      formData.append("audio", blob, "drawing-passive-done.webm");

      const response = await fetch("/api/drawing-game/transcribe", {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      if (data.success) {
        const transcript = cleanTranscript(data.text || "");

        if (transcript && transcriptHasPassiveDoneIntent(transcript)) {
          await handleDoneIntentFromSpeech();
          return;
        }
      }
    } catch (error) {
      console.warn("Passive drawing listener error:", error);
    } finally {
      passiveTranscribing = false;
      updateMicIndicator();
    }

    if (passiveDoneEnabled && !state.stageAdvanceLocked && !state.pendingDoneConfirmation && !state.gameCompleted) {
      startContinuousPassiveDoneListen(150);
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

  async function maybeTeacherSupportStarGuidance() {
    if (state.teacherSupportForStarCount >= 5) return;
    if (Math.random() > 0.35) return;

    state.teacherSupportForStarCount += 1;
    await sleep(120);
    await queueSpeak(TEACHER_ACTOR, pickLine([
      "That's a great point, Star.",
      "Good reminder, Star.",
      "I like that idea, Star.",
      "That makes sense, Star."
    ]));
  }

  async function giveDoneReminder() {
    if (state.gameCompleted || state.stageAdvanceLocked || state.pendingDoneConfirmation) return;

    state.doneRemindersThisStage += 1;
    state.lastGuidanceAt = Date.now();

    const partName = friendlyStageNameForSpeech();
    const sceneName = friendlySceneNameForSpeech();
    let reminder;

    if (isLastStageInCurrentScene() && !isLastSceneInGame()) {
      reminder = pickLine([
        `Let me know whenever this ${sceneName} feels ready, and we can decide whether to draw the ${nextSceneNameForSpeech()} next.`,
        `Whenever this ${sceneName} feels ready, tell me, and we can choose what to do next.`
      ]);
    } else if (isLastStageInCurrentScene() && isLastSceneInGame()) {
      reminder = pickLine([
        `Let me know whenever this ${sceneName} feels ready, and we can finish drawing for today.`,
        `Whenever this ${sceneName} feels ready, tell me, and we can wrap up for today.`
      ]);
    } else {
      reminder = pickLine([
        `Let me know whenever the ${partName} feels ready, and we can move on to the ${nextStageNameForSpeech()}.`,
        `Whenever the ${partName} feels ready, tell me, and we can decide about the ${nextStageNameForSpeech()}.`
      ]);
    }

    await queueSpeak("star", reminder);
    await maybeTeacherSupportStarGuidance();

    scheduleStageCheck(15000);
    schedulePassiveDoneListen(800);
  }

  async function maybeAskStageDone() {
    if (state.gameCompleted || state.stageAdvanceLocked || state.pendingDoneConfirmation) return;

    if (!hasDrawnThisStage || strokeCountThisStage < 12) {
      scheduleStageCheck(9000);
      return;
    }

    if (state.isListening || state.waitingForResponse) {
      scheduleStageCheck(5000);
      return;
    }

    if (Date.now() - state.stageStartedAt < 15000) {
      scheduleStageCheck(5000);
      return;
    }

    if (state.isSpeaking) {
      scheduleStageCheck(3500);
      return;
    }

    state.doneChecksThisStage += 1;
    await giveDoneReminder();
  }

  async function advanceStage(options = {}) {
    if (state.stageAdvanceLocked || state.gameCompleted) return;

    state.stageAdvanceLocked = true;
    clearStageCheckTimer();
    clearPassiveDoneTimer();

    const stage = currentStage();

    state.stagesCompleted += 1;
    state.roundsCompleted = Math.max(state.roundsCompleted, getSocialRound());

    if (!options.skipTeacherPraise) {
      await speakNow(TEACHER_ACTOR, pickLine(stage.donePraise));
    }

    const scene = currentScene();
    const isLastStageInScene = state.stageIndex >= scene.stages.length - 1;
    const isLastScene = state.sceneIndex >= drawingScenes.length - 1;

    if (isLastStageInScene) {
      state.scenesCompleted = Math.max(state.scenesCompleted, state.sceneIndex + 1);

      if (!isLastScene) {
        await saveDrawingProgress();
        await sleep(180);

        if (options.skipSceneChoice) {
          await continueToNextScene();
          return;
        }

        state.stageAdvanceLocked = false;
        await offerContinueAfterScene();
        return;
      }

      await finishFullActivity();
      return;
    }

    state.stageIndex += 1;
    await saveDrawingProgress();

    setTimeout(function () {
      beginStage({ clearCanvas: false });
    }, 650);
  }

  async function offerContinueAfterScene() {
    if (state.gameCompleted) return;

    await saveDrawingProgress();

    if (drawingHasBase()) {
      await queueSpeak(TEACHER_ACTOR, pickLine([
        "That finished picture looks nice. Good job.",
        "I like how that picture turned out.",
        "That picture is finished now. Nice work."
      ]));
      await sleep(130);
    }

    await queueSpeak("star", pickLine([
      `Do you want to draw another scene now, or be done drawing for today?`,
      `Should we start the ${nextSceneNameForSpeech()} now, or finish drawing for today?`,
      `Do you want to keep going with another picture, or be done drawing for today?`
    ]), {
      expectsResponse: true,
      askType: "choice",
      source: "scene-choice",
      intent: "scene_choice",
      responseSeconds: 8.0
    });
  }

  async function continueToNextScene() {
    state.sceneIndex += 1;
    state.stageIndex = 0;
    restoredCanvasData = false;
    savedCanvasDataToRestore = "";
    await saveDrawingProgress({ canvas_data: "" });

    setTimeout(function () {
      beginStage({ clearCanvas: true });
    }, 700);
  }

  async function finishFullActivity() {
    if (state.finalCompletionStarted || state.gameCompleted) return;

    state.finalCompletionStarted = true;

    await sleep(220);

    await speakNow(TEACHER_ACTOR, pickLine([
      "You made a whole set of pictures today. I loved seeing how each one came together.",
      "You added so many nice details today. Thank you for showing me your drawings.",
      "Your drawings looked thoughtful and creative today. I am glad I got to see them."
    ]));

    await sleep(180);

    await speakNow("star", pickLine([
      "That was great drawing today. We can finish for now.",
      "You finished all the pictures. Nice work today.",
      "We can be done drawing for today. Thanks for making these with us."
    ]));

    await completeAndGoNext();
  }

  async function completeAndGoNext() {
    if (state.gameCompleted) return;

    state.gameCompleted = true;
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
    await queueSpeak("star", "Let's play a drawing game. You can use the colors and drawing tools on the board, and you can tell us when each part feels done.");
    await queueSpeak(TEACHER_ACTOR, "Hi. I'm the Teacher. I'll watch your picture and notice the colors you choose.");
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
      restoreCanvasFromData(savedCanvasDataToRestore).then(function (restored) {
        if (savedCanvasDataToRestore && !restored) {
          state.stageIndex = 0;
          savedCanvasDataToRestore = "";
        }

        beginStage({ clearCanvas: !restored });
      });
    }, 1500);
  }

  async function startGameAfterCall() {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    stopRingtone();
    playCallAcceptedSound();
    ensureMicPermission();
    await loadSavedDrawingProgress();

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
    clearStageCheckTimer();
    clearPassiveDoneTimer();

    if (colorReactionTimer) {
      clearTimeout(colorReactionTimer);
      colorReactionTimer = null;
    }

    if (canvasSaveTimer) {
      clearTimeout(canvasSaveTimer);
      canvasSaveTimer = null;
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

    updateMicIndicator();
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
      askStarConfirmStageDone();
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
      saveDrawingProgress();
      cleanupMedia();
      window.location.href = "/dashboard";
    });
  }

  window.addEventListener("resize", resizeCanvasForDisplay);
  window.addEventListener("beforeunload", function () {
    saveDrawingProgress();
    cleanupMedia();
  });

  resizeCanvasForDisplay();
  setupCanvasStyle();
  updateRoundDisplay();
  setPalette(currentStage().palette);
  if (doneDrawingBtn) doneDrawingBtn.disabled = true;
  closeAllMouths();

  setTimeout(startRingtone, 400);
});
