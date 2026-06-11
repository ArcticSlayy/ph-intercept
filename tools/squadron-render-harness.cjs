const fs = require('fs');
const vm = require('vm');

let now = 0;
const rafQueue = [];
const fillTextCalls = [];
const storage = new Map();
storage.set('ph_display', JSON.stringify({
  friendlies: true,
  domain: true,
  client: true,
  multiClientDefenders: true,
  maxClientDefenders: 4,
}));

function makeStorage() {
  return {
    getItem: key => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: key => storage.delete(key),
  };
}

function makeClassList() {
  const values = new Set();
  return {
    add: value => values.add(value),
    remove: value => values.delete(value),
    contains: value => values.has(value),
    toString: () => [...values].join(' '),
  };
}

const ctx = new Proxy({
  canvas: null,
  measureText: text => ({ width: String(text || '').length * 8 }),
  fillText: (text, x, y) => fillTextCalls.push({ text: String(text), x, y }),
  createLinearGradient: () => ({ addColorStop() {} }),
  createRadialGradient: () => ({ addColorStop() {} }),
}, {
  get(target, prop) {
    if (prop in target) return target[prop];
    return () => undefined;
  },
  set(target, prop, value) {
    target[prop] = value;
    return true;
  },
});

const canvas = {
  width: 0,
  height: 0,
  style: {},
  tabIndex: 0,
  getContext: () => ctx,
  focus() {},
  addEventListener() {},
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 1280, height: 720 }),
};
ctx.canvas = canvas;

const settingsBtn = {
  style: {},
  classList: makeClassList(),
  querySelectorAll: () => [{ style: {} }, { style: {} }, { style: {} }],
  addEventListener() {},
  getBoundingClientRect: () => ({}),
};

const phLink = {
  dataset: { href: 'http://127.0.0.1:5380' },
  addEventListener() {},
  style: {},
};

const document = {
  body: { classList: makeClassList(), appendChild() {}, removeChild() {}, className: '' },
  documentElement: {},
  fonts: { ready: Promise.resolve(), status: 'loaded' },
  getElementById(id) {
    if (id === 'pihole-canvas') return canvas;
    if (id === 'settings-btn') return settingsBtn;
    if (id === 'pihole-link') return phLink;
    return null;
  },
  addEventListener() {},
  removeEventListener() {},
  querySelectorAll: () => [],
  createElement: () => ({
    style: {},
    getContext: () => ctx,
    remove() {},
    addEventListener() {},
    width: 0,
    height: 0,
  }),
};

class FakeEventSource {
  constructor(url) {
    this.url = url;
    FakeEventSource.last = this;
  }
  close() {}
}
FakeEventSource.last = null;

const context = {
  console,
  window: null,
  PROVIDER: 'technitium',
  innerWidth: 1280,
  innerHeight: 720,
  document,
  localStorage: makeStorage(),
  sessionStorage: makeStorage(),
  performance: { now: () => now },
  Date,
  Math,
  JSON,
  Image: class {
    constructor() {
      this.complete = true;
      this.naturalWidth = 16;
      this.naturalHeight = 16;
    }
  },
  EventSource: FakeEventSource,
  AbortSignal: { timeout: () => ({}) },
  fetch: async () => ({
    json: async () => ({ blocking: true, blocked: 2, queries: 2, percent: 100, gravity: 2 }),
  }),
  requestAnimationFrame: callback => {
    rafQueue.push(callback);
    return rafQueue.length;
  },
  cancelAnimationFrame() {},
  addEventListener() {},
  removeEventListener() {},
  open() {},
  setInterval: () => 1,
  clearInterval() {},
  setTimeout: callback => {
    rafQueue.push(() => callback());
    return 1;
  },
  clearTimeout() {},
  getComputedStyle: () => ({
    getPropertyValue: () => '0',
    opacity: '1',
    display: 'block',
    transform: 'none',
  }),
};
context.window = context;

function runFrame(ms) {
  now = ms;
  const callback = rafQueue.shift();
  if (callback) callback(ms);
  if (context.window.__phLastRenderError) {
    throw new Error(`render failed: ${JSON.stringify(context.window.__phLastRenderError)}`);
  }
}

vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/game-bitmaps.js', 'utf8'), context, { filename: 'game-bitmaps.js' });
vm.runInContext(fs.readFileSync('static/js/game.js', 'utf8'), context, { filename: 'game.js' });

if (typeof context.window.enterPiholeMode !== 'function') {
  throw new Error('enterPiholeMode was not exported');
}

context.window.enterPiholeMode();
runFrame(0);

if (!FakeEventSource.last || typeof FakeEventSource.last.onmessage !== 'function') {
  throw new Error('EventSource did not connect');
}

const events = [
  { client: 'Workstation', status: 'blocked', source: 'blocked' },
  { client: 'Phone', status: 'allowed', source: 'upstream' },
  { client: 'Tablet', status: 'blocked', source: 'blocked' },
  { client: 'Console', status: 'allowed', source: 'cache' },
];
const expectedClients = events.map(event => event.client);

for (const event of events) {
  FakeEventSource.last.onmessage({
    data: JSON.stringify([{
      domain: event.status === 'blocked' ? 'DoubleClick: doubleclick.net' : 'Example CDN: cdn.example.net',
      status: event.status,
      source: event.source,
      client: event.client,
    }]),
  });
}

for (let t = 100; t <= 5400; t += 100) runFrame(t);

const lastLabelByClient = new Map();
for (const call of fillTextCalls) {
  if (expectedClients.includes(call.text)) lastLabelByClient.set(call.text, call);
}

for (const expected of expectedClients) {
  if (!lastLabelByClient.has(expected)) {
    const rendered = fillTextCalls.map(call => call.text).slice(-40).join(' | ');
    throw new Error(`missing squadron label: ${expected}; rendered tail: ${rendered}`);
  }
}

const labelPositions = [...lastLabelByClient.values()].map(call => ({
  text: call.text,
  x: Math.round(call.x),
  y: Math.round(call.y),
}));
const uniquePositions = new Set(labelPositions.map(pos => `${pos.x},${pos.y}`));
if (uniquePositions.size !== expectedClients.length) {
  throw new Error(`squadron labels collapsed onto shared positions: ${JSON.stringify(labelPositions)}`);
}

console.log('squadron render harness passed');
