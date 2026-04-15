from backend.generator.svg_to_pptx.builder import _ensure_unique_media_names


def test_ensure_unique_media_names_renames_cross_slide_conflicts():
    used = {"image1.png"}
    media_files = {"image1.png": b"new-image"}
    rel_entries = [
        {
            "id": "rId2",
            "type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
            "target": "../media/image1.png",
        }
    ]

    renamed_media, renamed_rels = _ensure_unique_media_names(
        media_files,
        rel_entries,
        used,
        slide_num=5,
    )

    assert "image1.png" not in renamed_media
    assert len(renamed_media) == 1
    only_name = next(iter(renamed_media))
    assert only_name.startswith("slide5_image1_")
    assert renamed_rels[0]["target"] == f"../media/{only_name}"
