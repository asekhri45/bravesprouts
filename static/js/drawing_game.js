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

  const drawingPrompts = [
    {
      title: "Draw a flower",
      text: "A simple flower, any color.",
      intro: "Let's start with a flower.",
      firstQuestion: [
        "What color do you want to start with, {child}?",
        "{child}, should we start with the stem or the petals?",
        "Which part should we draw first, {child}?"
      ],
      starDuring: [
        "What color are you using now, {child}?",
        "Are you adding petals first, {child}?",
        "{child}, what should we add next?"
      ],
      librarianRedirect: [
        "Do you two want to add leaves to the flower?",
        "Should this flower have a big stem or a little stem?",
        "Do you think the flower should have more petals?"
      ],
      starRedirect: [
        "What do you think, {child}?",
        "{child}, what sounds good to you?",
        "Should we try that, {child}?",
        "What would you pick, {child}?"
      ],
      librarianDirect: [
        "What should we add to the flower, {child}?",
        "{child}, what color should the flower be?",
        "Should we add leaves or more petals, {child}?"
      ],
      doneLines: [
        "Nice flower, {child}.",
        "That flower looks sweet, {child}.",
        "I like that flower, {child}."
      ]
    },
    {
      title: "Draw a sun",
      text: "A bright sun in the sky.",
      intro: "Now let's draw a sun.",
      firstQuestion: [
        "Should the sun be big or small, {child}?",
        "{child}, what color should the sun be?",
        "Where should we put the sun, {child}?"
      ],
      starDuring: [
        "Are you adding sun rays, {child}?",
        "{child}, should we add clouds too?",
        "What should go near the sun, {child}?"
      ],
      librarianRedirect: [
        "Do you two want to add clouds near the sun?",
        "Should the sun have a happy face?",
        "Do you think the sky should have something else in it?"
      ],
      starRedirect: [
        "What do you think, {child}?",
        "{child}, what would you choose?",
        "Should we add that, {child}?",
        "What sounds best to you, {child}?"
      ],
      librarianDirect: [
        "{child}, should the sun have clouds around it?",
        "What should we add near the sun, {child}?",
        "Should the sun be smiling, {child}?"
      ],
      doneLines: [
        "That is a bright sun, {child}.",
        "Nice sun drawing, {child}.",
        "I like that sunny picture, {child}."
      ]
    },
    {
      title: "Draw a tree",
      text: "A tree with leaves, branches, or fruit.",
      intro: "Now let's draw a tree.",
      firstQuestion: [
        "What should we start with, {child}?",
        "{child}, should the tree be tall or short?",
        "Should we draw the trunk first, {child}?"
      ],
      starDuring: [
        "Are you adding leaves now, {child}?",
        "{child}, should we add apples or flowers?",
        "What should go next on the tree, {child}?"
      ],
      librarianRedirect: [
        "Do you two want to add apples to the tree?",
        "Should this tree have lots of leaves?",
        "Do you think an animal should be near the tree?"
      ],
      starRedirect: [
        "What do you think, {child}?",
        "{child}, would you add that?",
        "Should we try that idea, {child}?",
        "What would you like, {child}?"
      ],
      librarianDirect: [
        "What should be on the tree, {child}?",
        "{child}, should we add apples or leaves?",
        "Should an animal sit near the tree, {child}?"
      ],
      doneLines: [
        "Nice tree, {child}.",
        "That tree looks good, {child}.",
        "I like that tree drawing, {child}."
      ]
    },
    {
      title: "Draw a dog",
      text: "A simple dog with ears, legs, and a tail.",
      intro: "Now let's draw a dog.",
      firstQuestion: [
        "What part should we draw first, {child}?",
        "{child}, should the dog have floppy ears?",
        "What color should the dog be, {child}?"
      ],
      starDuring: [
        "Are you adding ears or a tail, {child}?",
        "{child}, should the dog be sitting or standing?",
        "What should we add next, {child}?"
      ],
      librarianRedirect: [
        "Do you two want to give the dog a collar?",
        "Should the dog have a long tail or a short tail?",
        "Do you think the dog should be sitting?"
      ],
      starRedirect: [
        "What do you think, {child}?",
        "{child}, which one should we pick?",
        "Should we do that, {child}?",
        "What sounds good to you, {child}?"
      ],
      librarianDirect: [
        "{child}, should the dog have a collar?",
        "What should the dog look like, {child}?",
        "Should the dog have long ears or short ears, {child}?"
      ],
      doneLines: [
        "That dog is cute, {child}.",
        "Nice dog drawing, {child}.",
        "I like that dog, {child}."
      ]
    },
    {
      title: "Draw a book",
      text: "A simple book, open or closed.",
      intro: "Now let's draw one final book.",
      firstQuestion: [
        "Should the book be open or closed, {child}?",
        "{child}, what color should the book be?",
        "What should we draw first on the book, {child}?"
      ],
      starDuring: [
        "Are you adding pages, {child}?",
        "{child}, should we add a title?",
        "What should go on the book, {child}?"
      ],
      librarianRedirect: [
        "Do you two want to put a star on the book?",
        "Should the book be open?",
        "Do you think the book needs a title?"
      ],
      starRedirect: [
        "What do you think, {child}?",
        "{child}, what would you choose?",
        "Should we add that, {child}?",
        "What sounds nice to you, {child}?"
      ],
      librarianDirect: [
        "Should the book be open or closed, {child}?",
        "{child}, what color should the book be?",
        "What should we put on the book, {child}?"
      ],
      doneLines: [
        "Nice book, {child}.",
        "That book looks good, {child}.",
        "I like that book drawing, {child}."
      ]
    }
  ];

  let state = freshState();

  let currentTool = "pen";
  let currentColor = "#7c3aed";
  let isDrawing = false;
  let lastPoint = null;
  let hasDrawnThisRound = false;
  let strokeCountThisRound = 0;

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

      spokenResponses: 0,
      spokenWords: 0,
      silentWindows: 0,

      starQuestionsAsked: 0,
      librarianQuestionsAsked: 0,
      redirectedQuestions: 0,
      librarianDirectResponses: 0,

      isSpeaking: false,
      isListening: false,
      waitingForResponse: false,
      currentQuestion: null,

      recentLines: [],

      drawingQuestionsThisRound: 0,
      quietCommentsThisRound: 0,
      librarianCommentsThisRound: 0,
      lastGuidanceAt: 0,

      doneReminderGivenThisRound: false,
      totalDoneReminders: 0,
      lastDoneReminderAt: 0,

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

  function pickRedirectLine(prompt) {
    const redirectOptions = prompt.starRedirect || [
      "What do you think, {child}?",
      "{child}, what sounds good to you?",
      "What would you pick, {child}?",
      "Should we try that, {child}?",
      "Which one should we choose, {child}?"
    ];

    return pickLine(redirectOptions);
  }

  function pickLibrarianCommentLine() {
    return pickLine([
      "That is looking good so far.",
      "Your drawing is coming along nicely.",
      "I like the way your picture is starting.",
      "That is a great start.",
      "You are doing a nice job with this drawing.",
      "I like the colors you are using.",
      "This is turning into a nice picture.",
      "You are adding some good details.",
      "That looks very creative.",
      "You are a careful artist.",
      "I like how your artwork is coming together.",
      "That is a lovely drawing so far.",
      "Your artwork is looking great.",
      "You are a great artist.",
      "That picture is coming along great.",
      "I like what you are making."
    ]);
  }

  function maybeRemindDoneButton(force = false) {
    if (!hasDrawnThisRound) return false;
    if (state.gameCompleted) return false;
    if (state.doneReminderGivenThisRound) return false;
    if (state.totalDoneReminders >= 3) return false;
    if (state.isSpeaking || state.isListening || state.waitingForResponse) return false;

    const now = Date.now();

    if (!force && strokeCountThisRound < 10) return false;
    if (!force && now - state.lastGuidanceAt < 4500) return false;
    if (!force && now - state.lastDoneReminderAt < 25000) return false;

    state.doneReminderGivenThisRound = true;
    state.totalDoneReminders += 1;
    state.lastDoneReminderAt = now;
    state.lastGuidanceAt = now;

    queueSpeak("star", pickLine([
      "When you're finished, press the Done Drawing button.",
      "{child}, when your drawing is done, you can press Done Drawing.",
      "Whenever you're finished, the Done Drawing button will move us to the next part.",
      "When this picture feels finished, press Done Drawing."
    ]));

    return true;
  }

  function updateQuietStatus(text) {
    if (quietStatusText) {
      quietStatusText.textContent = text;
    }
  }

  function getPrompt() {
    return drawingPrompts[Math.min(state.roundNumber - 1, drawingPrompts.length - 1)];
  }

  function setPrompt(prompt) {
    promptTitle.textContent = prompt.title;
    promptText.textContent = prompt.text;
  }

  function updateRoundDisplay() {
    roundNumber.textContent = String(state.roundNumber);
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
    const calmText = cleanLine(text);

    if (!calmText || state.gameCompleted) return;

    rememberLine(calmText);
    updateQuietStatus(actor === "librarian" ? "Librarian is talking" : "Star is talking");

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
      return actor === "librarian" ? introLibrarianTile : introStarTile;
    }

    return actor === "librarian" ? librarianVideoTile : starVideoTile;
  }

  function getMouth(actor) {
    if (introIsVisible()) {
      return actor === "librarian"
        ? document.getElementById("introLibrarianMouth")
        : document.getElementById("introStarMouth");
    }

    return actor === "librarian"
      ? document.getElementById("librarianMouth")
      : document.getElementById("starMouth");
  }

  function getMouthSrc(actor, size) {
    const safeSize = size || "closed";

    if (actor === "librarian") {
      const librarianFiles = {
        closed: "/static/images/librarian-mouth-closed.png",
        small: "/static/images/librarian-mouth-small.png",
        medium: "/static/images/librarian-mouth-medium.png",
        wide: "/static/images/librarian-mouth-wide.png"
      };

      return librarianFiles[safeSize] || librarianFiles.closed;
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
    setMouth("librarian", "closed", 1, 1);
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

    if (actor === "librarian") {
      state.librarianQuestionsAsked += 1;
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

    updateQuietStatus("Drawing together");

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

  function isNoText(text) {
    return /\b(no|nope|stop|done|finished|all done)\b/i.test(text);
  }

  async function handleSpeech(transcript, question) {
    const words = countWords(transcript);

    state.spokenResponses += 1;
    state.spokenWords += words;

    if (question.source === "librarian-direct") {
      state.librarianDirectResponses += 1;
    }

    if (question.source === "librarian-redirect") {
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

    if (question.source === "librarian-direct") {
      await speakNow("librarian", pickLine([
        "Nice choice.",
        "Good choice.",
        "Thanks for telling me.",
        "Okay. I like that idea.",
        "That sounds good.",
        "That is a good idea."
      ]));

      await sleep(250);

      await speakNow("star", pickLine([
        "Let's add that.",
        "I'll draw that with you.",
        "That works for our drawing.",
        "Good idea. Let's keep going.",
        "That will look nice in the picture."
      ]));

      return;
    }

    if (question.source === "librarian-redirect") {
      await speakNow("star", pickLine([
        "Good idea.",
        "Nice. Let's add that.",
        "Okay. Let's use that.",
        "That works.",
        "That sounds good.",
        "Let's try that."
      ]));

      return;
    }

    await speakNow("star", pickLine([
      "Good idea.",
      "Nice. Let's keep drawing.",
      "Okay. Let's add that.",
      "That sounds good.",
      "Let's try that.",
      "That will look nice."
    ]));
  }

  async function handleNoSpeech(question) {
    state.silentWindows += 1;

    if (!question) return;

    if (question.intent === "play_again") {
      await speakNow("star", "Okay. Let's try another drawing.");
      continueToNextRound();
      return;
    }

    if (question.intent === "final_play_again") {
      await speakNow("librarian", "Okay. We can do one more quick drawing.");
      startFinalRound();
      return;
    }

    if (question.source === "librarian-direct") {
      await speakNow("librarian", "That's okay. We can keep drawing.");
      return;
    }

    await speakNow("star", "That's okay. We can keep drawing.");
  }

  async function handlePlayAgainResponse(transcript) {
    if (isNoText(transcript) && state.roundNumber <= 2) {
      await speakNow("star", "Okay. We can stop drawing for now.");
      window.location.href = "/dashboard";
      return;
    }

    await speakNow("star", "Okay. Let's try another drawing.");
    continueToNextRound();
  }

  async function handleFinalPlayAgainResponse(transcript) {
    if (isNoText(transcript)) {
      await speakNow("librarian", "Okay. We can try the next game.");
      await completeAndGoNext();
      return;
    }

    await speakNow("star", "Okay. One more drawing together.");
    startFinalRound();
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
    hasDrawnThisRound = true;
    doneDrawingBtn.disabled = false;
    lastPoint = getCanvasPoint(event);

    maybeReactToDrawingStart();

    setTimeout(function () {
      maybeRemindDoneButton();
    }, 5500);
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
    strokeCountThisRound += 1;

    maybeReactDuringDrawing();
    maybeRemindDoneButton();
  }

  function stopDrawing() {
    isDrawing = false;
    lastPoint = null;
  }

  function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    hasDrawnThisRound = false;
    strokeCountThisRound = 0;
    doneDrawingBtn.disabled = true;
  }

  function setTool(tool) {
    currentTool = tool;

    toolButtons.forEach(button => {
      button.classList.toggle("active", button.dataset.tool === tool);
    });
  }

  function setColor(color) {
    currentColor = color;
    currentTool = "pen";

    colorButtons.forEach(button => {
      button.classList.toggle("active", button.dataset.color === color);
    });

    setTool("pen");
  }

  function canCharacterChimeIn() {
    if (state.isSpeaking || state.isListening || state.waitingForResponse || state.gameCompleted) {
      return false;
    }

    if (Date.now() - state.lastGuidanceAt < 9000) {
      return false;
    }

    return true;
  }

  function maybeReactToDrawingStart() {
    if (state.quietCommentsThisRound > 0) return;
    if (!canCharacterChimeIn()) return;

    state.quietCommentsThisRound += 1;
    state.lastGuidanceAt = Date.now();

    queueSpeak("star", pickLine([
      "I'm starting with you.",
      "I'll draw along with you.",
      "Start anywhere you want.",
      "I'm watching what you add first."
    ]));
  }

  function maybeReactDuringDrawing() {
    if (strokeCountThisRound < 12) return;
    if (!canCharacterChimeIn()) return;

    const prompt = getPrompt();
    const guidanceCount = state.drawingQuestionsThisRound + state.librarianCommentsThisRound;

    if (guidanceCount >= 2) return;

    /*
      Smooth progression:
      - Every round: Librarian can first compliment the child's drawing.
      - Rounds 1–3: Star handles during-drawing questions.
      - Round 4+: Librarian direct questions happen at round start after comments.
    */
    if (state.librarianCommentsThisRound < 1) {
      state.librarianCommentsThisRound += 1;
      state.lastGuidanceAt = Date.now();

      queueSpeak("librarian", pickLibrarianCommentLine());
      return;
    }

    if (state.drawingQuestionsThisRound >= 1) return;

    state.drawingQuestionsThisRound += 1;
    state.lastGuidanceAt = Date.now();

    queueSpeak("star", pickLine(prompt.starDuring), {
      expectsResponse: true,
      askType: "one_word",
      source: "star",
      responseSeconds: 5.2
    });
  }

  async function beginRound() {
    const prompt = getPrompt();

    updateRoundDisplay();
    setPrompt(prompt);
    clearCanvas();

    state.drawingQuestionsThisRound = 0;
    state.quietCommentsThisRound = 0;
    state.librarianCommentsThisRound = 0;
    state.doneReminderGivenThisRound = false;
    state.lastGuidanceAt = 0;

    updateQuietStatus("Drawing together");

    await queueSpeak("librarian", prompt.intro);
    await sleep(250);

    /*
      Round 1:
      Star is the only one asking the child.
    */
    if (state.roundNumber === 1) {
      await queueSpeak("star", pickLine(prompt.firstQuestion), {
        expectsResponse: true,
        askType: "one_word",
        source: "star",
        responseSeconds: 5.2
      });
      return;
    }

    /*
      Round 2:
      Librarian starts becoming socially present, but only with a soft comment.
      Star still asks the child.
    */
    if (state.roundNumber === 2) {
      await queueSpeak("librarian", pickLibrarianCommentLine());
      await sleep(200);

      await queueSpeak("star", pickLine(prompt.firstQuestion), {
        expectsResponse: true,
        askType: "one_word",
        source: "star",
        responseSeconds: 5.2
      });
      return;
    }

    /*
      Round 3:
      Librarian comments first, then asks the pair/group.
      Star redirects to the child with varied phrasing.
    */
    if (state.roundNumber === 3) {
      await queueSpeak("librarian", pickLibrarianCommentLine());
      await sleep(200);

      await queueSpeak("librarian", pickLine(prompt.librarianRedirect));
      await queueSpeak("star", pickRedirectLine(prompt), {
        expectsResponse: true,
        askType: "open",
        source: "librarian-redirect",
        responseSeconds: 5.2
      });
      return;
    }

    /*
      Round 4+:
      Librarian gives a soft comment first, then asks one simple direct question.
      Star frames it gently so it does not feel sudden.
    */
    await queueSpeak("librarian", pickLibrarianCommentLine());
    await sleep(200);

    await queueSpeak("star", pickLine([
      "The Librarian can ask one small question now.",
      "{child}, the Librarian can ask you one easy question now.",
      "You can answer the Librarian with just one word if you want."
    ]));

    await queueSpeak("librarian", pickLine(prompt.librarianDirect), {
      expectsResponse: true,
      askType: "one_word",
      source: "librarian-direct",
      responseSeconds: 5.6
    });
  }

  async function finishRound() {
    if (state.gameCompleted) return;

    if (!hasDrawnThisRound) {
      await speakNow("star", "You can draw a little bit first.");
      return;
    }

    doneDrawingBtn.disabled = true;

    state.roundsCompleted += 1;

    const prompt = getPrompt();

    if (state.finalRoundStarted) {
      await speakNow("librarian", pickLine(prompt.doneLines));
      await speakNow("star", "That was a nice last drawing.");
      await completeAndGoNext();
      return;
    }

    await speakNow("librarian", pickLine(prompt.doneLines));

    if (state.roundNumber >= 4) {
      await offerFinalPlayAgain();
      return;
    }

    await askPlayAgain();
  }

  async function askPlayAgain() {
    const prompt = getPrompt();

    await speakNow("librarian", pickLine([
      "Do you two want to draw another one?",
      "Should we try one more drawing?",
      "Do you want to keep drawing together?"
    ]));

    await speakNow("star", pickRedirectLine(prompt), {
      expectsResponse: true,
      askType: "open",
      source: "star-redirect",
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

    await speakNow("librarian", pickLine([
      "Do you want to draw one more before we play a different game, {child}?",
      "{child}, do you want one more drawing before the next game?",
      "Should we draw one final picture before the next game, {child}?"
    ]), {
      expectsResponse: true,
      askType: "open",
      source: "librarian-direct",
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
          rounds_completed: state.roundsCompleted,
          librarian_direct_responses: state.librarianDirectResponses
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
    await queueSpeak("star", "Hey again. It's me, Star. We're going to draw together today.");
    await queueSpeak("librarian", "Hi. I'm the Librarian. I'll pick what we draw, and Star can draw with you.");
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
      setColor(button.dataset.color);
    });
  });

  clearCanvasBtn.addEventListener("click", clearCanvas);
  doneDrawingBtn.addEventListener("click", finishRound);

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
  updateRoundDisplay();
  doneDrawingBtn.disabled = true;
  closeAllMouths();

  setTimeout(startRingtone, 400);
});