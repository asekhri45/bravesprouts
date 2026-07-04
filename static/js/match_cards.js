document.addEventListener("DOMContentLoaded", function () {
  const matchPage = document.querySelector(".match-page");
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

  let starAudio = null;
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

  let starState = freshStarState();

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

  function getHelpPrompt(context = {}) {
    if (context.cardName) {
      return {
        askType: "help_question",
        message: pickCalmLine("help_question_match", [
          "Can you help me look at the {card} card? What color do you notice?",
          "I missed part of that picture. What color do you see on the {card} card?",
          "I can't see the {card} card clearly. What color do you see?",
          "Help me look closely at the {card} card. What color stands out?",
          "I need help looking at that {card} picture. What color should I look at first?"
        ], context)
      };
    }

    return {
      askType: "help_question",
      message: pickCalmLine("help_question_no_match", [
        "Can you help me remember one card? Was one of those the {first} card?",
        "I missed the first card. Was it the {first} card or the {second} card?",
        "Help me remember. Did we see the {first} card or the {second} card first?",
      ], context)
    };
  }

  function getClearQuestion(context = {}) {
    if (context.cardName) {
      return {
        askType: "clear_question",
        message: pickCalmLine("clear_question_match", [
          "{child}, what card should I watch for next?",
          "{child}, which card should we try to find next?",
          "{child}, what card do you want me to look for next?",
          "{child}, what card should we remember next?",
          "{child}, what card do you want to find next?"
        ], context)
      };
    }

    return {
      askType: "clear_question",
      message: pickCalmLine("clear_question_no_match", [
        "{child}, which card should I remember, the {first} or the {second}?",
        "{child}, what card should I watch for, the {first} or the {second}?",
        "{child}, which one should we try to find next, the {first} or the {second}?",
        "{child}, what card do you want to remember from those two?"
      ], context)
    };
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

    const calmText = String(text || "")
      .replace(/\booo\b/gi, "")
      .replace(/\boh my\b/gi, "")
      .replace(/\s+/g, " ")
      .trim();

    updateStarMessage("Star", calmText);
    rememberStarMessage(calmText);

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

      if (data.success && Array.isArray(data.audio_parts) && data.audio_parts.length) {
        await playStarAudioSequence(data.audio_parts, {
          volume: options.volume || 0.86
        });
      } else if (data.success && data.audio_url) {
        await playStarAudio(data.audio_url, {
          volume: options.volume || 0.86
        });
      } else if (data.success && data.audio) {
        await playStarAudio(data.audio, {
          volume: options.volume || 0.86
        });
      } else {
        await sleep(700);
      }
    } catch (error) {
      console.error("Star TTS error:", error);
      await sleep(700);
    } finally {
      starState.isStarSpeaking = false;
    }

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
        secondCard: options.secondCard || ""
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

      await startResponseWindow(starState.currentQuestion, options.responseSeconds || null);
    }
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
      return;
    }

    // Warm the browser cache for all parts before Star starts talking.
    // This reduces the pause before name-callout lines like "Great job, Aarav!"
    await Promise.all(parts.map(preloadStarAudio));

    for (let i = 0; i < parts.length; i++) {
      await playStarAudio(parts[i], options);

      if (i < parts.length - 1) {
        await sleep(60);
      }
    }
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

        await speakStarLine(question.message, {
          expectsResponse: true,
          askType: question.askType,
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

        await speakStarLine(question.message, {
          expectsResponse: true,
          askType: question.askType,
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

  function playStarAudio(audioSrc, options = {}) {
    return new Promise(resolve => {
      if (!audioSrc) {
        resolve();
        return;
      }

      if (starAudio) {
        starAudio.pause();
        starAudio.currentTime = 0;
      }

      starAudio = new Audio(audioSrc);
      starAudio.volume = options.volume || 0.86;
      starAudio.playbackRate = 0.94;

      let resolved = false;
      let fallbackTimer = null;

      function finish() {
        if (resolved) return;
        resolved = true;

        if (fallbackTimer) {
          clearTimeout(fallbackTimer);
          fallbackTimer = null;
        }

        stopMouthAnimation();
        resolve();
      }

      starAudio.addEventListener("play", startMouthAnimation);
      starAudio.addEventListener("ended", finish);
      starAudio.addEventListener("error", finish);

      fallbackTimer = setTimeout(finish, 20000);

      starAudio.play().catch(function () {
        finish();
      });
    });
  }

  function startMouthAnimation() {
    const mouth = getActiveMouth();

    if (!mouth || !starAudio) return;

    stopMouthAnimation();

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    sourceNode = audioContext.createMediaElementSource(starAudio);
    sourceNode.connect(analyser);
    analyser.connect(audioContext.destination);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let currentMouth = "closed";

    function setMouth(state, scaleX, scaleY) {
      if (currentMouth !== state) {
        mouth.src = `/static/images/mouth-${state}.png`;
        currentMouth = state;
      }

      mouth.style.transform = `translateX(-50%) scale(${scaleX}, ${scaleY})`;
    }

    function animateMouth() {
      analyser.getByteFrequencyData(dataArray);

      let sum = 0;

      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }

      const average = sum / dataArray.length;
      const normalized = Math.min(Math.max((average - 10) / 70, 0), 1);

      const scaleX = 1 + normalized * 0.12;
      const scaleY = 1 + normalized * 0.20;

      if (average < 14) {
        setMouth("closed", 1, 1);
      } else if (average < 34) {
        setMouth("small", scaleX, scaleY);
      } else if (average < 58) {
        setMouth("medium", scaleX, scaleY);
      } else {
        setMouth("wide", scaleX, scaleY);
      }

      mouthAnimationFrame = requestAnimationFrame(animateMouth);
    }

    animateMouth();
  }

  function stopMouthAnimation() {
    const mouth = getActiveMouth();

    if (mouthAnimationFrame) {
      cancelAnimationFrame(mouthAnimationFrame);
      mouthAnimationFrame = null;
    }

    if (sourceNode) {
      try {
        sourceNode.disconnect();
      } catch (e) {}
      sourceNode = null;
    }

    if (analyser) {
      try {
        analyser.disconnect();
      } catch (e) {}
      analyser = null;
    }

    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }

    if (mouth) {
      mouth.src = "/static/images/mouth-closed.png";
      mouth.style.transform = "translateX(-50%) scale(1)";
    }
  }

  async function ensureMicPermission() {
    if (starState.micDenied) return null;
    if (mediaStream) return mediaStream;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      starState.micDenied = true;
      return null;
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      starState.micReady = true;
      return mediaStream;
    } catch (error) {
      console.warn("Mic permission unavailable:", error);
      starState.micDenied = true;
      starState.waitingForResponse = false;
      starState.questionCooldownUntil = Date.now() + 90 * 1000;
      return null;
    }
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

        const hasRecordedLongEnough = now - startedAt > 900;
        const silenceAfterSpeech = heardSpeechInWindow && now - lastSpeechTime > 800;
        const maxTimeReached = now - startedAt > maxWindowMs;

        if ((hasRecordedLongEnough && silenceAfterSpeech) || maxTimeReached) {
          stopResponseWindow();
          return;
        }

        responseMonitorFrame = requestAnimationFrame(monitorSpeech);
      }

      monitorSpeech();
    } catch (error) {
      console.warn("Could not start speech end detector:", error);
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

  async function startResponseWindow(question, overrideSeconds) {
    if (!starState.waitingForResponse || starState.isListening) return null;

    const stream = await ensureMicPermission();

    if (!stream) {
      starState.waitingForResponse = false;
      starState.currentQuestion = null;

      await handleNoSpeechHeard(question);

      return null;
    }

    recordingChunks = [];
    starState.isListening = true;

    if (starVideoTile) {
      starVideoTile.classList.add("soft-listening");
    }

    if (micControl) {
      micControl.classList.add("quiet-listening");
    }

    return new Promise(resolve => {
      try {
        const mimeType = getSupportedMimeType();
        mediaRecorder = mimeType
          ? new MediaRecorder(stream, { mimeType })
          : new MediaRecorder(stream);
      } catch (error) {
        console.warn("MediaRecorder fallback:", error);
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

      const maxWindowMs = getResponseWindowMs(question, overrideSeconds);
      startSpeechEndDetector(stream, maxWindowMs);

      recordingTimeout = setTimeout(function () {
        stopResponseWindow();
      }, maxWindowMs);
    });
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
    starState.isListening = false;
    starState.waitingForResponse = false;
    starState.currentQuestion = null;

    if (starVideoTile) {
      starVideoTile.classList.remove("soft-listening");
    }

    if (micControl) {
      micControl.classList.remove("quiet-listening");
    }

    if (!recordingChunks.length) {
      await handleNoSpeechHeard(question);
      return null;
    }

    const blob = new Blob(recordingChunks, {
      type: recordingChunks[0]?.type || "audio/webm"
    });

    recordingChunks = [];

    try {
      const formData = new FormData();
      formData.append("audio", blob, "match-response.webm");

      const response = await fetch("/api/matching-game/transcribe", {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      if (!data.success) {
        await handleNoSpeechHeard(question);
        return null;
      }

      const transcript = cleanTranscript(data.text || "");

      if (!transcript) {
        await handleNoSpeechHeard(question);
        return null;
      }

      await handleSpeechHeard(transcript, question);
      return transcript;
    } catch (error) {
      console.error("Transcription error:", error);
      await handleNoSpeechHeard(question);
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

  async function handleNoSpeechHeard(question = null) {
    starState.silentWindows += 1;

    const isPlayAgainQuestion =
      question?.askType === "play_again_team" ||
      question?.askType === "play_again_child" ||
      question?.intent === "play_again";

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

    starState.questionCooldownUntil = Date.now() + 100 * 1000;

    if (isPlayAgainQuestion && !roundInProgress && !nextRoundStarting && !starState.playAgainSilenceHandled) {
      starState.playAgainSilenceHandled = true;

      await sleep(500);

      await speakStarLine(pickCalmLine("play_again_silence_bridge", [
        "That's okay. Let's play another round.",
        "No problem. We can play another round together.",
        "That's okay. Let's try one more round together.",
        "No worries. Let's play another round."
      ]));

      startNextRound({ skipIntroLine: true });
    }
  }

  async function handleSpeechHeard(transcript, question) {
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

    const lower = transcript.toLowerCase();

    const isYes = /\b(yes|yeah|yep|sure|okay|ok|again|play|more|one more|another|round|continue|keep going)\b/.test(lower);
    const isNo = /\b(no|nope|not|stop|done|finished|finish|all done|be done|end|early|break|pause|dashboard)\b/.test(lower);

    let intent = question?.intent || null;

    if (question?.askType === "play_again_team" || question?.askType === "play_again_child") {
      intent = "play_again";
    }

    if (intent === "play_again") {
      if (isYes && !isNo) {
        starState.playAgainStartedByVoice = true;

        await speakStarLine(pickCalmLine("play_again_yes_ack", [
          "Okay. Let's play another round.",
          "Sounds good. Let's play another round.",
          "Okay. Let's do one more round together.",
          "Sure. Let's play another round."
        ]));

        startNextRound({ skipIntroLine: true });
        return;
      }

      if (isNo && !isYes) {
        await endGameWithGoodbye({ save: false });
        return;
      }

      await speakStarLine(pickCalmLine("play_again_unclear_ack", [
        "Okay. Let's play another round.",
        "Got it. Let's try one more round.",
        "Okay. One more round together."
      ]));

      startNextRound({ skipIntroLine: true });
      return;
    }

    starState.questionCooldownUntil = Date.now() + 75 * 1000;

    let responseLine = "Thanks for telling me. Let's keep playing.";
    const namedCard = getNamedCardFromTranscript(transcript);
    const color = getColorFromTranscript(transcript);

    if (
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

      await speakStarLine(question.message, {
        expectsResponse: true,
        askType: question.askType,
        intent: "play_again",
        responseSeconds: 6
      });

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
      return;
    }

    const minutesPlayed = getMinutesPlayed();

    try {
      await fetch("/api/matching-game/complete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
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
        })
      });

      starState.lastSavedRoundsCompleted = starState.roundsCompleted;
    } catch (error) {
      console.error("Could not save matching game completion:", error);
    }
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

    stopResponseWindow();

    if (options.save !== false) {
      await saveCompletion();
    }

    await speakStarLine(pickCalmLine("goodbye_end", [
      "Okay, I think we should end here for now. Bye-bye. See you later.",
      "Okay, we can finish here for now. Bye-bye. See you later.",
      "Sounds good. We can stop here for now. Bye-bye. I'll see you later.",
      "Okay. Thanks for playing with me. Bye-bye. See you later.",
      "Okay, let's end here for now. Bye-bye. See you later."
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
      '.go-back-dashboard'
    ];

    const elements = new Set();

    selectors.forEach(function (selector) {
      document.querySelectorAll(selector).forEach(function (element) {
        elements.add(element);
      });
    });

    elements.forEach(function (element) {
      if (!element || element === declineCall) return;

      element.addEventListener("click", function (event) {
        event.preventDefault();
        endGameWithGoodbye();
      });
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

    nextRoundStarting = true;

    hideCompleteModalCompletely();

    if (starAudio) {
      starAudio.pause();
      starAudio.currentTime = 0;
    }

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

    stopRingtone();
    playCallAcceptedSound();

    ensureMicPermission();

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

  stopResponseWindow();
  stopMouthAnimation();

  if (starAudio) {
    starAudio.pause();
    starAudio.currentTime = 0;
  }

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

  if (restartBtn) {
    restartBtn.addEventListener("click", function () {
      startNextRound({ skipIntroLine: false });
    });
  }

  window.addEventListener("beforeunload", cleanupMedia);
});