#!/usr/bin/env python3
"""Documentation validator for ForgeGuard Kokoro Server.

Validates the repository's documentation publication contract without any
third-party GitHub Actions — a single checked-in script (stdlib + PyYAML) so it
runs identically in CI and locally:

    python scripts/docs/validate_docs.py

Checks:
  * `.forgeguard/docs.yml` schema + repository identity
  * `docs/site/index.md` exists
  * every `docs/site/**/*.md` has required front matter (title/description/order/status)
  * allowed `status` values and integer `order`
  * unique normalized routes under `docs/site`
  * internal relative links resolve, and `#anchors` match a heading
  * no published page links into `docs/maintainers/` or other private paths
  * no path escapes or symlinks under `docs/site`
  * referenced images exist and carry alt text
  * the banner is a PNG at the canonical path, 2172x724, under a sane size
  * README references the banner and the docs index
  * a light secret scan across README + docs
  * basic Markdown hygiene (no tabs, no trailing whitespace, no unresolved conflict markers)

Exit code 0 = all good; 1 = one or more errors. Warnings never fail the build.
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs pyyaml
    print("ERROR: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "docs" / "site"
MAINTAINERS = REPO / "docs" / "maintainers"
MANIFEST = REPO / ".forgeguard" / "docs.yml"
README = REPO / "README.md"
BANNER = SITE / "assets" / "repository" / "banner-dark.png"

ALLOWED_STATUS = {"stable", "beta", "experimental", "deprecated"}
REQUIRED_FRONT_MATTER = ("title", "description", "order", "status")
BANNER_W, BANNER_H = 2172, 724
BANNER_MAX_BYTES = 3 * 1024 * 1024

# Repository identity the manifest must declare.
EXPECT_SLUG = "kokoro-server"
EXPECT_OWNER = "forgeguard-ai"
EXPECT_CONTENT_ROOT = "docs/site"

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


# --------------------------------------------------------------------------- #
# Front matter
# --------------------------------------------------------------------------- #

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_front_matter(text: str) -> dict | None:
    m = _FM_RE.match(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def body_after_front_matter(text: str) -> str:
    m = _FM_RE.match(text)
    return text[m.end():] if m else text


_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


def strip_code(text: str) -> str:
    """Remove fenced blocks and inline code so code samples that contain
    Markdown-like syntax (links, `#` shell comments) are not mistaken for real
    links or headings."""
    text = _FENCE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


# --------------------------------------------------------------------------- #
# Link / anchor helpers
# --------------------------------------------------------------------------- #

# Markdown inline links: [text](target) and images ![alt](target).
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$", re.MULTILINE)


def slugify_heading(text: str) -> str:
    """Approximate GitHub's heading-anchor algorithm."""
    text = re.sub(r"`[^`]*`", lambda m: m.group(0).strip("`"), text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # strip md links
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]+", "", text)  # drop punctuation
    text = text.replace(" ", "-")
    return text


def anchors_for(text: str) -> set[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    for h in HEADING_RE.findall(strip_code(text)):
        base = slugify_heading(h)
        n = seen.get(base, 0)
        anchor = base if n == 0 else f"{base}-{n}"
        seen[base] = n + 1
        out.add(anchor)
    return out


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "tel:"))


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


def check_manifest() -> None:
    if not MANIFEST.exists():
        err(f"missing manifest: {MANIFEST.relative_to(REPO)}")
        return
    try:
        data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        err(f"manifest is not valid YAML: {e}")
        return
    if not isinstance(data, dict):
        err("manifest root must be a mapping")
        return
    if data.get("version") != 1:
        err("manifest: version must be 1")
    project = data.get("project") or {}
    if project.get("slug") != EXPECT_SLUG:
        err(f"manifest: project.slug must be '{EXPECT_SLUG}'")
    if project.get("kind") not in {"original", "maintained-fork"}:
        err("manifest: project.kind must be 'original' or 'maintained-fork'")
    if project.get("kind") == "maintained-fork" and "upstream" not in data:
        err("manifest: maintained-fork requires an 'upstream' section")
    repo = data.get("repository") or {}
    if repo.get("owner") != EXPECT_OWNER:
        err(f"manifest: repository.owner must be '{EXPECT_OWNER}'")
    if repo.get("name") != EXPECT_SLUG:
        err(f"manifest: repository.name must be '{EXPECT_SLUG}'")
    source = data.get("source") or {}
    if source.get("content_root") != EXPECT_CONTENT_ROOT:
        err(f"manifest: source.content_root must be '{EXPECT_CONTENT_ROOT}'")
    entry = source.get("entrypoint", "index.md")
    if not (SITE / entry).exists():
        err(f"manifest: entrypoint '{entry}' not found under {EXPECT_CONTENT_ROOT}")
    publishing = data.get("publishing") or {}
    route = publishing.get("route", "")
    if not re.fullmatch(r"/projects/[a-z0-9-]+/docs", route):
        err(f"manifest: publishing.route '{route}' is not a valid project route")
    if publishing.get("versions") not in {"releases", "default-branch", "both"}:
        err("manifest: publishing.versions must be releases|default-branch|both")


def check_banner() -> None:
    if not BANNER.exists():
        err(f"banner not found at {BANNER.relative_to(REPO)}")
        return
    data = BANNER.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        err("banner is not a PNG")
        return
    if len(data) > BANNER_MAX_BYTES:
        err(f"banner exceeds {BANNER_MAX_BYTES} bytes ({len(data)})")
    w, h = struct.unpack(">II", data[16:24])
    if (w, h) != (BANNER_W, BANNER_H):
        err(f"banner must be {BANNER_W}x{BANNER_H}, got {w}x{h}")


def check_readme() -> None:
    if not README.exists():
        err("README.md missing")
        return
    text = README.read_text(encoding="utf-8")
    banner_rel = "docs/site/assets/repository/banner-dark.png"
    if banner_rel not in text:
        err(f"README does not reference the banner ({banner_rel})")
    if "docs/site/index.md" not in text:
        err("README does not link to docs/site/index.md")


def iter_site_pages() -> list[Path]:
    return sorted(p for p in SITE.rglob("*.md") if p.is_file())


def check_no_symlinks() -> None:
    for p in SITE.rglob("*"):
        if p.is_symlink():
            err(f"symlink not allowed under docs/site: {p.relative_to(REPO)}")


def check_pages() -> None:
    pages = iter_site_pages()
    if not (SITE / "index.md").exists():
        err("docs/site/index.md is missing")

    routes: dict[str, Path] = {}
    for page in pages:
        rel = page.relative_to(REPO)
        text = page.read_text(encoding="utf-8")

        # Markdown hygiene
        if "\t" in text:
            warn(f"{rel}: contains a tab character")
        if re.search(r"[<]{7}|[=]{7}=|[>]{7}", text):
            err(f"{rel}: unresolved merge-conflict marker")
        for i, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                warn(f"{rel}:{i}: trailing whitespace")
                break

        # Front matter
        fm = parse_front_matter(text)
        if fm is None:
            err(f"{rel}: missing or invalid YAML front matter")
        else:
            for key in REQUIRED_FRONT_MATTER:
                if key not in fm:
                    err(f"{rel}: front matter missing '{key}'")
            if "status" in fm and fm["status"] not in ALLOWED_STATUS:
                err(f"{rel}: status '{fm['status']}' not in {sorted(ALLOWED_STATUS)}")
            if "order" in fm and not isinstance(fm["order"], int):
                err(f"{rel}: order must be an integer")

        # Route uniqueness (normalized relative path without extension)
        route = page.relative_to(SITE).with_suffix("").as_posix().lower()
        if route in routes:
            err(f"duplicate route '{route}': {rel} and {routes[route].relative_to(REPO)}")
        routes[route] = page

        check_links(page, text, rel)


def check_links(page: Path, text: str, rel: Path) -> None:
    body = strip_code(body_after_front_matter(text))
    for bang, alt, target in LINK_RE.findall(body):
        target = target.strip()
        is_image = bang == "!"
        # Split off any anchor / title.
        url = target.split(" ")[0]
        anchor = ""
        if "#" in url:
            url, anchor = url.split("#", 1)

        if is_external(target):
            continue
        if is_image and not alt.strip():
            err(f"{rel}: image without alt text -> {target}")

        if url == "":
            # Same-page anchor.
            if anchor and anchor.lower() not in {a.lower() for a in anchors_for(body)}:
                err(f"{rel}: broken same-page anchor '#{anchor}'")
            continue

        dest = (page.parent / url).resolve()

        # Publication-boundary + escape checks.
        try:
            dest.relative_to(SITE.resolve())
        except ValueError:
            if MAINTAINERS.resolve() in dest.parents or dest == MAINTAINERS.resolve():
                err(f"{rel}: published page links into docs/maintainers -> {target}")
            else:
                err(f"{rel}: link escapes docs/site publication root -> {target}")
            continue

        if not dest.exists():
            err(f"{rel}: broken link -> {target}")
            continue

        # Anchor resolution into another markdown page.
        if anchor and dest.suffix == ".md":
            dtext = body_after_front_matter(dest.read_text(encoding="utf-8"))
            if anchor.lower() not in {a.lower() for a in anchors_for(dtext)}:
                err(f"{rel}: broken anchor '{target}'")


SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub personal access token"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
]


def check_secrets() -> None:
    targets = [README] + iter_site_pages() + (
        sorted(MAINTAINERS.rglob("*.md")) if MAINTAINERS.exists() else []
    )
    for p in targets:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for pat, label in SECRET_PATTERNS:
            if pat.search(text):
                err(f"{p.relative_to(REPO)}: possible {label} committed")


def main() -> int:
    if not SITE.exists():
        err("docs/site does not exist")
    else:
        check_no_symlinks()
        check_pages()
    check_manifest()
    check_banner()
    check_readme()
    check_secrets()

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    n_pages = len(iter_site_pages()) if SITE.exists() else 0
    print(f"\nChecked {n_pages} site pages · {len(warnings)} warnings · {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
