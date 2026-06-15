document.addEventListener("DOMContentLoaded", function () {
  const cardGrid = document.getElementById("cardGrid");
  const childTurnCard = document.getElementById("childTurnCard");
  const parentTurnCard = document.getElementById("parentTurnCard");
  const starBubble = document.getElementById("starBubble");
  const completeModal = document.getElementById("completeModal");
  const restartBtn = document.getElementById("restartBtn");


  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const zoomStage = document.getElementById("zoomStage");

const starIntroScreen = document.getElementById("starIntroScreen");

const screenShareLoading = document.getElementById("screenShareLoading");

const ringtone = new Audio("/static/images/ringtone.mp3");
ringtone.loop = true;
ringtone.volume = 0.35;

let ringtoneStarted = false;

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

const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
callAcceptedSound.volume = 0.5;

function playCallAcceptedSound() {
  callAcceptedSound.currentTime = 0;

  return callAcceptedSound.play().catch(function (error) {
    console.log("Could not play call accepted sound:", error);
  });
}

  const cardBack = "/static/images/card-back.png";

  const cardItems = [
    { name: "cat", image: "/static/images/card-cat.png" },
    { name: "dog", image: "/static/images/card-dog.png" },
    { name: "bunny", image: "/static/images/card-bunny.png" },
    { name: "fish", image: "/static/images/card-fish.png" },
    { name: "bird", image: "/static/images/card-bird.png" },
    { name: "flower", image: "/static/images/card-flower.png" }
  ];

  let firstCard = null;
  let secondCard = null;
  let lockBoard = false;
  let matchesFound = 0;
  let currentTurn = "child";
  let starAudio = null;

  let audioContext = null;
  let analyser = null;
  let sourceNode = null;
  let mouthAnimationFrame = null;

  let starState = freshStarState();

  const scriptedLines = {
    game_start: [
      "I’ll hang out while you play.",
      "Let’s see what we find.",
      "I’m here with you.",
      "This looks cozy."
    ],
    card_flip: [
      "Nice flip.",
      "Ooo, a pretty card.",
      "That one was hiding.",
      "Good pick.",
      "There it is."
    ],
    match_found: [
      "Nice match.",
      "Good memory.",
      "You found it.",
      "That was a great pair.",
      "Ooo, there it is."
    ],
    no_match: [
      "That was close.",
      "Almost.",
      "Hmm, not that one.",
      "The cards are tricky.",
      "Good try."
    ],
    child_turn: [
      "Your turn.",
      "Let’s see what you find.",
      "Two cards this time."
    ],
    parent_turn: [
      "Parent’s turn.",
      "Let’s see their pick.",
      "Now parent gets a try."
    ],
    game_complete: [
      "You found them all.",
      "That was great teamwork.",
      "All the matches are found."
    ]
  };

  const introLines = [
  "Hi there. I'm Star. I'll hang out while you play a matching game today... Let me just share my screen...",
  "Hello! I'm Star. I'll be right here while you play a matching game today... Let me just share my screen...",
  "Hi there. I'm Star. I'll keep you company while you play today... Let me just share my screen...",
  "Hey! I'm Star. I'll be hanging out with you while you play a matching game... Let me just share my screen...",
  "Hi there. I'm Star. I'll be cheering you on while you play today... Let me just share my screen...",
  "Hey friends! I’m Star. I’ll keep you company while you find the matches... Let me just share my screen..."
  ];

  function freshStarState() {
    return {
      sessionStart: Date.now(),
      maxComfortStage: 0,
      currentStage: 0,
      comfortScore: 0,

      lastStarTime: 0,
      lastApiCall: 0,
      isStarSpeaking: false,

      waitingForResponse: false,
      questionAskedAt: null,
      questionStage: 0,
      questionCooldownUntil: 0,

      starMessagesPlayed: 0,
      starQuestionsAsked: 0,
      recentStarMessages: []
    };
  }

  function getMinutesPlayed() {
    return (Date.now() - starState.sessionStart) / 60000;
  }

  function getTimeAllowedStage() {
    const minutes = getMinutesPlayed();

    if (minutes < 5) return 0;
    if (minutes < 10) return 1;
    if (minutes < 18) return 2;
    return 3;
  }

  function getStarStage() {
    return Math.min(getTimeAllowedStage(), starState.maxComfortStage);
  }

  function updateStage() {
    const minutes = getMinutesPlayed();

    if (minutes >= 5 && starState.comfortScore >= 8) {
      starState.maxComfortStage = Math.max(starState.maxComfortStage, 1);
    }

    if (minutes >= 10 && starState.comfortScore >= 18) {
      starState.maxComfortStage = Math.max(starState.maxComfortStage, 2);
    }

    if (minutes >= 18 && starState.comfortScore >= 32) {
      starState.maxComfortStage = Math.max(starState.maxComfortStage, 3);
    }

    starState.currentStage = getStarStage();
  }

  function lowerStageAfterNoResponse() {
    starState.maxComfortStage = Math.max(0, starState.maxComfortStage - 1);
    starState.comfortScore = Math.max(0, starState.comfortScore - 5);
    starState.waitingForResponse = false;
    starState.questionAskedAt = null;
    starState.questionCooldownUntil = Date.now() + 2 * 60000;
    updateStage();
  }

  function checkQuestionTimeout() {
    if (!starState.waitingForResponse) return;

    const elapsed = Date.now() - starState.questionAskedAt;

    if (elapsed > 10000) {
      lowerStageAfterNoResponse();
    }
  }

  function updateComfort(eventType) {
    checkQuestionTimeout();

    if (eventType === "card_flip") starState.comfortScore += 0.5;
    if (eventType === "match_found") starState.comfortScore += 2;
    if (eventType === "no_match") starState.comfortScore += 0.25;
    if (eventType === "game_complete") starState.comfortScore += 3;

    updateStage();
  }

  function shuffle(array) {
    const copy = [...array];

    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }

    return copy;
  }

  function updateStarMessage(title, message) {
    if (!starBubble) return;

    starBubble.innerHTML = `
      <h2>${title}</h2>
      <p>${message}</p>
    `;
  }

  function rememberStarMessage(message) {
    starState.recentStarMessages.push(message);

    if (starState.recentStarMessages.length > 10) {
      starState.recentStarMessages.shift();
    }
  }

  function pickScriptedLine(type) {
    const lines = scriptedLines[type] || scriptedLines.card_flip;
    return lines[Math.floor(Math.random() * lines.length)];
  }

  function speakInstant(type) {
    const line = pickScriptedLine(type);
    updateStarMessage("Star", line);
    rememberStarMessage(line);
  }

  function getAskType() {
    const stage = getStarStage();

    if (stage === 0) return "none";
    if (starState.waitingForResponse) return "none";
    if (Date.now() < starState.questionCooldownUntil) return "none";

    const r = Math.random();

    if (stage === 1) {
      return r < 0.18 ? "nonverbal" : "none";
    }

    if (stage === 2) {
      if (r < 0.14) return "yes_no";
      if (r < 0.24) return "choice";
      return "none";
    }

    if (stage >= 3) {
      if (r < 0.15) return "choice";
      if (r < 0.25) return "one_word";
      return "none";
    }

    return "none";
  }

  function shouldUseAI(eventType) {
    checkQuestionTimeout();
    updateStage();

    const now = Date.now();
    const stage = getStarStage();

    if (starState.isStarSpeaking) return false;
    if (now - starState.lastStarTime < 7000) return false;
    if (now - starState.lastApiCall < 15000) return false;

    if (eventType === "game_complete") return true;

    if (stage === 0) {
      if (eventType === "match_found" && Math.random() < 0.25) return true;
      if (eventType === "card_flip" && Math.random() < 0.12) return true;
      return false;
    }

    if (stage === 1) {
      if (eventType === "match_found" && Math.random() < 0.35) return true;
      if (eventType === "card_flip" && Math.random() < 0.18) return true;
      return Math.random() < 0.12;
    }

    if (stage >= 2) {
      if (eventType === "match_found" && Math.random() < 0.45) return true;
      if (eventType === "no_match" && Math.random() < 0.22) return true;
      return Math.random() < 0.2;
    }

    return false;
  }

  async function triggerStar(eventType, cardName = "") {
    updateComfort(eventType);

    if (!shouldUseAI(eventType)) {
      if (Math.random() < 0.7 || eventType === "game_complete") {
        speakInstant(eventType);
      }
      return;
    }

    const askType = getAskType();
    const stage = getStarStage();

    try {
      starState.lastStarTime = Date.now();
      starState.lastApiCall = Date.now();
      starState.isStarSpeaking = true;

      const response = await fetch("/api/matching-game/message", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          event_type: eventType,
          card_name: cardName,
          player: currentTurn,
          stage: stage,
          ask_type: askType,
          recent_star_messages: starState.recentStarMessages
        })
      });

      const data = await response.json();

      if (!data.success) {
        starState.isStarSpeaking = false;
        speakInstant(eventType);
        return;
      }

      updateStarMessage("Star", data.message);
      rememberStarMessage(data.message);

      starState.starMessagesPlayed += 1;

      if (askType !== "none") {
        starState.waitingForResponse = true;
        starState.questionAskedAt = Date.now();
        starState.questionStage = stage;
        starState.starQuestionsAsked += 1;
      }

      playStarAudio(data.audio);
    } catch (error) {
      console.error("Star error:", error);
      starState.isStarSpeaking = false;
      speakInstant(eventType);
    }
  }

  function getActiveMouth() {
  if (starIntroScreen && !starIntroScreen.classList.contains("hidden")) {
    return document.getElementById("introStarMouth");
  }

  return document.getElementById("starMouth");
  }

  function playStarAudio(audioSrc) {
  if (!audioSrc) {
    starState.isStarSpeaking = false;
    return;
  }

  starState.isStarSpeaking = true;

    if (starAudio) {
      starAudio.pause();
      starAudio.currentTime = 0;
    }

    starAudio = new Audio(audioSrc);
    starAudio.volume = 1.0;
    starAudio.playbackRate = 1.0;

    starAudio.addEventListener("play", startMouthAnimation);

    starAudio.addEventListener("ended", function () {
      starState.isStarSpeaking = false;
      stopMouthAnimation();
    });

    starAudio.addEventListener("error", function () {
      starState.isStarSpeaking = false;
      stopMouthAnimation();
    });

    starAudio.play().catch(function () {
      starState.isStarSpeaking = false;
      stopMouthAnimation();
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

  mouth.style.transform =
    `translateX(-50%) scale(${scaleX}, ${scaleY})`;
}

    function animateMouth() {
      analyser.getByteFrequencyData(dataArray);

      let sum = 0;

      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }

      const average = sum / dataArray.length;

      const normalized = Math.min(Math.max((average - 10) / 70, 0), 1);

let scaleX = 1 + normalized * 0.18;
let scaleY = 1 + normalized * 0.32;

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

  function setTurn(turn) {
    currentTurn = turn;

    if (turn === "child") {
      childTurnCard.classList.add("active");
      parentTurnCard.classList.remove("active");
      triggerStar("child_turn");
    } else {
      parentTurnCard.classList.add("active");
      childTurnCard.classList.remove("active");
      triggerStar("parent_turn");
    }
  }

  function createDeck() {
    const pairedCards = [...cardItems, ...cardItems];
    return shuffle(pairedCards);
  }

  function renderCards() {
    cardGrid.innerHTML = "";

    const deck = createDeck();

    deck.forEach(function (item, index) {
      const card = document.createElement("button");
      card.className = "memory-card";
      card.type = "button";
      card.dataset.name = item.name;
      card.dataset.index = index;

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

  function handleCardClick() {
    if (lockBoard) return;
    if (this.classList.contains("flipped")) return;
    if (this.classList.contains("matched")) return;

    this.classList.add("flipped");

    if (!firstCard) {
      firstCard = this;
      triggerStar("card_flip", this.dataset.name);
      return;
    }

    secondCard = this;
    lockBoard = true;

    checkForMatch();
  }

  function checkForMatch() {
    const isMatch = firstCard.dataset.name === secondCard.dataset.name;

    if (isMatch) {
      firstCard.classList.add("matched");
      secondCard.classList.add("matched");

      matchesFound += 1;

      triggerStar("match_found", firstCard.dataset.name);

      resetTurnCards();

      if (matchesFound === cardItems.length) {
        triggerStar("game_complete");

        setTimeout(function () {
          completeModal.classList.add("show");
        }, 800);

        return;
      }

      setTimeout(function () {
        switchTurn();
      }, 850);
    } else {
      triggerStar("no_match");

      setTimeout(function () {
        firstCard.classList.remove("flipped");
        secondCard.classList.remove("flipped");

        resetTurnCards();
        switchTurn();
      }, 1000);
    }
  }

  function resetTurnCards() {
    firstCard = null;
    secondCard = null;
    lockBoard = false;
  }

  function switchTurn() {
    if (currentTurn === "child") {
      setTurn("parent");
    } else {
      setTurn("child");
    }
  }

  function restartGame() {
    firstCard = null;
    secondCard = null;
    lockBoard = false;
    matchesFound = 0;
    currentTurn = "child";
    starState = freshStarState();

    if (starAudio) {
      starAudio.pause();
      starAudio.currentTime = 0;
    }

    stopMouthAnimation();

    completeModal.classList.remove("show");
    renderCards();
    setTurn("child");

    setTimeout(function () {
      triggerStar("game_start");
    }, 600);
  }

  function playIntroLine(text) {
  fetch("/api/star/tts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text: text
    })
  })
    .then(response => response.json())
    .then(data => {
      if (data.success && data.audio) {
        rememberStarMessage(text);
        playStarAudio(data.audio);

        const waitForAudio = setInterval(function () {
          if (!starState.isStarSpeaking) {
            clearInterval(waitForAudio);
            shrinkIntroToGame();
          }
        }, 300);
      } else {
        console.error(data.error || "Intro TTS failed");
        setTimeout(shrinkIntroToGame, 1800);
      }
    })
    .catch(function (error) {
      console.error("Intro TTS error:", error);
      setTimeout(shrinkIntroToGame, 1800);
    });
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

    setTurn("child");

    setTimeout(function () {
      triggerStar("game_start");
    }, 600);
  }, 1500);
}

function startGameAfterCall() {
  acceptCall.disabled = true;
  declineCall.disabled = true;

  stopRingtone();
  playCallAcceptedSound();

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

renderCards();

setTimeout(startRingtone, 400);

acceptCall.addEventListener("click", startGameAfterCall);

declineCall.addEventListener("click", function () {
  acceptCall.disabled = true;
  declineCall.disabled = true;

  stopRingtone();
  playCallAcceptedSound();

  setTimeout(function () {
    window.location.href = "/dashboard";
  }, 300);
});

restartBtn.addEventListener("click", restartGame);

setInterval(checkQuestionTimeout, 1000);
});