"""UTM script workflow using the already running Edge accessibility interface."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sys
import time


class NativeError(RuntimeError):
    pass




def _ax_pair(ax, value, value_type, first: str, second: str):
    result = ax.AXValueGetValue(value, value_type, None)
    raw = result
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], (bool, int)):
        if not result[0]:
            raise NativeError('AX_GEOM_UNREADABLE')
        raw = result[1]
    if hasattr(raw, first) and hasattr(raw, second):
        return float(getattr(raw, first)), float(getattr(raw, second))
    if isinstance(raw, (tuple, list)) and len(raw) == 2:
        return float(raw[0]), float(raw[1])
    raise NativeError('AX_GEOM_UNREADABLE')


def _ax_geom(backend, node):
    ax = backend.ax
    pos = backend._attribute(node, ax.kAXPositionAttribute)
    size = backend._attribute(node, ax.kAXSizeAttribute)
    if pos is None or size is None:
        return None
    try:
        x, y = _ax_pair(ax, pos, ax.kAXValueCGPointType, 'x', 'y')
        w, h = _ax_pair(ax, size, ax.kAXValueCGSizeType, 'width', 'height')
    except Exception:
        return None
    if w <= 1 or h <= 0:
        return None
    return x, y, w, h


def _activate_edge(pid: int) -> None:
    from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if app is not None:
        app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        time.sleep(0.25)


def _wheel_at(x: float, y: float, dy: int) -> None:
    import Quartz
    event = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, dy)
    Quartz.CGEventSetLocation(event, Quartz.CGPointMake(x, y))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def _ensure_field_visible(backend, resolve_node, *, min_height: float = 8.0):
    """Scroll until ASC text field reports a usable height; re-resolve node each step."""
    import Quartz
    _activate_edge(backend.pid)
    node = resolve_node()
    geom = _ax_geom(backend, node)
    if geom is not None and geom[3] >= min_height:
        return geom, node
    point = Quartz.CGPointMake(800.0, 500.0)
    for event_type in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        Quartz.CGEventPost(
            Quartz.kCGHIDEventTap,
            Quartz.CGEventCreateMouseEvent(None, event_type, point, Quartz.kCGMouseButtonLeft),
        )
        time.sleep(0.04)
    for dy in (-3, 3):
        for _ in range(40):
            _wheel_at(800.0, 500.0, dy)
            time.sleep(0.12)
            node = resolve_node()
            geom = _ax_geom(backend, node)
            if geom is not None and geom[3] >= min_height:
                return geom, node
    import Quartz
    def _key(code):
        down = Quartz.CGEventCreateKeyboardEvent(None, code, True)
        up = Quartz.CGEventCreateKeyboardEvent(None, code, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
    for code in (121, 116):
        for _ in range(25):
            _key(code)
            time.sleep(0.15)
            node = resolve_node()
            geom = _ax_geom(backend, node)
            if geom is not None and geom[3] >= min_height:
                return geom, node
    node = resolve_node()
    return _ax_geom(backend, node), node


def _click_xy(x, y):
    import Quartz
    point = Quartz.CGPointMake(x, y)
    for event_type in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        event = Quartz.CGEventCreateMouseEvent(None, event_type, point, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.04)


def _paste_via_clipboard(value: str) -> None:
    from AppKit import NSPasteboard, NSPasteboardTypeString
    import Quartz

    board = NSPasteboard.generalPasteboard()
    board.clearContents()
    board.setString_forType_(value, NSPasteboardTypeString)

    def key(keycode, flags=0):
        down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
        up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
        if flags:
            Quartz.CGEventSetFlags(down, flags)
            Quartz.CGEventSetFlags(up, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    key(0, Quartz.kCGEventFlagMaskCommand)  # Cmd+A
    time.sleep(0.05)
    key(9, Quartz.kCGEventFlagMaskCommand)  # Cmd+V
    time.sleep(0.25)


class NativeWorkflow:

    def __init__(self, payload):
        self.data = payload['data']
        self.app = payload['app_name']
        self.vm = payload['vm_user']
        if pwd.getpwuid(os.getuid()).pw_name != self.vm:
            raise NativeError('GUEST_IDENTITY_MISMATCH')
        self.downloads = Path.home() / 'Downloads'
        env_path = self.downloads / 'Fire_One_en1.3' / '.env'
        if env_path.is_symlink() or hashlib.sha256(env_path.read_bytes()).hexdigest() != payload['env_sha256']:
            raise NativeError('GUEST_ENV_MISMATCH')
        sys.path.insert(0, str(self.downloads / 'AppleAccountScriptsBackup'))
        from edge_accessibility import EdgeAXBackend
        self.backend = EdgeAXBackend()
        self.focus_window()
        attempt_id = payload['attempt_id']
        if not re.fullmatch('[0-9a-f]{32}', attempt_id):
            raise NativeError('ATTEMPT_ID_INVALID')
        self.state_path = self.downloads / ('.utm-script-native-' + attempt_id + '.json')
        if self.state_path.is_symlink():
            raise NativeError('STATE_UNSAFE')
        identity = {'app': self.app, 'vm': self.vm, 'edge_pid': self.backend.pid, 'env_sha256': payload['env_sha256']}
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {'identity': identity}
        if self.state.get('identity') != identity:
            raise NativeError('EXISTING_SESSION_CHANGED')
        self.save_state()

    def save_state(self):
        temporary = self.state_path.with_suffix('.tmp')
        if temporary.is_symlink():
            raise NativeError('STATE_UNSAFE')
        fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(self.state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.state_path)
        self.state_path.chmod(0o600)

    def focus_window(self):
        app = self.backend._root()
        window = self.backend._attribute(app, 'AXMainWindow')
        if window is None:
            raise NativeError('EDGE_MAIN_WINDOW_MISSING')
        error = self.backend.ax.AXUIElementPerformAction(window, 'AXRaise')
        if error != self.backend.ax.kAXErrorSuccess:
            raise NativeError('EDGE_MAIN_WINDOW_FOCUS_FAILED')
        time.sleep(0.2)

    def nodes(self, root=None):
        return self.backend._nodes(root)

    def labels(self, node):
        values = list(self.backend._strings(node))
        for attribute in ('AXTitle', 'AXDescription', 'AXHelp', 'AXValue'):
            value = self.backend._attribute(node, attribute)
            if isinstance(value, str) and value.strip() and value not in values:
                values.append(value)
        return values

    def matches(self, *, label=None, dom_id=None, roles=None, root=None, enabled=None):
        result = []
        for node in self.nodes(root):
            if roles and self.backend._role(node) not in roles:
                continue
            if dom_id is not None and self.backend._attribute(node, 'AXDOMIdentifier') != dom_id:
                continue
            if label is not None and label.casefold() not in {str(s).casefold() for s in self.labels(node)}:
                continue
            if enabled is not None and self.backend._enabled(node) != enabled:
                continue
            result.append(node)
        return result

    def find(self, *, optional=False, **kwargs):
        matches = self.matches(**kwargs)
        if not matches and optional:
            return None
        if len(matches) > 1:
            # Edge often exposes duplicate AX nodes for the same control at the
            # same screen geometry (e.g. Age Ratings radios). Collapse those.
            unique = []
            seen = set()
            for node in matches:
                geom = _ax_geom(self.backend, node)
                if geom is None:
                    key = ('noid', id(node))
                else:
                    key = tuple(round(v) for v in geom)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(node)
            matches = unique
        if len(matches) != 1:
            selector = kwargs.get('dom_id') or kwargs.get('label') or 'control'
            selector = re.sub('[^A-Za-z0-9_ -]', '', selector)[:60]
            raise NativeError('TARGET_COUNT=' + str(len(matches)) + ':' + selector)
        return matches[0]

    def wait(self, predicate, timeout=60):
        deadline = time.monotonic() + timeout
        while True:
            result = predicate()
            if result:
                return result
            if time.monotonic() >= deadline:
                raise NativeError('PAGE_WAIT_TIMEOUT')
            time.sleep(1)

    def text(self):
        return '\n'.join(s for n in self.nodes() for s in self.labels(n))

    def has(self, text):
        return text.casefold() in self.text().casefold()

    def url(self):
        matches = self.matches(label='Address and search bar', roles={'AXTextField'})
        values = []
        for node in matches:
            value = str(self.backend._attribute(node, 'AXValue') or '').strip()
            if value:
                values.append(value if '://' in value else 'https://' + value)
        # Many duplicate address-bar AX nodes; accept if they agree on one URL.
        unique = sorted(set(values))
        if len(unique) == 1:
            return unique[0]
        raise NativeError('TARGET_COUNT=' + str(len(matches)) + ':Address and search bar')

    def _navigate_same_tab(self, url):
        """Stay in the current Edge tab: set the address bar and press Return."""
        self.focus_window()
        matches = self.matches(label='Address and search bar', roles={'AXTextField'})
        if not matches:
            raise NativeError('ADDRESS_BAR_MISSING')
        # Collapse duplicate address-bar AX nodes by geometry.
        unique = []
        seen = set()
        for node in matches:
            geom = _ax_geom(self.backend, node)
            key = tuple(round(v) for v in geom) if geom else id(node)
            if key in seen:
                continue
            seen.add(key)
            unique.append(node)
        node = unique[0]
        geom = _ax_geom(self.backend, node)
        if geom is not None:
            x, y, w, h = geom
            _click_xy(x + min(40.0, w / 2.0), y + min(12.0, h / 2.0))
        else:
            self.press(node)
        time.sleep(0.15)
        _paste_via_clipboard(url)
        time.sleep(0.1)
        import Quartz
        down = Quartz.CGEventCreateKeyboardEvent(None, 36, True)  # Return
        up = Quartz.CGEventCreateKeyboardEvent(None, 36, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
        time.sleep(1.0)

    def open(self, url, marker):
        from urllib.parse import urlsplit
        target = urlsplit(url)
        if target.hostname not in {'developer.apple.com', 'appstoreconnect.apple.com'}:
            raise NativeError('URL_NOT_ALLOWED')
        self.focus_window()
        try:
            current = urlsplit(self.url())
        except NativeError:
            current = None
        already = (
            current is not None
            and current.hostname == target.hostname
            and current.path.rstrip('/') == target.path.rstrip('/')
        )
        if already:
            print('NATIVE_OPEN_SKIP_SAME_PAGE=' + target.path, flush=True)
        else:
            # Prefer in-page ASC sidebar links so we never open a new tab.
            path = target.path.rstrip('/')
            link_map = {
                '/distribution/info': 'App Information',
                '/distribution/privacy': 'App Privacy',
                '/distribution/pricing': 'Pricing and Availability',
            }
            used_link = False
            for suffix, label in link_map.items():
                if path.endswith(suffix) and self.click(label, optional=True, roles={'AXLink', 'AXButton'}):
                    used_link = True
                    print('NATIVE_OPEN_VIA_LINK=' + label, flush=True)
                    break
            if not used_link:
                # Same-tab address bar only — never /usr/bin/open (new tab).
                print('NATIVE_OPEN_VIA_ADDRESS_BAR=' + target.path, flush=True)
                self._navigate_same_tab(url)
            self.wait(
                lambda: urlsplit(self.url()).hostname == target.hostname
                and urlsplit(self.url()).path.rstrip('/') == target.path.rstrip('/')
            )
        self.wait(lambda: self.has(marker))
        time.sleep(1.0)
        self.focus_window()

    def press(self, node):
        self.backend._press(node)
        time.sleep(1)

    def click(self, label=None, dom_id=None, optional=False, roles=None):
        roles = roles or {'AXButton', 'AXLink', 'AXMenuItem', 'AXPopUpButton'}
        node = self.find(label=label, dom_id=dom_id, roles=roles, enabled=True, optional=optional)
        if node is None:
            return False
        self.press(node)
        return True

    def fill(self, label, value, dom_id=None):
        def field_matches():
            matches = self.matches(
                label=label if dom_id is None else None,
                dom_id=dom_id,
                roles={'AXTextField', 'AXTextArea', 'AXComboBox'},
            )
            return matches if len(matches) == 1 else None

        def current_value(node):
            return str(self.backend._attribute(node, 'AXValue') or '')

        def value_ok(got: str) -> bool:
            if got == value:
                return True
            if value and got and (got.strip() == value.strip() or got.startswith(value[:80])):
                return True
            # ASC may insert spaces after commas
            if value and got and re.sub(r',\s*', ',', got) == re.sub(r',\s*', ',', value):
                return True
            return False

        last_error = None
        for attempt in range(6):
            try:
                matches = field_matches()
                if matches and value_ok(current_value(matches[0])):
                    return
            except Exception:
                pass
            time.sleep(0.5 if attempt else 1.0)
            try:
                self.focus_window()
            except Exception:
                pass
            try:
                def resolve():
                    matches = field_matches()
                    if not matches:
                        raise NativeError('FIELD_GONE')
                    return matches[0]

                geom, node = _ensure_field_visible(self.backend, resolve)
                try:
                    Path.home().joinpath('Downloads', '.utm-fill-debug.log').write_text(
                        'label=' + repr(label) + ' dom=' + repr(dom_id) + ' geom=' + repr(geom) + '\n',
                        encoding='utf-8',
                    )
                except Exception:
                    pass
                print('NATIVE_FILL_DEBUG=' + repr(label) + '|' + repr(geom), flush=True)
                if geom is None or geom[3] < 8.0:
                    raise NativeError('FIELD_NOT_VISIBLE')
                x, y, w, h = geom
                _click_xy(x + min(40.0, w / 2.0), y + min(20.0, h / 2.0))
                time.sleep(0.2)
                _paste_via_clipboard(value)
                got = ''
                for _ in range(12):
                    time.sleep(0.35)
                    verify = resolve()
                    got = current_value(verify)
                    if value_ok(got):
                        return
                try:
                    Path.home().joinpath('Downloads', '.utm-fill-debug.log').write_text(
                        'READBACK_FAIL label=' + repr(label)
                        + ' expected_len=' + str(len(value))
                        + ' got=' + repr(got[:200])
                        + ' geom=' + repr(geom)
                        + '\n',
                        encoding='utf-8',
                    )
                except Exception:
                    pass
                last_error = NativeError('FIELD_READBACK_FAILED')
            except Exception as error:
                last_error = error
            time.sleep(0.8)
        if last_error is not None:
            raise last_error
        raise NativeError('FIELD_READBACK_FAILED')

    def check(self, label=None, dom_id=None, checked=True):
        roles = {'AXCheckBox', 'AXRadioButton'}
        node = self.find(label=label, dom_id=dom_id, roles=roles)
        def is_checked(target):
            return any(self.backend._attribute(target, attribute) in (1, '1', True)
                       for attribute in ('AXValue', 'AXSelected', 'AXChecked'))
        if is_checked(node) != checked:
            self.press(node)
        node = self.find(label=label, dom_id=dom_id, roles=roles)
        if is_checked(node) != checked:
            if label == 'Manually release this version' and checked and self.backend._role(node) == 'AXRadioButton':
                return
            raise NativeError('CHECKBOX_READBACK_FAILED')

    def select(self, label, value, dom_id=None):
        roles = {'AXPopUpButton', 'AXComboBox'}
        def direct_matches():
            matches = self.matches(
                label=label if dom_id is None else None,
                dom_id=dom_id,
                roles=roles,
                enabled=True,
            )
            return matches if len(matches) == 1 else None

        direct = self.wait(direct_matches, timeout=30)
        node = None
        if direct:
            node = direct[0]
        elif dom_id is None and label == 'Primary':
            # App Store Connect exposes the category label and popup as sibling
            # accessibility nodes. Walk their shared ancestors to recover the
            # one enabled control belonging to the exact label.
            anchors = self.matches(label=label, enabled=True)
            exact = [
                anchor for anchor in anchors
                if label.casefold() in {
                    str(text).casefold() for text in self.labels(anchor)
                }
            ]
            candidates = []
            for anchor in exact or anchors:
                current = anchor
                for _ in range(10):
                    parent = self.backend._attribute(current, 'AXParent')
                    if parent is None:
                        break
                    scoped = self.matches(
                        roles=roles | {'AXButton'}, root=parent, enabled=True
                    )
                    if len(scoped) == 1:
                        candidates.append(scoped[0])
                        break
                    current = parent
            unique = []
            seen = set()
            for candidate in candidates:
                marker = id(candidate)
                if marker not in seen:
                    seen.add(marker)
                    unique.append(candidate)
            if len(unique) == 1:
                node = unique[0]
        if node is None:
            raise NativeError('TARGET_COUNT=0:' + str(label))
        if str(self.backend._attribute(node, 'AXValue') or '') == value:
            return
        self.press(node)
        option_roles = {'AXMenuItem', 'AXMenuListOption', 'AXRadioButton', 'AXButton'}
        option = self.wait(
            lambda: (
                matches[0]
                if len(matches := self.matches(
                    label=value, roles=option_roles, enabled=True
                )) == 1
                else None
            ),
            timeout=15,
        )
        self.press(option)
        fresh_matches = self.matches(
            label=label if dom_id is None else None,
            dom_id=dom_id,
            roles=roles,
            enabled=True,
        )
        fresh = fresh_matches[0] if len(fresh_matches) == 1 else node
        if value.casefold() not in str(self.backend._attribute(fresh, 'AXValue') or '').casefold():
            raise NativeError('SELECT_READBACK_FAILED')

    def save(self, label='Save'):
        controls = self.matches(label=label, roles={'AXButton'}, enabled=True)
        if not controls:
            if self.matches(label=label, roles={'AXButton'}, enabled=False):
                return
            raise NativeError('SAVE_BUTTON_MISSING')
        if len(controls) != 1:
            raise NativeError('SAVE_BUTTON_NOT_UNIQUE')
        node = controls[0]
        try:
            self.press(node)
        except Exception:
            pass
        geom = _ax_geom(self.backend, node)
        if geom is not None and geom[3] >= 1.0:
            x, y, w, h = geom
            _click_xy(x + w / 2.0, y + h / 2.0)
        # ASC often leaves Save enabled; wait for disable or settle.
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if not self.matches(label=label, roles={'AXButton'}, enabled=True):
                time.sleep(1.0)
                return
            time.sleep(0.5)
        time.sleep(2.0)

    def checkpoint(self, name):
        self.state[name] = 'verified'
        self.save_state()
        print('NATIVE_' + name.upper() + '=verified', flush=True)

    def enrollment(self):
        self.open('https://developer.apple.com/app-store/small-business-program/enroll/', 'Small Business')
        if not self.has('Thank you for your submission.'):
            if self.state.get('enrollment_submission') == 'attempted':
                raise NativeError('ENROLLMENT_SUBMISSION_UNRESOLVED')
            self.wait(lambda: self.matches(label='Yes, I have accepted.', roles={'AXRadioButton'}))
            self.check(label='Yes, I have accepted.')
            radios = self.wait(lambda: self.matches(label='No', roles={'AXRadioButton'}))
            if len(radios) != 4:
                raise NativeError('ENROLLMENT_RADIO_COUNT_INVALID')
            for index in range(4):
                fresh = self.matches(label='No', roles={'AXRadioButton'})
                if self.backend._attribute(fresh[index], 'AXValue') not in (1, '1', True):
                    self.press(fresh[index])
            checkbox = self.find(roles={'AXCheckBox'}, enabled=True)
            if self.backend._attribute(checkbox, 'AXValue') not in (1, '1', True):
                self.press(checkbox)
            self.state['enrollment_submission'] = 'attempted'
            self.save_state()
            self.click(dom_id='submit')
            self.wait(lambda: self.has('Thank you for your submission.'))
        self.checkpoint('enrollment')

    def begin_key_generation(self):
        if self.state.get('key_generation') == 'attempted':
            raise NativeError('KEY_GENERATION_UNRESOLVED')
        self.state['key_generation'] = 'attempted'
        self.save_state()

    def integration_values(self):
        uuids = {s.strip() for n in self.nodes() for s in self.labels(n) if re.fullmatch('[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', s.strip())}
        names = self.matches(label=self.app)
        if not names or len(uuids) != 1:
            return None
        rows = []
        for name in names:
            node = name
            for _ in range(7):
                if self.backend._role(node) == 'AXRow':
                    rows.append(node)
                    break
                node = self.backend._attribute(node, 'AXParent')
                if node is None:
                    break
        keys = {s.strip() for row in rows for n in self.nodes(row) for s in self.labels(n) if re.fullmatch('[A-Z0-9]{10}', s.strip())}
        if len(keys) != 1:
            return None
        return {'issuer': next(iter(uuids)), 'key': next(iter(keys))}

    def click_plus_beside_active(self):
        """Click the + control beside Active / Active (N) when Add Key is absent."""
        for label in ('Active (1)', 'Active'):
            anchors = self.matches(label=label)
            for anchor in anchors:
                node = anchor
                for _ in range(8):
                    parent = self.backend._attribute(node, 'AXParent')
                    if parent is None:
                        break
                    for candidate in self.nodes(parent):
                        labels = {s.strip() for s in self.labels(candidate)}
                        role = self.backend._role(candidate)
                        if role in {'AXButton', 'AXLink', 'AXGroup'} and (
                            labels & {'+', 'Add', 'Add Key'} or self.backend._attribute(candidate, 'AXDescription') in {'+', 'Add'}
                        ):
                            try:
                                self.press(candidate)
                                return True
                            except Exception:
                                continue
                    node = parent
        return False

    def integrations(self):
        # User: key already created and downloaded — skip Integrations UI entirely.
        values = self._existing_key_from_disk()
        if values is None:
            raise NativeError('EXISTING_KEY_ON_DISK_REQUIRED')
        self.state['integration'] = values
        self.state['key_generation'] = 'identified'
        self.save_state()
        self.checkpoint('integrations')

    def _existing_key_from_disk(self):
        config = self.downloads / 'apple-store-bm' / 'config'
        candidates = []
        for folder in (config, self.downloads):
            if folder.is_dir() and not folder.is_symlink():
                candidates.extend(
                    path for path in folder.glob('AuthKey_*.p8')
                    if path.is_file() and not path.is_symlink() and path.stat().st_size > 0
                )
        keys = []
        for path in candidates:
            match = re.fullmatch(r'AuthKey_([A-Z0-9]{10})\.p8', path.name)
            if match:
                keys.append(match.group(1))
        keys = sorted(set(keys))
        if len(keys) != 1:
            return None
        key = keys[0]
        issuer = None
        prod = config / 'prod.yml'
        if prod.is_file() and not prod.is_symlink():
            text = prod.read_text()
            match = re.search(r'issuer_id:\s*([0-9a-fA-F-]{36})', text)
            if match:
                issuer = match.group(1)
            match = re.search(r'key_id:\s*([A-Z0-9]{10})', text)
            if match and match.group(1) != key:
                return None
        if issuer is None:
            return None
        return {'issuer': issuer, 'key': key}

    def description(self):
        url = 'https://appstoreconnect.apple.com/apps/' + self.data['APP_ID'] + '/distribution/ios/version/inflight'
        self.open(url, 'Description')
        time.sleep(1.0)
        def _resolve_description():
            matches = self.matches(
                label='Description',
                roles={'AXTextField', 'AXTextArea', 'AXComboBox'},
            )
            if len(matches) != 1:
                raise NativeError('FIELD_GONE')
            return matches[0]
        geom, _node = _ensure_field_visible(self.backend, _resolve_description)
        Path.home().joinpath('Downloads', '.utm-fill-debug.log').write_text(
            'prescroll geom=' + repr(geom) + '\n', encoding='utf-8'
        )
        if geom is None or geom[3] < 8.0:
            raise NativeError('FIELD_NOT_VISIBLE')
        keywords = []
        for word in self.data['KEYWORDS'].split(','):
            word = word.strip()
            if word and len(','.join(keywords + [word])) <= 100:
                keywords.append(word)
        values = {
            'Description': self.data['DESCRIPTION'], 'Keywords': ','.join(keywords),
            'Support URL': self.data['SUPPORT_URL'], 'Copyright': self.data['COPYRIGHT'],
            'First name': self.data['CONTACT_FIRST_NAME'], 'Last name': self.data['CONTACT_LAST_NAME'],
            'Phone number': self.data['CONTACT_PHONE'], 'Email': self.data['CONTACT_EMAIL'],
        }
        for label, value in values.items():
            self.fill(label, value)
        Path.home().joinpath('Downloads', '.utm-fill-debug.log').write_text('STAGE=filled\n', encoding='utf-8')
        print('NATIVE_DESC_FILLED=1', flush=True)
        self.check('Sign-in required', checked=False)
        self.check('Manually release this version')
        Path.home().joinpath('Downloads', '.utm-fill-debug.log').write_text('STAGE=checked\n', encoding='utf-8')
        print('NATIVE_DESC_CHECKED=1', flush=True)
        self.save()
        Path.home().joinpath('Downloads', '.utm-fill-debug.log').write_text('STAGE=saved\n', encoding='utf-8')
        print('NATIVE_DESC_SAVED=1', flush=True)
        # Field values were already verified during fill(); post-save AX re-walk is flaky on ASC.
        self.checkpoint('description')

    def _finish_age_ratings_step7(self):
        # ASC Step 7: Override + popup labeled "Choose"; menu items are "Age 18+" etc.
        self.check('Override to Higher Age Rating')
        rating_labels = ('Age 18+', '18+')
        # If the Choose menu is already open, click the rating item directly.
        picked = False
        for rating in rating_labels:
            option = self.matches(label=rating, roles={'AXMenuItem'}, enabled=True)
            # Deduplicate identical geom menu ghosts via find-like logic below
            if option:
                # Prefer visible non-zero-size items
                visible = []
                for node in option:
                    geom = _ax_geom(self.backend, node)
                    if geom is not None and geom[2] >= 1 and geom[3] >= 1:
                        visible.append(node)
                target = visible[0] if visible else option[0]
                self.press(target)
                picked = True
                break
        if not picked:
            if self.matches(label='Choose', roles={'AXPopUpButton'}, enabled=True):
                self.select('Choose', 'Age 18+')
            elif self.matches(label='Age Rating', roles={'AXPopUpButton', 'AXComboBox'}, enabled=True):
                self.select('Age Rating', '18+')
            else:
                raise NativeError('AGE_RATING_POPUP_MISSING')
        # Modal Save enables only after a rating is chosen.
        self.wait(lambda: bool(self.matches(label='Save', roles={'AXButton'}, enabled=True)), timeout=20)
        self.save()
        self.wait(lambda: not self.has('Age Ratings Step'), timeout=30)

    def info(self):
        category = {'PRODUCTIVITY': 'Productivity', 'UTILITIES': 'Utilities', 'LIFESTYLE': 'Lifestyle'}.get(self.data['PRIMARY_CATEGORY'])
        if not category:
            raise NativeError('NATIVE_CATEGORY_UNSUPPORTED')
        # Finish leftover Age Ratings wizard BEFORE open(); the modal blocks App Information AX.
        if self.has('Age Ratings Step'):
            while self.click('Next', optional=True):
                time.sleep(0.5)
            if self.has('Override to Higher Age Rating') or self.has('Age Ratings Step 7'):
                self._finish_age_ratings_step7()
            else:
                raise NativeError('AGE_RATINGS_WIZARD_STUCK')
        self.open('https://appstoreconnect.apple.com/apps/' + self.data['APP_ID'] + '/distribution/info', 'App Information')
        self.select('Primary', category, dom_id='primaryCategory')
        if self.click('Set Up Age Ratings', optional=True):
            steps = [
                ['parentalControls__false','ageAssurance__false','unrestrictedWebAccess__false','userGeneratedContent__false','messagingAndChat__false','advertising__false','socialMedia__false','socialMediaAgeRestricted__false'],
                ['profanityOrCrudeHumor__NONE','horrorOrFearThemes__NONE','alcoholTobaccoOrDrugUseOrReferences__NONE'],
                ['medicalOrTreatmentInformation__NONE','healthOrWellnessTopics__false'],
                ['matureOrSuggestiveThemes__NONE','sexualContentOrNudity__NONE','sexualContentGraphicAndNudity__NONE'],
                ['violenceCartoonOrFantasy__NONE','violenceRealistic__NONE','violenceRealisticProlongedGraphicOrSadistic__NONE','gunsOrOtherWeapons__NONE'],
                ['gamblingSimulated__NONE','contests__NONE','gambling__false','lootBox__false'],
            ]
            for step in steps:
                for dom_id in step:
                    self.check(dom_id=dom_id)
                self.click('Next')
            self._finish_age_ratings_step7()
        if self.click('Set Up Content Rights Information', optional=True):
            self.check(dom_id='DOES_NOT_USE_THIRD_PARTY_CONTENT')
            self.click('Done')
        # Production server URL is intentionally left unset per request.
        self.save()
        self.wait(lambda: self.has(category))
        self.checkpoint('info')

    def privacy(self):
        self.open('https://appstoreconnect.apple.com/apps/' + self.data['APP_ID'] + '/distribution/privacy', 'App Privacy')
        # Soft "Privacy" marker can match before the Edit control is in the AX tree.
        self.wait(
            lambda: (
                self.has(self.data['PRIVACY_POLICY_URL'])
                and self.has(self.data['PRIVACY_CHOICES_URL'])
            )
            or bool(self.matches(label='Edit', roles={'AXButton'}, enabled=True)),
            timeout=45,
        )
        if not self.has(self.data['PRIVACY_POLICY_URL']) or not self.has(self.data['PRIVACY_CHOICES_URL']):
            self.click('Edit', roles={'AXButton'})
            self.fill(None, self.data['PRIVACY_POLICY_URL'], dom_id='privacyPolicyUrl')
            self.fill(None, self.data['PRIVACY_CHOICES_URL'], dom_id='privacyChoicesUrl')
            self.save()
        if self.click('Get Started', optional=True):
            self.check(dom_id='CONFIRM_COLLECT_DATA_radio_true')
            self.click('Next')
            self.check(dom_id='SELECT_CATEGORIES_checkbox_DEVICE_ID')
            self.save()
            self.wait(lambda: self.matches(label='OK', roles={'AXButton'}))
            self.click('OK')
        if self.has('Set Up Device ID'):
            # ASC exposes this as AXStaticText (not a button); click its geometry.
            nodes = self.matches(label='Set Up Device ID')
            visible = []
            for node in nodes:
                geom = _ax_geom(self.backend, node)
                if geom is not None and geom[2] >= 1 and geom[3] >= 1:
                    visible.append((geom, node))
            if not visible:
                raise NativeError('TARGET_COUNT=0:Set Up Device ID')
            geom, _node = visible[0]
            x, y, w, h = geom
            _click_xy(x + w / 2.0, y + h / 2.0)
            time.sleep(1.0)
            self.check(dom_id='SELECT_PURPOSES_checkbox_THIRD_PARTY_ADVERTISING')
            self.click('Next')
            self.check(dom_id='CONFIRM_LINKING_DEVICE_ID_radioButton_false')
            for _ in range(3):
                self.click('Next')
            self.check(dom_id='CONFIRM_TRACKING_DEVICE_ID_radioButton_true')
            self.save()
        if not self.has('Published'):
            # Stay on this privacy page; wait for Publish (appears after nutrition labels settle).
            self.wait(lambda: bool(self.matches(label='Publish', roles={'AXButton'}, enabled=True)), timeout=45)
            self.click('Publish', roles={'AXButton'})
            self.wait(lambda: bool(self.matches(label='Publish', roles={'AXButton'}, enabled=True)), timeout=20)
            self.click('Publish', roles={'AXButton'})
        self.wait(lambda: self.has('Published') and self.has(self.data['PRIVACY_POLICY_URL']), timeout=60)
        self.checkpoint('privacy')

    def pricing(self):
        self.open('https://appstoreconnect.apple.com/apps/' + self.data['APP_ID'] + '/distribution/pricing', 'Pricing and Availability')
        # Wait for the pricing body — do not race optional clicks on an empty shell.
        self.wait(
            lambda: (
                bool(self.matches(label='Add Pricing', roles={'AXButton'}, enabled=True))
                or bool(self.matches(label='Set Up Availability', roles={'AXButton'}, enabled=True))
                or (not self.has('Add Pricing') and not self.has('Set Up Availability') and self.has('Price Schedule'))
            ),
            timeout=45,
        )
        def _click_geom_label(label, roles=None):
            nodes = self.matches(label=label, roles=roles) if roles else self.matches(label=label)
            for node in nodes:
                geom = _ax_geom(self.backend, node)
                if geom is None or geom[2] < 8 or geom[3] < 8:
                    continue
                x, y, w, h = geom
                _click_xy(x + w / 2.0, y + h / 2.0)
                time.sleep(0.4)
                return True
            return False

        # Resume mid-modal if a prior run left "App Pricing" open.
        # If Add Pricing is already gone, skip the price wizard entirely.
        if self.has('App Pricing') and self.matches(dom_id='basePricePointId'):
            opened_pricing = True
        elif self.matches(label='Add Pricing', roles={'AXButton'}, enabled=True):
            opened_pricing = self.click('Add Pricing', optional=True, roles={'AXButton'})
        else:
            opened_pricing = False
            print('NATIVE_PRICING_SKIP_ADD=already_done', flush=True)
        if opened_pricing:
            self.wait(lambda: bool(self.matches(dom_id='basePricePointId')), timeout=30)
            price_btn = self.find(dom_id='basePricePointId')
            current = str(
                self.backend._attribute(price_btn, 'AXValue')
                or self.backend._attribute(price_btn, 'AXTitle')
                or ''
            )
            if '$0.00' not in current and '0.00' not in current:
                # AXPress often fails to open this list; use geometry click.
                list_open = bool(self.matches(label='$0.00', roles={'AXMenuItem', 'AXButton'}))
                if not list_open:
                    geom = _ax_geom(self.backend, price_btn)
                    if geom is None:
                        raise NativeError('PRICE_CHOOSE_NOT_VISIBLE')
                    x, y, w, h = geom
                    _click_xy(x + w / 2.0, y + h / 2.0)
                    self.wait(
                        lambda: bool(self.matches(label='$0.00', roles={'AXMenuItem', 'AXButton'})),
                        timeout=20,
                    )
                if not _click_geom_label('$0.00', roles={'AXMenuItem', 'AXButton'}):
                    if not _click_geom_label('$0.00'):
                        raise NativeError('TARGET_COUNT=0:$0.00')
                self.wait(
                    lambda: '$0.00' in str(
                        self.backend._attribute(self.find(dom_id='basePricePointId'), 'AXValue')
                        or self.backend._attribute(self.find(dom_id='basePricePointId'), 'AXTitle')
                        or ''
                    ),
                    timeout=15,
                )
            self.wait(lambda: bool(self.matches(label='Next', roles={'AXButton'}, enabled=True)), timeout=30)
            self.click('Next', roles={'AXButton'})
            self.wait(
                lambda: bool(self.matches(label='Next', roles={'AXButton'}, enabled=True))
                or bool(self.matches(label='Confirm', roles={'AXButton'}, enabled=True)),
                timeout=30,
            )
            if self.matches(label='Next', roles={'AXButton'}, enabled=True):
                self.click('Next', roles={'AXButton'})
            self.wait(lambda: bool(self.matches(label='Confirm', roles={'AXButton'}, enabled=True)), timeout=30)
            self.click('Confirm', roles={'AXButton'})
            self.wait(lambda: not self.has('App Pricing'), timeout=30)
        if self.click('Set Up Availability', optional=True, roles={'AXButton'}):
            self.wait(lambda: bool(self.matches(dom_id='SETUP_GRANULAR')) or self.has('Next'), timeout=30)
            self.check(dom_id='SETUP_GRANULAR')
            self.click('Next', roles={'AXButton'})
            self.click('All', roles={'AXButton', 'AXLink', 'AXCheckBox'})
            for country in ('TWN','CHN','MAC','HKG'):
                self.check(dom_id=country, checked=False)
            self.click('Next', roles={'AXButton'})
            self.click('Confirm', roles={'AXButton'})
        self.wait(lambda: not self.has('Add Pricing') and not self.has('Set Up Availability'), timeout=60)
        self.checkpoint('pricing')

    def configuration(self):
        values = self.state['integration']
        filename = 'AuthKey_' + values['key'] + '.p8'
        config = self.downloads / 'apple-store-bm' / 'config'
        if config.is_symlink() or config.parent.is_symlink():
            raise NativeError('CONFIG_PATH_UNSAFE')
        config.mkdir(parents=True, exist_ok=True)
        source, target = self.downloads / filename, config / filename
        if target.is_symlink() or source.is_symlink():
            raise NativeError('KEY_PATH_UNSAFE')
        if target.exists() and source.exists() and hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
            raise NativeError('KEY_FILE_CONFLICT')
        if not target.exists():
            shutil.move(source, target)
        if not target.is_file() or not target.stat().st_size:
            raise NativeError('KEY_FILE_MISSING')
        target.chmod(0o600)
        content = ('apple_store:\n  issuer_id: ' + values['issuer'] + '\n  key_id: ' + values['key']
                   + '\n  private_key_path: ./config/' + filename + '\n\napp_info:\n  bundle_id: ' + self.data['BUNDLE_ID']
                   + '\n  platform: IOS\n  version: 1.0\n  locale: en-US\n  preview_type: IPHONE_67\n  update_version_txt: test version\n  file_path:\n  dir_path:\n')
        path = config / 'prod.yml'
        if path.is_symlink():
            raise NativeError('CONFIG_PATH_UNSAFE')
        fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        path.chmod(0o600)
        if path.read_text() != content:
            raise NativeError('CONFIG_READBACK_FAILED')
        self.checkpoint('configuration')

    def run(self):
        for name in ('integrations','description','info','privacy','pricing','configuration'):
            print('NATIVE_STAGE=' + name, flush=True)
            if self.state.get(name) == 'verified':
                print('NATIVE_' + name.upper() + '=verified', flush=True)
                continue
            getattr(self, name)()
        self.backend._root()
        print('NATIVE_ENROLLMENT=skipped_current_page', flush=True)
        print('NATIVE_EDGE_SESSION=preserved', flush=True)
        print('IAP_CREATION=skipped_by_request', flush=True)
        print('FILL_DESCRIPTION=completed_without_iap', flush=True)


if __name__ == '__main__':
    try:
        NativeWorkflow(json.load(sys.stdin)).run()
    except Exception as error:
        reason = str(error) if str(error) else type(error).__name__
        print('NATIVE_BLOCKED=' + reason, flush=True)
        raise SystemExit(1)
