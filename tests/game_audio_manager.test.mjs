import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "..", "static", "js", "game-audio-manager.js"), "utf8");

class FakeAudio {
  static instances = [];

  constructor() {
    this.listeners = new Map();
    this.duration = 1;
    this.playbackRate = 1;
    this.paused = false;
    FakeAudio.instances.push(this);
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  removeEventListener(name, listener) {
    if (this.listeners.get(name) === listener) this.listeners.delete(name);
  }

  play() {
    return Promise.resolve();
  }

  pause() {
    this.paused = true;
  }

  emit(name) {
    const listener = this.listeners.get(name);
    if (listener) listener();
  }
}

function makeManager() {
  const win = {
    setTimeout,
    clearTimeout,
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {}
  };

  new Function("window", "Audio", source)(win, FakeAudio);
  return win.GameAudioManager.create({ defaultTimeoutMs: 5000 });
}

test("cancelActive resolves the pending playback instead of freezing its caller", async () => {
  FakeAudio.instances = [];
  const manager = makeManager();
  const playback = manager.playAndWait("/voice.mp3");

  manager.cancelActive("child_barged_in");

  const result = await Promise.race([
    playback,
    new Promise((_, reject) => setTimeout(() => reject(new Error("playback stayed pending")), 100))
  ]);

  assert.equal(result.status, "cancelled");
  assert.equal(result.reason, "child_barged_in");
  assert.equal(FakeAudio.instances[0].paused, true);
});

test("starting a new prompt resolves the superseded playback", async () => {
  FakeAudio.instances = [];
  const manager = makeManager();
  const first = manager.playAndWait("/first.mp3");
  const second = manager.playAndWait("/second.mp3");

  assert.equal((await first).status, "cancelled");

  FakeAudio.instances[1].emit("ended");
  assert.equal((await second).status, "ended");
});
