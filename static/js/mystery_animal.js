document.addEventListener("DOMContentLoaded", function () {
  const animalPage = document.querySelector(".animal-page");

  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const animalStage = document.getElementById("animalStage");

  const hangupBtn = document.getElementById("hangupBtn");
  const animalStatus = document.getElementById("animalStatus");
  const animalResponsePanel = document.getElementById("animalResponsePanel");
  const roundNumber = document.getElementById("roundNumber");

  let mediaRecorder = null;
  let audioChunks = [];
  let isListening = false;
  let maxRecordTimer = null;

  let currentResponseMode = "none";
  let currentStage = "intro";

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
  let starSpeaking = false;

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

  let thinkingFillerTimer = null;
  let thinkingFillerInterval = null;
  let thinkingFillerAudio = null;
  let recentThinkingLines = [];
  let thinkingFillerRequestId = 0;

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;

  const activityId = document.querySelector("[data-activity-id]")?.dataset.activityId || "unknown";
  function dlog(...args) { if (window.APP_DEBUG) console.log(`[mystery_animal:${activityId}]`, ...args); }

  const diagnostics = window.GameDiagnostics
    ? window.GameDiagnostics.createSession({ game: "mystery_animal", activityId: activityId })
    : null;

  const audioManager = window.GameAudioManager
    ? window.GameAudioManager.create({ diagnostics: diagnostics })
    : null;

  function diagLog(eventName, details) {
    if (diagnostics) diagnostics.log(eventName, details);
  }

  // Incremented on every new turn (a fresh requestStarMessage call) and on
  // restart/exit. Any async continuation (fetch response, playback result)
  // captures the token active when it started and checks it still matches
  // before mutating game state -- a stale continuation from a turn that no
  // longer applies (game was restarted or ended in the meantime) becomes a
  // no-op instead of corrupting the current turn.
  let currentTurnToken = 0;
  function beginNewTurn() {
    currentTurnToken += 1;
    return currentTurnToken;
  }
  function isTurnStale(token) {
    return token !== currentTurnToken;
  }

  // Real, intentional pause after a prompt is CONFIRMED finished (real
  // `ended` event, via audioManager.playAndWait) before opening the mic --
  // gives the device's audio output a tiny buffer so the final phoneme
  // isn't clipped by the transition. This is not used to guess whether
  // playback finished; playAndWait already guarantees that.
  const SETTLE_BUFFER_MS = 300;
  const TRANSCRIBE_TIMEOUT_MS = 18000;
  let recordingExtension = "webm";
  let promptRetryCount = 0;
  let currentMouthState = "closed";

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.5;

  let ringtoneStarted = false;

  function setStatus(text, shouldShow = true) {
    if (!animalStatus) return;

    animalStatus.textContent = text || "";

    if (shouldShow && text) {
      animalStatus.classList.add("show");
    } else {
      animalStatus.classList.remove("show");
    }
  }

  function updateRoundDisplay(gameState = {}, stage = currentStage) {
    if (!roundNumber) return;

    const totalRounds = 9;
    const completed = Math.max(0, Number(gameState.rounds_completed || 0));
    let displayRound = completed + 1;

    if (stage === "round_choice" || stage === "session_done") {
      displayRound = Math.max(1, completed);
    }

    displayRound = Math.max(1, Math.min(totalRounds, displayRound));
    roundNumber.textContent = `${displayRound} of ${totalRounds}`;
  }

  function setListeningUI(active) {
    if (!animalPage) return;

    if (active) {
      animalPage.classList.add("is-listening");
      setStatus("I’m listening.");
    } else {
      animalPage.classList.remove("is-listening");
    }
  }

  // Called only after audioManager.playAndWait has already confirmed the
  // prompt's real `ended` event fired -- there is no stale-audio-state to
  // re-check here, unlike the old implementation.
  function startListeningAfterStarFinishes() {
    if (!gameActive || sessionDone) return;

    setTimeout(function () {
      if (!gameActive || sessionDone) return;
      startListeningForChild();
    }, SETTLE_BUFFER_MS);
  }

  function getLiveHardCapDuration() {
    const extraThinkingTime = Math.min(thinkingRestartCount * 2500, 5000);

    if (currentResponseMode === "yes_no") return 12000 + extraThinkingTime;
    if (currentResponseMode === "guess_confirmation") return 12000 + extraThinkingTime;
    if (currentResponseMode === "choice") return 11000 + extraThinkingTime;
    if (currentResponseMode === "one_word") return 13000 + extraThinkingTime;
    if (currentResponseMode === "short_phrase") return 16000 + extraThinkingTime;
    if (currentResponseMode === "open_hint") return 18000 + extraThinkingTime;
    if (currentResponseMode === "round_choice") return 18000 + extraThinkingTime;

    return 12000 + extraThinkingTime;
  }

  function getBackupListeningDuration() {
    const extraThinkingTime = Math.min(thinkingRestartCount * 2500, 5000);

    if (currentResponseMode === "yes_no") return 10000 + extraThinkingTime;
    if (currentResponseMode === "guess_confirmation") return 10000 + extraThinkingTime;
    if (currentResponseMode === "choice") return 8500 + extraThinkingTime;
    if (currentResponseMode === "one_word") return 10000 + extraThinkingTime;
    if (currentResponseMode === "short_phrase") return 12500 + extraThinkingTime;
    if (currentResponseMode === "open_hint") return 14500 + extraThinkingTime;
    if (currentResponseMode === "round_choice") return 15000 + extraThinkingTime;

    return 10000 + extraThinkingTime;
  }

  function getBackupSilenceAfterSpeechDuration() {
    const extraThinkingPause = Math.min(thinkingRestartCount * 800, 1800);

    if (currentResponseMode === "yes_no") return 2600 + extraThinkingPause;
    if (currentResponseMode === "guess_confirmation") return 2600 + extraThinkingPause;
    if (currentResponseMode === "choice") return 2200 + extraThinkingPause;
    if (currentResponseMode === "one_word") return 2400 + extraThinkingPause;
    if (currentResponseMode === "short_phrase") return 3100 + extraThinkingPause;
    if (currentResponseMode === "open_hint") return 3600 + extraThinkingPause;
    if (currentResponseMode === "round_choice") return 3200 + extraThinkingPause;

    return 2400 + extraThinkingPause;
  }

  function getBackupMinimumRecordingDuration() {
    if (currentResponseMode === "yes_no") return 750;
    if (currentResponseMode === "guess_confirmation") return 650;
    if (currentResponseMode === "choice") return 1000;
    if (currentResponseMode === "one_word") return 1150;
    if (currentResponseMode === "short_phrase") return 1500;
    if (currentResponseMode === "open_hint") return 1800;
    if (currentResponseMode === "round_choice") return 1800;

    return 1200;
  }

  function getLiveSubmitDelay(cleanedTranscript) {
    if (currentResponseMode === "yes_no") {
      if (isYesOrNoLike(cleanedTranscript)) return 1100;
      return 1500;
    }

    if (currentResponseMode === "guess_confirmation") {
      if (isYesOrNoLike(cleanedTranscript)) return 1100;
      return 1500;
    }

    if (currentResponseMode === "choice") return 1500;
    if (currentResponseMode === "one_word") return 1500;
    if (currentResponseMode === "short_phrase") return 1900;
    if (currentResponseMode === "open_hint") return 1500;
    if (currentResponseMode === "round_choice") return 1200;

    return 1000;
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
      "um",
      "uh",
      "umm",
      "uhh",
      "hmm",
      "hm",
      "mmm",
      "like"
    ]);

    let words = cleaned.split(" ").filter(Boolean);

    while (words.length > 0 && startingFillers.has(words[0])) {
      words.shift();
    }

    cleaned = words.join(" ").trim();

    const softStarts = [
      "let me think",
      "i think",
      "i guess",
      "wait",
      "hold on"
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
      "um",
      "uh",
      "umm",
      "uhh",
      "hmm",
      "hm",
      "mmm",
      "let me think",
      "i am thinking",
      "i'm thinking",
      "im thinking",
      "thinking",
      "wait",
      "one second",
      "hold on",
      "give me a second",
      "give me one second",
      "give me a minute",
      "i need a second",
      "i need to think",
      "let me see",
      "hmm let me think",
      "um let me think",
      "uh let me think"
    ]);

    if (thinkingOnlyPhrases.has(cleaned)) {
      return true;
    }

    const words = cleaned.split(" ").filter(Boolean);

    const fillerWords = new Set([
      "um",
      "uh",
      "umm",
      "uhh",
      "hmm",
      "hm",
      "mmm",
      "like",
      "wait"
    ]);

    return words.length > 0 && words.every(function (word) {
      return fillerWords.has(word);
    });
  }

  function isYesOrNoLike(text) {
    const cleaned = normalizeTranscriptText(text);
    const words = new Set(cleaned.split(" ").filter(Boolean));

    const yesWords = new Set([
      "yes",
      "yeah",
      "yep",
      "yup",
      "correct",
      "right",
      "sure"
    ]);

    const noWords = new Set([
      "no",
      "nope",
      "nah",
      "not"
    ]);

    for (const word of words) {
      if (yesWords.has(word) || noWords.has(word)) {
        return true;
      }
    }

    return false;
  }

  function resetThinkingState() {
    thinkingRestartCount = 0;
  }

  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async function playThinkingFillerLine() {
    if (!waitingForStarResponse || sessionDone) return;

    const requestId = thinkingFillerRequestId;

    try {
      const response = await fetch("/api/mystery-animal/thinking-audio", {
        method: "GET",
        credentials: "same-origin"
      });

      const data = await response.json();

      if (
        requestId !== thinkingFillerRequestId ||
        !waitingForStarResponse ||
        sessionDone
      ) {
        return;
      }

      if (!response.ok || !data.success || !data.audio_url) {
        return;
      }

      if (
        data.line &&
        recentThinkingLines.length > 0 &&
        recentThinkingLines[recentThinkingLines.length - 1] === data.line
      ) {
        return;
      }

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
        if (!waitingForStarResponse || sessionDone || starSpeaking) {
          stopThinkingFiller();
          return;
        }

        playThinkingFillerLine();
      }, 6500);
    }, 1800);
  }

  async function finishThinkingFillerBeforeStar() {
    thinkingFillerRequestId += 1;

    if (thinkingFillerTimer) {
      clearTimeout(thinkingFillerTimer);
      thinkingFillerTimer = null;
    }

    if (thinkingFillerInterval) {
      clearInterval(thinkingFillerInterval);
      thinkingFillerInterval = null;
    }

    if (
      thinkingFillerAudio &&
      !thinkingFillerAudio.paused &&
      !thinkingFillerAudio.ended
    ) {
      await Promise.race([
        new Promise(resolve => {
          thinkingFillerAudio.addEventListener("ended", resolve, { once: true });
          thinkingFillerAudio.addEventListener("error", resolve, { once: true });
        }),
        delay(650)
      ]);

      await delay(220);
    }

    thinkingFillerAudio = null;
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

    if (SpeechRecognition) {
      return;
    }

    setTimeout(function () {
      if (!isListening && !waitingForStarResponse && gameActive && !sessionDone) {
        startListeningForChild();
      }
    }, 250);
  }


  function showResponseButtons(mode) {
    // Speech-only Mystery Animal: no on-screen answer buttons.
    hideResponseButtons();
  }

  function hideResponseButtons() {
    if (!animalResponsePanel) return;

    animalResponsePanel.classList.add("hide");
    animalResponsePanel.innerHTML = "";
  }


  function startRingtone() {
    if (ringtoneStarted) return;

    ringtone
      .play()
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
    if (waitingForStarResponse || starSpeaking || sessionDone) return;

    const turnToken = beginNewTurn();
    waitingForStarResponse = true;
    hideResponseButtons();
    setListeningUI(false);

    if (eventType === "first_question") {
      setStatus("Star is ready.");
    } else if (eventType === "no_response") {
      setStatus("Star is thinking.");
      startThinkingFiller();
    } else if (eventType === "child_answer") {
      setStatus("Star is thinking.");
      startThinkingFiller();
    } else {
      setStatus("Star is getting ready.");
    }

    diagLog("prompt_requested", { eventType: eventType });
    const requestedAt = Date.now();

    try {
      const response = await fetch("/api/mystery-animal/message", {
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
      if (diagnostics) diagnostics.logTimed("message_response_received", requestedAt, { eventType: eventType, ok: response.ok });
      console.log("⭐ Star response:", data);

      await finishThinkingFillerBeforeStar();

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "requestStarMessage_response" });
        return;
      }

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Star response failed");
      }

      currentResponseMode = data.response_mode || "none";
      currentStage = data.stage || "intro";
      updateRoundDisplay(data.game_state || {}, currentStage);

      const expectsResponse = Boolean(data.expects_response) && !data.session_done;
      const nextEvent = data.next_event || null;
      const pauseBeforeNext = data.pause_before_next_ms || 0;
      const nextUrl = data.next_url || null;
      const redirectAfterMs = Number(data.redirect_after_ms || 0);

      await playStarResponseAudio(data, expectsResponse, function () {
        if (isTurnStale(turnToken)) {
          diagLog("stale_callback_rejected", { where: "requestStarMessage_onEnded" });
          return;
        }

        if (nextUrl) {
          sessionDone = true;
          gameActive = false;
          setStatus("Calling you right back.", true);

          playCallAcceptedSound();

          if (animalPage) {
            animalPage.classList.add("call-ending-transition");
          }

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
              diagLog("stale_callback_rejected", { where: "nextEvent_timeout" });
              return;
            }
            requestStarMessage(nextEvent);
          }, pauseBeforeNext);

          return;
        }

        if (expectsResponse && gameActive && !sessionDone) {
          diagLog("round_advanced", { stage: currentStage });
          startListeningAfterStarFinishes();
        }
      }, turnToken);
    } catch (error) {
      stopThinkingFiller();
      console.error("Mystery Animal request error:", error);
      diagLog("error", { where: "requestStarMessage", message: String(error && error.message || error) });
      if (!isTurnStale(turnToken)) {
        setStatus("Something got quiet. You can try again.");
      }
    } finally {
      waitingForStarResponse = false;
    }
  }

  async function startListeningForChild() {
    if (isListening || waitingForStarResponse || starSpeaking || sessionDone || !gameActive) return;

    roundResolved = false;

    hideResponseButtons();
    // "Listening" is intentionally NOT shown here. It's shown only once
    // MediaRecorder's real `start` event fires (see startAudioRecorderFallback)
    // -- otherwise the UI can claim "I'm listening" while getUserMedia is
    // still resolving or permission is still being granted, and the
    // child's first words are spoken into a mic that isn't capturing yet.

    // MediaRecorder always captures the full response window from this
    // point forward, regardless of whether SpeechRecognition is available
    // or how it ends up erroring out. This mirrors Match Cards: browser
    // recognition is purely a fast-path optimization layered on top, never
    // a precondition for audio being captured. If SpeechRecognition never
    // fires a usable result, the recorder (already running since t=0) still
    // has the child's full response and gets sent to the server -- no
    // audio spoken before a recognition error/timeout is lost.
    const recorderStarted = await startAudioRecorderFallback();

    if (roundResolved || sessionDone || !gameActive) return;

    if (!recorderStarted) {
      // The recorder is the sole authoritative audio source (recognition is
      // only ever a fast-path hint layered on top of it, never a
      // replacement) -- if it couldn't start, there is nothing for
      // recognition to usefully do, and showing "I'm listening" here would
      // be a lie the child has no way to know is false. Offer a real
      // recovery action instead of silently pretending to listen.
      diagLog("recovery_started", { action: "mic_unavailable_offer_retry" });
      setStatus("I can't hear you right now.", true);
      showReplayButton(function () {
        startListeningForChild();
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

      // Rebuild the whole recognition transcript each time. Starting at
      // event.resultIndex can drop an earlier softly-spoken word when the
      // browser emits the answer in multiple result chunks.
      for (let i = 0; i < event.results.length; i++) {
        transcript += `${event.results[i][0].transcript || ""} `;
      }

      transcript = transcript.trim();

      if (!transcript) return;

      lastLiveTranscript = transcript;

      const cleanedTranscript = cleanTranscriptForMeaning(transcript);

      if (!cleanedTranscript || isThinkingOnlyTranscript(cleanedTranscript)) {
        console.log("Live thinking/filler detected:", transcript);
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

      if (recognitionStoppedByUs || !recognitionActive || sessionDone || !gameActive) {
        return;
      }

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
      // authoritative source for this response window.
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
    if (!recognitionActive || !isListening || waitingForStarResponse || sessionDone || !gameActive) {
      return;
    }

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

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      ignoreNextRecording = true;
      try {
        mediaRecorder.stop();
      } catch (error) {
        console.error("Could not cancel concurrent recorder:", error);
      }
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

    if (markStoppedByUs) {
      recognitionStoppedByUs = true;
    }

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

    if (markStoppedByUs) {
      isListening = false;
    }
  }

  function clearRecognitionSubmitTimer() {
    if (recognitionSubmitTimer) {
      clearTimeout(recognitionSubmitTimer);
      recognitionSubmitTimer = null;
    }
  }

  function pickSupportedRecorderMimeType() {
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return null;

    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4;codecs=mp4a.40.2",
      "audio/mp4",
      "audio/ogg;codecs=opus"
    ];

    for (let i = 0; i < candidates.length; i++) {
      if (MediaRecorder.isTypeSupported(candidates[i])) return candidates[i];
    }

    return null;
  }

  function extensionForMimeType(mimeType) {
    if (!mimeType) return "webm";
    if (mimeType.indexOf("mp4") !== -1) return "mp4";
    if (mimeType.indexOf("ogg") !== -1) return "ogg";
    return "webm";
  }

  function verifyMicStreamReady(stream) {
    const track = stream && stream.getAudioTracks ? stream.getAudioTracks()[0] : null;

    if (!track) return { ok: false, reason: "no_audio_track" };
    if (track.readyState !== "live") return { ok: false, reason: "track_not_live" };
    if (!track.enabled) return { ok: false, reason: "track_disabled" };
    if (track.muted) return { ok: false, reason: "track_muted" };

    return { ok: true };
  }

  async function startAudioRecorderFallback() {
    if (sessionDone || !gameActive) return false;

    const turnToken = currentTurnToken;
    console.log("🎤 Starting backup recorder...");
    diagLog("microphone_permission_requested", {});

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      diagLog("microphone_permission_denied", { message: String(error && error.message || error) });
      console.error("Microphone error:", error);
      return false;
    }

    if (isTurnStale(turnToken) || sessionDone || !gameActive) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      diagLog("stale_callback_rejected", { where: "getUserMedia" });
      return false;
    }

    diagLog("microphone_permission_granted", {});

    const readiness = verifyMicStreamReady(stream);
    if (!readiness.ok) {
      diagLog("microphone_track_not_ready", { reason: readiness.reason });
      stream.getTracks().forEach(function (track) { track.stop(); });
      return false;
    }

    activeStream = stream;
    audioChunks = [];
    speechDetected = false;
    firstSpeechAt = 0;
    ignoreNextRecording = false;

    const mimeType = pickSupportedRecorderMimeType();
    recordingExtension = extensionForMimeType(mimeType);
    diagLog("recording_requested", { mimeType: mimeType || "browser_default" });

    try {
      mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType: mimeType })
        : new MediaRecorder(stream);
    } catch (error) {
      diagLog("error", { where: "MediaRecorder_construct", message: String(error && error.message || error) });
      console.error("Could not create recorder:", error);
      stopActiveStream();
      return false;
    }

    mediaRecorder.addEventListener("dataavailable", function (event) {
      if (event.data && event.data.size > 0) {
        audioChunks.push(event.data);
      }
    });

    // Only now -- once the browser has confirmed recording actually began --
    // does the UI claim "I'm listening."
    mediaRecorder.addEventListener("start", function () {
      if (isTurnStale(turnToken)) return;

      isListening = true;
      recordStartedAt = Date.now();
      lastSpeechAt = recordStartedAt;
      setListeningUI(true);
      diagLog("recording_started", { mimeType: mediaRecorder.mimeType });

      setupMicSilenceDetection(stream);

      maxRecordTimer = setTimeout(function () {
        stopListeningForChild();
      }, getBackupListeningDuration());
    });

    mediaRecorder.addEventListener("stop", async function () {
      const shouldIgnore = ignoreNextRecording;

      isListening = false;
      setListeningUI(false);
      hideResponseButtons();
      clearMaxRecordTimer();
      cleanupMicAnalysis();
      stopActiveStream();

      diagLog("recording_stopped", { chunkCount: audioChunks.length, speechDetected: speechDetected });

      if (shouldIgnore || roundResolved || isTurnStale(turnToken)) {
        ignoreNextRecording = false;
        return;
      }

      // The recorder is the authoritative end of the response window now
      // -- stop recognition (if it's still running) so a late
      // onresult/onerror can't also try to resolve this same round.
      roundResolved = true;
      if (recognitionActive || recognition) stopLiveSpeechRecognition(true);

      const audioBlob = new Blob(audioChunks, {
        type: mediaRecorder.mimeType || "audio/webm"
      });
      diagLog("audio_blob_created", { size: audioBlob.size, type: audioBlob.type });
      dlog("recording stopped", { size: audioBlob.size, type: audioBlob.type, speechDetected });

      if (!audioBlob.size || !speechDetected) {
        console.warn("No clear speech captured.");
        resetThinkingState();
        await requestStarMessage("no_response", "");
        return;
      }

      await sendAudioToTranscribe(audioBlob, turnToken);
    });

    mediaRecorder.start();
    return true;
  }

  function stopListeningForChild() {
    // Recognition and the recorder run concurrently now, so both need to be
    // stopped here -- previously this returned early after stopping
    // recognition alone, which (in the old mutually-exclusive model) was
    // correct because the recorder was never running at the same time.
    if (recognitionActive) {
      stopLiveSpeechRecognition(true);
    }

    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      setListeningUI(false);
      hideResponseButtons();
      return;
    }

    try {
      mediaRecorder.stop();
    } catch (error) {
      console.error("Could not stop recorder:", error);
    }
  }

  function cancelListening() {
    roundResolved = true;
    clearRecognitionSubmitTimer();

    if (recognitionActive || recognition) {
      stopLiveSpeechRecognition(true);
    }

    if (!isListening && !mediaRecorder) return;

    ignoreNextRecording = true;
    clearMaxRecordTimer();
    cleanupMicAnalysis();

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.stop();
      } catch (error) {
        console.error("Could not cancel recorder:", error);
      }
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

        const speechThreshold = 0.012;

        if (rms > speechThreshold) {
          if (!speechDetected) {
            firstSpeechAt = now;
          }

          speechDetected = true;
          lastSpeechAt = now;
        }

        const elapsedSinceStart = now - recordStartedAt;
        const speechDuration = firstSpeechAt ? lastSpeechAt - firstSpeechAt : 0;

        let silenceNeeded = getBackupSilenceAfterSpeechDuration();

        const speechWasVeryBrief =
          speechDetected &&
          speechDuration < 1200 &&
          elapsedSinceStart < getBackupListeningDuration() - 1200;

        if (speechWasVeryBrief) {
          if (currentResponseMode === "yes_no" || currentResponseMode === "guess_confirmation") {
            silenceNeeded += 2200;
          } else {
            silenceNeeded += 4200;
          }
        }

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
      try {
        micSource.disconnect();
      } catch (e) {}
      micSource = null;
    }

    if (micAnalyser) {
      try {
        micAnalyser.disconnect();
      } catch (e) {}
      micAnalyser = null;
    }

    if (micAudioContext) {
      try {
        micAudioContext.close();
      } catch (e) {}
      micAudioContext = null;
    }
  }

  async function sendAudioToTranscribe(audioBlob, turnToken) {
    setStatus("Star is thinking.");
    startThinkingFiller();

    const extension = recordingExtension || "webm";
    const uploadStartedAt = Date.now();
    diagLog("upload_started", { size: audioBlob.size, type: audioBlob.type });

    const controller = new AbortController();
    const timeoutHandle = setTimeout(function () { controller.abort(); }, TRANSCRIBE_TIMEOUT_MS);

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, `child-response.${extension}`);

      const response = await fetch("/api/mystery-animal/transcribe", {
        method: "POST",
        credentials: "same-origin",
        body: formData,
        signal: controller.signal
      });

      clearTimeout(timeoutHandle);

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "transcribe_response" });
        return;
      }

      const data = await response.json();
      if (diagnostics) diagnostics.logTimed("upload_completed", uploadStartedAt, { ok: response.ok });

      console.log("📝 Backup transcription response:", data);
      stopThinkingFiller();

      if (!response.ok || !data.success) {
        console.error(data.error || "Transcription failed");
        diagLog("error", { where: "transcribe", category: data.error_category || "unknown" });
        resetThinkingState();
        await requestStarMessage("no_response", "");
        return;
      }

      const transcript = (data.text || "").trim();
      diagLog("transcription_completed", { hasTranscript: Boolean(transcript), length: transcript.length });

      if (!transcript) {
        resetThinkingState();
        await requestStarMessage("no_response", "");
        return;
      }

      if (isThinkingOnlyTranscript(transcript)) {
        console.log("Thinking sound detected, continuing to listen:", transcript);
        continueListeningAfterThinkingSound();
        return;
      }

      const cleanedTranscript = cleanTranscriptForMeaning(transcript);

      if (!cleanedTranscript || isThinkingOnlyTranscript(cleanedTranscript)) {
        console.log("Transcript became filler after cleaning, continuing to listen:", transcript);
        continueListeningAfterThinkingSound();
        return;
      }

      console.log("Sending cleaned backup transcript:", cleanedTranscript);

      resetThinkingState();
      await requestStarMessage("child_answer", cleanedTranscript);
    } catch (error) {
      clearTimeout(timeoutHandle);
      stopThinkingFiller();

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "transcribe_catch" });
        return;
      }

      const category = error && error.name === "AbortError" ? "transcription_timeout" : "upstream_service_error";
      diagLog("error", { where: "transcribe", category: category, message: String(error && error.message || error) });
      console.error("Transcription request error:", error);
      resetThinkingState();
      await requestStarMessage("no_response", "");
    }
  }

  function preloadAudio(src) {
    return new Promise(resolve => {
      if (!src) {
        resolve(null);
        return;
      }

      const audio = new Audio(src);
      audio.preload = "auto";

      let done = false;

      function finish() {
        if (done) return;
        done = true;
        resolve(audio);
      }

      audio.addEventListener("canplaythrough", finish, { once: true });
      audio.addEventListener("loadeddata", finish, { once: true });
      audio.addEventListener("error", finish, { once: true });

      audio.load();
      setTimeout(finish, 900);
    });
  }

  // Drives the mouth PNG from the shared AudioManager's real-time analyser
  // callback (see attachMouthSync in game-audio-manager.js). Only ever
  // called while genuine playback is in progress -- there is no separate
  // per-line AudioContext to leak or leave suspended, and mouth animation
  // structurally cannot outlive real playback since it's driven by the
  // same `ended`/ cancellation path that resolves playAndWait.
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

    if (average < 14) {
      setMouth("closed", 1, 1);
    } else if (average < 34) {
      setMouth("small", scaleX, scaleY);
    } else if (average < 58) {
      setMouth("medium", scaleX, scaleY);
    } else {
      setMouth("wide", scaleX, scaleY);
    }
  }

  // Shows a single, child-friendly "tap to continue" affordance reusing the
  // existing (currently-unused-for-buttons) response panel, rather than
  // adding new DOM/CSS. Only ever shown when a required prompt has
  // genuinely failed after one automatic retry.
  function showReplayButton(onClick) {
    if (!animalResponsePanel) {
      onClick();
      return;
    }

    animalResponsePanel.innerHTML = "";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "animal-response-btn";
    btn.textContent = "Tap to continue";

    btn.addEventListener("click", function () {
      animalResponsePanel.classList.add("hide");
      animalResponsePanel.innerHTML = "";

      // A real click gesture -- re-confirm the shared AudioContext is
      // resumed before retrying, since this is exactly the kind of user
      // gesture autoplay policies require.
      if (audioManager) audioManager.unlock();

      onClick();
    }, { once: true });

    animalResponsePanel.appendChild(btn);
    animalResponsePanel.classList.remove("hide");
  }

  // A required prompt failed (rejected play(), media error, stall timeout).
  // Per the reliability requirements: never treat this as "the line played."
  // Retry automatically once; if that also fails, pause here and require an
  // explicit tap before continuing -- the tap itself is the gesture needed
  // to guarantee the retried playback isn't blocked by autoplay policy.
  function handleFailedPrompt(result, url, onRetry) {
    diagLog("prompt_failed", { url: url, status: result.status });

    if (result.status === "cancelled") {
      // Superseded intentionally (restart/new turn) -- not a failure, and
      // must not surface a replay affordance for a turn that no longer
      // applies.
      return;
    }

    if (promptRetryCount < 1) {
      promptRetryCount += 1;
      diagLog("recovery_started", { action: "auto_retry", url: url });
      onRetry();
      return;
    }

    promptRetryCount = 0;
    setStatus("Tap to hear that again.", true);
    showReplayButton(function () {
      diagLog("recovery_started", { action: "manual_replay", url: url });
      onRetry();
    });
  }

  // Plays exactly one clip as THE authoritative dialogue audio and resolves
  // with audioManager's honest status -- "ended" is the only status that
  // means the line was actually heard.
  function playCurrentPrompt(url) {
    stopThinkingFiller();
    starSpeaking = true;
    hideResponseButtons();
    setStatus("", false);

    if (isListening || recognitionActive) {
      cancelListening();
    }

    if (!audioManager) {
      // No AudioManager available (very old/unsupported browser) -- fall
      // back to a plain play() so the game still runs, without the
      // reliability guarantees.
      return new Promise(function (resolve) {
        const audio = new Audio(url);
        audio.addEventListener("ended", function () { resolve({ status: "ended" }); }, { once: true });
        audio.addEventListener("error", function () { resolve({ status: "error" }); }, { once: true });
        const p = audio.play();
        if (p && p.catch) p.catch(function (err) { resolve({ status: "play_rejected", error: err }); });
      }).then(function (result) {
        starSpeaking = false;
        return result;
      });
    }

    return audioManager.playAndWait(url, { onMouthLevel: updateMouthFromLevel }).then(function (result) {
      starSpeaking = false;
      return result;
    });
  }

  async function playStarAudioSequence(audioParts, expectsResponse = true, onEnded = null, turnToken) {
    const parts = (audioParts || []).filter(Boolean);

    if (!parts.length) {
      if (onEnded) onEnded();
      return;
    }

    await Promise.all(parts.map(preloadAudio));

    for (let i = 0; i < parts.length; i++) {
      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "playStarAudioSequence" });
        return;
      }

      const result = await playCurrentPrompt(parts[i]);

      if (isTurnStale(turnToken)) {
        diagLog("stale_callback_rejected", { where: "playStarAudioSequence_after_play" });
        return;
      }

      if (result.status !== "ended") {
        handleFailedPrompt(result, parts[i], function () {
          playStarAudioSequence(parts.slice(i), expectsResponse, onEnded, turnToken);
        });
        return;
      }

      promptRetryCount = 0;

      if (i < parts.length - 1) {
        await delay(220);
      }
    }

    if (onEnded) {
      onEnded();
      return;
    }

    if (expectsResponse && gameActive && !sessionDone) {
      startListeningAfterStarFinishes();
    }
  }

  async function playStarResponseAudio(data, expectsResponse = true, onEnded = null, turnToken) {
    promptRetryCount = 0;

    const audioParts = Array.isArray(data.audio_parts)
      ? data.audio_parts.filter(Boolean)
      : [];

    if (audioParts.length) {
      await playStarAudioSequence(audioParts, expectsResponse, onEnded, turnToken);
      return;
    }

    if (data.audio_url) {
      await playStarAudioSequence([data.audio_url], expectsResponse, onEnded, turnToken);
      return;
    }

    if (!data.audio) {
      starSpeaking = false;
      if (onEnded) onEnded();
      return;
    }

    await playStarAudioSequence([data.audio], expectsResponse, onEnded, turnToken);
  }

  function restartGame() {
    // Invalidate any turn/callback still in flight from before the restart
    // *before* anything else runs, so a late-arriving response from the
    // pre-restart game can no longer mutate state.
    beginNewTurn();
    if (audioManager) audioManager.cancelActive("restart");

    cancelListening();
    stopThinkingFiller();
    resetThinkingState();

    currentResponseMode = "none";
    currentStage = "intro";
    sessionDone = false;
    gameActive = true;

    diagLog("game_restarted", {});

    setTimeout(function () {
      requestStarMessage("restart");
    }, 350);
  }

  function startGameAfterCall() {
    if (acceptCall) acceptCall.disabled = true;
    if (declineCall) declineCall.disabled = true;

    // Must happen synchronously inside this real click handler: resuming or
    // creating the shared AudioContext here, inside a genuine user gesture,
    // is what lets later programmatic audio.play() calls (from async
    // continuations further down the dialogue chain) succeed under
    // browsers' autoplay policies.
    if (audioManager) audioManager.unlock();
    diagLog("accept_call_clicked", {});

    stopRingtone();
    playCallAcceptedSound();

    if (incomingCallScreen) {
      incomingCallScreen.classList.add("hide");
    }

    if (animalStage) {
      animalStage.classList.remove("call-hidden");
    }

    setTimeout(function () {
      if (incomingCallScreen) {
        incomingCallScreen.style.display = "none";
      }
    }, 450);

    currentResponseMode = "none";
    currentStage = "intro";
    sessionDone = false;
    gameActive = true;
    resetThinkingState();

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

  if (acceptCall) {
    acceptCall.addEventListener("click", startGameAfterCall);
  }

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

  if (hangupBtn) {
    hangupBtn.addEventListener("click", endCall);
  }

  updateRoundDisplay({ rounds_completed: 0 }, "intro");

  setTimeout(startRingtone, 400);

  // The ringtone's first autoplay attempt (above) has no user gesture behind
  // it and can be silently blocked. If that happens, retry once on the very
  // first real interaction with the page rather than leaving it silent for
  // the rest of the incoming-call screen.
  window.addEventListener("pointerdown", function retryRingtoneOnFirstInteraction() {
    if (!ringtoneStarted) startRingtone();
  }, { once: true });

  const params = new URLSearchParams(window.location.search);

  if (params.get("skip_call") === "1") {
    setTimeout(function () {
      startGameAfterCall();
    }, 250);
  }

  window.restartMysteryAnimal = restartGame;
  window.mysteryAnimalDiagnostics = diagnostics;
});
// Mystery Animal decision-tree backend integration version: 2026-07-17
