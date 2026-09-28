"""Noise cancelling on Sony headphones (WH-1000XM5 and relatives).

Sony's headphones take commands over a Bluetooth RFCOMM channel of their
own, the one their phone app uses. The protocol is not published; what is
here follows how Gadgetbridge, the open-source Android companion app, talks
to them (Freeyourgadget/Gadgetbridge, service/devices/sony/headphones --
its Message, SonyHeadphonesProtocol and SonyProtocolImplV1/V2), rewritten
from that description for this one feature. Nothing but Python's own socket
module is needed:

* The channel number is not fixed, so it is asked of the headphones' SDP
  server (L2CAP PSM 1) by the service's UUID -- one request and reply,
  written out here rather than depending on libbluetooth.
* A frame is 0x3E, then escaped [type, sequence, 4-byte length, payload,
  checksum], then 0x3C. The checksum is the byte sum of type..payload;
  0x3C/0x3D/0x3E inside are sent as 0x3D followed by the byte & 0xEF.
* Every command is answered with an ACK carrying the next sequence number,
  and every command the headphones send must be ACKed the same way.
* The session starts with an init command; the length of its reply tells
  the protocol version: 4 bytes v1 (WH-1000XM3/XM4 era), 8 bytes v2
  (WH-1000XM5, WF-1000XM4/XM5, LinkBuds).

Blocking and slow (seconds) by nature: call it from a background thread.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import time

# the service the Sony app connects to, newer then older generation
SERVICE_UUIDS = ("956C7B26-D49A-4BA8-B03F-B17D393CB6E2",
                 "96CC203E-5068-46AD-B32D-E316F5E069BA")

MODES = ("nc", "ambient", "off")
# Ambient sound's strength, how much of the outside is let in: 1..20, as
# in Sony's app. Noise cancelling has no strength in the protocol (nor in
# Sony's app, for the WH-1000XM5): the headphones set it themselves.
AMBIENT_MIN, AMBIENT_MAX = 1, 20
AMBIENT_LEVEL = 20

HEADER, TRAILER, ESCAPE = 0x3E, 0x3C, 0x3D
T_ACK, T_COMMAND = 0x01, 0x0C
TIMEOUT = 6.0
# The channel a pair of headphones answered on, so it is looked up once.
_channels: dict[str, int] = {}


# What happened on each attempt, for when the headphones cannot be reached
# (see log); kept small.
LOG_PATH = os.path.expanduser("~/.local/share/spatiallinux/noise-cancelling.log")
LOG_MAX = 64 * 1024


def log(message: str):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX:
            os.replace(LOG_PATH, LOG_PATH + ".old")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
    except OSError:
        pass


class SonyError(Exception):
    """Something the listener should be told, in words. str() is the code
    ("connect_failed", ...); `detail` says what the system reported, for a
    tooltip."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.detail = detail


def available() -> bool:
    return all(hasattr(socket, n) for n in
               ("AF_BLUETOOTH", "BTPROTO_RFCOMM", "BTPROTO_L2CAP"))


# -- which headphones ------------------------------------------------------
def bluetooth_outputs(pw_dump_text: str) -> list[dict]:
    """[{address, name}] of the Bluetooth audio outputs PipeWire knows."""
    try:
        objects, _ = json.JSONDecoder().raw_decode(pw_dump_text)
    except (json.JSONDecodeError, ValueError):
        return []
    out, seen = [], set()
    for o in objects if isinstance(objects, list) else []:
        props = (o.get("info") or {}).get("props") or {}
        addr = props.get("api.bluez5.address")
        if not addr or addr in seen:
            continue
        if o.get("type") == "PipeWire:Interface:Node" and \
                props.get("media.class") != "Audio/Sink":
            continue
        seen.add(addr)
        out.append({"address": addr,
                    "name": props.get("device.description")
                    or props.get("node.description") or addr})
    return out


def looks_like_sony(name: str) -> bool:
    """Sony's own model names (WH-1000XM5, WF-1000XM4, LinkBuds, ...)."""
    import re
    return bool(re.search(r"\b(WH|WF|WI|MDR)-|LinkBuds|\bSony\b", name or "",
                          re.IGNORECASE))


def find_headphones(host_command) -> list[dict]:
    try:
        text = subprocess.run(host_command(["pw-dump"]), capture_output=True,
                              text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"pw-dump failed: {e}")
        return []
    found = bluetooth_outputs(text)
    log("bluetooth outputs: " + (", ".join(f"{d['name']} [{d['address']}]"
                                            for d in found) or "none"))
    return found


# -- SDP: which RFCOMM channel ---------------------------------------------
def _uuid128(text: str) -> bytes:
    return bytes.fromhex(text.replace("-", ""))


def _element(data: bytes, i: int):
    """(type, value, next index) of the SDP data element at i. Sequences
    come back as lists of (type, value)."""
    head = data[i]
    kind, size = head >> 3, head & 7
    i += 1
    if kind == 0:
        return 0, None, i
    if size < 5:
        length = (1, 2, 4, 8, 16)[size]
    else:
        n = (1, 2, 4)[size - 5]
        length = int.from_bytes(data[i:i + n], "big")
        i += n
    body = data[i:i + length]
    if kind in (6, 7):                       # sequence / alternative
        items, j = [], 0
        while j < len(body):
            k, v, j = _element(body, j)
            items.append((k, v))
        return kind, items, i + length
    if kind == 1:
        return kind, int.from_bytes(body, "big"), i + length
    return kind, body, i + length


BASE_UUID_TAIL = bytes.fromhex("00001000800000805F9B34FB")


def _is_rfcomm(v) -> bool:
    """The RFCOMM protocol UUID (0x0003), in any of its three sizes."""
    if not isinstance(v, bytes):
        return False
    return (v == b"\x00\x03" or v == b"\x00\x00\x00\x03"
            or (len(v) == 16 and v[:4] == b"\x00\x00\x00\x03"
                and v[4:] == BASE_UUID_TAIL))


def _rfcomm_in(value) -> int | None:
    """The RFCOMM channel in a ProtocolDescriptorList (or part of one):
    the uint following the RFCOMM UUID 0x0003."""
    if not isinstance(value, list):
        return None
    for idx, (kind, v) in enumerate(value):
        if kind == 3 and _is_rfcomm(v) \
                and idx + 1 < len(value) and value[idx + 1][0] == 1:
            return value[idx + 1][1]
        found = _rfcomm_in(v)
        if found:
            return found
    return None


def rfcomm_channel(address: str, uuid: str) -> int | None:
    """Ask the headphones' SDP server where `uuid` is (ServiceSearchAttribute
    request for its ProtocolDescriptorList, attribute 0x0004)."""
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET,
                      socket.BTPROTO_L2CAP)
    s.settimeout(TIMEOUT)
    try:
        s.connect((address, 1))
        pattern = b"\x35\x11\x1c" + _uuid128(uuid)
        attrs = b"\x35\x03\x09\x00\x04"
        collected, cont, tid = b"", b"\x00", 1
        while True:
            params = pattern + b"\x04\x00" + attrs + cont
            s.send(struct.pack(">BHH", 0x06, tid, len(params)) + params)
            reply = s.recv(4096)
            if len(reply) < 7 or reply[0] != 0x07:
                return None
            count = int.from_bytes(reply[5:7], "big")
            collected += reply[7:7 + count]
            cont = reply[7 + count:] or b"\x00"
            tid += 1
            if cont[0] == 0:
                break
        if not collected:
            return None
        _k, lists, _ = _element(collected, 0)
        return _rfcomm_in(lists)
    except OSError as e:
        # not "no such service": the headphones did not answer at all, which
        # is worth trying again rather than taking them for another make
        log(f"{address}: SDP for {uuid[:8]} failed: {e}")
        raise SonyError("connect_failed", f"SDP: {e}")
    finally:
        s.close()


# -- framing ---------------------------------------------------------------
def encode(kind: int, seq: int, payload: bytes) -> bytes:
    body = bytes([kind, seq]) + struct.pack(">I", len(payload)) + payload
    body += bytes([sum(body) & 0xFF])
    out = bytearray([HEADER])
    for b in body:
        if b in (HEADER, TRAILER, ESCAPE):
            out += bytes([ESCAPE, b & 0xEF])
        else:
            out.append(b)
    out.append(TRAILER)
    return bytes(out)


def decode(frame: bytes):
    """(type, seq, payload) of one frame (0x3E..0x3C), or None if bad."""
    raw, i = bytearray(), 1
    while i < len(frame) - 1:
        b = frame[i]
        if b == ESCAPE and i + 1 < len(frame) - 1:
            i += 1
            b = frame[i] | 0x10
        raw.append(b)
        i += 1
    if len(raw) < 7 or (sum(raw[:-1]) & 0xFF) != raw[-1]:
        return None
    length = int.from_bytes(raw[2:6], "big")
    if length != len(raw) - 7:
        return None
    return raw[0], raw[1], bytes(raw[6:-1])


class _Session:
    def __init__(self, sock):
        self.sock = sock
        self.buf = b""
        self.seq = 0
        self.version = None

    def _frames(self):
        while True:
            start = self.buf.find(bytes([HEADER]))
            end = self.buf.find(bytes([TRAILER]), start + 1)
            if start >= 0 and end > start:
                frame, self.buf = self.buf[start:end + 1], self.buf[end + 1:]
                msg = decode(frame)
                if msg:
                    return msg
                continue
            chunk = self.sock.recv(1024)
            if not chunk:
                raise SonyError("disconnected")
            self.buf += chunk

    def request(self, payload: bytes, want: int | None = None) -> bytes | None:
        """Send a command, wait for its ACK, and -- with `want` -- for the
        headphones' command whose payload starts with that byte."""
        self.sock.send(encode(T_COMMAND, self.seq, payload))
        acked, answer = False, None
        while not acked or (want is not None and answer is None):
            kind, seq, body = self._frames()
            if kind == T_ACK:
                self.seq = seq
                acked = True
            else:
                self.sock.send(encode(T_ACK, 1 - seq, b""))
                if want is not None and body and body[0] == want:
                    answer = body
        return answer

    def init(self):
        reply = self.request(b"\x00\x00", want=0x01)
        self.version = 1 if len(reply) == 4 else 2


def _open(address: str) -> _Session:
    """A session, tried twice: with two devices connected (the headphones'
    multipoint) the first attempt sometimes finds them busy."""
    try:
        return _open_once(address)
    except SonyError as e:
        if str(e) != "connect_failed":
            raise
        _channels.pop(address, None)
        import time
        time.sleep(0.8)
        return _open_once(address)


def _open_once(address: str) -> _Session:
    if not available():
        raise SonyError("no_bluetooth")
    channel = _channels.get(address)
    if not channel:
        for uuid in SERVICE_UUIDS:
            channel = rfcomm_channel(address, uuid)
            if channel:
                break
    if not channel:
        log(f"{address}: no Sony service found")
        raise SonyError("not_sony")
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                      socket.BTPROTO_RFCOMM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((address, channel))
    except OSError as e:
        s.close()
        log(f"{address}: RFCOMM {channel} connect failed: {e}")
        raise SonyError("connect_failed", f"RFCOMM {channel}: {e}")
    session = _Session(s)
    try:
        session.init()
    except (OSError, SonyError) as e:
        s.close()
        log(f"{address}: init failed on channel {channel}: {e!r}")
        raise SonyError("connect_failed", f"init: {str(e) or type(e).__name__}")
    _channels[address] = channel
    log(f"{address}: connected on channel {channel}, protocol v{session.version}")
    return session


def set_payload(version: int, mode: str, level: int = AMBIENT_LEVEL,
                voice: bool = False) -> bytes:
    """The ambient-sound-control command. v2 as the WH-1000XM5 takes it
    (Gadgetbridge's form without wind-noise support, which the XM5 lacks);
    v1 as the WH-1000XM3/XM4 take it (with it)."""
    on = mode != "off"
    level = max(AMBIENT_MIN, min(AMBIENT_MAX, int(level)))
    focus = 0x01 if voice else 0x00
    if version == 2:
        return bytes([0x68, 0x15, 0x01, 0x01 if on else 0x00,
                      0x01 if mode == "ambient" else 0x00,
                      focus, level])
    return bytes([0x68, 0x02, 0x11 if on else 0x00, 0x02,
                  0x02 if mode == "nc" else 0x00, 0x01, focus,
                  0x00 if mode == "nc" else level])


def parse_mode(version: int, payload: bytes) -> str | None:
    """The mode from the headphones' reply (v2 only; v1's is not known)."""
    return parse_state(version, payload).get("mode")


def parse_state(version: int, payload: bytes) -> dict:
    """{mode, level, voice} from the headphones' reply, as much as can be
    read (v2 only). The layout is the set command's: on, ambient, focus on
    voice, level."""
    if version != 2 or len(payload) < 5 or payload[1] not in (0x15, 0x17):
        return {}
    if payload[3] == 0x00:
        mode = "off"
    else:
        mode = {0x00: "nc", 0x01: "ambient"}.get(payload[4])
    state = {"mode": mode}
    if payload[1] == 0x15 and len(payload) >= 7:
        state["voice"] = payload[5] == 0x01
        if AMBIENT_MIN <= payload[6] <= AMBIENT_MAX:
            state["level"] = payload[6]
    return state


def get_state(address: str) -> dict:
    """{mode, level, voice} as the headphones report them ({} if they use
    the older protocol, whose reply is not known)."""
    session = _open(address)
    try:
        if session.version != 2:
            return {}
        reply = session.request(bytes([0x66, 0x15]), want=0x67)
        return parse_state(2, reply or b"")
    except (OSError, SonyError) as e:
        log(f"{address}: reading the mode failed: {e!r}")
        raise SonyError("connect_failed", f"read: {str(e) or type(e).__name__}")
    finally:
        session.sock.close()


def get_mode(address: str) -> str | None:
    return get_state(address).get("mode")


def set_mode(address: str, mode: str, level: int = AMBIENT_LEVEL,
             voice: bool = False):
    if mode not in MODES:
        raise ValueError(mode)
    session = _open(address)
    try:
        session.request(set_payload(session.version, mode, level, voice))
    except (OSError, SonyError) as e:
        log(f"{address}: setting {mode} failed: {e!r}")
        raise SonyError("connect_failed", f"set: {str(e) or type(e).__name__}")
    finally:
        session.sock.close()
