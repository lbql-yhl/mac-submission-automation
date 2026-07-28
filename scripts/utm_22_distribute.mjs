#!/usr/bin/env node

import { execFileSync, spawnSync } from 'node:child_process';
import { createHash, createPrivateKey, randomUUID, sign } from 'node:crypto';
import {
  chmodSync,
  closeSync,
  existsSync,
  fsyncSync,
  lstatSync,
  mkdtempSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const API = 'https://api.appstoreconnect.apple.com/v1';

function b64url(value) {
  return Buffer.from(value).toString('base64url');
}

export function makeToken({ issuerId, keyId, privateKey, now = Math.floor(Date.now() / 1000) }) {
  const header = b64url(JSON.stringify({ alg: 'ES256', kid: keyId, typ: 'JWT' }));
  const payload = b64url(JSON.stringify({
    iss: issuerId,
    iat: now,
    exp: now + 1200,
    aud: 'appstoreconnect-v1',
  }));
  const message = `${header}.${payload}`;
  const signature = sign('sha256', Buffer.from(message), {
    key: privateKey,
    dsaEncoding: 'ieee-p1363',
  });
  return `${message}.${signature.toString('base64url')}`;
}

export function createBuildUploadBody(appId, version, build) {
  return {
    data: {
      type: 'buildUploads',
      attributes: {
        cfBundleShortVersionString: version,
        cfBundleVersion: build,
        platform: 'IOS',
      },
      relationships: { app: { data: { type: 'apps', id: appId } } },
    },
  };
}

export function createBuildUploadFileBody(uploadId, fileName, fileSize) {
  return {
    data: {
      type: 'buildUploadFiles',
      attributes: {
        assetType: 'ASSET',
        fileName,
        fileSize,
        uti: 'com.apple.ipa',
      },
      relationships: {
        buildUpload: { data: { type: 'buildUploads', id: uploadId } },
      },
    },
  };
}

export function commitBuildUploadFileBody(fileId) {
  return {
    data: {
      type: 'buildUploadFiles',
      id: fileId,
      attributes: {
        uploaded: true,
      },
    },
  };
}

export function operationChunk(buffer, operation) {
  const offset = Number(operation.offset);
  const length = Number(operation.length);
  if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(length) || offset < 0 || length < 1 || offset + length > buffer.length) {
    throw new Error('upload operation is outside file');
  }
  return buffer.subarray(offset, offset + length);
}

function run(command, args, options = {}) {
  try {
    return execFileSync(command, args, { encoding: 'utf8', ...options }).trim();
  } catch (error) {
    const detail = String(error.stderr || error.stdout || error.message).trim().split('\n').slice(-8).join('\n');
    throw new Error(`${basename(command)} failed: ${detail}`);
  }
}

function plist(path) {
  return JSON.parse(run('/usr/bin/plutil', ['-convert', 'json', '-o', '-', path]));
}

function xmlPlist(xml) {
  return JSON.parse(run('/usr/bin/plutil', ['-convert', 'json', '-o', '-', '-'], { input: xml }));
}

function profileValue(path, key, optional = false) {
  const result = spawnSync('/usr/libexec/PlistBuddy', ['-c', `Print :${key}`, path], { encoding: 'utf8' });
  if (result.status === 0) return result.stdout.trim();
  if (optional) return undefined;
  throw new Error(`provisioning profile is missing ${key}`);
}

export function readDecodedProfile(path) {
  const bool = (key, optional = false) => {
    const value = profileValue(path, key, optional);
    if (value === undefined) return false;
    if (value === 'true') return true;
    if (value === 'false') return false;
    throw new Error(`provisioning profile ${key} is not boolean`);
  };
  return {
    name: profileValue(path, 'Name'),
    expirationDate: run('/usr/bin/plutil', ['-extract', 'ExpirationDate', 'raw', '-o', '-', path]),
    applicationIdentifier: profileValue(path, 'Entitlements:application-identifier'),
    teamIdentifier: profileValue(path, 'Entitlements:com.apple.developer.team-identifier', true)
      || profileValue(path, 'TeamIdentifier:0'),
    getTaskAllow: bool('Entitlements:get-task-allow'),
    betaReportsActive: bool('Entitlements:beta-reports-active'),
    hasProvisionedDevices: profileValue(path, 'ProvisionedDevices', true) !== undefined,
    provisionsAllDevices: bool('ProvisionsAllDevices', true),
  };
}

function codesignDetails(appPath) {
  const result = spawnSync('/usr/bin/codesign', ['-d', '--verbose=4', '--entitlements', ':-', appPath], { encoding: 'utf8' });
  if (result.status !== 0) throw new Error(`codesign details failed: ${(result.stderr || result.stdout).trim()}`);
  const output = `${result.stdout}\n${result.stderr}`;
  const plistStart = output.indexOf('<?xml');
  const plistEnd = output.indexOf('</plist>', plistStart);
  if (plistStart < 0 || plistEnd < 0) throw new Error('signed entitlements are missing');
  const authorities = [...output.matchAll(/^Authority=(.+)$/gm)].map((match) => match[1]);
  return {
    authorities,
    teamIdentifier: output.match(/^TeamIdentifier=(.+)$/m)?.[1],
    entitlements: xmlPlist(output.slice(plistStart, plistEnd + 8)),
  };
}

function oneApplication(archivePath) {
  const products = join(archivePath, 'Products', 'Applications');
  const names = run('/usr/bin/find', [products, '-maxdepth', '1', '-type', 'd', '-name', '*.app']).split('\n').filter(Boolean);
  if (names.length !== 1) throw new Error(`archive must contain exactly one top-level app; found ${names.length}`);
  return names[0];
}

export function inspectArchive(archive) {
  const archivePath = resolve(archive);
  if (!archivePath.endsWith('.xcarchive') || !existsSync(join(archivePath, 'Info.plist'))) {
    throw new Error('an existing .xcarchive with Info.plist is required');
  }

  const appPath = oneApplication(archivePath);
  const info = plist(join(appPath, 'Info.plist'));
  for (const key of ['CFBundleIdentifier', 'CFBundleShortVersionString', 'CFBundleVersion']) {
    if (!info[key]) throw new Error(`app Info.plist is missing ${key}`);
  }

  run('/usr/bin/codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath]);
  const signing = codesignDetails(appPath);
  if (!signing.authorities.some((value) => value.startsWith('Apple Distribution:'))) {
    throw new Error('app is not signed with an Apple Distribution certificate');
  }

  const profilePath = join(appPath, 'embedded.mobileprovision');
  if (!existsSync(profilePath)) throw new Error('embedded.mobileprovision is missing');
  const profileDirectory = mkdtempSync(join(tmpdir(), 'utm-22-profile-'));
  const decodedProfile = join(profileDirectory, 'profile.plist');
  let profile;
  try {
    writeFileSync(decodedProfile, run('/usr/bin/security', ['cms', '-D', '-i', profilePath]));
    profile = readDecodedProfile(decodedProfile);
  } finally {
    rmSync(profileDirectory, { recursive: true, force: true });
  }
  const appIdentifier = profile.applicationIdentifier;
  const teamId = profile.teamIdentifier;

  if (new Date(profile.expirationDate).getTime() <= Date.now()) throw new Error('provisioning profile is expired');
  if (profile.hasProvisionedDevices || profile.provisionsAllDevices) throw new Error('profile is not an App Store distribution profile');
  if (profile.getTaskAllow !== false) throw new Error('get-task-allow must be false');
  if (profile.betaReportsActive !== true) throw new Error('beta-reports-active must be true');
  if (!appIdentifier.endsWith(`.${info.CFBundleIdentifier}`)) throw new Error('profile bundle identifier does not match app');
  if (!teamId || signing.teamIdentifier !== teamId) throw new Error('certificate team does not match profile team');
  if (signing.entitlements['application-identifier'] !== appIdentifier) throw new Error('signed application-identifier does not match profile');

  return {
    archivePath,
    appPath,
    appName: basename(appPath),
    bundleId: info.CFBundleIdentifier,
    version: `${info.CFBundleShortVersionString}`,
    build: `${info.CFBundleVersion}`,
    profileName: profile.name,
  };
}

export function swiftLibraries(appPath) {
  const frameworks = join(appPath, 'Frameworks');
  if (!existsSync(frameworks)) return [];
  return readdirSync(frameworks, { withFileTypes: true })
    .filter((entry) => entry.isFile() && /^libswift.*\.dylib$/.test(entry.name))
    .map((entry) => join(frameworks, entry.name))
    .sort();
}

export function selectSwiftSupportLibrary(name, embeddedUuid, candidates) {
  const matches = candidates.filter((candidate) => candidate.name === name
    && candidate.uuid === embeddedUuid
    && candidate.authority === 'Software Signing');
  if (matches.length !== 1) throw new Error(`${name} requires exactly one UUID-matching Apple-signed Command Line Tools runtime`);
  return matches[0].path;
}

function swiftUuid(path) {
  const matches = [...run('/usr/bin/dwarfdump', ['--uuid', path]).matchAll(/UUID: ([A-F0-9-]+) \(arm64\)/g)];
  if (matches.length !== 1) throw new Error(`${basename(path)} must contain exactly one arm64 UUID`);
  return matches[0][1];
}

function signingAuthority(path) {
  const result = spawnSync('/usr/bin/codesign', ['-dv', '--verbose=4', path], { encoding: 'utf8' });
  if (result.status !== 0) throw new Error(`codesign details failed for ${basename(path)}`);
  return `${result.stdout}\n${result.stderr}`.match(/^Authority=(.+)$/m)?.[1] || '';
}

function swiftSupportLibraries(appPath) {
  const root = '/Library/Developer/CommandLineTools/usr/lib';
  if (!existsSync(root)) throw new Error('Apple Command Line Tools Swift runtime is missing');
  return swiftLibraries(appPath).map((embedded) => {
    const name = basename(embedded);
    const paths = run('/usr/bin/find', [root, '-type', 'f', '-name', name]).split('\n')
      .filter((path) => path.includes('/iphoneos/'));
    const candidates = paths.map((path) => ({ path, name, uuid: swiftUuid(path), authority: signingAuthority(path) }));
    const selected = selectSwiftSupportLibrary(name, swiftUuid(embedded), candidates);
    run('/usr/bin/codesign', ['--verify', '--strict', '--verbose=2', selected]);
    return selected;
  });
}

export function packageArchive(metadata, output) {
  const outputPath = resolve(output);
  if (!outputPath.endsWith('.ipa')) throw new Error('output must end with .ipa');
  if (existsSync(outputPath)) throw new Error('output IPA already exists');
  if (outputPath.startsWith(`${metadata.archivePath}/`)) throw new Error('output must not be inside the archive');

  const supportLibraries = swiftSupportLibraries(metadata.appPath);
  const staging = mkdtempSync(join(tmpdir(), 'utm-22-'));
  try {
    const payload = join(staging, 'Payload');
    mkdirSync(payload);
    run('/usr/bin/ditto', [metadata.appPath, join(payload, metadata.appName)]);
    if (supportLibraries.length) {
      const swiftSupport = join(staging, 'SwiftSupport', 'iphoneos');
      mkdirSync(swiftSupport, { recursive: true });
      for (const library of supportLibraries) run('/usr/bin/ditto', [library, join(swiftSupport, basename(library))]);
    }
    run('/usr/bin/ditto', ['-c', '-k', '--sequesterRsrc', staging, outputPath]);
  } finally {
    rmSync(staging, { recursive: true, force: true });
  }

  const entries = run('/usr/bin/unzip', ['-Z1', outputPath]).split('\n');
  if (!entries.includes(`Payload/${metadata.appName}/Info.plist`)) throw new Error('IPA Payload is invalid');
  for (const library of supportLibraries) {
    if (!entries.includes(`SwiftSupport/iphoneos/${basename(library)}`)) throw new Error('IPA SwiftSupport is invalid');
  }
  run('/usr/bin/codesign', ['--verify', '--deep', '--strict', '--verbose=2', metadata.appPath]);
  return {
    ...metadata,
    ipaPath: outputPath,
    ipaSize: statSync(outputPath).size,
    sha256: createHash('sha256').update(readFileSync(outputPath)).digest('hex'),
  };
}

export function resumePackagedIpa(metadata, ipa, attemptFile) {
  const ipaPath = resolve(ipa);
  const attemptPath = resolve(attemptFile);
  if (!ipaPath.endsWith('.ipa') || !existsSync(ipaPath)) {
    throw new Error('same-attempt IPA is not a regular .ipa file');
  }
  const ipaInfo = lstatSync(ipaPath);
  if (ipaInfo.isSymbolicLink()) throw new Error('same-attempt IPA must not be a symlink');
  if (!ipaInfo.isFile()) throw new Error('same-attempt IPA is not a regular .ipa file');
  if (!existsSync(attemptPath)) {
    throw new Error('same-attempt metadata file is missing');
  }
  const attemptInfo = lstatSync(attemptPath);
  if (attemptInfo.isSymbolicLink()) throw new Error('same-attempt metadata must not be a symlink');
  if (!attemptInfo.isFile()) throw new Error('same-attempt metadata file is not regular');
  if ((attemptInfo.mode & 0o777) !== 0o600) throw new Error('same-attempt metadata mode must be 600');
  const attempt = JSON.parse(readFileSync(attemptPath, 'utf8'));
  for (const key of ['bundleId', 'version', 'build']) {
    if (attempt[key] !== metadata[key]) throw new Error(`same-attempt IPA identity mismatch: ${key}`);
  }
  const file = readFileSync(ipaPath);
  const sha256 = createHash('sha256').update(file).digest('hex');
  if (!attempt.ipaSha256 || attempt.ipaSha256 !== sha256) {
    throw new Error('same-attempt IPA hash mismatch');
  }
  return {
    ...metadata,
    ipaPath,
    ipaSize: file.length,
    sha256,
  };
}

function apiError(status, body) {
  const details = body?.errors?.map((item) => `${item.code || status}: ${item.title || ''} ${item.detail || ''}`.trim());
  return new Error(details?.join('; ') || `App Store Connect API HTTP ${status}`);
}

async function apiRequest(method, path, credentials, body) {
  const token = makeToken({
    issuerId: credentials.issuerId,
    keyId: credentials.keyId,
    privateKey: credentials.privateKey,
  });
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const parsed = text ? JSON.parse(text) : {};
  if (!response.ok) throw apiError(response.status, parsed);
  return parsed;
}

async function uploadOperations(ipa, operations) {
  const file = readFileSync(ipa);
  const ordered = [...operations].sort((a, b) => Number(a.offset) - Number(b.offset));
  let expectedOffset = 0;
  for (const operation of ordered) {
    if (Number(operation.offset) !== expectedOffset) throw new Error('upload operations are not contiguous');
    const chunk = operationChunk(file, operation);
    const headers = Object.fromEntries((operation.requestHeaders || []).map(({ name, value }) => [name, value]));
    let uploaded = false;
    let lastError;
    for (let attempt = 1; attempt <= 3 && !uploaded; attempt += 1) {
      try {
        const response = await fetch(operation.url, { method: operation.method, headers, body: chunk });
        if (response.ok) {
          uploaded = true;
          break;
        }
        lastError = new Error(`file upload failed with HTTP ${response.status}`);
        if (![408, 429].includes(response.status) && response.status < 500) break;
      } catch (error) {
        lastError = error;
      }
      if (attempt < 3) await new Promise((resolveDelay) => setTimeout(resolveDelay, attempt * 3000));
    }
    if (!uploaded) throw new Error(`file upload operation exhausted recovery: ${lastError?.message || 'unknown error'}`);
    expectedOffset += chunk.length;
  }
  if (expectedOffset !== file.length) throw new Error('upload operations do not cover the whole IPA');
}

function stateDetails(state) {
  return (state?.errors || []).map((item) => `${item.code || 'ERROR'}: ${item.message || item.description || JSON.stringify(item)}`).join('; ');
}

export function buildStatus(response) {
  const build = (response.included || []).find((item) => item.type === 'builds');
  return {
    uploadState: response.data?.attributes?.state?.state,
    buildId: build?.id,
    processingState: build?.attributes?.processingState,
    version: build?.attributes?.version,
  };
}

function stateName(item) {
  const state = item?.attributes?.state;
  return typeof state === 'string' ? state : state?.state;
}

export function classifyMatchingUploads(items) {
  if (!Array.isArray(items) || items.length === 0) return { action: 'create' };
  if (items.length !== 1) return { action: 'ambiguous', count: items.length };
  const uploadId = items[0]?.id;
  const state = stateName(items[0]) || 'UNKNOWN';
  if (!uploadId) return { action: 'ambiguous', count: 1 };
  if (['COMPLETE', 'PROCESSING'].includes(state)) return { action: 'resume', uploadId, state };
  if (state === 'FAILED') return { action: 'failed', uploadId, state };
  return { action: 'ambiguous', count: 1, uploadId, state };
}

function fsyncDirectory(path) {
  const descriptor = openSync(path, 'r');
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

function atomicReplaceFile(target, payload, mode) {
  const temporary = join(dirname(target), `.${basename(target)}.tmp-${randomUUID()}`);
  let descriptor;
  try {
    descriptor = openSync(temporary, 'wx', mode);
    writeFileSync(descriptor, payload);
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
    chmodSync(temporary, mode);
    renameSync(temporary, target);
    fsyncDirectory(dirname(target));
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
    rmSync(temporary, { force: true });
  }
}

export function writeAttempt(path, value) {
  const target = resolve(path);
  const directory = dirname(target);
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const directoryInfo = lstatSync(directory);
  if (directoryInfo.isSymbolicLink() || !directoryInfo.isDirectory()) {
    throw new Error('upload attempt directory must not be a symlink');
  }

  const existed = existsSync(target);
  let before;
  let beforeMode;
  if (existed) {
    const info = lstatSync(target);
    if (info.isSymbolicLink()) throw new Error('upload attempt path must not be a symlink');
    if (!info.isFile()) throw new Error('upload attempt path is not a regular file');
    before = readFileSync(target);
    beforeMode = info.mode & 0o777;
  }

  const payload = Buffer.from(`${JSON.stringify(value, null, 2)}\n`, 'utf8');
  if (before?.equals(payload) && beforeMode === 0o600) return;

  let replaced = false;
  try {
    atomicReplaceFile(target, payload, 0o600);
    replaced = true;
    const current = lstatSync(target);
    if (current.isSymbolicLink() || !current.isFile()) throw new Error('upload attempt readback is not a regular file');
    if ((current.mode & 0o777) !== 0o600) throw new Error('upload attempt readback mode mismatch');
    if (!readFileSync(target).equals(payload)) throw new Error('upload attempt readback content mismatch');
  } catch (error) {
    if (replaced) {
      try {
        if (existed) {
          atomicReplaceFile(target, before, beforeMode);
          const restored = lstatSync(target);
          if (!readFileSync(target).equals(before) || (restored.mode & 0o777) !== beforeMode) {
            throw new Error('rollback readback mismatch');
          }
        } else {
          unlinkSync(target);
          fsyncDirectory(directory);
          if (existsSync(target)) throw new Error('rollback removal mismatch');
        }
      } catch (rollbackError) {
        throw new Error(`upload attempt write failed and rollback was not verified: ${rollbackError.message}`, { cause: error });
      }
    }
    throw error;
  }
}

function loadOrCreateAttempt(path, metadata, appId) {
  const identity = {
    appId,
    bundleId: metadata.bundleId,
    version: metadata.version,
    build: metadata.build,
    ipaSha256: metadata.sha256,
  };
  if (existsSync(path)) {
    const info = lstatSync(path);
    if (info.isSymbolicLink()) throw new Error('upload attempt path must not be a symlink');
    if (!info.isFile()) throw new Error('upload attempt path is not a regular file');
    if ((info.mode & 0o777) !== 0o600) {
      chmodSync(path, 0o600);
      if ((lstatSync(path).mode & 0o777) !== 0o600) throw new Error('upload attempt mode repair failed');
    }
    const current = JSON.parse(readFileSync(path, 'utf8'));
    for (const [key, value] of Object.entries(identity)) {
      if (current[key] !== value) throw new Error(`upload attempt identity mismatch: ${key}`);
    }
    if (!current.attemptId) throw new Error('upload attempt ID is missing');
    return current;
  }
  const attempt = {
    attemptId: randomUUID(),
    ...identity,
    state: 'preflight',
    createdAt: new Date().toISOString(),
  };
  writeAttempt(path, attempt);
  return attempt;
}

export function matchingBuildsQuery(metadata, appId) {
  const query = new URLSearchParams({
    'filter[app]': appId,
    'filter[version]': metadata.build,
    include: 'preReleaseVersion',
    'fields[builds]': 'version,processingState,preReleaseVersion',
    'fields[preReleaseVersions]': 'version',
    limit: '200',
  });
  return `/builds?${query}`;
}

async function matchingBuilds(metadata, appId, credentials) {
  const response = await apiRequest('GET', matchingBuildsQuery(metadata, appId), credentials);
  const preReleaseVersions = new Map((response.included || [])
    .filter((item) => item?.type === 'preReleaseVersions')
    .map((item) => [item.id, item.attributes?.version]));
  return (response.data || []).filter((item) => (
    item?.attributes?.version === metadata.build
    && preReleaseVersions.get(item?.relationships?.preReleaseVersion?.data?.id) === metadata.version
  ));
}

async function pollBuildUpload(uploadId, credentials, waitSeconds) {
  const deadline = Date.now() + waitSeconds * 1000;
  const delays = [15000, 30000, 60000, 120000];
  let pollIndex = 0;
  let previousUpload;
  let previousBuild;
  while (Date.now() < deadline) {
    const current = await apiRequest('GET', `/buildUploads/${encodeURIComponent(uploadId)}?include=build&fields[buildUploads]=state,build&fields[builds]=processingState,version`, credentials);
    const state = current.data?.attributes?.state || {};
    const build = buildStatus(current);
    if (state.state !== previousUpload) {
      console.log(`BUILD_UPLOAD_STATE=${state.state || 'UNKNOWN'}`);
      previousUpload = state.state;
    }
    if (build.processingState && build.processingState !== previousBuild) {
      console.log(`BUILD_PROCESSING_STATE=${build.processingState}`);
      previousBuild = build.processingState;
    }
    if (state.state === 'COMPLETE' && build.processingState === 'VALID') {
      return { uploadId, state: state.state, buildId: build.buildId, buildProcessingState: build.processingState };
    }
    if (state.state === 'FAILED') throw new Error(`Apple build upload failed: ${stateDetails(state) || 'no details returned'}`);
    if (['FAILED', 'INVALID'].includes(build.processingState)) throw new Error(`Apple build processing failed: ${build.processingState}`);
    const delay = delays[Math.min(pollIndex, delays.length - 1)];
    pollIndex += 1;
    if (Date.now() + delay >= deadline) break;
    await new Promise((resolveDelay) => setTimeout(resolveDelay, delay));
  }
  return { uploadId, state: previousUpload || 'PROCESSING', buildProcessingState: previousBuild || 'PROCESSING' };
}

export async function uploadIpa(metadata, options) {
  const credentials = {
    issuerId: options.issuerId,
    keyId: options.keyId,
    privateKey: createPrivateKey(readFileSync(options.privateKeyPath)),
  };

  const app = await apiRequest('GET', `/apps/${encodeURIComponent(options.appId)}?fields[apps]=bundleId,name`, credentials);
  if (app.data?.attributes?.bundleId !== metadata.bundleId) {
    throw new Error('App Store Connect app bundle ID does not match the IPA');
  }

  const attempt = loadOrCreateAttempt(options.attemptFile, metadata, options.appId);
  console.log(`UPLOAD_ATTEMPT_ID=${attempt.attemptId}`);
  const existingBuilds = await matchingBuilds(metadata, options.appId, credentials);
  if (existingBuilds.length > 0) {
    writeAttempt(options.attemptFile, {
      ...attempt,
      state: existingBuilds.length === 1 ? 'existing_build_no_create' : 'ambiguous_existing_upload',
      existingBuildIds: existingBuilds.map((item) => item.id),
    });
    throw new Error('same-version build already exists; refusing to create another upload');
  }

  writeAttempt(options.attemptFile, { ...attempt, state: 'creating_build_upload' });
  let upload;
  try {
    upload = await apiRequest('POST', '/buildUploads', credentials,
      createBuildUploadBody(options.appId, metadata.version, metadata.build));
  } catch (error) {
    for (const delay of [5000, 10000, 20000]) {
      await new Promise((resolveDelay) => setTimeout(resolveDelay, delay));
      const recoveredBuilds = await matchingBuilds(metadata, options.appId, credentials);
      if (recoveredBuilds.length > 0) {
        writeAttempt(options.attemptFile, {
          ...attempt,
          state: 'recovered_after_create_result_unknown',
          existingBuildIds: recoveredBuilds.map((item) => item.id),
        });
        throw new Error('build appeared after an ambiguous create result; refusing to create another upload');
      }
    }
    writeAttempt(options.attemptFile, { ...attempt, state: 'create_result_ambiguous' });
    throw new Error(`build upload create result is ambiguous; no retry was performed (${error.message})`);
  }
  const uploadId = upload.data.id;
  writeAttempt(options.attemptFile, { ...attempt, state: 'build_upload_created', buildUploadId: uploadId });
  const reservation = await apiRequest('POST', '/buildUploadFiles', credentials,
    createBuildUploadFileBody(uploadId, basename(metadata.ipaPath), metadata.ipaSize));
  const fileId = reservation.data.id;
  writeAttempt(options.attemptFile, {
    ...attempt,
    state: 'file_reserved',
    buildUploadId: uploadId,
    buildUploadFileId: fileId,
  });
  const operations = reservation.data.attributes?.uploadOperations || [];
  if (!operations.length) throw new Error('Apple returned no upload operations');

  await uploadOperations(metadata.ipaPath, operations);
  await apiRequest('PATCH', `/buildUploadFiles/${encodeURIComponent(fileId)}`, credentials,
    commitBuildUploadFileBody(fileId));
  writeAttempt(options.attemptFile, {
    ...attempt,
    state: 'file_committed',
    buildUploadId: uploadId,
    buildUploadFileId: fileId,
  });
  const completed = await pollBuildUpload(uploadId, credentials, options.waitSeconds);
  writeAttempt(options.attemptFile, {
    ...attempt,
    state: completed.state === 'COMPLETE' && completed.buildProcessingState === 'VALID' ? 'verified' : 'processing',
    buildUploadId: uploadId,
    buildUploadFileId: fileId,
    buildId: completed.buildId,
  });
  return completed;
}

function argumentsFrom(argv) {
  const [command, ...rest] = argv;
  const options = {};
  for (let i = 0; i < rest.length; i += 2) {
    if (!rest[i]?.startsWith('--') || rest[i + 1] === undefined) throw new Error(`invalid argument: ${rest[i] || ''}`);
    options[rest[i].slice(2).replaceAll('-', '_')] = rest[i + 1];
  }
  return { command, options };
}

function required(options, names) {
  for (const name of names) if (!options[name]) throw new Error(`--${name.replaceAll('_', '-')} is required`);
}

async function main() {
  const { command, options } = argumentsFrom(process.argv.slice(2));
  if (!['prepare', 'distribute'].includes(command)) {
    throw new Error('usage: utm_22_distribute.mjs prepare|distribute [options]');
  }
  required(options, ['archive', 'output']);
  const archiveMetadata = inspectArchive(options.archive);
  let metadata;
  if (command === 'distribute' && existsSync(resolve(options.output))) {
    required(options, ['attempt_file']);
    metadata = resumePackagedIpa(archiveMetadata, options.output, options.attempt_file);
    console.log('SAME_ATTEMPT_IPA=verified');
  } else {
    metadata = packageArchive(archiveMetadata, options.output);
    console.log('ARCHIVE_DISTRIBUTION=verified');
  }
  console.log(`APP_BUNDLE_ID=${metadata.bundleId}`);
  console.log(`APP_VERSION=${metadata.version}`);
  console.log(`APP_BUILD=${metadata.build}`);
  console.log(`IPA_PATH=${metadata.ipaPath}`);
  console.log(`IPA_SIZE=${metadata.ipaSize}`);
  console.log(`IPA_SHA256=${metadata.sha256}`);

  if (command !== 'prepare') {
    required(options, ['app_id', 'issuer_id', 'key_id', 'private_key', 'attempt_file']);
    const result = await uploadIpa(metadata, {
      appId: options.app_id,
      issuerId: options.issuer_id,
      keyId: options.key_id,
      privateKeyPath: options.private_key,
      attemptFile: options.attempt_file,
      waitSeconds: Number(options.wait_seconds || 1800),
    });
    console.log(`BUILD_UPLOAD_ID=${result.uploadId}`);
    console.log(`BUILD_UPLOAD_FINAL_STATE=${result.state}`);
    console.log(`BUILD_PROCESSING_STATE=${result.buildProcessingState}`);
    if (result.state !== 'COMPLETE' || result.buildProcessingState !== 'VALID') process.exitCode = 2;
  }
}

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) main().catch((error) => {
  console.error(`UTM_22_ERROR=${error.message}`);
  process.exitCode = 1;
});
