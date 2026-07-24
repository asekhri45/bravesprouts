document.addEventListener("DOMContentLoaded", function () {
  const matchPage = document.querySelector(".match-page");

  function dlog(...args) {
    const debugEnabled =
      Boolean(window.APP_DEBUG) ||
      new URLSearchParams(window.location.search).get("debug") === "1" ||
      window.localStorage?.getItem("matchCardsDebug") === "1";

    if (debugEnabled) {
      console.log(
        `[match_cards:${matchPage ? matchPage.dataset.activityId : "unknown"}]`,
        ...args
      );
    }
  }

  const cardGrid = document.getElementById("cardGrid");
  const gameArea = document.getElementById("gameArea");
  const childTurnCard = document.getElementById("childTurnCard");
  const parentTurnCard = document.getElementById("parentTurnCard");
  const starBubble = document.getElementById("starBubble");
  const starVideoTile = document.getElementById("starVideoTile");
  const completeModal = document.getElementById("completeModal");
  const restartBtn = document.getElementById("restartBtn");
  const roundNumber = document.getElementById("roundNumber");

  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const zoomStage = document.getElementById("zoomStage");
  const starIntroScreen = document.getElementById("starIntroScreen");
  const micControl = document.getElementById("micControl");

  const activityId = Number(matchPage?.dataset.activityId || 1);
  const childName = (matchPage?.dataset.childName || "there").trim() || "there";

  const cardBack = "/static/images/card-back.png";

  const developerThingy = false;

  const cardItems = [
    { name: "cat", image: "/static/images/card-cat.png" },
    { name: "dog", image: "/static/images/card-dog.png" },
    { name: "bunny", image: "/static/images/card-bunny.png" },
    { name: "fish", image: "/static/images/card-fish.png" },
    { name: "bird", image: "/static/images/card-bird.png" },
    { name: "flower", image: "/static/images/card-flower.png" }
  ];

  const introLines = [
    "Hi there. I'm Star. I'll hang out while you play matching cards today. Let me share my screen.",
    "Hello. I'm Star. I'll stay here while you play matching cards. Let me share my screen.",
    "Hi. I'm Star. I'll keep you company while you play. Let me share my screen.",
    "Hey. I'm Star. I'll be here while you and your grown-up find matches. Let me share my screen."
  ];

  const returningIntroLines = [
  "Okay, I'll keep you company while you guys play the matching game again. Let me share my screen.",
  "Okay, I'm here to keep you company while you two keep playing matching cards. Let me share my screen.",
  "Welcome back. I'll hang out while you guys keep playing the matching game. Let me share my screen.",
  "Okay, let's keep going. I'll be here while you two play matching cards again. Let me share my screen.",
  "Welcome back. I'll keep you company while you guys continue the matching game. Let me share my screen."
];

  const gameInstructionLine =
  "Let’s play Match Cards. Flip two cards each turn. If they match, they stay open. If not, they flip back over. Try to remember where each picture is, then find all the pairs.";

  let firstCard = null;
  let secondCard = null;
  let lockBoard = true;
  let matchesFound = 0;
  let currentTurn = "child";
  let roundInProgress = false;
  let nextRoundStarting = false;

  let mediaStream = null;
  let recordingTimeout = null;

  let responseAudioContext = null;
  let responseAnalyser = null;
  let responseMicSource = null;
  let responseMonitorFrame = null;
  let heardSpeechInWindow = false;
  let lastSpeechTime = 0;

  let starState = freshStarState();

  const diagnostics = window.GameDiagnostics
    ? window.GameDiagnostics.createSession({
        game: "match_cards",
        activityId: activityId,
        getState: function () {
          return {
            roundNumber: starState.roundNumber,
            currentTurn: currentTurn,
            roundInProgress: roundInProgress,
            isListening: starState.isListening,
            isStarSpeaking: starState.isStarSpeaking,
            waitingForResponse: starState.waitingForResponse,
            micReady: starState.micReady,
            micDenied: starState.micDenied
          };
        }
      })
    : null;

  const audioManager = window.GameAudioManager
    ? window.GameAudioManager.create({ diagnostics: diagnostics })
    : null;

  const micManager = window.GameMicManager
    ? window.GameMicManager.create({ diagnostics: diagnostics })
    : null;

  const turnGuard = window.GameTurnGuard
    ? window.GameTurnGuard.create({ diagnostics: diagnostics })
    : null;

  function diagLog(eventName, details) {
    if (diagnostics) diagnostics.log(eventName, details);
  }

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.45;

  let ringtoneStarted = false;

  function freshStarState() {
    return {
      sessionStart: Date.now(),
      currentStage: 0,
      comfortScore: 0,

      roundNumber: 1,
      roundsCompleted: 0,
      questionsThisRound: 0,

      cardFlips: 0,
      childFlips: 0,
      parentFlips: 0,
      childMatches: 0,
      parentMatches: 0,
      turnsTaken: 0,

      spokenResponses: 0,
      spokenWords: 0,
      silentWindows: 0,
      longestResponseWords: 0,

      directChildQuestionsAsked: 0,
      directChildQuestionSilences: 0,
      wonderPromptsAsked: 0,
      helpPromptsAsked: 0,
      clearPromptsAsked: 0,
      concreteChildResponses: 0,
      childChoiceResponses: 0,
      childOpinionResponses: 0,
      clearChildResponses: 0,
      directQuestionBackoffUntilRound: 0,
      nextChildPromptOverride: null,
      lastSavedRoundsCompleted: -1,
      isEnding: false,
      lastDirectChildQuestionRound: 0,
      lastPlayAgainQuestionRound: 0,

      isStarSpeaking: false,
      isListening: false,
      waitingForResponse: false,
      questionAskedAt: null,
      questionCooldownUntil: 0,
      currentQuestion: null,

      recentStarMessages: [],
      recentLineKeys: [],
      recentPraiseOpeners: [],

      starQuestionsAsked: 0,
      micReady: false,
      micDenied: false,

      gameCompleted: false,
      playAgainStartedByVoice: false,
      playAgainSilenceHandled: false
    };
  }

  async function loadSavedMatchingProgress() {
    try {
      const response = await fetch(`/api/matching-game/state?activity_id=${activityId}`);

      if (!response.ok) {
        return;
      }

      const data = await response.json();

      if (!data.success || !data.state) {
        return;
      }

      const saved = data.state;
      const savedRounds = Math.max(0, Number(saved.rounds_completed || 0));

      starState.roundsCompleted = savedRounds;
      starState.roundNumber = savedRounds + 1;

      starState.spokenResponses = Math.max(starState.spokenResponses, Number(saved.spoken_responses || 0));
      starState.silentWindows = Math.max(starState.silentWindows, Number(saved.silent_windows || 0));
      starState.wonderPromptsAsked = Math.max(starState.wonderPromptsAsked, Number(saved.wonder_prompts_asked || 0));
      starState.helpPromptsAsked = Math.max(starState.helpPromptsAsked, Number(saved.help_prompts_asked || 0));
      starState.clearPromptsAsked = Math.max(starState.clearPromptsAsked, Number(saved.clear_prompts_asked || 0));
      starState.childChoiceResponses = Math.max(starState.childChoiceResponses, Number(saved.child_choice_responses || 0));
      starState.childOpinionResponses = Math.max(starState.childOpinionResponses, Number(saved.child_opinion_responses || 0));
      starState.clearChildResponses = Math.max(starState.clearChildResponses, Number(saved.clear_child_responses || 0));
      starState.directChildQuestionSilences = Math.max(
        starState.directChildQuestionSilences,
        Number(saved.direct_child_question_silences || 0)
      );

      updateStage();
      updateRoundDisplay();
    } catch (error) {
      console.warn("Could not load saved matching progress:", error);
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

    return callAcceptedSound.play().catch(function (error) {
      console.log("Could not play call accepted sound:", error);
    });
  }

  function shuffle(array) {
    const copy = [...array];

    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }

    return copy;
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function getMinutesPlayed() {
    return Math.max(0, (Date.now() - starState.sessionStart) / 60000);
  }

  function updateStage() {
    const minutes = getMinutesPlayed();
    let nextStage = 0;

    /*
      Stage 0: Rounds 1-3. Star comments only.
      Stage 1: Rounds 4-6. Soft I-wonder child prompts.
      Stage 2: Rounds 7-9. Help-me-look child prompts.
      Stage 3: Rounds 10-12. Clear child questions.
      Stage 4: Round 13+. Continued clear questions / stronger conversation.
    */

    if (starState.roundNumber >= 4 || minutes >= 8) {
      nextStage = 1;
    }

    if (starState.roundNumber >= 7 || minutes >= 14) {
      nextStage = 2;
    }

    if (starState.roundNumber >= 10 || minutes >= 20) {
      nextStage = 3;
    }

    if (starState.roundNumber >= 13 || starState.clearChildResponses >= 2) {
      nextStage = 4;
    }

    starState.currentStage = Math.min(4, nextStage);
    return starState.currentStage;
  }

  function getStarStage() {
    return updateStage();
  }

  function addComfort(points) {
    starState.comfortScore += points;
    updateStage();
  }

  function updateComfortFromEvent(eventType) {
    if (eventType === "pair_attempt") addComfort(0.45);
    if (eventType === "match_found") addComfort(1.6);
    if (eventType === "game_complete") addComfort(2.3);
  }

  function updateRoundDisplay() {
    if (roundNumber) {
      roundNumber.textContent = String(starState.roundNumber);
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function updateStarMessage(title, message) {
    if (!starBubble) return;

    starBubble.innerHTML = `
      <h2>${escapeHtml(title)}</h2>
      <p>${escapeHtml(message)}</p>
    `;
  }

  function rememberStarMessage(message) {
    if (!message) return;

    starState.recentStarMessages.push(message);

    if (starState.recentStarMessages.length > 18) {
      starState.recentStarMessages.shift();
    }
  }

  function cardLabel(name) {
    const labels = {
      cat: "cat",
      dog: "dog",
      bunny: "bunny",
      fish: "fish",
      bird: "bird",
      flower: "flower"
    };

    return labels[name] || "card";
  }

  function cardPlural(name) {
    const labels = {
      cat: "cats",
      dog: "dogs",
      bunny: "bunnies",
      fish: "fish",
      bird: "birds",
      flower: "flowers"
    };

    return labels[name] || "cards";
  }

  /*
    Card categories, and the follow-up questions Star asks about the two cards
    that were just turned over (rounds 7-12).

    The deck mixes animals with a flower, so a template is only offered when it
    actually makes sense for both revealed cards. Without that check Star ended
    up asking which of a dog and a flower you would rather keep as a pet, or
    which of two animals smells nicer. Every template is a short, concrete
    this-or-that a five-year-old can answer by naming one of the two pictures
    in front of them -- never yes/no, and never a chore-shaped question like
    "which would you rather take care of?".
  */
  const CARD_CATEGORIES = {
    cat: "animal",
    dog: "animal",
    bunny: "animal",
    fish: "animal",
    bird: "animal",
    flower: "plant"
  };

  function cardCategory(name) {
    return CARD_CATEGORIES[name] || "thing";
  }

  // Work for any two cards, including a mixed animal/plant pair.
  const ANY_PAIR_QUESTIONS = [
    "Which one would you rather draw, the {first} or the {second}?",
    "Which one has prettier colors, the {first} or the {second}?",
    "Which one would you rather put on a sticker, the {first} or the {second}?",
    "Which one would you rather take a picture of, the {first} or the {second}?",
    "Which one would you rather see in a story, the {first} or the {second}?",
    "Which one would make you smile more, the {first} or the {second}?",
    "Which one would you rather show to a friend, the {first} or the {second}?",
    "Which one would you rather see outside, the {first} or the {second}?",
    "Which one would you pick for a birthday card, the {first} or the {second}?",
    "Which one would you rather learn something fun about, the {first} or the {second}?"
  ];

  const BOTH_ANIMAL_QUESTIONS = [
    "Which one would you rather have as a pet, the {first} or the {second}?",
    "Which one would be more fun to play with, the {first} or the {second}?",
    "Which one would you rather see at a zoo, the {first} or the {second}?",
    "Which one do you think would move faster, the {first} or the {second}?",
    "Which one would you rather watch for a whole day, the {first} or the {second}?"
  ];

  const BOTH_PLANT_QUESTIONS = [
    "Which one would you rather grow in a garden, the {first} or the {second}?",
    "Which one would you give to someone, the {first} or the {second}?",
    "Which one do you think would smell nicer, the {first} or the {second}?",
    "Which one would you rather see in a bouquet, the {first} or the {second}?"
  ];

  function getTwoCardChoiceQuestions(firstName, secondName) {
    const questions = ANY_PAIR_QUESTIONS.slice();
    const firstCategory = cardCategory(firstName);
    const secondCategory = cardCategory(secondName);

    if (firstCategory === "animal" && secondCategory === "animal") {
      return questions.concat(BOTH_ANIMAL_QUESTIONS);
    }

    if (firstCategory === "plant" && secondCategory === "plant") {
      return questions.concat(BOTH_PLANT_QUESTIONS);
    }

    // Mixed categories: only the neutral preference questions apply.
    return questions;
  }

  /*
    Both revealed cards show the same picture, so there is no second card to
    compare against. These stay this-or-that by offering two concrete things
    you could do with that one card.
  */
  const MATCHED_CARD_CHOICE_QUESTIONS = {
    cat: [
      "Would you rather pet the cat, or watch it chase a wiggly string?",
      "Which would be more fun with the cat, playing with it, or having it curl up next to you?"
    ],
    dog: [
      "Would you rather play fetch with the dog, or take it for a walk?",
      "Which would be more fun with the dog, running around, or giving it a big hug?"
    ],
    bunny: [
      "Would you rather feed the bunny a carrot, or watch it hop around?",
      "Which would be more fun with the bunny, holding it, or watching it jump?"
    ],
    fish: [
      "Would you rather watch the fish swim, or feed it?",
      "Which would be more fun, one fish, or a whole tank of them?"
    ],
    bird: [
      "Would you rather listen to the bird sing, or watch it fly?",
      "Which would be more fun with the bird, teaching it a song, or watching it flap its wings?"
    ],
    flower: [
      "Would you rather smell the flower, or pick one for somebody?",
      "Which would be nicer, a whole garden of flowers, or one flower in a vase?"
    ]
  };

  /*
    The single entry point for the rounds 7-12 follow-up question. Rounds 10-12
    used to ask "which card should I remember?" -- a memory chore rather than
    something a child enjoys answering -- and rounds 7-9 asked about colours
    Star could already see. Both now come from here.
  */
  function getRevealedCardQuestion(context) {
    const firstName = context.firstCard;
    const secondName = context.secondCard;
    const isPair = Boolean(context.cardName) || firstName === secondName;

    if (isPair) {
      const matchedName = context.cardName || firstName;
      const options = MATCHED_CARD_CHOICE_QUESTIONS[matchedName];
      if (options) {
        return pickCalmLine("pair_choice_" + matchedName, options, context);
      }
      return null;
    }

    if (firstName && secondName) {
      return pickCalmLine(
        "two_card_choice_" + firstName + "_" + secondName,
        getTwoCardChoiceQuestions(firstName, secondName),
        context
      );
    }

    return null;
  }

  /*
    Star's own opinion about the card the child picked. One short sentence,
    specific to that card, and only stating things that are actually true of
    it -- no invented facts. Used occasionally (see handleSpeechHeard) so the
    agreement feels like a reaction rather than a formula.
  */
  const CARD_AGREEMENT_LINES = {
    cat: [
      "Me too. Cats can be so cute.",
      "I like the cat too. It looks so soft.",
      "Good choice. I think the cat is fun to watch."
    ],
    dog: [
      "Me too. I think the dog would be fun to draw.",
      "I like the dog too. It looks so friendly.",
      "Good choice. Dogs are so playful."
    ],
    bunny: [
      "Me too. I love how bunnies hop.",
      "I like the bunny too. Those ears are great.",
      "Good choice. The bunny looks so soft."
    ],
    fish: [
      "Me too. I like watching fish swim.",
      "I like the fish too. It looks so shiny.",
      "Good choice. The fish has such pretty colors."
    ],
    bird: [
      "Me too. I like how birds sing.",
      "I like the bird too. Those wings are amazing.",
      "Good choice. The bird looks so bright."
    ],
    flower: [
      "I like that one too. It looks so bright.",
      "Me too. Flowers make me happy.",
      "Good choice. That flower has lovely colors."
    ]
  };

  function getCardAgreementLine(cardName) {
    const options = CARD_AGREEMENT_LINES[cardName];
    if (!options) return null;
    return pickCalmLine("card_agreement_" + cardName, options, {});
  }

  function remainingPairsText(count) {
    if (count === 1) return "1 pair left";
    return `${count} pairs left`;
  }

  function isAnimalCard(name) {
    return ["cat", "dog", "bunny", "fish", "bird"].includes(name);
  }

  function fillLine(template, context = {}) {
    return template
      .replaceAll("{child}", childName)
      .replaceAll("{card}", cardLabel(context.cardName))
      .replaceAll("{cards}", cardPlural(context.cardName))
      .replaceAll("{first}", cardLabel(context.firstCard))
      .replaceAll("{second}", cardLabel(context.secondCard))
      .replaceAll("{left}", context.leftText || "")
      .replaceAll("{color}", context.color || "")
      .replaceAll("{spoken}", context.spoken || "");
  }

  function pickCalmLine(key, options, context = {}) {
    const recentMessages = new Set(starState.recentStarMessages);
    const recentKeys = new Set(starState.recentLineKeys);

    let filled = options.map(option => fillLine(option, context));
    let fresh = filled.filter(line => !recentMessages.has(line));

    if (!fresh.length) {
      fresh = filled;
    }

    let chosen = fresh[Math.floor(Math.random() * fresh.length)];

    if (recentKeys.has(key) && fresh.length > 1) {
      const alternative = fresh.find(line => line !== chosen);
      if (alternative) chosen = alternative;
    }

    starState.recentLineKeys.push(key);

    if (starState.recentLineKeys.length > 6) {
      starState.recentLineKeys.shift();
    }

    return chosen;
  }

  function pickPraiseOpener() {
    const allOpeners = [
      "",
      "",
      "",
      "Wow, ",
      "Nice, ",
      "Awesome, ",
      "Amazing, ",
      "There it is, ",
      "Look at that, ",
      "Good eye, "
    ];

    let fresh = allOpeners.filter(opener => !starState.recentPraiseOpeners.includes(opener));

    if (!fresh.length) {
      fresh = allOpeners;
    }

    const chosen = fresh[Math.floor(Math.random() * fresh.length)];

    starState.recentPraiseOpeners.push(chosen);

    if (starState.recentPraiseOpeners.length > 4) {
      starState.recentPraiseOpeners.shift();
    }

    return chosen;
  }

  function childSkillPraiseLine(context = {}) {
    return pickCalmLine("child_skill_praise", [
      "You're really good at finding these, {child}. You found the {card} pair.",
      "You're awesome at this, {child}. You found the {card} pair.",
      "You're great at this game, {child}. Those are both {cards}.",
      "You are really good at remembering the cards, {child}. You found the {card} pair.",
      "You found that fast, {child}. The {card} cards match."
    ], context);
  }

  function getChildMatchLines(remainingPairs) {
    if (remainingPairs > 0 && remainingPairs <= 2) {
      return [
        "{opener}{child}, you found the {card} pair. Only {left}.",
        "{opener}you matched the two {card} cards, {child}. Only {left}.",
        "{opener}you found the {card} pair, {child}. Only {left}.",
        "{opener}those are both {cards}, {child}. Only {left}.",
        "{opener}the {card} cards match, {child}. Only {left}.",
        "{opener}you found both {card} cards. Only {left}."
      ];
    }

    return [
      "{opener}{child}, you found the {card} pair.",
      "{opener}you matched the two {card} cards, {child}.",
      "{opener}you found the {card} pair, {child}.",
      "{opener}those are both {cards}, {child}.",
      "{opener}the {card} cards match, {child}.",
      "{opener}you found both {card} cards.",
      "{opener}there are the two {card} cards.",
      "{opener}the pair is {cards}.",
      "{opener}you got the {card} pair.",
      "{opener}that is a match. Two {cards}."
    ];
  }

  function getParentMatchLines(remainingPairs) {
    if (remainingPairs > 0 && remainingPairs <= 2) {
      return [
        "{opener}you two found the {card} pair. Only {left}.",
        "{opener}the {card} cards match. Only {left}.",
        "{opener}you found the {card} pair together. Only {left}.",
        "{opener}those are both {cards}. Only {left}.",
        "{opener}good teamwork. The {card} cards match. Only {left}.",
        "{opener}you two are almost finished. Only {left}."
      ];
    }

    return [
      "{opener}you two found the {card} pair.",
      "{opener}the {card} cards match.",
      "{opener}you found the {card} pair together.",
      "{opener}those are both {cards}.",
      "{opener}good teamwork. The {card} cards match.",
      "{opener}you two got the {card} pair.",
      "{opener}there are the two {card} cards.",
      "{opener}the pair is {cards}.",
      "{opener}that is a match. Two {cards}.",
      "{opener}you two make a good team. The {card} cards match."
    ];
  }

  function getMatchLine(context) {
    const remainingPairs = Number(context.remainingPairs || 0);
    const opener = pickPraiseOpener();

    const withContext = {
      ...context,
      opener,
      leftText: remainingPairs > 0 ? remainingPairsText(remainingPairs) : ""
    };

    // Occasionally give the child a stronger skill-based compliment, but not every time.
    if (
      context.player === "child" &&
      starState.roundNumber >= 2 &&
      Math.random() < 0.16
    ) {
      return childSkillPraiseLine(withContext);
    }

    if (context.player === "child") {
      return pickCalmLine("child_match_clear", getChildMatchLines(remainingPairs), withContext)
        .replaceAll("{opener}", opener);
    }

    return pickCalmLine("parent_match_clear", getParentMatchLines(remainingPairs), withContext)
      .replaceAll("{opener}", opener);
  }

  function getNoMatchObservation(context = {}) {
    const stage = getStarStage();

    if (stage < 1) return null;
    if (Math.random() > 0.22) return null;

    return pickCalmLine("no_match_observe", [
      "I wonder where the matching {first} card is.",
      "I wonder where the matching {second} card is.",
      "Those two are different. Let's keep looking.",
      "Not a pair yet. There are more cards to try.",
      "I saw a {first} and a {second}. Let's remember those."
    ], context);
  }

  function getNewRoundLine() {
    const stage = getStarStage();

    if (stage >= 3) {
      return pickCalmLine("new_round_stage3", [
        "New round, {child}. Let's find the matching cards.",
        "The cards are ready again.",
        "Here comes another round.",
        "Let's try one more round.",
        "Another round is ready."
      ]);
    }

    if (stage >= 1) {
      return pickCalmLine("new_round_stage1", [
        "New round. You two are doing great together.",
        "The cards are ready again.",
        "Let's find more pairs.",
        "Here comes another round.",
        "Another round is ready."
      ]);
    }

    return pickCalmLine("new_round_stage0", [
      "Let's play another round.",
      "The cards are ready again.",
      "New round.",
      "Let's find more pairs."
    ]);
  }

  function getAutoNextRoundLine() {
    return pickCalmLine("auto_next_round", [
      "You found all the pairs. Let's play another round.",
      "All the pairs are found. Let's play another round.",
      "You found every pair. Let's play another round.",
      "That round is finished. Let's play another round.",
      "All the pairs are matched. Let's play another round."
    ]);
  }

  function childReadyForDirectQuestion(questionLevel = "wonder") {
    const stage = getStarStage();

    if (stage < 1) return false;

    // I-wonder prompts are soft observations, so they should still happen even without mic access.
    if (starState.micDenied && questionLevel !== "wonder") return false;

    // Rounds 1-3 are intentionally only comments.
    if (starState.roundNumber <= 3) return false;

    // Only one child-directed prompt per round.
    if (starState.lastDirectChildQuestionRound === starState.roundNumber) return false;
    if (starState.questionsThisRound >= 1) return false;

    // After silence, Star skips one round, then tries again.
    if (starState.roundNumber < starState.directQuestionBackoffUntilRound) return false;

    // If the child has been silent multiple times, avoid jumping into the strongest prompts.
    if (
      starState.directChildQuestionSilences >= 2 &&
      questionLevel === "clear" &&
      starState.clearChildResponses === 0
    ) {
      return false;
    }

    return true;
  }

  function childReadyForPlayAgainQuestion() {
    return (
      starState.roundNumber >= 10 &&
      starState.clearChildResponses >= 1 &&
      starState.silentWindows <= starState.spokenResponses + 2
    );
  }

  function shouldAskPlayAgainQuestion() {
    const completed = starState.roundsCompleted;

    if (completed < 2) return false;

    // Ask after every two completed rounds: 2, 4, 6, 8, 10, 12, etc.
    return completed % 2 === 0;
  }

  function getPlayAgainQuestion() {
    if (childReadyForPlayAgainQuestion()) {
      return {
        message: pickCalmLine("play_again_child", [
          "{child}, do you want to play another round, or do you want to finish here for now?",
          "{child}, would you like another round, or should we end here for now?",
          "{child}, do you want one more round, or do you want to finish early?",
          "{child}, should we keep playing, or should we stop here?"
        ]),
        askType: "play_again_child"
      };
    }

    return {
      message: pickCalmLine("play_again_team", [
        "Do you guys want to play another round, or do you want to finish early?",
        "Do you two want another round, or should we finish here for now?",
        "Should we keep playing, or should we end here for now?",
        "For both of you, do you want one more round, or do you want to stop here?",
        "Do you guys want to keep playing, or do you want to finish for now?"
      ]),
      askType: "play_again_team"
    };
  }

  function getChildQuestionLevel() {
    /*
      Round-driven fade-in:
      Rounds 1-3: comments only.
      Rounds 4-6: I-wonder child prompts.
      Rounds 7-9: help-me-look child prompts.
      Rounds 10-12: clear direct child questions.
    */

    if (starState.nextChildPromptOverride) {
      return starState.nextChildPromptOverride;
    }

    if (starState.roundNumber <= 3) {
      return "none";
    }

    if (starState.roundNumber >= 4 && starState.roundNumber <= 6) {
      return "wonder";
    }

    if (starState.roundNumber >= 7 && starState.roundNumber <= 9) {
      return "help";
    }

    if (starState.roundNumber >= 10) {
      return "clear";
    }

    return "none";
  }

  function getWonderPrompt(context = {}) {
    if (context.cardName) {
      return {
        askType: "wonder_observation",
        message: pickCalmLine("wonder_observation_match", [
          "I wonder what color stands out on the {card} card, {child}.",
          "I wonder what color is easiest to see on the {card} card, {child}.",
          "I wonder what part of the {card} card you noticed first, {child}.",
          "I wonder what color you see first on the {card} card, {child}.",
          "I wonder which color is brightest on the {card} card, {child}."
        ], context)
      };
    }

    return {
      askType: "wonder_observation",
      message: pickCalmLine("wonder_observation_no_match", [
        "I wonder which card will be easier to remember, the {first} or the {second}, {child}.",
        "I wonder where the matching {first} card is, {child}.",
        "I wonder where the matching {second} card is, {child}.",
        "I wonder which card we should remember first, the {first} or the {second}, {child}."
      ], context)
    };
  }

  /*
    Rounds 7-9. These used to ask the child to name a colour on a card, or
    which of the two cards had just been turned over -- questions whose answer
    Star can already see, and which pretended Star could not see the board.
    They now ask a simple opinion question about the two cards that were just
    revealed: concrete, never yes-or-no, and always built from the real card
    labels so the question cannot reference a card that is not on screen.
  /*
    Rounds 7-9 and 10-12 both ask a short follow-up about the two cards that
    were just revealed, and both now come from getRevealedCardQuestion(). The
    old versions asked the child to name a colour on a card (rounds 7-9) or
    which card Star should remember (rounds 10-12) -- the first is something
    Star can already see, the second is a memory chore. Returns null when the
    revealed cards do not support a sensible question, and the caller simply
    skips the prompt rather than asking something that does not fit.
  */
  function getHelpPrompt(context = {}) {
    const message = getRevealedCardQuestion(context);
    if (!message) return null;

    return { askType: "help_question", isPreference: true, message: message };
  }

  /*
    Rounds 10-12. These used to ask which card Star should remember or watch
    for next -- a memory chore, and one whose answer Star can already see. They
    now use the same revealed-card preference questions as rounds 7-9, which is
    what the child actually enjoys answering. The askType stays
    "clear_question" so the existing comfort scoring, backoff and progression
    for this band are untouched.
  */
  function getClearQuestion(context = {}) {
    const message = getRevealedCardQuestion(context);
    if (!message) return null;

    return { askType: "clear_question", isPreference: true, message: message };
  }

  function getSimpleChoiceQuestion(context = {}) {
    const first = context.firstCard;
    const second = context.secondCard;

    if (first && second && first !== second) {
      return {
        askType: "choice",
        message: pickCalmLine("simple_choice_from_two", [
          "Which card should I watch for, the {first} or the {second}, {child}?",
          "Which card should we remember, the {first} or the {second}, {child}?",
          "Which card do you want me to look for, the {first} or the {second}, {child}?",
          "Should I watch the {first} card or the {second} card, {child}?"
        ], context)
      };
    }

    return {
      askType: "choice",
      message: pickCalmLine("simple_choice_match", [
        "Should I watch for another {card} card or a different card, {child}?",
        "Should we look for the {card} again or choose a different card, {child}?",
        "Should I remember the {card} card or watch a new card, {child}?"
      ], context)
    };
  }

  function getOpinionQuestion(context = {}) {
    return {
      askType: "opinion_choice",
      message: pickCalmLine("opinion_choice", [
        "Which card do you like more, the {first} or the {second}, {child}?",
        "Which card is more fun, the {first} or the {second}, {child}?",
        "Which animal card do you like better, the {first} or the {second}, {child}?",
        "Which card would you pick first next time, the {first} or the {second}, {child}?"
      ], context)
    };
  }

  function getPreferenceQuestion(eventType, context = {}) {
    if (Date.now() < starState.questionCooldownUntil) return null;
    if (context.player !== "child") return null;

    const level = getChildQuestionLevel();

    if (level === "none") return null;
    if (!childReadyForDirectQuestion(level)) return null;

    // Prompt on the first child pair event of the round. This is intentional,
    // not random, so the child actually moves through the fade-in progression.
    if (level === "wonder") {
      return getWonderPrompt(context);
    }

    if (level === "help") {
      return getHelpPrompt(context);
    }

    if (level === "clear") {
      return getClearQuestion(context);
    }

    return null;
  }

  function registerNonListeningWonderPrompt() {
    starState.wonderPromptsAsked += 1;
    starState.questionsThisRound += 1;
    starState.lastDirectChildQuestionRound = starState.roundNumber;
  }

  function isVerbalAsk(askType) {
    return (
      askType === "help_question" ||
      askType === "clear_question" ||
      askType === "choice" ||
      askType === "opinion_choice" ||
      askType === "one_word" ||
      askType === "play_again_team" ||
      askType === "play_again_child"
    );
  }

  async function speakStarLine(text, options = {}) {
    const expectsResponse = Boolean(options.expectsResponse);
    const askType = options.askType || "none";
    const intent = options.intent || null;

    // A new turn begins whenever Star is about to say something new --
    // this invalidates any recording/listening still in flight from
    // whatever the previous turn was doing, and gives every async step
    // below a token to check itself against.
    const turnToken = turnGuard ? turnGuard.beginNewTurn() : null;

    const calmText = String(text || "")
      .replace(/\booo\b/gi, "")
      .replace(/\boh my\b/gi, "")
      .replace(/\s+/g, " ")
      .trim();

    updateStarMessage("Star", calmText);
    rememberStarMessage(calmText);
    diagLog("prompt_requested", { askType: askType, expectsResponse: expectsResponse });

    let playbackResult = { status: "ended" };

    try {
      starState.isStarSpeaking = true;

      const response = await fetch("/api/matching-game/tts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ text: calmText })
      });

      const data = await response.json();

      if (turnGuard && turnGuard.rejectIfStale(turnToken, "speakStarLine_tts_response")) {
        return;
      }

      diagLog("backend_response_received", { ok: response.ok, success: !!data.success });

      if (data.success && Array.isArray(data.audio_parts) && data.audio_parts.length) {
        playbackResult = await playStarAudioSequence(data.audio_parts, {
          volume: options.volume || 0.86
        });
      } else if (data.success && data.audio_url) {
        playbackResult = await playStarAudio(data.audio_url, {
          volume: options.volume || 0.86
        });
      } else if (data.success && data.audio) {
        playbackResult = await playStarAudio(data.audio, {
          volume: options.volume || 0.86
        });
      } else {
        playbackResult = { status: "error" };
        await sleep(700);
      }

      // One safe automatic retry for a genuinely failed (not cancelled)
      // prompt -- mirrors the Mystery Animal reference behavior. Match
      // Cards has no on-screen replay button, so a prompt that still
      // fails after the retry is simply skipped (see below) rather than
      // ever being treated as successfully spoken.
      if (
        playbackResult.status !== "ended" &&
        playbackResult.status !== "cancelled" &&
        !(turnGuard && turnGuard.isStale(turnToken))
      ) {
        diagLog("recovery_started", { action: "auto_retry", status: playbackResult.status });

        if (Array.isArray(data.audio_parts) && data.audio_parts.length) {
          playbackResult = await playStarAudioSequence(data.audio_parts, { volume: options.volume || 0.86 });
        } else if (data.audio_url || data.audio) {
          playbackResult = await playStarAudio(data.audio_url || data.audio, { volume: options.volume || 0.86 });
        }
      }
    } catch (error) {
      console.error("Star TTS error:", error);
      diagLog("error", { where: "speakStarLine", message: String(error && error.message || error) });
      playbackResult = { status: "error" };
      await sleep(700);
    } finally {
      starState.isStarSpeaking = false;
    }

    if (turnGuard && turnGuard.rejectIfStale(turnToken, "speakStarLine_after_playback")) {
      return;
    }

    if (playbackResult.status !== "ended" && playbackResult.status !== "cancelled") {
      // The line genuinely never played. Never enter a listening window
      // the child was never actually asked to respond to -- skip this
      // one prompt gracefully (gameplay/cards continue normally; only
      // this one flavor line/question is missed) rather than faking a
      // question that was never heard.
      diagLog("prompt_failed", { askType: askType, status: playbackResult.status });
      return;
    }

    diagLog("prompt_ended", { askType: askType });

    if (expectsResponse && isVerbalAsk(askType)) {
      starState.waitingForResponse = true;
      starState.questionAskedAt = Date.now();
      starState.currentQuestion = {
        askType,
        intent,
        stage: getStarStage(),
        message: calmText,
        cardName: options.cardName || "",
        firstCard: options.firstCard || "",
        secondCard: options.secondCard || "",
        // Rounds 7-9 ask an opinion about the revealed cards rather than a
        // "help me look" question, so the answer is acknowledged differently.
        isPreference: Boolean(options.isPreference),
        // When set, the caller runs its own listen/classify loop and this
        // call resolves with the raw transcript instead of dispatching.
        deferDispatch: Boolean(options.deferDispatch)
      };

      if (askType !== "play_again_team" && askType !== "play_again_child") {
        starState.starQuestionsAsked += 1;
        starState.questionsThisRound += 1;
        starState.directChildQuestionsAsked += 1;
        starState.lastDirectChildQuestionRound = starState.roundNumber;

        if (askType === "wonder_observation") {
          starState.wonderPromptsAsked += 1;
        }

        if (askType === "help_question") {
          starState.helpPromptsAsked += 1;
        }

        if (askType === "clear_question") {
          starState.clearPromptsAsked += 1;
        }
      }

      const windowResult = await startResponseWindow(
        starState.currentQuestion,
        options.responseSeconds || null,
        turnToken
      );

      if (options.deferDispatch) return windowResult;
    }

    return null;
  }


  function preloadStarAudio(src) {
    return new Promise(resolve => {
      if (!src) {
        resolve(null);
        return;
      }

      const audio = new Audio(src);
      audio.preload = "auto";

      let resolved = false;
      let fallbackTimer = null;

      function finish() {
        if (resolved) return;
        resolved = true;

        if (fallbackTimer) {
          clearTimeout(fallbackTimer);
          fallbackTimer = null;
        }

        resolve(audio);
      }

      audio.addEventListener("canplaythrough", finish, { once: true });
      audio.addEventListener("loadeddata", finish, { once: true });
      audio.addEventListener("error", finish, { once: true });

      fallbackTimer = setTimeout(finish, 900);

      try {
        audio.load();
      } catch (error) {
        finish();
      }
    });
  }

  async function playStarAudioSequence(audioParts, options = {}) {
    const parts = (audioParts || []).filter(Boolean);

    if (!parts.length) {
      return { status: "ended" };
    }

    // Warm the browser cache for all parts before Star starts talking.
    // This reduces the pause before name-callout lines like "Great job, Aarav!"
    await Promise.all(parts.map(preloadStarAudio));

    for (let i = 0; i < parts.length; i++) {
      const result = await playStarAudio(parts[i], options);

      if (result.status !== "ended") {
        return result;
      }

      if (i < parts.length - 1) {
        await sleep(60);
      }
    }

    return { status: "ended" };
  }

  async function speakForPairEvent(eventType, context = {}) {
    updateComfortFromEvent(eventType);

    const question = getPreferenceQuestion(eventType, context);

    if (eventType === "match_found") {
      // Star comments on every match for the entire game.
      // This compliment/comment always happens before any I-wonder, help, or clear prompt.
      await speakStarLine(getMatchLine(context));

      if (question) {
        await sleep(350);

        if (question.askType === "wonder_observation") {
          // I-wonders are comfort-building observations, not questions.
          // Do not turn on the mic, do not wait, and do not treat silence as a missed response.
          registerNonListeningWonderPrompt();

          await speakStarLine(question.message, {
            expectsResponse: false,
            askType: question.askType,
            cardName: context.cardName || "",
              firstCard: context.firstCard || "",
            secondCard: context.secondCard || "",
            volume: 1.0
          });

          return;
        }

        await runChildAnswerExchange(question, {
          expectsResponse: true,
          askType: question.askType,
          isPreference: Boolean(question.isPreference),
          cardName: context.cardName || "",
          firstCard: context.firstCard || "",
          secondCard: context.secondCard || "",
          responseSeconds:
            question.askType === "help_question" ||
            question.askType === "clear_question"
              ? 6
              : 5.4
        });
      }

      return;
    }

    if (eventType === "no_match") {
      if (question) {
        if (question.askType === "wonder_observation") {
          // I-wonders are comfort-building observations, not questions.
          registerNonListeningWonderPrompt();

          await speakStarLine(question.message, {
            expectsResponse: false,
            askType: question.askType,
            cardName: context.cardName || "",
            firstCard: context.firstCard || "",
            secondCard: context.secondCard || ""
          });

          return;
        }

        await runChildAnswerExchange(question, {
          expectsResponse: true,
          askType: question.askType,
          isPreference: Boolean(question.isPreference),
          cardName: context.cardName || "",
          firstCard: context.firstCard || "",
          secondCard: context.secondCard || "",
          responseSeconds:
            question.askType === "help_question" ||
            question.askType === "clear_question"
              ? 6
              : 5.4
        });

        return;
      }

      const noMatchLine = getNoMatchObservation(context);
      if (noMatchLine) {
        await speakStarLine(noMatchLine);
      }
    }
  }

  function getActiveMouth() {
    if (starIntroScreen && !starIntroScreen.classList.contains("hidden")) {
      return document.getElementById("introStarMouth");
    }

    return document.getElementById("starMouth");
  }

  // Drives the mouth PNG from the shared AudioManager's real-time analyser
  // callback. getActiveMouth() is re-resolved on every call (not cached)
  // to preserve the existing behavior of switching from the intro mouth
  // to the main game mouth mid-line if that transition happens while
  // audio is still playing.
  let currentMouthState = "closed";

  function updateMouthFromLevel(level) {
    const mouth = getActiveMouth();
    if (!mouth) return;

    const average = level * 255;
    const normalized = Math.min(Math.max((average - 10) / 70, 0), 1);
    const scaleX = 1 + normalized * 0.12;
    const scaleY = 1 + normalized * 0.20;

    function setMouth(state, sx, sy) {
      if (currentMouthState !== state) {
        mouth.src = `/static/images/mouth-${state}.png`;
        currentMouthState = state;
      }
      mouth.style.transform = `translateX(-50%) scale(${sx}, ${sy})`;
    }

    if (average < 14) {
      setMouth("closed", 1, 1);
    } else if (average < 34) {
      setMouth("small", scaleX, scaleY);
    } else if (average < 58) {
      setMouth("medium", scaleX, scaleY);
    } else {
      setMouth("wide", scaleX, scaleY);
    }
  }

  // Cancels whatever Star audio is currently playing (if any) and resets
  // the mouth to closed. Kept as a small named function since it's called
  // from several restart/transition sites below -- actual audio
  // cancellation and mouth-sync teardown is delegated to the shared
  // AudioManager, which already stops mouth animation on cancel.
  function stopMouthAnimation() {
    if (audioManager) audioManager.cancelActive("stop_mouth_animation");

    const mouth = getActiveMouth();
    if (mouth) {
      mouth.src = "/static/images/mouth-closed.png";
      mouth.style.transform = "translateX(-50%) scale(1)";
      currentMouthState = "closed";
    }
  }

  // Plays exactly one clip as THE authoritative Star audio and returns the
  // AudioManager's honest status ({status:"ended"} is the only one that
  // means the line was actually heard). Preserves the existing volume
  // (default 0.86) and the game's deliberate 0.94 playbackRate.
  function playStarAudio(audioSrc, options = {}) {
    if (!audioSrc) return Promise.resolve({ status: "ended" });

    if (!audioManager) {
      // No AudioManager available (very old/unsupported browser) -- fall
      // back to a plain play() so the game still runs.
      return new Promise(resolve => {
        const audio = new Audio(audioSrc);
        audio.volume = options.volume || 0.86;
        audio.playbackRate = 0.94;
        audio.addEventListener("ended", function () { resolve({ status: "ended" }); }, { once: true });
        audio.addEventListener("error", function () { resolve({ status: "error" }); }, { once: true });
        const p = audio.play();
        if (p && p.catch) p.catch(function (err) { resolve({ status: "play_rejected", error: err }); });
      });
    }

    return audioManager.playAndWait(audioSrc, {
      onMouthLevel: updateMouthFromLevel,
      configureAudio: function (audioEl) {
        audioEl.volume = options.volume || 0.86;
        audioEl.playbackRate = 0.94;
      }
    });
  }

  async function ensureMicPermission() {
  if (starState.micDenied) return null;

  if (mediaStream) {
    const liveAudioTrack = mediaStream
      .getAudioTracks()
      .find(track => track.readyState === "live");

    if (liveAudioTrack) {
      // A previously acquired track can remain live but become disabled.
      // Re-enable it before each response window.
      liveAudioTrack.enabled = true;
      starState.micReady = true;
      return mediaStream;
    }

    mediaStream = null;
  }

  const permissions = window.BraveSproutPermissions;

  if (
    !permissions ||
    typeof permissions.requestMicrophone !== "function"
  ) {
    console.warn(
      "BraveSproutPermissions.requestMicrophone is unavailable."
    );

    starState.micDenied = true;
    starState.micReady = false;
    return null;
  }

  try {
    const result = await permissions.requestMicrophone({
      keepStream: true
    });

    /*
      Supports either:
      - a MediaStream returned directly
      - { success: true, stream }
      - { ready: true, stream }
    */
    const returnedStream =
      result instanceof MediaStream
        ? result
        : result?.stream || null;

    const successful =
      result instanceof MediaStream ||
      result === true ||
      result?.success === true ||
      result?.ready === true;

    if (!successful) {
      throw new Error(
        result?.message ||
        "Microphone permission was not granted."
      );
    }

    /*
      Match Cards needs a live MediaStream for MediaRecorder.
      If the shared helper did not preserve one, acquire it here
      after permission has already been approved.
    */
    if (returnedStream) {
      mediaStream = returnedStream;
    } else if (
      navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia
    ) {
      mediaStream =
        await navigator.mediaDevices.getUserMedia({
          audio: true
        });
    } else {
      throw new Error(
        "This browser does not support microphone access."
      );
    }

    const liveAudioTrack = mediaStream
      .getAudioTracks()
      .find(track => track.readyState === "live");

    if (!liveAudioTrack) {
      throw new Error(
        "The microphone stream is not active."
      );
    }

    liveAudioTrack.enabled = true;

    starState.micReady = true;
    starState.micDenied = false;

    dlog("mic permission granted through shared helper");

    return mediaStream;
  } catch (error) {
    console.warn("Mic permission unavailable:", error);
    dlog(
      "mic permission denied",
      error?.name || error?.message || error
    );

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => {
        track.stop();
      });

      mediaStream = null;
    }

    starState.micReady = false;
    starState.micDenied = true;
    starState.waitingForResponse = false;
    starState.questionCooldownUntil =
      Date.now() + 90 * 1000;

    return null;
  }
}

  function getResponseWindowMs(question, overrideSeconds) {
    if (overrideSeconds) return overrideSeconds * 1000;

    const askType = question?.askType;

    if (askType === "wonder_observation") return 5600;
    if (askType === "help_question") return 6200;
    if (askType === "clear_question") return 6200;
    if (askType === "one_word") return 5500;
    if (askType === "choice" || askType === "opinion_choice") return 5400;
    if (askType === "play_again_team" || askType === "play_again_child") return 6500;

    return 5000;
  }

  function startSpeechEndDetector(stream, maxWindowMs, question = null) {
    stopSpeechEndDetector();

    try {
      responseAudioContext = new (window.AudioContext || window.webkitAudioContext)();

      // Safari can create the context in a suspended state even though the
      // microphone stream itself is valid. Resuming makes the level detector
      // reliable without changing the MediaRecorder audio.
      if (responseAudioContext.state === "suspended") {
        responseAudioContext.resume().catch(function () {});
      }

      responseAnalyser = responseAudioContext.createAnalyser();
      responseAnalyser.fftSize = 512;

      responseMicSource = responseAudioContext.createMediaStreamSource(stream);
      responseMicSource.connect(responseAnalyser);

      const dataArray = new Uint8Array(responseAnalyser.frequencyBinCount);
      const startedAt = Date.now();
      const isPlayAgainWindow =
        question?.intent === "play_again" ||
        question?.askType === "play_again_team" ||
        question?.askType === "play_again_child";

      /*
        Trailing silence used to be 1.6s on the play-again window so a parent
        redirecting the question to the child ("What do you think, Mikey?")
        would not end the window before the child answered. That made a child
        who answered directly wait ~3s after finishing a two-word reply.

        Redirection is now recovered by re-opening the microphone silently
        (see runPlayAgainExchange), and a reply that turns out to be an
        unfinished fragment is stitched onto the next one, so the window no
        longer has to stay open "just in case". It closes as soon as the
        utterance has actually ended.
      */
      const speechThreshold = isPlayAgainWindow ? 6 : 9;
      const minimumRecordingMs = isPlayAgainWindow ? 700 : 900;
      const endingSilenceMs = isPlayAgainWindow ? 900 : 800;

      dlog("speech detector started", {
        askType: question?.askType || null,
        intent: question?.intent || null,
        maxWindowMs,
        speechThreshold,
        minimumRecordingMs,
        endingSilenceMs,
        audioContextState: responseAudioContext.state
      });

      function monitorSpeech() {
        if (!responseAnalyser || !micManager || !micManager.isRecording()) {
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

        if (volume > speechThreshold) {
          if (!heardSpeechInWindow) {
            dlog("speech first detected", {
              askType: question?.askType || null,
              volume: Number(volume.toFixed(2)),
              elapsedMs: now - startedAt
            });
          }

          heardSpeechInWindow = true;
          lastSpeechTime = now;
        }

        const hasRecordedLongEnough = now - startedAt > minimumRecordingMs;
        const silenceAfterSpeech =
          heardSpeechInWindow && now - lastSpeechTime > endingSilenceMs;
        const maxTimeReached = now - startedAt > maxWindowMs;

        if ((hasRecordedLongEnough && silenceAfterSpeech) || maxTimeReached) {
          dlog("speech detector stopping response window", {
            askType: question?.askType || null,
            heardSpeechInWindow,
            reason: maxTimeReached ? "maximum_time" : "silence_after_speech",
            elapsedMs: now - startedAt,
            silenceMs: lastSpeechTime ? now - lastSpeechTime : null
          });

          stopResponseWindow();
          return;
        }

        responseMonitorFrame = requestAnimationFrame(monitorSpeech);
      }

      monitorSpeech();
    } catch (error) {
      console.warn("Could not start speech end detector:", error);
      dlog("speech detector failed", error?.message || error);
    }
  }

  function stopSpeechEndDetector() {
    if (responseMonitorFrame) {
      cancelAnimationFrame(responseMonitorFrame);
      responseMonitorFrame = null;
    }

    if (responseMicSource) {
      try {
        responseMicSource.disconnect();
      } catch (e) {}
      responseMicSource = null;
    }

    if (responseAudioContext) {
      responseAudioContext.close().catch(function () {});
      responseAudioContext = null;
    }

    responseAnalyser = null;
  }

  /*
    Single owner of the "Star is listening" visuals. Every path that ends a
    listening window must call this with `false` -- previously the classes
    were only removed inside handleRecordingStop, so any window that ended
    without reaching it (a superseded recorder, a recorder error, a stale
    turn) left the mic stuck in its active state with nothing listening.
  */
  function setMicListeningUI(active) {
    if (starVideoTile) starVideoTile.classList.toggle("soft-listening", Boolean(active));
    if (micControl) micControl.classList.toggle("quiet-listening", Boolean(active));
  }

  async function startResponseWindow(question, overrideSeconds, turnToken) {
    if (!starState.waitingForResponse || starState.isListening) return null;
    if (turnGuard && turnGuard.isStale(turnToken)) return null;

    const stream = await ensureMicPermission();

    if (turnGuard && turnGuard.rejectIfStale(turnToken, "startResponseWindow_after_permission")) {
      return null;
    }

    if (!stream) {
      diagLog("microphone_track_not_ready", { reason: "ensureMicPermission_failed" });
      starState.waitingForResponse = false;
      setMicListeningUI(false);
      return null;
    }

    if (!micManager) {
      console.warn("Match Cards: shared mic manager unavailable.");
      starState.waitingForResponse = false;
      setMicListeningUI(false);
      return null;
    }

    return new Promise(resolve => {
      const maxWindowMs = getResponseWindowMs(question, overrideSeconds);

      // Reset once when a new recording window begins. Do not reset this in
      // handleRecordingStop, because duplicate stop events must remain blocked.
      responseSubmittedForCurrentWindow = false;

      const liveTrack = stream.getAudioTracks().find(track => track.readyState === "live");
      if (liveTrack) liveTrack.enabled = true;

      dlog("starting response recording", {
        askType: question?.askType || null,
        intent: question?.intent || null,
        maxWindowMs,
        trackState: liveTrack?.readyState || null,
        trackEnabled: liveTrack?.enabled ?? null,
        trackMuted: liveTrack?.muted ?? null
      });

      micManager.startRecording(stream, {
        onStart: function () {
          if (turnGuard && turnGuard.rejectIfStale(turnToken, "startResponseWindow_onStart")) {
            micManager.stopActive("stale_turn_after_start");
            starState.isListening = false;
            setMicListeningUI(false);
            resolve(null);
            return;
          }

          // "Listening" UI is shown only now -- once the browser has
          // confirmed the recorder actually started -- never before.
          starState.isListening = true;

          setMicListeningUI(true);

          heardSpeechInWindow = false;
          lastSpeechTime = 0;

          dlog("response recorder started", {
            askType: question?.askType || null,
            intent: question?.intent || null,
            maxWindowMs,
            trackState: stream.getAudioTracks()[0]?.readyState || null,
            trackEnabled: stream.getAudioTracks()[0]?.enabled ?? null,
            trackMuted: stream.getAudioTracks()[0]?.muted ?? null
          });

          startSpeechEndDetector(stream, maxWindowMs, question);

          recordingTimeout = setTimeout(function () {
            stopResponseWindow();
          }, maxWindowMs);
        },
        onStop: function (blob, mimeType, extension, wasActive) {
          dlog("response recorder stopped", {
            askType: question?.askType || null,
            intent: question?.intent || null,
            blobSize: blob?.size || 0,
            blobType: blob?.type || mimeType || null,
            extension: extension || null,
            wasActive,
            heardSpeechInWindow
          });

          if (!wasActive) {
            // Superseded by a newer recording before it stopped on its
            // own -- that newer recording's own onStop owns resolve().
            return;
          }
          handleRecordingStop(question, turnToken, blob, extension).then(resolve);
        },
        onError: function (error) {
          diagLog("error", { where: "startResponseWindow_recorder", message: String(error && error.message || error) });
          // A recorder that errored will not deliver a usable `stop`, so this
          // is the only chance to release the listening state and let the
          // caller (and the board) move on instead of waiting forever.
          stopSpeechEndDetector();
          if (recordingTimeout) {
            clearTimeout(recordingTimeout);
            recordingTimeout = null;
          }
          starState.isListening = false;
          starState.waitingForResponse = false;
          setMicListeningUI(false);
          resolve(null);
        }
      });
    });
  }

  function stopResponseWindow() {
    stopSpeechEndDetector();

    if (recordingTimeout) {
      clearTimeout(recordingTimeout);
      recordingTimeout = null;
    }

    if (micManager) micManager.stopActive("response_window_ended");

    // Once we've asked the recorder to stop we are no longer listening, so
    // the mic must not keep showing its active state. handleRecordingStop
    // clears this too; doing it here as well covers the paths where the
    // recorder was already inactive and no `stop` event is coming.
    setMicListeningUI(false);
  }

  // Guards against the live-transcript path and the backup recording path
  // both submitting the same child response -- match_cards only has the
  // backup recorder path today (no live SpeechRecognition wired in), but
  // this flag keeps handleRecordingStop itself safe to call more than
  // once for the same window (e.g. a stray duplicate `stop` event).
  let responseSubmittedForCurrentWindow = false;

  async function handleRecordingStop(question, turnToken, blob, extension) {
    // When the caller drives its own listen/classify loop (the play-again
    // exchange and the round 7-9 answers), this function only transcribes and
    // hands the text back -- it must not speak or advance the game itself.
    // Return values in that mode: a transcript string, "" for "nothing
    // usable was heard", or null for "this turn is stale, abandon it".
    const deferDispatch = Boolean(question && question.deferDispatch);

    starState.isListening = false;
    starState.waitingForResponse = false;
    starState.currentQuestion = null;

    setMicListeningUI(false);

    diagLog("recording_stopped", { size: blob ? blob.size : 0 });
    dlog("recording stopped", { round: starState.roundNumber, size: blob ? blob.size : 0 });

    if (turnGuard && turnGuard.rejectIfStale(turnToken, "handleRecordingStop")) {
      return null;
    }

    if (!blob || !blob.size) {
      if (deferDispatch) return "";
      await handleNoSpeechHeard(question, turnToken);
      return null;
    }

    diagLog("audio_blob_created", { size: blob.size, type: blob.type });

    try {
      const formData = new FormData();
      formData.append("audio", blob, `match-response.${extension || "webm"}`);

      diagLog("upload_started", { size: blob.size, type: blob.type });
      dlog("transcribe request start", { round: starState.roundNumber, size: blob.size, type: blob.type });

      const response = await fetch("/api/matching-game/transcribe", {
        method: "POST",
        body: formData
      });

      if (turnGuard && turnGuard.rejectIfStale(turnToken, "handleRecordingStop_transcribe_response")) {
        return null;
      }

      const data = await response.json();
      diagLog("upload_completed", { ok: response.ok, success: !!data.success });
      dlog("transcribe response", {
        status: response.status,
        success: data.success,
        hasText: Boolean(data.text),
        text: data.text || "",
        message: data.message || data.error || ""
      });

      if (!data.success) {
        if (deferDispatch) return "";
        await handleNoSpeechHeard(question, turnToken);
        return null;
      }

      const transcript = cleanTranscript(data.text || "");
      diagLog("transcription_completed", { hasTranscript: !!transcript, length: transcript.length });

      if (!transcript) {
        if (deferDispatch) return "";
        await handleNoSpeechHeard(question, turnToken);
        return null;
      }

      if (turnGuard && turnGuard.rejectIfStale(turnToken, "handleRecordingStop_before_submit")) {
        return null;
      }

      if (responseSubmittedForCurrentWindow) {
        diagLog("duplicate_submission_rejected", { where: "handleRecordingStop" });
        return null;
      }
      responseSubmittedForCurrentWindow = true;

      if (deferDispatch) {
        diagLog("response_returned_to_caller", { length: transcript.length });
        return transcript;
      }

      diagLog("response_submission_started", {});
      await handleSpeechHeard(transcript, question, turnToken);
      return transcript;
    } catch (error) {
      console.error("Transcription error:", error);
      diagLog("error", { where: "handleRecordingStop", message: String(error && error.message || error) });
      dlog("transcribe request failed", error.message || error);
      if (turnGuard && turnGuard.isStale(turnToken)) return null;
      if (deferDispatch) return "";
      await handleNoSpeechHeard(question, turnToken);
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
    return String(text || "").trim().split(/\s+/).filter(Boolean).length;
  }

  function getNamedCardFromTranscript(text) {
    const lower = String(text || "").toLowerCase();

    for (const item of cardItems) {
      const singular = cardLabel(item.name).toLowerCase();
      const plural = cardPlural(item.name).toLowerCase();

      if (new RegExp(`\\b${singular}\\b`).test(lower)) {
        return item.name;
      }

      if (new RegExp(`\\b${plural}\\b`).test(lower)) {
        return item.name;
      }
    }

    return null;
  }

  function getColorFromTranscript(text) {
    const lower = String(text || "").toLowerCase();
    const colors = [
      "red", "orange", "yellow", "green", "blue", "purple", "pink",
      "brown", "black", "white", "gray", "grey", "tan", "gold", "silver"
    ];

    for (const color of colors) {
      if (new RegExp(`\\b${color}\\b`).test(lower)) {
        return color === "grey" ? "gray" : color;
      }
    }

    return null;
  }

  async function handleNoSpeechHeard(question = null, turnToken = null) {
    if (turnGuard && turnGuard.rejectIfStale(turnToken, "handleNoSpeechHeard")) {
      return;
    }

    diagLog("speech_not_detected", { askType: question?.askType || null });
    starState.silentWindows += 1;

    const isDirectChildQuestion =
      question?.askType === "help_question" ||
      question?.askType === "clear_question" ||
      question?.askType === "choice" ||
      question?.askType === "opinion_choice" ||
      question?.askType === "one_word";

    if (isDirectChildQuestion) {
      starState.directChildQuestionSilences += 1;
      starState.directQuestionBackoffUntilRound = Math.max(
        starState.directQuestionBackoffUntilRound,
        starState.roundNumber + 1
      );

      if (question?.askType === "clear_question" && starState.clearChildResponses === 0) {
        starState.nextChildPromptOverride = "help";
      } else if (question?.askType === "help_question" && starState.directChildQuestionSilences >= 2) {
        starState.nextChildPromptOverride = "wonder";
      }

      starState.questionCooldownUntil = Date.now() + 90 * 1000;

      await speakStarLine(pickCalmLine("direct_question_silence_support", [
        "That's okay. You don't have to answer. Let's keep playing.",
        "That's okay. We can just keep playing together.",
        "No problem. Let's keep looking for pairs.",
        "That's okay. I'll watch the next turn with you.",
        "No worries. Let's keep finding matches."
      ]));

      return;
    }

    // Silence on the play-again question is handled by runPlayAgainExchange(),
    // which owns that whole exchange and its retries.
    starState.questionCooldownUntil = Date.now() + 100 * 1000;
  }


  /*
    A parent very often answers Star's "play again or finish?" by turning the
    question around to the child ("What do you think, Mikey?"). That is not a
    decision, and treating it as one -- or as an "unclear" answer worth another
    spoken prompt -- talks over the child just as they are about to reply. The
    classifier therefore has a distinct `redirect` outcome: the caller reopens
    the microphone silently and lets the child answer.

    The distinction is grammatical, not acoustic (no speaker identification):
    a second-person interrogative or a hand-off ("tell Star...", "it's your
    turn") does not answer Star, while a first-person declarative ("I want to
    finish") or a bare choice ("play again") does.
  */
  /*
    Match Cards' reading of the play-again answer.

    The phrase tables that used to live here were a second copy of the same
    done/continue/repeat/redirect knowledge held by the Drawing Game and the
    server, and they drifted: this copy had no "repeat" outcome and its
    negation handling was separate from everyone else's. Classification is now
    delegated to the shared GameIntent module (mirrored by intent.py on the
    server); all that remains here is the mapping onto this game's own labels.
  */
  function classifyPlayAgainResponseLocally(rawTranscript) {
    if (!window.GameIntent) return "unclear";

    var result = window.GameIntent.classify(rawTranscript);

    if (result.intent === "continue") return "play_again";
    if (result.intent === "stop") return "stop";
    if (result.intent === "redirect") return "redirect";
    if (result.intent === "repeat") return "repeat";

    return "unclear";
  }

  /*
    A reply that stopped mid-thought ("I want to...", "I'd like to..."). The
    window closes quickly now, so an unfinished sentence has to be stitched
    onto whatever the child says next rather than dispatched or treated as an
    unclear answer that earns a spoken retry.
  */
  const INCOMPLETE_FRAGMENT_PATTERNS = [
    /\b(?:i|we)\s+(?:want|would like|wanna|need)\s+to$/,
    /\b(?:i|we)\s+(?:want|would like|wanna)$/,
    // GameIntent.normalize() expands "let's" to "let us" before this runs.
    /\blet us$/,
    /\bi\s+(?:am|m)$/,
    /\bcan\s+(?:we|i)$/,
    /\bdo\s+(?:we|i)$/,
    /\b(?:to|the|and|or|a|an|my|another)$/
  ];

  function looksLikeIncompleteFragment(rawTranscript) {
    if (!window.GameIntent) return false;

    var text = window.GameIntent.normalize(rawTranscript);
    if (!text) return false;

    // Anything that already carries a complete intent is not a fragment.
    if (classifyPlayAgainResponseLocally(rawTranscript) !== "unclear") return false;

    return INCOMPLETE_FRAGMENT_PATTERNS.some(function (pattern) {
      return pattern.test(text);
    });
  }

  /*
    Only consulted when the local patterns above cannot decide. The backend
    returns one of the same four labels from a constrained enum; any other
    value (or a failed request) falls back to the local result, so the game
    never depends on the model being reachable.
  */
  async function classifyPlayAgainResponse(rawTranscript) {
    const local = classifyPlayAgainResponseLocally(rawTranscript);

    if (local !== "unclear") return local;

    const text = String(rawTranscript || "").trim();
    if (!text) return "unclear";

    try {
      const response = await fetch("/api/matching-game/classify-intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: text, intent: "play_again" })
      });

      if (!response.ok) return local;

      const data = await response.json();
      const decision = data && data.success ? String(data.decision || "") : "";

      if (["play_again", "stop", "redirect", "unclear"].includes(decision)) {
        diagLog("play_again_ai_classification", { decision: decision });
        return decision;
      }
    } catch (error) {
      diagLog("error", {
        where: "classifyPlayAgainResponse",
        message: String(error && error.message || error)
      });
    }

    return local;
  }

  /*
    Reopens the microphone for the same question without Star saying anything.
    Used after a parent redirects the question to the child: speaking again
    there would talk straight over the child's answer.
  */
  async function listenAgainWithoutSpeaking(question, responseSeconds) {
    const turnToken = turnGuard ? turnGuard.beginNewTurn() : null;

    starState.waitingForResponse = true;
    starState.questionAskedAt = Date.now();
    starState.currentQuestion = Object.assign({}, question, { deferDispatch: true });

    diagLog("silent_relisten_started", { askType: question.askType || null });

    return startResponseWindow(starState.currentQuestion, responseSeconds || null, turnToken);
  }

  /*
    Generic "this speaker handed the question to the child rather than
    answering it" test, used for Star's direct child questions. Same idea as
    the play-again classifier: a second-person interrogative or a hand-off is
    not an answer, so Star keeps listening instead of acknowledging it and
    moving on before the child has spoken.
  */
  function looksLikeRedirection(rawTranscript) {
    if (!window.GameIntent) return false;

    const text = window.GameIntent.normalize(rawTranscript);
    if (!text) return false;

    if (window.GameIntent.classify(rawTranscript).intent === "redirect") return true;

    // "Which do you like more, Mikey?" -- a question in the second person
    // that the shared patterns do not cover verbatim. Speech-to-text often
    // drops the question mark, so the second-person check carries most of the
    // weight and the mark is only corroborating.
    return /[?]/.test(String(rawTranscript || "")) && /\byou\b|\byour\b/.test(text);
  }

  const CHILD_ANSWER_MAX_REDIRECTS = 2;

  /*
    Owns one direct-child-question exchange (rounds 4-12), so a parent
    redirecting the question does not get acknowledged as the child's answer.
    Star listens again silently in that case; anything else is handed to the
    existing acknowledgment/silence handling unchanged.
  */
  async function runChildAnswerExchange(question, speakOptions) {
    let transcript = await speakStarLine(
      question.message,
      Object.assign({}, speakOptions, { deferDispatch: true })
    );

    for (let redirects = 0; redirects <= CHILD_ANSWER_MAX_REDIRECTS; redirects += 1) {
      // Superseded turn (round restart, navigation away) -- abandon quietly.
      if (transcript === null) return;

      // The listening window that just resolved belongs to the current turn,
      // so hand these the live token -- turnGuard treats a null token as
      // stale and would silently drop the answer.
      const liveToken = turnGuard ? turnGuard.currentToken() : null;

      if (transcript === "") {
        await handleNoSpeechHeard(question, liveToken);
        return;
      }

      if (redirects < CHILD_ANSWER_MAX_REDIRECTS && looksLikeRedirection(transcript)) {
        diagLog("child_answer_redirect_detected", { askType: question.askType || null });
        transcript = await listenAgainWithoutSpeaking(
          Object.assign({}, speakOptions, { askType: question.askType }),
          9
        );
        continue;
      }

      await handleSpeechHeard(
        transcript,
        Object.assign({}, speakOptions, { askType: question.askType }),
        liveToken
      );
      return;
    }
  }

  // Bounded so the microphone can never stay open indefinitely, while still
  // leaving room for the common "parent redirects, then child answers" shape.
  const PLAY_AGAIN_MAX_LISTENS = 7;
  const PLAY_AGAIN_MAX_REDIRECTS = 3;
  const PLAY_AGAIN_MAX_UNCLEAR = 2;
  const PLAY_AGAIN_MAX_SILENCES = 2;

  /*
    Owns the whole "play again or finish?" exchange as one loop.

    Previously each unclear answer re-entered speakStarLine from inside the
    recording callback that was still unwinding, so every retry nested another
    listening window inside the previous one's promise. The loop keeps exactly
    one window open at a time and always terminates.
  */
  async function runPlayAgainExchange(question) {
    let listens = 0;
    let redirects = 0;
    let unclearCount = 0;
    let silences = 0;
    // Carries an unfinished reply ("I want to...") onto the next window so the
    // two halves are classified together instead of separately.
    let pendingFragment = "";

    let transcript = await speakStarLine(question.message, {
      expectsResponse: true,
      askType: question.askType,
      intent: "play_again",
      responseSeconds: 9,
      deferDispatch: true
    });

    while (listens < PLAY_AGAIN_MAX_LISTENS) {
      listens += 1;

      /*
        null means no usable listening window. If the game has already moved
        on (a new round started, or we're exiting) something else owns it and
        this exchange must stay quiet. Otherwise the window itself failed --
        no mic permission, a recorder error -- and breaking to the default
        below is what stops the board from staying locked forever.
      */
      if (transcript === null) {
        if (roundInProgress || nextRoundStarting || starState.isEnding) {
          diagLog("play_again_exchange_abandoned", { listens: listens });
          return;
        }

        diagLog("play_again_listen_failed", { listens: listens });
        break;
      }

      if (transcript === "") {
        silences += 1;

        if (silences > PLAY_AGAIN_MAX_SILENCES) break;

        transcript = await speakStarLine(
          pickCalmLine("play_again_silence_retry", [
            "I didn't hear an answer. You can say, let's play again, or, let's finish for now.",
            "I didn't quite hear you. Say, play again, or, I'm done.",
            "Take your time. You can say, one more round, or, finish for now."
          ]),
          {
            expectsResponse: true,
            askType: question.askType,
            intent: "play_again",
            responseSeconds: 9,
            deferDispatch: true
          }
        );
        continue;
      }

      // Stitch an unfinished earlier reply onto this one before classifying.
      if (pendingFragment) {
        transcript = (pendingFragment + " " + transcript).trim();
        pendingFragment = "";
      }

      /*
        The child stopped mid-thought. The window closes quickly now, so this
        is expected -- keep listening and join the halves rather than
        dispatching a partial answer or talking over them with a retry.
      */
      if (looksLikeIncompleteFragment(transcript)) {
        diagLog("play_again_fragment_held", { length: transcript.length });
        pendingFragment = transcript;
        transcript = await listenAgainWithoutSpeaking(question, 7);
        continue;
      }

      const decision = await classifyPlayAgainResponse(transcript);

      dlog("play again response classified", { decision: decision });
      diagLog("play_again_response_classified", {
        decision: decision,
        transcriptLength: transcript.length,
        listens: listens
      });

      // "Can you say that again?" -- replay the exact question, then listen.
      if (decision === "repeat") {
        transcript = await speakStarLine(
          pickCalmLine("play_again_repeat_ack", [
            "Sure, no problem.",
            "Of course.",
            "Okay, here it is again."
          ]) + " " + question.message,
          {
            expectsResponse: true,
            askType: question.askType,
            intent: "play_again",
            responseSeconds: 9,
            deferDispatch: true
          }
        );
        continue;
      }

      if (decision === "play_again") {
        starState.playAgainStartedByVoice = true;
        starState.playAgainSilenceHandled = false;

        // Warm and varied: Star sounds pleased rather than reading a receipt.
        await speakStarLine(pickCalmLine("play_again_yes_ack", [
          "Great idea. I want to play again too.",
          "Yay, let's play another round.",
          "Sounds good. Let's keep going.",
          "Me too. Here comes the next round.",
          "Okay. Let's do one more round together.",
          "Nice. Another round coming up."
        ]));

        startNextRound({ skipIntroLine: true });
        return;
      }

      if (decision === "stop") {
        starState.playAgainSilenceHandled = false;
        await endGameWithGoodbye({ save: false });
        return;
      }

      if (decision === "redirect" && redirects < PLAY_AGAIN_MAX_REDIRECTS) {
        // Someone handed the question to the child. Say nothing, just keep
        // listening -- with a longer window, because the child now has to
        // think before answering.
        redirects += 1;
        transcript = await listenAgainWithoutSpeaking(question, 11);
        continue;
      }

      unclearCount += 1;

      if (unclearCount > PLAY_AGAIN_MAX_UNCLEAR) break;

      transcript = await speakStarLine(
        pickCalmLine("play_again_unclear_retry", [
          "I wasn't sure. You can say, let's play again, or, let's finish for now.",
          "I didn't quite catch that. Say, play again, or, I'm done.",
          "That's okay. You can say, one more round, or, finish for now."
        ]),
        {
          expectsResponse: true,
          askType: question.askType,
          intent: "play_again",
          responseSeconds: 9,
          deferDispatch: true
        }
      );
    }

    /*
      No decision arrived. Continuing is the recoverable default: the board
      stays live, Star asks again after the next two rounds, and the child or
      parent can leave any time with the on-screen back link. Stopping here
      instead would strand the game on a finished board with the microphone
      closed and no on-screen way forward.
    */
    if (roundInProgress || nextRoundStarting || starState.isEnding) return;

    diagLog("play_again_exchange_defaulted", { listens: listens });

    await speakStarLine(pickCalmLine("play_again_no_answer_default", [
      "That's okay. I'll set up another round, and you can tell me any time you want to finish.",
      "No problem. Let's play one more, and just tell me when you'd like to stop.",
      "That's alright. I'll deal another round. Tell me whenever you want to finish."
    ]));

    startNextRound({ skipIntroLine: true });
  }

  async function handleSpeechHeard(transcript, question, turnToken = null) {
    if (turnGuard && turnGuard.rejectIfStale(turnToken, "handleSpeechHeard")) {
      return;
    }

    diagLog("live_transcript_received", { length: transcript.length });

    const words = countWords(transcript);

    starState.spokenResponses += 1;
    starState.spokenWords += words;
    starState.longestResponseWords = Math.max(starState.longestResponseWords, words);

    if (question?.askType === "help_question") {
      starState.concreteChildResponses += 1;
      starState.nextChildPromptOverride = null;
      addComfort(5);
    } else if (question?.askType === "clear_question") {
      starState.clearChildResponses += 1;
      starState.nextChildPromptOverride = null;
      addComfort(6);
    } else if (question?.askType === "choice") {
      starState.childChoiceResponses += 1;
      addComfort(5);
    } else if (question?.askType === "opinion_choice") {
      starState.childOpinionResponses += 1;
      addComfort(5);
    } else {
      addComfort(question?.askType === "one_word" ? 7 : 5);
    }

    // The play-again exchange is driven by runPlayAgainExchange(), which
    // listens with deferDispatch and never routes through here.
    starState.questionCooldownUntil = Date.now() + 75 * 1000;

    let responseLine = "Thanks for telling me. Let's keep playing.";
    const namedCard = getNamedCardFromTranscript(transcript);
    const color = getColorFromTranscript(transcript);

    if (question?.isPreference) {
      /*
        A rounds 7-12 opinion answer. A short reply ("the dog") is a complete
        answer here, so naming the card back is the natural acknowledgment --
        the "thanks for helping me look" wording used for the help/clear
        questions would not make sense for an opinion.

        When Star can tell which card was chosen it sometimes agrees with a
        short, specific line about that card. Only sometimes: agreeing every
        single time stops sounding like an opinion and starts sounding like a
        tic. If the answer was not understood, Star never pretends it was.
      */
      if (namedCard) {
        const agreement = getCardAgreementLine(namedCard);

        if (agreement && Math.random() < 0.45) {
          responseLine = agreement;
        } else {
          responseLine = pickCalmLine("preference_named_ack", [
            "The {first}. Good pick, {child}.",
            "Ooh, the {first}. I like that one too.",
            "The {first}. Thanks for telling me, {child}.",
            "Got it, the {first}. Nice choice."
          ], { firstCard: namedCard });
        }
      } else {
        responseLine = pickCalmLine("preference_ack", [
          "That's a good choice, {child}.",
          "Nice. Thanks for telling me.",
          "I like hearing what you think, {child}.",
          "Good pick. Let's keep playing."
        ]);
      }
    } else if (
      question?.askType === "help_question" ||
      question?.askType === "clear_question"
    ) {
      if (color) {
        responseLine = pickCalmLine("color_ack", [
          "I heard {color}. Thanks for helping me look, {child}.",
          "{color}. I see that too. Thanks, {child}.",
          "Nice, {child}. You noticed {color}.",
          "I heard {color}. Good eye, {child}.",
          "{color}. Thanks for telling me, {child}."
        ], { color });
      } else if (namedCard && namedCard === question.cardName) {
        responseLine = pickCalmLine("card_ack_same", [
          "Yes, the {card} card. Thanks, {child}.",
          "I heard {card}. Thanks for helping me look, {child}.",
          "Right, the {card}. Thanks, {child}.",
          "Yes, those are {cards}. Good eye, {child}."
        ], { cardName: question.cardName });
      } else if (namedCard) {
        responseLine = pickCalmLine("card_ack_other", [
          "I heard {first}. Thanks for answering, {child}.",
          "You said {first}. Thanks, {child}.",
          "I heard the {first} card. Thanks for telling me, {child}."
        ], {
          firstCard: namedCard,
          cardName: question.cardName
        });
      } else {
        responseLine = pickCalmLine("general_response_ack", [
          "I heard you. Thanks for helping me look, {child}.",
          "Thanks, {child}. Let's keep playing.",
          "Thanks for answering, {child}. Let's keep finding pairs.",
          "I heard you, {child}. I'll keep watching the cards."
        ], { cardName: question.cardName });
      }
    } else if (question?.askType === "choice") {
      if (namedCard) {
        responseLine = pickCalmLine("choice_named_ack", [
          "Okay, you picked the {first}. Thanks for telling me.",
          "I heard {first}. Thanks for telling me.",
          "Got it, the {first}. Let's keep playing."
        ], { firstCard: namedCard });
      } else {
        responseLine = pickCalmLine("choice_ack", [
          "Okay. Thanks for telling me.",
          "Thanks. Let's keep looking at the cards.",
          "Got it. Let's keep finding pairs.",
          "Okay. Let's keep playing."
        ]);
      }
    } else if (question?.askType === "opinion_choice") {
      if (namedCard) {
        responseLine = pickCalmLine("opinion_named_ack", [
          "Okay, you like the {first}. Thanks for telling me.",
          "I heard {first}. Thanks for telling me.",
          "Got it, the {first}. Let's keep playing."
        ], { firstCard: namedCard });
      } else {
        responseLine = pickCalmLine("opinion_ack", [
          "Thanks for telling me.",
          "Okay, I heard you.",
          "Got it. Let's keep playing.",
          "Thanks. Let's keep going."
        ]);
      }
    } else if (question?.askType === "one_word") {
      responseLine = "Thank you. Let's keep playing.";
    }

    await speakStarLine(responseLine);
  }

  function setTurn(turn) {
    currentTurn = turn;

    if (turn === "child") {
      childTurnCard.classList.add("active");
      parentTurnCard.classList.remove("active");
    } else {
      parentTurnCard.classList.add("active");
      childTurnCard.classList.remove("active");
    }
  }

  function createDeck() {
    const pairedCards = [...cardItems, ...cardItems];
    return shuffle(pairedCards);
  }

  function renderCards() {
    cardGrid.innerHTML = "";
    cardGrid.classList.remove("board-blurred");

    const deck = createDeck();

    deck.forEach(function (item, index) {
      const card = document.createElement("button");

      card.className = "memory-card";
      card.type = "button";
      card.dataset.name = item.name;
      card.dataset.index = index;
      card.setAttribute("aria-label", "Hidden card");

      card.innerHTML = `
        <div class="memory-card-inner">
          <div class="card-face card-front">
            <img src="${cardBack}" alt="Card back">
          </div>
          <div class="card-face card-back">
            <img src="${item.image}" alt="${item.name}">
          </div>
        </div>
      `;

      card.addEventListener("click", handleCardClick);
      cardGrid.appendChild(card);
    });
  }

  async function handleCardClick() {
  if (lockBoard || !roundInProgress) return;
  if (firstCard && secondCard) return; // prevents 3rd fast flip
  if (this.classList.contains("flipped")) return;
  if (this.classList.contains("matched")) return;

  lockBoard = true;

  this.classList.add("flipped");
  this.setAttribute("aria-label", `${this.dataset.name} card`);

  starState.cardFlips += 1;

  const actingPlayer = currentTurn;

  if (actingPlayer === "child") {
    starState.childFlips += 1;
  }

  if (actingPlayer === "parent") {
    starState.parentFlips += 1;
  }

  if (!firstCard) {
    firstCard = this;
    lockBoard = false;
    return;
  }

  secondCard = this;
  starState.turnsTaken += 1;

  await checkForMatch(actingPlayer);
}

  async function checkForMatch(actingPlayer) {
    const isMatch = firstCard.dataset.name === secondCard.dataset.name;
    const firstName = firstCard.dataset.name;
    const secondName = secondCard.dataset.name;

    updateComfortFromEvent("pair_attempt");

    if (isMatch) {
      firstCard.classList.add("matched");
      secondCard.classList.add("matched");

      matchesFound += 1;

      if (actingPlayer === "child") {
        starState.childMatches += 1;
      }

      if (actingPlayer === "parent") {
        starState.parentMatches += 1;
      }

      await speakForPairEvent("match_found", {
        cardName: firstName,
        firstCard: firstName,
        secondCard: secondName,
        player: actingPlayer,
        remainingPairs: cardItems.length - matchesFound
      });

      resetTurnCards();

      if (matchesFound === cardItems.length) {
        await completeRound();
        return;
      }

      await sleep(300);
      switchTurn();
      lockBoard = false;
    } else {
      await speakForPairEvent("no_match", {
        firstCard: firstName,
        secondCard: secondName,
        player: actingPlayer,
        remainingPairs: cardItems.length - matchesFound
      });

      await sleep(starState.roundNumber === 1 ? 650 : 500);

      firstCard.classList.remove("flipped");
      secondCard.classList.remove("flipped");

      firstCard.setAttribute("aria-label", "Hidden card");
      secondCard.setAttribute("aria-label", "Hidden card");

      resetTurnCards();
      switchTurn();
      lockBoard = false;
    }
  }

  function resetTurnCards() {
    firstCard = null;
    secondCard = null;
  }

  function switchTurn() {
    if (currentTurn === "child") {
      setTurn("parent");
    } else {
      setTurn("child");
    }
  }

  async function completeRound() {
    roundInProgress = false;
    lockBoard = true;
    starState.gameCompleted = true;
    starState.roundsCompleted += 1;
    starState.playAgainStartedByVoice = false;
    starState.playAgainSilenceHandled = false;

    await saveCompletion();

    if (shouldAskPlayAgainQuestion()) {
      const question = getPlayAgainQuestion();
      starState.lastPlayAgainQuestionRound = starState.roundsCompleted;

      await runPlayAgainExchange(question);

      return;
    }

    await speakStarLine(getAutoNextRoundLine());
    startNextRound({ skipIntroLine: true });
  }

  async function saveCompletion(options = {}) {
    const allowDuplicateRoundSave = Boolean(options.allowDuplicateRoundSave);

    if (
      !allowDuplicateRoundSave &&
      starState.roundsCompleted > 0 &&
      starState.lastSavedRoundsCompleted === starState.roundsCompleted
    ) {
      return true;
    }

    const minutesPlayed = getMinutesPlayed();

    const payload = {
      activity_id: activityId,
      words_spoken: starState.spokenWords,
      minutes_spoken: Math.max(0, starState.spokenResponses * 0.08),
      active_minutes: minutesPlayed,
      time_spent_on_activity: minutesPlayed,
      spoken_responses: starState.spokenResponses,
      questions_asked: starState.starQuestionsAsked,
      silent_windows: starState.silentWindows,
      child_matches: starState.childMatches,
      parent_matches: starState.parentMatches,
      final_stage: starState.currentStage,
      rounds_completed: starState.roundsCompleted,
      wonder_prompts_asked: starState.wonderPromptsAsked,
      help_prompts_asked: starState.helpPromptsAsked,
      clear_prompts_asked: starState.clearPromptsAsked,
      child_choice_responses: starState.childChoiceResponses,
      child_opinion_responses: starState.childOpinionResponses,
      child_clear_responses: starState.clearChildResponses,
      direct_child_question_silences: starState.directChildQuestionSilences
    };

    diagLog("completion_save_started", { roundsCompleted: starState.roundsCompleted });

    // The endpoint is safe to call twice with the same rounds_completed
    // (MAX()-based columns server-side, and it only appends a session_log
    // row when the saved count actually increases), so one retry here
    // cannot double-count progress.
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const response = await fetch("/api/matching-game/complete", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        });

        const data = await response.json().catch(function () { return null; });

        if (response.ok && data && data.success) {
          starState.lastSavedRoundsCompleted = starState.roundsCompleted;
          diagLog("completion_saved", { roundsCompleted: starState.roundsCompleted });
          return true;
        }

        diagLog("recoverable_error", { where: "saveCompletion", attempt: attempt, status: response.status });
      } catch (error) {
        diagLog("recoverable_error", { where: "saveCompletion_network", attempt: attempt, message: String(error && error.message || error) });
        console.error("Could not save matching game completion:", error);
      }

      if (attempt === 0) await sleep(500);
    }

    // Previously this function silently believed the save had succeeded
    // regardless of the response, so a real failure here would
    // permanently and silently lose that round's progress (the next
    // completeRound() would see lastSavedRoundsCompleted already "match"
    // and skip saving again). Now it's surfaced in diagnostics instead --
    // the game itself still continues normally, since match_cards has no
    // single combined completion+redirect step this needs to block.
    diagLog("fatal_error", { where: "saveCompletion", roundsCompleted: starState.roundsCompleted });
    console.error("Match Cards: completion save failed after retry; this round's progress may not be recorded.");
    return false;
  }

  function fadeOutToDashboard() {
    let fade = document.getElementById("blackFadeOverlay");

    if (!fade) {
      fade = document.createElement("div");
      fade.id = "blackFadeOverlay";
      fade.style.position = "fixed";
      fade.style.inset = "0";
      fade.style.background = "black";
      fade.style.opacity = "0";
      fade.style.pointerEvents = "none";
      fade.style.transition = "opacity 900ms ease";
      fade.style.zIndex = "99999";
      document.body.appendChild(fade);
    }

    requestAnimationFrame(function () {
      fade.style.opacity = "1";
    });

    setTimeout(function () {
      window.location.href = "/dashboard";
    }, 1100);
  }

  async function endGameWithGoodbye(options = {}) {
    if (starState.isEnding) return;

    starState.isEnding = true;
    roundInProgress = false;
    lockBoard = true;

    if (turnGuard) turnGuard.beginNewTurn();
    diagLog("replay_requested", { where: "endGameWithGoodbye" });

    stopResponseWindow();

    if (options.save !== false) {
      await saveCompletion();
    }

    await speakStarLine(pickCalmLine("goodbye_end", [
      "Okay. Thanks for playing with me. Bye-bye. See you later.",
      "That was fun. We can play again another time. Bye-bye.",
      "All right, we can finish for now. Bye-bye. See you later.",
      "Okay, we can finish here for now. Bye-bye. See you later.",
      "Sounds good. We can stop here for now. Bye-bye. I'll see you later."
    ]));

    cleanupMedia();
    fadeOutToDashboard();
  }

  function setupDashboardExitHandlers() {
    const selectors = [
      'a[href="/dashboard"]',
      'a[href="/dashboard/"]',
      'a[href$="/dashboard"]',
      '#backToDashboard',
      '#goBackDashboard',
      '#backDashboardBtn',
      '.back-to-dashboard',
      '.dashboard-link',
      '.go-back-dashboard',
      // The red leave button in the call bar. It previously had no handler at
      // all, so pressing it did nothing. Routing it through this same list
      // means it exits by exactly the path Back to Dashboard uses --
      // endGameWithGoodbye(), which saves progress, stops the recorder and
      // Star's audio, invalidates in-flight turns and navigates once -- rather
      // than a second, separate exit implementation.
      '#hangupButton'
    ];

    const elements = new Set();

    selectors.forEach(function (selector) {
      document.querySelectorAll(selector).forEach(function (element) {
        elements.add(element);
      });
    });

    elements.forEach(function (element) {
      if (!element || element === declineCall) return;

      const exit = function (event) {
        event.preventDefault();
        endGameWithGoodbye();
      };

      element.addEventListener("click", exit);

      // `role="button"` elements do not activate on Enter/Space by themselves.
      if (element.getAttribute("role") === "button") {
        element.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
            exit(event);
          }
        });
      }
    });
  }

  function hideCompleteModalCompletely() {
    if (completeModal) {
      completeModal.classList.remove("show");
      completeModal.style.display = "none";
    }

    if (gameArea) {
      gameArea.classList.remove("round-complete");
    }

    if (cardGrid) {
      cardGrid.classList.remove("board-blurred");
    }
  }

  function startNextRound(options = {}) {
    if (nextRoundStarting || roundInProgress) return;

    dlog("round transition", { fromRound: starState.roundNumber, stage: getStarStage() });

    // Invalidate whatever the previous round's turn was doing BEFORE
    // anything else runs, so a late audio/recording callback from it
    // can't mutate the round we're about to start.
    if (turnGuard) turnGuard.beginNewTurn();
    if (micManager) micManager.stopActive("start_next_round");

    nextRoundStarting = true;

    hideCompleteModalCompletely();

    stopResponseWindow();
    stopMouthAnimation();

    firstCard = null;
    secondCard = null;
    matchesFound = 0;
    currentTurn = "child";
    roundInProgress = true;
    lockBoard = true;

    starState.gameCompleted = false;
    starState.playAgainStartedByVoice = false;
    starState.playAgainSilenceHandled = false;
    starState.roundNumber += 1;
    starState.questionsThisRound = 0;

    updateRoundDisplay();
    renderCards();
    setTurn("child");
    updateStage();

    if (options.skipIntroLine) {
      lockBoard = false;
      nextRoundStarting = false;
      return;
    }

    speakStarLine(getNewRoundLine())
      .then(function () {
        lockBoard = false;
        nextRoundStarting = false;
      })
      .catch(function () {
        lockBoard = false;
        nextRoundStarting = false;
      });
  }

  async function playIntroLine(text) {
    await speakStarLine(text);
    shrinkIntroToGame();
  }

  function shrinkIntroToGame() {
    stopMouthAnimation();

    const introMouth = document.getElementById("introStarMouth");

    if (introMouth) {
      introMouth.src = "/static/images/mouth-closed.png";
      introMouth.style.transform = "translateX(-50%) scale(1)";
    }

    requestAnimationFrame(function () {
      starIntroScreen.classList.add("shrink");
    });

    setTimeout(function () {
      zoomStage.classList.remove("call-hidden");
    }, 1050);

    setTimeout(function () {
      starIntroScreen.style.display = "none";
      starIntroScreen.classList.add("hidden");
      beginFirstRound();
    }, 1500);
  }

  function getGameStartLine() {
    if (starState.roundNumber > 1) {
      return pickCalmLine("returning_game_instruction", [
        "Let's keep playing matching cards. You can keep going from here.",
        "Let's keep playing. The cards are ready for your next round.",
        "You can keep going from where you left off. Flip two cards and try to find a pair.",
        "Let's keep going with matching cards. Take turns and try to find a pair."
      ]);
    }

    return gameInstructionLine;
  }

  async function beginFirstRound() {
    setTurn("child");
    roundInProgress = true;
    lockBoard = true;
    updateStage();

    await speakStarLine(getGameStartLine());

    lockBoard = false;
  }

  async function startGameAfterCall() {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    // Must happen synchronously inside this real click handler: resuming
    // or creating the shared AudioContext here, inside a genuine user
    // gesture, is what lets later programmatic audio.play() calls (from
    // async continuations further down) succeed under browsers'
    // autoplay policies.
    if (audioManager) audioManager.unlock();
    diagLog("accept_call_clicked", {});

    stopRingtone();
    playCallAcceptedSound();

    const microphoneStream = await ensureMicPermission();

    if (!microphoneStream) {
      diagLog("microphone_track_not_ready", { reason: "startGameAfterCall_ensureMicPermission_failed" });
      console.warn(
        "Match Cards started without microphone access."
      );
    }

    await loadSavedMatchingProgress();

    starIntroScreen.classList.remove("hidden");

    const introLine = getCallIntroLine();

    requestAnimationFrame(function () {
      incomingCallScreen.classList.add("hide");
    });

    setTimeout(function () {
      incomingCallScreen.style.display = "none";
    }, 450);

    setTimeout(function () {
      playIntroLine(introLine);
    }, 900);
  }

function getCallIntroLine() {
  const isEarlyStage = starState.roundNumber <= 3;

  if (isEarlyStage) {
    return introLines[Math.floor(Math.random() * introLines.length)];
  }

  return returningIntroLines[Math.floor(Math.random() * returningIntroLines.length)];
}

function resetStagePromptState() {
  starState.questionsThisRound = 0;
  starState.lastDirectChildQuestionRound = 0;
  starState.directQuestionBackoffUntilRound = 0;
  starState.questionCooldownUntil = 0;
  starState.nextChildPromptOverride = null;
  starState.playAgainSilenceHandled = false;
  starState.playAgainStartedByVoice = false;
}

async function jumpToMatchingRound(targetRound) {
  if (starState.isEnding || nextRoundStarting) return;

  if (turnGuard) turnGuard.beginNewTurn();
  if (micManager) micManager.stopActive("jump_to_round");

  stopResponseWindow();
  stopMouthAnimation();

  hideCompleteModalCompletely();

  roundInProgress = false;
  nextRoundStarting = false;
  lockBoard = true;

  /*
    startNextRound() adds 1 to roundNumber.
    So to land on targetRound, set roundNumber to targetRound - 1 first.
  */
  starState.roundNumber = targetRound - 1;
  starState.roundsCompleted = Math.max(0, targetRound - 1);

  resetStagePromptState();
  updateStage();
  updateRoundDisplay();

  await saveCompletion({ allowDuplicateRoundSave: true });

  startNextRound({ skipIntroLine: false });
}

function skipToNextMatchingStage() {
  if (starState.roundNumber <= 3) {
    jumpToMatchingRound(4);
  } else if (starState.roundNumber <= 6) {
    jumpToMatchingRound(7);
  } else if (starState.roundNumber <= 9) {
    jumpToMatchingRound(10);
  } else {
    jumpToMatchingRound(13);
  }
}

function goBackMatchingStage() {
  if (starState.roundNumber >= 10) {
    jumpToMatchingRound(7);
  } else if (starState.roundNumber >= 7) {
    jumpToMatchingRound(4);
  } else if (starState.roundNumber >= 4) {
    jumpToMatchingRound(1);
  }
}

function createDemoStageButtons() {
  const buttonWrap = document.createElement("div");
  buttonWrap.style.position = "fixed";
  buttonWrap.style.right = "24px";
  buttonWrap.style.bottom = "24px";
  buttonWrap.style.zIndex = "9999";
  buttonWrap.style.display = "flex";
  buttonWrap.style.gap = "10px";

  const backButton = document.createElement("button");
  backButton.type = "button";
  backButton.textContent = "Previous Stage";

  const skipButton = document.createElement("button");
  skipButton.type = "button";
  skipButton.textContent = "Skip Stage";

  [backButton, skipButton].forEach(function (button) {
    button.style.padding = "12px 16px";
    button.style.borderRadius = "999px";
    button.style.border = "none";
    button.style.color = "white";
    button.style.fontWeight = "700";
    button.style.cursor = "pointer";
    button.style.boxShadow = "0 8px 20px rgba(0,0,0,0.18)";
  });

  backButton.style.background = "#4b5563";
  skipButton.style.background = "#7f51f2";

  backButton.addEventListener("click", goBackMatchingStage);
  skipButton.addEventListener("click", skipToNextMatchingStage);

  buttonWrap.appendChild(backButton);
  buttonWrap.appendChild(skipButton);
  document.body.appendChild(buttonWrap);
}

  function cleanupMedia() {
    stopResponseWindow();

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }
  }

  renderCards();
updateRoundDisplay();
setTurn("child");
hideCompleteModalCompletely();
setupDashboardExitHandlers();
if (developerThingy) {
  createDemoStageButtons();
}

  setTimeout(startRingtone, 400);

  // The ringtone's first autoplay attempt (above) has no user gesture
  // behind it and can be silently blocked. If that happens, retry once
  // on the very first real interaction with the page.
  window.addEventListener("pointerdown", function retryRingtoneOnFirstInteraction() {
    if (!ringtoneStarted) startRingtone();
  }, { once: true });

  acceptCall.addEventListener("click", startGameAfterCall);

  declineCall.addEventListener("click", function () {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    if (turnGuard) turnGuard.beginNewTurn();
    if (audioManager) audioManager.cancelActive("decline_call");
    diagLog("game_exited", { where: "decline_call" });

    stopRingtone();
    playCallAcceptedSound();
    cleanupMedia();

    setTimeout(function () {
      window.location.href = "/dashboard";
    }, 300);
  });

  if (restartBtn) {
    restartBtn.addEventListener("click", function () {
      diagLog("retry_requested", { where: "restartBtn" });
      startNextRound({ skipIntroLine: false });
    });
  }

  window.addEventListener("beforeunload", function () {
    if (turnGuard) turnGuard.beginNewTurn();
    if (audioManager) audioManager.cancelActive("beforeunload");
    cleanupMedia();
  });
});