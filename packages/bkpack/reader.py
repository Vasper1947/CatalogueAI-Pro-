"""Read a BK-PACK ZIP back into its evidence rows and media."""

import json
import zipfile

from .spec import MEDIA_DIR


def read_bkpack(path: str) -> dict:
    with zipfile.ZipFile(path, "r") as zf:
        datapackage = json.loads(zf.read("datapackage.json"))
        evidence = [
            json.loads(line)
            for line in zf.read("evidence.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
        prefix = f"{MEDIA_DIR}/"
        media = {
            name[len(prefix):]: zf.read(name)
            for name in zf.namelist()
            if name.startswith(prefix)
        }
    return {"datapackage": datapackage, "evidence": evidence, "media": media}
