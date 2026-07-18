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

  let starAudio = null;
  let audioContext = null;
  let analyser = null;
  let sourceNode = null;
  let mouthAnimationFrame = null;

  let mediaRecorder = null;
  let audioChunks = [];
  let isListening = false;
  let maxRecordTimer = null;

  let currentResponseMode = "none";
  let currentStage = "intro";
  let offerNextGame = false;

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

  const activityId = document.querySelector("[data-activity-id]")?.dataset.activityId || "unknown";
  function dlog(...args) { if (window.APP_DEBUG) console.log(`[library_guessing_game:${activityId}]`, ...args); }

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

    const classroomObjectWords = new Set([
      "pencil", "backpack", "bag", "bookbag", "glue", "gluestick", "stick"
    ]);

    const words = cleaned.split(" ").filter(Boolean);
    const hasClassroomObject = words.some(function (word) {
      return classroomObjectWords.has(word);
    }) || cleaned.includes("glue stick") || cleaned.includes("school bag");

    if (!hasClassroomObject) return false;

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
      const response = await fetch(`/api/library-guessing-game/thinking-audio?avoid=${avoid}`, {
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

    setTimeout(function () {
      if (!isListening && !waitingForStarResponse && gameActive && !sessionDone) {
        startListeningForChild();
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

    waitingForStarResponse = true;
    hideResponseButtons();
    setListeningUI(false);

    if (eventType === "child_answer" || eventType === "no_response") {
      setStatus("Teacher is thinking.");
      stopThinkingFiller();
    } else if (eventType === "first_prompt") {
      setStatus("Teacher is ready.");
    } else {
      setStatus("Teacher is getting ready.");
    }

    try {
      const response = await fetch("/api/library-guessing-game/message", {
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
      console.log("⭐ Classroom Guessing Game Teacher response:", data);

      stopThinkingFiller();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Teacher response failed");
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

      playStarAudio(data.audio, expectsResponse, function () {
        if (nextUrl) {
          sessionDone = true;
          gameActive = false;
          setStatus("Calling you right back.", true);
          playCallAcceptedSound();

          if (guessPage) {
            guessPage.classList.add("call-ending-transition");
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
            requestStarMessage(nextEvent);
          }, pauseBeforeNext);

          return;
        }

        if (expectsResponse && gameActive && !sessionDone) {
          setTimeout(function () {
            startListeningForChild();
          }, 150);
        }
      });
    } catch (error) {
      stopThinkingFiller();
      console.error("Guessing Game request error:", error);
      setStatus("Something got quiet. You can try again.");
    } finally {
      waitingForStarResponse = false;
    }
  }

  async function startListeningForChild() {
    if (isListening || waitingForStarResponse || sessionDone || !gameActive) return;

    roundResolved = false;

    hideResponseButtons();
    setListeningUI(true);
    showResponseButtons(currentResponseMode);

    // MediaRecorder always captures the full response window from this
    // point forward, regardless of whether SpeechRecognition is available
    // or how it ends up erroring out. This mirrors Match Cards: browser
    // recognition is purely a fast-path optimization layered on top, never
    // a precondition for audio being captured. If SpeechRecognition never
    // fires a usable result, the recorder (already running since t=0) still
    // has the child's full response and gets sent to the server -- no
    // audio spoken before a recognition error/timeout is lost.
    await startAudioRecorderFallback();

    if (roundResolved || sessionDone || !gameActive) return;

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

  async function startAudioRecorderFallback() {
    if (sessionDone || !gameActive) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      activeStream = stream;
      audioChunks = [];
      speechDetected = false;
      firstSpeechAt = 0;
      ignoreNextRecording = false;

      mediaRecorder = new MediaRecorder(stream);
      isListening = true;
      recordStartedAt = Date.now();
      lastSpeechAt = recordStartedAt;

      setListeningUI(true);
      showResponseButtons(currentResponseMode);

      mediaRecorder.addEventListener("dataavailable", function (event) {
        if (event.data && event.data.size > 0) audioChunks.push(event.data);
      });

      mediaRecorder.addEventListener("stop", async function () {
        const shouldIgnore = ignoreNextRecording;

        isListening = false;
        setListeningUI(false);
        hideResponseButtons();
        clearMaxRecordTimer();
        cleanupMicAnalysis();
        stopActiveStream();

        if (shouldIgnore || roundResolved) {
          ignoreNextRecording = false;
          return;
        }

        // The recorder is the authoritative end of the response window now
        // -- stop recognition (if it's still running) so a late
        // onresult/onerror can't also try to resolve this same round.
        roundResolved = true;
        if (recognitionActive || recognition) stopLiveSpeechRecognition(true);

        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        dlog("recording stopped", { size: audioBlob.size, type: audioBlob.type, speechDetected });

        if (!audioBlob.size || !speechDetected) {
          if (silentRetryCount < 1 && currentResponseMode !== "round_choice_voice" && currentResponseMode !== "round_choice") {
            silentRetryCount += 1;
            setStatus("I’m listening.");
            setTimeout(function () {
              startListeningForChild();
            }, 250);
            return;
          }

          resetThinkingState();
          silentRetryCount = 0;
          await requestStarMessage("no_response", "");
          return;
        }

        await sendAudioToTranscribe(audioBlob);
      });

      mediaRecorder.start();
      setupMicSilenceDetection(stream);

      maxRecordTimer = setTimeout(function () {
        stopListeningForChild();
      }, getBackupListeningDuration());
    } catch (error) {
      console.error("Microphone error:", error);
      isListening = false;
      setListeningUI(false);
      showResponseButtons(currentResponseMode);
      setStatus("You can try the mic again.");
    }
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

    if (recognitionActive || recognition) stopLiveSpeechRecognition(true);

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

  async function sendAudioToTranscribe(audioBlob) {
    setStatus("Teacher is thinking.");
    stopThinkingFiller();

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "child-response.webm");

      const response = await fetch("/api/library-guessing-game/transcribe", {
        method: "POST",
        credentials: "same-origin",
        body: formData
      });

      const data = await response.json();
      stopThinkingFiller();

      if (!response.ok || !data.success) {
        resetThinkingState();
        silentRetryCount = 0;
        await requestStarMessage("no_response", "");
        return;
      }

      const transcript = (data.text || "").trim();

      if (!transcript) {
        resetThinkingState();
        silentRetryCount = 0;
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
      stopThinkingFiller();
      console.error("Transcription request error:", error);
      resetThinkingState();
      await requestStarMessage("no_response", "");
    }
  }

  function playStarAudio(audioSrc, expectsResponse = true, onEnded = null) {
    if (!audioSrc) {
      stopMouthAnimation();
      if (onEnded) onEnded();
      return;
    }

    stopThinkingFiller();

    if (isListening || recognitionActive) cancelListening();

    if (starAudio) {
      starAudio.pause();
      starAudio.currentTime = 0;
    }

    stopMouthAnimation();
    hideResponseButtons();
    setStatus("", false);

    starAudio = new Audio(audioSrc);
    starAudio.volume = 1.0;
    starAudio.playbackRate = 0.94;
    starAudio.preservesPitch = false;
    starAudio.mozPreservesPitch = false;
    starAudio.webkitPreservesPitch = false;

    starAudio.addEventListener("play", function () {
      startMouthAnimation();
    });

    starAudio.addEventListener("ended", function () {
      stopMouthAnimation();

      if (onEnded) {
        onEnded();
        return;
      }

      if (expectsResponse && gameActive && !sessionDone) {
        setTimeout(function () {
          startListeningForChild();
        }, 150);
      }
    });

    starAudio.addEventListener("error", function () {
      console.error("Teacher audio error");
      stopMouthAnimation();

      if (onEnded) {
        onEnded();
        return;
      }

      if (expectsResponse && gameActive && !sessionDone) {
        setTimeout(startListeningForChild, 150);
      }
    });

    starAudio.play().catch(function (error) {
      console.error("Audio playback error:", error);
      stopMouthAnimation();

      if (onEnded) {
        onEnded();
        return;
      }

      if (expectsResponse && gameActive && !sessionDone) {
        setTimeout(startListeningForChild, 150);
      }
    });
  }

  function startMouthAnimation() {
    const mouth = document.getElementById("librarianMouth");
    if (!mouth || !starAudio) return;

    stopMouthAnimation();

    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;

      sourceNode = audioContext.createMediaElementSource(starAudio);
      sourceNode.connect(analyser);
      analyser.connect(audioContext.destination);
    } catch (error) {
      console.warn("Mouth animation could not start:", error);
      return;
    }

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let currentMouth = "closed";

    function setMouth(state, scaleX, scaleY) {
      if (currentMouth !== state) {
        mouth.src = `/static/images/librarian-mouth-${state}.png`;
        currentMouth = state;
      }

      mouth.style.transform = `translateX(-50%) scale(${scaleX}, ${scaleY})`;
    }

    function animateMouth() {
      if (!analyser) return;

      analyser.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];

      const average = sum / dataArray.length;
      const normalized = Math.min(Math.max((average - 10) / 70, 0), 1);

      const scaleX = 1 + normalized * 0.18;
      const scaleY = 1 + normalized * 0.32;

      if (average < 14) setMouth("closed", 1, 1);
      else if (average < 34) setMouth("small", scaleX, scaleY);
      else if (average < 58) setMouth("medium", scaleX, scaleY);
      else setMouth("wide", scaleX, scaleY);

      mouthAnimationFrame = requestAnimationFrame(animateMouth);
    }

    animateMouth();
  }

  function stopMouthAnimation() {
    const mouth = document.getElementById("librarianMouth");

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
      try { audioContext.close(); } catch (e) {}
      audioContext = null;
    }

    if (mouth) {
      mouth.src = "/static/images/librarian-mouth-closed.png";
      mouth.style.transform = "translateX(-50%) scale(1)";
    }
  }

  function restartGame() {
    if (starAudio) {
      starAudio.pause();
      starAudio.currentTime = 0;
    }

    cancelListening();
    stopThinkingFiller();
    stopMouthAnimation();
    resetThinkingState();

    currentResponseMode = "none";
    currentStage = "intro";
    offerNextGame = false;
    sessionDone = false;
    gameActive = true;
    updateRoundDisplay({ rounds_completed: 0 });

    setTimeout(function () {
      requestStarMessage("restart");
    }, 350);
  }

  function startGameAfterCall() {
    if (acceptCall) acceptCall.disabled = true;
    if (declineCall) declineCall.disabled = true;

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
    gameActive = false;
    sessionDone = true;

    stopRingtone();
    stopThinkingFiller();

    if (starAudio) {
      starAudio.pause();
      starAudio.currentTime = 0;
    }

    cancelListening();
    stopMouthAnimation();
    resetThinkingState();

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

  const params = new URLSearchParams(window.location.search);

  if (params.get("skip_call") === "1") {
    setTimeout(function () {
      startGameAfterCall();
    }, 250);
  }

  window.restartGuessingGame = restartGame;
});