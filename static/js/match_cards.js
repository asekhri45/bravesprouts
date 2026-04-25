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

  function shuffle(array) {
    const copy = [...array];

    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }

    return copy;
  }

  function setTurn(turn) {
    currentTurn = turn;

    if (turn === "child") {
      childTurnCard.classList.add("active");
      parentTurnCard.classList.remove("active");
      updateStarMessage("It’s your turn now!", "Pick two cards!");
    } else {
      parentTurnCard.classList.add("active");
      childTurnCard.classList.remove("active");
      updateStarMessage("Parent’s turn!", "Let’s watch together!");
    }
  }

  function updateStarMessage(title, message) {
    starBubble.innerHTML = `
      <h2>${title}</h2>
      <p>${message}</p>
    `;
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
      updateStarMessage("Nice choice!", "Pick one more card!");
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

      updateStarMessage("You found a match!", "Great job!");

      resetTurnCards();

      if (matchesFound === cardItems.length) {
        setTimeout(() => {
          completeModal.classList.add("show");
        }, 600);
        return;
      }

      setTimeout(() => {
        switchTurn();
      }, 850);
    } else {
      updateStarMessage("So close!", "Let’s remember those cards!");

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
    completeModal.classList.remove("show");
    setTurn("child");
    renderCards();
  }

  restartBtn.addEventListener("click", restartGame);

  setTurn("child");
  renderCards();
});