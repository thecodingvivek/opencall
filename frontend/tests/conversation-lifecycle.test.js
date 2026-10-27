import { afterAll, beforeEach, expect, mock, test } from "bun:test";
import * as React from "react";
import * as livekit from "livekit-client";

// Exercise dashboard event ordering without a microphone or a browser.
let hooks, cursor, rooms, failJoin, failMicrophone;
const originalFetch = globalThis.fetch;
const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");

mock.module("react", () => ({
  ...React,
  useState(initial) {
    const index = cursor++;
    if (!(index in hooks)) hooks[index] = initial;
    return [hooks[index], value => { hooks[index] = value; }];
  },
  useRef(initial) {
    const index = cursor++;
    if (!(index in hooks)) hooks[index] = { current: initial };
    return hooks[index];
  },
  useEffect() {},
}));
mock.module("next/link", () => ({ default: "a" }));
mock.module("@livekit/components-react", () => ({
  RoomContext: { Provider: "room-provider" }, RoomAudioRenderer() {},
  useVoiceAssistant() {}, useTranscriptions() {}, useLocalParticipant() {},
  useRoomContext() {}, useConnectionState() {},
}));

class TestRoom {
  handlers = new Map();
  localParticipant = {
    setMicrophoneEnabled: async () => {
      if (failMicrophone) throw Object.assign(new Error("Denied"), { name: "NotAllowedError" });
    },
  };
  constructor() { rooms.push(this); }
  on(event, handler) { this.handlers.set(event, handler); return this; }
  emit(event, reason) { this.handlers.get(event)?.(reason); }
  async connect() {
    if (failJoin) {
      // This is the SDK ordering: Disconnected fires before connect rejects.
      this.emit(livekit.RoomEvent.Disconnected, livekit.DisconnectReason.JOIN_FAILURE);
      throw livekit.ConnectionError.serverUnreachable("Server unavailable");
    }
  }
  async disconnect() { this.emit(livekit.RoomEvent.Disconnected, livekit.DisconnectReason.CLIENT_INITIATED); }
  async startAudio() {}
}
mock.module("livekit-client", () => ({ ...livekit, Room: TestRoom }));
const { default: Dashboard } = await import("../src/app/dashboard/page");

function render() { cursor = 0; return Dashboard(); }
function find(node, predicate) {
  if (!node || typeof node !== "object") return undefined;
  if (predicate(node)) return node;
  const children = node.props?.children;
  for (const child of Array.isArray(children) ? children : [children]) {
    const found = find(child, predicate);
    if (found) return found;
  }
}
function alert() { return find(render(), node => node.props?.role === "alert")?.props.children; }
async function start() {
  await find(render(), node => node.type === "button" && node.props.children === "Start conversation").props.onClick();
}

beforeEach(() => {
  hooks = []; rooms = []; failJoin = false; failMicrophone = false;
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { mediaDevices: { getUserMedia() {} } } });
  globalThis.fetch = async () => Response.json({ server_url: "ws://localhost:7880", participant_token: "test" });
});
afterAll(() => {
  globalThis.fetch = originalFetch;
  if (originalNavigator) Object.defineProperty(globalThis, "navigator", originalNavigator);
  else delete globalThis.navigator;
  mock.restore();
});

test("failed room join reports the startup failure and allows retry", async () => {
  failJoin = true;
  await start();
  expect(alert()).toContain("Check that LiveKit is running");
  failJoin = false;
  await start();
  expect(alert()).toBeUndefined();
  expect(rooms).toHaveLength(2);
});

test("server shutdown after joining reports a restart and allows a new call", async () => {
  await start();
  rooms[0].emit(livekit.RoomEvent.Disconnected, livekit.DisconnectReason.SERVER_SHUTDOWN);
  expect(alert()).toContain("voice server restarted");
  await start();
  rooms[0].emit(livekit.RoomEvent.Disconnected, livekit.DisconnectReason.SERVER_SHUTDOWN);
  expect(alert()).toBeUndefined();
});

test("microphone failure keeps its permission error during cleanup", async () => {
  failMicrophone = true;
  await start();
  expect(alert()).toContain("Microphone access was denied");
});
