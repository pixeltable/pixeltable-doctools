from pathlib import Path

import pytest

from pixeltable_doctools.changelog import fetch_releases


def test_escape_empty_mdx_fragments_preserves_code() -> None:
    text = """Proxy tables: import_<>()
`inline_<>()`
``inline_`<>()``
````python
def fenced_<>() -> None:
    pass
````
"""

    assert (
        fetch_releases._escape_empty_mdx_fragments(text)
        == """Proxy tables: import_&lt;&gt;()
`inline_<>()`
``inline_`<>()``
````python
def fenced_<>() -> None:
    pass
````
"""
    )


def test_convert_release_to_mdx_escapes_empty_fragment() -> None:
    release = {
        "tag_name": "v0.6.7",
        "name": "v0.6.7",
        "published_at": "2026-07-14T00:00:00Z",
        "author": {"login": "aaron-siegel"},
        "html_url": "https://github.com/pixeltable/pixeltable/releases/tag/v0.6.7",
        "body": "* Proxy tables: FastAPIRouter and import_<>()",
    }

    result = fetch_releases.convert_release_to_mdx(release)

    assert "import_&lt;&gt;()" in result
    assert "import_<>()" not in result


def test_generate_changelog_escapes_empty_fragment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    release = {
        "tag_name": "v0.6.7",
        "name": "v0.6.7",
        "published_at": "2026-07-14T00:00:00Z",
        "author": {"login": "aaron-siegel"},
        "html_url": "https://github.com/pixeltable/pixeltable/releases/tag/v0.6.7",
        "body": (
            "## What's Changed\n"
            "* Proxy tables: FastAPIRouter and import_<>() by @mkornacker in "
            "https://github.com/pixeltable/pixeltable/pull/1437"
        ),
    }
    monkeypatch.setattr(fetch_releases, "fetch_releases_from_github", lambda repo: [release])

    fetch_releases.generate_changelog_to_dir(tmp_path)

    changelog = (tmp_path / "changelog.mdx").read_text()
    assert "import_&lt;&gt;()" in changelog
    assert "import_<>()" not in changelog
    assert "#### What's Changed" in changelog
    assert "[@mkornacker](https://github.com/mkornacker)" in changelog
    assert "[#1437](https://github.com/pixeltable/pixeltable/pull/1437)" in changelog
