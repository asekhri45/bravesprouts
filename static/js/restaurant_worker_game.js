document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".restaurant-page");
  if (!page) return;

  const activityId = Number(page.dataset.activityId || 10);
  const childName = (page.dataset.childName || "there").trim() || "there";

  function dlog(...args) { if (window.APP_DEBUG) console.log(`[restaurant_worker_game:${activityId}]`, ...args); }

  const invite = document.getElementById("restaurantInvite");
  const startBtn = document.getElementById("startRestaurantBtn");
  const stage = document.getElementById("restaurantStage");
  const socialStageChip = document.getElementById("socialStageChip");
  const micPill = document.getElementById("micPill");
  const orderIndexText = document.getElementById("orderIndexText");
  const orderTitle = document.getElementById("orderTitle");
  const orderIcon = document.getElementById("orderIcon");
  const stepKicker = document.getElementById("stepKicker");
  const stepTitle = document.getElementById("stepTitle");
  const stepInstruction = document.getElementById("stepInstruction");
  const stepAsset = document.getElementById("stepAsset");
  const stepDots = document.getElementById("stepDots");
  const stepList = document.getElementById("stepList");
  const workZone = document.getElementById("workZone");
  const gentlePrompt = document.getElementById("gentlePrompt");
  const doneStepBtn = document.getElementById("doneStepBtn");
  const teacherSlot = document.getElementById("teacherSlot");
  const workerSlot = document.getElementById("workerSlot");
  const teacherMouth = document.getElementById("teacherMouth");
  const workerCharacter = document.getElementById("workerCharacter");

  const TEACHER = "teacher";
  const WORKER = "worker";
  const TARGET_ORDERS = 8;

  const ASSET_ROOT = "/static/images/restaurant/";
  const restaurantAsset = name => `${ASSET_ROOT}${name}`;

  const STEP_ASSETS = {
    sauce: "sauce-brush.svg",
    cheese: "cheese.svg",
    pepperoni: "pepperoni.svg",
    veggies: "veggies.svg",
    salad: "salad.svg",
    grilled: "grilled-cheese.svg",
    lemonade: "lemonade.svg",
    sundae: "sundae.svg",
    kids: "kids-meal.svg",
    chef: "chef.svg"
  };

  const FOOD_EMOJI = {
    pepperoni: "🔴",
    mushroom: "🍄",
    pepper: "🫑",
    tomato: "🍅",
    olive: "🫒",
    lettuce: "🥬",
    cucumber: "🥒",
    cheese: "🧀",
    bread: "🍞",
    lemon: "🍋",
    ice: "🧊",
    water: "💧",
    stir: "🥄",
    scoop: "🍨",
    syrup: "🍫",
    sprinkles: "✨",
    cherry: "🍒",
    fries: "🍟",
    burger: "🍔",
    drink: "🥤",
    apple: "🍎"
  };

  const ORDERS = [
    {
      id: "cheese_pizza",
      title: "Cheese Pizza",
      icon: "🍕",
      stageText: "Stage 1 · Teacher leads",
      finishLine: "The chef can bake it now, and I can bring it to the customer.",
      steps: [
        step("sauce", "paint_sauce", "Spread the sauce", "Paint the sauce all over the crust.", "sauce", 0.66, {
          guide: ["Let's start by spreading the sauce.", "First, paint the tomato sauce over the crust.", "We can start with sauce. Cover the crust as much as you want."],
          praise: ["Great job. That sauce is looking really good.", "Perfect. The pizza is already coming together.", "Nice work spreading the sauce."],
          wonder: ["I wonder if this customer likes lots of sauce.", "I wonder if the sauce should reach all the way to the edges."],
          direct: ["{child}, do you think the sauce is ready?", "{child}, should we move to the cheese now?"]
        }),
        step("cheese", "sprinkle_cheese", "Add the cheese", "Sprinkle cheese wherever you think it should go.", "cheese", 0.68, {
          requiredCount: 34,
          guide: ["Now sprinkle the cheese.", "Next, add cheese all over the sauce.", "You can sprinkle the cheese wherever it looks good."],
          praise: ["Wow. That cheese looks delicious.", "Nice sprinkling. The customer will like this.", "That is a great cheese pizza."],
          wonder: ["I wonder if this customer likes a little cheese or lots of cheese.", "I wonder where the cheesiest bite will be."],
          direct: ["{child}, does this have enough cheese?", "{child}, should we send this one to the oven?"]
        })
      ]
    },
    {
      id: "pepperoni_pizza",
      title: "Pepperoni Pizza",
      icon: "🍕",
      stageText: "Stage 1 · Teacher leads",
      finishLine: "The chef can bake it now. I can bring it to the customer when it is ready.",
      steps: [
        step("sauce", "paint_sauce", "Spread the sauce", "Paint sauce on the crust.", "sauce", 0.60, {
          guide: ["Let's start this pepperoni pizza with sauce.", "First, paint the sauce on the crust."],
          praise: ["Nice. You remembered the sauce step.", "That sauce is looking great."],
          wonder: ["I wonder if this pizza will smell amazing when it bakes.", "I wonder if the pepperoni will go on top soon."],
          direct: ["{child}, is the sauce ready?", "{child}, should we move to cheese?"]
        }),
        step("cheese", "sprinkle_cheese", "Sprinkle cheese", "Sprinkle cheese over the sauce.", "cheese", 0.60, {
          requiredCount: 28,
          guide: ["Now add cheese.", "Sprinkle some cheese over the sauce."],
          praise: ["Great. The cheese is looking good.", "Nice job. This is almost ready for pepperoni."],
          wonder: ["I wonder where the pepperoni will go.", "I wonder if each slice will get some cheese."],
          direct: ["{child}, is there enough cheese?", "{child}, should we add pepperoni now?"]
        }),
        step("pepperoni", "place_pizza_items", "Place pepperoni", "Put pepperoni around the pizza. Try to give different slices some toppings.", "pepperoni", 0.72, {
          item: "pepperoni",
          requiredCount: 12,
          guide: ["Now place the pepperoni pieces.", "Next, add pepperoni wherever it looks good."],
          praise: ["Wow. That pepperoni looks great.", "Nice placing. Each slice is getting toppings."],
          wonder: ["I wonder which slice will have the most pepperoni.", "I wonder if every slice should get one piece."],
          direct: ["{child}, is there enough pepperoni?", "{child}, should I send this to the chef?"]
        })
      ]
    },
    {
      id: "veggie_pizza",
      title: "Veggie Pizza",
      icon: "🍕",
      stageText: "Stage 2 · Leo wonders",
      finishLine: "The chef will bake it now. I can bring it out when it is ready.",
      steps: [
        step("sauce", "paint_sauce", "Spread sauce", "Paint the sauce over the crust.", "sauce", 0.58, {
          guide: ["Let's start the veggie pizza with sauce.", "First, paint the sauce on this crust."],
          praise: ["That is a good start.", "Great sauce spreading."],
          wonder: ["I wonder which veggies this customer picked.", "I wonder if the pizza will look colorful soon."],
          direct: ["{child}, is the sauce ready?", "{child}, should we move on?"]
        }),
        step("cheese", "sprinkle_cheese", "Add cheese", "Sprinkle cheese over the sauce.", "cheese", 0.56, {
          requiredCount: 25,
          guide: ["Now add some cheese.", "Sprinkle cheese before the vegetables."],
          praise: ["Nice. That cheese will help hold the vegetables.", "Great job sprinkling."],
          wonder: ["I wonder if the veggies will go on top of this cheese.", "I wonder where the mushrooms will go."],
          direct: ["{child}, enough cheese?", "{child}, ready for vegetables?"]
        }),
        step("veggies", "place_pizza_items", "Add vegetables", "Add mushrooms, peppers, tomatoes, and olives.", "veggies", 0.80, {
          itemSet: ["mushroom", "pepper", "tomato", "olive"],
          requiredCount: 14,
          guide: ["Now we can add the vegetables.", "Put the vegetables wherever they look tasty."],
          praise: ["That veggie pizza looks colorful.", "Nice. The customer will like all those veggies."],
          wonder: ["I wonder if the customer likes mushrooms or peppers more.", "I wonder which color looks best on this pizza."],
          direct: ["{child}, does this veggie pizza look ready?", "{child}, should I send this to the chef?"]
        })
      ]
    },
    {
      id: "garden_salad",
      title: "Garden Salad",
      icon: "🥗",
      stageText: "Stage 2 · Leo wonders",
      finishLine: "I can bring the salad to the customer. You helped make it look fresh.",
      steps: [
        step("lettuce", "bowl_items", "Add lettuce", "Tap or drag lettuce into the bowl.", "salad", 0.75, {
          itemSet: ["lettuce"],
          requiredCount: 8,
          guide: ["This order is a garden salad. Let's start with lettuce.", "Put some lettuce in the bowl first."],
          praise: ["Fresh lettuce. Nice job.", "That is a good salad start."],
          wonder: ["I wonder if this salad will be crunchy.", "I wonder how much lettuce this bowl needs."],
          direct: ["{child}, is there enough lettuce?", "{child}, ready for vegetables?"]
        }),
        step("veggies", "bowl_items", "Add vegetables", "Add tomatoes and cucumbers to the salad.", "veggies", 0.78, {
          itemSet: ["tomato", "cucumber"],
          requiredCount: 10,
          guide: ["Now add tomatoes and cucumbers.", "Put the vegetables in the bowl."],
          praise: ["That salad is getting colorful.", "Nice. Those vegetables look fresh."],
          wonder: ["I wonder if the customer likes tomatoes or cucumbers more.", "I wonder if this salad needs one more tomato."],
          direct: ["{child}, does it have enough vegetables?", "{child}, should we toss the salad?"]
        }),
        step("toss", "toss_bowl", "Toss the salad", "Move around the bowl to mix everything together.", "salad", 1, {
          requiredCount: 12,
          guide: ["Now we can gently toss the salad.", "Mix the salad so everything comes together."],
          praise: ["Great mixing. That salad looks ready.", "Nice. Everything is mixed together."],
          wonder: ["I wonder if this salad is ready for the customer.", "I wonder if the customer will like how fresh it looks."],
          direct: ["{child}, does the salad look ready?", "{child}, should I take this to the customer?"]
        })
      ]
    },
    {
      id: "grilled_cheese",
      title: "Grilled Cheese",
      icon: "🥪",
      stageText: "Stage 3 · Leo asks indirectly",
      finishLine: "The chef can handle the hot grill. I can bring it out when it is cooked.",
      steps: [
        step("butter", "butter_bread", "Butter the bread", "Paint butter over the bread.", "grilled", 0.66, {
          guide: ["This one is grilled cheese. Let's butter the bread first.", "Paint butter across the bread."],
          praise: ["Nice buttering. The bread will toast well.", "Great job covering the bread."],
          wonder: ["I wonder if the bread has enough butter.", "I wonder if the chef will toast it soon."],
          direct: ["{child}, is the bread buttered enough?", "{child}, ready for cheese?"]
        }),
        step("cheese", "sandwich_layers", "Add cheese", "Add cheese slices to the bread.", "cheese", 0.78, {
          itemSet: ["cheese"],
          requiredCount: 3,
          guide: ["Now add cheese slices.", "Put the cheese on the bread."],
          praise: ["That looks cheesy.", "Good job adding the cheese."],
          wonder: ["I wonder if this sandwich has enough cheese.", "I wonder if the customer likes melty cheese."],
          direct: ["{child}, enough cheese?", "{child}, ready for the chef?"]
        })
      ]
    },
    {
      id: "lemonade",
      title: "Lemonade",
      icon: "🍋",
      stageText: "Stage 3 · Leo asks indirectly",
      finishLine: "I can carry the lemonade to the customer when the cup is ready.",
      steps: [
        step("ice", "pitcher_items", "Add ice", "Tap to drop ice cubes into the glass.", "lemonade", 0.75, {
          itemSet: ["ice"],
          requiredCount: 4,
          guide: ["This customer ordered lemonade. Start by adding ice to the glass.", "Tap the glass to drop in a few ice cubes."],
          praise: ["Nice. The glass is getting cold.", "Good job adding the ice."],
          wonder: ["I wonder how cold this lemonade will be.", "I wonder if the customer likes lots of ice."],
          direct: ["{child}, is there enough ice?", "{child}, should we squeeze the lemon now?"]
        }),
        step("lemons", "pitcher_items", "Squeeze lemons", "Tap to squeeze lemon juice into the glass.", "lemonade", 0.72, {
          itemSet: ["lemon"],
          requiredCount: 5,
          guide: ["Now squeeze a little lemon juice into the glass.", "Tap to squeeze the lemon juice over the ice."],
          praise: ["That looks bright and lemony.", "Nice. The lemonade is starting."],
          wonder: ["I wonder if it will taste sweet or sour.", "I wonder if it needs another squeeze."],
          direct: ["{child}, is that enough lemon?", "{child}, should we add water?"]
        }),
        step("water", "pitcher_items", "Add water", "Tap to pour water on top of the lemon juice.", "lemonade", 0.76, {
          itemSet: ["water"],
          requiredCount: 6,
          guide: ["Now add water on top of the lemon juice.", "Tap the glass to pour water above the lemon juice."],
          praise: ["Nice. The glass is filling up.", "Good job pouring the water."],
          wonder: ["I wonder if the water is high enough.", "I wonder if the ice is floating now."],
          direct: ["{child}, does it have enough water?", "{child}, ready to stir?"]
        }),
        step("stir", "stir_pitcher", "Stir the lemonade", "Move around the glass to stir it.", "lemonade", 1, {
          requiredCount: 12,
          guide: ["Now stir the lemonade.", "Mix it gently so the lemon juice and water blend together."],
          praise: ["Great stirring. That lemonade looks ready.", "Nice. That looks cold and sweet."],
          wonder: ["I wonder if this drink is ready for me to carry.", "I wonder if the customer will smile when they taste it."],
          direct: ["{child}, is the lemonade ready?", "{child}, should I bring it to the customer?"]
        })
      ]
    },
    {
      id: "sundae",
      title: "Ice Cream Sundae",
      icon: "🍨",
      stageText: "Stage 4 · Leo asks directly",
      finishLine: "I will carry the sundae carefully so it does not spill.",
      steps: [
        step("scoops", "sundae_items", "Add ice cream", "Add ice cream scoops to the bowl.", "sundae", 0.70, {
          itemSet: ["scoop"],
          requiredCount: 3,
          guide: ["This customer ordered an ice cream sundae. Add the scoops first.", "Put ice cream in the bowl."],
          praise: ["Those scoops look great.", "Nice. That sundae is starting."],
          wonder: ["I wonder which scoop looks biggest.", "I wonder if the sundae needs one more scoop."],
          direct: ["{child}, are there enough scoops?", "{child}, should we add toppings?"]
        }),
        step("toppings", "sundae_items", "Add toppings", "Add syrup and sprinkles.", "sundae", 0.78, {
          itemSet: ["syrup", "sprinkles"],
          requiredCount: 9,
          guide: ["Now add syrup and sprinkles.", "Put toppings on the ice cream."],
          praise: ["Wow. That looks fun.", "Nice toppings. The sundae looks special."],
          wonder: ["I wonder if the customer likes sprinkles.", "I wonder if that is enough syrup."],
          direct: ["{child}, are there enough toppings?", "{child}, does this look ready for a cherry?"]
        }),
        step("cherry", "sundae_items", "Add the cherry", "Put one cherry on top.", "sundae", 1, {
          itemSet: ["cherry"],
          requiredCount: 1,
          guide: ["Last step. Add the cherry on top.", "Put one cherry wherever it looks best."],
          praise: ["Perfect. The cherry makes it look finished.", "That sundae looks amazing."],
          wonder: ["I wonder if that cherry is in the perfect spot.", "I wonder if this sundae is ready."],
          direct: ["{child}, is the sundae ready?", "{child}, should I take this to the customer?"]
        })
      ]
    },
    {
      id: "kids_meal",
      title: "Kids Meal",
      icon: "🍔",
      stageText: "Stage 4 · Leo asks directly",
      finishLine: "I will bring the tray to the table. That was our last order together.",
      steps: [
        step("main", "tray_items", "Add the meal", "Put the burger and fries on the tray.", "kids", 0.76, {
          itemSet: ["burger", "fries"],
          requiredCount: 2,
          guide: ["This is the last order. Start with the burger and fries.", "Put the meal on the tray."],
          praise: ["Nice. The tray is starting to look ready.", "Great. The main food is on the tray."],
          wonder: ["I wonder if the fries should go next to the burger.", "I wonder if this is the biggest order today."],
          direct: ["{child}, is the meal on the tray?", "{child}, should we add the drink and fruit?"]
        }),
        step("sides", "tray_items", "Add drink and fruit", "Add the drink and apple to the tray.", "kids", 0.80, {
          itemSet: ["drink", "apple"],
          requiredCount: 2,
          guide: ["Now add the drink and the apple.", "Put the rest of the kids meal on the tray."],
          praise: ["That tray looks balanced.", "Nice. The customer has everything."],
          wonder: ["I wonder if the drink should go in the corner.", "I wonder if the apple makes it feel complete."],
          direct: ["{child}, does the tray have everything?", "{child}, is the kids meal ready?"]
        })
      ]
    }
  ];

  function step(id, type, title, instruction, assetKey, minProgress, extras = {}) {
    return {
      id,
      type,
      title,
      instruction,
      asset: STEP_ASSETS[assetKey] || STEP_ASSETS.chef,
      minProgress,
      requiredCount: extras.requiredCount || 1,
      item: extras.item || null,
      itemSet: extras.itemSet || null,
      guide: extras.guide || [],
      praise: extras.praise || [],
      wonder: extras.wonder || [],
      direct: extras.direct || [],
      readyQuestion: extras.readyQuestion || "Do you think this step is ready?",
      notReadyHint: extras.notReadyHint || "It looks good already. A little more could help before we move on."
    };
  }

  function readyStep(title, instruction) {
    return step("ready", "ready_card", title, instruction, "chef", 1, {
      guide: ["Let's check this order together.", "Now we can decide if this is ready.", "This order looks close to ready."],
      praise: ["Thanks for helping. I can take it from here.", "Great teamwork.", "Nice work finishing this order."],
      wonder: ["Do you think this order is ready for me to take?", "Do you think the customer will like it?"],
      direct: ["{child}, do you think this order is ready?", "{child}, should I take this one now?"]
    });
  }

  let state = freshState();
  let speechQueue = Promise.resolve();
  let activeAudio = null;
  let audioContext = null;
  let analyser = null;
  let sourceNode = null;
  let mouthAnimationFrame = null;
  let activeMouthActor = null;
  let workerFlapUntil = 0;
  let workerNextFlapAt = 0;
  let workerLastFrame = "closed";

  let mediaStream = null;
  let responseRecorder = null;
  let responseChunks = [];
  let responseTimer = null;
  let responseRecognition = null;
  let passiveRecognition = null;
  let passiveRestartTimer = null;
  let stepDoneReminderTimer = null;
  let stepDoneReminderCount = 0;
  let progressCommentTimer = null;

  let currentSceneController = null;
  let currentPointerDown = false;
  let selectedPaletteItem = null;

  const WORKER_FRAME_CANDIDATES = {
    closed: ["restaurant-worker-mouth-closed.png", "restaurant-worker-mouth-small.png"],
    small: ["restaurant-worker-mouth-small.png", "restaurant-worker-mouth-closed.png"],
    medium: ["restaurant-worker-mouth-medium.png", "restaurant-worker-mouth-mid.png", "restaurant-worker-mouth-small.png"],
    wide: ["restaurant-worker-mouth-wide.png", "restaurant-worker-mouth-large.png", "restaurant-worker-mouth-open.png", "restaurant-worker-mouth-medium.png"]
  };
  const workerFrames = {};

  function freshState() {
    return {
      sessionStart: Date.now(),
      orderIndex: 0,
      stepIndex: 0,
      ordersCompleted: 0,
      stepsCompleted: 0,
      spokenResponses: 0,
      spokenWords: 0,
      silentWindows: 0,
      workerDirectResponses: 0,
      teacherRedirects: 0,
      totalChoices: 0,
      moveChoiceCounter: 0,
      isSpeaking: false,
      isListening: false,
      waitingForResponse: false,
      micReady: false,
      micDenied: false,
      gameCompleted: false,
      orderStates: {},
      isReturningSession: false,
      recentLines: [],
      seenInstructionKeys: {},
      specialCommentFlags: {},
      currentProgress: 0
    };
  }

  function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

  function cleanText(text) {
    return String(text || "")
      .replace(/\s+/g, " ")
      .replace(/[!?]+$/g, ".")
      .trim();
  }

  function fillLine(line) {
    const name = childName && childName.toLowerCase() !== "there" ? childName : "";
    return String(line || "").replaceAll("{child}, ", name ? `${name}, ` : "").replaceAll("{child}", name || "you");
  }

  function pickLine(lines, fallback = "Nice work.") {
    const choices = (lines || []).map(fillLine).filter(Boolean);
    if (!choices.length) return fallback;
    const fresh = choices.filter(line => !state.recentLines.includes(line));
    const pool = fresh.length ? fresh : choices;
    const chosen = pool[Math.floor(Math.random() * pool.length)] || fallback;
    state.recentLines.push(chosen);
    if (state.recentLines.length > 24) state.recentLines.shift();
    return chosen;
  }

  function countWords(text) {
    return (String(text || "").toLowerCase().match(/[a-z0-9']+/g) || []).length;
  }

  function currentOrder() { return ORDERS[Math.min(state.orderIndex, ORDERS.length - 1)]; }
  function currentStep() { return currentOrder().steps[Math.min(state.stepIndex, currentOrder().steps.length - 1)]; }

  function socialStageIndex() {
    if (state.orderIndex <= 1) return 1;
    if (state.orderIndex <= 3) return 2;
    if (state.orderIndex <= 5) return 3;
    return 4;
  }

  function isPizzaOrder(order = currentOrder()) { return order.id.includes("pizza"); }

  function orderState(order = currentOrder()) {
    if (!state.orderStates[order.id]) {
      state.orderStates[order.id] = { items: [], sauceDone: false, cheeseDone: false, stepCounts: {}, pitcherFill: 0 };
    }
    return state.orderStates[order.id];
  }

  async function imageLoads(src) {
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
        const src = `/static/images/restaurant/${filename}`;
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
    if (!workerCharacter) return;
    const safeFrame = workerFrames[frame] ? frame : "closed";
    if (workerLastFrame === safeFrame && workerCharacter.src.endsWith((workerFrames[safeFrame] || "").split("/").pop())) return;
    workerLastFrame = safeFrame;
    workerCharacter.src = workerFrames[safeFrame] || workerFrames.closed || workerCharacter.src;
  }

  function teacherMouthSrc(size) {
    const files = {
      closed: "/static/images/librarian-mouth-closed.png",
      small: "/static/images/librarian-mouth-small.png",
      medium: "/static/images/librarian-mouth-medium.png",
      wide: "/static/images/librarian-mouth-wide.png"
    };
    return files[size] || files.closed;
  }

  function setTeacherMouth(size, scaleX = 1, scaleY = 1) {
    if (!teacherMouth) return;
    teacherMouth.src = teacherMouthSrc(size);
    teacherMouth.style.transform = `translateX(-50%) scale(${scaleX}, ${scaleY})`;
  }

  function closeMouths() {
    setTeacherMouth("closed", 1, 1);
    setWorkerFrame("closed");
  }

  function updateMicStatus(label, mode = "idle") {
    if (!micPill) return;
    micPill.classList.toggle("listening", mode === "listening");
    micPill.classList.toggle("speaking", mode === "speaking");
    micPill.classList.add("dot-only");
    micPill.setAttribute("aria-label", label || (mode === "speaking" ? "Talking" : mode === "listening" ? "Listening" : "Microphone status"));

    // Keep the small white status card and colored dot, but remove the text label.
    // Green dot = listening, orange dot = talking, gray dot = idle.
    micPill.style.minWidth = "54px";
    micPill.style.width = "54px";
    micPill.style.padding = "0";
    micPill.style.gap = "0";

    const strong = micPill.querySelector("strong");
    if (strong) {
      strong.textContent = "";
      strong.style.display = "none";
      strong.setAttribute("aria-hidden", "true");
    }
  }

  function setSpeakingActor(actor, on) {
    const slot = actor === WORKER ? workerSlot : teacherSlot;
    if (slot) slot.classList.toggle("speaking", Boolean(on));
  }

  function updateHeader() {
    const order = currentOrder();
    const step = currentStep();
    const orderNum = state.orderIndex + 1;
    if (orderIndexText) orderIndexText.textContent = String(orderNum);
    if (orderTitle) orderTitle.textContent = order.title;
    if (orderIcon) orderIcon.textContent = order.icon;
    if (socialStageChip) socialStageChip.textContent = order.stageText;
    if (stepKicker) stepKicker.textContent = `Step ${state.stepIndex + 1} / ${order.steps.length}`;
    if (stepTitle) stepTitle.textContent = step.title;
    if (stepInstruction) stepInstruction.textContent = step.instruction;
    if (stepAsset) stepAsset.src = restaurantAsset(step.asset || STEP_ASSETS.chef);

    renderStepDots();
    renderStepList();

    if (gentlePrompt) {
      const p = gentlePrompt.querySelector("p");
      if (p) p.textContent = promptForCurrentStep();
    }
  }

  function promptForCurrentStep() {
    const step = currentStep();
    if (step.type === "ready_card") return "Tell us when you think this order is ready.";
    if (step.type === "paint_sauce") return "Tell us when you think the sauce is spread all over.";
    if (step.type === "butter_bread") return "Tell us when you think the bread is buttered.";
    if (step.type.includes("pitcher")) return "Tell us when this drink step feels ready.";
    return "Tell us when this step feels done.";
  }

  function renderStepDots() {
    if (!stepDots) return;
    stepDots.innerHTML = "";
    currentOrder().steps.forEach((_, index) => {
      const dot = document.createElement("span");
      if (index < state.stepIndex) dot.classList.add("done");
      if (index === state.stepIndex) dot.classList.add("active");
      stepDots.appendChild(dot);
    });
  }

  function renderStepList() {
    if (!stepList) return;
    stepList.innerHTML = "";
    const steps = currentOrder().steps;
    steps.forEach((s, index) => {
      if (index === state.stepIndex) return;
      const row = document.createElement("div");
      row.className = "locked-step";
      if (index < state.stepIndex) row.classList.add("done");
      row.innerHTML = `
        <div>
          <span class="mini-kicker">Step ${index + 1}</span>
          <strong>${s.title}</strong>
        </div>
        <span class="lock-icon">${index < state.stepIndex ? "✓" : "🔒"}</span>
      `;
      stepList.appendChild(row);
    });
  }

  function setDoneButton(disabled) {
    if (doneStepBtn) doneStepBtn.disabled = Boolean(disabled);
  }

  function resetSceneController() {
    if (currentSceneController && typeof currentSceneController.destroy === "function") {
      currentSceneController.destroy();
    }
    currentSceneController = null;
    currentPointerDown = false;
    selectedPaletteItem = null;
  }

  function renderCurrentWorkScene() {
    resetSceneController();
    updateHeader();
    state.currentProgress = 0;
    const step = currentStep();
    const os = orderState();

    if (!workZone) return;
    workZone.innerHTML = "";
    setDoneButton(false);

    if (step.type === "paint_sauce") currentSceneController = createPizzaPaintScene("sauce");
    else if (step.type === "sprinkle_cheese") currentSceneController = createPizzaSprinkleScene();
    else if (step.type === "place_pizza_items") currentSceneController = createPizzaItemsScene();
    else if (step.type === "bowl_items") currentSceneController = createBowlItemsScene();
    else if (step.type === "toss_bowl") currentSceneController = createTossBowlScene();
    else if (step.type === "butter_bread") currentSceneController = createButterBreadScene();
    else if (step.type === "sandwich_layers") currentSceneController = createBoardItemsScene("sandwich");
    else if (step.type === "pitcher_items") currentSceneController = createPitcherItemsScene();
    else if (step.type === "stir_pitcher") currentSceneController = createStirPitcherScene();
    else if (step.type === "sundae_items") currentSceneController = createSundaeItemsScene();
    else if (step.type === "tray_items") currentSceneController = createBoardItemsScene("tray");
    else currentSceneController = createReadyScene();

    if (currentSceneController && currentSceneController.progress) {
      state.currentProgress = currentSceneController.progress();
    }

    void saveProgress();
  }

  function createFoodScene(className = "food-scene") {
    const scene = document.createElement("div");
    scene.className = className;
    workZone.appendChild(scene);
    return scene;
  }

  function createPizzaShell({ sauce = false, cheese = false } = {}) {
    const scene = createFoodScene("food-scene pizza-scene");
    scene.innerHTML = `
      <div class="board-shadow"></div>
      <div class="round-board">
        <div class="pizza-base" id="pizzaBase">
          ${sauce ? '<div class="pizza-sauce-fill"></div>' : ''}
          <canvas class="pizza-canvas saved-pizza-canvas" id="savedPizzaCanvas" aria-hidden="true"></canvas>
          <div class="token-layer" id="tokenLayer"></div>
        </div>
      </div>
    `;

    const pizzaBase = scene.querySelector("#pizzaBase");
    const tokenLayer = scene.querySelector("#tokenLayer");
    const savedCanvas = scene.querySelector("#savedPizzaCanvas");

    requestAnimationFrame(() => {
      const os = orderState();
      renderSavedSauceCanvas(savedCanvas, pizzaBase, os);
      renderSavedPizzaTokens(tokenLayer, pizzaBase, os, { includeCheese: cheese || Boolean(os.cheeseTokens?.length), includeToppings: true });
    });

    return { scene, pizzaBase, tokenLayer, savedCanvas };
  }



  function pizzaOvalForRect(rect) {
    return {
      cx: rect.width * 0.50,
      cy: rect.height * 0.50,
      rx: rect.width * 0.385,
      ry: rect.height * 0.335
    };
  }

  function pointInOval(x, y, oval, pad = 1) {
    const nx = (x - oval.cx) / (oval.rx * pad);
    const ny = (y - oval.cy) / (oval.ry * pad);
    return nx * nx + ny * ny <= 1;
  }

  function renderSavedSauceCanvas(canvas, pizzaBase, os) {
    if (!canvas || !pizzaBase || !os) return;
    if (!os.sauceDone && !Array.isArray(os.sauceStrokes)) return;

    const rect = pizzaBase.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(2, Math.round(rect.width * dpr));
    canvas.height = Math.max(2, Math.round(rect.height * dpr));
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;

    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const oval = pizzaOvalForRect(rect);

    ctx.save();
    ctx.beginPath();
    ctx.ellipse(oval.cx, oval.cy, oval.rx, oval.ry, 0, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = "#d83a30";
    ctx.globalAlpha = .90;

    if (Array.isArray(os.sauceStrokes) && os.sauceStrokes.length) {
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#d83a30";
      ctx.lineWidth = Math.max(26, rect.width * .07);
      os.sauceStrokes.forEach(stroke => {
        if (!Array.isArray(stroke) || stroke.length < 1) return;
        ctx.beginPath();
        stroke.forEach((pt, idx) => {
          const x = pt.x * rect.width;
          const y = pt.y * rect.height;
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      });
    } else if (os.sauceDone) {
      ctx.beginPath();
      ctx.ellipse(oval.cx, oval.cy, oval.rx, oval.ry, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  function renderSavedPizzaTokens(tokenLayer, pizzaBase, os, opts = {}) {
    if (!tokenLayer || !pizzaBase || !os) return;
    const w = pizzaBase.clientWidth || 1;
    const h = pizzaBase.clientHeight || 1;

    if (opts.includeCheese && Array.isArray(os.cheeseTokens)) {
      os.cheeseTokens.forEach(saved => {
        const bit = document.createElement("div");
        bit.className = "food-token cheese-bit";
        bit.style.left = `${saved.x * w}px`;
        bit.style.top = `${saved.y * h}px`;
        bit.style.setProperty("--rot", saved.rot || `${rand(-85, 85)}deg`);
        bit.style.setProperty("--scale", saved.scale || rand(.82, 1.18).toFixed(2));
        tokenLayer.appendChild(bit);
      });
    }

    if (opts.includeToppings && Array.isArray(os.pizzaTokens)) {
      os.pizzaTokens.forEach(saved => {
        addToken(tokenLayer, saved.item, saved.x * w, saved.y * h);
      });
    }
  }

  function createPizzaPaintScene() {
    const { scene, pizzaBase } = createPizzaShell();
    const canvas = document.createElement("canvas");
    canvas.className = "pizza-canvas";
    pizzaBase.appendChild(canvas);

    const ctx = canvas.getContext("2d");
    const grid = new Set();
    const os = orderState();
    if (!Array.isArray(os.sauceStrokes)) os.sauceStrokes = [];
    let lastPoint = null;
    let activeStroke = null;

    function resize() {
      const rect = pizzaBase.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(2, Math.round(rect.width * dpr));
      canvas.height = Math.max(2, Math.round(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      renderSavedSauceCanvas(canvas, pizzaBase, os);
    }

    function markCoverageAt(x, y, rect) {
      const oval = pizzaOvalForRect(rect);
      if (!pointInOval(x, y, oval, 1.02)) return;

      const gx = Math.floor(((x - (oval.cx - oval.rx)) / (oval.rx * 2)) * 24);
      const gy = Math.floor(((y - (oval.cy - oval.ry)) / (oval.ry * 2)) * 20);

      for (let yy = gy - 2; yy <= gy + 2; yy += 1) {
        for (let xx = gx - 2; xx <= gx + 2; xx += 1) {
          if (xx >= 0 && xx < 24 && yy >= 0 && yy < 20) {
            const cellCx = ((xx + 0.5) / 24) * 2 - 1;
            const cellCy = ((yy + 0.5) / 20) * 2 - 1;
            if (cellCx * cellCx + cellCy * cellCy <= 1.08) grid.add(`${xx},${yy}`);
          }
        }
      }

      updateProgress(Math.min(1, grid.size / 245));
    }

    function paintAt(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      const oval = pizzaOvalForRect(rect);

      if (!pointInOval(x, y, oval, 1.03)) return;

      const radius = Math.max(24, rect.width * 0.064);

      ctx.save();
      ctx.beginPath();
      ctx.ellipse(oval.cx, oval.cy, oval.rx, oval.ry, 0, 0, Math.PI * 2);
      ctx.clip();

      ctx.globalAlpha = 0.90;
      ctx.strokeStyle = "#d83a30";
      ctx.fillStyle = "#d83a30";
      ctx.lineWidth = radius * 1.95;

      if (lastPoint) {
        ctx.beginPath();
        ctx.moveTo(lastPoint.x, lastPoint.y);
        ctx.lineTo(x, y);
        ctx.stroke();

        const distance = Math.hypot(x - lastPoint.x, y - lastPoint.y);
        const samples = Math.max(2, Math.ceil(distance / 14));
        for (let i = 0; i <= samples; i += 1) {
          const tx = lastPoint.x + (x - lastPoint.x) * (i / samples);
          const ty = lastPoint.y + (y - lastPoint.y) * (i / samples);
          markCoverageAt(tx, ty, rect);
        }
      } else {
        ctx.beginPath();
        ctx.arc(x, y, radius * 0.72, 0, Math.PI * 2);
        ctx.fill();
        markCoverageAt(x, y, rect);
      }

      ctx.restore();
      lastPoint = { x, y };

      if (activeStroke) {
        activeStroke.push({ x: x / rect.width, y: y / rect.height });
        if (activeStroke.length > 80) activeStroke.shift();
      }
    }

    function onDown(event) {
      currentPointerDown = true;
      lastPoint = null;
      activeStroke = [];
      os.sauceStrokes.push(activeStroke);
      canvas.setPointerCapture?.(event.pointerId);
      paintAt(event.clientX, event.clientY);
      maybeCommentDuringInteraction();
    }

    function onMove(event) {
      if (currentPointerDown) paintAt(event.clientX, event.clientY);
    }

    function onUp() {
      currentPointerDown = false;
      lastPoint = null;
      activeStroke = null;
    }

    resize();
    window.addEventListener("resize", resize);
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);

    return {
      progress: () => state.currentProgress,
      destroy: () => window.removeEventListener("resize", resize)
    };
  }



  function makeCircleCells(size) {
    const cells = new Set();
    const center = (size - 1) / 2;
    const radius = size * 0.42;
    for (let y = 0; y < size; y += 1) {
      for (let x = 0; x < size; x += 1) {
        const dx = x - center;
        const dy = y - center;
        if (Math.sqrt(dx * dx + dy * dy) <= radius) cells.add(`${x},${y}`);
      }
    }
    return cells;
  }

  function createPizzaSprinkleScene() {
    const { pizzaBase, tokenLayer } = createPizzaShell({ sauce: true, cheese: true });
    const step = currentStep();
    const os = orderState();
    if (!Array.isArray(os.cheeseTokens)) os.cheeseTokens = [];
    let count = 0;
    let lastAt = 0;

    function sprinkle(clientX, clientY, force = false) {
      const now = Date.now();
      if (!force && now - lastAt < 42) return;
      lastAt = now;
      const rect = pizzaBase.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      if (!pointInsidePizza(x, y, rect)) return;

      for (let i = 0; i < 2; i += 1) {
        const px = x + rand(-12, 12);
        const py = y + rand(-10, 10);
        const rot = `${rand(-88, 88)}deg`;
        const scale = rand(.82, 1.18).toFixed(2);

        const bit = document.createElement("div");
        bit.className = "food-token cheese-bit";
        bit.style.left = `${px}px`;
        bit.style.top = `${py}px`;
        bit.style.setProperty("--rot", rot);
        bit.style.setProperty("--scale", scale);
        tokenLayer.appendChild(bit);

        os.cheeseTokens.push({ x: px / rect.width, y: py / rect.height, rot, scale });
        count += 1;
      }

      updateProgress(Math.min(1, count / (step.requiredCount || 30)));
      if (count > (step.requiredCount || 30) + 18) maybeAbundanceComment("cheese", "extraCheese");
      maybeCommentDuringInteraction();
    }

    function onDown(event) {
      currentPointerDown = true;
      pizzaBase.setPointerCapture?.(event.pointerId);
      sprinkle(event.clientX, event.clientY, true);
    }
    function onMove(event) { if (currentPointerDown) sprinkle(event.clientX, event.clientY); }
    function onUp() { currentPointerDown = false; }

    pizzaBase.addEventListener("pointerdown", onDown);
    pizzaBase.addEventListener("pointermove", onMove);
    pizzaBase.addEventListener("pointerup", onUp);
    pizzaBase.addEventListener("pointercancel", onUp);

    return { progress: () => state.currentProgress };
  }



  function createPizzaItemsScene() {
    const { pizzaBase, tokenLayer } = createPizzaShell({ sauce: true, cheese: true });
    const step = currentStep();
    const stateForOrder = orderState();
    if (!Array.isArray(stateForOrder.pizzaTokens)) stateForOrder.pizzaTokens = [];
    let count = 0;
    let itemIndex = 0;
    const items = step.itemSet || [step.item || "pepperoni"];
    renderToolPalette(pizzaBase.parentElement.parentElement, items);

    function place(clientX, clientY) {
      const rect = pizzaBase.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      if (!pointInsidePizza(x, y, rect)) return;
      const item = selectedPaletteItem || items[itemIndex % items.length];
      itemIndex += 1;
      addToken(tokenLayer, item, x, y);
      stateForOrder.pizzaTokens.push({ item, x: x / rect.width, y: y / rect.height });
      count += 1;
      updateProgress(Math.min(1, count / (step.requiredCount || 10)));
      if (count > (step.requiredCount || 10) + 4) maybeAbundanceComment(labelForItem(item).toLowerCase(), `${step.id}_${item}`);
      maybeCommentDuringInteraction();
    }

    function onDown(event) {
      currentPointerDown = true;
      pizzaBase.setPointerCapture?.(event.pointerId);
      place(event.clientX, event.clientY);
    }
    function onMove(event) {
      if (!currentPointerDown) return;
      if (Date.now() % 5 === 0) place(event.clientX, event.clientY);
    }
    function onUp() { currentPointerDown = false; }

    pizzaBase.addEventListener("pointerdown", onDown);
    pizzaBase.addEventListener("pointermove", onMove);
    pizzaBase.addEventListener("pointerup", onUp);
    pizzaBase.addEventListener("pointercancel", onUp);
    return { progress: () => state.currentProgress };
  }



  function pointInsidePizza(x, y, rect) {
    const oval = pizzaOvalForRect(rect);
    return pointInOval(x, y, oval, 1.0);
  }



  function renderToolPalette(parent, items) {
    selectedPaletteItem = null;
    // No visible multi-option tray. The game now cycles the needed ingredient pieces
    // automatically, so the child only focuses on where to place them.
    return;
  }

  function addToken(layer, item, x, y, classPrefix = "food-token") {
    const token = document.createElement("div");
    token.className = `${classPrefix} ${item}`;
    token.textContent = "";
    token.style.left = `${x}px`;
    token.style.top = `${y}px`;
    token.style.setProperty("--rot", `${rand(-18, 18)}deg`);
    token.style.setProperty("--scale", rand(.9, 1.12).toFixed(2));
    token.style.zIndex = String(Math.round(10 + y));
    layer.appendChild(token);
    return token;
  }

  function createBowlItemsScene() {
    const scene = createFoodScene("bowl-scene side-bowl-scene");
    const step = currentStep();
    const items = step.itemSet || ["lettuce"];
    const stateForOrder = orderState();
    if (!Array.isArray(stateForOrder.saladItems)) stateForOrder.saladItems = [];
    let count = 0;

    scene.innerHTML = `<div class="big-bowl side-bowl" id="bigBowl"><div class="salad-pile" id="saladPile"></div></div>`;
    const bowl = scene.querySelector("#bigBowl");
    const pile = scene.querySelector("#saladPile");
    renderToolPalette(scene, items);

    stateForOrder.saladItems.forEach(saved => {
      addToken(pile, saved.item, saved.x * bowl.clientWidth, saved.y * bowl.clientHeight, "salad-item settled");
    });

    function add(clientX, clientY) {
      const rect = bowl.getBoundingClientRect();
      const item = selectedPaletteItem || items[count % items.length];
      const layer = stateForOrder.saladItems.length;

      const clickX = clientX - rect.left;
      const fallX = Math.max(rect.width * .14, Math.min(rect.width * .86, clickX || rect.width * .5));
      const finalX = fallX + rand(-24, 24);
      // Keep salad pieces half tucked behind the bowl front and half visible above the rim.
      const pileBaseY = rect.height * .43;
      const pileLift = Math.min(rect.height * .16, layer * 4.6);
      const finalY = pileBaseY - pileLift + rand(-6, 8);

      const token = addToken(pile, item, finalX, finalY, "salad-item falling");
      token.style.setProperty("--fall-start", `${-rect.height * .42}px`);

      stateForOrder.saladItems.push({ item, x: finalX / rect.width, y: finalY / rect.height });
      count += 1;
      updateProgress(Math.min(1, count / (step.requiredCount || 8)));
      if (count > (step.requiredCount || 8) + 3) maybeAbundanceComment(labelForItem(item).toLowerCase(), `${step.id}_${item}`);
      maybeCommentDuringInteraction();
    }

    scene.addEventListener("pointerdown", event => add(event.clientX, event.clientY));
    return { progress: () => state.currentProgress };
  }



  function createTossBowlScene() {
    const scene = createFoodScene("bowl-scene side-bowl-scene");
    const step = currentStep();
    const stateForOrder = orderState();
    if (!Array.isArray(stateForOrder.saladItems) || !stateForOrder.saladItems.length) {
      stateForOrder.saladItems = ["lettuce", "lettuce", "tomato", "cucumber", "lettuce", "tomato", "cucumber"].map((item, i) => ({ item, x: .24 + (i % 4) * .17, y: .43 - Math.floor(i / 4) * .07 }));
    }
    let count = 0;
    scene.innerHTML = `<div class="big-bowl side-bowl mixing" id="bigBowl"><div class="salad-pile" id="saladPile"></div></div>`;
    const bowl = scene.querySelector("#bigBowl");
    const pile = scene.querySelector("#saladPile");
    stateForOrder.saladItems.forEach(saved => addToken(pile, saved.item, saved.x * bowl.clientWidth, saved.y * bowl.clientHeight, "salad-item settled"));

    function mix() {
      count += 1;
      bowl.style.transform = `rotate(${count % 2 ? -1.7 : 1.7}deg) translateY(${count % 2 ? -1 : 1}px)`;
      const updated = [];
      pile.querySelectorAll(".salad-item").forEach((el, i) => {
        const x = rand(bowl.clientWidth * .14, bowl.clientWidth * .86);
        const y = rand(bowl.clientHeight * .36, bowl.clientHeight * .52) - Math.min(22, i * 1.4);
        el.style.left = `${x}px`;
        el.style.top = `${y}px`;
        el.style.zIndex = String(Math.round(10 + y));
        const item = [...el.classList].find(cls => ["lettuce", "tomato", "cucumber", "pepper", "olive", "cheese"].includes(cls)) || "lettuce";
        updated.push({ item, x: x / bowl.clientWidth, y: y / bowl.clientHeight });
      });
      stateForOrder.saladItems = updated;
      updateProgress(Math.min(1, count / (step.requiredCount || 12)));
    }

    scene.addEventListener("pointerdown", () => { currentPointerDown = true; mix(); maybeCommentDuringInteraction(); });
    scene.addEventListener("pointermove", () => { if (currentPointerDown && Date.now() % 3 === 0) mix(); });
    window.addEventListener("pointerup", () => { currentPointerDown = false; });
    return { progress: () => state.currentProgress };
  }



  function createButterBreadScene() {
    const scene = createFoodScene("sandwich-scene");
    const os = orderState();
    scene.innerHTML = `
      <div class="sandwich-board clean-sandwich-board">
        <div class="sandwich-stack" id="sandwichStack">
          <div class="bread-piece white-bread base-bread ${os.butterDone ? "buttered" : ""}" id="breadPiece">
            <canvas class="butter-canvas" id="butterCanvas"></canvas>
          </div>
        </div>
      </div>
    `;
    const bread = scene.querySelector("#breadPiece");
    const canvas = scene.querySelector("#butterCanvas");
    const ctx = canvas.getContext("2d");
    const grid = new Set();
    const active = makeRectCells(12, 8);
    let lastPoint = null;

    function resize() {
      const rect = bread.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(2, Math.round(rect.width * dpr));
      canvas.height = Math.max(2, Math.round(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      if (os.butterDone) {
        ctx.globalAlpha = .36;
        ctx.fillStyle = "#fff1a8";
        ctx.fillRect(rect.width * .08, rect.height * .12, rect.width * .84, rect.height * .74);
      }
    }

    function mark(x, y, rect) {
      const gx = Math.floor((x / rect.width) * 12);
      const gy = Math.floor((y / rect.height) * 8);
      for (let yy = gy - 1; yy <= gy + 1; yy += 1) {
        for (let xx = gx - 1; xx <= gx + 1; xx += 1) {
          if (active.has(`${xx},${yy}`)) grid.add(`${xx},${yy}`);
        }
      }
      updateProgress(Math.min(1, grid.size / 66));
    }

    function paint(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      if (x < 0 || y < 0 || x > rect.width || y > rect.height) return;

      bread.classList.add("buttered");
      os.butterStarted = true;
      ctx.save();
      ctx.globalAlpha = .58;
      ctx.strokeStyle = "#fff1a8";
      ctx.fillStyle = "#fff1a8";
      ctx.lineWidth = Math.max(28, rect.width * .12);

      if (lastPoint) {
        ctx.beginPath();
        ctx.moveTo(lastPoint.x, lastPoint.y);
        ctx.lineTo(x, y);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(x, y, Math.max(18, rect.width * .08), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      mark(x, y, rect);
      lastPoint = { x, y };
    }

    resize();
    window.addEventListener("resize", resize);
    canvas.addEventListener("pointerdown", e => { currentPointerDown = true; lastPoint = null; paint(e.clientX, e.clientY); maybeCommentDuringInteraction(); });
    canvas.addEventListener("pointermove", e => { if (currentPointerDown) paint(e.clientX, e.clientY); });
    window.addEventListener("pointerup", () => { currentPointerDown = false; lastPoint = null; });
    return { progress: () => state.currentProgress, destroy: () => window.removeEventListener("resize", resize) };
  }



  function makeRectCells(w, h) {
    const cells = new Set();
    for (let y = 0; y < h; y += 1) for (let x = 0; x < w; x += 1) cells.add(`${x},${y}`);
    return cells;
  }

  function createBoardItemsScene(kind) {
    const className = kind === "tray" ? "tray-scene" : "sandwich-scene";
    const boardClass = kind === "tray" ? "tray-board" : "sandwich-board";
    const scene = createFoodScene(className);
    const step = currentStep();
    const items = step.itemSet || ["cheese"];
    const os = orderState();

    if (kind === "sandwich") {
      os.sandwichLayers = Array.isArray(os.sandwichLayers) ? os.sandwichLayers : [];
      scene.innerHTML = `
        <div class="sandwich-board clean-sandwich-board" id="itemBoard">
          <div class="sandwich-stack" id="sandwichStack">
            <div class="bread-piece white-bread base-bread ${os.butterDone || os.butterStarted ? "buttered" : ""}"></div>
          </div>
        </div>
      `;
      const stack = scene.querySelector("#sandwichStack");

      function renderStack() {
        stack.querySelectorAll(".sandwich-layer, .top-bread").forEach(el => el.remove());
        os.sandwichLayers.forEach((item, i) => {
          const layer = document.createElement("div");
          layer.className = `sandwich-layer ${item}`;
          layer.style.setProperty("--offset", `${-i * 7}px`);
          layer.style.zIndex = String(10 + i);
          stack.appendChild(layer);
        });
        if (os.sandwichTop) {
          const top = document.createElement("div");
          top.className = "bread-piece white-bread top-bread";
          top.style.zIndex = String(40 + os.sandwichLayers.length);
          stack.appendChild(top);
        }
      }

      renderStack();

      scene.addEventListener("pointerdown", () => {
        if (step.id === "cheese") {
          const next = "cheese";
          os.sandwichLayers.push(next);
          renderStack();
          const countForThisStep = os.sandwichLayers.filter(item => item === "cheese").length;
          updateProgress(Math.min(1, countForThisStep / (step.requiredCount || 3)));
          if (countForThisStep > (step.requiredCount || 3) + 2) maybeAbundanceComment("cheese", "grilledCheeseExtra");
          maybeCommentDuringInteraction();
        }
      });

      const existingForThisStep = os.sandwichLayers.filter(item => items.includes(item)).length;
      updateProgress(Math.min(1, existingForThisStep / (step.requiredCount || items.length)));
      return { progress: () => state.currentProgress };
    }

    let count = 0;
    scene.innerHTML = `<div class="${boardClass}" id="itemBoard"></div>`;
    const board = scene.querySelector("#itemBoard");
    scene.addEventListener("pointerdown", event => {
      const rect = board.getBoundingClientRect();
      let x = event.clientX - rect.left;
      let y = event.clientY - rect.top;
      if (x < 0 || y < 0 || x > rect.width || y > rect.height) {
        x = rand(rect.width * .25, rect.width * .75);
        y = rand(rect.height * .35, rect.height * .7);
      }
      const item = items[count % items.length];
      addToken(board, item, x, y, "tray-item");
      count += 1;
      updateProgress(Math.min(1, count / (step.requiredCount || items.length)));
      maybeCommentDuringInteraction();
    });
    return { progress: () => Math.min(1, count / (step.requiredCount || items.length)) };
  }



  function lemonadeState() {
    const os = orderState();
    if (!os.lemonade || typeof os.lemonade !== "object") {
      os.lemonade = { ice: 0, lemon: 0, water: 0, mixed: 0 };
    }
    os.lemonade.ice = Math.max(0, Math.min(5, Number(os.lemonade.ice || 0)));
    os.lemonade.lemon = Math.max(0, Math.min(0.22, Number(os.lemonade.lemon || 0)));
    os.lemonade.water = Math.max(0, Math.min(0.44, Number(os.lemonade.water || 0)));
    os.lemonade.mixed = Math.max(0, Math.min(1, Number(os.lemonade.mixed || 0)));
    return os.lemonade;
  }



  function renderPitcherLayers(pitcher, lstate, mixOverride = null) {
    const lemonLayer = pitcher.querySelector(".lemon-juice-layer");
    const waterLayer = pitcher.querySelector(".water-layer");
    const mixedLayer = pitcher.querySelector(".mixed-lemonade-layer");
    const iceLayer = pitcher.querySelector(".ice-layer");

    const lemonHeight = Math.round(lstate.lemon * 100);
    const waterHeight = Math.round(lstate.water * 100);
    const totalHeight = Math.min(72, lemonHeight + waterHeight);
    const mix = mixOverride == null ? lstate.mixed : mixOverride;

    if (lemonLayer) {
      lemonLayer.style.height = `${lemonHeight}%`;
      lemonLayer.style.opacity = String(Math.max(0, 1 - mix * .85));
    }

    if (waterLayer) {
      waterLayer.style.height = `${waterHeight}%`;
      waterLayer.style.bottom = `${lemonHeight}%`;
      waterLayer.style.opacity = String(Math.max(0, 1 - mix * .90));
    }

    if (mixedLayer) {
      mixedLayer.style.height = `${totalHeight}%`;
      mixedLayer.style.opacity = String(mix);
    }

    if (iceLayer) {
      iceLayer.innerHTML = "";
      const fluid = Math.min(.72, lstate.lemon + lstate.water);
      for (let i = 0; i < Math.round(lstate.ice); i += 1) {
        const cube = document.createElement("div");
        cube.className = "css-ice-cube";
        cube.style.left = `${30 + (i % 3) * 17 + rand(-2, 2)}%`;
        const bottom = fluid <= 0.02
          ? 10 + Math.floor(i / 3) * 10
          : Math.max(14, Math.min(56, fluid * 88 - 2 + Math.floor(i / 3) * 7));
        cube.style.bottom = `${bottom}%`;
        cube.style.setProperty("--rot", `${rand(-12, 12)}deg`);
        iceLayer.appendChild(cube);
      }
    }
  }



  function createPitcherMarkup(extra = "") {
    return `
      <div class="board-shadow"></div>
      <div class="lemonade-station">
        <div class="pitcher modern-pitcher" id="pitcher">
          <div class="lemon-juice-layer"></div>
          <div class="water-layer"></div>
          <div class="mixed-lemonade-layer"></div>
          <div class="ice-layer"></div>
          <div class="pitcher-shine"></div>
        </div>
        ${extra}
      </div>
    `;
  }

  function createPitcherItemsScene() {
    const scene = createFoodScene("pitcher-scene");
    const step = currentStep();
    const lstate = lemonadeState();

    const mode = step.id === "ice" ? "ice" : step.id === "lemons" ? "lemon" : "water";
    const cap = mode === "ice" ? 4 : mode === "lemon" ? 0.22 : 0.44;

    scene.innerHTML = createPitcherMarkup(
      mode === "lemon"
        ? `<div class="lemon-press"><div class="lemon-half"></div><span>Tap to squeeze</span></div>`
        : mode === "water"
          ? `<div class="water-note">Tap to pour water</div>`
          : `<div class="water-note ice-note">Tap to drop ice</div>`
    );

    const pitcher = scene.querySelector("#pitcher");
    renderPitcherLayers(pitcher, lstate);

    function showStream(className) {
      const stream = document.createElement("div");
      stream.className = className;
      pitcher.appendChild(stream);
      setTimeout(() => stream.remove(), 420);
    }

    function addIngredient() {
      if (mode === "ice") {
        lstate.ice = Math.min(5, lstate.ice + 1);
        updateProgress(Math.min(1, lstate.ice / cap));
        if (lstate.ice >= 5) maybeAbundanceComment("ice", "lemonadeIce");
      } else if (mode === "lemon") {
        lstate.lemon = Math.min(cap, lstate.lemon + 0.032);
        showStream("lemon-stream");
        updateProgress(Math.min(1, lstate.lemon / cap));
      } else {
        lstate.water = Math.min(cap, lstate.water + 0.052);
        showStream("water-stream");
        updateProgress(Math.min(1, lstate.water / cap));
      }

      renderPitcherLayers(pitcher, lstate);
      maybeCommentDuringInteraction();
    }

    scene.addEventListener("pointerdown", addIngredient);

    if (mode === "ice") updateProgress(Math.min(1, lstate.ice / cap));
    else if (mode === "lemon") updateProgress(Math.min(1, lstate.lemon / cap));
    else updateProgress(Math.min(1, lstate.water / cap));

    return { progress: () => state.currentProgress };
  }



  function createStirPitcherScene() {
    const scene = createFoodScene("pitcher-scene");
    const step = currentStep();
    const lstate = lemonadeState();
    let count = Math.round(lstate.mixed * (step.requiredCount || 12));

    scene.innerHTML = createPitcherMarkup(`<div class="stir-spoon" id="stirSpoon"></div>`);
    const pitcher = scene.querySelector("#pitcher");
    const station = scene.querySelector(".lemonade-station");
    const spoon = scene.querySelector("#stirSpoon");
    renderPitcherLayers(pitcher, lstate);

    function stir(event = null) {
      count += 1;
      lstate.mixed = Math.min(1, count / (step.requiredCount || 12));
      renderPitcherLayers(pitcher, lstate, lstate.mixed);
      pitcher.style.transform = `rotate(${count % 2 ? -1.2 : 1.2}deg)`;
      if (event) {
        const rect = station.getBoundingClientRect();
        spoon.style.left = `${event.clientX - rect.left}px`;
        spoon.style.top = `${event.clientY - rect.top}px`;
      }
      updateProgress(lstate.mixed);
    }

    scene.addEventListener("pointerdown", event => { currentPointerDown = true; stir(event); maybeCommentDuringInteraction(); });
    scene.addEventListener("pointermove", event => { if (currentPointerDown) stir(event); });
    window.addEventListener("pointerup", () => { currentPointerDown = false; });
    updateProgress(lstate.mixed);
    return { progress: () => state.currentProgress };
  }



  function createSundaeItemsScene() {
    const scene = createFoodScene("sundae-scene side-sundae-scene");
    const step = currentStep();
    const items = step.itemSet || ["scoop"];
    const os = orderState();
    if (!Array.isArray(os.sundaeItems)) os.sundaeItems = [];
    let count = 0;

    scene.innerHTML = `<div class="sundae-cup side-sundae-cup" id="sundaeCup"><div class="sundae-pile" id="sundaePile"></div></div>`;
    const cup = scene.querySelector("#sundaeCup");
    const pile = scene.querySelector("#sundaePile");
    renderToolPalette(scene, items);

    function renderSaved() {
      pile.innerHTML = "";
      os.sundaeItems.forEach(saved => addToken(pile, saved.item, saved.x * cup.clientWidth, saved.y * cup.clientHeight, "sundae-item"));
    }
    renderSaved();

    scene.addEventListener("pointerdown", event => {
      const rect = cup.getBoundingClientRect();
      const item = selectedPaletteItem || items[count % items.length];
      let x;
      let y;

      if (item === "scoop") {
        const scoopIndex = os.sundaeItems.filter(saved => saved.item === "scoop").length;
        x = rect.width * (.33 + (scoopIndex % 3) * .17) + rand(-8, 8);
        y = rect.height * (.28 + Math.floor(scoopIndex / 3) * .09) + rand(-6, 6);
      } else if (item === "cherry") {
        x = rect.width * .50;
        y = rect.height * .11;
      } else {
        x = rand(rect.width * .25, rect.width * .75);
        y = rand(rect.height * .18, rect.height * .38);
      }

      os.sundaeItems.push({ item, x: x / rect.width, y: y / rect.height });
      addToken(pile, item, x, y, "sundae-item");
      count += 1;
      updateProgress(Math.min(1, count / (step.requiredCount || 3)));
      if (count > (step.requiredCount || 3) + 4) maybeAbundanceComment(labelForItem(item).toLowerCase(), `${step.id}_${item}`);
      maybeCommentDuringInteraction();
    });

    return { progress: () => state.currentProgress };
  }



  function createReadyScene() {
    const order = currentOrder();

    if (isPizzaOrder(order)) {
      createPizzaShell({ sauce: true, cheese: true });
    } else if (order.id === "grilled_cheese") {
      createBoardItemsScene("sandwich");
    } else if (order.id === "garden_salad") {
      createTossBowlScene();
    } else if (order.id === "sundae") {
      createSundaeItemsScene();
    } else if (order.id === "lemonade") {
      createStirPitcherScene();
    } else {
      const scene = createFoodScene("tray-scene");
      scene.innerHTML = `<div class="tray-board ready-tray"></div>`;
    }
    updateProgress(1);
    return { progress: () => 1 };
  }



  function assetForItem(item) {
    const map = {
      pepperoni: "pepperoni.svg", mushroom: "mushroom.svg", pepper: "pepper.svg", tomato: "tomato.svg", olive: "olive.svg",
      lettuce: "lettuce.svg", cucumber: "cucumber.svg", cheese: "cheese.svg", lemon: "lemon.svg", ice: "ice.svg", water: "water.svg",
      scoop: "icecream.svg", syrup: "syrup.svg", sprinkles: "sprinkles.svg", cherry: "cherry.svg", fries: "fries.svg", burger: "burger.svg", drink: "drink.svg", apple: "apple.svg"
    };
    return map[item] || "chef.svg";
  }

  function labelForItem(item) {
    const labels = {
      pepperoni: "Pepperoni", mushroom: "Mushroom", pepper: "Pepper", tomato: "Tomato", olive: "Olive",
      lettuce: "Lettuce", cucumber: "Cucumber", cheese: "Cheese", lemon: "Lemon", ice: "Ice", water: "Water",
      scoop: "Scoop", syrup: "Syrup", sprinkles: "Sprinkles", cherry: "Cherry", fries: "Fries", burger: "Burger", drink: "Drink", apple: "Apple"
    };
    return labels[item] || "Item";
  }

  function rand(min, max) { return Math.random() * (max - min) + min; }

  function scheduleProgressCommentCheck(delay = 360) {
    if (state.gameCompleted || socialStageIndex() > 2) return;
    if (progressCommentTimer) return;

    progressCommentTimer = setTimeout(() => {
      progressCommentTimer = null;
      void maybeCommentDuringInteraction();
    }, delay);
  }

  function updateProgress(value) {
    state.currentProgress = Math.max(0, Math.min(1, value || 0));
    scheduleProgressCommentCheck();
  }

  function stepReady() {
    const step = currentStep();
    if (step.type === "ready_card") return true;
    if (step.type === "paint_sauce") return state.currentProgress >= 0.38;
    if (step.type === "butter_bread") return state.currentProgress >= 0.42;
    const min = step.minProgress || 0.7;
    return state.currentProgress >= min;
  }


  /*
    Restaurant Worker Game dialogue rewrite:
    - Teacher now fills Star's safety-bridge role.
    - Leo now fills the Teacher/exposure role.
    - Every two orders advances one social level:
      1) Teacher leads, Leo softly observes.
      2) Leo wonders, Teacher bridges.
      3) Leo asks gently, Teacher models/redirects after silence.
      4) Leo asks directly, Teacher stays nearby and supports.
  */

  function friendlyStepName(step = currentStep()) {
    const map = {
      sauce: "sauce",
      cheese: "cheese",
      pepperoni: "pepperoni",
      veggies: "vegetables",
      lettuce: "lettuce",
      toss: "salad",
      butter: "bread",
      ice: "ice",
      lemons: "lemon juice",
      water: "water",
      stir: "lemonade",
      scoops: "ice cream",
      toppings: "toppings",
      cherry: "cherry",
      main: "meal",
      sides: "drink and fruit",
      ready: "order"
    };
    return map[step?.id] || String(step?.title || "this part").toLowerCase();
  }

  function friendlyOrderName(order = currentOrder()) {
    return String(order?.title || "order").toLowerCase();
  }

  function nextOrderName() {
    const next = ORDERS[state.orderIndex + 1];
    return next ? String(next.title || "the next order").toLowerCase() : "the next order";
  }

  function teacherLeadLineForStep(step = currentStep()) {
    const order = friendlyOrderName();
    const part = friendlyStepName(step);

    const byType = {
      paint_sauce: [
        `Let's start with the sauce for this ${order}.`,
        `First, spread the sauce on this ${order}.`,
        `We can start with sauce. Put it wherever it looks good.`
      ],
      sprinkle_cheese: [
        "Now add the cheese.",
        "Next, sprinkle the cheese over the sauce.",
        "You can add the cheese wherever it looks good."
      ],
      place_pizza_items: [
        `Now add the ${part}.`,
        `Next, put the ${part} around the pizza.`,
        `You can place the ${part} wherever it looks good.`
      ],
      bowl_items: [
        `Now add the ${part}.`,
        `Next, put the ${part} into the bowl.`,
        `You can add the ${part} wherever it looks good in the bowl.`
      ],
      toss_bowl: [
        "Now gently toss the salad.",
        "Next, mix the salad so everything comes together.",
        "You can move the bowl around to mix the salad."
      ],
      butter_bread: [
        "Let's start by buttering the bread.",
        "First, spread butter across the bread.",
        "You can cover the bread with butter wherever it looks good."
      ],
      sandwich_layers: [
        "Now add the cheese slices.",
        "Next, put the cheese on the bread.",
        "You can add the cheese slices wherever they fit."
      ],
      pitcher_items: [
        step.id === "ice" ? "Let's start by adding ice to the glass." :
        step.id === "lemons" ? "Now squeeze lemon juice into the glass." :
        "Now add water to the glass.",
        step.id === "ice" ? "First, put a few ice cubes in the glass." :
        step.id === "lemons" ? "Tap to add lemon juice over the ice." :
        "Tap to pour water on top.",
        "You can add this part wherever it looks good."
      ],
      stir_pitcher: [
        "Now stir the lemonade.",
        "Next, mix the lemonade gently.",
        "You can move around the glass to stir it."
      ],
      sundae_items: [
        `Now add the ${part}.`,
        `Next, put the ${part} on the sundae.`,
        `You can add the ${part} wherever it looks good.`
      ],
      tray_items: [
        `Now add the ${part}.`,
        `Next, put the ${part} on the tray.`,
        `You can place the ${part} wherever it looks good.`
      ],
      ready_card: [
        "Now we can check this order together.",
        "This order looks close to ready.",
        "Let's look at the order before Leo takes it."
      ]
    };

    return pickLine(byType[step.type] || [
      `Let's work on the ${part}.`,
      `You can add the ${part} wherever it looks good.`,
      `Take your time with the ${part}.`
    ]);
  }

  function teacherChoiceLineForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const byType = {
      paint_sauce: [
        "The sauce can go near the middle or closer to the edges.",
        "You can spread a little sauce or a lot of sauce.",
        "Choose where the sauce should go first."
      ],
      sprinkle_cheese: [
        "The cheese can be spread out or gathered in some spots.",
        "You can add a little cheese or a lot of cheese.",
        "Choose where the cheese should go."
      ],
      place_pizza_items: [
        `The ${part} can go on different slices.`,
        `You can put the ${part} wherever it looks tasty.`,
        `Choose where the ${part} should go.`
      ],
      bowl_items: [
        `The ${part} can fall in any part of the bowl.`,
        `You can add a little ${part} or more ${part}.`,
        `Choose where the ${part} should go.`
      ],
      toss_bowl: [
        "You can mix it gently.",
        "You can move the bowl a little or a lot.",
        "Choose how much mixing feels right."
      ],
      butter_bread: [
        "The butter can cover the middle or the edges too.",
        "You can spread a little butter or more butter.",
        "Choose where the butter should go first."
      ],
      sandwich_layers: [
        "The cheese can go in the middle of the bread.",
        "You can add the cheese slices one at a time.",
        "Choose where the cheese should sit."
      ],
      pitcher_items: [
        "You can add a little or a lot.",
        "Choose where this part should go.",
        "You can add it when you are ready."
      ],
      stir_pitcher: [
        "You can stir slowly.",
        "You can mix it until it looks ready.",
        "Choose how much stirring feels right."
      ],
      sundae_items: [
        `The ${part} can go anywhere on the sundae.`,
        `You can add a little ${part} or more ${part}.`,
        `Choose where the ${part} should go.`
      ],
      tray_items: [
        "The food can go anywhere on the tray.",
        "You can place the pieces where they fit.",
        "Choose where everything should go."
      ],
      ready_card: [
        "You can look at the order and decide if it feels ready.",
        "You can tell us if it is ready or if it needs more time.",
        "Take your time checking it."
      ]
    };

    return pickLine(byType[step.type] || [
      `You can choose where the ${part} should go.`,
      `Start wherever the ${part} feels easiest.`,
      `Take your time with the ${part}.`
    ]);
  }

  function leoCommentLineForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const byType = {
      paint_sauce: [
        "Sauce is a nice first part for the pizza.",
        "That is a good place to start.",
        "I like starting with the sauce."
      ],
      sprinkle_cheese: [
        "Cheese is a good next part.",
        "That helps the pizza come together.",
        "I like adding cheese after the sauce."
      ],
      place_pizza_items: [
        `The ${part} is a nice next part.`,
        `That will make the pizza look more complete.`,
        `I like that topping for this order.`
      ],
      bowl_items: [
        `The ${part} is a good part for the salad.`,
        `That makes the bowl look fresh.`,
        `I like that next part.`
      ],
      toss_bowl: [
        "Mixing helps the salad come together.",
        "That is a nice final step for the salad.",
        "I like seeing everything mix together."
      ],
      butter_bread: [
        "Butter is a good first part for grilled cheese.",
        "That will help the bread toast nicely.",
        "I like starting with the bread."
      ],
      sandwich_layers: [
        "Cheese is a nice next part for the sandwich.",
        "That will make the sandwich feel complete.",
        "I like adding the cheese here."
      ],
      pitcher_items: [
        `The ${part} is a good part for the lemonade.`,
        `That helps the drink come together.`,
        `I like adding the ${part} here.`
      ],
      stir_pitcher: [
        "Stirring helps the lemonade come together.",
        "That is a nice final step for the drink.",
        "I like seeing the lemonade mix."
      ],
      sundae_items: [
        `The ${part} is a nice part for the sundae.`,
        `That makes the sundae look special.`,
        `I like that detail.`
      ],
      tray_items: [
        `The ${part} is a good part for the tray.`,
        `That helps the meal look ready.`,
        `I like that part of the order.`
      ],
      ready_card: [
        "This order is looking close to ready.",
        "I like how this order came together.",
        "That looks like a careful order."
      ]
    };

    return pickLine(byType[step.type] || [
      `That is a nice part for the ${friendlyOrderName()}.`,
      `I like how the ${part} is coming together.`,
      `That is a good next part.`
    ]);
  }
  function leoWonderLineForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const order = friendlyOrderName();

    const byType = {
      paint_sauce: [
        "I wonder how much sauce this customer likes on pizza.",
        "I wonder if the sauce will reach the edges or stay mostly in the middle.",
        "I wonder if the customer likes a saucy pizza or just a little sauce."
      ],
      sprinkle_cheese: [
        "I wonder if the customer likes a little cheese or lots of cheese.",
        "I wonder which slice will be the cheesiest.",
        "I wonder if this customer loves cheese as much as I do."
      ],
      place_pizza_items: [
        step.id === "veggies"
          ? "I wonder which vegetable the customer will like more."
          : `I wonder which slice the customer will pick first with the ${part} on it.`,
        step.id === "veggies"
          ? "I wonder which vegetable is the tastiest one on this pizza."
          : `I wonder if every slice should get some ${part}.`,
        step.id === "veggies"
          ? "I wonder which vegetable is the healthiest one here."
          : `I wonder where the ${part} should go so the pizza looks balanced.`
      ],
      bowl_items: [
        "I wonder how much salad the customer might want.",
        "I wonder which one the customer will like more: tomatoes or cucumbers.",
        "I wonder which salad piece is crunchier.",
        "I wonder if kids like salad more or veggie pizza more."
      ],
      toss_bowl: [
        "I wonder if the salad should be mixed a little or a lot.",
        "I wonder if the customer likes every bite mixed together.",
        "I wonder how fresh this salad will look when it is mixed."
      ],
      butter_bread: [
        "I wonder if grilled cheese tastes better with crispy bread.",
        "I wonder if the chef will toast this bread until it is golden.",
        "I wonder if the customer likes the bread buttery or just a little buttery."
      ],
      sandwich_layers: [
        "I wonder if kids like grilled cheese more when it is really cheesy.",
        "I wonder how melty the cheese will get when the chef cooks it.",
        "I wonder if this sandwich needs a little cheese or lots of cheese."
      ],
      pitcher_items: [
        step.id === "ice"
          ? "I wonder if the customer likes lemonade extra cold."
          : step.id === "lemons"
            ? "I wonder if this lemonade will taste sweet or sour."
            : "I wonder how full the glass should be.",
        step.id === "ice"
          ? "I wonder if kids like lots of ice or just a little ice."
          : step.id === "lemons"
            ? "I wonder if the lemon will make the drink taste bright."
            : "I wonder if the ice will float when the water goes in.",
        "I wonder if the customer will smile when they taste this lemonade."
      ],
      stir_pitcher: [
        "I wonder if the lemonade tastes better when it is mixed really well.",
        "I wonder if the lemon and water are blending together now.",
        "I wonder if the customer will want this drink very cold."
      ],
      sundae_items: [
        step.id === "toppings"
          ? "I wonder if kids like sprinkles more or syrup more."
          : `I wonder where the ${part} should go on the sundae.`,
        step.id === "cherry"
          ? "I wonder if the cherry should go right on top."
          : "I wonder which part of the sundae the customer will eat first.",
        "I wonder if this sundae will be the most fun order today."
      ],
      tray_items: [
        step.id === "main"
          ? "I wonder if kids like fries more or burgers more."
          : "I wonder if kids like the drink more or the apple more.",
        "I wonder where everything should go so the tray looks neat.",
        "I wonder which part of this meal the customer will eat first."
      ],
      ready_card: [
        `I wonder if this ${order} is ready for the customer.`,
        "I wonder if the customer will like how this order turned out.",
        "I wonder if this is ready for me to carry carefully."
      ]
    };

    return pickLine(byType[step.type] || [
      `I wonder where the ${part} should go.`,
      `I wonder if the customer will like the ${part}.`,
      `I wonder if this part is almost ready.`
    ]);
  }

  function stageThreePreferencePrompts(order = currentOrder()) {
    if (order.id === "grilled_cheese") {
      return [
        "What would you rather eat, grilled cheese or salad?",
        "Which has been more fun so far, making pizza or working on grilled cheese?",
        "Which one sounds tastier, cheese pizza or grilled cheese?"
      ];
    }

    if (order.id === "lemonade") {
      return [
        "What would you rather have with lunch, lemonade or salad?",
        "Which was more fun to make, the pizza or the lemonade?",
        "Would you pick veggie pizza or grilled cheese?"
      ];
    }

    return [
      "What have you liked making more so far, pizza or salad?",
      "What would you rather eat, this order or the last order?",
      "Which one has been more fun to make so far?"
    ];
  }

  function stageThreeTeacherBridgeLines(order = currentOrder()) {
    if (order.id === "grilled_cheese") {
      return [
        "I think I would pick grilled cheese today. What about you, {child}?",
        "I liked making the pizza, but the grilled cheese looks fun too. What about you, {child}?",
        "I think cheese pizza sounds tasty. What about you, {child}?"
      ];
    }

    if (order.id === "lemonade") {
      return [
        "I think I would pick lemonade with lunch. What about you, {child}?",
        "I liked making the pizza, but the lemonade is fun too. What about you, {child}?",
        "I think I would pick grilled cheese today. What about you, {child}?"
      ];
    }

    return [
      "I think I liked making the pizza. What about you, {child}?",
      "I would pick this order today. What about you, {child}?",
      "I think this one has been fun to make. What about you, {child}?"
    ];
  }

  async function maybeAskStageThreePreference() {
    const social = socialStageIndex();
    if (social !== 3 || state.gameCompleted || state.isSpeaking || state.waitingForResponse || state.isListening) return;

    const order = currentOrder();
    const step = currentStep();
    if (!order || !step || step.type === "ready_card") return;

    const os = orderState(order);
    os.stageThreePreferenceCount = os.stageThreePreferenceCount || 0;
    os.stageThreePreferenceSteps = os.stageThreePreferenceSteps || {};

    const maxForOrder = 1;
    const stepKey = `pref_${state.stepIndex}`;
    // Keep this gentle: Leo should only make one casual preference prompt per order.
    if (state.stepIndex !== 0) return;
    if (os.stageThreePreferenceCount >= maxForOrder || os.stageThreePreferenceSteps[stepKey]) return;

    const prompts = stageThreePreferencePrompts(order);
    const promptIndex = Math.min(os.stageThreePreferenceCount, prompts.length - 1);
    os.stageThreePreferenceCount += 1;
    os.stageThreePreferenceSteps[stepKey] = true;

    await speakNow(WORKER, prompts[promptIndex], {
      expectsResponse: true,
      intent: "preference_choice",
      source: "worker-preference",
      responseActor: WORKER,
      preferenceIndex: promptIndex,
      responseSeconds: 4.6
    });
  }

  function workerMoveOnQuestionForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const order = currentOrder();
    const next = order.steps[state.stepIndex + 1];

    if (nextStepIsReadyCard()) {
      return `Do you guys think it is ready to ${orderReadyDestinationForSpeech()}, or do you guys want to add a little more ${part} first?`;
    }

    if (step.type === "ready_card") {
      return "Do you guys think this order is ready for the customer, or do you guys want to look at it a little more first?";
    }

    if (!next) {
      return `Do you guys think it is ready to ${orderReadyDestinationForSpeech()}, or do you guys want to do a little more with the ${part} first?`;
    }

    if (isGardenSaladVegetableToTossStep(step)) {
      return "Do you guys want to keep adding vegetables, or do you guys want to start tossing the salad?";
    }

    return `Do you guys want to keep working on the ${part}, or do you guys want to move on to the ${friendlyStepName(next)}?`;
  }

  function teacherMoveBridgeLineForStep(step = currentStep()) {
    if (isGardenSaladVegetableToTossStep(step)) {
      return "I think we can start tossing the salad. What do you think, {child}?";
    }

    if (nextStepIsReadyCard()) {
      return `I think this can ${orderReadyDestinationForSpeech()} now. What do you think, {child}?`;
    }

    const next = currentOrder().steps[state.stepIndex + 1];
    if (next) {
      return `I think we can move on to the ${friendlyStepName(next)}. What do you think, {child}?`;
    }

    return "I think this looks ready for the customer. What do you think, {child}?";
  }

  async function completeMoveChoice(choice, responderActor = WORKER) {
    if (choice === "keep") {
      await speakNow(responderActor, pickLine([
        `Okay, you guys can keep working on the ${friendlyStepName(currentStep())}.`,
        "Sure, you guys can do a little more first.",
        "Okay, keep going for a little longer."
      ]));
      return;
    }

    if (!nextStepIsReadyCard()) {
      await speakNow(responderActor, pickLine([
        "Okay, let's move on.",
        "Great, we can go to the next part.",
        "Sounds good, let's keep the order going."
      ]));
    }

    await completeStepAfterReadyCheck({ skipPraise: true });
  }

  function leoToTeacherLineForStep(step = currentStep()) {
    const part = friendlyStepName(step);

    const byType = {
      paint_sauce: [
        "Teacher, I wonder if the sauce should reach the edges.",
        "Teacher, I wonder if this customer likes a saucy pizza.",
        "Teacher, I wonder how much sauce this pizza needs."
      ],
      sprinkle_cheese: [
        "Teacher, I wonder if the customer likes a little cheese or lots of cheese.",
        "Teacher, I wonder where the cheesiest bite will be.",
        "Teacher, I wonder if this customer loves cheese too."
      ],
      place_pizza_items: [
        step.id === "veggies"
          ? "Teacher, I wonder which vegetable the customer will like more."
          : `Teacher, I wonder where the ${part} should go.`,
        step.id === "veggies"
          ? "Teacher, I wonder which vegetable is tastier."
          : `Teacher, I wonder if every slice should get some ${part}.`,
        step.id === "veggies"
          ? "Teacher, I wonder which vegetable is healthier."
          : `Teacher, I wonder if the ${part} should be spread out.`
      ],
      bowl_items: [
        "Teacher, I wonder how much salad the customer might want.",
        "Teacher, I wonder if the customer likes tomatoes or cucumbers more.",
        "Teacher, I wonder if kids like salad more or veggie pizza more."
      ],
      toss_bowl: [
        "Teacher, I wonder if this salad should be mixed a little or a lot.",
        "Teacher, I wonder if the customer likes every bite mixed together.",
        "Teacher, I wonder if the salad looks fresh enough now."
      ],
      butter_bread: [
        "Teacher, I wonder if grilled cheese tastes better with crispy bread.",
        "Teacher, I wonder if the chef will toast this until it is golden.",
        "Teacher, I wonder if the bread needs butter near the edges."
      ],
      sandwich_layers: [
        "Teacher, I wonder if kids like grilled cheese more when it is really cheesy.",
        "Teacher, I wonder how melty this cheese will get.",
        "Teacher, I wonder if this sandwich needs more cheese."
      ],
      pitcher_items: [
        step.id === "ice"
          ? "Teacher, I wonder if the customer likes lemonade extra cold."
          : step.id === "lemons"
            ? "Teacher, I wonder if this lemonade will taste sweet or sour."
            : "Teacher, I wonder how full the glass should be.",
        step.id === "ice"
          ? "Teacher, I wonder if kids like lots of ice or just a little ice."
          : step.id === "lemons"
            ? "Teacher, I wonder if the lemon will make the drink taste bright."
            : "Teacher, I wonder if the ice will float when the water goes in.",
        "Teacher, I wonder if the customer will smile when they taste this lemonade."
      ],
      stir_pitcher: [
        "Teacher, I wonder if the lemonade tastes better when it is mixed really well.",
        "Teacher, I wonder if the lemon and water are blending together now.",
        "Teacher, I wonder if the drink looks ready."
      ],
      sundae_items: [
        step.id === "toppings"
          ? "Teacher, I wonder if kids like sprinkles more or syrup more."
          : `Teacher, I wonder where the ${part} should go on the sundae.`,
        step.id === "cherry"
          ? "Teacher, I wonder if the cherry should go right on top."
          : "Teacher, I wonder which part of the sundae the customer will eat first.",
        "Teacher, I wonder if this sundae will be the most fun order today."
      ],
      tray_items: [
        step.id === "main"
          ? "Teacher, I wonder if kids like fries more or burgers more."
          : "Teacher, I wonder if kids like the drink more or the apple more.",
        "Teacher, I wonder where everything should go so the tray looks neat.",
        "Teacher, I wonder which part of this meal the customer will eat first."
      ],
      ready_card: [
        "Teacher, I wonder if this order is ready.",
        "Teacher, I wonder if the customer will like this order.",
        "Teacher, I wonder if I should carry this carefully now."
      ]
    };

    return pickLine(byType[step.type] || [
      `Teacher, I wonder where the ${part} should go.`,
      `Teacher, I wonder if the customer will like the ${part}.`,
      `Teacher, I wonder if this part is almost ready.`
    ]);
  }

  function leoIndirectQuestionForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const byType = {
      paint_sauce: [
        "Tell me if the sauce should be little or big.",
        "Tell me if the sauce should reach the edges.",
        "Tell me where the sauce should go: middle or edges."
      ],
      sprinkle_cheese: [
        "Tell me which feels better: a little cheese or lots of cheese.",
        "Tell me if the cheese should be spread out or bunched up.",
        "Tell me where the cheese should go: middle or all over."
      ],
      place_pizza_items: [
        `Tell me where the ${part} should go: middle or edges.`,
        `Tell me if the ${part} should be spread out or close together.`,
        `Tell me if every slice should get some ${part}.`
      ],
      bowl_items: [
        `Tell me where the ${part} should go: middle or side.`,
        `Tell me if the bowl needs a little ${part} or more ${part}.`,
        `Tell me if the salad should look light or full.`
      ],
      toss_bowl: [
        "Tell me if the salad should be mixed a little or a lot.",
        "Tell me if the salad looks ready or needs more mixing.",
        "Tell me which feels better: gentle mixing or more mixing."
      ],
      butter_bread: [
        "Tell me if the butter should cover the middle or the edges.",
        "Tell me if the bread needs a little butter or more butter.",
        "Tell me if the bread looks ready for cheese."
      ],
      sandwich_layers: [
        "Tell me if the sandwich needs one slice or more cheese.",
        "Tell me where the cheese should go: middle or side.",
        "Tell me if the cheese looks ready."
      ],
      pitcher_items: [
        `Tell me if this needs a little ${part} or more ${part}.`,
        `Tell me if the ${part} looks ready.`,
        `Tell me which feels better: a little more or enough.`
      ],
      stir_pitcher: [
        "Tell me if the lemonade needs a little mixing or more mixing.",
        "Tell me if the lemonade looks ready.",
        "Tell me if the drink should be stirred more."
      ],
      sundae_items: [
        `Tell me where the ${part} should go: middle or top.`,
        `Tell me if the sundae needs a little ${part} or more ${part}.`,
        `Tell me if this ${part} looks ready.`
      ],
      tray_items: [
        `Tell me where the ${part} should go: middle or side.`,
        `Tell me if the tray needs anything else.`,
        `Tell me if the ${part} looks ready.`
      ],
      ready_card: [
        "Tell me if this order is ready or needs more time.",
        "Tell me if this order is ready for the customer or needs more time.",
        "Tell me if this looks ready for the customer."
      ]
    };

    return pickLine(byType[step.type] || [
      `Tell me where the ${part} should go.`,
      `Tell me if the ${part} looks ready.`,
      `Tell me if this part needs more.`
    ]);
  }

  function teacherBridgeAnswerForStep(step = currentStep(), questionIndex = 0) {
    const part = friendlyStepName(step);
    const byType = {
      paint_sauce: [
        "Hmm, I think the sauce could reach the edges. What do you think?",
        "I would spread the sauce a little more in the middle. What do you think?"
      ],
      sprinkle_cheese: [
        "I like lots of cheese on pizza. What do you think?",
        "I would spread the cheese out. What do you think?"
      ],
      place_pizza_items: [
        `I would spread the ${part} across the pizza. What do you think?`,
        `I think different slices could get some ${part}. What do you think?`
      ],
      bowl_items: [
        `I would add the ${part} near the middle. What do you think?`,
        `I think the bowl could use a little more ${part}. What do you think?`
      ],
      toss_bowl: [
        "I think gentle mixing works well. What do you think?",
        "I think it could use a little more mixing. What do you think?"
      ],
      butter_bread: [
        "I would put butter near the edges too. What do you think?",
        "I think the bread looks almost ready for cheese. What do you think?"
      ],
      sandwich_layers: [
        "I would put the cheese in the middle. What do you think?",
        "I think more cheese could work here. What do you think?"
      ],
      pitcher_items: [
        `I think a little more ${part} could work. What do you think?`,
        `I think the ${part} looks close to ready. What do you think?`
      ],
      stir_pitcher: [
        "I think the lemonade looks close to mixed. What do you think?",
        "I would stir it a little more. What do you think?"
      ],
      sundae_items: [
        `I would put the ${part} near the top. What do you think?`,
        `I think this ${part} looks good here. What do you think?`
      ],
      tray_items: [
        `I would put the ${part} on the side of the tray. What do you think?`,
        `I think the tray is looking ready. What do you think?`
      ],
      ready_card: [
        "I think this order looks ready. What do you think?",
        "I think this looks ready for the customer. What do you think?"
      ]
    };

    const lines = byType[step.type] || [
      `I think the ${part} looks good. What do you think?`,
      `I think this part is close to ready. What do you think?`
    ];

    return fillLine(lines[Math.min(questionIndex, lines.length - 1)] || lines[0]);
  }

  function leoDirectQuestionForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const byType = {
      paint_sauce: [
        "Does the sauce look ready?",
        "Should the sauce reach the edges?",
        "Should we move to the cheese now?"
      ],
      sprinkle_cheese: [
        "Does this have enough cheese?",
        "Should the cheese go all over?",
        "Should we move to the next part?"
      ],
      place_pizza_items: [
        `Does this have enough ${part}?`,
        `Where should the ${part} go?`,
        `Should I send this pizza to the chef?`
      ],
      bowl_items: [
        `Does the bowl have enough ${part}?`,
        `Where should the ${part} go?`,
        `Should we add the next part?`
      ],
      toss_bowl: [
        "Does the salad look mixed?",
        "Should I take the salad to the customer?",
        "Should we mix it more?"
      ],
      butter_bread: [
        "Does the bread have enough butter?",
        "Should we add cheese now?",
        "Should the butter go near the edges too?"
      ],
      sandwich_layers: [
        "Does this sandwich have enough cheese?",
        "Should the cheese go in the middle?",
        "Is this ready for the chef?"
      ],
      pitcher_items: [
        `Does this have enough ${part}?`,
        `Should we add more ${part}?`,
        `Should we move to the next drink step?`
      ],
      stir_pitcher: [
        "Does the lemonade look stirred?",
        "Should I bring this lemonade to the customer?",
        "Should we stir it more?"
      ],
      sundae_items: [
        `Does the sundae have enough ${part}?`,
        `Where should the ${part} go?`,
        `Should I bring this sundae to the customer?`
      ],
      tray_items: [
        `Does the tray have the ${part}?`,
        `Where should the ${part} go?`,
        `Does the tray look ready?`
      ],
      ready_card: [
        "Does this order look ready?",
        "Should I take this order to the customer?",
        "Should we keep working on this order?"
      ]
    };

    return makeDirectChildQuestion(pickLine(byType[step.type] || [
      `Does the ${part} look ready?`,
      `Where should the ${part} go?`,
      `Should we move on now?`
    ]));
  }

  function makeDirectChildQuestion(question) {
    const line = String(question || "").trim();
    const prefix = childPrefix();
    if (!prefix || !line) return line;
    return `${prefix}${line.charAt(0).toLowerCase()}${line.slice(1)}`;
  }

  function completionPraiseForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const byType = {
      paint_sauce: [
        "Great job. That sauce looks amazing.",
        "Nice work. The sauce is spread out really well.",
        "Good job. The pizza has sauce now, and it looks great."
      ],
      sprinkle_cheese: [
        "Great job. The cheese looks amazing.",
        "Nice work adding the cheese. You're really good at this.",
        "Good job. The pizza is coming together so well."
      ],
      place_pizza_items: [
        `Great job. The ${part} looks amazing.`,
        `Nice work adding the ${part}. You're doing great.`,
        `Good job. The pizza has ${part} now, and it looks really good.`
      ],
      bowl_items: [
        `Great job. The ${part} looks fresh and full.`,
        `Nice work adding the ${part}. You're doing great.`,
        `Good job. The bowl is coming together really well.`
      ],
      toss_bowl: [
        "Great job. The salad looks mixed really well.",
        "Nice work tossing the salad. You're doing great.",
        "Good job. The salad looks ready."
      ],
      butter_bread: [
        "Great job. The bread looks buttered really well.",
        "Nice work spreading the butter. You're doing great.",
        "Good job. The bread is ready for cheese."
      ],
      sandwich_layers: [
        "Great job. The cheese looks amazing.",
        "Nice work adding the cheese slices. You're doing great.",
        "Good job. The sandwich is coming together so well."
      ],
      pitcher_items: [
        `Great job. The ${part} looks good.`,
        `Nice work adding the ${part}. You're doing great.`,
        `Good job. The drink is coming together really well.`
      ],
      stir_pitcher: [
        "Great job. The lemonade looks stirred really well.",
        "Nice work mixing the lemonade. You're doing great.",
        "Good job. The drink looks ready."
      ],
      sundae_items: [
        `Great job. The ${part} looks amazing.`,
        `Nice work adding the ${part}. You're doing great.`,
        `Good job. The sundae is coming together so well.`
      ],
      tray_items: [
        `Great job. The ${part} looks good on the tray.`,
        `Nice work adding the ${part}. You're doing great.`,
        `Good job. The tray is coming together really well.`
      ],
      ready_card: [
        "Great job. This order looks ready.",
        "Nice work checking the order. You're doing great.",
        "Good job. Leo can take this one."
      ]
    };

    return pickLine(byType[step.type] || [
      `Great job. The ${part} looks really nice.`,
      `Nice work with the ${part}. You're doing great.`,
      `Good job. This part looks ready.`
    ]);
  }


  function currentStepContextKey() {
    return `${state.orderIndex}:${state.stepIndex}`;
  }

  function clearStepDoneReminder() {
    if (stepDoneReminderTimer) {
      clearTimeout(stepDoneReminderTimer);
      stepDoneReminderTimer = null;
    }
  }
  function nextStepNameForSpeech() {
    const order = currentOrder();
    const next = order.steps[state.stepIndex + 1];

    if (next) return friendlyStepName(next);
    return "finish the order";
  }

  function isGardenSaladVegetableToTossStep(step = currentStep()) {
    const order = currentOrder();
    const next = order.steps[state.stepIndex + 1];
    return Boolean(order?.id === "garden_salad" && step?.id === "veggies" && next?.type === "toss_bowl");
  }

  function teacherMoveAcceptanceLines() {
    if (isGardenSaladVegetableToTossStep()) {
      return [
        "Okay. Let's start tossing the salad.",
        "Got it. We can begin mixing the salad now.",
        "Okay, the vegetables look ready. Let's gently toss the salad."
      ];
    }

    return [
      `Okay. Let's move on to the ${nextStepNameForSpeech()}.`,
      `Got it. We can try the ${nextStepNameForSpeech()} now.`,
      `Okay, this part is ready. Let's go to the ${nextStepNameForSpeech()}.`
    ];
  }

  function stepActionName(step = currentStep()) {
    const map = {
      sauce: "spreading the sauce",
      cheese: "adding the cheese",
      pepperoni: "placing the pepperoni",
      veggies: "adding the vegetables",
      lettuce: "adding the lettuce",
      toss: "tossing the salad",
      butter: "buttering the bread",
      ice: "adding the ice",
      lemons: "squeezing the lemon juice",
      water: "adding the water",
      stir: "stirring the lemonade",
      scoops: "adding the ice cream",
      toppings: "adding the toppings",
      cherry: "adding the cherry",
      main: "adding the meal",
      sides: "adding the drink and fruit",
      ready: "checking the order"
    };

    return map[step?.id] || `working on the ${friendlyStepName(step)}`;
  }
  function teacherLetMeKnowLineForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const order = currentOrder();
    const next = order.steps[state.stepIndex + 1];

    if (step.type === "ready_card") {
      return "Let me know whenever this order feels ready, so Leo can take it to the customer.";
    }

    if (!next) {
      return `Let me know whenever you're finished with the ${part}, so Leo can finish this order.`;
    }

    if (isGardenSaladVegetableToTossStep(step)) {
      return "Let me know whenever you're finished adding vegetables, so we can begin tossing the salad.";
    }

    return `Let me know whenever you're finished with the ${part}, so we can move on to the ${friendlyStepName(next)}.`;
  }
  function teacherDoneReminderLineForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const order = currentOrder();
    const next = order.steps[state.stepIndex + 1];

    if (step.type === "ready_card") {
      return pickLine([
        "Whenever this order feels ready, let me know and Leo can take it to the customer.",
        "When this order feels ready, just let me know and we can have Leo take it."
      ]);
    }

    if (!next) {
      return pickLine([
        `Whenever you're finished with the ${part}, just let me know and Leo can finish this order.`,
        `When the ${part} feels done, let me know and Leo can get this order ready.`,
        `No rush. Keep working on the ${part}, and let me know when it feels ready.`
      ]);
    }

    if (isGardenSaladVegetableToTossStep(step)) {
      return pickLine([
        "Whenever you're finished adding vegetables, just let me know and we can begin tossing the salad.",
        "When the vegetables feel done, let me know and we can start mixing the salad.",
        "No rush. Keep adding vegetables if you want, and let me know when you're ready to toss the salad."
      ]);
    }

    return pickLine([
      `Whenever you're finished with the ${part}, just let me know and we can move on to the ${friendlyStepName(next)}.`,
      `When the ${part} feels done, let me know and we can try the ${friendlyStepName(next)}.`,
      `No rush. Keep working on the ${part}, and let me know when it feels ready.`
    ]);
  }

  function scheduleStepDoneReminder(delay = 10000) {
    clearStepDoneReminder();

    const social = socialStageIndex();
    if (social > 4 || state.gameCompleted) return;

    const contextKey = currentStepContextKey();

    stepDoneReminderTimer = setTimeout(async function () {
      stepDoneReminderTimer = null;

      if (state.gameCompleted || currentStepContextKey() !== contextKey) return;

      if (state.isSpeaking || state.waitingForResponse || state.isListening) {
        scheduleStepDoneReminder(3000);
        return;
      }

      stepDoneReminderCount += 1;
      await speakNow(TEACHER, teacherDoneReminderLineForStep(currentStep()));

      // Keep reminders gentle. After the first reminder, wait longer before another one.
      if (!state.gameCompleted && currentStepContextKey() === contextKey) {
        scheduleStepDoneReminder(stepDoneReminderCount <= 1 ? 18000 : 26000);
      }
    }, delay);
  }
  function leoConfirmedCommentForStep(step = currentStep()) {
    const progress = state.currentProgress || 0;
    const os = orderState();
    const part = friendlyStepName(step);

    if (!state.specialCommentFlags || typeof state.specialCommentFlags !== "object") {
      state.specialCommentFlags = {};
    }

    function oneTimeCheeseComparison() {
      if (state.specialCommentFlags.usedCheeseComparison) return "";
      state.specialCommentFlags.usedCheeseComparison = true;
      return "Wow, you put so much cheese. You must really like cheese. I love cheese too.";
    }

    if (step.type === "paint_sauce") {
      if (progress >= 0.72) {
        return pickLine([
          "Wow, you spread so much sauce already. It looks great. You're doing an amazing job.",
          "That sauce is covering the pizza so well. Great job. You're really good at this.",
          "I can see the sauce reaching all over the pizza. Nice work, this is looking great."
        ]);
      }
      return pickLine([
        "Great job, the sauce is spreading really nicely. You're very good at this.",
        "Wow, I can see a good amount of sauce already. It looks great so far.",
        "Nice work with the sauce. You're doing an amazing job covering the pizza.",
        "I can see the sauce going across the pizza. Great job, you're really good at spreading it."
      ]);
    }

    if (step.type === "sprinkle_cheese") {
      const count = Array.isArray(os.cheeseTokens) ? os.cheeseTokens.length : Math.round(progress * (step.requiredCount || 30));
      if (count >= (step.requiredCount || 30)) {
        const cheeseLine = oneTimeCheeseComparison();
        return cheeseLine || pickLine([
          "That is so much cheese. This pizza is looking amazing. You're doing such a great job.",
          "I can see lots of cheese on the pizza now. Nice, this is one of my favorite parts too.",
          "Wow, this pizza looks extra cheesy. Great job making it look so good."
        ]);
      }
      return pickLine([
        "Nice, I can see the cheese going on. You're doing great.",
        "Good job adding the cheese. The pizza is starting to look really good.",
        "I see more cheese on the pizza now. Great work, keep going when you're ready."
      ]);
    }

    if (step.type === "place_pizza_items") {
      const count = Array.isArray(os.pizzaTokens) ? os.pizzaTokens.length : Math.round(progress * (step.requiredCount || 10));
      if (count >= (step.requiredCount || 10)) {
        return pickLine([
          step.id === "veggies"
            ? "Wow, you added so many vegetables. This pizza looks colorful and amazing."
            : `Wow, you added a lot of ${part}. This pizza is looking great.`,
          `I can see ${part} on so many parts of the pizza. You're doing an amazing job.`,
          `Nice work. The ${part} is spread out really well, and the pizza looks fun now.`
        ]);
      }
      return pickLine([
        `Nice, I can see the ${part} going onto the pizza.`,
        `Good job adding the ${part}. The pizza is starting to look really tasty.`,
        `I see more ${part} on the pizza now. You're doing great.`
      ]);
    }

    if (step.type === "bowl_items") {
      const count = Array.isArray(os.saladItems) ? os.saladItems.length : Math.round(progress * (step.requiredCount || 8));
      if (count >= (step.requiredCount || 8)) {
        return pickLine([
          `Wow, the bowl has so much ${part} now. You're doing an amazing job.`,
          `I can see a lot of ${part} in the bowl. This salad looks great.`,
          `Nice work. The ${part} makes the bowl look really full and fresh.`
        ]);
      }
      return pickLine([
        `Nice, I can see the ${part} falling into the bowl.`,
        `Good job adding the ${part}. The salad is starting to look fresh.`,
        `I see more ${part} in the bowl now. You're doing great.`
      ]);
    }

    if (step.type === "toss_bowl") {
      if (progress >= 0.75) {
        return pickLine([
          "Wow, you mixed that salad really well. It looks great.",
          "The salad looks nicely mixed now. You're doing an amazing job.",
          "I can see everything moving together in the bowl. Nice work."
        ]);
      }
      return pickLine([
        "Nice, I can see the salad starting to mix.",
        "Good job moving the bowl. The salad is starting to come together.",
        "I see the salad pieces moving around now. You're doing great."
      ]);
    }

    if (step.type === "butter_bread") {
      if (progress >= 0.7) {
        return pickLine([
          "Wow, the bread has butter across so much of it now. Great job.",
          "That bread is looking really good. You're doing an amazing job buttering it.",
          "I can see butter covering a lot of the bread. Nice work."
        ]);
      }
      return pickLine([
        "Nice, I can see the butter starting to spread.",
        "Good job with the butter. The bread is starting to look ready.",
        "I see more butter on the bread now. You're doing great."
      ]);
    }

    if (step.type === "sandwich_layers") {
      const count = Array.isArray(os.sandwichLayers) ? os.sandwichLayers.filter(item => item === "cheese").length : Math.round(progress * (step.requiredCount || 3));
      if (count >= (step.requiredCount || 3)) {
        const cheeseLine = oneTimeCheeseComparison();
        return cheeseLine || pickLine([
          "That sandwich is getting so cheesy. You're doing an amazing job.",
          "I can see the cheese slices on the bread now. Nice work.",
          "Wow, that grilled cheese is going to be very cheesy. It looks great."
        ]);
      }
      return pickLine([
        "Nice, I can see the cheese going onto the bread.",
        "Good job adding the cheese. This sandwich is starting to look tasty.",
        "I see a cheese slice on the bread now. You're doing great."
      ]);
    }

    if (step.type === "pitcher_items") {
      if (progress >= 0.75) {
        return pickLine([
          `Wow, I can see plenty of ${part} now. You're doing great.`,
          `The ${part} is helping the lemonade come together. Nice work.`,
          `I see the glass filling with ${part}. This is looking really good.`
        ]);
      }
      return pickLine([
        `Nice, I can see the ${part} going in now.`,
        `Good job adding the ${part}. The drink is starting to come together.`,
        `I see more ${part} in the glass now. You're doing great.`
      ]);
    }

    if (step.type === "stir_pitcher") {
      if (progress >= 0.75) {
        return pickLine([
          "Wow, the lemonade looks really mixed now. Great job.",
          "That lemonade is coming together so well. You're doing an amazing job.",
          "I can see the drink looking mixed now. Nice work."
        ]);
      }
      return pickLine([
        "Nice, I can see the lemonade starting to mix.",
        "Good job stirring. The drink is starting to come together.",
        "I see the lemonade moving around now. You're doing great."
      ]);
    }

    if (step.type === "sundae_items") {
      const count = Array.isArray(os.sundaeItems) ? os.sundaeItems.length : Math.round(progress * (step.requiredCount || 3));
      if (count >= (step.requiredCount || 3)) {
        return pickLine([
          `Wow, that sundae has so much ${part}. It looks amazing.`,
          `I can see lots of ${part} on the sundae. You're doing an amazing job.`,
          `Nice work. The ${part} makes the sundae look really fun.`
        ]);
      }
      return pickLine([
        `Nice, I can see the ${part} going onto the sundae.`,
        `Good job adding the ${part}. The sundae is starting to look great.`,
        `I see more ${part} on the sundae now. You're doing great.`
      ]);
    }

    if (step.type === "tray_items") {
      if (progress >= 0.75) {
        return pickLine([
          `Wow, the ${part} is on the tray now. This looks great.`,
          `I can see the tray coming together with the ${part}. You're doing an amazing job.`,
          `Nice work. The tray is starting to look ready for the customer.`
        ]);
      }
      return pickLine([
        `Nice, I can see the ${part} going onto the tray.`,
        `Good job adding the ${part}. The tray is starting to look good.`,
        `I see more food on the tray now. You're doing great.`
      ]);
    }

    return pickLine([
      `Nice, I can see the ${part} coming together. You're doing great.`,
      `Good job with the ${part}. It is looking really nice so far.`,
      `You're doing an amazing job with the ${part}. Keep going when you're ready.`
    ]);
  }
  async function maybeCommentDuringInteraction() {
    const step = currentStep();
    const os = orderState();
    os.stepCounts = os.stepCounts || {};

    if (state.isSpeaking || state.waitingForResponse || state.isListening) return;

    const social = socialStageIndex();
    const progress = state.currentProgress || 0;
    const confirmedKey = `${step.id}_confirmed_comments`;
    const wonderKey = `${step.id}_wonder_comments`;

    const confirmedNeeded = step.type === "paint_sauce" ? 0.24 : 0.34;
    const wonderNeeded = step.type === "paint_sauce" ? 0.52 : 0.58;

    if (social <= 1) {
      if ((os.stepCounts[confirmedKey] || 0) >= 1) return;
      if (progress < confirmedNeeded) return;
      os.stepCounts[confirmedKey] = (os.stepCounts[confirmedKey] || 0) + 1;
      queueSpeak(WORKER, leoConfirmedCommentForStep(step), { noPassiveResume: false });
      return;
    }

    if (social === 2) {
      if ((os.stepCounts[confirmedKey] || 0) < 1 && progress >= confirmedNeeded) {
        os.stepCounts[confirmedKey] = (os.stepCounts[confirmedKey] || 0) + 1;
        queueSpeak(WORKER, leoConfirmedCommentForStep(step), { noPassiveResume: false });
        return;
      }

      if ((os.stepCounts[wonderKey] || 0) < 1 && progress >= wonderNeeded) {
        os.stepCounts[wonderKey] = (os.stepCounts[wonderKey] || 0) + 1;
        queueSpeak(WORKER, leoWonderLineForStep(step), { noPassiveResume: false });
        return;
      }

      return;
    }

    if (social === 3) {
      if ((os.stepCounts[wonderKey] || 0) >= 1) return;
      if (progress < 0.40) return;
      os.stepCounts[wonderKey] = (os.stepCounts[wonderKey] || 0) + 1;
      queueSpeak(WORKER, leoToTeacherLineForStep(step), { noPassiveResume: false });
      return;
    }

    if ((os.stepCounts[confirmedKey] || 0) >= 1) return;
    if (progress < 0.45) return;
    os.stepCounts[confirmedKey] = (os.stepCounts[confirmedKey] || 0) + 1;
    queueSpeak(WORKER, leoCommentLineForStep(step), { noPassiveResume: false });
  }
  function maybeAbundanceComment(itemLabel, key) {
    const os = orderState();
    if (!os.abundanceComments || typeof os.abundanceComments !== "object") os.abundanceComments = {};
    if (os.abundanceComments[key]) return;
    if (state.isSpeaking || state.waitingForResponse || state.isListening) return;

    os.abundanceComments[key] = true;

    if (!state.specialCommentFlags || typeof state.specialCommentFlags !== "object") {
      state.specialCommentFlags = {};
    }

    const social = socialStageIndex();
    const label = String(itemLabel || "that part").toLowerCase();
    const isCheese = label.includes("cheese");

    if (social <= 2) {
      if (isCheese && !state.specialCommentFlags.usedCheeseComparison) {
        state.specialCommentFlags.usedCheeseComparison = true;
        queueSpeak(WORKER, "Wow, you added a lot of cheese. You must really like cheese. I like cheese too.", { noPassiveResume: false });
        return;
      }

      queueSpeak(WORKER, pickLine([
        `That is so much ${label}. Nice work, you're doing an amazing job.`,
        `I can see plenty of ${label} now. This order is looking great.`,
        `Wow, you added a lot of ${label}. You are making this look really good.`
      ]), { noPassiveResume: false });
      return;
    }

    if (social === 3) return;

    queueSpeak(WORKER, pickLine([
      `Nice work. That ${label} makes the order look full.`,
      `I see plenty of ${label}. That can work.`,
      `That ${label} is helping the order look ready.`
    ]), { noPassiveResume: false });
  }

  function queueSpeak(actor, text, options = {}) {
    speechQueue = speechQueue
      .then(() => speakNow(actor, text, options))
      .catch(error => console.error("Restaurant speech queue error:", error));
    return speechQueue;
  }

  async function speakNow(actor, text, options = {}) {
    const message = cleanText(fillLine(typeof text === "function" ? text() : text));
    if (!message || state.gameCompleted) return;

    pausePassiveListening();
    updateMicStatus(actor === WORKER ? "Leo is talking" : "Teacher is talking", "speaking");
    setSpeakingActor(actor, true);
    state.isSpeaking = true;

    try {
      const response = await fetch("/api/restaurant-game/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speaker: actor, text: message, game_complete: Boolean(options.gameComplete) })
      });
      const data = await response.json();
      if (data.success && data.audio) {
        await playCharacterAudio(actor, data.audio);
      } else {
        await sleep(Math.min(1600, 420 + message.length * 18));
      }
    } catch (error) {
      console.error("Restaurant TTS error:", error);
      await sleep(Math.min(1600, 420 + message.length * 18));
    } finally {
      state.isSpeaking = false;
      setSpeakingActor(actor, false);
      stopMouthAnimation();
      closeMouths();
      updateMicStatus("Listening for done", "listening");
      if (!options.expectsResponse) resumePassiveListeningSoon(350);
    }

    if (options.expectsResponse) {
      await askForResponse(actor, message, options);
    }
  }

  function playCharacterAudio(actor, audioSrc) {
    return new Promise(resolve => {
      if (activeAudio) {
        try { activeAudio.pause(); } catch (error) {}
        activeAudio = null;
      }
      activeAudio = new Audio(audioSrc);
      activeMouthActor = actor;
      let resolved = false;
      const done = () => {
        if (resolved) return;
        resolved = true;
        stopMouthAnimation();
        resolve();
      };
      activeAudio.addEventListener("play", () => startMouthAnimation(actor, activeAudio));
      activeAudio.addEventListener("ended", done);
      activeAudio.addEventListener("error", done);
      activeAudio.addEventListener("pause", () => {
        if (activeAudio && activeAudio.currentTime > 0) done();
      });
      activeAudio.play().catch(done);
    });
  }

  function startMouthAnimation(actor, audioElement) {
    stopMouthAnimation();
    activeMouthActor = actor;
    workerFlapUntil = 0;
    workerNextFlapAt = performance.now() + rand(240, 440);

    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = actor === WORKER ? 0.68 : 0.56;
      sourceNode = audioContext.createMediaElementSource(audioElement);
      sourceNode.connect(analyser);
      analyser.connect(audioContext.destination);
      const data = new Uint8Array(analyser.frequencyBinCount);
      let smoothed = 0;
      let displayedFrame = "closed";
      let heldUntil = 0;
      let cycleSeed = Math.random() * Math.PI * 2;

      function volumeToFrame(value) {
        if (value < 8) return "closed";
        if (value < 19) return "small";
        if (value < 34) return "medium";
        return "wide";
      }

      function chooseWorkerFrame(target, now) {
        // Keep Leo from freezing in one open frame.
        if ((target === "medium" || target === "wide") && now >= workerNextFlapAt) {
          workerFlapUntil = now + rand(52, 92);
          workerNextFlapAt = now + rand(210, 360);
        }

        if (workerFlapUntil && now < workerFlapUntil) {
          return Math.random() < 0.25 ? "closed" : "small";
        }

        // Add a tiny rhythmic up/down movement even while loud speech continues.
        if (target === "wide") {
          return Math.sin(now / 110 + cycleSeed) > 0.22 ? "wide" : "medium";
        }
        if (target === "medium") {
          return Math.sin(now / 125 + cycleSeed) > 0.08 ? "medium" : "small";
        }
        if (target === "small") {
          return Math.sin(now / 165 + cycleSeed) > 0.42 ? "small" : "closed";
        }
        return "closed";
      }

      function animate(now) {
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i += 1) sum += data[i];
        const avg = sum / data.length;
        smoothed = smoothed * 0.78 + avg * 0.22;
        const target = volumeToFrame(smoothed);
        const normalized = Math.min(1, smoothed / 72);
        const scaleX = 1 + normalized * 0.07;
        const scaleY = 1 + normalized * 0.14;

        let nextFrame = target;
        if (actor === WORKER) nextFrame = chooseWorkerFrame(target, now);

        if (now >= heldUntil || nextFrame !== displayedFrame) {
          heldUntil = now + (nextFrame === "wide" ? 92 : nextFrame === "medium" ? 84 : nextFrame === "small" ? 78 : 72);
          displayedFrame = nextFrame;
          if (actor === WORKER) {
            setWorkerFrame(displayedFrame);
          } else {
            setTeacherMouth(displayedFrame, scaleX, scaleY);
          }
        } else if (actor !== WORKER && displayedFrame !== "closed") {
          // Teacher can keep a subtle squash/stretch while holding the same frame.
          setTeacherMouth(displayedFrame, scaleX, scaleY);
        }

        mouthAnimationFrame = requestAnimationFrame(animate);
      }
      mouthAnimationFrame = requestAnimationFrame(animate);
    } catch (error) {
      console.warn("Could not animate mouth:", error);
    }
  }

function stopMouthAnimation() {
    if (mouthAnimationFrame) cancelAnimationFrame(mouthAnimationFrame);
    mouthAnimationFrame = null;
    if (sourceNode) { try { sourceNode.disconnect(); } catch (error) {} }
    if (analyser) { try { analyser.disconnect(); } catch (error) {} }
    if (audioContext) { try { audioContext.close(); } catch (error) {} }
    sourceNode = null;
    analyser = null;
    audioContext = null;
    activeMouthActor = null;
  }

  async function ensureMicPermission() {
    if (state.micDenied) return null;
    if (mediaStream) return mediaStream;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      state.micDenied = true;
      updateMicStatus("Use the done button", "idle");
      return null;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      state.micReady = true;
      updateMicStatus("Listening for done", "listening");
      return mediaStream;
    } catch (error) {
      state.micDenied = true;
      updateMicStatus("Use the done button", "idle");
      return null;
    }
  }

  function recognitionConstructor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function pausePassiveListening() {
    if (passiveRestartTimer) clearTimeout(passiveRestartTimer);
    passiveRestartTimer = null;
    if (passiveRecognition) {
      const recognition = passiveRecognition;
      passiveRecognition = null;
      try { recognition.onend = null; recognition.stop(); } catch (error) {}
    }
  }

  function resumePassiveListeningSoon(delay = 500) {
    if (state.gameCompleted) return;
    if (passiveRestartTimer) clearTimeout(passiveRestartTimer);
    passiveRestartTimer = setTimeout(startPassiveDoneListening, delay);
  }

  function startPassiveDoneListening() {
    if (state.gameCompleted || state.isSpeaking || state.waitingForResponse || state.isListening) return;
    const Recognition = recognitionConstructor();
    if (!Recognition) {
      updateMicStatus(state.micDenied ? "Use the done button" : "Listening for done", state.micDenied ? "idle" : "listening");
      return;
    }
    pausePassiveListening();
    try {
      const recognition = new Recognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      passiveRecognition = recognition;
      recognition.onresult = event => {
        if (state.isSpeaking || state.waitingForResponse || state.isListening) return;
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const transcript = cleanTranscript(event.results[i][0]?.transcript || "");
          if (transcriptHasDoneIntent(transcript)) {
            pausePassiveListening();
            void handleDoneStep("voice");
            return;
          }
        }
      };
      recognition.onerror = () => { passiveRecognition = null; resumePassiveListeningSoon(1200); };
      recognition.onend = () => { passiveRecognition = null; resumePassiveListeningSoon(1200); };
      recognition.start();
      updateMicStatus("Listening for done", "listening");
    } catch (error) {
      passiveRecognition = null;
      resumePassiveListeningSoon(1500);
    }
  }

  function cleanTranscript(text) {
    return String(text || "").toLowerCase().replace(/[^a-z0-9'\s]/g, " ").replace(/\s+/g, " ").trim();
  }

  function transcriptHasDoneIntent(text) {
    const lower = cleanTranscript(text);
    if (!lower) return false;
    return ["done", "finished", "ready", "all done", "i'm done", "im done", "i am done", "next", "move on", "looks ready", "it's ready", "its ready"].some(phrase => lower.includes(phrase));
  }

  async function askForResponse(actor, message, options = {}) {
    state.waitingForResponse = true;
    state.isListening = true;
    pausePassiveListening();
    updateMicStatus("Listening", "listening");
    const transcript = await startResponseWindow(options.responseSeconds || 4.6);
    state.waitingForResponse = false;
    state.isListening = false;

    if (transcript) {
      await handleSpeech(transcript, options);
    } else {
      await handleNoSpeech(options);
    }
    resumePassiveListeningSoon(650);
  }

  async function startResponseWindow(seconds) {
    const stream = await ensureMicPermission();
    const Recognition = recognitionConstructor();
    let browserTranscript = "";
    let stopResolve;
    const donePromise = new Promise(resolve => { stopResolve = resolve; });

    if (Recognition) {
      try {
        responseRecognition = new Recognition();
        responseRecognition.continuous = true;
        responseRecognition.interimResults = true;
        responseRecognition.lang = "en-US";
        responseRecognition.onresult = event => {
          let combined = "";
          for (let i = 0; i < event.results.length; i += 1) combined += " " + (event.results[i][0]?.transcript || "");
          browserTranscript = cleanTranscript(combined);
          if (browserTranscript && browserTranscript.split(" ").length >= 1) {
            setTimeout(() => stopResolve(browserTranscript), 700);
          }
        };
        responseRecognition.start();
      } catch (error) { responseRecognition = null; }
    }

    if (stream && window.MediaRecorder) {
      try {
        responseChunks = [];
        responseRecorder = new MediaRecorder(stream, getRecorderOptions());
        responseRecorder.ondataavailable = event => { if (event.data && event.data.size) responseChunks.push(event.data); };
        responseRecorder.onstop = async () => {
          if (browserTranscript) return;
          const text = await transcribeChunks(responseChunks);
          stopResolve(cleanTranscript(text));
        };
        responseRecorder.start();
      } catch (error) { responseRecorder = null; }
    }

    responseTimer = setTimeout(() => {
      dlog("response window timeout", { hasBrowserTranscript: !!browserTranscript, hasRecorder: !!responseRecorder });

      if (browserTranscript || !responseRecorder || responseRecorder.state === "inactive") {
        stopResolve(browserTranscript || "");
        return;
      }

      // Stop the recorder so its own onstop handler can run server-side
      // transcription instead of discarding whatever audio was captured in
      // this window -- mirrors Activity 1 (Match Cards), where the hard
      // timeout always stops-and-transcribes rather than resolving empty.
      stopResponseCapture();
    }, seconds * 1000);
    const transcript = await donePromise;
    stopResponseCapture();
    dlog("response window resolved", { transcript });
    return cleanTranscript(transcript || browserTranscript || "");
  }

  function stopResponseCapture() {
    if (responseTimer) clearTimeout(responseTimer);
    responseTimer = null;
    if (responseRecognition) {
      try { responseRecognition.stop(); } catch (error) {}
      responseRecognition = null;
    }
    if (responseRecorder && responseRecorder.state !== "inactive") {
      try { responseRecorder.stop(); } catch (error) {}
    }
    responseRecorder = null;
  }

  function getRecorderOptions() {
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
    for (const type of types) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(type)) return { mimeType: type };
    }
    return undefined;
  }

  async function transcribeChunks(chunks) {
    if (!chunks || !chunks.length) return "";
    try {
      const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
      const form = new FormData();
      form.append("audio", blob, "restaurant-response.webm");
      const response = await fetch("/api/restaurant-game/transcribe", { method: "POST", body: form });
      const data = await response.json();
      return data.success ? data.text || "" : "";
    } catch (error) {
      console.warn("Restaurant transcription error:", error);
      return "";
    }
  }


  function classifyMoveOnChoice(text) {
    const lower = cleanTranscript(text);
    const words = new Set((lower.match(/[a-z0-9']+/g) || []));

    const keepPhrases = [
      "not yet", "more time", "keep working", "keep going", "keep adding",
      "a little more", "do more", "more", "not done", "not finished", "wait"
    ];

    const movePhrases = [
      "move on", "next", "next step", "next part", "ready", "done", "finished",
      "all done", "i'm done", "im done", "i am done", "yes", "yeah", "yep", "sure", "okay", "ok",
      "oven", "go in the oven", "go to the oven", "send it", "send to the chef"
    ];

    if (keepPhrases.some(phrase => lower.includes(phrase))) return "keep";
    if (movePhrases.some(phrase => lower.includes(phrase))) return "move";
    if (words.has("no") || words.has("nope") || words.has("nah")) return "keep";

    return "move";
  }

  function classifyOrderContinueChoice(text) {
    const lower = cleanTranscript(text);
    const words = new Set((lower.match(/[a-z0-9']+/g) || []));

    const stopPhrases = [
      "be done", "done helping", "finish helping", "stop helping", "stop",
      "end", "all done", "i'm done", "im done", "i am done", "dashboard", "not now"
    ];

    const continuePhrases = [
      "move on", "next order", "next", "keep helping", "continue", "another",
      "yes", "yeah", "yep", "sure", "okay", "ok", "let's go", "lets go"
    ];

    if (stopPhrases.some(phrase => lower.includes(phrase))) return "stop";
    if (words.has("no") || words.has("nope") || words.has("nah")) return "stop";
    if (continuePhrases.some(phrase => lower.includes(phrase))) return "continue";

    return "continue";
  }

  async function handleSpeech(transcript, options = {}) {
    const cleaned = cleanTranscript(transcript);
    if (!cleaned) return;

    state.spokenResponses += 1;
    state.spokenWords += countWords(cleaned);

    if (options.source === "worker-direct") state.workerDirectResponses += 1;
    if (options.source === "teacher-redirect") state.teacherRedirects += 1;

    if (options.intent === "order_continue_choice") {
      const choice = classifyOrderContinueChoice(cleaned);

      if (choice === "stop") {
        await stopHelpingForToday();
        return;
      }

      const continueActor = options.source === "worker-order-choice" ? WORKER : TEACHER;
      await speakNow(continueActor, pickLine(continueActor === WORKER ? [
        "Great. I have another order ready for us.",
        "Okay, let's keep helping customers together.",
        "Awesome. Let's help with the next order."
      ] : [
        "Okay. Let's help Leo with the next order.",
        "Great. We can move on to the next order together.",
        "Okay. Leo has the next order ready for us."
      ]));

      enterPreCookingMode();
      await sleep(420);
      await introduceOrder();
      return;
    }

    if (options.intent === "preference_choice") {
      await speakNow(WORKER, pickLine([
        "Nice choice. I like hearing that.",
        "Good choice. That makes sense.",
        "I like that answer. Let's keep making the order.",
        "That is a good pick. I like hearing what you think."
      ]));
      await sleep(140);
      await speakNow(TEACHER, pickLine([
        "That works.",
        "Okay, let's keep going.",
        "Nice. We can keep helping Leo.",
        "Good idea. Let's keep working on the order."
      ]));
      return;
    }

    if (options.intent === "ready_check") {
      if (options.source === "worker-move-choice" || options.source === "teacher-move-redirect") {
        await completeMoveChoice(classifyMoveOnChoice(cleaned), options.source === "worker-move-choice" ? WORKER : TEACHER);
        return;
      }

      if (options.source === "teacher-move-choice") {
        const choice = classifyMoveOnChoice(cleaned);

        if (choice === "keep") {
          const keepLines = isGardenSaladVegetableToTossStep()
            ? [
                "Okay. Keep adding vegetables for a little longer.",
                "Sure. Add a few more vegetables when you want.",
                "Okay. We can stay with the vegetables before tossing the salad."
              ]
            : [
                `Okay. Keep working on the ${friendlyStepName(currentStep())}.`,
                "Sure. Add a little more when you want.",
                "Okay. We can stay on this part for a little longer."
              ];
          await speakNow(TEACHER, pickLine(keepLines));
          scheduleStepDoneReminder(11000);
          return;
        }

        if (!nextStepIsReadyCard()) {
          await speakNow(TEACHER, pickLine(teacherMoveAcceptanceLines()));
        }

        await completeStepAfterReadyCheck({ skipPraise: true });
        return;
      }

      if (options.source === "worker-direct") {
        await speakNow(WORKER, pickLine([
          "Nice choice.",
          "Good choice.",
          "Okay. I like that idea.",
          "That sounds good.",
          "That works for this order."
        ]));
        await sleep(160);
        await speakNow(TEACHER, pickLine([
          "Let's use that idea.",
          "That works for this part.",
          "Keep going when you're ready.",
          "That sounds good for this order."
        ]));
      } else if (options.source === "worker-indirect" || options.source === "teacher-redirect") {
        await speakNow(WORKER, pickLine([
          "Great choice. That helps me know what to do.",
          "Nice answer. That works for this order.",
          "Good choice. I like hearing that.",
          "That makes sense for this part."
        ]));
      } else {
        await speakNow(TEACHER, pickLine([
          "Good idea.",
          "Nice. Let's keep helping Leo.",
          "Okay. That sounds good.",
          "That works for this part."
        ]));
      }

      await completeStepAfterReadyCheck({ skipPraise: true });
      return;
    }

    if (options.intent === "friendly_choice") {
      await queueSpeak(TEACHER, pickLine([
        "Great. We can help Leo together.",
        "Okay. I will stay right here while we help Leo.",
        "That sounds good. We can start together."
      ]));
      return;
    }

    await queueSpeak(TEACHER, pickLine([
      "Good idea.",
      "Nice. Let's keep going.",
      "That sounds good.",
      "That will work for this order."
    ]));
  }


  async function handleNoSpeech(options = {}) {
    state.silentWindows += 1;

    if (options.intent === "order_continue_choice") {
      await speakNow(TEACHER, pickLine([
        "That's okay. We can be done helping Leo for today.",
        "No rush. We can stop here for today.",
        "That's okay. Leo will remember where you finished."
      ]));
      await saveProgress({
        order_index: state.orderIndex,
        step_index: 0,
        orders_completed: state.ordersCompleted
      });
      window.location.href = "/dashboard";
      return;
    }

    if (options.intent === "friendly_choice") {
      await speakNow(TEACHER, "That's okay. We can start together, and I will help you.");
      return;
    }

    if (options.intent === "preference_choice") {
      if (options.source === "worker-preference") {
        await speakNow(TEACHER, stageThreeTeacherBridgeLines(currentOrder())[Math.min(options.preferenceIndex || 0, stageThreeTeacherBridgeLines(currentOrder()).length - 1)], {
          expectsResponse: true,
          intent: "preference_choice",
          source: "teacher-preference-redirect",
          responseActor: TEACHER,
          preferenceIndex: options.preferenceIndex || 0,
          responseSeconds: 4.4
        });
        return;
      }

      await speakNow(TEACHER, pickLine([
        "That's okay. We can keep making the order.",
        "No rush. We can keep helping Leo.",
        "That's okay. Let's keep going together."
      ]));
      return;
    }

    if (options.intent === "ready_check") {
      const ready = stepReady();

      if (options.source === "worker-move-choice") {
        await speakNow(TEACHER, teacherMoveBridgeLineForStep(currentStep()), {
          expectsResponse: true,
          intent: "ready_check",
          source: "teacher-move-redirect",
          responseActor: TEACHER,
          responseSeconds: 4.4
        });
        return;
      }

      if (options.source === "teacher-move-redirect") {
        await speakNow(TEACHER, pickLine([
          "Okay. We can use that idea and move on.",
          "That's okay. I think we can move on together.",
          "No rush. We can go to the next part."
        ]));
        await completeStepAfterReadyCheck({ skipPraise: true });
        return;
      }

      if (options.source === "teacher-move-choice") {
        await speakNow(TEACHER, pickLine([
          `That's okay. We can keep working on the ${friendlyStepName(currentStep())}.`,
          "No rush. You can add a little more when you want.",
          "That's okay. We can stay on this part for now."
        ]));
        scheduleStepDoneReminder(11000);
        return;
      }

      if (options.source === "worker-indirect") {
        const questionIndex = Number.isFinite(options.questionIndex) ? options.questionIndex : 0;
        await speakNow(TEACHER, teacherBridgeAnswerForStep(currentStep(), questionIndex), {
          expectsResponse: true,
          intent: "ready_check",
          source: "teacher-redirect",
          responseActor: TEACHER,
          questionIndex,
          responseSeconds: 4.3
        });
        return;
      }

      if (options.source === "worker-direct") {
        await speakNow(WORKER, pickLine([
          "That's okay. We can keep helping with the order.",
          "No rush. The Teacher can help.",
          "That's okay. We can still make this order."
        ]));
        await sleep(150);
        await speakNow(TEACHER, pickLine([
          "That's okay. Keep going when you're ready.",
          "No rush. You can add more when you want.",
          "That's okay. Take your time."
        ]));

        if (ready) {
          await completeStepAfterReadyCheck({ skipPraise: true });
        }

        return;
      }

      if (ready) {
        await speakNow(TEACHER, pickLine([
          "That's okay. I think this part looks ready.",
          "No rush. This part looks ready to me.",
          "That's okay. We can move on when it feels ready."
        ]));
        await completeStepAfterReadyCheck({ skipPraise: true });
      } else {
        await speakNow(TEACHER, pickLine([
          "That's okay. We can keep working on this part.",
          "No rush. You can add a little more.",
          "That's okay. Take your time with this part."
        ]));
      }

      return;
    }

    await queueSpeak(TEACHER, "That's okay. We can keep helping in the restaurant.");
  }


  function childPrefix() {
    return childName && childName.toLowerCase() !== "there" ? `${childName}, ` : "";
  }


  function nextStepIsReadyCard(order = currentOrder(), stepIndex = state.stepIndex) {
    const next = order.steps[stepIndex + 1];
    return Boolean(next && next.type === "ready_card");
  }

  function orderReadyDestinationForSpeech(order = currentOrder()) {
    if (order.id.includes("pizza")) return "go in the oven";
    if (order.id === "grilled_cheese") return "go to the chef";
    if (order.id === "kids_meal") return "go to the table";
    return "go to the customer";
  }

  function teacherOrderContinueQuestion(order = currentOrder()) {
    const item = friendlyOrderName(order);
    if (order.id.includes("pizza")) {
      return `While this ${item} goes in the oven, do you want to move on to the next order, or be done helping Leo for today?`;
    }
    return `While Leo gets this ${item} ready for the customer, do you want to move on to the next order, or be done helping Leo for today?`;
  }

  function leoOrderContinueQuestion(order = currentOrder()) {
    const item = friendlyOrderName(order);
    if (order.id.includes("pizza")) {
      return `While this ${item} goes in the oven, do you guys want to help me with another order, or do you guys want to be done helping for today?`;
    }
    if (order.id === "grilled_cheese") {
      return `While the chef cooks this ${item}, do you guys want to help me with another order, or do you guys want to be done helping for today?`;
    }
    return `While I get this ${item} ready for the customer, do you guys want to help me with another order, or do you guys want to be done helping for today?`;
  }

  function leoOrderFinishedLine(order = currentOrder()) {
    const item = friendlyOrderName(order);
    if (order.id.includes("pizza")) {
      return pickLine([
        `Great. That means the ${item} is done. You did a great job with this order.`,
        `Amazing job. This ${item} is ready for the oven now. You helped so much.`,
        `Nice work. The ${item} is finished, and it looks great. You did awesome with this order.`
      ]);
    }

    return pickLine([
      `Great. That means the ${item} is done. You did a great job with this order.`,
      `Amazing job. This ${item} is ready for the customer now. You helped so much.`,
      `Nice work. The ${item} is finished, and it looks great. You did awesome with this order.`
    ]);
  }

  async function stopHelpingForToday() {
    await saveProgress({
      order_index: state.orderIndex,
      step_index: 0,
      orders_completed: state.ordersCompleted
    });

    await speakNow(TEACHER, pickLine([
      "Okay. We can be done helping Leo for today.",
      "That's okay. We can stop here for today.",
      "Okay. Leo will remember where you finished."
    ]));

    window.location.href = "/dashboard";
  }
  function teacherMoveOnQuestionForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const order = currentOrder();
    const next = order.steps[state.stepIndex + 1];

    if (nextStepIsReadyCard()) {
      return `Do you think it is ready to ${orderReadyDestinationForSpeech()}, or would you like to add a little more ${part} first?`;
    }

    if (step.type === "ready_card") {
      return "Do you think this order is ready for the customer, or would you like to look at it a little more first?";
    }

    if (!next) {
      return `Do you think it is ready to ${orderReadyDestinationForSpeech()}, or would you like to do a little more with the ${part} first?`;
    }

    if (isGardenSaladVegetableToTossStep(step)) {
      return "Do you want to keep adding vegetables, or are you ready to begin tossing the salad?";
    }

    return `Are you ready to move on to the ${friendlyStepName(next)}, or would you like to do a little more with the ${part} first?`;
  }

  function leoDonePraiseForStep(step = currentStep()) {
    const part = friendlyStepName(step);
    const action = stepActionName(step);

    if (step.type === "ready_card") {
      return pickLine([
        "Great job. This order looks amazing. You helped so much.",
        "Nice work. This order came together really well. You're great at this.",
        "Wow, this order looks ready. You did such an amazing job helping."
      ]);
    }

    return pickLine([
      `Great job. The ${part} is looking amazing so far.`,
      `Nice work ${action}. You're doing such a great job.`,
      `Wow, you did the ${part} step really well. It looks great.`
    ]);
  }

  async function handleDoneStep() {
    if (state.isSpeaking || state.waitingForResponse) return;

    setDoneButton(true);
    clearStepDoneReminder();

    const step = currentStep();
    const social = socialStageIndex();
    const ready = stepReady();

    if (!ready && step.type !== "ready_card") {
      const actor = social <= 2 ? TEACHER : WORKER;
      await speakNow(actor, pickLine([
        `It is looking good already. A little more could help before we move on.`,
        `This part is started nicely. We can add a little more first.`,
        `No rush. This part can use a little more before the next step.`
      ]));
      if (social <= 2) scheduleStepDoneReminder(10000);
      setDoneButton(false);
      return;
    }

    if (social <= 2) {
      await speakNow(WORKER, leoDonePraiseForStep(step));
      await sleep(150);
      await speakNow(TEACHER, teacherMoveOnQuestionForStep(step), {
        expectsResponse: true,
        intent: "ready_check",
        source: "teacher-move-choice",
        responseActor: TEACHER,
        responseSeconds: 5.5
      });
      setDoneButton(false);
      return;
    }

    await speakNow(WORKER, leoDonePraiseForStep(step));
    await sleep(150);

    const isLastStepInOrder = state.stepIndex >= currentOrder().steps.length - 1;
    if (isLastStepInOrder) {
      await completeStepAfterReadyCheck({ skipPraise: true });
      setDoneButton(false);
      return;
    }

    state.moveChoiceCounter = Number(state.moveChoiceCounter || 0) + 1;
    const shouldAskMoveChoice = state.moveChoiceCounter % 2 === 1;

    if (!shouldAskMoveChoice) {
      await speakNow(WORKER, pickLine([
        `Let's move on to the ${nextStepNameForSpeech()} now.`,
        `Great. We can go to the ${nextStepNameForSpeech()} next.`,
        `Nice work. Let's keep the order going with the ${nextStepNameForSpeech()}.`
      ]));
      await completeStepAfterReadyCheck({ skipPraise: true });
      setDoneButton(false);
      return;
    }

    await speakNow(WORKER, workerMoveOnQuestionForStep(step), {
      expectsResponse: true,
      intent: "ready_check",
      source: "worker-move-choice",
      responseActor: WORKER,
      responseSeconds: 5.0
    });

    setDoneButton(false);
  }



  async function completeStepAfterReadyCheck(options = {}) {
    clearStepDoneReminder();
    stepDoneReminderCount = 0;
    const step = currentStep();
    const social = socialStageIndex();
    const order = currentOrder();

    if (!options.skipPraise) {
      await speakNow(social <= 1 ? TEACHER : WORKER, completionPraiseForStep(step));
    }

    state.stepsCompleted += 1;

    if (step.type === "paint_sauce") orderState().sauceDone = true;
    if (step.type === "sprinkle_cheese") orderState().cheeseDone = true;
    if (step.type === "butter_bread") orderState().butterDone = true;
    if (order.id === "grilled_cheese" && step.id === "cheese") orderState().sandwichTop = true;

    if (social <= 2 && nextStepIsReadyCard(order, state.stepIndex)) {
      await finishCurrentOrder();
      return;
    }

    if (state.stepIndex >= order.steps.length - 1) {
      await finishCurrentOrder();
      return;
    }

    state.stepIndex += 1;

    // For pizza ready checks, do not redraw the pizza. Keep the child's
    // actual sauce/cheese/topping result visible and just update the left card.
    if (isPizzaOrder(order) && currentStep().type === "ready_card") {
      updateHeader();
      await saveProgress();
      await sleep(220);
      await giveStepIntro();
      return;
    }

    renderCurrentWorkScene();
    await sleep(220);
    await giveStepIntro();
  }



  async function finishCurrentOrder() {
    const order = currentOrder();
    const completedOrderIndex = state.orderIndex;
    const social = socialStageIndex();

    await showCompletionToast(order);

    state.ordersCompleted = Math.max(state.ordersCompleted, completedOrderIndex + 1);

    if (completedOrderIndex >= ORDERS.length - 1) {
      await speakNow(WORKER, leoOrderFinishedLine(order));
      await saveProgress({
        orders_completed: state.ordersCompleted,
        order_index: completedOrderIndex,
        step_index: 0
      });
      await finishActivity();
      return;
    }

    const nextOrderIndex = completedOrderIndex + 1;

    // Round-level save: finishing order 1 should reopen at order 2,
    // and leaving mid-order should reopen at the beginning of that same order.
    await saveProgress({
      orders_completed: state.ordersCompleted,
      order_index: nextOrderIndex,
      step_index: 0
    });

    if (social <= 2) {
      await speakNow(WORKER, leoOrderFinishedLine(order));

      state.orderIndex = nextOrderIndex;
      state.stepIndex = 0;
      await saveProgress({
        orders_completed: state.ordersCompleted,
        order_index: state.orderIndex,
        step_index: 0
      });

      await sleep(160);
      await speakNow(TEACHER, teacherOrderContinueQuestion(order), {
        expectsResponse: true,
        intent: "order_continue_choice",
        source: "teacher-order-choice",
        responseActor: TEACHER,
        responseSeconds: 5.5
      });
      return;
    }

    await speakNow(WORKER, leoOrderFinishedLine(order));

    state.orderIndex = nextOrderIndex;
    state.stepIndex = 0;
    await saveProgress({
      orders_completed: state.ordersCompleted,
      order_index: state.orderIndex,
      step_index: 0
    });

    await sleep(160);
    await speakNow(WORKER, leoOrderContinueQuestion(order), {
      expectsResponse: true,
      intent: "order_continue_choice",
      source: "worker-order-choice",
      responseActor: WORKER,
      responseSeconds: 5.5
    });
  }


  async function showCompletionToast(order) {
    const toast = document.createElement("div");
    toast.className = "completion-toast";
    toast.innerHTML = `<h2>${order.icon} Order ready!</h2><p>${order.title} is finished. I can help the customer now.</p>`;
    document.body.appendChild(toast);
    await sleep(1450);
    toast.remove();
  }

  function enterPreCookingMode() {
    if (stage) stage.classList.add("pre-cooking");
    if (workZone) workZone.innerHTML = "";
    currentSceneController = null;
  }

  function enterCookingMode() {
    if (stage) stage.classList.remove("pre-cooking");
    renderCurrentWorkScene();
  }


  function ordinalOrderName(index) {
    const names = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"];
    return names[index] || `order ${index + 1}`;
  }

  async function introduceOrder() {
    enterPreCookingMode();

    const order = currentOrder();
    updateHeader();

    const social = socialStageIndex();
    const ordinal = ordinalOrderName(state.orderIndex);

    if (state.isReturningSession) {
      state.isReturningSession = false;
      await speakNow(TEACHER, "Welcome back to the restaurant game.");
      await speakNow(WORKER, `Welcome back. The current order is ${order.title}.`);
      await speakNow(WORKER, `Let's keep helping me make this ${friendlyOrderName(order)}.`);
      await speakNow(TEACHER, "We will start this order from the beginning, so the food area is fresh again.");
    } else if (state.orderIndex === 0) {
      await speakNow(TEACHER, "Hi. It's me, the Teacher. Today we are going to help at a restaurant.");
      await speakNow(TEACHER, "I want to introduce you to someone new. This is Leo. He works here at the restaurant.");
      await speakNow(WORKER, "Hi. I'm Leo. I'll watch the orders and cheer you on while you help.");
      await speakNow(TEACHER, "I will stay with you while we help Leo with some food orders.");
      await speakNow(WORKER, `The ${ordinal} order is ${order.title}.`);
      await speakNow(TEACHER, "I will help with the first orders, and Leo can watch how the food comes together.");
    } else if (social === 1) {
      await speakNow(WORKER, `The ${ordinal} order is ${order.title}.`);
      await speakNow(TEACHER, "I will walk us through this one too.");
      await speakNow(WORKER, "I can watch how this order comes together. I bet it is going to look great.");
    } else if (social === 2) {
      await speakNow(WORKER, `The ${ordinal} order is ${order.title}.`);
      await speakNow(WORKER, `I wonder how this ${friendlyOrderName(order)} will turn out.`);
      await speakNow(TEACHER, "I will still help with the steps.");
    } else if (social === 3) {
      await speakNow(WORKER, `The ${ordinal} order is ${order.title}.`);
      await speakNow(TEACHER, "I will stay right here while we keep helping Leo.");
      await speakNow(WORKER, `Let's keep making this ${friendlyOrderName(order)} together.`);
    } else {
      await speakNow(WORKER, `The ${ordinal} order is ${order.title}. I can help lead this one.`);
      await speakNow(TEACHER, "I will still be right here with you.");
    }

    enterCookingMode();
    await sleep(140);
    await giveStepIntro();
  }



  function actionInstructionLine(step) {
    if (!step) return "";
    const type = step.type || "";

    if (type === "paint_sauce") return "For this part, press and drag inside the middle of the pizza to spread the sauce across the crust.";
    if (type === "sprinkle_cheese") return "For this part, press and drag over the pizza to sprinkle cheese wherever it looks good.";
    if (type === "place_pizza_items") return "For this part, tap on the pizza wherever you want the toppings to go.";
    if (type === "bowl_items") return "For this part, tap inside the bowl and the salad pieces will fall in.";
    if (type === "toss_bowl") return "For this part, tap or drag around the bowl to gently mix the salad.";
    if (type === "butter_bread") return "For this part, press and drag across the bread to spread the butter.";
    if (type === "sandwich_layers") return "For this part, tap the bread to add cheese slices.";
    if (type === "pitcher_items") {
      if (step.id === "ice") return "For this part, tap the glass to drop in ice cubes.";
      if (step.id === "lemons") return "For this part, tap to squeeze lemon juice into the glass.";
      return "For this part, tap the glass to pour in water.";
    }
    if (type === "stir_pitcher") return "For this part, drag inside the glass to stir the lemonade.";
    if (type === "sundae_items") return "For this part, tap the bowl to add each sundae piece.";
    if (type === "tray_items") return "For this part, tap the tray to add the next piece of the meal.";
    if (type === "ready_card") return "For this part, look at the order and decide if it feels ready for the customer.";

    return step.instruction || "You can add this part wherever it looks good.";
  }


  function instructionKeyForStep(step = currentStep()) {
    if (!step) return "";
    const type = step.type || "step";
    const id = step.id || step.title || "part";
    // Same ingredient + same interaction style should only receive the full "how to use it" explanation once.
    return `${type}:${id}`;
  }

  function shouldExplainActionForStep(step = currentStep()) {
    if (!state.seenInstructionKeys || typeof state.seenInstructionKeys !== "object") {
      state.seenInstructionKeys = {};
    }

    if (!step || step.type === "ready_card") return false;

    const key = instructionKeyForStep(step);
    if (!key) return false;
    if (state.seenInstructionKeys[key]) return false;

    state.seenInstructionKeys[key] = true;
    return true;
  }

  function teacherShortRepeatLineForStep(step = currentStep()) {
    const part = friendlyStepName(step);

    const byType = {
      paint_sauce: [
        "You already know this part. Spread the sauce wherever it looks good.",
        "This is sauce again. Put it where you think it should go.",
        "You can use the sauce the same way as before."
      ],
      sprinkle_cheese: [
        "You already know this part. Add the cheese wherever it looks good.",
        "This is cheese again. Put it where you think it should go.",
        "You can sprinkle the cheese the same way as before."
      ],
      place_pizza_items: [
        `Now add the ${part}. Put it wherever it looks good.`,
        `You can place the ${part} wherever you want it to go.`,
        `This part is the ${part}. Choose where it should go.`
      ],
      bowl_items: [
        `Now add the ${part}. Put it wherever it looks good in the bowl.`,
        `You can add the ${part} to the bowl.`,
        `This part is the ${part}. Choose where it should go.`
      ],
      toss_bowl: [
        "Now mix the salad gently.",
        "You can toss the salad until it looks ready.",
        "This is the mixing part again. Move it how you want."
      ],
      butter_bread: [
        "Now spread the butter on the bread.",
        "You can butter the bread wherever it looks good.",
        "This is the butter part. Cover the bread how you want."
      ],
      sandwich_layers: [
        "Now add the cheese slices to the bread.",
        "You can put the cheese wherever it fits.",
        "This part is cheese slices. Place them on the bread."
      ],
      pitcher_items: [
        `Now add the ${part}.`,
        `You can put in the ${part} when you're ready.`,
        `This part is the ${part}. Add it where it belongs.`
      ],
      stir_pitcher: [
        "Now stir the lemonade gently.",
        "You can mix the lemonade until it looks ready.",
        "This is the stirring part. Stir it how you want."
      ],
      sundae_items: [
        `Now add the ${part}.`,
        `You can put the ${part} wherever it looks good.`,
        `This part is the ${part}. Choose where it should go.`
      ],
      tray_items: [
        `Now add the ${part} to the tray.`,
        `You can put the ${part} wherever it fits.`,
        `This part is the ${part}. Choose a spot on the tray.`
      ]
    };

    return pickLine(byType[step.type] || [
      `Now work on the ${part}.`,
      `You can add the ${part} wherever it looks good.`,
      `Take your time with the ${part}.`
    ]);
  }


  function indirectQuestionForStep(step) {
    return leoDirectQuestionForStep(step || currentStep());
  }



  function teacherBridgeAnswerForStep(step, questionIndex = 0) {
    const part = friendlyStepName(step || currentStep());
    const byType = {
      paint_sauce: [
        "Hmm, I think the sauce could reach the edges. What do you think?",
        "I would spread the sauce a little more in the middle. What do you think?"
      ],
      sprinkle_cheese: [
        "I like lots of cheese on pizza. What do you think?",
        "I would spread the cheese out. What do you think?"
      ],
      place_pizza_items: [
        `I would spread the ${part} across the pizza. What do you think?`,
        `I think different slices could get some ${part}. What do you think?`
      ],
      bowl_items: [
        `I would add the ${part} near the middle. What do you think?`,
        `I think the bowl could use a little more ${part}. What do you think?`
      ],
      toss_bowl: [
        "I think gentle mixing works well. What do you think?",
        "I think it could use a little more mixing. What do you think?"
      ],
      butter_bread: [
        "I would put butter near the edges too. What do you think?",
        "I think the bread looks almost ready for cheese. What do you think?"
      ],
      sandwich_layers: [
        "I would put the cheese in the middle. What do you think?",
        "I think more cheese could work here. What do you think?"
      ],
      pitcher_items: [
        `I think a little more ${part} could work. What do you think?`,
        `I think the ${part} looks close to ready. What do you think?`
      ],
      stir_pitcher: [
        "I think the lemonade looks close to mixed. What do you think?",
        "I would stir it a little more. What do you think?"
      ],
      sundae_items: [
        `I would put the ${part} near the top. What do you think?`,
        `I think this ${part} looks good here. What do you think?`
      ],
      tray_items: [
        `I would put the ${part} on the side of the tray. What do you think?`,
        `I think the tray is looking ready. What do you think?`
      ],
      ready_card: [
        "I think this order looks ready. What do you think?",
        "I think this looks ready for the customer. What do you think?"
      ]
    };

    const lines = byType[(step || currentStep()).type] || [
      `I think the ${part} looks good. What do you think?`,
      `I think this part is close to ready. What do you think?`
    ];

    return fillLine(lines[Math.min(questionIndex, lines.length - 1)] || lines[0]);
  }



  async function giveStepIntro() {
    clearStepDoneReminder();
    stepDoneReminderCount = 0;

    const step = currentStep();
    const social = socialStageIndex();
    const instruction = actionInstructionLine(step);
    const explainAction = shouldExplainActionForStep(step);

    if (social === 1) {
      await speakNow(TEACHER, teacherLeadLineForStep(step));
      await speakNow(TEACHER, explainAction ? instruction : teacherShortRepeatLineForStep(step));
      await speakNow(TEACHER, teacherLetMeKnowLineForStep(step));
      scheduleStepDoneReminder(10000);
      return;
    }

    if (social === 2) {
      await speakNow(TEACHER, teacherLeadLineForStep(step));
      await speakNow(TEACHER, explainAction ? instruction : teacherShortRepeatLineForStep(step));
      await sleep(120);
      await speakNow(WORKER, leoWonderLineForStep(step));
      await sleep(120);
      await speakNow(TEACHER, teacherChoiceLineForStep(step));
      await speakNow(TEACHER, teacherLetMeKnowLineForStep(step));
      scheduleStepDoneReminder(10000);
      return;
    }

    if (social === 3) {
      await speakNow(TEACHER, teacherLeadLineForStep(step));
      if (explainAction) {
        await speakNow(TEACHER, instruction);
      } else {
        await speakNow(TEACHER, teacherShortRepeatLineForStep(step));
      }
      await speakNow(TEACHER, teacherLetMeKnowLineForStep(step));
      scheduleStepDoneReminder(12000);
      await sleep(180);
      await maybeAskStageThreePreference();
      return;
    }

    await speakNow(WORKER, teacherLeadLineForStep(step));
    await sleep(120);
    await speakNow(TEACHER, pickLine([
      "I will be right here if you want help.",
      "I am still right here with you.",
      "You can take your time. I am right here."
    ]));
    await speakNow(TEACHER, teacherLetMeKnowLineForStep(step));
    scheduleStepDoneReminder(12000);
  }


  async function saveProgress(extra = {}) {
    if (state.gameCompleted) return;
    try {
      await fetch("/api/restaurant-game/save-progress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activity_id: activityId,
          order_index: state.orderIndex,
          step_index: 0,
          orders_completed: state.ordersCompleted,
          steps_completed: state.stepsCompleted,
          spoken_responses: state.spokenResponses,
          silent_windows: state.silentWindows,
          worker_direct_responses: state.workerDirectResponses,
          teacher_redirects: state.teacherRedirects,
          total_choices: state.totalChoices,
          last_pizza_json: JSON.stringify(state.orderStates).slice(0, 15000),
          ...extra
        })
      });
    } catch (error) {
      console.warn("Could not save restaurant progress:", error);
    }
  }

  async function loadSavedProgress() {
    try {
      const response = await fetch(`/api/restaurant-game/state?activity_id=${activityId}`);
      if (!response.ok) return;
      const data = await response.json();
      if (!data.success || !data.state) return;
      const saved = data.state;
      const savedOrdersCompleted = clampInt(saved.orders_completed, 0, TARGET_ORDERS);
      const savedOrderIndex = clampInt(saved.order_index, 0, ORDERS.length - 1);

      // Round-level restore only: completed order 1 reopens at order 2,
      // and an unfinished order always restarts at that order's first step.
      state.ordersCompleted = savedOrdersCompleted;
      state.orderIndex = clampInt(Math.max(savedOrderIndex, savedOrdersCompleted), 0, ORDERS.length - 1);
      state.stepIndex = 0;
      state.stepsCompleted = clampInt(saved.steps_completed, 0, 200);
      state.spokenResponses = clampInt(saved.spoken_responses, 0, 99999);
      state.silentWindows = clampInt(saved.silent_windows, 0, 99999);
      state.workerDirectResponses = clampInt(saved.worker_direct_responses, 0, 99999);
      state.teacherRedirects = clampInt(saved.teacher_redirects, 0, 99999);
      state.totalChoices = clampInt(saved.total_choices, 0, 99999);

      // Resume is intentionally round-level, not step-level.
      // If the child leaves halfway through an order, we reopen the same order
      // from step 1 with a clean plate/bowl/tray instead of restoring partial food.
      const savedStepIndex = clampInt(saved.step_index, 0, 999);
      const savedStepsCompleted = clampInt(saved.steps_completed, 0, 99999);
      state.isReturningSession = Boolean(
        savedOrdersCompleted > 0 ||
        savedOrderIndex > 0 ||
        savedStepIndex > 0 ||
        savedStepsCompleted > 0
      );
      state.orderStates = {};
      state.currentProgress = 0;
    } catch (error) {
      console.warn("Could not load restaurant progress:", error);
    }
  }

  function clampInt(value, min, max) {
    const n = Number.parseInt(value, 10);
    if (!Number.isFinite(n)) return min;
    return Math.max(min, Math.min(max, n));
  }


  async function finishActivity() {
    state.gameCompleted = true;
    pausePassiveListening();

    await speakNow(TEACHER, pickLine([
      "You helped Leo with all the restaurant orders today. I liked seeing how each one came together.",
      "You helped make a whole set of restaurant orders today. I am glad I got to see them.",
      "You added so many careful parts today. The restaurant orders looked really nice."
    ]), { gameComplete: true });

    await speakNow(WORKER, pickLine([
      "Thank you for helping me today. You were a great restaurant helper.",
      "You finished all the orders with me. Nice work today.",
      "We can be done helping in the restaurant for today. I liked making these orders with you."
    ]), { gameComplete: true });

    const minutesPlayed = Math.max(0, (Date.now() - state.sessionStart) / 60000);

    try {
      const response = await fetch("/api/restaurant-game/complete", {
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
          worker_direct_responses: state.workerDirectResponses,
          teacher_redirects: state.teacherRedirects,
          total_choices: state.totalChoices,
          orders_completed: TARGET_ORDERS,
          steps_completed: state.stepsCompleted
        })
      });

      const data = await response.json();

      if (data.success && data.next_activity_id) {
        window.location.href = `/activity/${data.next_activity_id}`;
        return;
      }
    } catch (error) {
      console.warn("Could not complete restaurant activity:", error);
    }

    window.location.href = "/dashboard";
  }


  async function startGame() {
    if (startBtn) startBtn.disabled = true;
    if (invite) invite.classList.add("hide");
    if (stage) stage.classList.remove("is-hidden");
    await ensureMicPermission();
    await preloadWorkerFrames();
    await loadSavedProgress();
    enterPreCookingMode();
    setTimeout(() => { if (invite) invite.style.display = "none"; }, 430);
    await sleep(520);
    await introduceOrder();
    resumePassiveListeningSoon(700);
  }

  if (startBtn) startBtn.addEventListener("click", () => { void startGame(); });
  if (doneStepBtn) doneStepBtn.addEventListener("click", () => { void handleDoneStep("button"); });

  window.addEventListener("beforeunload", () => { void saveProgress(); });
});
