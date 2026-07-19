document.addEventListener("DOMContentLoaded", function () {
  const guessPage = document.querySelector(".guess-page");

  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const guessStage = document.getElementById("guessStage");

  const hangupBtn = document.getElementById("hangupBtn");
  const guessStatus = document.getElementById("guessStatus");
  const guessResponsePanel = document.getElementById("guessResponsePanel");
  const guessRoundNumber = document.getElementById("guessRoundNumber");

  let isListening = false;
  let maxRecordTimer = null;

  let currentResponseMode = "none";
  let currentStage = "intro";
  let offerNextGame = false;

  // Declared early because the diagnostics session's getState() callback
  // (and logTimed()) reference these -- see the temporal-dead-zone note
  // in the Mystery Animal reference implementation.
  let currentTurnToken = 0;
  let lastKnownMimeType = null;

  let activeStream = null;
  let micAudioContext = null;
  let micAnalyser = null;
  let micSource = null;
  let micAnimationFrame = null;
  let recordStartedAt = 0;
  let firstSpeechAt = 0;
  let lastSpeechAt = 0;
  let speechDetected = false;
  let ignoreNextRecording = false;

  let waitingForStarResponse = false;
  let gameActive = false;
  let sessionDone = false;

  // Guards a single response window against being resolved twice --
  // MediaRecorder and SpeechRecognition now run concurrently (see
  // startListeningForChild), so both a recognition result AND the
  // recorder's own stop/transcribe path could otherwise fire for the same
  // round. Whichever settles first sets this to true; every other
  // resolution path checks it and becomes a no-op.
  let roundResolved = false;

  let recognition = null;
  let recognitionActive = false;
  let recognitionStartedAt = 0;
  let recognitionHardCapTimer = null;
  let recognitionRestartTimer = null;
  let recognitionSubmitTimer = null;
  let recognitionStoppedByUs = false;
  let lastLiveTranscript = "";
  let lastCleanTranscript = "";
  let thinkingRestartCount = 0;
  let silentRetryCount = 0;

  let thinkingFillerTimer = null;
  let thinkingFillerInterval = null;
  let thinkingFillerAudio = null;
  let recentThinkingLines = [];
  let thinkingFillerRequestId = 0;

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;

  const activityId = guessPage ? guessPage.dataset.activityId : "unknown";

  function dlog(...args) {
    if (window.APP_DEBUG) console.log(`[guessing_game:${activityId}]`, ...args);
  }

  const diagnostics = window.GameDiagnostics
    ? window.GameDiagnostics.createSession({
        game: "guessing_game",
        activityId: activityId,
        getState: function () {
          return {
            stage: currentStage,
            responseMode: currentResponseMode,
            gameActive: gameActive,
            sessionDone: sessionDone,
            isListening: isListening,
            waitingForStarResponse: waitingForStarResponse,
            turnToken: currentTurnToken,
            recorderMimeType: lastKnownMimeType
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

  function beginNewTurn() {
    currentTurnToken = turnGuard ? turnGuard.beginNewTurn() : currentTurnToken + 1;
    return currentTurnToken;
  }

  function isTurnStale(token) {
    return turnGuard ? turnGuard.isStale(token) : false;
  }

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.5;

  let ringtoneStarted = false;

  function setStatus(text, shouldShow = true) {
    if (!guessStatus) return;

    guessStatus.textContent = text || "";

    if (shouldShow && text) {
      guessStatus.classList.add("show");
    } else {
      guessStatus.classList.remove("show");
    }
  }

  function updateRoundDisplay(gameState) {
    if (!guessRoundNumber || !gameState) return;

    const completed = Number(gameState.rounds_completed || 0);
    const currentRound = Math.min(Math.max(completed + 1, 1), 3);

    guessRoundNumber.textContent = String(currentRound);
  }

  function setListeningUI(active) {
    if (!guessPage) return;

    if (active) {
      guessPage.classList.add("is-listening");
      setStatus("I’m listening.");
    } else {
      guessPage.classList.remove("is-listening");
    }
  }

  function getLiveHardCapDuration() {
    const extraThinkingTime = Math.min(thinkingRestartCount * 2500, 5000);

    if (((currentResponseMode === "round_choice" || currentResponseMode === "round_choice_voice") || currentResponseMode === "round_choice_voice")) return 18000 + extraThinkingTime;
    return 24000 + extraThinkingTime;
  }

  function getBackupListeningDuration() {
    const extraThinkingTime = Math.min(thinkingRestartCount * 2500, 5000);

    if (((currentResponseMode === "round_choice" || currentResponseMode === "round_choice_voice") || currentResponseMode === "round_choice_voice")) return 14000 + extraThinkingTime;
    return 21000 + extraThinkingTime;
  }

  function getBackupSilenceAfterSpeechDuration() {
    const extraThinkingPause = Math.min(thinkingRestartCount * 500, 1000);

    if (((currentResponseMode === "round_choice" || currentResponseMode === "round_choice_voice") || currentResponseMode === "round_choice_voice")) return 2200 + extraThinkingPause;
    return 2900 + extraThinkingPause;
  }

  function getBackupMinimumRecordingDuration() {
    if (((currentResponseMode === "round_choice" || currentResponseMode === "round_choice_voice") || currentResponseMode === "round_choice_voice")) return 1400;
    return 1800;
  }

  function getLiveSubmitDelay(cleanedTranscript) {
    if (((currentResponseMode === "round_choice" || currentResponseMode === "round_choice_voice") || currentResponseMode === "round_choice_voice")) {
      if (isShortChoiceLike(cleanedTranscript)) return 300;
      return 650;
    }

    if (isLikelyDirectGuess(cleanedTranscript)) return 650;
    if (isLikelyShortQuestion(cleanedTranscript)) return 1150;

    return 1400;
  }

  function normalizeTranscriptText(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[.,!?;:()[\]{}"“”‘’]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function cleanTranscriptForMeaning(text) {
    let cleaned = normalizeTranscriptText(text);

    if (!cleaned) return "";

    const startingFillers = new Set([
      "um", "uh", "umm", "uhh", "hmm", "hm", "mmm", "like"
    ]);

    let words = cleaned.split(" ").filter(Boolean);

    while (words.length > 0 && startingFillers.has(words[0])) {
      words.shift();
    }

    cleaned = words.join(" ").trim();

    const softStarts = [
      "let me think", "i think", "i guess", "maybe", "wait", "hold on"
    ];

    for (const phrase of softStarts) {
      if (cleaned === phrase) return "";

      if (cleaned.startsWith(phrase + " ")) {
        cleaned = cleaned.slice(phrase.length).trim();
        break;
      }
    }

    return cleaned.replace(/\s+/g, " ").trim();
  }

  function isThinkingOnlyTranscript(text) {
    const cleaned = normalizeTranscriptText(text);

    if (!cleaned) return true;

    const thinkingOnlyPhrases = new Set([
      "um", "uh", "umm", "uhh", "hmm", "hm", "mmm",
      "let me think", "i am thinking", "i'm thinking", "im thinking",
      "thinking", "wait", "one second", "hold on", "give me a second",
      "give me one second", "give me a minute", "i need a second",
      "i need to think", "let me see"
    ]);

    if (thinkingOnlyPhrases.has(cleaned)) return true;

    const words = cleaned.split(" ").filter(Boolean);
    const fillerWords = new Set(["um", "uh", "umm", "uhh", "hmm", "hm", "mmm", "like", "wait"]);

    return words.length > 0 && words.every(function (word) {
      return fillerWords.has(word);
    });
  }

  function isShortChoiceLike(text) {
    const cleaned = normalizeTranscriptText(text);
    const words = cleaned.split(" ").filter(Boolean);

    if (words.length > 4) return false;

    const choiceWords = new Set([
      "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "alright", "cool",
      "again", "more", "stop", "done", "no", "nope", "next", "different"
    ]);

    return words.some(function (word) {
      return choiceWords.has(word);
    });
  }

  function isLikelyDirectGuess(text) {
    const cleaned = normalizeTranscriptText(text);

    if (!cleaned) return false;

    const animalWords = new Set([
      "dog", "cat", "fish", "bird", "rabbit", "frog", "horse", "cow", "duck",
      "lion", "tiger", "elephant", "giraffe", "penguin", "dolphin", "shark",
      "turtle", "monkey", "zebra", "panda"
    ]);

    const words = cleaned.split(" ").filter(Boolean);
    const hasAnimal = words.some(function (word) {
      return animalWords.has(word);
    });

    if (!hasAnimal) return false;

    return cleaned.includes("is it") || cleaned.includes("i think") || cleaned.includes("guess") || words.length <= 4;
  }

  function isLikelyShortQuestion(text) {
    const cleaned = normalizeTranscriptText(text);
    const words = cleaned.split(" ").filter(Boolean);

    if (words.length <= 3) return false;

    const starters = ["is", "are", "do", "does", "can", "could", "would", "has", "have", "what", "where", "how"];
    return starters.includes(words[0]);
  }

  function resetThinkingState() {
    thinkingRestartCount = 0;
  }

  async function playThinkingFillerLine() {
    if (!waitingForStarResponse || sessionDone) return;

    const requestId = thinkingFillerRequestId;

    try {
      const avoid = encodeURIComponent(recentThinkingLines.join("|"));
      const response = await fetch(`/api/guessing-game/thinking-audio?avoid=${avoid}`, {
        method: "GET",
        credentials: "same-origin"
      });

      const data = await response.json();

      if (requestId !== thinkingFillerRequestId || !waitingForStarResponse || sessionDone) return;
      if (!response.ok || !data.success || !data.audio_url) return;

      if (data.line) {
        recentThinkingLines.push(data.line);
        recentThinkingLines = recentThinkingLines.slice(-5);
      }

      if (thinkingFillerAudio) {
        thinkingFillerAudio.pause();
        thinkingFillerAudio.currentTime = 0;
      }

      thinkingFillerAudio = new Audio(data.audio_url);
      thinkingFillerAudio.volume = 0.72;
      thinkingFillerAudio.playbackRate = 0.96;
      thinkingFillerAudio.preservesPitch = false;
      thinkingFillerAudio.mozPreservesPitch = false;
      thinkingFillerAudio.webkitPreservesPitch = false;

      thinkingFillerAudio.play().catch(function (error) {
        console.log("Could not play thinking filler:", error);
      });
    } catch (error) {
      console.log("Thinking filler unavailable:", error);
    }
  }

  function startThinkingFiller() {
    stopThinkingFiller();
    thinkingFillerRequestId += 1;

    thinkingFillerTimer = setTimeout(function () {
      playThinkingFillerLine();

      thinkingFillerInterval = setInterval(function () {
        if (!waitingForStarResponse || sessionDone) {
          stopThinkingFiller();
          return;
        }

        playThinkingFillerLine();
      }, 4200);
    }, 900);
  }

  function stopThinkingFiller() {
    thinkingFillerRequestId += 1;

    if (thinkingFillerTimer) {
      clearTimeout(thinkingFillerTimer);
      thinkingFillerTimer = null;
    }

    if (thinkingFillerInterval) {
      clearInterval(thinkingFillerInterval);
      thinkingFillerInterval = null;
    }

    if (thinkingFillerAudio) {
      try {
        thinkingFillerAudio.pause();
        thinkingFillerAudio.currentTime = 0;
      } catch (error) {}

      thinkingFillerAudio = null;
    }
  }

  function continueListeningAfterThinkingSound() {
    if (!gameActive || sessionDone) return;

    thinkingRestartCount += 1;
    setStatus("Take your time.", true);

    if (SpeechRecognition) return;

    const tokenAtCall = currentTurnToken;

    setTimeout(function () {
      if (isTurnStale(tokenAtCall)) return;
      if (!isListening && !waitingForStarResponse && gameActive && !sessionDone) {
        startListeningForChild(tokenAtCall);
      }
    }, 250);
  }

  function makeResponseButton(label, value) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "guess-response-btn";
    button.textContent = label;

    button.addEventListener("click", function () {
      handleManualResponse(value);
    });

    return button;
  }

  function showResponseButtons(mode) {
    // Voice-only game: no play-again / stop buttons.
    hideResponseButtons();
  }

  function hideResponseButtons() {
    if (!guessResponsePanel) return;

    guessResponsePanel.classList.add("hide");
    guessResponsePanel.innerHTML = "";
  }

  function handleManualResponse(value) {
    if (waitingForStarResponse || sessionDone) return;

    resetThinkingState();
    cancelListening();
    hideResponseButtons();
    requestStarMessage("child_answer", value);
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

  async function requestStarMessage(eventType, childResponse = "") {
    if (waitingForStarResponse || sessionDone) return;

    if (eventType === "child_answer") {
      silentRetryCount = 0;
    }

    const turnToken = beginNewTurn();
    waitingForStarResponse = true;
    hideResponseButtons();
    setListeningUI(false);

    if (eventType === "child_answer" || eventType === "no_response") {
      setStatus("Star is thinking.");
      stopThinkingFiller();
    } else if (eventType === "first_prompt") {
      setStatus("Star is ready.");
    } else {
      setStatus("Star is getting ready.");
    }

    diagLog("prompt_requested", { eventType: eventType });
    const requestedAt = diagnostics ? diagnostics.now() : Date.now();

    try {
      const response = await fetch("/api/guessing-game/message", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "same-origin",
        body: JSON.stringify({
          event_type: eventType,
          child_response: childResponse,
          response_mode: currentResponseMode
        })
      });

      const data = await response.json();
      if (diagnostics) diagnostics.logTimed("backend_response_received", requestedAt, { eventType: eventType, ok: response.ok });
      console.log("⭐ Guessing Game Star response:", data);

      stopThinkingFiller();

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "requestStarMessage_response", staleTurnToken: turnToken, currentTurnToken: currentTurnToken });
        return;
      }

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Star response failed");
      }

      currentResponseMode = data.response_mode || "none";
      currentStage = data.stage || "intro";
      offerNextGame = Boolean(data.offer_next_game);
      updateRoundDisplay(data.game_state);

      const expectsResponse = Boolean(data.expects_response) && !data.session_done;
      const nextEvent = data.next_event || null;
      const pauseBeforeNext = data.pause_before_next_ms || 0;
      const nextUrl = data.next_url || null;
      const redirectAfterMs = Number(data.redirect_after_ms || 0);

      const playbackResult = await playCurrentPrompt(data.audio, turnToken);

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "requestStarMessage_after_playback", staleTurnToken: turnToken, currentTurnToken: currentTurnToken });
        return;
      }

      if (playbackResult.status !== "ended" && playbackResult.status !== "cancelled" && playbackResult.status !== "skipped_no_audio") {
        // A required prompt genuinely failed to play (not merely
        // cancelled/superseded). Never enter listening for a question the
        // child was never actually asked -- pause here instead.
        diagLog("prompt_failed", { eventType: eventType, status: playbackResult.status });
        setStatus("Tap to hear that again.", true);
        showReplayButton(function () {
          requestStarMessage(eventType, childResponse);
        });
        return;
      }

      diagLog("prompt_ended", { eventType: eventType });

      if (nextUrl) {
        sessionDone = true;
        gameActive = false;
        setStatus("Calling you right back.", true);
        playCallAcceptedSound();

        if (guessPage) {
          guessPage.classList.add("call-ending-transition");
        }

        diagLog("redirect_initiated", { nextUrl: nextUrl });

        setTimeout(function () {
          window.location.href = nextUrl;
        }, redirectAfterMs || 1500);

        return;
      }

      if (data.session_done) {
        sessionDone = true;
        gameActive = false;
        setStatus("Game finished.", true);
        return;
      }

      if (nextEvent) {
        setStatus("Take a second.", true);

        setTimeout(function () {
          if (isTurnStale(turnToken)) {
            diagLog("stale_callback_rejected", { where: "nextEvent_timeout", staleTurnToken: turnToken, currentTurnToken: currentTurnToken });
            return;
          }
          requestStarMessage(nextEvent);
        }, pauseBeforeNext);

        return;
      }

      if (expectsResponse && gameActive && !sessionDone) {
        diagLog("round_advanced", { stage: currentStage });
        setTimeout(function () {
          if (isTurnStale(turnToken)) return;
          startListeningForChild(turnToken);
        }, 150);
      }
    } catch (error) {
      stopThinkingFiller();
      console.error("Guessing Game request error:", error);
      diagLog("error", { where: "requestStarMessage", message: String(error && error.message || error) });
      if (!isTurnStale(turnToken)) {
        setStatus("Something got quiet. You can try again.");
      }
    } finally {
      waitingForStarResponse = false;
    }
  }

  async function startListeningForChild(turnToken) {
    if (isListening || waitingForStarResponse || sessionDone || !gameActive) return;
    if (isTurnStale(turnToken)) return;

    roundResolved = false;

    hideResponseButtons();
    // "Listening" is intentionally NOT shown here -- only once
    // MediaRecorder's real `start` event fires (see startAudioRecorderFallback).

    // MediaRecorder always captures the full response window from this
    // point forward, regardless of whether SpeechRecognition is available
    // or how it ends up erroring out. This mirrors Match Cards: browser
    // recognition is purely a fast-path optimization layered on top, never
    // a precondition for audio being captured. If SpeechRecognition never
    // fires a usable result, the recorder (already running since t=0) still
    // has the child's full response and gets sent to the server -- no
    // audio spoken before a recognition error/timeout is lost.
    const recorderStarted = await startAudioRecorderFallback(turnToken);

    if (roundResolved || sessionDone || !gameActive || isTurnStale(turnToken)) return;

    if (!recorderStarted) {
      diagLog("recovery_started", { action: "mic_unavailable_offer_retry" });
      setStatus("I can't hear you right now.", true);
      showReplayButton(function () {
        startListeningForChild(turnToken);
      });
      return;
    }

    if (SpeechRecognition) {
      startLiveSpeechRecognition();
    }
  }

  function startLiveSpeechRecognition() {
    stopLiveSpeechRecognition(false);

    isListening = true;
    recognitionActive = true;
    recognitionStoppedByUs = false;
    recognitionStartedAt = Date.now();
    lastLiveTranscript = "";
    lastCleanTranscript = "";

    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    setStatus("I’m listening.");

    recognition.onresult = function (event) {
      let transcript = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript || "";
      }

      transcript = transcript.trim();
      if (!transcript) return;

      lastLiveTranscript = transcript;

      const cleanedTranscript = cleanTranscriptForMeaning(transcript);

      if (!cleanedTranscript || isThinkingOnlyTranscript(cleanedTranscript)) {
        lastCleanTranscript = "";
        clearRecognitionSubmitTimer();
        continueListeningAfterThinkingSound();
        return;
      }

      lastCleanTranscript = cleanedTranscript;
      setStatus("I heard you.");

      clearRecognitionSubmitTimer();

      recognitionSubmitTimer = setTimeout(function () {
        submitLiveTranscriptIfReady();
      }, getLiveSubmitDelay(cleanedTranscript));
    };

    recognition.onerror = function (event) {
      console.warn("Speech recognition error:", event.error);
      dlog("recognition error", event.error);

      if (recognitionStoppedByUs || roundResolved) return;

      // MediaRecorder has been capturing this entire response window
      // concurrently since startListeningForChild(), so a recognition error
      // -- "no-speech", "network", or otherwise -- never loses any audio.
      // Just stop the (now useless) recognizer; the recorder's own
      // silence-detector/timeout remains the authoritative decision-maker
      // for this round, exactly like Match Cards.
      stopLiveSpeechRecognition(true);
    };

    recognition.onend = function () {
      const elapsed = Date.now() - recognitionStartedAt;

      if (recognitionStoppedByUs || !recognitionActive || sessionDone || !gameActive) return;

      if (elapsed < getLiveHardCapDuration()) {
        clearTimeout(recognitionRestartTimer);

        recognitionRestartTimer = setTimeout(function () {
          if (
            recognitionActive &&
            !recognitionStoppedByUs &&
            !waitingForStarResponse &&
            gameActive &&
            !sessionDone
          ) {
            try {
              recognition.start();
            } catch (error) {
              console.warn("Could not restart speech recognition:", error);
            }
          }
        }, 120);
      }
    };

    recognitionHardCapTimer = setTimeout(function () {
      if (!recognitionActive || roundResolved || waitingForStarResponse || sessionDone || !gameActive) return;

      const cleanedTranscript = cleanTranscriptForMeaning(lastLiveTranscript);

      if (cleanedTranscript && !isThinkingOnlyTranscript(cleanedTranscript)) {
        submitLiveTranscript(cleanedTranscript);
        return;
      }

      // No usable live transcript within the recognition-specific time
      // budget -- just stop trying to recognize. Do NOT decide the round
      // here: the MediaRecorder started concurrently in
      // startListeningForChild is still running and remains the
      // authoritative source for this response window; its own
      // silence-detector/timeout decides when to stop and transcribe.
      dlog("recognition hard cap reached with no usable live transcript, deferring to recorder");
      stopLiveSpeechRecognition(true);
    }, getLiveHardCapDuration());

    try {
      recognition.start();
    } catch (error) {
      // The concurrently-running recorder (started in startListeningForChild
      // before this function was called) is unaffected -- no need to start
      // it again here.
      console.warn("Speech recognition could not start:", error);
      dlog("recognition failed to start", error.name || error);
      stopLiveSpeechRecognition(true);
    }
  }

  function submitLiveTranscriptIfReady() {
    if (!recognitionActive || !isListening || waitingForStarResponse || sessionDone || !gameActive) return;

    const cleanedTranscript = cleanTranscriptForMeaning(lastCleanTranscript || lastLiveTranscript);

    if (!cleanedTranscript || isThinkingOnlyTranscript(cleanedTranscript)) {
      continueListeningAfterThinkingSound();
      return;
    }

    submitLiveTranscript(cleanedTranscript);
  }

  function submitLiveTranscript(cleanedTranscript) {
    if (waitingForStarResponse || sessionDone || !gameActive || roundResolved) return;
    roundResolved = true;

    console.log("Sending live transcript:", cleanedTranscript);
    dlog("live recognition won the race", { transcript: cleanedTranscript });

    resetThinkingState();
    stopLiveSpeechRecognition(true);

    // A live transcript already won the race -- cancel the concurrently
    // running recorder without letting its own "stop" handler send a
    // second (redundant) transcription request or a duplicate round
    // advancement for the same response window.
    cancelConcurrentRecorder();

    setListeningUI(false);
    hideResponseButtons();

    requestStarMessage("child_answer", cleanedTranscript);
  }

  function cancelConcurrentRecorder() {
    clearMaxRecordTimer();
    cleanupMicAnalysis();

    if (micManager && micManager.isRecording()) {
      ignoreNextRecording = true;
      micManager.stopActive("live_transcript_won_race");
    } else {
      stopActiveStream();
    }
  }

  function stopLiveSpeechRecognition(markStoppedByUs) {
    clearRecognitionSubmitTimer();

    if (recognitionRestartTimer) {
      clearTimeout(recognitionRestartTimer);
      recognitionRestartTimer = null;
    }

    if (recognitionHardCapTimer) {
      clearTimeout(recognitionHardCapTimer);
      recognitionHardCapTimer = null;
    }

    if (markStoppedByUs) recognitionStoppedByUs = true;

    if (recognition) {
      try {
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.onend = null;
        recognition.stop();
      } catch (error) {
        try {
          recognition.abort();
        } catch (e) {}
      }
    }

    recognition = null;
    recognitionActive = false;

    if (markStoppedByUs) isListening = false;
  }

  function clearRecognitionSubmitTimer() {
    if (recognitionSubmitTimer) {
      clearTimeout(recognitionSubmitTimer);
      recognitionSubmitTimer = null;
    }
  }

  async function startAudioRecorderFallback(turnToken) {
    if (sessionDone || !gameActive) return false;

    dlog("recorder fallback: requesting mic");
    diagLog("microphone_permission_requested", {});

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      diagLog("microphone_permission_denied", { message: String(error && error.message || error) });
      console.error("Microphone error:", error);
      dlog("mic permission error", error.name || error);
      return false;
    }

    if (isTurnStale(turnToken) || sessionDone || !gameActive) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      diagLog("stale_callback_rejected", { where: "getUserMedia", staleTurnToken: turnToken, currentTurnToken: currentTurnToken });
      return false;
    }

    diagLog("microphone_permission_granted", {});

    if (!micManager) {
      console.warn("Guessing Game: shared mic manager unavailable.");
      stream.getTracks().forEach(function (track) { track.stop(); });
      return false;
    }

    activeStream = stream;
    speechDetected = false;
    firstSpeechAt = 0;
    ignoreNextRecording = false;

    return new Promise(resolve => {
      micManager.startRecording(stream, {
        onStart: function (info) {
          if (isTurnStale(turnToken)) {
            micManager.stopActive("stale_turn_after_start");
            resolve(false);
            return;
          }

          lastKnownMimeType = info ? info.mimeType : null;
          isListening = true;
          recordStartedAt = Date.now();
          lastSpeechAt = recordStartedAt;
          setListeningUI(true);
          showResponseButtons(currentResponseMode);

          setupMicSilenceDetection(stream);

          maxRecordTimer = setTimeout(function () {
            stopListeningForChild();
          }, getBackupListeningDuration());

          resolve(true);
        },
        onStop: async function (blob, mimeType, extension, wasActive) {
          if (!wasActive) return;

          const shouldIgnore = ignoreNextRecording;

          isListening = false;
          setListeningUI(false);
          hideResponseButtons();
          clearMaxRecordTimer();
          cleanupMicAnalysis();
          stopActiveStream();

          diagLog("recording_stopped", { size: blob.size, speechDetected: speechDetected });

          if (shouldIgnore || roundResolved) {
            ignoreNextRecording = false;
            return;
          }

          // The recorder is the authoritative end of the response window now
          // (SpeechRecognition, if it was running, is only useful if it wins
          // the race before this fires) -- stop it so a late onresult/onerror
          // can't also try to resolve this same round.
          roundResolved = true;
          if (recognitionActive || recognition) stopLiveSpeechRecognition(true);

          dlog("recording stopped", { size: blob.size, type: blob.type, speechDetected });

          if (!blob.size || !speechDetected) {
            if (silentRetryCount < 1 && currentResponseMode !== "round_choice_voice" && currentResponseMode !== "round_choice") {
              silentRetryCount += 1;
              setStatus("I’m listening.");
              setTimeout(function () {
                if (isTurnStale(turnToken)) return;
                startListeningForChild(turnToken);
              }, 250);
              return;
            }

            resetThinkingState();
            silentRetryCount = 0;
            await requestStarMessage("no_response", "");
            return;
          }

          diagLog("audio_blob_created", { size: blob.size, type: blob.type });
          await sendAudioToTranscribe(blob, turnToken, extension);
        },
        onError: function (error) {
          diagLog("error", { where: "startAudioRecorderFallback", message: String(error && error.message || error) });
          console.error("Microphone error:", error);
          isListening = false;
          setListeningUI(false);
          showResponseButtons(currentResponseMode);
          setStatus("Microphone unavailable. Check your permission and try again.");
          resolve(false);
        }
      });
    });
  }

  function stopListeningForChild() {
    // Recognition and the recorder run concurrently now, so both need to be
    // stopped here -- previously this returned early after stopping
    // recognition alone, which (in the old mutually-exclusive model) was
    // correct because the recorder was never running at the same time.
    if (recognitionActive) {
      stopLiveSpeechRecognition(true);
    }

    if (!micManager || !micManager.isRecording()) {
      setListeningUI(false);
      hideResponseButtons();
      return;
    }

    micManager.stopActive("response_window_ended");
  }

  function cancelListening() {
    roundResolved = true;
    clearRecognitionSubmitTimer();

    if (recognitionActive || recognition) stopLiveSpeechRecognition(true);

    const wasRecording = micManager && micManager.isRecording();

    if (!isListening && !wasRecording) return;

    ignoreNextRecording = true;
    clearMaxRecordTimer();
    cleanupMicAnalysis();

    if (wasRecording) {
      micManager.stopActive("cancel_listening");
    } else {
      stopActiveStream();
      setListeningUI(false);
    }

    isListening = false;
  }

  function clearMaxRecordTimer() {
    if (maxRecordTimer) {
      clearTimeout(maxRecordTimer);
      maxRecordTimer = null;
    }
  }

  function stopActiveStream() {
    if (!activeStream) return;

    activeStream.getTracks().forEach(function (track) {
      track.stop();
    });

    activeStream = null;
  }

  function setupMicSilenceDetection(stream) {
    cleanupMicAnalysis();

    try {
      micAudioContext = new (window.AudioContext || window.webkitAudioContext)();
      micAnalyser = micAudioContext.createAnalyser();
      micAnalyser.fftSize = 512;

      micSource = micAudioContext.createMediaStreamSource(stream);
      micSource.connect(micAnalyser);

      const dataArray = new Uint8Array(micAnalyser.fftSize);

      function checkVolume() {
        if (!isListening || !micAnalyser) return;

        micAnalyser.getByteTimeDomainData(dataArray);

        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          const centered = (dataArray[i] - 128) / 128;
          sum += centered * centered;
        }

        const rms = Math.sqrt(sum / dataArray.length);
        const now = Date.now();

        if (rms > 0.035) {
          if (!speechDetected) firstSpeechAt = now;
          speechDetected = true;
          lastSpeechAt = now;
        }

        const elapsedSinceStart = now - recordStartedAt;
        const speechDuration = firstSpeechAt ? lastSpeechAt - firstSpeechAt : 0;

        let silenceNeeded = getBackupSilenceAfterSpeechDuration();

        const speechWasVeryBrief =
          speechDetected &&
          speechDuration < 850 &&
          elapsedSinceStart < getBackupListeningDuration() - 1200;

        if (speechWasVeryBrief) silenceNeeded += 2500;

        const heardSpeechAndThenPause =
          speechDetected &&
          elapsedSinceStart > getBackupMinimumRecordingDuration() &&
          now - lastSpeechAt > silenceNeeded;

        if (heardSpeechAndThenPause) {
          stopListeningForChild();
          return;
        }

        micAnimationFrame = requestAnimationFrame(checkVolume);
      }

      checkVolume();
    } catch (error) {
      console.warn("Mic silence detection unavailable:", error);
    }
  }

  function cleanupMicAnalysis() {
    if (micAnimationFrame) {
      cancelAnimationFrame(micAnimationFrame);
      micAnimationFrame = null;
    }

    if (micSource) {
      try { micSource.disconnect(); } catch (e) {}
      micSource = null;
    }

    if (micAnalyser) {
      try { micAnalyser.disconnect(); } catch (e) {}
      micAnalyser = null;
    }

    if (micAudioContext) {
      try { micAudioContext.close(); } catch (e) {}
      micAudioContext = null;
    }
  }

  const TRANSCRIBE_TIMEOUT_MS = 30000;

  async function sendAudioToTranscribe(audioBlob, turnToken, extension) {
    setStatus("Star is thinking.");
    stopThinkingFiller();
    dlog("transcribe request start", { size: audioBlob.size, type: audioBlob.type });
    diagLog("upload_started", { size: audioBlob.size, type: audioBlob.type });

    const controller = new AbortController();
    const timeoutHandle = setTimeout(function () { controller.abort(); }, TRANSCRIBE_TIMEOUT_MS);

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, `child-response.${extension || "webm"}`);

      const response = await fetch("/api/guessing-game/transcribe", {
        method: "POST",
        credentials: "same-origin",
        body: formData,
        signal: controller.signal
      });

      clearTimeout(timeoutHandle);

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "sendAudioToTranscribe_response", staleTurnToken: turnToken, currentTurnToken: currentTurnToken });
        return;
      }

      const data = await response.json();
      stopThinkingFiller();
      diagLog("upload_completed", { ok: response.ok, success: !!data.success });
      dlog("transcribe response", { status: response.status, success: data.success, hasText: !!data.text });

      if (!response.ok || !data.success) {
        diagLog("error", { where: "transcribe", category: data.error_category || "unknown" });
        resetThinkingState();
        silentRetryCount = 0;
        setStatus("We couldn't hear that. Try again.");
        await requestStarMessage("no_response", "");
        return;
      }

      const transcript = (data.text || "").trim();
      diagLog("transcription_completed", { hasTranscript: !!transcript, length: transcript.length });

      if (!transcript) {
        resetThinkingState();
        silentRetryCount = 0;
        setStatus("We couldn't hear that. Try again.");
        await requestStarMessage("no_response", "");
        return;
      }

      if (isThinkingOnlyTranscript(transcript)) {
        continueListeningAfterThinkingSound();
        return;
      }

      const cleanedTranscript = cleanTranscriptForMeaning(transcript);

      if (!cleanedTranscript || isThinkingOnlyTranscript(cleanedTranscript)) {
        continueListeningAfterThinkingSound();
        return;
      }

      resetThinkingState();
      await requestStarMessage("child_answer", cleanedTranscript);
    } catch (error) {
      clearTimeout(timeoutHandle);
      stopThinkingFiller();

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "sendAudioToTranscribe_catch", staleTurnToken: turnToken, currentTurnToken: currentTurnToken });
        return;
      }

      const category = error && error.name === "AbortError" ? "transcription_timeout" : "network_failure";
      diagLog("error", { where: "transcribe", category: category, message: String(error && error.message || error) });
      console.error("Transcription request error:", error);
      dlog("transcribe request failed", error.message || error);
      resetThinkingState();
      setStatus("We couldn't hear that. Try again.");
      await requestStarMessage("no_response", "");
    }
  }

  let currentMouthState = "closed";

  function updateMouthFromLevel(level) {
    const mouth = document.getElementById("starMouth");
    if (!mouth) return;

    const average = level * 255;
    const normalized = Math.min(Math.max((average - 10) / 70, 0), 1);
    const scaleX = 1 + normalized * 0.18;
    const scaleY = 1 + normalized * 0.32;

    function setMouth(state, sx, sy) {
      if (currentMouthState !== state) {
        mouth.src = `/static/images/mouth-${state}.png`;
        currentMouthState = state;
      }
      mouth.style.transform = `translateX(-50%) scale(${sx}, ${sy})`;
    }

    if (average < 14) setMouth("closed", 1, 1);
    else if (average < 34) setMouth("small", scaleX, scaleY);
    else if (average < 58) setMouth("medium", scaleX, scaleY);
    else setMouth("wide", scaleX, scaleY);
  }

  function stopMouthAnimation() {
    if (audioManager) audioManager.cancelActive("stop_mouth_animation");

    const mouth = document.getElementById("starMouth");
    if (mouth) {
      mouth.src = "/static/images/mouth-closed.png";
      mouth.style.transform = "translateX(-50%) scale(1)";
      currentMouthState = "closed";
    }
  }

  function showReplayButton(onClick) {
    if (!guessResponsePanel) {
      onClick();
      return;
    }

    guessResponsePanel.innerHTML = "";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "guess-response-btn";
    btn.textContent = "Tap to continue";

    btn.addEventListener("click", function () {
      guessResponsePanel.classList.add("hide");
      guessResponsePanel.innerHTML = "";
      if (audioManager) audioManager.unlock();
      onClick();
    }, { once: true });

    guessResponsePanel.appendChild(btn);
    guessResponsePanel.classList.remove("hide");
  }

  // Plays exactly one clip as THE authoritative Star audio and resolves
  // with audioManager's honest status. Unlike Mystery Animal/Match Cards,
  // this game's backend sends a single `data.audio` clip per turn (no
  // multi-part sequence), so there is no per-part loop here.
  async function playCurrentPrompt(audioSrc, turnToken) {
    if (!audioSrc) {
      stopMouthAnimation();
      return { status: "skipped_no_audio" };
    }

    stopThinkingFiller();

    if (isListening || recognitionActive) cancelListening();

    hideResponseButtons();
    setStatus("", false);

    if (!audioManager) {
      return new Promise(resolve => {
        const audio = new Audio(audioSrc);
        audio.volume = 1.0;
        audio.playbackRate = 0.94;
        audio.addEventListener("ended", function () { resolve({ status: "ended" }); }, { once: true });
        audio.addEventListener("error", function () { resolve({ status: "error" }); }, { once: true });
        const p = audio.play();
        if (p && p.catch) p.catch(function (err) { resolve({ status: "play_rejected", error: err }); });
      });
    }

    let result = await audioManager.playAndWait(audioSrc, {
      onMouthLevel: updateMouthFromLevel,
      configureAudio: function (audioEl) {
        audioEl.volume = 1.0;
        audioEl.playbackRate = 0.94;
        audioEl.preservesPitch = false;
        audioEl.mozPreservesPitch = false;
        audioEl.webkitPreservesPitch = false;
      }
    });

    // One safe automatic retry for a genuinely failed (not cancelled)
    // prompt, mirroring the Mystery Animal reference behavior.
    if (result.status !== "ended" && result.status !== "cancelled" && !isTurnStale(turnToken)) {
      diagLog("recovery_started", { action: "auto_retry", status: result.status });
      result = await audioManager.playAndWait(audioSrc, {
        onMouthLevel: updateMouthFromLevel,
        configureAudio: function (audioEl) {
          audioEl.volume = 1.0;
          audioEl.playbackRate = 0.94;
        }
      });
    }

    return result;
  }

  function restartGame() {
    beginNewTurn();
    if (audioManager) audioManager.cancelActive("restart");

    cancelListening();
    stopThinkingFiller();
    resetThinkingState();

    currentResponseMode = "none";
    currentStage = "intro";
    offerNextGame = false;
    sessionDone = false;
    gameActive = true;
    updateRoundDisplay({ rounds_completed: 0 });

    diagLog("game_restarted", {});

    setTimeout(function () {
      requestStarMessage("restart");
    }, 350);
  }

  function startGameAfterCall() {
    if (acceptCall) acceptCall.disabled = true;
    if (declineCall) declineCall.disabled = true;

    // Must happen synchronously inside this real click handler -- see the
    // Mystery Animal reference implementation for why.
    if (audioManager) audioManager.unlock();
    diagLog("accept_call_clicked", {});

    stopRingtone();
    playCallAcceptedSound();

    if (incomingCallScreen) incomingCallScreen.classList.add("hide");
    if (guessStage) guessStage.classList.remove("call-hidden");

    setTimeout(function () {
      if (incomingCallScreen) incomingCallScreen.style.display = "none";
    }, 450);

    currentResponseMode = "none";
    currentStage = "intro";
    offerNextGame = false;
    sessionDone = false;
    gameActive = true;
    resetThinkingState();
    updateRoundDisplay({ rounds_completed: 0 });

    setTimeout(function () {
      requestStarMessage("intro");
    }, 650);
  }

  function endCall() {
    beginNewTurn();
    gameActive = false;
    sessionDone = true;

    stopRingtone();
    stopThinkingFiller();

    if (audioManager) audioManager.cancelActive("exit");

    cancelListening();
    resetThinkingState();

    diagLog("game_exited", {});

    window.location.href = "/dashboard";
  }

  if (acceptCall) acceptCall.addEventListener("click", startGameAfterCall);

  if (declineCall) {
    declineCall.addEventListener("click", function () {
      if (acceptCall) acceptCall.disabled = true;
      if (declineCall) declineCall.disabled = true;

      stopRingtone();
      playCallAcceptedSound();

      setTimeout(function () {
        window.location.href = "/dashboard";
      }, 300);
    });
  }

  if (hangupBtn) hangupBtn.addEventListener("click", endCall);

  setTimeout(startRingtone, 400);

  window.addEventListener("pointerdown", function retryRingtoneOnFirstInteraction() {
    if (!ringtoneStarted) startRingtone();
  }, { once: true });

  const params = new URLSearchParams(window.location.search);

  if (params.get("skip_call") === "1") {
    setTimeout(function () {
      startGameAfterCall();
    }, 250);
  }

  window.restartGuessingGame = restartGame;
  window.guessingGameDiagnostics = diagnostics;
});