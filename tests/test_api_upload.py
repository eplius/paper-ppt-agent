from __future__ import annotations


def test_upload_pdf_returns_session(client, pdf_bytes: bytes):
    response = client.post(
        "/api/upload",
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_info"]["source_type"] == "pdf"
    assert payload["session_id"]


def test_upload_tex_is_classified_as_latex(client):
    response = client.post(
        "/api/upload",
        files={"file": ("paper.tex", b"\\documentclass{article}", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["file_info"]["source_type"] == "latex"


def test_upload_zip_is_classified_as_latex(client, zip_bytes: bytes):
    response = client.post(
        "/api/upload",
        files={"file": ("paper.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 200
    assert response.json()["file_info"]["source_type"] == "latex"


def test_upload_tar_gz_is_classified_as_latex(client, tar_gz_bytes: bytes):
    response = client.post(
        "/api/upload",
        files={"file": ("paper.tar.gz", tar_gz_bytes, "application/gzip")},
    )

    assert response.status_code == 200
    assert response.json()["file_info"]["source_type"] == "latex"
