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
import socket
import struct
import subprocess

# the service the Sony app connects to, newer then older generation
SERVICE_UUIDS = ("956C7B26-D49A-4BA8-B03F-B17D393CB6E2",
                 "96CC203E-5068-46AD-B32D-E316F5E069BA")

MODES = ("nc", "ambient", "off")
AMBIENT_LEVEL = 20            # 1..20, how much of the outside is let in

HEADER, TRAILER, ESCAPE = 0x3E, 0x3C, 0x3D
T_ACK, T_COMMAND = 0x01, 0x0C
TIMEOUT = 4.0


class SonyError(Exception):
    """Something the listener should be told, in words."""


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


def find_headphones(host_command) -> list[dict]:
    try:
        text = subprocess.run(host_command(["pw-dump"]), capture_output=True,
                              text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return bluetooth_outputs(text)


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
    except OSError:
        return None
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
    if not available():
        raise SonyError("no_bluetooth")
    channel = None
    for uuid in SERVICE_UUIDS:
        channel = rfcomm_channel(address, uuid)
        if channel:
            break
    if not channel:
        raise SonyError("not_sony")
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                      socket.BTPROTO_RFCOMM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((address, channel))
    except OSError:
        s.close()
        raise SonyError("connect_failed")
    session = _Session(s)
    try:
        session.init()
    except (OSError, SonyError):
        s.close()
        raise SonyError("connect_failed")
    return session


def set_payload(version: int, mode: str) -> bytes:
    """The ambient-sound-control command. v2 as the WH-1000XM5 takes it
    (Gadgetbridge's form without wind-noise support, which the XM5 lacks);
    v1 as the WH-1000XM3/XM4 take it (with it)."""
    on = mode != "off"
    if version == 2:
        return bytes([0x68, 0x15, 0x01, 0x01 if on else 0x00,
                      0x01 if mode == "ambient" else 0x00,
                      0x00, AMBIENT_LEVEL])
    return bytes([0x68, 0x02, 0x11 if on else 0x00, 0x02,
                  0x02 if mode == "nc" else 0x00, 0x01, 0x00,
                  0x00 if mode == "nc" else AMBIENT_LEVEL])


def parse_mode(version: int, payload: bytes) -> str | None:
    """The mode from the headphones' reply (v2 only; v1's is not known)."""
    if version != 2 or len(payload) < 5 or payload[1] not in (0x15, 0x17):
        return None
    if payload[3] == 0x00:
        return "off"
    return {0x00: "nc", 0x01: "ambient"}.get(payload[4])


def get_mode(address: str) -> str | None:
    session = _open(address)
    try:
        if session.version != 2:
            return None
        reply = session.request(bytes([0x66, 0x15]), want=0x67)
        return parse_mode(2, reply or b"")
    except (OSError, SonyError):
        raise SonyError("connect_failed")
    finally:
        session.sock.close()


def set_mode(address: str, mode: str):
    if mode not in MODES:
        raise ValueError(mode)
    session = _open(address)
    try:
        session.request(set_payload(session.version, mode))
    except (OSError, SonyError):
        raise SonyError("connect_failed")
    finally:
        session.sock.close()
