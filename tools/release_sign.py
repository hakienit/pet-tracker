"""Ký SHA256SUMS.txt của release bằng Ed25519; app kiểm chữ ký bằng khoá công khai trong pet_tracker/updater.py.

  python tools/release_sign.py keygen <file khoá bí mật>   # tạo cặp khoá, in khoá công khai (chỉ làm một lần)
  python tools/release_sign.py sign <file>                 # ghi <file>.sig; khoá bí mật (hex) lấy từ env WISP_SIGNING_KEY
  python tools/release_sign.py verify <file>               # kiểm <file>.sig bằng khoá công khai trong app

Khoá bí mật để ngoài repo; trên GitHub nó là secret WISP_SIGNING_KEY của repo.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pet_tracker import ed25519  # noqa: E402
from pet_tracker.updater import SIGNING_PUBLIC_KEY  # noqa: E402


def main(argv):
    if len(argv) != 2 or argv[0] not in ("keygen", "sign", "verify"):
        print(__doc__)
        return 2
    cmd, target = argv[0], Path(argv[1])
    if cmd == "keygen":
        if target.exists():
            print(f"{target} đã có, không ghi đè")
            return 1
        sk = secrets.token_bytes(32)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(sk.hex() + "\n", encoding="ascii")
        print("khoá bí mật:", target)
        print("khoá công khai:", ed25519.public_key(sk).hex())
        return 0
    sig_path = target.with_name(target.name + ".sig")
    if cmd == "sign":
        key = os.environ.get("WISP_SIGNING_KEY", "").strip()
        if len(key) != 64:
            print("thiếu WISP_SIGNING_KEY (64 ký tự hex)")
            return 1
        sk = bytes.fromhex(key)
        if ed25519.public_key(sk).hex() != SIGNING_PUBLIC_KEY:
            print("WISP_SIGNING_KEY không khớp khoá công khai trong pet_tracker/updater.py")
            return 1
        sig_path.write_text(ed25519.sign(sk, target.read_bytes()).hex() + "\n", encoding="ascii")
        print("đã ký:", sig_path)
        return 0
    ok = ed25519.verify(bytes.fromhex(SIGNING_PUBLIC_KEY), target.read_bytes(),
                        bytes.fromhex(sig_path.read_text(encoding="ascii").strip()))
    print("chữ ký hợp lệ" if ok else "CHỮ KÝ SAI")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
