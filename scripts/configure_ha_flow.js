#!/usr/bin/env node
"use strict";

const haUrl = process.env.HA_WS_URL || "ws://homeassistant.local:8123/api/websocket";
const haToken = process.env.HA_TOKEN;
const freeboxAppToken = process.env.FREEBOX_APP_TOKEN;
const freeboxAppId = process.env.FREEBOX_APP_ID || "fr.rkn21.freebox_simple_metrics";
const freeboxHost = process.env.FREEBOX_HOST || "192.168.1.254";
const entryName = process.env.FREEBOX_ENTRY_NAME || "Freebox Simple Metrics";

if (!haToken) {
  throw new Error("HA_TOKEN is required");
}
if (!freeboxAppToken) {
  throw new Error("FREEBOX_APP_TOKEN is required");
}

let nextId = 1;
let finished = false;

const ws = new WebSocket(haUrl);

function send(message) {
  ws.send(JSON.stringify(message));
}

function finish(code = 0) {
  finished = true;
  ws.close();
  process.exitCode = code;
}

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === "auth_required") {
    send({ type: "auth", access_token: haToken });
    return;
  }

  if (message.type === "auth_ok") {
    console.log("auth_ok");
    send({
      id: nextId++,
      type: "config_entries/flow/init",
      handler: "freebox_simple_metrics",
      context: { source: "user" },
    });
    return;
  }

  if (message.type !== "result") {
    return;
  }

  if (!message.success) {
    console.error("result_error", JSON.stringify(message.error));
    finish(1);
    return;
  }

  const result = message.result || {};
  console.log("flow_result", result.type, result.step_id || "", result.reason || "");

  if (result.type === "form" && result.step_id === "user") {
    send({
      id: nextId++,
      type: "config_entries/flow/configure",
      flow_id: result.flow_id,
      user_input: {
        host: freeboxHost,
        name: entryName,
        scan_interval: 30,
        timeout: 10,
        app_id: freeboxAppId,
        app_token: freeboxAppToken,
      },
    });
    return;
  }

  if (result.type === "create_entry") {
    console.log("created_entry", result.title || entryName);
    finish(0);
    return;
  }

  if (result.type === "abort") {
    console.log("aborted", result.reason);
    finish(result.reason === "already_configured" ? 0 : 1);
  }
};

ws.onerror = (error) => {
  console.error("websocket_error", error.message || error.type || "unknown");
  finish(1);
};

setTimeout(() => {
  if (!finished) {
    console.error("timeout");
    finish(1);
  }
}, 30000);
