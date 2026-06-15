document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".toy-sorting-page");
  const activityId = Number(page?.dataset.activityId || 4);
  const childName = (page?.dataset.childName || "there").trim() || "there";

  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const introScreen = document.getElementById("introScreen");
  const zoomStage = document.getElementById("zoomStage");

  const roundTitle = document.getElementById("roundTitle");
  const roundText = document.getElementById("roundText");
  const roundNumber = document.getElementById("roundNumber");
  const toysLeftCount = document.getElementById("toysLeftCount");
  const quietStatusText = document.getElementById("quietStatusText");

  const toyGrid = document.getElementById("toyGrid");
  const binGrid = document.getElementById("binGrid");
  const resetRoundBtn = document.getElementById("resetRoundBtn");
  const doneSortingBtn = document.getElementById("doneSortingBtn");

  const librarianVideoTile = document.getElementById("librarianVideoTile");
  const toyWorkerVideoTile = document.getElementById("toyWorkerVideoTile");
  const introLibrarianTile = document.getElementById("introLibrarianTile");
  const introToyWorkerTile = document.getElementById("introToyWorkerTile");

  const micControl = document.getElementById("micControl");
  const hangupButton = document.getElementById("hangupButton");

  const rounds = [
    {
      title: "Sort soft toys and rolling toys",
      text: "Click a toy, then choose the bin where it belongs.",
      intro: "Now can you sort the soft toys and the toys with wheels?",
      bins: [
        { id: "soft", title: "Soft toys", hint: "Stuffed or cuddly toys" },
        { id: "wheels", title: "Toys with wheels", hint: "Cars, trains, and rolling toys" }
      ],
      toys: [
        { id: "teddy", name: "Teddy bear", emoji: "🧸", category: "soft" },
        { id: "doll", name: "Doll", emoji: "🪆", category: "soft" },
        { id: "car", name: "Toy car", emoji: "🚗", category: "wheels" },
        { id: "train", name: "Train", emoji: "🚂", category: "wheels" }
      ],
      firstQuestion: [
        "{child}, which toy should we sort first?",
        "{child}, what toy do you want to start with?",
        "{child}, should we start with a soft toy or a toy with wheels?"
      ],
      workerDuring: [
        "{child}, where should the next toy go?",
        "{child}, which bin are you looking at now?",
        "{child}, what toy should we pick next?"
      ],
      workerDirect: [
        "{child}, should this one go with soft toys or wheels?",
        "{child}, which side should the next toy go on?"
      ]
    },
    {
      title: "Sort building toys and game toys",
      text: "Put each toy with the kind of play it matches.",
      intro: "Now can you sort the building toys and the game toys?",
      bins: [
        { id: "build", title: "Building toys", hint: "Stack, build, or make things" },
        { id: "game", title: "Games and puzzles", hint: "Play on a table or solve" }
      ],
      toys: [
        { id: "blocks", name: "Blocks", emoji: "🧱", category: "build" },
        { id: "robot", name: "Robot", emoji: "🤖", category: "build" },
        { id: "puzzle", name: "Puzzle", emoji: "🧩", category: "game" },
        { id: "boardgame", name: "Board game", emoji: "🎲", category: "game" }
      ],
      firstQuestion: [
        "{child}, which toy should we put away first?",
        "{child}, what should we sort next?",
        "{child}, do you want to start with blocks or a puzzle?"
      ],
      workerDuring: [
        "{child}, does that one look like a building toy?",
        "{child}, where should this toy go?",
        "{child}, what should we pick next?"
      ],
      workerDirect: [
        "{child}, should this go with building toys or games?",
        "{child}, which bin should we use?"
      ]
    },
    {
      title: "Sort pretend toys and active toys",
      text: "Pretend toys go together. Active toys go together.",
      intro: "Now can you sort the pretend toys and the active toys?",
      bins: [
        { id: "pretend", title: "Pretend toys", hint: "Characters and make-believe toys" },
        { id: "active", title: "Active toys", hint: "Throw, bounce, spin, or move" }
      ],
      toys: [
        { id: "figure", name: "Action figure", emoji: "🦸", category: "pretend" },
        { id: "dollhouse", name: "Dollhouse", emoji: "🏠", category: "pretend" },
        { id: "ball", name: "Ball", emoji: "⚽", category: "active" },
        { id: "yoyo", name: "Yo-yo", emoji: "🪀", category: "active" }
      ],
      firstQuestion: [
        "{child}, which toy looks fun to sort first?",
        "{child}, what toy should we start with?",
        "{child}, which bin should we use first?"
      ],
      workerDuring: [
        "{child}, is that one more pretend or active?",
        "{child}, where do you think that toy belongs?",
        "{child}, what should we sort next?"
      ],
      workerDirect: [
        "{child}, should this toy go with pretend toys or active toys?",
        "{child}, which group does this toy belong with?"
      ]
    },
    {
      title: "Sort shelf toys and basket toys",
      text: "Some toys go on the shelf. Some toys go in the basket.",
      intro: "Now can you sort the shelf toys and the basket toys?",
      bins: [
        { id: "shelf", title: "Shelf toys", hint: "Toys we display neatly" },
        { id: "basket", title: "Basket toys", hint: "Toys we toss into a basket" }
      ],
      toys: [
        { id: "robot2", name: "Robot", emoji: "🤖", category: "shelf" },
        { id: "puzzle2", name: "Puzzle", emoji: "🧩", category: "shelf" },
        { id: "ball2", name: "Ball", emoji: "🏀", category: "basket" },
        { id: "blocks2", name: "Blocks", emoji: "🧱", category: "basket" }
      ],
      firstQuestion: [
        "{child}, which toy should we put away first?",
        "{child}, should we start with the shelf or the basket?",
        "{child}, what toy should I help with first?"
      ],
      workerDuring: [
        "{child}, should that go on the shelf or in the basket?",
        "{child}, where should this one go?",
        "{child}, which spot are you choosing?"
      ],
      workerDirect: [
        "{child}, should this one go on the shelf or in the basket?",
        "{child}, which place should we use?"
      ]
    },
    {
      title: "Sort one final shelf",
      text: "One more quick shelf before the next game.",
      intro: "Now can you sort one final shelf?",
      bins: [
        { id: "quiet", title: "Quiet toys", hint: "Calm toys for sitting" },
        { id: "moving", title: "Moving toys", hint: "Toys that roll, bounce, or move" }
      ],
      toys: [
        { id: "booktoy", name: "Story cards", emoji: "📚", category: "quiet" },
        { id: "puzzle3", name: "Puzzle", emoji: "🧩", category: "quiet" },
        { id: "car3", name: "Car", emoji: "🚙", category: "moving" },
        { id: "ball3", name: "Ball", emoji: "🏐", category: "moving" }
      ],
      firstQuestion: [
        "{child}, what should we sort first for the last shelf?",
        "{child}, which toy should go first?",
        "{child}, should we start with a quiet toy or a moving toy?"
      ],
      workerDuring: [
        "{child}, where should the next toy go?",
        "{child}, what toy should we pick next?",
        "{child}, which bin looks right?"
      ],
      workerDirect: [
        "{child}, should this one be quiet or moving?",
        "{child}, which group should this toy join?"
      ]
    }
  ];

  let state = freshState();
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

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.45;

  let ringtoneStarted = false;

  function freshState() {
    return {
      sessionStart: Date.now(),

      roundNumber: 1,
      roundsCompleted: 0,

      selectedToyId: null,
      sortedToyIds: new Set(),
      sortedByBin: {},
      currentRoundStarted: false,

      correctSorts: 0,
      wrongSorts: 0,

      spokenResponses: 0,
      spokenWords: 0,
      silentWindows: 0,

      librarianQuestionsAsked: 0,
      workerQuestionsAsked: 0,
      redirectedQuestions: 0,
      workerDirectResponses: 0,

      isSpeaking: false,
      isListening: false,
      waitingForResponse: false,
      currentQuestion: null,

      recentLines: [],
      guidanceThisRound: 0,
      lastGuidanceAt: 0,

      finalOfferStarted: false,
      finalRoundStarted: false,
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

    if (state.recentLines.length > 18) {
      state.recentLines.shift();
    }
  }

  function pickLine(options) {
    const filled = options.map(fillLine);
    const fresh = filled.filter(line => !state.recentLines.includes(line));
    const choices = fresh.length ? fresh : filled;

    return choices[Math.floor(Math.random() * choices.length)];
  }

  function updateQuietStatus(text) {
    if (quietStatusText) {
      quietStatusText.textContent = text;
    }
  }

  function getRound() {
    return rounds[Math.min(state.roundNumber - 1, rounds.length - 1)];
  }

  function updateRoundDisplay() {
    roundNumber.textContent = String(state.roundNumber);
  }

  function updateToysLeft() {
    const round = getRound();
    const left = round.toys.length - state.sortedToyIds.size;
    toysLeftCount.textContent = `${left} left`;
    doneSortingBtn.disabled = left !== 0;
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
        console.error("Toy sorting speak queue error:", error);
      });

    return speechQueue;
  }

  async function speakNow(actor, text, options = {}) {
    const calmText = cleanLine(text);

    if (!calmText || state.gameCompleted) return;

    rememberLine(calmText);
    updateQuietStatus(actor === "toyworker" ? "Toy Store Worker is talking" : "Librarian is talking");

    const tile = getTile(actor);

    if (tile) tile.classList.add("speaking");

    try {
      state.isSpeaking = true;

      const response = await fetch("/api/toy-sorting-game/tts", {
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
      console.error("Toy sorting TTS error:", error);
      await sleep(750);
    } finally {
      state.isSpeaking = false;

      if (tile) tile.classList.remove("speaking");

      stopMouthAnimation();
      updateQuietStatus("Sorting toys together");
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
      return actor === "toyworker" ? introToyWorkerTile : introLibrarianTile;
    }

    return actor === "toyworker" ? toyWorkerVideoTile : librarianVideoTile;
  }

  function getMouth(actor) {
    if (introIsVisible()) {
      return actor === "toyworker"
        ? document.getElementById("introToyWorkerMouth")
        : document.getElementById("introLibrarianMouth");
    }

    return actor === "toyworker"
      ? document.getElementById("toyWorkerMouth")
      : document.getElementById("librarianMouth");
  }

  function getMouthSrc(actor, size) {
    const safeSize = size || "closed";

    if (actor === "toyworker") {
      const toyWorkerFiles = {
        closed: "/static/images/toyworker-mouth-closed.png",
        small: "/static/images/toyworker-mouth-small.png",
        medium: "/static/images/toyworker-mouth-medium.png",
        wide: "/static/images/toyworker-mouth-wide.png"
      };

      return toyWorkerFiles[safeSize] || toyWorkerFiles.closed;
    }

    const librarianFiles = {
      closed: "/static/images/librarian-mouth-closed.png",
      small: "/static/images/librarian-mouth-small.png",
      medium: "/static/images/librarian-mouth-medium.png",
      wide: "/static/images/librarian-mouth-wide.png"
    };

    return librarianFiles[safeSize] || librarianFiles.closed;
  }

  function setMouth(actor, size, scaleX = 1, scaleY = 1) {
    const mouth = getMouth(actor);
    if (!mouth) return;

    mouth.src = getMouthSrc(actor, size);
    mouth.style.transform = `translateX(-50%) scale(${scaleX}, ${scaleY})`;
  }

  function closeAllMouths() {
    setMouth("librarian", "closed", 1, 1);
    setMouth("toyworker", "closed", 1, 1);
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
      source: options.source || actor
    };

    if (actor === "toyworker") {
      state.workerQuestionsAsked += 1;
    } else {
      state.librarianQuestionsAsked += 1;
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

    const tile = getTile(question.actor || "librarian");

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

    const tile = getTile(question.actor || "librarian");

    if (tile) tile.classList.remove("soft-listening");
    if (micControl) micControl.classList.remove("quiet-listening");

    updateQuietStatus("Sorting toys together");

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
      formData.append("audio", blob, "toy-sorting-response.webm");

      const response = await fetch("/api/toy-sorting-game/transcribe", {
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
      console.error("Toy sorting transcription error:", error);
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

  function isNoText(text) {
    return /\b(no|nope|stop|done|finished|all done)\b/i.test(text);
  }

  async function handleSpeech(transcript, question) {
    const words = countWords(transcript);

    state.spokenResponses += 1;
    state.spokenWords += words;

    if (question.source === "worker-direct") {
      state.workerDirectResponses += 1;
    }

    if (question.source === "worker-redirect") {
      state.redirectedQuestions += 1;
    }

    if (question.intent === "play_again") {
      await handlePlayAgainResponse(transcript);
      return;
    }

    if (question.intent === "final_play_again") {
      await handleFinalPlayAgainResponse(transcript);
      return;
    }

    if (question.source === "worker-direct") {
      await speakNow("toyworker", pickLine([
        "I heard you. Nice choice.",
        "Good choice.",
        "Thanks for telling me.",
        "Okay. I like that idea.",
        "I heard that."
      ]));

      await sleep(250);

      await speakNow("librarian", pickLine([
        "Let's sort that one.",
        "Good idea. Let's keep going.",
        "That works for the toy shelf.",
        "We can use that."
      ]));

      return;
    }

    if (question.source === "worker-redirect") {
      await speakNow("librarian", pickLine([
        "Good idea.",
        "I heard you.",
        "Nice. Let's sort it.",
        "Okay. Let's use that.",
        "That works."
      ]));

      return;
    }

    await speakNow("librarian", pickLine([
      "Good idea.",
      "I heard you.",
      "Nice. Let's sort that.",
      "Okay. Let's keep going.",
      "That sounds good."
    ]));
  }

  async function handleNoSpeech(question) {
    state.silentWindows += 1;

    if (!question) return;

    if (question.intent === "play_again") {
      await speakNow("librarian", "Okay. Let's sort another shelf.");
      continueToNextRound();
      return;
    }

    if (question.intent === "final_play_again") {
      await speakNow("toyworker", "Okay. We can sort one more quick shelf.");
      startFinalRound();
      return;
    }

    if (question.source === "worker-direct") {
      await speakNow("toyworker", "That's okay. We can keep sorting.");
      return;
    }

    await speakNow("librarian", "That's okay. We can keep sorting.");
  }

  async function handlePlayAgainResponse(transcript) {
    if (isNoText(transcript) && state.roundNumber <= 2) {
      await speakNow("librarian", "Okay. We can stop sorting for now.");
      window.location.href = "/dashboard";
      return;
    }

    await speakNow("librarian", "Okay. Let's sort another shelf.");
    continueToNextRound();
  }

  async function handleFinalPlayAgainResponse(transcript) {
    if (isNoText(transcript)) {
      await speakNow("toyworker", "Okay. We can try the next game.");
      await completeAndGoNext();
      return;
    }

    await speakNow("librarian", "Okay. One more shelf together.");
    startFinalRound();
  }

  function renderRound() {
    const round = getRound();

    roundTitle.textContent = round.title;
    roundText.textContent = round.text;

    toyGrid.innerHTML = "";
    binGrid.innerHTML = "";

    state.selectedToyId = null;
    state.sortedToyIds = new Set();
    state.sortedByBin = {};
    state.correctSorts = 0;
    state.wrongSorts = 0;

    round.bins.forEach(bin => {
      state.sortedByBin[bin.id] = [];

      const binButton = document.createElement("button");
      binButton.type = "button";
      binButton.className = "bin-card";
      binButton.dataset.binId = bin.id;
      binButton.innerHTML = `
        <div class="bin-header">
          <div class="bin-icon" aria-hidden="true">
            <img src="/static/images/bucket.png" alt="">
          </div>
          <div class="bin-copy">
            <span class="bin-title">${escapeHtml(bin.title)}</span>
            <span class="bin-hint">${escapeHtml(bin.hint)}</span>
          </div>
        </div>
        <div class="bin-items" id="binItems-${escapeHtml(bin.id)}">
          <span class="empty-bin-text">Put toys here</span>
        </div>
      `;

      binButton.addEventListener("click", function () {
        handleBinClick(bin.id);
      });

      binButton.addEventListener("dragover", function (event) {
        event.preventDefault();
      });

      binButton.addEventListener("dragenter", function (event) {
        event.preventDefault();
        binButton.classList.add("drag-over");
      });

      binButton.addEventListener("dragleave", function () {
        binButton.classList.remove("drag-over");
      });

      binButton.addEventListener("drop", function (event) {
        event.preventDefault();
        binButton.classList.remove("drag-over");
        const toyId = event.dataTransfer ? event.dataTransfer.getData("text/plain") : "";
        if (toyId) {
          handleToyDropIntoBin(toyId, bin.id);
        }
      });

      binGrid.appendChild(binButton);
    });

    round.toys.forEach(toy => {
      const toyButton = document.createElement("button");
      toyButton.type = "button";
      toyButton.className = "toy-card";
      toyButton.dataset.toyId = toy.id;
      toyButton.dataset.category = toy.category;
      toyButton.innerHTML = `
        <span class="toy-emoji">${escapeHtml(toy.emoji)}</span>
        <span class="toy-name">${escapeHtml(toy.name)}</span>
      `;

      toyButton.addEventListener("click", function () {
        handleToyClick(toy.id);
      });

      toyButton.draggable = true;

      toyButton.addEventListener("dragstart", function (event) {
        handleToyClick(toy.id);
        toyButton.classList.add("dragging");

        if (event.dataTransfer) {
          event.dataTransfer.setData("text/plain", toy.id);
          event.dataTransfer.effectAllowed = "move";
        }
      });

      toyButton.addEventListener("dragend", function () {
        toyButton.classList.remove("dragging");
        document.querySelectorAll(".bin-card").forEach(bin => bin.classList.remove("drag-over"));
      });

      toyGrid.appendChild(toyButton);
    });

    updateRoundDisplay();
    updateToysLeft();
    doneSortingBtn.disabled = true;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getToyById(toyId) {
    return getRound().toys.find(toy => toy.id === toyId) || null;
  }

  function getBinById(binId) {
    return getRound().bins.find(bin => bin.id === binId) || null;
  }

  function handleToyClick(toyId) {
    if (state.sortedToyIds.has(toyId) || state.gameCompleted) return;

    state.selectedToyId = toyId;

    document.querySelectorAll(".toy-card").forEach(card => {
      card.classList.toggle("selected", card.dataset.toyId === toyId);
    });

    document.querySelectorAll(".bin-card").forEach(bin => {
      bin.classList.add("ready");
    });

    maybeGuideAfterToySelect(toyId);
  }

  async function maybeGuideAfterToySelect(toyId) {
    if (state.guidanceThisRound >= 1) return;
    if (!canCharacterChimeIn()) return;

    const toy = getToyById(toyId);

    if (!toy) return;

    state.guidanceThisRound += 1;
    state.lastGuidanceAt = Date.now();

    if (state.roundNumber >= 3) {
      await queueSpeak("toyworker", `${childName}, where should the ${toy.name.toLowerCase()} go?`, {
        expectsResponse: true,
        askType: "one_word",
        source: state.roundNumber >= 4 ? "worker-direct" : "worker-redirect",
        responseSeconds: 5.3
      });
      return;
    }

    await queueSpeak("librarian", `${childName}, where should the ${toy.name.toLowerCase()} go?`, {
      expectsResponse: true,
      askType: "one_word",
      source: "librarian",
      responseSeconds: 5.2
    });
  }

  async function handleToyDropIntoBin(toyId, binId) {
    if (state.sortedToyIds.has(toyId) || state.gameCompleted) return;

    state.selectedToyId = toyId;

    document.querySelectorAll(".toy-card").forEach(card => {
      card.classList.toggle("selected", card.dataset.toyId === toyId);
    });

    document.querySelectorAll(".bin-card").forEach(bin => {
      bin.classList.add("ready");
    });

    await handleBinClick(binId);
  }

  async function handleBinClick(binId) {
    if (!state.selectedToyId || state.gameCompleted) return;

    const toy = getToyById(state.selectedToyId);
    const bin = getBinById(binId);

    if (!toy || !bin) return;

    if (toy.category !== binId) {
      state.wrongSorts += 1;

      const card = document.querySelector(`[data-toy-id="${CSS.escape(toy.id)}"]`);

      if (card) {
        card.classList.remove("wrong");
        void card.offsetWidth;
        card.classList.add("wrong");
      }

      await speakNow(state.roundNumber >= 3 ? "toyworker" : "librarian", pickLine([
        "Almost. Try the other bin.",
        "Not quite. Let's try the other side.",
        "Hmm. I think that one belongs in the other bin.",
        "Close. Try the other bin."
      ]));

      return;
    }

    await sortToyIntoBin(toy, bin);
  }

  async function sortToyIntoBin(toy, bin) {
    state.sortedToyIds.add(toy.id);
    state.sortedByBin[bin.id].push(toy.id);
    state.correctSorts += 1;
    state.selectedToyId = null;

    const toyCard = document.querySelector(`[data-toy-id="${CSS.escape(toy.id)}"]`);

    if (toyCard) {
      toyCard.classList.remove("selected");
      toyCard.classList.add("sorted");
    }

    document.querySelectorAll(".bin-card").forEach(binCard => {
      binCard.classList.remove("ready");
    });

    const binItems = document.getElementById(`binItems-${bin.id}`);

    if (binItems) {
      const emptyText = binItems.querySelector(".empty-bin-text");
      if (emptyText) {
        emptyText.remove();
      }

      const chip = document.createElement("span");
      chip.className = "sorted-chip";
      chip.innerHTML = `<span>${escapeHtml(toy.emoji)}</span><span>${escapeHtml(toy.name)}</span>`;
      binItems.appendChild(chip);
    }

    updateToysLeft();

    const isRoundComplete = state.sortedToyIds.size === getRound().toys.length;

    if (isRoundComplete) {
      await speakNow(getSortSpeaker(), pickLine([
        "That shelf is sorted.",
        "Nice sorting.",
        "Everything is in the right spot.",
        "The toys are put away."
      ]));

      return;
    }

    if (state.correctSorts === 2 || state.correctSorts === 3) {
      await maybeCommentAfterCorrectSort(toy, bin);
    }
  }

  function getSortSpeaker() {
    if (state.roundNumber >= 4) return "toyworker";
    if (state.roundNumber >= 3 && state.correctSorts >= 2) return "toyworker";
    return "librarian";
  }

  async function maybeCommentAfterCorrectSort(toy, bin) {
    if (!canCharacterChimeIn()) return;

    state.lastGuidanceAt = Date.now();

    const actor = getSortSpeaker();

    await speakNow(actor, pickLine([
      `Yes, the ${toy.name.toLowerCase()} goes with ${bin.title.toLowerCase()}.`,
      `Good, the ${toy.name.toLowerCase()} fits there.`,
      `That is the right spot for the ${toy.name.toLowerCase()}.`,
      `Nice, that toy belongs there.`
    ]));
  }

  function canCharacterChimeIn() {
    if (state.isSpeaking || state.isListening || state.waitingForResponse || state.gameCompleted) {
      return false;
    }

    if (Date.now() - state.lastGuidanceAt < 6500) {
      return false;
    }

    return true;
  }

  async function beginRound() {
    renderRound();

    const round = getRound();

    state.currentRoundStarted = true;
    state.guidanceThisRound = 0;
    state.lastGuidanceAt = 0;

    updateQuietStatus("Sorting toys together");

    await queueSpeak("librarian", round.intro);

    await sleep(250);

    if (state.roundNumber === 3) {
      await queueSpeak("toyworker", "Do you two want to sort this shelf together?");
      await queueSpeak("librarian", `What do you think, ${childName}?`, {
        expectsResponse: true,
        askType: "open",
        source: "worker-redirect",
        responseSeconds: 5.2
      });
      return;
    }

    if (state.roundNumber >= 4) {
      await queueSpeak("toyworker", pickLine(round.firstQuestion), {
        expectsResponse: true,
        askType: "one_word",
        source: "worker-direct",
        responseSeconds: 5.6
      });
      return;
    }

    await queueSpeak("librarian", pickLine(round.firstQuestion), {
      expectsResponse: true,
      askType: "one_word",
      source: "librarian",
      responseSeconds: 5.2
    });
  }

  async function finishRound() {
    if (state.gameCompleted) return;

    const round = getRound();

    if (state.sortedToyIds.size < round.toys.length) {
      await speakNow(getSortSpeaker(), "Let's sort the rest of the toys first.");
      return;
    }

    doneSortingBtn.disabled = true;
    state.roundsCompleted += 1;

    if (state.finalRoundStarted) {
      await speakNow("toyworker", `Nice sorting, ${childName}. Let's play a different game now.`);
      await completeAndGoNext();
      return;
    }

    if (state.roundNumber === 1) {
      await speakNow("librarian", `Nice sorting, ${childName}.`);
    } else if (state.roundNumber === 2) {
      await speakNow("librarian", `That shelf looks organized, ${childName}.`);
      await speakNow("toyworker", "Thanks for helping with the toys.");
    } else if (state.roundNumber === 3) {
      await speakNow("toyworker", "I liked sorting that shelf with you.");
    } else {
      await speakNow("toyworker", `Thanks for telling me your idea, ${childName}.`);
    }

    if (state.roundNumber >= 4 || state.workerDirectResponses >= 1) {
      await offerFinalPlayAgain();
      return;
    }

    await askPlayAgain();
  }

  async function askPlayAgain() {
    await speakNow("toyworker", "Do you two want to play again?");
    await speakNow("librarian", `What do you think, ${childName}?`, {
      expectsResponse: true,
      askType: "open",
      source: "librarian-redirect",
      intent: "play_again",
      responseSeconds: 5.2
    });
  }

  function continueToNextRound() {
    state.roundNumber += 1;

    setTimeout(function () {
      beginRound();
    }, 650);
  }

  async function offerFinalPlayAgain() {
    if (state.finalOfferStarted) return;

    state.finalOfferStarted = true;

    await speakNow("toyworker", `Do you want to sort one more shelf before we play a different game, ${childName}?`, {
      expectsResponse: true,
      askType: "open",
      source: "worker-direct",
      intent: "final_play_again",
      responseSeconds: 5.8
    });
  }

  function startFinalRound() {
    if (state.finalRoundStarted) return;

    state.finalRoundStarted = true;
    state.roundNumber += 1;

    setTimeout(function () {
      beginRound();
    }, 650);
  }

  async function completeAndGoNext() {
    if (state.gameCompleted) return;

    state.gameCompleted = true;

    const minutesPlayed = Math.max(0, (Date.now() - state.sessionStart) / 60000);

    try {
      const response = await fetch("/api/toy-sorting-game/complete", {
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
          rounds_completed: state.roundsCompleted,
          worker_direct_responses: state.workerDirectResponses,
          correct_sorts: state.correctSorts,
          wrong_sorts: state.wrongSorts
        })
      });

      const data = await response.json();

      if (data.success && data.next_activity_id) {
        window.location.href = `/activity/${data.next_activity_id}`;
        return;
      }
    } catch (error) {
      console.error("Could not save toy sorting completion:", error);
    }

    window.location.href = "/dashboard";
  }

  async function playIntro() {
    await queueSpeak("librarian", "Hi again. It's me, the Librarian. Today we're going to sort toys together.");
    await queueSpeak("librarian", "I brought someone who knows a lot about toys.");
    await queueSpeak("toyworker", "Hi. I'm the Toy Store Worker. I can help with the toy shelf.");
    await queueSpeak("librarian", "I'll share my screen so we can start sorting.");
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
      beginRound();
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

  function resetRound() {
    renderRound();
    queueSpeak("librarian", "Okay. We can sort this shelf again.");
  }

  function cleanupMedia() {
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

  resetRoundBtn.addEventListener("click", resetRound);
  doneSortingBtn.addEventListener("click", finishRound);

  if (hangupButton) {
    hangupButton.addEventListener("click", function () {
      cleanupMedia();
      window.location.href = "/dashboard";
    });
  }

  window.addEventListener("beforeunload", cleanupMedia);

  updateRoundDisplay();
  doneSortingBtn.disabled = true;
  closeAllMouths();

  setTimeout(startRingtone, 400);
});
