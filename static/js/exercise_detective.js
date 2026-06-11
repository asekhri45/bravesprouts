document.addEventListener("DOMContentLoaded", function () {
  const completeModal = document.getElementById("completeModal");
  const restartBtn = document.getElementById("restartBtn");

  const incomingCallScreen = document.getElementById("incomingCallScreen");
  const acceptCall = document.getElementById("acceptCall");
  const declineCall = document.getElementById("declineCall");
  const exerciseStage = document.getElementById("exerciseStage");

  let characterAudio = null;
  let audioContext = null;
  let analyser = null;
  let sourceNode = null;
  let mouthAnimationFrame = null;

  let mediaRecorder = null;
  let audioChunks = [];
  let isListening = false;
  let silenceTimer = null;
  let currentResponseMode = "none";

  const ringtone = new Audio("/static/images/ringtone.mp3");
  ringtone.loop = true;
  ringtone.volume = 0.35;

  const callAcceptedSound = new Audio("/static/images/call_accepted.mp3");
  callAcceptedSound.volume = 0.5;

  let ringtoneStarted = false;

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

  async function requestCharacterMessage(eventType, childResponse = "") {
    try {
      const response = await fetch("/api/exercise-detective/message", {
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
      console.log("🏃 Exercise Detective response:", data);

      if (!data.success) {
        console.error(data.error || "Gym teacher response failed");
        return;
      }

      currentResponseMode = data.response_mode || "none";

      if (data.game_complete) {
        setTimeout(function () {
          completeModal.classList.add("show");
        }, 900);
      }

      playCharacterAudio(data.audio, data.expects_response !== false);

    } catch (error) {
      console.error("Exercise Detective request error:", error);
    }
  }

  async function startListeningForChild() {
    if (isListening) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true
      });

      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      isListening = true;

      mediaRecorder.addEventListener("dataavailable", function (event) {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      });

      mediaRecorder.addEventListener("stop", async function () {
        isListening = false;

        stream.getTracks().forEach(function (track) {
          track.stop();
        });

        const audioBlob = new Blob(audioChunks, {
          type: "audio/webm"
        });

        if (!audioBlob.size) {
          requestCharacterMessage("no_response", "");
          return;
        }

        await sendAudioToTranscribe(audioBlob);
      });

      mediaRecorder.start();

      silenceTimer = setTimeout(function () {
        stopListeningForChild();
      }, 8000);

    } catch (error) {
      console.error("Microphone error:", error);
      requestCharacterMessage("no_response", "");
    }
  }

  function stopListeningForChild() {
    if (!mediaRecorder) return;
    if (mediaRecorder.state === "inactive") return;

    clearTimeout(silenceTimer);
    mediaRecorder.stop();
  }

  async function sendAudioToTranscribe(audioBlob) {
    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "child-response.webm");

      const response = await fetch("/api/exercise-detective/transcribe", {
        method: "POST",
        credentials: "same-origin",
        body: formData
      });

      const data = await response.json();

      if (!data.success) {
        requestCharacterMessage("no_response", "");
        return;
      }

      const transcript = (data.text || "").trim();

      if (!transcript) {
        requestCharacterMessage("no_response", "");
        return;
      }

      requestCharacterMessage("child_answer", transcript);

    } catch (error) {
      console.error("Transcription request error:", error);
      requestCharacterMessage("no_response", "");
    }
  }

  function playCharacterAudio(audioSrc, shouldListenAfter = true) {
    if (!audioSrc) {
      stopMouthAnimation();
      return;
    }

    if (isListening) {
      stopListeningForChild();
    }

    if (characterAudio) {
      characterAudio.pause();
      characterAudio.currentTime = 0;
    }

    characterAudio = new Audio(audioSrc);
    characterAudio.volume = 1.0;
    characterAudio.playbackRate = 1.04;

    characterAudio.addEventListener("play", function () {
      startMouthAnimation();
    });

    characterAudio.addEventListener("ended", function () {
      stopMouthAnimation();

      if (shouldListenAfter) {
        setTimeout(function () {
          startListeningForChild();
        }, 500);
      }
    });

    characterAudio.addEventListener("error", function () {
      stopMouthAnimation();
    });

    characterAudio.play().catch(function (error) {
      console.error("Audio playback error:", error);
      stopMouthAnimation();
    });
  }

  function startMouthAnimation() {
    const mouth = document.getElementById("characterMouth");
    if (!mouth || !characterAudio) return;

    stopMouthAnimation();

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    sourceNode = audioContext.createMediaElementSource(characterAudio);
    sourceNode.connect(analyser);
    analyser.connect(audioContext.destination);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let currentMouth = "closed";

    function setMouth(state, scaleX, scaleY) {
      if (currentMouth !== state) {
        mouth.src = `/static/images/gym_teacher_mouth-${state}.png`;
        currentMouth = state;
      }

      mouth.style.transform = `translateX(-50%) scale(${scaleX}, ${scaleY})`;
    }

    function animateMouth() {
      analyser.getByteFrequencyData(dataArray);

      let sum = 0;

      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }

      const average = sum / dataArray.length;
      const normalized = Math.min(Math.max((average - 10) / 70, 0), 1);

      const scaleX = 1 + normalized * 0.18;
      const scaleY = 1 + normalized * 0.32;

      if (average < 14) {
        setMouth("closed", 1, 1);
      } else if (average < 34) {
        setMouth("small", scaleX, scaleY);
      } else if (average < 58) {
        setMouth("medium", scaleX, scaleY);
      } else {
        setMouth("wide", scaleX, scaleY);
      }

      mouthAnimationFrame = requestAnimationFrame(animateMouth);
    }

    animateMouth();
  }

  function stopMouthAnimation() {
    const mouth = document.getElementById("characterMouth");

    if (mouthAnimationFrame) {
      cancelAnimationFrame(mouthAnimationFrame);
      mouthAnimationFrame = null;
    }

    if (sourceNode) {
      try {
        sourceNode.disconnect();
      } catch (e) {}
      sourceNode = null;
    }

    if (analyser) {
      try {
        analyser.disconnect();
      } catch (e) {}
      analyser = null;
    }

    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }

    if (mouth) {
      mouth.src = "/static/images/gym_teacher_mouth-closed.png";
      mouth.style.transform = "translateX(-50%) scale(1)";
    }
  }

  function restartGame() {
    if (characterAudio) {
      characterAudio.pause();
      characterAudio.currentTime = 0;
    }

    if (isListening) {
      stopListeningForChild();
    }

    stopMouthAnimation();
    completeModal.classList.remove("show");
    currentResponseMode = "none";

    setTimeout(function () {
      requestCharacterMessage("restart");
    }, 500);
  }

  function startGameAfterCall() {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    stopRingtone();
    playCallAcceptedSound();

    incomingCallScreen.classList.add("hide");
    exerciseStage.classList.remove("call-hidden");

    setTimeout(function () {
      incomingCallScreen.style.display = "none";
    }, 450);

    setTimeout(function () {
      requestCharacterMessage("intro");
    }, 700);
  }

  acceptCall.addEventListener("click", startGameAfterCall);

  declineCall.addEventListener("click", function () {
    acceptCall.disabled = true;
    declineCall.disabled = true;

    stopRingtone();
    playCallAcceptedSound();

    setTimeout(function () {
      window.location.href = "/dashboard";
    }, 300);
  });

  restartBtn.addEventListener("click", restartGame);

  setTimeout(startRingtone, 400);
});