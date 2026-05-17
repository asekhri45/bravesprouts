document.addEventListener("DOMContentLoaded", function () {
  const cardGrid = document.getElementById("cardGrid");
  const childTurnCard = document.getElementById("childTurnCard");
  const parentTurnCard = document.getElementById("parentTurnCard");
  const starBubble = document.getElementById("starBubble");
  const completeModal = document.getElementById("completeModal");
  const restartBtn = document.getElementById("restartBtn");

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

  let starState = {
    sessionStart: Date.now(),
    stageOffsetMinutes: 0,

    lastStarTime: 0,
    isStarSpeaking: false,

    lastMessageWasQuestion: false,
    waitingForResponse: false,
    questionAskedAt: null,
    unansweredQuestions: 0,

    starMessagesPlayed: 0,
    starQuestionsAsked: 0,
    recentStarMessages: []
  };

  function shuffle(array) {
    const copy = [...array];

    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }

    return copy;
  }

  function updateStarMessage(title, message) {
    starBubble.innerHTML = `
      <h2>${title}</h2>
      <p>${message}</p>
    `;
  }

  function rememberStarMessage(message) {
    starState.recentStarMessages.push(message);

    if (starState.recentStarMessages.length > 12) {
      starState.recentStarMessages.shift();
    }
  }

  function getRealMinutesPlayed() {
    return (Date.now() - starState.sessionStart) / 60000;
  }

  function getEffectiveMinutesPlayed() {
    const realMinutes = getRealMinutesPlayed();
    return Math.max(0, realMinutes - starState.stageOffsetMinutes);
  }

  function getStarStage() {
    const minutes = getEffectiveMinutesPlayed();

    if (minutes < 10) return 0;
    if (minutes < 20) return 1;
    return 2;
  }

  function resetStarProgression() {
    starState.stageOffsetMinutes = getRealMinutesPlayed();
    starState.waitingForResponse = false;
    starState.lastMessageWasQuestion = false;
    starState.questionAskedAt = null;
    starState.unansweredQuestions = 0;
  }

  function checkQuestionTimeout() {
    if (!starState.waitingForResponse) return;

    const timeSinceQuestion = Date.now() - starState.questionAskedAt;

    if (timeSinceQuestion > 12000) {
      resetStarProgression();
    }
  }

  function canStarSpeak() {
    checkQuestionTimeout();

    const now = Date.now();
    const stage = getStarStage();

    let cooldown = 9000;

    if (stage === 0) cooldown = 10000;
    if (stage === 1) cooldown = 9000;
    if (stage === 2) cooldown = 8000;

    if (starState.isStarSpeaking) return false;
    if (now - starState.lastStarTime < cooldown) return false;

    return true;
  }

  function shouldAskQuestion() {
    const stage = getStarStage();

    if (stage === 0) return false;
    if (starState.waitingForResponse) return false;

    const random = Math.random();

    if (stage === 1) return random < 0.22;
    if (stage === 2) return random < 0.32;

    return false;
  }

  function shouldStarReact(eventType) {
    if (!canStarSpeak()) return false;

    const stage = getStarStage();
    const random = Math.random();

    if (eventType === "game_complete") return true;
    if (eventType === "match_found") return true;

    if (stage === 0) return random < 0.65;
    if (stage === 1) return random < 0.7;

    return random < 0.75;
  }

  async function triggerStar(eventType, cardName = "") {
    if (!shouldStarReact(eventType)) return;

    const askQuestion = shouldAskQuestion();
    const stage = getStarStage();

    try {
      starState.lastStarTime = Date.now();
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

          minutes_played: getEffectiveMinutesPlayed(),
          stage: stage,
          should_ask_question: askQuestion,
          unanswered_questions: starState.unansweredQuestions,
          star_messages_played: starState.starMessagesPlayed,
          star_questions_asked: starState.starQuestionsAsked,
          recent_star_messages: starState.recentStarMessages
        })
      });

      const data = await response.json();

      console.log("Star data:", data);

      if (!data.success) {
        starState.isStarSpeaking = false;
        return;
      }

      updateStarMessage("Star", data.message);
      rememberStarMessage(data.message);

      starState.starMessagesPlayed += 1;

      if (askQuestion || data.asked_question) {
        starState.lastMessageWasQuestion = true;
        starState.waitingForResponse = true;
        starState.questionAskedAt = Date.now();
        starState.starQuestionsAsked += 1;
      } else {
        starState.lastMessageWasQuestion = false;
      }

      if (!data.audio) {
        starState.isStarSpeaking = false;
        return;
      }

      if (starAudio) {
        starAudio.pause();
        starAudio.currentTime = 0;
      }

      starAudio = new Audio(data.audio);
      starAudio.volume = 1.0;
      starAudio.playbackRate = 1.15;

      starAudio.addEventListener("ended", function () {
        starState.isStarSpeaking = false;
      });

      starAudio.addEventListener("error", function () {
        console.error("Audio element error:", starAudio.error);
        starState.isStarSpeaking = false;
      });

      starAudio.play()
        .then(() => {
          console.log("Star audio played");
        })
        .catch((error) => {
          console.error("Audio blocked/failed:", error);
          starState.isStarSpeaking = false;
        });

    } catch (error) {
      console.error("Star error:", error);
      starState.isStarSpeaking = false;
    }
  }

  function setTurn(turn) {
    currentTurn = turn;

    if (turn === "child") {
      childTurnCard.classList.add("active");
      parentTurnCard.classList.remove("active");
      updateStarMessage("Your turn!", "Pick two cards!");
    } else {
      parentTurnCard.classList.add("active");
      childTurnCard.classList.remove("active");
      updateStarMessage("Parent’s turn!", "Pick two cards!");
    }
  }

  function createDeck() {
    const pairedCards = [...cardItems, ...cardItems];
    return shuffle(pairedCards);
  }

  function renderCards() {
    cardGrid.innerHTML = "";

    const deck = createDeck();

    deck.forEach((item, index) => {
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

        setTimeout(() => {
          completeModal.classList.add("show");
        }, 600);

        return;
      }

      setTimeout(() => {
        switchTurn();
      }, 850);
    } else {
      triggerStar("no_match");

      setTimeout(() => {
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

    starState = {
      sessionStart: Date.now(),
      stageOffsetMinutes: 0,

      lastStarTime: 0,
      isStarSpeaking: false,

      lastMessageWasQuestion: false,
      waitingForResponse: false,
      questionAskedAt: null,
      unansweredQuestions: 0,

      starMessagesPlayed: 0,
      starQuestionsAsked: 0,
      recentStarMessages: []
    };

    if (starAudio) {
      starAudio.pause();
      starAudio.currentTime = 0;
    }

    completeModal.classList.remove("show");
    setTurn("child");
    renderCards();
  }

  restartBtn.addEventListener("click", restartGame);

  setInterval(checkQuestionTimeout, 1000);

  renderCards();
  setTurn("child");
});