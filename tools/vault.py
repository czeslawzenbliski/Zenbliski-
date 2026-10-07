"""Szyfrowanie galerii chronionych hasłem.

Repozytorium i strona są publiczne, więc zdjęcia z takiej galerii leżą na
serwerze wyłącznie w postaci zaszyfrowanej. Odszyfrowuje je przeglądarka po
wpisaniu hasła (docs/assets/site.js, funkcja initVault).

Układ katalogu docs/zdjecia/<galeria>/ dla galerii chronionej:

    lock.json     sól, liczba iteracji, klucz danych zaszyfrowany kluczem z hasła
                  oraz zaszyfrowany manifest (lista zdjęć, wymiary, podpisy)
    <losowe>.bin  zaszyfrowane zdjęcia i miniatury; nazwy nic nie mówią o treści

Kryptografia: klucz z hasła przez PBKDF2-HMAC-SHA256, dane szyfrowane AES-256-GCM.
Każdy zaszyfrowany blok to 12 bajtów losowej wartości jednorazowej i szyfrogram.
Klucz danych jest losowy, a hasło szyfruje tylko ten klucz.

Hasła nie wolno zapisywać w repozytorium ani w plikach projektu.
Siła ochrony zależy wyłącznie od hasła: zaszyfrowane pliki są publiczne, więc
każdy może zgadywać hasło u siebie bez ograniczeń. Kilka przypadkowych słów
wystarcza, kilka cyfr nie.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import unicodedata
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

LOCK_FILE = "lock.json"
ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 12


class WrongPassword(Exception):
    pass


def normalize(password: str) -> str:
    """Ta sama normalizacja co w przeglądarce: NFC i bez spacji na końcach."""
    return unicodedata.normalize("NFC", password).strip()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _kek(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(normalize(password).encode("utf-8"))


def seal(key: bytes, plain: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plain, None)


def unseal(key: bytes, blob: bytes) -> bytes:
    return AESGCM(key).decrypt(blob[:12], blob[12:], None)


def is_locked(gallery_dir: Path) -> bool:
    return (gallery_dir / LOCK_FILE).exists()


def random_name() -> str:
    return secrets.token_hex(8) + ".bin"


def create(gallery_dir: Path, password: str) -> tuple[bytes, list[dict]]:
    """Zakłada nową chronioną galerię. Zwraca klucz danych i pusty manifest."""
    if len(normalize(password)) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Hasło jest za krótkie (minimum {MIN_PASSWORD_LENGTH} znaków). "
            "Zaszyfrowane pliki są publiczne, więc krótkie hasło da się zgadnąć."
        )
    gallery_dir.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(16)
    data_key = AESGCM.generate_key(bit_length=256)
    lock = {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iter": ITERATIONS,
        "salt": _b64(salt),
        "key": _b64(seal(_kek(password, salt, ITERATIONS), data_key)),
    }
    _write(gallery_dir, lock, data_key, [])
    return data_key, []


def unlock(gallery_dir: Path, password: str) -> tuple[bytes, list[dict]]:
    """Otwiera istniejącą chronioną galerię. Zwraca klucz danych i manifest."""
    lock = json.loads((gallery_dir / LOCK_FILE).read_text(encoding="utf-8"))
    kek = _kek(password, base64.b64decode(lock["salt"]), lock["iter"])
    try:
        data_key = unseal(kek, base64.b64decode(lock["key"]))
    except InvalidTag:
        raise WrongPassword("Hasło do tej galerii jest nieprawidłowe.") from None
    manifest = json.loads(unseal(data_key, base64.b64decode(lock["manifest"])))
    return data_key, manifest


def save_manifest(gallery_dir: Path, data_key: bytes, manifest: list[dict]) -> None:
    lock = json.loads((gallery_dir / LOCK_FILE).read_text(encoding="utf-8"))
    _write(gallery_dir, lock, data_key, manifest)


def _write(gallery_dir: Path, lock: dict, data_key: bytes, manifest: list[dict]) -> None:
    plain = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    lock["manifest"] = _b64(seal(data_key, plain))
    (gallery_dir / LOCK_FILE).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
