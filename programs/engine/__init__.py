"""Program 3 — the engine.

Detects which BK template a BK-PACK's evidence best matches (against the parsed
packages/schemas store) and populates that template's writable fields from the
evidence — flagging every field with no evidence as needs_input rather than
fabricating a value.

Floor Price is never populated here: it is a manual BK-management pricing step
with no source in extracted data, surfaced as a fixed pending gate so a
"ready_for_review" result is never mistaken for upload-ready.
"""
