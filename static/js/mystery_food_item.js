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

  // Use browser speech recognition first, matching the working Mystery Animal / Classroom Object flow.
  // If the browser cannot hear anything, fall back to recorded audio transcription.
  //
  // NOTE: USE_BROWSER_SPEECH_RECOGNITION was referenced below (in
  // startListeningForChild and continueListeningAfterThinkingSound) but was
  // never declared anywhere in this file or elsewhere in the repo -- every
  // call to those functions threw "ReferenceError: USE_BROWSER_SPEECH_RECOGNITION
  // is not defined" before either SpeechRecognition or MediaRecorder ever
  // started, meaning this activity's microphone never activated at all.
  // Declaring it here (true, matching the comment above and every sibling
  // activity's default behavior) is the actual fix for that -- unrelated to
  // and more severe than the onerror-fallback bug fixed elsewhere in this file.
  const USE_BROWSER_SPEECH_RECOGNITION = true;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;

  const activityId = document.querySelector("[data-activity-id]")?.dataset.activityId || "unknown";
  function dlog(...args) { if (window.APP_DEBUG) console.log(`[mystery_food_item:${activityId}]`, ...args); }
  let triedRecorderForThisTurn = false;

  const LISTEN_AFTER_STAR_AUDIO_MS = 650;

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.5;

  let ringtoneStarted = false;


  const WORKER_FRAME_CANDIDATES = {
    closed: ["restaurant-worker-mouth-closed.png", "restaurant-worker-mouth-small.png"],
    small: ["restaurant-worker-mouth-small.png", "restaurant-worker-mouth-closed.png"],
    medium: ["restaurant-worker-mouth-medium.png", "restaurant-worker-mouth-mid.png", "restaurant-worker-mouth-small.png"],
    wide: ["restaurant-worker-mouth-wide.png", "restaurant-worker-mouth-large.png", "restaurant-worker-mouth-open.png", "restaurant-worker-mouth-medium.png"]
  };

  const workerFrames = {};
  let workerLastFrame = "closed";
  let workerFlapUntil = 0;
  let workerNextFlapAt = 0;

  function restaurantAsset(name) {
    return `/static/images/restaurant/${name}`;
  }

  function imageLoads(src) {
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = src;
    });
  }

  async function preloadWorkerFrames() {
    for (const [frame, files] of Object.entries(WORKER_FRAME_CANDIDATES)) {
      for (const filename of files) {
        const src = restaurantAsset(filename);
        // eslint-disable-next-line no-await-in-loop
        if (await imageLoads(src)) {
          workerFrames[frame] = src;
          break;
        }
      }
    }

    workerFrames.closed = workerFrames.closed || workerFrames.small;
    workerFrames.small = workerFrames.small || workerFrames.closed;
    workerFrames.medium = workerFrames.medium || workerFrames.small;
    workerFrames.wide = workerFrames.wide || workerFrames.medium;
    setWorkerFrame("closed");
  }

  function setWorkerFrame(frame) {
    const workerCharacter = document.getElementById("workerCharacter");
    if (!workerCharacter) return;

    const safeFrame = workerFrames[frame] ? frame : "closed";
    const nextSrc = workerFrames[safeFrame] || workerFrames.closed || workerCharacter.src;
    if (workerLastFrame === safeFrame && workerCharacter.src.endsWith((nextSrc || "").split("/").pop())) return;

    workerLastFrame = safeFrame;
    workerCharacter.src = nextSrc;
  }

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

  function startListeningAfterStarFinishes() {
    if (!gameActive || sessionDone) return;

    setTimeout(function () {
      if (!gameActive || sessionDone) return;

      if (starAudio && !starAudio.ended && !starAudio.paused) {
        starAudio.addEventListener("ended", function () {
          setTimeout(function () {
            if (gameActive && !sessionDone) {
              startListeningForChild();
            }
          }, 350);
        }, { once: true });

        return;
      }

      startListeningForChild();
    }, LISTEN_AFTER_STAR_AUDIO_MS);
  }

  function getLiveHardCapDuration() {
    const extraThinkingTime = Math.min(thinkingRestartCount * 2500, 5000);

    if (currentResponseMode === "yes_no") return 9000 + extraThinkingTime;
    if (currentResponseMode === "guess_confirmation") return 9000 + extraThinkingTime;
    if (currentResponseMode === "guess_reaction") return 14000 + extraThinkingTime;
    if (currentResponseMode === "choice") return 11000 + extraThinkingTime;
    if (currentResponseMode === "one_word") return 13000 + extraThinkingTime;
    if (currentResponseMode === "short_phrase") return 16000 + extraThinkingTime;
    if (currentResponseMode === "open_hint") return 18000 + extraThinkingTime;
    if (currentResponseMode === "round_choice") return 18000 + extraThinkingTime;

    return 12000 + extraThinkingTime;
  }

  function getBackupListeningDuration() {
    const extraThinkingTime = Math.min(thinkingRestartCount * 2500, 5000);

    if (currentResponseMode === "yes_no") return 6500 + extraThinkingTime;
    if (currentResponseMode === "guess_confirmation") return 7000 + extraThinkingTime;
    if (currentResponseMode === "guess_reaction") return 11000 + extraThinkingTime;
    if (currentResponseMode === "choice") return 8500 + extraThinkingTime;
    if (currentResponseMode === "one_word") return 10000 + extraThinkingTime;
    if (currentResponseMode === "short_phrase") return 12500 + extraThinkingTime;
    if (currentResponseMode === "open_hint") return 14500 + extraThinkingTime;
    if (currentResponseMode === "round_choice") return 15000 + extraThinkingTime;

    return 10000 + extraThinkingTime;
  }

  function getBackupSilenceAfterSpeechDuration() {
    const extraThinkingPause = Math.min(thinkingRestartCount * 800, 1800);

    if (currentResponseMode === "yes_no") return 1500 + extraThinkingPause;
    if (currentResponseMode === "guess_confirmation") return 1100 + extraThinkingPause;
    if (currentResponseMode === "guess_reaction") return 2300 + extraThinkingPause;
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
    if (currentResponseMode === "guess_reaction") return 1000;
    if (currentResponseMode === "choice") return 1000;
    if (currentResponseMode === "one_word") return 1150;
    if (currentResponseMode === "short_phrase") return 1500;
    if (currentResponseMode === "open_hint") return 1800;
    if (currentResponseMode === "round_choice") return 1800;

    return 1200;
  }

  function getLiveSubmitDelay(cleanedTranscript) {
    if (currentResponseMode === "yes_no") {
      if (isYesOrNoLike(cleanedTranscript)) return 350;
      return 900;
    }

    if (currentResponseMode === "guess_confirmation") {
      if (isYesOrNoLike(cleanedTranscript)) return 350;
      return 900;
    }

    if (currentResponseMode === "guess_reaction") return 1100;

    if (currentResponseMode === "choice") return 900;
    if (currentResponseMode === "one_word") return 950;
    if (currentResponseMode === "short_phrase") return 1250;
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
      const response = await fetch("/api/mystery-food-item/thinking-audio", {
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

    if (USE_BROWSER_SPEECH_RECOGNITION && SpeechRecognition) {
      return;
    }

    setTimeout(function () {
      if (!isListening && !waitingForStarResponse && gameActive && !sessionDone) {
        startListeningForChild();
      }
    }, 250);
  }


  function showResponseButtons(mode) {
    // Speech-only activity: no on-screen answer buttons.
    hideResponseButtons();
  }

  function hideResponseButtons() {
    if (!animalResponsePanel) return;

    animalResponsePanel.classList.add("hide");
    animalResponsePanel.innerHTML = "";
  }


  function startRingtone() {
    // Intentionally disabled. Mystery Food Item is in-person at the counter.
    ringtoneStarted = false;
  }

  function stopRingtone() {
    ringtone.pause();
    ringtone.currentTime = 0;
    ringtoneStarted = false;
  }

  function playCallAcceptedSound() {
    return Promise.resolve();
  }

  async function requestStarMessage(eventType, childResponse = "") {
    if (waitingForStarResponse || starSpeaking || sessionDone) return;

    waitingForStarResponse = true;
    hideResponseButtons();
    setListeningUI(false);

    if (eventType === "first_question") {
      setStatus("Leo is ready.");
    } else if (eventType === "no_response") {
      setStatus("Leo is thinking.");
      startThinkingFiller();
    } else if (eventType === "child_answer") {
      setStatus("Leo is thinking.");
      startThinkingFiller();
    } else {
      setStatus("Leo is getting ready.");
    }

    try {
      const response = await fetch("/api/mystery-food-item/message", {
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
      console.log("🍽️ Leo response:", data);

      await finishThinkingFillerBeforeStar();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Leo response failed");
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
        if (nextUrl) {
          sessionDone = true;
          gameActive = false;
          setStatus("Heading back.", true);

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
          setStatus("Finished for now.", true);
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
          startListeningAfterStarFinishes();
        }
      });
    } catch (error) {
      stopThinkingFiller();
      console.error("Mystery Food Item request error:", error);
      setStatus("Leo had a little trouble there.");
    } finally {
      waitingForStarResponse = false;
    }
  }

  async function startListeningForChild() {
    if (isListening || waitingForStarResponse || starSpeaking || sessionDone || !gameActive) return;

    roundResolved = false;
    triedRecorderForThisTurn = true;
    hideResponseButtons();
    setListeningUI(true);

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

    if (USE_BROWSER_SPEECH_RECOGNITION && SpeechRecognition) {
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

  async function startAudioRecorderFallback() {
    if (sessionDone || !gameActive) return;

    console.log("🎤 Starting backup recorder...");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      activeStream = stream;
      audioChunks = [];
      speechDetected = false;
      firstSpeechAt = 0;
      ignoreNextRecording = false;

      let recorderOptions = {};
      if (window.MediaRecorder && MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        recorderOptions = { mimeType: "audio/webm;codecs=opus" };
      } else if (window.MediaRecorder && MediaRecorder.isTypeSupported("audio/webm")) {
        recorderOptions = { mimeType: "audio/webm" };
      }

      mediaRecorder = new MediaRecorder(stream, recorderOptions);
      isListening = true;
      recordStartedAt = Date.now();
      lastSpeechAt = recordStartedAt;

      setListeningUI(true);

      mediaRecorder.addEventListener("dataavailable", function (event) {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
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

        const audioBlob = new Blob(audioChunks, {
          type: "audio/webm"
        });
        dlog("recording stopped", { size: audioBlob.size, type: audioBlob.type });

        // Do not reject the child response only because local volume detection
        // did not cross the threshold. Quiet voices, laptop mics, and background
        // noise can all make speechDetected unreliable. Send the recording to
        // the transcription endpoint and let the transcript decide.
        if (!audioBlob.size || audioBlob.size < 120) {
          console.warn("Recording was too small to transcribe.");
          resetThinkingState();
          await requestStarMessage("no_response", "");
          return;
        }

        await sendAudioToTranscribe(audioBlob);
      });

      mediaRecorder.start(250);
      setupMicSilenceDetection(stream);

      maxRecordTimer = setTimeout(function () {
        stopListeningForChild();
      }, getBackupListeningDuration());
    } catch (error) {
      console.error("Microphone error:", error);
      isListening = false;
      setListeningUI(false);
      hideResponseButtons();
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

        const speechThreshold = 0.010;

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
          speechDuration < 850 &&
          elapsedSinceStart < getBackupListeningDuration() - 1200;

        if (speechWasVeryBrief) {
          if (currentResponseMode === "yes_no" || currentResponseMode === "guess_confirmation" || currentResponseMode === "guess_reaction") {
            silenceNeeded += 1200;
          } else {
            silenceNeeded += 3200;
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

  async function sendAudioToTranscribe(audioBlob) {
    setStatus("Leo is thinking.");
    startThinkingFiller();

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "child-response.webm");

      const response = await fetch("/api/mystery-food-item/transcribe", {
        method: "POST",
        credentials: "same-origin",
        body: formData
      });

      const data = await response.json();

      console.log("📝 Backup transcription response:", data);
      stopThinkingFiller();

      if (!response.ok || !data.success) {
        console.error(data.error || "Transcription failed");
        resetThinkingState();
        await requestStarMessage("no_response", "");
        return;
      }

      const transcript = (data.text || "").trim();

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
      stopThinkingFiller();
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

  function playStarAudioAsPromise(audioSrc) {
    return new Promise(resolve => {
      playStarAudio(audioSrc, false, resolve);
    });
  }

  async function playStarAudioSequence(audioParts, expectsResponse = true, onEnded = null) {
    const parts = (audioParts || []).filter(Boolean);

    if (!parts.length) {
      if (onEnded) onEnded();
      return;
    }

    await Promise.all(parts.map(preloadAudio));

    for (let i = 0; i < parts.length; i++) {
      await playStarAudioAsPromise(parts[i]);

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

  async function playStarResponseAudio(data, expectsResponse = true, onEnded = null) {
    const audioParts = Array.isArray(data.audio_parts)
      ? data.audio_parts.filter(Boolean)
      : [];

    if (audioParts.length) {
      await playStarAudioSequence(audioParts, expectsResponse, onEnded);
      return;
    }

    if (data.audio_url) {
      await playStarAudioSequence([data.audio_url], expectsResponse, onEnded);
      return;
    }

    await playStarAudioAsPromise(data.audio); if (onEnded) onEnded();
  }

  function playStarAudio(audioSrc, expectsResponse = true, onEnded = null) {
    if (!audioSrc) {
      starSpeaking = false;
      stopMouthAnimation();

      if (onEnded) {
        onEnded();
      }

      return;
    }

    stopThinkingFiller();
    starSpeaking = true;

    if (isListening || recognitionActive) {
      cancelListening();
    }

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
      starSpeaking = false;
      stopMouthAnimation();

      if (onEnded) {
        onEnded();
        return;
      }

      if (expectsResponse && gameActive && !sessionDone) {
        startListeningAfterStarFinishes();
      }
    });

    starAudio.addEventListener("error", function () {
      starSpeaking = false;
      console.error("Star audio error");
      stopMouthAnimation();

      if (onEnded) {
        onEnded();
        return;
      }

      if (expectsResponse && gameActive && !sessionDone) {
        startListeningAfterStarFinishes();
      }
    });

    starAudio.play().catch(function (error) {
      starSpeaking = false;
      console.error("Audio playback error:", error);
      stopMouthAnimation();

      if (onEnded) {
        onEnded();
        return;
      }

      if (expectsResponse && gameActive && !sessionDone) {
        startListeningAfterStarFinishes();
      }
    });
  }

  function startMouthAnimation() {
    if (!starAudio) return;

    stopMouthAnimation();
    workerFlapUntil = 0;
    workerNextFlapAt = performance.now() + 260;

    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.68;

      sourceNode = audioContext.createMediaElementSource(starAudio);
      sourceNode.connect(analyser);
      analyser.connect(audioContext.destination);
    } catch (error) {
      console.warn("Leo mouth animation could not start:", error);
      return;
    }

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let displayedFrame = "closed";
    let heldUntil = 0;
    let smoothed = 0;
    const cycleSeed = Math.random() * Math.PI * 2;

    function volumeToFrame(value) {
      if (value < 8) return "closed";
      if (value < 19) return "small";
      if (value < 34) return "medium";
      return "wide";
    }

    function chooseWorkerFrame(target, now) {
      if ((target === "medium" || target === "wide") && now >= workerNextFlapAt) {
        workerFlapUntil = now + 52 + Math.random() * 40;
        workerNextFlapAt = now + 210 + Math.random() * 150;
      }

      if (workerFlapUntil && now < workerFlapUntil) {
        return Math.random() < 0.25 ? "closed" : "small";
      }

      if (target === "wide") return Math.sin(now / 110 + cycleSeed) > 0.22 ? "wide" : "medium";
      if (target === "medium") return Math.sin(now / 125 + cycleSeed) > 0.08 ? "medium" : "small";
      if (target === "small") return Math.sin(now / 165 + cycleSeed) > 0.42 ? "small" : "closed";
      return "closed";
    }

    function animateMouth(now) {
      if (!analyser) return;

      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];

      const average = sum / dataArray.length;
      smoothed = smoothed * 0.78 + average * 0.22;
      const target = volumeToFrame(smoothed);
      const nextFrame = chooseWorkerFrame(target, now || performance.now());

      if ((now || performance.now()) >= heldUntil || nextFrame !== displayedFrame) {
        heldUntil = (now || performance.now()) + (nextFrame === "wide" ? 92 : nextFrame === "medium" ? 84 : nextFrame === "small" ? 78 : 72);
        displayedFrame = nextFrame;
        setWorkerFrame(displayedFrame);
      }

      mouthAnimationFrame = requestAnimationFrame(animateMouth);
    }

    mouthAnimationFrame = requestAnimationFrame(animateMouth);
  }

  function stopMouthAnimation() {
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

    setWorkerFrame("closed");
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
    sessionDone = false;
    gameActive = true;

    setTimeout(function () {
      requestStarMessage("restart");
    }, 350);
  }

  function startGameAfterCall() {
    if (acceptCall) acceptCall.disabled = true;
    if (declineCall) declineCall.disabled = true;

    stopRingtone();

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

  if (acceptCall) {
    acceptCall.addEventListener("click", startGameAfterCall);
  }

  if (declineCall) {
    declineCall.addEventListener("click", function () {
      if (acceptCall) acceptCall.disabled = true;
      if (declineCall) declineCall.disabled = true;

      stopRingtone();

      setTimeout(function () {
        window.location.href = "/dashboard";
      }, 300);
    });
  }

  if (hangupBtn) {
    hangupBtn.addEventListener("click", endCall);
  }

  updateRoundDisplay({ rounds_completed: 0 }, "intro");
  preloadWorkerFrames();

  // No ringtone in this activity: it takes place at Leo's restaurant counter, not on a call.

  const params = new URLSearchParams(window.location.search);

  if (params.get("skip_call") === "1") {
    setTimeout(function () {
      startGameAfterCall();
    }, 250);
  }

  window.restartMysteryFoodItem = restartGame;
  window.restartMysteryAnimal = restartGame;
  window.restartMysteryClassroomObject = restartGame;
  window.restartBookGuessingGame = restartGame;
});