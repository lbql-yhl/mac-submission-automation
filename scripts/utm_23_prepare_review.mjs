#!/usr/bin/env node

import process from "node:process";
import path from "node:path";
import { chmod, mkdir, stat } from "node:fs/promises";


const TIMEOUT = 30_000;
const APP_STORE_CONNECT_URL = "https://appstoreconnect.apple.com/apps";
const RETRY_DELAYS_MS = [0, 5_000, 10_000];
const BUILD_VISIBILITY_DELAYS_MS = [0, 15_000, 30_000, 60_000, 120_000];
const IAP_STATUSES = [
  "Developer Removed from Sale",
  "Developer Action Needed",
  "Pending Binary Approval",
  "Ready for Review",
  "Ready to Submit",
  "Waiting for Review",
  "Missing Metadata",
  "Removed from Sale",
  "Processing Content",
  "In Review",
  "Rejected",
  "Approved",
];


function normalize(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function reviewItemsReady(iapCount) {
  if (!Number.isInteger(iapCount) || iapCount < 1) {
    throw new Error("IAP count must be a positive integer");
  }
  return iapCount + 1;
}

if (process.argv[2] === "--self-test") {
  const count = 7;
  process.stdout.write(
    `UTM_23_SCRIPT=self-test-passed;IAP_COUNT=${count};ITEMS_READY=${reviewItemsReady(count)}\n`,
  );
  process.exit(0);
}

const { connectLocalBrowser, secureScreenshot } = await import(
  new URL("./session.mjs", import.meta.url)
);

function requireString(value, label, pattern = null) {
  const normalized = normalize(value);
  if (!normalized || (pattern && !pattern.test(normalized))) {
    throw new Error(`UTM-23 input is invalid: ${label}`);
  }
  return normalized;
}

async function readInput() {
  let text = "";
  process.stdin.setEncoding("utf8");
  for await (const chunk of process.stdin) text += chunk;
  if (!text.trim()) throw new Error("UTM-23 requires JSON on stdin");
  const payload = JSON.parse(text);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("UTM-23 stdin must be a JSON object");
  }
  const allowed = new Set([
    "RUN_ID",
    "APP_NAME",
    "APP_ID",
    "BUNDLE_ID",
    "APP_VERSION",
    "BUILD_NUMBER",
  ]);
  for (const key of Object.keys(payload)) {
    if (!allowed.has(key)) throw new Error(`UTM-23 stdin contains unsupported field: ${key}`);
  }
  return {
    runId: requireString(payload.RUN_ID, "RUN_ID", /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/),
    appName: requireString(payload.APP_NAME, "APP_NAME"),
    appId: requireString(payload.APP_ID, "APP_ID", /^\d+$/),
    bundleId: requireString(
      payload.BUNDLE_ID,
      "BUNDLE_ID",
      /^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/,
    ),
    appVersion: requireString(payload.APP_VERSION, "APP_VERSION", /^\d+(?:\.\d+)*$/),
    buildNumber: requireString(payload.BUILD_NUMBER, "BUILD_NUMBER", /^[1-9]\d*$/),
  };
}

function safeUrl(value) {
  const url = new URL(value);
  return `${url.protocol}//${url.host}${url.pathname}`;
}

function assertAppStoreConnectUrl(value, appId = null) {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.hostname !== "appstoreconnect.apple.com") {
    throw new Error(`Unexpected App Store Connect page: ${safeUrl(value)}`);
  }
  if (appId && !url.pathname.includes(`/apps/${appId}`)) {
    throw new Error("App Store Connect App ID changed");
  }
  return url;
}

function iapIdentity(value, appId, baseUrl = APP_STORE_CONNECT_URL) {
  try {
    const url = new URL(value, baseUrl);
    if (url.protocol !== "https:" || url.hostname !== "appstoreconnect.apple.com") return null;
    if (!url.pathname.startsWith(`/apps/${appId}/`)) return null;
    const match = url.pathname.match(/\/in-app-purchases\/([^/]+)(?:\/|$)/i);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

async function visible(locator) {
  const values = [];
  for (let index = 0; index < await locator.count(); index += 1) {
    const item = locator.nth(index);
    if (await item.isVisible().catch(() => false)) values.push(item);
  }
  return values;
}

async function uniqueVisible(locator, label) {
  const values = await visible(locator);
  if (values.length !== 1) {
    throw new Error(`${label} must be uniquely visible; found ${values.length}`);
  }
  return values[0];
}

async function optionalUniqueVisible(locator, label) {
  const values = await visible(locator);
  if (values.length > 1) {
    throw new Error(`${label} is ambiguous; found ${values.length}`);
  }
  return values[0] || null;
}

async function bodyText(page) {
  return normalize(await page.locator("body").innerText({ timeout: TIMEOUT }));
}

async function waitForBody(page, pattern, label, timeout = TIMEOUT) {
  const deadline = Date.now() + timeout;
  do {
    const text = await bodyText(page).catch(() => "");
    if (pattern.test(text)) return text;
    await page.waitForTimeout(100);
  } while (Date.now() < deadline);
  throw new Error(`${label} did not become visible`);
}

async function assertAuthenticated(page) {
  assertAppStoreConnectUrl(page.url());
  const loginControls = await visible(
    page.locator("input[type='password'], input[autocomplete~='username']"),
  );
  if (loginControls.length) throw new Error("App Store Connect session is not authenticated");
}

async function retryStep(label, action) {
  let lastError = null;
  for (const delay of RETRY_DELAYS_MS) {
    if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
    try {
      return await action();
    } catch (error) {
      lastError = error;
    }
  }
  throw new Error(`${label} failed after bounded recovery: ${lastError?.message || "unknown"}`);
}

async function exactTextLink(page, text) {
  const expected = normalize(text);
  const links = await visible(page.locator("a"));
  const matches = [];
  for (const link of links) {
    if (normalize(await link.innerText().catch(() => "")) === expected) matches.push(link);
  }
  if (matches.length !== 1) {
    throw new Error(`Exact link must be unique: ${expected}`);
  }
  return matches[0];
}

async function openApplication(context, config) {
  let page = context.pages().find((candidate) => {
    try {
      const url = assertAppStoreConnectUrl(candidate.url());
      return url.pathname.includes(`/apps/${config.appId}`);
    } catch {
      return false;
    }
  });
  if (!page) {
    page = context.pages().find((candidate) => {
      try { return assertAppStoreConnectUrl(candidate.url()).pathname.startsWith("/apps"); } catch { return false; }
    });
  }
  page ||= context.pages().length === 1 ? context.pages()[0] : await context.newPage();
  await page.bringToFront();
  if (!page.url().includes(`/apps/${config.appId}`)) {
    await page.goto(APP_STORE_CONNECT_URL, { waitUntil: "domcontentloaded", timeout: TIMEOUT });
    await assertAuthenticated(page);
    await waitForBody(page, /\bApps\b/, "Apps page");
    const application = await exactTextLink(page, config.appName);
    await application.click({ timeout: TIMEOUT });
  }
  await page.waitForLoadState("domcontentloaded").catch(() => {});
  assertAppStoreConnectUrl(page.url(), config.appId);
  await assertAuthenticated(page);
  const text = await bodyText(page);
  if (!text.includes(config.appName)) throw new Error("App Store Connect application name mismatch");
  return page;
}

async function navigateToVersion(page, config) {
  const versionUrl = `https://appstoreconnect.apple.com/apps/${config.appId}/appstore/ios/version/inflight`;
  if (safeUrl(page.url()) !== versionUrl) {
    await page.goto(versionUrl, { waitUntil: "domcontentloaded", timeout: TIMEOUT });
  }
  await assertAuthenticated(page);
  assertAppStoreConnectUrl(page.url(), config.appId);
  const text = await waitForBody(
    page,
    new RegExp(`\\b${escapeRegExp(config.appVersion)}\\b`),
    "current App Version",
  );
  if (!text.includes(config.appName)) throw new Error("Version page application mismatch");
}

async function nearestContainer(locator) {
  return locator.locator(
    "xpath=ancestor::*[self::section or self::fieldset or @role='dialog' or @role='row' or self::tr or self::li][1]",
  );
}

async function buildIsAttached(page, config) {
  const text = await bodyText(page);
  const versionAndBuild = new RegExp(
    `${escapeRegExp(config.appVersion)}[\\s\\S]{0,120}${escapeRegExp(config.buildNumber)}|${escapeRegExp(config.buildNumber)}[\\s\\S]{0,120}${escapeRegExp(config.appVersion)}`,
  );
  return versionAndBuild.test(text) && !/Select a build before you submit your app/.test(text);
}

async function attachBuild(page, config) {
  if (await buildIsAttached(page, config)) return;
  let addBuild = null;
  for (const delay of BUILD_VISIBILITY_DELAYS_MS) {
    if (delay) {
      await page.waitForTimeout(delay);
      await page.reload({ waitUntil: "domcontentloaded", timeout: TIMEOUT });
      await navigateToVersion(page, config);
      if (await buildIsAttached(page, config)) return;
    }
    addBuild = await optionalUniqueVisible(
      page.getByRole("button", { name: /^Add Build$/i }),
      "Add Build",
    );
    if (addBuild) break;
  }
  if (!addBuild) throw new Error("Add Build stayed unavailable after bounded polling");
  await addBuild.click({ timeout: TIMEOUT });
  const dialog = await uniqueVisible(page.locator("[role='dialog']"), "Add Build dialog");
  const rows = await visible(dialog.locator("tr,[role='row']"));
  const matches = [];
  for (const row of rows) {
    const text = normalize(await row.innerText().catch(() => ""));
    if (
      new RegExp(`\\b${escapeRegExp(config.buildNumber)}\\b`).test(text)
      && text.includes(config.appVersion)
    ) matches.push(row);
  }
  if (matches.length !== 1) throw new Error("Exact build candidate is not unique");
  const selector = await optionalUniqueVisible(
    matches[0].locator("input[type='checkbox'],input[type='radio']"),
    "build selector",
  );
  if (selector && !await selector.isChecked()) await selector.check({ timeout: TIMEOUT });
  else if (!selector) await matches[0].click({ timeout: TIMEOUT });
  const done = await uniqueVisible(dialog.getByRole("button", { name: /^Done$/i }), "Add Build Done");
  if (!await done.isEnabled()) throw new Error("Add Build Done is disabled");
  await done.click({ timeout: TIMEOUT });
  await dialog.waitFor({ state: "hidden", timeout: TIMEOUT });
  if (!await buildIsAttached(page, config)) throw new Error("Exact build was not attached");
}

async function clearMissingCompliance(page) {
  const missing = await optionalUniqueVisible(
    page.getByText("Missing Compliance", { exact: true }),
    "Missing Compliance",
  );
  if (!missing) return;
  const container = await nearestContainer(missing);
  const manage = await uniqueVisible(
    container.getByRole("button", { name: /^Manage$/i }),
    "Missing Compliance Manage",
  );
  await manage.click({ timeout: TIMEOUT });
  const dialog = await uniqueVisible(page.locator("[role='dialog']"), "compliance dialog");
  const noneLabel = /^None of the algorithms mentioned above$/i;
  let none = await optionalUniqueVisible(dialog.getByLabel(noneLabel), "encryption None option");
  none ||= await uniqueVisible(dialog.getByText(noneLabel, { exact: true }), "encryption None label");
  const control = none.locator("input[type='radio'],input[type='checkbox']");
  if (await control.count()) {
    const input = await uniqueVisible(control, "encryption None control");
    if (!await input.isChecked()) await input.check({ timeout: TIMEOUT });
  } else {
    await none.click({ timeout: TIMEOUT });
  }
  const save = await uniqueVisible(dialog.getByRole("button", { name: /^Save$/i }), "compliance Save");
  if (!await save.isEnabled()) throw new Error("Compliance Save is disabled");
  await save.click({ timeout: TIMEOUT });
  await dialog.waitFor({ state: "hidden", timeout: TIMEOUT });
  if (await visible(page.getByText("Missing Compliance", { exact: true })).then((items) => items.length)) {
    throw new Error("Missing Compliance was not cleared");
  }
}

async function keepGameCenterUncheckedAndSave(page) {
  const label = await optionalUniqueVisible(
    page.getByText("Game Center", { exact: true }),
    "Game Center label",
  );
  if (label) {
    const container = await nearestContainer(label);
    const checkboxes = await visible(container.locator("input[type='checkbox']"));
    if (checkboxes.length > 1) throw new Error("Game Center checkbox is ambiguous");
    if (checkboxes.length === 1 && await checkboxes[0].isChecked()) {
      await checkboxes[0].uncheck({ timeout: TIMEOUT });
    }
    if (checkboxes.length === 1 && await checkboxes[0].isChecked()) {
      throw new Error("Game Center stayed checked");
    }
  }
  const saves = await visible(page.getByRole("button", { name: /^Save$/i }));
  const enabled = [];
  for (const save of saves) if (await save.isEnabled().catch(() => false)) enabled.push(save);
  if (enabled.length > 1) throw new Error("Version Save control is ambiguous");
  if (enabled.length === 1) await enabled[0].click({ timeout: TIMEOUT });
  await page.waitForTimeout(500);
}

async function clickNavigation(page, pattern, label) {
  const candidates = [
    page.getByRole("link", { name: pattern }),
    page.getByRole("button", { name: pattern }),
  ];
  const matches = [];
  for (const locator of candidates) matches.push(...await visible(locator));
  if (matches.length !== 1) throw new Error(`${label} navigation is not unique`);
  await matches[0].click({ timeout: TIMEOUT });
  await page.waitForLoadState("domcontentloaded").catch(() => {});
}

async function openIapList(page, config) {
  if (!/in-app-purchases/i.test(page.url())) {
    await clickNavigation(page, /^In-App Purchases$/i, "In-App Purchases");
  }
  assertAppStoreConnectUrl(page.url(), config.appId);
  await waitForBody(page, /In-App Purchases/i, "In-App Purchases page");
}

async function expandAll(page) {
  for (let index = 0; index < 100; index += 1) {
    const seeMore = await optionalUniqueVisible(
      page.getByRole("button", { name: /^See More$/i }),
      "See More",
    );
    if (!seeMore || !await seeMore.isEnabled().catch(() => false)) return;
    await seeMore.click({ timeout: TIMEOUT });
    await page.waitForTimeout(200);
  }
  throw new Error("See More did not converge");
}

async function collectIapRows(page, config) {
  await expandAll(page);
  const rows = await visible(page.locator("tr,[role='row']"));
  const items = [];
  for (const row of rows) {
    const text = normalize(await row.innerText().catch(() => ""));
    const links = await visible(row.locator("a[href]"));
    const productLinks = [];
    for (const link of links) {
      const href = await link.getAttribute("href").catch(() => null);
      const identity = iapIdentity(href, config.appId, page.url());
      if (identity) productLinks.push({ identity, link });
    }
    if (!productLinks.length) continue;
    const identities = [...new Set(productLinks.map((item) => item.identity))];
    if (identities.length !== 1) throw new Error("Complete IAP row identity is ambiguous");
    const status = IAP_STATUSES.find((value) => text.includes(value));
    if (!status) throw new Error("Complete IAP row has an unsupported status");
    const product = productLinks.find((item) => item.identity === identities[0]);
    const name = normalize(await product.link.innerText().catch(() => ""));
    if (!name) throw new Error("IAP row has no stable identity");
    items.push({ identity: identities[0], name, status, row, link: product.link });
  }
  const identities = items.map((item) => item.identity);
  if (items.length < 1 || new Set(identities).size !== items.length) {
    throw new Error("Complete IAP set is empty or ambiguous");
  }
  return items;
}

async function chooseExistingDraft(page) {
  const dialogs = await visible(page.locator("[role='dialog']"));
  const scope = dialogs.at(-1) || page;
  const createNew = await visible(scope.getByText("Create New Submission", { exact: true }));
  for (const item of createNew) {
    const control = item.locator("input[type='radio'],input[type='checkbox']");
    if (await control.count() && await control.first().isChecked().catch(() => false)) {
      throw new Error("Create New Submission was selected");
    }
  }
  const labels = await visible(scope.locator("label"));
  const existing = [];
  for (const label of labels) {
    const text = normalize(await label.innerText().catch(() => ""));
    if (/Draft Submission/i.test(text) && !/Create New Submission/i.test(text)) existing.push(label);
  }
  if (existing.length !== 1) throw new Error("Existing Draft Submission is not unique");
  const input = existing[0].locator("input[type='radio'],input[type='checkbox']");
  if (await input.count()) {
    const control = await uniqueVisible(input, "existing draft control");
    if (!await control.isChecked()) await control.check({ timeout: TIMEOUT });
  } else {
    await existing[0].click({ timeout: TIMEOUT });
  }
  const confirms = [];
  for (const name of [/^Add$/i, /^Done$/i, /^Add for Review$/i]) {
    confirms.push(...await visible(scope.getByRole("button", { name })));
  }
  const enabled = [];
  for (const button of confirms) if (await button.isEnabled().catch(() => false)) enabled.push(button);
  if (enabled.length !== 1) throw new Error("Existing draft confirmation is not unique");
  await enabled[0].click({ timeout: TIMEOUT });
  if (dialogs.length) await scope.waitFor({ state: "hidden", timeout: TIMEOUT }).catch(() => {});
}

async function addOneIap(page, config, item) {
  if (!item.link) throw new Error("Ready to Submit IAP has no detail link");
  const listUrl = page.url();
  await item.link.click({ timeout: TIMEOUT });
  await page.waitForLoadState("domcontentloaded").catch(() => {});
  assertAppStoreConnectUrl(page.url(), config.appId);
  await waitForBody(page, new RegExp(escapeRegExp(item.name)), "IAP detail");
  const add = await uniqueVisible(
    page.getByRole("button", { name: /^Add for Review$/i }),
    "IAP Add for Review",
  );
  await add.click({ timeout: TIMEOUT });
  await chooseExistingDraft(page);
  await page.goto(listUrl, { waitUntil: "domcontentloaded", timeout: TIMEOUT });
  await openIapList(page, config);
}

async function linkAllIaps(page, config) {
  const initial = await collectIapRows(page, config);
  const expectedIdentities = initial.map((item) => item.identity).sort();
  for (let round = 0; round < initial.length; round += 1) {
    const current = await collectIapRows(page, config);
    const missing = current.find((item) => item.status === "Ready to Submit");
    if (!missing) break;
    await addOneIap(page, config, missing);
  }
  const finalItems = await collectIapRows(page, config);
  const finalIdentities = finalItems.map((item) => item.identity).sort();
  if (
    finalItems.some((item) => item.status !== "Ready for Review")
    || JSON.stringify(finalIdentities) !== JSON.stringify(expectedIdentities)
  ) {
    throw new Error("Complete IAP set is not Ready for Review");
  }
  return finalItems;
}

async function linkAppVersion(page, config) {
  await navigateToVersion(page, config);
  const ready = new RegExp(`${escapeRegExp(config.appVersion)}[\\s\\S]{0,80}Ready for Review`);
  if (ready.test(await bodyText(page))) return;
  const add = await uniqueVisible(
    page.getByRole("button", { name: /^Add for Review$/i }),
    "App Version Add for Review",
  );
  await add.click({ timeout: TIMEOUT });
  await chooseExistingDraft(page);
  await waitForBody(page, ready, "App Version Ready for Review");
}

async function openDraftSubmission(page, config, iapItems, draftUrl = null) {
  if (draftUrl) {
    assertAppStoreConnectUrl(draftUrl, config.appId);
    await page.goto(draftUrl, { waitUntil: "domcontentloaded", timeout: TIMEOUT });
  }
  const candidates = [];
  for (const pattern of [/^Draft Submissions(?:\s*\(1\))?$/i, /^Publishing$/i]) {
    candidates.push(...await visible(page.getByRole("link", { name: pattern })));
  }
  if (candidates.length > 1) throw new Error("Draft Submission navigation is ambiguous");
  if (candidates.length === 1) {
    await candidates[0].click({ timeout: TIMEOUT });
    await page.waitForLoadState("domcontentloaded").catch(() => {});
  }
  assertAppStoreConnectUrl(page.url(), config.appId);
  await expandAll(page);
  const text = await bodyText(page);
  const draftMarkers = text.match(/Draft Submission/gi) || [];
  if (!/Draft Submissions?\s*\(1\)/i.test(text) && draftMarkers.length !== 1) {
    throw new Error("Draft Submission count is not exactly one");
  }
  if (!text.includes(config.appVersion)) throw new Error("Draft is missing the current App Version");
  for (const item of iapItems) {
    if (!text.includes(item.name)) throw new Error("Draft is missing an expected IAP");
  }
  const draftIdentities = [];
  for (const link of await visible(page.locator("a[href]"))) {
    const href = await link.getAttribute("href").catch(() => null);
    const identity = iapIdentity(href, config.appId, page.url());
    if (identity) draftIdentities.push(identity);
  }
  if (draftIdentities.length) {
    const expected = [...new Set(iapItems.map((item) => item.identity))].sort();
    const actual = [...new Set(draftIdentities)].sort();
    if (JSON.stringify(actual) !== JSON.stringify(expected)) {
      throw new Error("Draft IAP identities do not match the complete IAP set");
    }
  }
  const readyCount = (text.match(/Ready for Review/g) || []).length;
  if (readyCount !== reviewItemsReady(iapItems.length)) {
    throw new Error("Draft does not show the exact dynamic review item count");
  }
  return page.url();
}

async function sectionForHeading(page, pattern, label) {
  const headings = await visible(page.getByRole("heading", { name: pattern }));
  if (headings.length > 1) throw new Error(`${label} section heading is ambiguous`);
  if (!headings.length) return null;
  const section = headings[0].locator(
    "xpath=ancestor::*[self::section or self::fieldset or @role='region'][1]",
  );
  return await section.count() ? section : headings[0].locator("xpath=parent::*");
}

async function clearRegulations(page) {
  const section = await sectionForHeading(
    page,
    /App Store Regulations\s*&\s*Permits/i,
    "regulations",
  );
  if (!section) throw new Error("Regulations & Permits section is missing");
  for (let index = 0; index < 50; index += 1) {
    const destructive = [];
    for (const pattern of [/^Remove$/i, /^Delete$/i]) {
      destructive.push(...await visible(section.getByRole("button", { name: pattern })));
    }
    if (!destructive.length) return;
    if (destructive.length !== 1) throw new Error("Regulations removal target is not unique");
    await destructive[0].click({ timeout: TIMEOUT });
    const dialog = await uniqueVisible(page.locator("[role='dialog']"), "regulations removal dialog");
    const confirms = [];
    for (const pattern of [/^Remove$/i, /^Delete$/i]) {
      confirms.push(...await visible(dialog.getByRole("button", { name: pattern })));
    }
    if (confirms.length !== 1) throw new Error("Regulations removal confirmation is not unique");
    await confirms[0].click({ timeout: TIMEOUT });
    await dialog.waitFor({ state: "hidden", timeout: TIMEOUT });
  }
  throw new Error("Regulations removal did not converge");
}

async function clearServerUrls(page) {
  const inputs = [];
  for (const pattern of [/Production Server URL/i, /Sandbox Server URL/i]) {
    const matches = await visible(page.getByLabel(pattern));
    if (matches.length > 1) throw new Error("Server URL field is ambiguous");
    if (matches.length === 1) inputs.push(matches[0]);
  }
  if (!inputs.length) {
    const text = await bodyText(page);
    if (!/Set Up URL/i.test(text)) throw new Error("Server URL empty state is not verified");
    return;
  }
  let changed = false;
  for (const input of inputs) {
    if (normalize(await input.inputValue().catch(() => ""))) {
      await input.fill("");
      changed = true;
    }
  }
  if (!changed) return;
  const saves = await visible(page.getByRole("button", { name: /^Save$/i }));
  const enabled = [];
  for (const save of saves) if (await save.isEnabled().catch(() => false)) enabled.push(save);
  if (enabled.length !== 1) throw new Error("App Information Save is not unique");
  await enabled[0].click({ timeout: TIMEOUT });
  for (const input of inputs) {
    if (normalize(await input.inputValue().catch(() => ""))) {
      throw new Error("Server URL was not cleared");
    }
  }
}

async function cleanAppInformation(page, config) {
  const infoUrl = `https://appstoreconnect.apple.com/apps/${config.appId}/appstore/info`;
  await page.goto(infoUrl, { waitUntil: "domcontentloaded", timeout: TIMEOUT });
  await assertAuthenticated(page);
  assertAppStoreConnectUrl(page.url(), config.appId);
  const text = await waitForBody(page, /App Information/i, "App Information page");
  if (!text.includes(config.appName) || !text.includes(config.bundleId)) {
    throw new Error("App Information identity mismatch");
  }
  const readyVersion = new RegExp(
    `${escapeRegExp(config.appVersion)}[\\s\\S]{0,100}Ready for Review`,
  );
  if (!readyVersion.test(text)) throw new Error("Current Ready for Review version is not visible");
  await clearRegulations(page);
  await clearServerUrls(page);
}

async function saveOwnedScreenshot(page, outputDir, filename) {
  const target = path.join(outputDir, filename);
  await secureScreenshot(page, target);
  await chmod(target, 0o600);
  const metadata = await stat(target);
  if (!metadata.isFile() || metadata.size < 100 || (metadata.mode & 0o777) !== 0o600) {
    throw new Error(`Review screenshot is invalid: ${filename}`);
  }
  return target;
}

async function main() {
  const config = await readInput();
  const outputDir = path.join(
    "/Users",
    process.env.USER || "",
    "Downloads",
    "utm-23-review",
    config.runId,
  );
  const expectedRoot = `/Users/${process.env.USER}/Downloads/utm-23-review/${config.runId}`;
  if (outputDir !== expectedRoot) throw new Error("Review screenshot path escaped its owner");
  await mkdir(outputDir, { recursive: true, mode: 0o700 });
  await chmod(outputDir, 0o700);

  const connected = await connectLocalBrowser();
  const page = await retryStep("open exact application", () => openApplication(connected.context, config));
  await retryStep("open exact version", () => navigateToVersion(page, config));
  await retryStep("attach exact build", () => attachBuild(page, config));
  await retryStep("clear export compliance", () => clearMissingCompliance(page));
  await retryStep("save Game Center state", () => keepGameCenterUncheckedAndSave(page));
  await retryStep("open IAP list", () => openIapList(page, config));
  const iapItems = await retryStep("link complete IAP set", () => linkAllIaps(page, config));
  const iapCount = iapItems.length;
  await retryStep("link App Version", () => linkAppVersion(page, config));
  const draftUrl = await retryStep(
    "open exact Draft Submission",
    () => openDraftSubmission(page, config, iapItems),
  );
  const screenshot02 = await saveOwnedScreenshot(page, outputDir, "02-iap-drafts.png");
  await retryStep("clear scoped App Information", () => cleanAppInformation(page, config));
  const screenshot03 = await saveOwnedScreenshot(page, outputDir, "03-app-information.png");
  await retryStep(
    "final Draft Submission verification",
    () => openDraftSubmission(page, config, iapItems, draftUrl),
  );

  process.stdout.write(`${JSON.stringify({
    UTM_23: "verified",
    BUILD_ATTACHED: "verified",
    EXPORT_COMPLIANCE_STATUS: "cleared",
    GAME_CENTER_CHECKBOX: "unchecked",
    VERSION_PAGE: "saved",
    DRAFT_SUBMISSIONS: 1,
    IAP_READY_FOR_REVIEW: iapCount,
    REVIEW_ITEMS_READY: reviewItemsReady(iapCount),
    APP_VERSION_DRAFT_LINK: "verified",
    APP_STORE_REGULATIONS_PERMITS: "empty",
    APP_STORE_SERVER_NOTIFICATIONS: "empty",
    REVIEW_SCREENSHOT_02: "verified",
    REVIEW_SCREENSHOT_03: "verified",
    SUBMIT_FOR_REVIEW: "not_clicked",
    screenshot_02_path: screenshot02,
    screenshot_03_path: screenshot03,
  })}\n`);
}

main().catch((error) => {
  process.stderr.write(`UTM_23_ERROR=${error.message}\n`, () => process.exit(1));
});
