"""
MeGaADesk - authenticated encryption, pure stdlib (hashlib only).

No AES in the standard library, so we build an authenticated stream cipher from
HMAC-SHA256:

  * Key derivation:  PBKDF2-HMAC-SHA256(password, salt) -> 64 bytes,
                     split into a 32-byte encryption key and a 32-byte MAC key.
  * Cipher:          HMAC-SHA256 in counter mode is a secure pseudo-random
                     generator; we XOR its keystream with the plaintext.
  * Authentication:  Encrypt-then-MAC. Tag = HMAC-SHA256(mac_key, nonce||ct).
                     A wrong password (or any tampering by the relay) makes the
                     tag check fail, so open() raises and the peer is rejected.

This gives confidentiality + integrity + password authentication with zero
third-party dependencies. It is NOT forward-secret (the session key comes only
from the password); an ephemeral Diffie-Hellman upgrade is a planned follow-up.
"""
import hashlib
import hmac
import os
import struct

PBKDF2_ROUNDS = 200_000
KEY_LEN = 32
NONCE_LEN = 16
TAG_LEN = 32
SALT_LEN = 16


def new_salt():
    return os.urandom(SALT_LEN)


def derive_keys(password, salt):
    """password: str -> (enc_key, mac_key), each 32 bytes."""
    if isinstance(password, str):
        password = password.encode("utf-8")
    material = hashlib.pbkdf2_hmac("sha256", password, salt, PBKDF2_ROUNDS, dklen=KEY_LEN * 2)
    return material[:KEY_LEN], material[KEY_LEN:]


def _keystream(enc_key, nonce, length):
    """HMAC-SHA256 counter-mode keystream of the requested length."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(enc_key, nonce + struct.pack(">Q", counter), hashlib.sha256).digest()
        out += block
        counter += 1
    return bytes(out[:length])


def _xor(data, keystream):
    """XOR two equal-length byte strings at C speed via big integers."""
    if not data:
        return b""
    return (int.from_bytes(data, "big") ^ int.from_bytes(keystream, "big")).to_bytes(len(data), "big")


def seal(enc_key, mac_key, plaintext):
    """Return nonce || ciphertext || tag."""
    nonce = os.urandom(NONCE_LEN)
    ct = _xor(plaintext, _keystream(enc_key, nonce, len(plaintext)))
    tag = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    return nonce + ct + tag


def open(enc_key, mac_key, blob):
    """Verify and decrypt. Raises ValueError on a bad tag / wrong password."""
    if len(blob) < NONCE_LEN + TAG_LEN:
        raise ValueError("ciphertext too short")
    nonce = blob[:NONCE_LEN]
    ct = blob[NONCE_LEN:-TAG_LEN]
    tag = blob[-TAG_LEN:]
    expected = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("authentication failed (wrong password or tampering)")
    return _xor(ct, _keystream(enc_key, nonce, len(ct)))


if __name__ == "__main__":
    salt = new_salt()
    ek, mk = derive_keys("hunter2", salt)
    msg = b"the quick brown fox" * 1000
    blob = seal(ek, mk, msg)
    assert open(ek, mk, blob) == msg
    # wrong password fails
    ek2, mk2 = derive_keys("wrong", salt)
    try:
        open(ek2, mk2, blob)
        print("FAIL: wrong password accepted")
    except ValueError:
        print("ok: wrong password rejected")
    # tamper fails
    bad = bytearray(blob); bad[NONCE_LEN] ^= 1
    try:
        open(ek, mk, bytes(bad))
        print("FAIL: tamper accepted")
    except ValueError:
        print("ok: tamper rejected")
    print("ok: roundtrip + auth")
