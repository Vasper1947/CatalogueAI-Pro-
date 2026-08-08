"""package_for_upload: builds the real ZIP shape BK's Instructions sheet
states (xlsx at root + media/ folder) and programmatically verifies every
media-column filename in a REAL written xlsx against what's actually
supplied — never assumed."""

import zipfile

from engine.populate import FieldResult, PopulationResult
from engine.writer import write_template, write_template_batch
from export.upload import package_for_upload


def _schema():
    return {
        "zip_category": "Test Category",
        "filename": "test.xlsx",
        "category_path": ["Test Category", "Widget"],
        "fields": [
            {
                "name": "Brand", "column": "A", "type": "dropdown", "required": True,
                "conditional": False, "locked": False, "is_formula": False,
                "section": "Info", "dropdown_source": "inline", "vocabulary": ["Acme"],
            },
            {
                "name": "Cover Image", "column": "B", "type": "string", "required": False,
                "conditional": False, "locked": False, "is_formula": False,
                "section": "Media", "dropdown_source": None, "vocabulary": [],
            },
            {
                "name": "Other Images", "column": "C", "type": "string", "required": False,
                "conditional": False, "locked": False, "is_formula": False,
                "section": "Media", "dropdown_source": None, "vocabulary": [],
            },
        ],
        "lookups": {"Brand": ["Acme"]},
        "instructions": {
            "raw_lines": [
                "Generated for:", "Test Category > Widget",
                ("8. For media fields: place files in a \"media/\" folder, "
                 "ZIP together with this .xlsx file, and upload the .zip."),
                "9. Alternatively, enter direct URLs for media files.",
                "up to 500 products",
            ],
            "row_limit": 500,
        },
    }


def _pop(cover, other):
    fields = [
        FieldResult(name="Brand", required=True, status="populated", value="Acme"),
        FieldResult(name="Cover Image", required=False,
                    status="populated" if cover else "needs_input", value=cover),
        FieldResult(name="Other Images", required=False,
                    status="populated" if other else "needs_input", value=other),
    ]
    return PopulationResult(
        category_path=["Test Category", "Widget"], fields=fields, status="incomplete",
        missing_required=[], populated_count=0, needs_input_count=0,
    )


def test_referenced_media_files_are_packaged_with_no_gaps(tmp_path):
    schema = _schema()
    pop = _pop("p1_cover.webp", "p1_0.webp,p1_1.webp")
    xlsx = tmp_path / "out.xlsx"
    write_template(pop, schema, xlsx)

    media_files = {
        "p1_cover.webp": b"cover-bytes",
        "p1_0.webp": b"img0-bytes",
        "p1_1.webp": b"img1-bytes",
    }
    out_zip = tmp_path / "upload.zip"

    result = package_for_upload(xlsx, media_files, out_zip)

    assert result.missing_media == []
    assert result.unreferenced_media == []
    assert set(result.media_written) == set(media_files)

    with zipfile.ZipFile(out_zip) as zf:
        names = set(zf.namelist())
        assert "out.xlsx" in names
        assert "media/p1_cover.webp" in names
        assert "media/p1_0.webp" in names
        assert "media/p1_1.webp" in names
        assert zf.read("media/p1_cover.webp") == b"cover-bytes"


def test_missing_media_file_is_reported_not_assumed(tmp_path):
    schema = _schema()
    pop = _pop("p1_cover.webp", None)
    xlsx = tmp_path / "out.xlsx"
    write_template(pop, schema, xlsx)

    out_zip = tmp_path / "upload.zip"
    result = package_for_upload(xlsx, {}, out_zip)  # nothing supplied

    assert result.missing_media == ["p1_cover.webp"]
    # The ZIP is still built -- a missing media file doesn't withhold the
    # otherwise-good xlsx data.
    with zipfile.ZipFile(out_zip) as zf:
        assert "out.xlsx" in zf.namelist()


def test_unreferenced_supplied_media_is_reported_and_still_included(tmp_path):
    schema = _schema()
    pop = _pop("p1_cover.webp", None)
    xlsx = tmp_path / "out.xlsx"
    write_template(pop, schema, xlsx)

    media_files = {"p1_cover.webp": b"cover", "extra_unused.webp": b"extra"}
    out_zip = tmp_path / "upload.zip"
    result = package_for_upload(xlsx, media_files, out_zip)

    assert result.unreferenced_media == ["extra_unused.webp"]
    assert result.missing_media == []
    with zipfile.ZipFile(out_zip) as zf:
        assert "media/extra_unused.webp" in zf.namelist()  # kept, not dropped


def test_direct_url_media_value_is_not_treated_as_a_missing_local_file(tmp_path):
    # Instructions point 9: a direct URL is a valid alternative to a local
    # media/ file -- must not be flagged as "missing".
    schema = _schema()
    pop = _pop("https://example.com/cover.jpg", None)
    xlsx = tmp_path / "out.xlsx"
    write_template(pop, schema, xlsx)

    out_zip = tmp_path / "upload.zip"
    result = package_for_upload(xlsx, {}, out_zip)

    assert result.missing_media == []


def test_batch_file_media_references_checked_across_every_row(tmp_path):
    schema = _schema()
    pops = [_pop("p1_cover.webp", None), _pop("p2_cover.webp", None)]
    xlsx = tmp_path / "batch.xlsx"
    write_template_batch(pops, schema, xlsx)

    media_files = {"p1_cover.webp": b"a", "p2_cover.webp": b"b"}
    out_zip = tmp_path / "upload.zip"
    result = package_for_upload(xlsx, media_files, out_zip)

    assert result.missing_media == []
    assert result.unreferenced_media == []


def test_no_media_at_all_is_a_clean_empty_result(tmp_path):
    schema = _schema()
    pop = _pop(None, None)
    xlsx = tmp_path / "out.xlsx"
    write_template(pop, schema, xlsx)

    out_zip = tmp_path / "upload.zip"
    result = package_for_upload(xlsx, {}, out_zip)

    assert result.missing_media == []
    assert result.unreferenced_media == []
    assert result.media_written == []
