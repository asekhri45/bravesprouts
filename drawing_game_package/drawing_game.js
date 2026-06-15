document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".drawing-page");
  const activityId = Number(page?.dataset.activityId || 7);
  const childName = (page?.dataset.childName || "there").trim() || "there";

  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const introScreen = document.getElementById("introScreen");
  const zoomStage = document.getElementById("zoomStage");
  const screenShareLoading = document.getElementById("screenShareLoading");

  const promptTitle = document.getElementById("promptTitle");
  const promptText = document.getElementById("promptText");
  const roundNumber = document.getElementById("roundNumber");
  const speakerName = document.getElementById("speakerName");
  const speakerLine = document.getElementById("speakerLine");
  const bridgeStageLabel = document.getElementById("bridgeStageLabel");
  const bridgeStageText = document.getElementById("bridgeStageText");

  const starVideoTile = document.getElementById("starVideoTile");
  const librarianVideoTile = document.getElementById("librarianVideoTile");
  const micControl = document.getElementById("micControl");
  const hangupButton = document.getElementById("hangupButton");

  const canvas = document.getElementById("drawingCanvas");
  const ctx = canvas.getContext("2d");
  const doneDrawingBtn = document.getElementById("doneDrawingBtn");
  const clearCanvasBtn = document.getElementById("clearCanvasBtn");

  const toolButtons = document.querySelectorAll("[data-tool]");
  const colorButtons = document.querySelectorAll("[data-color]");

  const prompts = [
    { title: "Draw a sunny day", text: "Draw a sun, sky, or anything you want outside.", noun: "sun", choices: ["blue", "yellow"] },
    { title: "Draw a flower", text: "Draw a flower with any color you like.", noun: "flower", choices: ["pink", "purple"] },
    { title: "Draw a silly face", text: "Draw a happy, silly, or surprised face.", noun: "face", choices: ["smile", "hat"] },
    { title: "Draw a cozy book cover", text: "Draw a pretend cover for a storybook.", noun: "book", choices: ["star", "heart"] },
    { title: "Draw one final picture", text: "Draw anything you want before the next game.", noun: "picture", choices: ["star", "flower"] }
  ];

  let state = freshState();

  let currentTool = "pen";
  let currentColor = "#7c3aed";
  let isDrawing = false;
  let lastPoint = null;
  let hasDrawnThisRound = false;

  let activeAudio = null;
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

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.45;
  let ringtoneStarted = false;

  function freshState() {
    return {
      sessionStart: Date.now(),
      bridgeStage: 0,

      roundNumber: 1,
      roundsCompleted: 0,
      finalRoundStarted: false,
      endingStarted: false,

      starQuestionsAsked: 0,
      librarianQuestionsAsked: 0,
      redirectedQuestions: 0,
      spokenResponses: 0,
      spokenWords: 0,
      silentWindows: 0,
      librarianDirectResponses: 0,

      isSpeaking: false,
      isListening: false,
      waitingForResponse: false,
      currentQuestion: null,

      recentLines: [],
      micReady: false,
      micDenied: false
    };
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
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
    state.recentLines = state.recentLines.slice(-18);
  }

  function pickLine(options) {
    const fresh = options.filter(line => !state.recentLines.includes(line));
    const choices = fresh.length ? fresh : options;
    return choices[Math.floor(Math.random() * choices.length)];
  }

  function updateSpeaker(actor, text) {
    const display = actor === "librarian" ? "Librarian" : "Star";

    speakerName.textContent = display;
    speakerLine.textContent = text;
  }

  function updateRoundDisplay() {
    roundNumber.textContent = String(state.roundNumber);
  }

  function updateBridgeStage() {
    let stage = 0;

    /*
      Stage 0: Star leads; Librarian only greets/cheers.
      Stage 1: Star and child draw together; Librarian gives gentle praise.
      Stage 2: Star asks child tiny answers.
      Stage 3: Librarian asks the group, Star redirects to child.
      Stage 4: Librarian directly asks child by name.
    */

    if (state.roundsCompleted >= 1) stage = 1;
    if (state.roundsCompleted >= 2 || state.spokenResponses >= 1) stage = 2;
    if (state.roundsCompleted >= 3 || state.redirectedQuestions >= 1) stage = 3;
    if (state.librarianDirectResponses >= 1 || state.roundsCompleted >= 4) stage = 4;

    state.bridgeStage = Math.max(state.bridgeStage, stage);

    const labels = [
      "Stage 1",
      "Stage 2",
      "Stage 3",
      "Stage 4",
      "Ready for Book Guessing"
    ];

    const texts = [
      "Star leads. The Librarian cheers quietly.",
      "Star and the child draw together.",
      "Star asks tiny questions.",
      "The Librarian asks, and Star helps redirect.",
      "The Librarian can ask the child directly."
    ];

    bridgeStageLabel.textContent = labels[state.bridgeStage] || labels[0];
    bridgeStageText.textContent = texts[state.bridgeStage] || texts[0];

    return state.bridgeStage;
  }

  function getCurrentPrompt() {
    return prompts[Math.min(state.roundNumber - 1, prompts.length - 1)];
  }

  function setPrompt(prompt) {
    promptTitle.textContent = prompt.title;
    promptText.textContent = prompt.text;
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

  function getMouth(actor) {
    const introVisible = introScreen && !introScreen.classList.contains("hidden");

    if (introVisible) {
      return actor === "librarian"
        ? document.getElementById("introLibrarianMouth")
        : document.getElementById("introStarMouth");
    }

    return actor === "librarian"
      ? document.getElementById("librarianMouth")
      : document.getElementById("starMouth");
  }

  function getTile(actor) {
    return actor === "librarian" ? librarianVideoTile : starVideoTile;
  }

  function setMouth(actor, size, scaleX = 1, scaleY = 1) {
    const mouth = getMouth(actor);
    if (!mouth) return;

    const files = {
      closed: "/static/images/mouth-closed.png",
      small: "/static/images/mouth-small.png",
      medium: "/static/images/mouth-medium.png",
      wide: "/static/images/mouth-wide-open.png"
    };

    mouth.src = files[size] || files.closed;
    mouth.style.transform = `translateX(-50%) scale(${scaleX}, ${scaleY})`;
  }

  async function speak(actor, text, options = {}) {
    const calmText = cleanLine(text);

    if (!calmText) return;

    updateSpeaker(actor, calmText);
    rememberLine(calmText);

    const tile = getTile(actor);
    if (tile) tile.classList.add("speaking");

    try {
      state.isSpeaking = true;

      const response = await fetch("/api/drawing-game/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speaker: actor, text: calmText })
      });

      const data = await response.json();

      if (data.success && data.audio) {
        await playCharacterAudio(actor, data.audio);
      } else {
        await sleep(800);
      }
    } catch (error) {
      console.error("Drawing game TTS error:", error);
      await sleep(800);
    } finally {
      state.isSpeaking = false;
      if (tile) tile.classList.remove("speaking");
      stopMouthAnimation(actor);
    }

    if (options.expectsResponse) {
      await askForResponse(actor, calmText, options);
    }
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

      activeAudio.addEventListener("play", function () {
        startMouthAnimation(actor, activeAudio);
      });

      activeAudio.addEventListener("ended", function () {
        stopMouthAnimation(actor);
        resolve();
      });

      activeAudio.addEventListener("error", function () {
        stopMouthAnimation(actor);
        resolve();
      });

      activeAudio.play().catch(function () {
        stopMouthAnimation(actor);
        resolve();
      });
    });
  }

  function startMouthAnimation(actor, audioElement) {
    stopMouthAnimation(actor);

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
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];

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

  function stopMouthAnimation(actor = "star") {
    if (mouthAnimationFrame) {
      cancelAnimationFrame(mouthAnimationFrame);
      mouthAnimationFrame = null;
    }

    if (sourceNode) {
      try { sourceNode.disconnect(); } catch (e) {}
      sourceNode = null;
    }

    if (analyser) {
      try { analyser.disconnect(); } catch (e) {}
      analyser = null;
    }

    if (audioContext) {
      audioContext.close().catch(function () {});
      audioContext = null;
    }

    setMouth(actor, "closed", 1, 1);
  }

  function getSupportedMimeType() {
    const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

    for (const option of options) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(option)) {
        return option;
      }
    }

    return "";
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
      try { responseMicSource.disconnect(); } catch (e) {}
      responseMicSource = null;
    }

    if (responseAudioContext) {
      responseAudioContext.close().catch(function () {});
      responseAudioContext = null;
    }

    responseAnalyser = null;
  }

  async function askForResponse(actor, message, options = {}) {
    if (state.isListening) return;

    state.waitingForResponse = true;
    state.currentQuestion = {
      actor,
      message,
      askType: options.askType || "one_word",
      intent: options.intent || null,
      source: options.source || actor
    };

    if (actor === "librarian") state.librarianQuestionsAsked += 1;
    if (actor === "star") state.starQuestionsAsked += 1;

    await startResponseWindow(state.currentQuestion, options.responseSeconds || 5.5);
  }

  async function startResponseWindow(question, seconds) {
    const stream = await ensureMicPermission();

    if (!stream) {
      state.waitingForResponse = false;
      state.currentQuestion = null;
      handleNoSpeech(question);
      return;
    }

    const tile = getTile(question.actor || "star");
    if (tile) tile.classList.add("soft-listening");
    if (micControl) micControl.classList.add("quiet-listening");

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
        if (event.data && event.data.size > 0) recordingChunks.push(event.data);
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

    if (!recordingChunks.length) {
      handleNoSpeech(question);
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
        handleNoSpeech(question);
        return null;
      }

      const transcript = cleanTranscript(data.text || "");

      if (!transcript) {
        handleNoSpeech(question);
        return null;
      }

      await handleSpeech(transcript, question);
      return transcript;
    } catch (error) {
      console.error("Drawing transcription error:", error);
      handleNoSpeech(question);
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

  async function handleSpeech(transcript, question) {
    const words = countWords(transcript);
    const lower = transcript.toLowerCase();

    state.spokenResponses += 1;
    state.spokenWords += words;

    if (question.source === "librarian-direct") {
      state.librarianDirectResponses += 1;
    }

    updateBridgeStage();

    const isYes = /\b(yes|yeah|yep|sure|okay|ok|again|more|one more|another)\b/.test(lower);
    const isNo = /\b(no|nope|stop|done|finished|all done)\b/.test(lower);

    if (question.intent === "final_one_more") {
      if (isNo) {
        await speak("librarian", "Okay. We can go to the next game.");
        await completeAndGoNext();
        return;
      }

      await speak("star", "Okay. Let's draw one more quick picture together.");
      startFinalRound();
      return;
    }

    if (question.source === "librarian-direct") {
      await speak("librarian", pickLine([
        "I heard you. Nice choice.",
        "Good choice.",
        "Thanks for telling me.",
        "Okay. We can use that.",
        "I heard that."
      ]));

      if (state.librarianDirectResponses >= 1 && state.roundsCompleted >= 3 && !state.endingStarted) {
        await offerEndingPoint();
      }
      return;
    }

    if (question.source === "librarian-redirect") {
      state.redirectedQuestions += 1;
      await speak("star", pickLine([
        "Good choice.",
        "I heard you.",
        "Nice. Let's add that.",
        "Okay. Let's use that.",
        "That works."
      ]));
      return;
    }

    await speak("star", pickLine([
      "Good choice.",
      "I heard you.",
      "Nice. Let's keep drawing.",
      "Okay. Let's add that.",
      "That sounds good."
    ]));
  }

  function handleNoSpeech(question) {
    state.silentWindows += 1;
    updateBridgeStage();

    if (question?.intent === "final_one_more" && !state.finalRoundStarted) {
      setTimeout(function () {
        speak("star", "That's okay. We can do one more quick drawing together.").then(startFinalRound);
      }, 650);
    }
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
    const clientX = event.touches ? event.touches[0].clientX : event.clientX;
    const clientY = event.touches ? event.touches[0].clientY : event.clientY;

    return {
      x: (clientX - rect.left) * window.devicePixelRatio,
      y: (clientY - rect.top) * window.devicePixelRatio
    };
  }

  function startDrawing(event) {
    event.preventDefault();
    isDrawing = true;
    hasDrawnThisRound = true;
    doneDrawingBtn.disabled = false;
    lastPoint = getCanvasPoint(event);
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
  }

  function stopDrawing() {
    isDrawing = false;
    lastPoint = null;
  }

  function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    hasDrawnThisRound = false;
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

  async function beginRound() {
    updateBridgeStage();
    updateRoundDisplay();

    const prompt = getCurrentPrompt();
    setPrompt(prompt);
    clearCanvas();

    doneDrawingBtn.disabled = true;

    if (state.roundNumber === 1) {
      await speak("star", "Let's draw together. You can make any sunny picture you want.");
      await speak("librarian", "I'll stay here and look at your drawing. You two are doing great.");
      return;
    }

    if (state.roundNumber === 2) {
      await speak("star", `${childName}, what color should we use next?`, {
        expectsResponse: true,
        askType: "one_word",
        source: "star",
        responseSeconds: 5
      });
      return;
    }

    if (state.roundNumber === 3) {
      await speak("librarian", "Do you two want to add a little detail to this drawing?");
      await speak("star", `What do you think, ${childName}? You can say yes or no.`, {
        expectsResponse: true,
        askType: "yes_no",
        source: "librarian-redirect",
        responseSeconds: 5
      });
      return;
    }

    await speak("librarian", `${childName}, should we add a ${prompt.choices[0]} or a ${prompt.choices[1]}?`, {
      expectsResponse: true,
      askType: "choice",
      source: "librarian-direct",
      responseSeconds: 5.5
    });
  }

  async function finishRound() {
    if (!hasDrawnThisRound) return;

    doneDrawingBtn.disabled = true;
    state.roundsCompleted += 1;

    const prompt = getCurrentPrompt();

    if (state.finalRoundStarted) {
      await speak("librarian", "That was a nice final drawing. Let's try the next game.");
      await completeAndGoNext();
      return;
    }

    if (state.roundNumber === 1) {
      await speak("star", "Nice drawing. I like how you used the board.");
      await speak("librarian", "Good job. You two are very good at this.");
    } else if (state.roundNumber === 2) {
      await speak("librarian", `That ${prompt.noun} looks great. You two are doing really well.`);
    } else if (state.roundNumber === 3) {
      await speak("librarian", "Nice work. I like drawing with you both.");
    } else {
      await speak("librarian", "I liked hearing your idea. That was a good drawing.");
    }

    updateBridgeStage();

    if (state.librarianDirectResponses >= 1 && state.roundsCompleted >= 3 && !state.endingStarted) {
      await offerEndingPoint();
      return;
    }

    state.roundNumber += 1;
    await sleep(650);
    beginRound();
  }

  async function offerEndingPoint() {
    if (state.endingStarted) return;
    state.endingStarted = true;

    await speak("librarian", `Hey ${childName}, do you want to play one more drawing round before we play a different game?`, {
      expectsResponse: true,
      askType: "yes_no",
      source: "librarian-direct",
      intent: "final_one_more",
      responseSeconds: 6
    });
  }

  function startFinalRound() {
    state.finalRoundStarted = true;
    state.roundNumber += 1;
    beginRound();
  }

  async function completeAndGoNext() {
    const minutesPlayed = Math.max(0, (Date.now() - state.sessionStart) / 60000);

    try {
      const response = await fetch("/api/drawing-game/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activity_id: activityId,
          words_spoken: state.spokenWords,
          minutes_spoken: Math.max(0, state.spokenResponses * 0.08),
          active_minutes: minutesPlayed,
          time_spent_on_activity: minutesPlayed,
          spoken_responses: state.spokenResponses,
          silent_windows: state.silentWindows,
          rounds_completed: state.roundsCompleted,
          final_bridge_stage: state.bridgeStage,
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
    await speak("star", "Hey again. It's me, Star. We're going to play a drawing game together.");
    await speak("librarian", "Hi. I'm the Librarian. I'll draw with you and cheer you on.");
    await speak("star", "I'll share my screen so we can use the drawing board.");
    shrinkIntroToGame();
  }

  function shrinkIntroToGame() {
    stopMouthAnimation("star");
    stopMouthAnimation("librarian");

    requestAnimationFrame(function () {
      introScreen.classList.add("shrink");
    });

    setTimeout(function () {
      zoomStage.classList.remove("call-hidden");
    }, 1050);

    setTimeout(function () {
      introScreen.style.display = "none";
      introScreen.classList.add("hidden");
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

    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }
  }

  // Canvas events
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
  updateBridgeStage();
  doneDrawingBtn.disabled = true;

  setTimeout(startRingtone, 400);
});
