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
      intro: "Now can you draw a flower?",
      firstQuestion: [
        "{child}, what color are you starting with?",
        "{child}, which part are you starting with?",
        "{child}, have you drawn a flower before?"
      ],
      starDuring: [
        "{child}, what color are you using now?",
        "{child}, are you drawing the petals first?",
        "{child}, what should we add next?"
      ],
      librarianDirect: [
        "{child}, what should we add to the flower?",
        "{child}, what color should the flower be?"
      ],
      doneLines: [
        "Nice flower, {child}.",
        "That flower looks sweet, {child}.",
        "I like that flower, {child}."
      ]
    },
    {
      title: "Draw a silly face",
      text: "A happy, silly, or surprised face.",
      intro: "Now can you draw a silly face?",
      firstQuestion: [
        "{child}, what part should we start with?",
        "{child}, should the face be happy or surprised?",
        "{child}, what color are you choosing first?"
      ],
      starDuring: [
        "{child}, what kind of mouth are you drawing?",
        "{child}, should we add hair or a hat?",
        "{child}, what should we draw next?"
      ],
      librarianDirect: [
        "{child}, should the face have a hat or hair?",
        "{child}, what should the face look like?"
      ],
      doneLines: [
        "That is a fun face, {child}.",
        "I like that silly face, {child}.",
        "Nice silly face, {child}."
      ]
    },
    {
      title: "Draw a book cover",
      text: "A pretend cover for a storybook.",
      intro: "Now can you draw a book cover?",
      firstQuestion: [
        "{child}, what should be on the cover?",
        "{child}, what color should we start with?",
        "{child}, should it be a funny book or a cozy book?"
      ],
      starDuring: [
        "{child}, what detail are you adding now?",
        "{child}, should we add a star or a heart?",
        "{child}, what should go in the middle?"
      ],
      librarianDirect: [
        "{child}, should the book cover have a star or a heart?",
        "{child}, what should we add to the book cover?"
      ],
      doneLines: [
        "That looks like a good book cover, {child}.",
        "Nice book cover, {child}.",
        "I like that story idea, {child}."
      ]
    },
    {
      title: "Draw a tiny animal",
      text: "A cat, dog, bunny, bird, or any animal.",
      intro: "Now can you draw a tiny animal?",
      firstQuestion: [
        "{child}, what animal are you thinking of?",
        "{child}, what color should the animal be?",
        "{child}, what part should we start with?"
      ],
      starDuring: [
        "{child}, are you adding ears or a tail?",
        "{child}, what should we draw next?",
        "{child}, what color are you using now?"
      ],
      librarianDirect: [
        "{child}, what animal did you choose?",
        "{child}, should the animal have ears or a tail?"
      ],
      doneLines: [
        "That animal is cute, {child}.",
        "Nice animal drawing, {child}.",
        "I like that tiny animal, {child}."
      ]
    },
    {
      title: "Draw one final picture",
      text: "Anything you want before the next game.",
      intro: "Now can you draw one final picture?",
      firstQuestion: [
        "{child}, what do you want to draw for the last one?",
        "{child}, what color should we start with?",
        "{child}, what part should we start with?"
      ],
      starDuring: [
        "{child}, what are you adding now?",
        "{child}, what should go next?",
        "{child}, what color are you using now?"
      ],
      librarianDirect: [
        "{child}, what are you drawing?",
        "{child}, what should we add before the next game?"
      ],
      doneLines: [
        "Nice final drawing, {child}.",
        "That was a good last picture, {child}.",
        "I liked drawing that with you, {child}."
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

  /*
    Queue is only used for planned lines.
    Response lines use speakNow directly.
    This avoids the old deadlock where the response handler waited on the same queue
    that was waiting for the response handler to finish.
  */
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
        wide: "/static/images/librarian-mouth-wide-open.png"
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
        "I heard you. Nice choice.",
        "Good choice.",
        "Thanks for telling me.",
        "Okay. I like that idea.",
        "I heard that."
      ]));

      await sleep(250);

      await speakNow("star", pickLine([
        "Let's add that.",
        "I'll draw that with you.",
        "That works for our drawing.",
        "Good idea. Let's keep going."
      ]));

      return;
    }

    if (question.source === "librarian-redirect") {
      await speakNow("star", pickLine([
        "Good idea.",
        "I heard you.",
        "Nice. Let's add that.",
        "Okay. Let's use that.",
        "That works."
      ]));

      return;
    }

    await speakNow("star", pickLine([
      "Good idea.",
      "I heard you.",
      "Nice. Let's keep drawing.",
      "Okay. Let's add that.",
      "That sounds good."
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

    // Silence is allowed, but the game should not feel dead.
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
    if (strokeCountThisRound < 18) return;
    if (state.drawingQuestionsThisRound >= 2) return;
    if (!canCharacterChimeIn()) return;

    state.drawingQuestionsThisRound += 1;
    state.lastGuidanceAt = Date.now();

    const prompt = getPrompt();

    if (state.roundNumber >= 4 && state.drawingQuestionsThisRound === 2) {
      queueSpeak("librarian", pickLine(prompt.librarianDirect), {
        expectsResponse: true,
        askType: "one_word",
        source: "librarian-direct",
        responseSeconds: 5.5
      });
      return;
    }

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
    state.lastGuidanceAt = 0;

    updateQuietStatus("Drawing together");

    await queueSpeak("librarian", prompt.intro);
    await sleep(250);

    if (state.roundNumber === 3) {
      await queueSpeak("librarian", "Do you two want to add something silly to this one?");
      await queueSpeak("star", `What do you think, ${childName}?`, {
        expectsResponse: true,
        askType: "open",
        source: "librarian-redirect",
        responseSeconds: 5.2
      });
      return;
    }

    if (state.roundNumber >= 4) {
      await queueSpeak("librarian", pickLine(prompt.librarianDirect), {
        expectsResponse: true,
        askType: "one_word",
        source: "librarian-direct",
        responseSeconds: 5.6
      });
      return;
    }

    await queueSpeak("star", pickLine(prompt.firstQuestion), {
      expectsResponse: true,
      askType: "one_word",
      source: "star",
      responseSeconds: 5.2
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

    if (state.roundNumber >= 4 || state.librarianDirectResponses >= 1) {
      await offerFinalPlayAgain();
      return;
    }

    await askPlayAgain();
  }

  async function askPlayAgain() {
    await speakNow("librarian", "Do you two want to play again?");
    await speakNow("star", `What do you think, ${childName}?`, {
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

    await speakNow("librarian", `Do you want to draw one more before we play a different game, ${childName}?`, {
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
