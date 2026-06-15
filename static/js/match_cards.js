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

  const gameInstructionLine =
    "Let’s play matching cards. Flip two cards, try to find a pair, and take turns with your grown-up.";

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

      isStarSpeaking: false,
      isListening: false,
      waitingForResponse: false,
      questionAskedAt: null,
      questionCooldownUntil: 0,
      currentQuestion: null,

      recentStarMessages: [],
      recentLineKeys: [],

      starQuestionsAsked: 0,
      micReady: false,
      micDenied: false,

      gameCompleted: false,
      playAgainStartedByVoice: false,
      playAgainSilenceHandled: false
    };
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
      Stage 0: Star is a calm teammate.
      Stage 1: Star notices the child more directly.
      Stage 2: Star may ask rare, easy preference questions.
      Stage 3: Star may ask child-specific tiny questions.
    */

    if (minutes >= 3 || starState.roundsCompleted >= 1 || starState.cardFlips >= 12) {
      nextStage = 1;
    }

    if (
      minutes >= 7 ||
      starState.roundsCompleted >= 2 ||
      (starState.spokenResponses >= 1 && starState.roundsCompleted >= 1)
    ) {
      nextStage = 2;
    }

    if (
      minutes >= 11 ||
      starState.roundsCompleted >= 4 ||
      (starState.spokenResponses >= 2 && starState.roundsCompleted >= 2) ||
      starState.spokenWords >= 5
    ) {
      nextStage = 3;
    }

    starState.currentStage = Math.min(3, nextStage);
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

  function isAnimalCard(name) {
    return ["cat", "dog", "bunny", "fish", "bird"].includes(name);
  }

  function bothAreAnimals(first, second) {
    return isAnimalCard(first) && isAnimalCard(second);
  }

  function fillLine(template, context = {}) {
    return template
      .replaceAll("{child}", childName)
      .replaceAll("{card}", cardLabel(context.cardName))
      .replaceAll("{cards}", cardPlural(context.cardName))
      .replaceAll("{first}", cardLabel(context.firstCard))
      .replaceAll("{second}", cardLabel(context.secondCard));
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

  function getMatchLine(context) {
    const stage = getStarStage();
    const player = context.player;

    if (player === "parent") {
      if (stage >= 2) {
        return pickCalmLine("parent_match_later", [
          "Nice match with the {card}.",
          "That was a good turn.",
          "You two found another pair.",
          "Good teamwork on that match.",
          "That pair is off the board."
        ], context);
      }

      return pickCalmLine("parent_match_early", [
        "Nice match with the {card}.",
        "Great teamwork.",
        "You two found a pair.",
        "That was a good team match.",
        "Nice remembering."
      ], context);
    }

    if (stage >= 3) {
      return pickCalmLine("child_match_stage3", [
        "Great match with the {card}, {child}.",
        "You found the {card} pair.",
        "Nice remembering with the {card}.",
        "That was careful looking.",
        "You got both {card} cards together."
      ], context);
    }

    if (stage >= 1) {
      return pickCalmLine("child_match_stage1", [
        "Great match with the {card}.",
        "You found the {card} pair.",
        "Nice job finding both {card} cards.",
        "Good remembering.",
        "That was a strong match."
      ], context);
    }

    return pickCalmLine("team_match_stage0", [
      "Great match with the {card}.",
      "You two found a pair.",
      "Nice teamwork.",
      "That pair is found.",
      "Good job finding a match."
    ], context);
  }

  function getNewRoundLine() {
    const stage = getStarStage();

    if (stage >= 3) {
      return pickCalmLine("new_round_stage3", [
        "New round, {child}. Let’s see what you find.",
        "The cards are mixed again.",
        "Here comes another board.",
        "Let’s try one more board.",
        "Another round is ready."
      ]);
    }

    if (stage >= 1) {
      return pickCalmLine("new_round_stage1", [
        "New round. You two are a good team.",
        "The cards are mixed again.",
        "Let’s find more matches.",
        "Here comes another board.",
        "Another round is ready."
      ]);
    }

    return pickCalmLine("new_round_stage0", [
      "Let’s try another round.",
      "The cards are mixed again.",
      "New round.",
      "Let’s find more matches."
    ]);
  }

  function childReadyForDirectQuestion() {
    const stage = getStarStage();

    if (stage < 2) return false;

    // Do not ask child-directed questions too early.
    if (starState.roundsCompleted < 2 && getMinutesPlayed() < 7) return false;

    // If silence has happened more than speech, slow down.
    if (starState.silentWindows > starState.spokenResponses + 1) return false;

    return true;
  }

  function childReadyForPlayAgainQuestion() {
    const stage = getStarStage();

    return (
      stage >= 3 &&
      starState.roundsCompleted >= 3 &&
      starState.spokenResponses >= 2 &&
      starState.silentWindows <= starState.spokenResponses + 1
    );
  }

  function getPlayAgainQuestion() {
    if (childReadyForPlayAgainQuestion()) {
      return {
        message: pickCalmLine("play_again_child", [
          "{child}, you can say yes if you want another round.",
          "{child}, we can play another round if you want.",
          "{child}, you can tell me if you want one more round."
        ]),
        askType: "play_again_child"
      };
    }

    return {
      message: pickCalmLine("play_again_team", [
        "You can say yes if you two want another round.",
        "We can play another round if you want.",
        "You can tell me if you want one more round together."
      ]),
      askType: "play_again_team"
    };
  }

  function getPreferenceQuestion(eventType, context = {}) {
    const stage = getStarStage();

    if (!childReadyForDirectQuestion()) return null;
    if (starState.questionsThisRound >= (stage >= 3 ? 2 : 1)) return null;
    if (Date.now() < starState.questionCooldownUntil) return null;
    if (context.player !== "child") return null;

    const first = context.firstCard;
    const second = context.secondCard;
    const card = context.cardName;
    const r = Math.random();

    if (stage === 2) {
      if (eventType === "match_found" && r < 0.18) {
        if (isAnimalCard(card)) {
          return {
            askType: "yes_no",
            message: `${childName}, would you keep a ${cardLabel(card)} as a pet?`
          };
        }

        return {
          askType: "yes_no",
          message: `${childName}, do you like the flower card?`
        };
      }

      if (eventType === "no_match" && r < 0.10) {
        if (bothAreAnimals(first, second)) {
          return {
            askType: "choice",
            message: `${childName}, which one do you think is cuter, the ${cardLabel(first)} or the ${cardLabel(second)}?`
          };
        }

        return {
          askType: "choice",
          message: `${childName}, which card do you like more, the ${cardLabel(first)} or the ${cardLabel(second)}?`
        };
      }
    }

    if (stage >= 3) {
      if (eventType === "match_found" && r < 0.26) {
        if (isAnimalCard(card)) {
          return {
            askType: "one_word",
            message: `${childName}, what animal card is your favorite?`
          };
        }

        return {
          askType: "one_word",
          message: `${childName}, which card is your favorite?`
        };
      }

      if (eventType === "no_match" && r < 0.16) {
        if (bothAreAnimals(first, second)) {
          return {
            askType: "choice",
            message: `${childName}, which animal would you rather have as a pet, the ${cardLabel(first)} or the ${cardLabel(second)}?`
          };
        }

        return {
          askType: "choice",
          message: `${childName}, which card do you like more, the ${cardLabel(first)} or the ${cardLabel(second)}?`
        };
      }
    }

    return null;
  }

  function shouldStarSpeakForMatch(actingPlayer) {
    const round = starState.roundNumber;

    /*
      Round 1: frequent positive support.
      Round 2: still supportive, but less constant.
      Round 3+: Star is calmer and comments only sometimes.
      Misses are silent unless Star is asking a question.
    */

    if (round === 1) {
      return true;
    }

    if (round === 2) {
      return true;
    }

    if (round === 3) {
      return actingPlayer === "child" ? Math.random() < 0.55 : Math.random() < 0.30;
    }

    if (round >= 4) {
      return actingPlayer === "child" ? Math.random() < 0.38 : Math.random() < 0.18;
    }

    return false;
  }

  function isVerbalAsk(askType) {
    return (
      askType === "yes_no" ||
      askType === "choice" ||
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
      .replace(/!/g, ".")
      .replace(/\?/g, ".")
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

      if (data.success && data.audio) {
        await playStarAudio(data.audio);
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
      }

      await startResponseWindow(starState.currentQuestion, options.responseSeconds || null);
    }
  }

  async function speakForPairEvent(eventType, context = {}) {
    updateComfortFromEvent(eventType);

    const question = getPreferenceQuestion(eventType, context);

    if (question) {
      await speakStarLine(question.message, {
        expectsResponse: true,
        askType: question.askType,
        cardName: context.cardName || "",
        firstCard: context.firstCard || "",
        secondCard: context.secondCard || "",
        responseSeconds: question.askType === "one_word" ? 5.5 : 5.2
      });

      return;
    }

    // Misses stay silent unless Star is asking a real child-directed question.
    if (eventType === "no_match") {
      return;
    }

    if (eventType === "match_found" && !shouldStarSpeakForMatch(context.player)) {
      return;
    }

    if (eventType === "match_found") {
      await speakStarLine(getMatchLine(context));
    }
  }

  function getActiveMouth() {
    if (starIntroScreen && !starIntroScreen.classList.contains("hidden")) {
      return document.getElementById("introStarMouth");
    }

    return document.getElementById("starMouth");
  }

  function playStarAudio(audioSrc) {
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

      /*
        This helps keep Star calmer from the browser side.
        True pitch/emotion control is mostly in ElevenLabs voice settings,
        but this reduces speed and sharpness a bit.
      */
      starAudio.volume = 0.84;
      starAudio.playbackRate = 0.92;

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

      fallbackTimer = setTimeout(finish, 9000);

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

    // These are only max windows. The speech-end detector usually stops earlier.
    if (askType === "one_word") return 5500;
    if (askType === "choice") return 5200;
    if (askType === "yes_no") return 4500;
    if (askType === "play_again_team" || askType === "play_again_child") return 5000;

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

        /*
          This stops recording soon after the child/parent finishes talking.
          If it cuts off very quiet answers, lower this to 7.
          If background noise triggers it too easily, raise this to 11 or 12.
        */
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

      if (question?.intent === "play_again") {
        handleNoSpeechHeard(question);
      }

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
      handleNoSpeechHeard(question);
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
        handleNoSpeechHeard(question);
        return null;
      }

      const transcript = cleanTranscript(data.text || "");

      if (!transcript) {
        handleNoSpeechHeard(question);
        return null;
      }

      await handleSpeechHeard(transcript, question);
      return transcript;
    } catch (error) {
      console.error("Transcription error:", error);
      handleNoSpeechHeard(question);
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

  function handleNoSpeechHeard(question = null) {
    starState.silentWindows += 1;
    starState.questionCooldownUntil = Date.now() + 100 * 1000;

    const isPlayAgainQuestion =
      question?.askType === "play_again_team" ||
      question?.askType === "play_again_child" ||
      question?.intent === "play_again";

    if (isPlayAgainQuestion && !roundInProgress && !nextRoundStarting && !starState.playAgainSilenceHandled) {
      starState.playAgainSilenceHandled = true;

      setTimeout(function () {
        speakStarLine(pickCalmLine("play_again_silence_bridge", [
          "I think we can do one more round together.",
          "Let’s try one more round together.",
          "I’ll mix the cards one more time.",
          "We can do one more board together."
        ])).then(function () {
          startNextRound({ skipIntroLine: true });
        });
      }, 900);
    }
  }

  async function handleSpeechHeard(transcript, question) {
    const words = countWords(transcript);

    starState.spokenResponses += 1;
    starState.spokenWords += words;
    starState.longestResponseWords = Math.max(starState.longestResponseWords, words);

    addComfort(question?.askType === "one_word" ? 7 : 5);

    const lower = transcript.toLowerCase();

    const isYes = /\b(yes|yeah|yep|sure|okay|ok|again|play|more|one more|another)\b/.test(lower);
    const isNo = /\b(no|nope|not|stop|done|finished|all done)\b/.test(lower);

    let intent = question?.intent || null;

    if (question?.askType === "play_again_team" || question?.askType === "play_again_child") {
      intent = "play_again";
    }

    if (intent === "play_again") {
      if (isYes) {
        starState.playAgainStartedByVoice = true;

        await speakStarLine(pickCalmLine("play_again_yes_ack", [
          "That’s great. Let’s play another round.",
          "Great. Let’s play another round.",
          "Sounds good. I’ll mix the cards again.",
          "Okay. Let’s do one more round together."
        ]));

        startNextRound({ skipIntroLine: true });
        return;
      }

      if (isNo) {
        updateStarMessage("Star", "Okay, we can stop here.");
        await speakStarLine("Okay, we can stop here.");
        return;
      }

      await speakStarLine("Okay.");
      startNextRound({ skipIntroLine: true });
      return;
    }

    starState.questionCooldownUntil = Date.now() + 55 * 1000;

    let responseLine = "Got it, let’s keep playing.";

    if (question?.askType === "one_word") {
      const firstWord = transcript.split(/\s+/)[0] || transcript;
      responseLine = `${firstWord}, nice.`;
    } else if (question?.askType === "choice") {
      responseLine = "Good choice.";
    } else if (question?.askType === "yes_no") {
      responseLine = "Got it.";
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
        player: actingPlayer
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
        player: actingPlayer
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

    const question = getPlayAgainQuestion();

    await speakStarLine(question.message, {
      expectsResponse: true,
      askType: question.askType,
      intent: "play_again",
      responseSeconds: 5
    });
  }

  async function saveCompletion() {
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
          rounds_completed: starState.roundsCompleted
        })
      });
    } catch (error) {
      console.error("Could not save matching game completion:", error);
    }
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

  async function beginFirstRound() {
    setTurn("child");
    roundInProgress = true;
    lockBoard = true;

    await speakStarLine(gameInstructionLine);

    lockBoard = false;
  }

  async function startGameAfterCall() {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    stopRingtone();
    playCallAcceptedSound();

    ensureMicPermission();

    starIntroScreen.classList.remove("hidden");

    const introLine = introLines[Math.floor(Math.random() * introLines.length)];

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