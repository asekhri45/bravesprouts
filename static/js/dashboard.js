document.addEventListener("DOMContentLoaded", function () {
  // ---------------------
  // PROFILE DROPDOWN
  // ---------------------
  const profileDropdown = document.querySelector(".profile-dropdown");
  const profileTrigger = document.getElementById("profileTrigger");
  const dropdownMenu = document.getElementById("dropdownMenu");

  if (profileDropdown && profileTrigger && dropdownMenu) {
    profileTrigger.addEventListener("click", function (event) {
      event.stopPropagation();

      dropdownMenu.classList.toggle("active");
      profileDropdown.classList.toggle("open");
    });

    dropdownMenu.addEventListener("click", function (event) {
      event.stopPropagation();
    });

    document.addEventListener("click", function () {
      dropdownMenu.classList.remove("active");
      profileDropdown.classList.remove("open");
    });
  }

  // ---------------------
  // PROFILE ICON
  // ---------------------
  const currentProfileIcon = document.getElementById("currentProfileIcon");
  const iconOptions = document.querySelectorAll(".icon-option");

  iconOptions.forEach((button) => {
    button.addEventListener("click", async function () {
      const selectedIcon = this.dataset.icon;

      if (!selectedIcon || !currentProfileIcon) return;

      currentProfileIcon.src = `/static/images/${selectedIcon}`;

      try {
        const response = await fetch("/update-profile-icon", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded"
          },
          credentials: "same-origin",
          body: new URLSearchParams({
            icon: selectedIcon
          })
        });

        const data = await response.json();

        if (!data.success) {
          console.error(data.error || "Failed to save icon");
        }
      } catch (error) {
        console.error("Error saving profile icon:", error);
      }
    });
  });

  // ---------------------
  // ACTIVITY BUTTONS
  // ---------------------
  const activityButtons = document.querySelectorAll(".activity-action-btn");

  const unlockModal = document.getElementById("unlockModal");
  const confirmUnlockBtn = document.getElementById("confirmUnlockBtn");
  const cancelUnlockBtn = document.getElementById("cancelUnlockBtn");
  const unlockChecks = document.querySelectorAll(".unlock-check");

  const unlockModalTitle = document.getElementById("unlockModalTitle");
  const characterCheckText = document.getElementById("characterCheckText");
  const activityCheckText = document.getElementById("activityCheckText");
  const timeCheckText = document.getElementById("timeCheckText");

  let pendingUnlockActivityId = null;
  let pendingUnlockButton = null;

  function resetUnlockModal() {
    unlockChecks.forEach((check) => {
      check.checked = false;
    });

    if (confirmUnlockBtn) {
      confirmUnlockBtn.disabled = true;
    }
  }

  function allUnlockChecksComplete() {
    return [...unlockChecks].every((check) => check.checked);
  }

  async function sendActivityAction(endpoint, activityId, button) {
    try {
      if (button) {
        button.disabled = true;
      }

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "same-origin",
        body: JSON.stringify({
          activity_id: activityId
        })
      });

      const data = await response.json();

      if (data.success) {
        location.reload();
      } else {
        console.error(data.error || "Action failed");
        alert(data.error || "Something went wrong.");

        if (button) {
          button.disabled = false;
        }
      }
    } catch (error) {
      console.error("Fetch error:", error);
      alert("Something went wrong. Check the console.");

      if (button) {
        button.disabled = false;
      }
    }
  }

  activityButtons.forEach((button) => {
    button.addEventListener("click", async function () {
      const action = this.dataset.action;
      const activityId = this.dataset.activityId;

      if (!action || !activityId) {
        console.error("Missing action or activity ID");
        return;
      }

      if (action === "set-current") {
        await sendActivityAction("/set-current", activityId, this);
        return;
      }

      if (action === "restart") {
  const confirmRestart = confirm(
    "Restart this activity? This will make it behave like the first time opening it."
  );

  if (!confirmRestart) return;

  await sendActivityAction("/restart-activity", activityId, this);
  return;
}

      if (action === "unlock") {
        pendingUnlockActivityId = activityId;
        pendingUnlockButton = this;

        const activityName = this.dataset.activityName || "this activity";
        const character = this.dataset.character || "the character";
        const time = this.dataset.time || "30";

        if (unlockModalTitle) {
          unlockModalTitle.textContent = `Unlock ${activityName}?`;
        }

        if (characterCheckText) {
          characterCheckText.textContent =
            `Is the child comfortable speaking to ${character}?`;
        }

        if (activityCheckText) {
          activityCheckText.textContent =
            `Can the child comfortably complete ${activityName}?`;
        }

        if (timeCheckText) {
          timeCheckText.textContent =
            `Has the child been on this activity for at least ${time} minutes?`;
        }

        resetUnlockModal();

        if (unlockModal) {
          unlockModal.classList.add("active");
        }

        return;
      }

      console.error("Unknown action:", action);
    });
  });

  unlockChecks.forEach((check) => {
    check.addEventListener("change", function () {
      if (confirmUnlockBtn) {
        confirmUnlockBtn.disabled = !allUnlockChecksComplete();
      }
    });
  });

  if (cancelUnlockBtn && unlockModal) {
    cancelUnlockBtn.addEventListener("click", function () {
      unlockModal.classList.remove("active");
      pendingUnlockActivityId = null;
      pendingUnlockButton = null;
    });
  }

  if (confirmUnlockBtn && unlockModal) {
    confirmUnlockBtn.addEventListener("click", async function () {
      if (!pendingUnlockActivityId) return;

      unlockModal.classList.remove("active");

      await sendActivityAction(
        "/unlock-activity",
        pendingUnlockActivityId,
        pendingUnlockButton
      );
    });
  }

  // ---------------------
  // JOURNEY COLORS / CONNECTOR LINES
  // ---------------------
  function isLockedItem(item) {
    return item && item.classList.contains("journey-locked");
  }

  function readJourneyColorFromElement(element) {
    if (!element) return "";

    const computed = getComputedStyle(element);

    const color =
      element.dataset.color ||
      element.dataset.journeyColor ||
      computed.getPropertyValue("--journey-color").trim() ||
      computed.getPropertyValue("--activity-color").trim() ||
      computed.getPropertyValue("--node-color").trim() ||
      computed.backgroundColor;

    if (!color || color === "transparent" || color === "rgba(0, 0, 0, 0)") {
      return "";
    }

    return color;
  }

  function getJourneyColor(item, node) {
    if (isLockedItem(item)) {
      return "#d8d8e0";
    }

    return (
      readJourneyColorFromElement(item) ||
      readJourneyColorFromElement(node) ||
      "#8b5cf6"
    );
  }

  // ---------------------
// CURRENT ACTIVITY INSTRUCTIONS MODAL
// ---------------------
const instructionsByActivityId = {
  "1": `
  <h3>Purpose</h3>

  <p>
    Match Cards is designed to help your child become comfortable interacting
    with Star while participating in a simple, familiar activity.
  </p>

  <p>
    The game begins as a traditional matching game between the child and parent.
    As the activity progresses, Star gradually becomes more involved in the
    interaction, moving from making observations about the game to participating
    more directly in the conversation.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Sit with your child and start the activity together.</li>
    <li>Take turns flipping over two cards at a time.</li>
    <li>Try to find matching pairs.</li>
    <li>Continue until all pairs have been found.</li>
    <li>As you play, Star will occasionally comment on the game or join the conversation.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    The most important thing is to keep the activity feeling relaxed and enjoyable.
  </p>

  <p>
    During the first few rounds, Star will mostly observe and comment on what is
    happening in the game. Later, Star may begin asking simple questions related
    to the cards or the activity.
  </p>

  <p>When Star speaks:</p>

  <ul>
    <li>Give your child a moment to respond on their own.</li>
    <li>Avoid repeating the same question multiple times.</li>
    <li>
      If a question is directed to both of you, or is phrased generally, it can
      be helpful to casually involve your child by saying:
      <ul>
        <li>"What do you think?"</li>
        <li>"Which one should we look for next?"</li>
        <li>"Hmm, what card do you think Star means?"</li>
      </ul>
    </li>
    <li>If your child does not respond, simply continue playing.</li>
  </ul>

  <p>
    The goal is not to get your child to answer every question. The goal is to
    help conversations that include Star feel increasingly familiar and comfortable.
  </p>

  <h3>What to Expect During Each Round</h3>

  <h4>Rounds 1–3: Star Watches and Comments</h4>

  <p>
    During the first few rounds, Star mostly acts like a friendly observer.
    Star may comment when matches are found, notice what is happening, or
    encourage the parent and child as a team.
  </p>

  <p>
    During these rounds, Star is not trying to get your child to answer
    questions yet. This stage helps your child get used to Star's voice,
    timing, and presence while focusing primarily on the matching game itself.
  </p>

  <p><strong>Parent role:</strong> Simply play the game. There is no need to encourage responses to Star yet.</p>

  <h4>Rounds 4–6: Star Begins Including the Child</h4>

  <p>
    In these rounds, Star starts making comments that include your child more
    directly, but these are still gentle observations and do not require a response.
  </p>

  <p>
    These comments are meant to help your child become more accustomed to being
    included in a conversation with Star nearby.
  </p>

  <p><strong>Parent role:</strong></p>

  <ul>
    <li>"What do you think?"</li>
    <li>"Hmm, I wonder too."</li>
  </ul>

  <p>
    Do not push for an answer. If your child does not respond, simply keep playing.
  </p>

  <h4>Rounds 7–9: Star Asks for Help</h4>

  <p>
    In these rounds, Star begins asking simple questions connected to the cards.
  </p>

  <p>
    This is the first stage where Star is creating more direct opportunities
    for communication. The questions remain simple and concrete because they are
    tied to what your child can already see on the screen.
  </p>

  <p><strong>Parent role:</strong></p>

  <ul>
    <li>Pause briefly after Star asks a question.</li>
    <li>Give your child an opportunity to respond directly.</li>
    <li>If appropriate, casually involve your child by asking "What do you think?" or "Can you help Star?"</li>
  </ul>

  <p>
    Avoid making a big deal out of responses. Treat communication with Star as a
    normal part of the game.
  </p>

  <h4>Rounds 10–12: Star Asks Direct Questions</h4>

  <p>
    In these rounds, Star begins asking clearer and more direct questions.
  </p>

  <p>
    At this point, Star is becoming a more active participant in the conversation
    rather than simply commenting on the game.
  </p>

  <p><strong>Parent role:</strong></p>

  <ul>
    <li>Allow your child the first opportunity to respond.</li>
    <li>Stay present and supportive without taking over the interaction.</li>
    <li>Use simple prompts such as "What do you think?" if needed.</li>
  </ul>

  <p>
    The goal is for Star and your child to begin interacting more naturally with one another.
  </p>

  <h4>Rounds 13 and Beyond: Continued Direct Practice</h4>

  <p>
    After round 12, the game continues in a similar style. Star continues asking
    simple, direct questions and responding naturally to what your child says.
  </p>

  <p>
    This stage is not meant to introduce a new type of interaction. Instead, it
    provides additional opportunities to practice the same direct communication
    introduced in rounds 10–12.
  </p>

  <p><strong>Parent role:</strong></p>

  <ul>
    <li>Continue playing together.</li>
    <li>Allow as much communication as possible to occur directly between your child and Star.</li>
  </ul>

  <h4>If Your Child Does Not Respond</h4>

  <p>
    If your child does not answer, simply continue playing.
  </p>

  <p>
    Star is designed to continue the activity without making silence feel like a
    failure. Additional opportunities for communication will naturally occur later.
  </p>

  <p>
    The goal is not perfect participation during a single session. The goal is to
    help communication with Star feel increasingly natural and comfortable over time.
  </p>
`,
  "2": `
  <h3>Purpose</h3>

  <p>
    Mystery Animal is designed to help your child practice speaking directly
    with Star through a guessing game.
  </p>

  <p>
    Your child thinks of an animal, and Star asks questions to figure it out.
    As the rounds continue, Star gradually asks questions that require more
    information from your child.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Start the video call with Star.</li>
    <li>Have your child think of an animal silently in their head.</li>
    <li>Star will ask questions about the animal.</li>
    <li>Your child answers Star out loud.</li>
    <li>Star uses the answers to guess the animal.</li>
    <li>After Star guesses correctly, your child can think of a new animal for the next round.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, Star is the main conversation partner.
    Your role is mostly to stay nearby and let the conversation happen directly
    between your child and Star.
  </p>

  <p>
    If your child seems unsure, you can give a small prompt like:
  </p>

  <ul>
    <li>"What should we tell Star?"</li>
    <li>"What clue would help Star?"</li>
    <li>"What do you think?"</li>
  </ul>

  <p>
    Try not to answer for your child right away. Also avoid making speaking
    feel like a big event. The goal is for talking to Star to feel like a normal
    part of the game.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1–3: Simple Answers</h4>

  <p>
    In the first few rounds, Star asks mostly straightforward questions.
    Many questions can be answered with one word or by choosing between options.
  </p>

  <p>
    Star may ask things like:
  </p>

  <ul>
    <li>"Is it big or small?"</li>
    <li>"Does it live on land or in water?"</li>
    <li>"Is it a pet or a wild animal?"</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child answer Star directly in a
    simple, predictable way.
  </p>

  <h4>Rounds 4–6: Giving More Information</h4>

  <p>
    In the next few rounds, Star may ask follow-up questions that require a
    little more information.
  </p>

  <p>
    For example, if your child says the animal has one main color, Star may ask:
  </p>

  <ul>
    <li>"What is the animal's main color?"</li>
  </ul>

  <p>
    These questions are still about clear, concrete details, but your child may
    need to give more than a yes/no answer.
  </p>

  <p>
    The purpose of these rounds is to help your child practice giving Star
    useful details.
  </p>

  <h4>Rounds 7–9: Giving Hints</h4>

  <p>
    In the later rounds, Star may occasionally ask more open-ended questions.
  </p>

  <p>
    Star may ask things like:
  </p>

  <ul>
    <li>"Can you give me a hint?"</li>
    <li>"What's something important I should know about your animal?"</li>
    <li>"Can you help me figure it out?"</li>
  </ul>

  <p>
    These questions have many possible answers. Your child is no longer only
    answering Star's questions; they are helping decide what information Star
    needs.
  </p>

  <p>
    The purpose of these rounds is to help your child practice generating and
    sharing information during a conversation.
  </p>

  <h4>If Your Child Does Not Respond</h4>

  <p>
    If your child does not answer right away, give them time.
  </p>

  <p>
    If they still do not respond, keep the mood calm and let the game continue.
    The goal is repeated direct practice with Star, not forcing every response.
  </p>
`,
  "3": `
  <h3>Purpose</h3>

  <p>
    Guessing Game is designed to help your child practice asking questions and
    leading a conversation with Star.
  </p>

  <p>
    Star thinks of an animal, and your child asks questions to figure out what
    it is. The more information your child gathers, the easier it becomes to
    make a good guess.
  </p>

  <p>
    Unlike Mystery Animal, where Star asks the questions, this activity encourages
    your child to take the lead by deciding what they would like to ask next.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Star thinks of an animal.</li>
    <li>Your child asks Star questions.</li>
    <li>Star answers the questions.</li>
    <li>Your child uses the clues to figure out the animal.</li>
    <li>Your child makes a guess.</li>
    <li>If the guess is incorrect, the conversation continues.</li>
    <li>If the guess is correct, the round is complete.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, your child is encouraged to lead the conversation.
  </p>

  <p>
    Whenever possible, allow your child to ask questions directly to Star.
  </p>

  <p>
    If your child gets stuck, you can gently remind them that they can ask about:
  </p>

  <ul>
    <li>What the animal looks like</li>
    <li>Where the animal lives</li>
    <li>What the animal eats</li>
    <li>Whether the animal can fly, swim, or run</li>
    <li>Any other clue they would like to know</li>
  </ul>

  <p>
    If your child is unsure what to ask, they can always ask Star for a hint.
  </p>

  <p>
    Try to let the conversation happen directly between your child and Star
    rather than asking questions on your child's behalf.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1–2: Learning the Game</h4>

  <p>
    During the first two rounds, Star provides a lot of guidance and examples.
  </p>

  <p>
    Star may say things like:
  </p>

  <ul>
    <li>"You can ask me if it's big."</li>
    <li>"You can ask me if it can fly."</li>
    <li>"You can ask me what color it is."</li>
    <li>"You can ask me where it lives."</li>
  </ul>

  <p>
    If your child gets stuck, Star will often suggest specific questions they
    can ask next.
  </p>

  <p>
    The purpose of these rounds is to help your child learn the format of the
    game and become comfortable asking Star questions.
  </p>

  <h4>Rounds 3–4: Generating Questions</h4>

  <p>
    During the next two rounds, Star begins providing less direct guidance.
  </p>

  <p>
    Instead of suggesting exact questions, Star may encourage your child to
    think about what information would be helpful.
  </p>

  <p>
    Star may say things like:
  </p>

  <ul>
    <li>"What would you like to ask first?"</li>
    <li>"What would help you figure it out?"</li>
    <li>"You could ask about what it looks like."</li>
    <li>"You could ask where it lives."</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child begin coming up with
    their own questions while still receiving some support from Star.
  </p>

  <h4>Rounds 5–6: Leading the Conversation</h4>

  <p>
    During the final rounds, Star provides only minimal guidance.
  </p>

  <p>
    Your child is encouraged to decide what questions to ask, what clues are
    important, and when they are ready to make a guess.
  </p>

  <p>
    Star may still provide hints when asked, but your child is now leading
    most of the conversation.
  </p>

  <p>
    The purpose of these rounds is to help your child independently initiate
    questions and guide the interaction.
  </p>

  <h4>If Your Child Gets Stuck</h4>

  <p>
    If your child is unsure what to ask, encourage them to think about what
    information would help them learn more about the animal.
  </p>

  <p>
    They can also ask Star for a hint at any time.
  </p>

  <p>
    The goal is not to ask perfect questions. The goal is to practice taking
    the lead in a conversation by asking questions and gathering information.
  </p>
`,
  "4": `
  <h3>Instructions Coming Soon</h3>

  <p>
    This activity is currently in active development.
  </p>

  <p>
    We are continuing to refine the activity experience and will provide
    detailed instructions, parent guidance, and activity goals once development
    is complete.
  </p>
`,
  "5": `
  <h3>Purpose</h3>

  <p>
    Toy Trivia is designed to help your child practice speaking directly
    with the Toy Store Worker through a guessing game.
  </p>

  <p>
    Your child thinks of a toy, and the Toy Store Worker asks questions to figure it out.
    As the rounds continue, the Toy Store Worker gradually asks questions that require more
    information from your child.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Start the video call with the Toy Store Worker.</li>
    <li>Have your child think of a toy silently in their head.</li>
    <li>The Toy Store Worker will ask questions about the toy.</li>
    <li>Your child answers out loud.</li>
    <li>The Toy Store Worker uses the answers to guess the toy.</li>
    <li>After the toy is guessed correctly, your child can think of a new toy for the next round.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, the Toy Store Worker is the main conversation partner.
    Your role is mostly to stay nearby and let the conversation happen directly
    between your child and the Toy Store Worker.
  </p>

  <p>
    If your child seems unsure, you can give a small prompt like:
  </p>

  <ul>
    <li>"What should we tell the Toy Store Worker?"</li>
    <li>"What clue would help?"</li>
    <li>"What do you think?"</li>
  </ul>

  <p>
    Try not to answer for your child right away. Also avoid making speaking
    feel like a big event. The goal is for talking to the Toy Store Worker to feel like a normal
    part of the game.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1–3: Simple Answers</h4>

  <p>
    In the first few rounds, the Toy Store Worker asks mostly straightforward questions.
    Many questions can be answered with one word or by choosing between options.
  </p>

  <p>
    The Toy Store Worker may ask things like:
  </p>

  <ul>
    <li>"Is it big or small?"</li>
    <li>"Is it soft or hard?"</li>
    <li>"Is it a toy people play with indoors or outdoors?"</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child answer directly in a
    simple, predictable way.
  </p>

  <h4>Rounds 4–6: Giving More Information</h4>

  <p>
    In the next few rounds, the Toy Store Worker may ask follow-up questions that require a
    little more information.
  </p>

  <p>
    For example, if your child says the toy has one main color, the Toy Store Worker may ask:
  </p>

  <ul>
    <li>"What is the toy's main color?"</li>
  </ul>

  <p>
    These questions are still about clear, concrete details, but your child may
    need to give more than a yes/no answer.
  </p>

  <p>
    The purpose of these rounds is to help your child practice giving useful details.
  </p>

  <h4>Rounds 7–9: Giving Hints</h4>

  <p>
    In the later rounds, the Toy Store Worker may occasionally ask more open-ended questions.
  </p>

  <p>
    The Toy Store Worker may ask things like:
  </p>

  <ul>
    <li>"Can you give me a hint?"</li>
    <li>"What's something important I should know about your toy?"</li>
    <li>"Can you help me figure it out?"</li>
  </ul>

  <p>
    These questions have many possible answers. Your child is no longer only
    answering questions; they are helping decide what information is most useful.
  </p>

  <p>
    The purpose of these rounds is to help your child practice generating and
    sharing information during a conversation.
  </p>

  <h4>If Your Child Does Not Respond</h4>

  <p>
    If your child does not answer right away, give them time.
  </p>

  <p>
    If they still do not respond, keep the mood calm and let the game continue.
    The goal is repeated direct practice, not forcing every response.
  </p>
`,
  "6": `
  <h3>Purpose</h3>

  <p>
    Toy Guessing Game is designed to help your child practice asking questions and
    leading a conversation with the Toy Store Worker.
  </p>

  <p>
    The Toy Store Worker thinks of a toy, and your child asks questions to figure out what
    it is. The more information your child gathers, the easier it becomes to
    make a good guess.
  </p>

  <p>
    Unlike Toy Trivia, where the Toy Store Worker asks the questions, this activity encourages
    your child to take the lead by deciding what they would like to ask next.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>The Toy Store Worker thinks of a toy.</li>
    <li>Your child asks questions.</li>
    <li>The Toy Store Worker answers the questions.</li>
    <li>Your child uses the clues to figure out the toy.</li>
    <li>Your child makes a guess.</li>
    <li>If the guess is incorrect, the conversation continues.</li>
    <li>If the guess is correct, the round is complete.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, your child is encouraged to lead the conversation.
  </p>

  <p>
    Whenever possible, allow your child to ask questions directly to the Toy Store Worker.
  </p>

  <p>
    If your child gets stuck, you can gently remind them that they can ask about:
  </p>

  <ul>
    <li>What the toy looks like</li>
    <li>What color the toy is</li>
    <li>What the toy is used for</li>
    <li>Whether the toy is soft, hard, big, or small</li>
    <li>Any other clue they would like to know</li>
  </ul>

  <p>
    If your child is unsure what to ask, they can always ask the Toy Store Worker for a hint.
  </p>

  <p>
    Try to let the conversation happen directly between your child and the Toy Store Worker
    rather than asking questions on your child's behalf.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1–2: Learning the Game</h4>

  <p>
    During the first two rounds, the Toy Store Worker provides a lot of guidance and examples.
  </p>

  <p>
    The Toy Store Worker may say things like:
  </p>

  <ul>
    <li>"You can ask me if it's big."</li>
    <li>"You can ask me what color it is."</li>
    <li>"You can ask me what it is used for."</li>
    <li>"You can ask me if it's soft."</li>
  </ul>

  <p>
    If your child gets stuck, the Toy Store Worker will often suggest specific questions they
    can ask next.
  </p>

  <p>
    The purpose of these rounds is to help your child learn the format of the
    game and become comfortable asking questions.
  </p>

  <h4>Rounds 3–4: Generating Questions</h4>

  <p>
    During the next two rounds, the Toy Store Worker begins providing less direct guidance.
  </p>

  <p>
    Instead of suggesting exact questions, the Toy Store Worker may encourage your child to
    think about what information would be helpful.
  </p>

  <p>
    The Toy Store Worker may say things like:
  </p>

  <ul>
    <li>"What would you like to ask first?"</li>
    <li>"What would help you figure it out?"</li>
    <li>"You could ask what it looks like."</li>
    <li>"You could ask what people do with it."</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child begin coming up with
    their own questions while still receiving some support.
  </p>

  <h4>Rounds 5–6: Leading the Conversation</h4>

  <p>
    During the final rounds, the Toy Store Worker provides only minimal guidance.
  </p>

  <p>
    Your child is encouraged to decide what questions to ask, what clues are
    important, and when they are ready to make a guess.
  </p>

  <p>
    The Toy Store Worker may still provide hints when asked, but your child is now leading
    most of the conversation.
  </p>

  <p>
    The purpose of these rounds is to help your child independently initiate
    questions and guide the interaction.
  </p>

  <h4>If Your Child Gets Stuck</h4>

  <p>
    If your child is unsure what to ask, encourage them to think about what
    information would help them learn more about the toy.
  </p>

  <p>
    They can also ask the Toy Store Worker for a hint at any time.
  </p>

  <p>
    The goal is not to ask perfect questions. The goal is to practice taking
    the lead in a conversation by asking questions and gathering information.
  </p>
`,
"7": `
  <h3>Instructions Coming Soon</h3>

  <p>
    This activity is currently in active development.
  </p>

  <p>
    We are continuing to refine the activity experience and will provide
    detailed instructions, parent guidance, and activity goals once development
    is complete.
  </p>
`,
"8": `
  <h3>Purpose</h3>

  <p>
    Book Mystery is designed to help your child practice speaking directly
    with the Teacher through a guessing game.
  </p>

  <p>
    Your child thinks of a book, and the Teacher asks questions to figure it out.
    As the rounds continue, the Teacher gradually asks questions that require more
    information from your child.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>Start the video call with the Teacher.</li>
    <li>Have your child think of a book silently in their head.</li>
    <li>The Teacher will ask questions about the book.</li>
    <li>Your child answers out loud.</li>
    <li>The Teacher uses the answers to guess the book.</li>
    <li>After the book is guessed correctly, your child can think of a new book for the next round.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, the Teacher is the main conversation partner.
    Your role is mostly to stay nearby and let the conversation happen directly
    between your child and the Teacher.
  </p>

  <p>
    If your child seems unsure, you can give a small prompt like:
  </p>

  <ul>
    <li>"What should we tell the Teacher?"</li>
    <li>"What clue would help?"</li>
    <li>"What do you think?"</li>
  </ul>

  <p>
    Try not to answer for your child right away. Also avoid making speaking
    feel like a big event.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1–3: Simple Answers</h4>

  <p>
    In the first few rounds, the Teacher asks mostly straightforward questions.
  </p>

  <ul>
    <li>"Is it a fiction or nonfiction book?"</li>
    <li>"Is it a long book or a short book?"</li>
    <li>"Is it about animals, people, or something else?"</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child answer directly in a
    simple, predictable way.
  </p>

  <h4>Rounds 4–6: Giving More Information</h4>

  <p>
    In the next few rounds, the Teacher may ask follow-up questions that require
    a little more information.
  </p>

  <ul>
    <li>"What color is the cover?"</li>
    <li>"Who is the main character?"</li>
    <li>"What is the book mostly about?"</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child practice giving useful details.
  </p>

  <h4>Rounds 7–9: Giving Hints</h4>

  <p>
    In the later rounds, the Teacher may occasionally ask more open-ended questions.
  </p>

  <ul>
    <li>"Can you give me a hint?"</li>
    <li>"What's something important I should know about the book?"</li>
    <li>"Can you help me figure it out?"</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child practice generating and
    sharing information during a conversation.
  </p>

  <h4>If Your Child Does Not Respond</h4>

  <p>
    If your child does not answer right away, give them time.
  </p>

  <p>
    If they still do not respond, keep the mood calm and let the game continue.
  </p>
`,
"9": `
  <h3>Purpose</h3>

  <p>
    Classroom Guessing Game is designed to help your child practice asking questions and
    leading a conversation with the Teacher.
  </p>

  <p>
    The Teacher thinks of an object that might be found in a classroom or at school,
    and your child asks questions to figure out what it is.
  </p>

  <p>
    Unlike Book Mystery, where the Teacher asks the questions, this activity encourages
    your child to take the lead by deciding what they would like to ask next.
  </p>

  <h3>How to Play</h3>

  <ol>
    <li>The Teacher thinks of a classroom object.</li>
    <li>Your child asks questions.</li>
    <li>The Teacher answers the questions.</li>
    <li>Your child uses the clues to figure out the object.</li>
    <li>Your child makes a guess.</li>
    <li>If the guess is incorrect, the conversation continues.</li>
    <li>If the guess is correct, the round is complete.</li>
  </ol>

  <h3>Your Role</h3>

  <p>
    In this activity, your child is encouraged to lead the conversation.
  </p>

  <p>
    Whenever possible, allow your child to ask questions directly to the Teacher.
  </p>

  <p>
    If your child gets stuck, you can gently remind them that they can ask about:
  </p>

  <ul>
    <li>What the object looks like</li>
    <li>What color it is</li>
    <li>What it is used for</li>
    <li>Where it is usually found</li>
    <li>Any other clue they would like to know</li>
  </ul>

  <p>
    If your child is unsure what to ask, they can always ask the Teacher for a hint.
  </p>

  <h3>What to Expect During the Rounds</h3>

  <h4>Rounds 1–2: Learning the Game</h4>

  <p>
    During the first two rounds, the Teacher provides a lot of guidance and examples.
  </p>

  <ul>
    <li>"You can ask me what color it is."</li>
    <li>"You can ask me what it is used for."</li>
    <li>"You can ask me where it is usually found."</li>
    <li>"You can ask me if students use it."</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child learn the format of the
    game and become comfortable asking questions.
  </p>

  <h4>Rounds 3–4: Generating Questions</h4>

  <p>
    During the next two rounds, the Teacher begins providing less direct guidance.
  </p>

  <ul>
    <li>"What would you like to ask first?"</li>
    <li>"What would help you figure it out?"</li>
    <li>"You could ask what it is used for."</li>
    <li>"You could ask where you might see it."</li>
  </ul>

  <p>
    The purpose of these rounds is to help your child begin coming up with
    their own questions while still receiving some support.
  </p>

  <h4>Rounds 5–6: Leading the Conversation</h4>

  <p>
    During the final rounds, the Teacher provides only minimal guidance.
  </p>

  <p>
    Your child is encouraged to decide what questions to ask, what clues are
    important, and when they are ready to make a guess.
  </p>

  <p>
    The Teacher may still provide hints when asked, but your child is now leading
    most of the conversation.
  </p>

  <p>
    The purpose of these rounds is to help your child independently initiate
    questions and guide the interaction.
  </p>

  <h4>If Your Child Gets Stuck</h4>

  <p>
    If your child is unsure what to ask, encourage them to think about what
    information would help them learn more about the object.
  </p>

  <p>
    They can also ask the Teacher for a hint at any time.
  </p>

  <p>
    The goal is not to ask perfect questions. The goal is to practice taking
    the lead in a conversation by asking questions and gathering information.
  </p>
`,
};

const viewInstructionsBtn = document.getElementById("viewInstructionsBtn");
const instructionsModal = document.getElementById("instructionsModal");
const closeInstructionsBtn = document.getElementById("closeInstructionsBtn");
const instructionsTitle = document.getElementById("instructionsTitle");
const instructionsContent = document.getElementById("instructionsContent");

if (viewInstructionsBtn && instructionsModal && instructionsTitle && instructionsContent) {
  viewInstructionsBtn.addEventListener("click", function () {
    const activityId = this.dataset.activityId;
    const activityName = this.dataset.activityName || "Activity";

    instructionsTitle.textContent = `${activityName} Instructions`;
    instructionsContent.innerHTML =
      instructionsByActivityId[activityId] ||
      "<p>Follow the on-screen prompts and support your child through the activity.</p>";

    instructionsModal.classList.add("active");
  });
}

if (closeInstructionsBtn && instructionsModal) {
  closeInstructionsBtn.addEventListener("click", function () {
    instructionsModal.classList.remove("active");
  });
}

if (instructionsModal) {
  instructionsModal.addEventListener("click", function (event) {
    if (event.target === instructionsModal) {
      instructionsModal.classList.remove("active");
    }
  });
}

document.addEventListener("keydown", function (event) {
  if (event.key === "Escape" && instructionsModal) {
    instructionsModal.classList.remove("active");
  }
});

  function drawJourneyConnector() {
    const pathContainer = document.querySelector(".journey-path");
    const svg = document.querySelector(".journey-connector-svg");
    const items = [...document.querySelectorAll(".journey-path-item")];
    const nodes = [...document.querySelectorAll(".journey-node")];

    if (!pathContainer || !svg || nodes.length < 2) return;

    const containerRect = pathContainer.getBoundingClientRect();

    svg.setAttribute(
      "viewBox",
      `0 0 ${pathContainer.offsetWidth} ${pathContainer.offsetHeight}`
    );

    svg.innerHTML = `<defs id="journeyGradientDefs"></defs>`;

    const defs = svg.querySelector("#journeyGradientDefs");

    for (let i = 0; i < nodes.length - 1; i++) {
      const currentItem = items[i];
      const nextItem = items[i + 1];

      const currentNode = nodes[i];
      const nextNode = nodes[i + 1];

      const currentRect = currentNode.getBoundingClientRect();
      const nextRect = nextNode.getBoundingClientRect();

      const startX = currentRect.left + currentRect.width / 2 - containerRect.left;
      const startY = currentRect.bottom - containerRect.top;

      const endX = nextRect.left + nextRect.width / 2 - containerRect.left;
      const endY = nextRect.top - containerRect.top + 7;

      const midY = (startY + endY) / 2;

      const fromColor = getJourneyColor(currentItem, currentNode);
      const toColor = getJourneyColor(nextItem, nextNode);

      const gradientId = `journey-gradient-${i}`;

      const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
      gradient.setAttribute("id", gradientId);
      gradient.setAttribute("x1", startX);
      gradient.setAttribute("y1", startY);
      gradient.setAttribute("x2", endX);
      gradient.setAttribute("y2", endY);
      gradient.setAttribute("gradientUnits", "userSpaceOnUse");

      gradient.innerHTML = `
        <stop offset="0%" stop-color="${fromColor}" />
        <stop offset="100%" stop-color="${toColor}" />
      `;

      defs.appendChild(gradient);

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");

      path.setAttribute(
        "d",
        `
        M ${startX} ${startY}
        C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}
        `
      );

      path.setAttribute("fill", "none");
      path.setAttribute("stroke", `url(#${gradientId})`);
      path.setAttribute("stroke-width", "5");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");

      svg.appendChild(path);
    }
  }

  drawJourneyConnector();
  window.addEventListener("resize", drawJourneyConnector);
});