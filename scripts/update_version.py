#!/usr/bin/env python3
"""
Version Update Script

This script reads the version from the VERSION file and updates references
in pyproject.toml, the Helm chart, and README.md.
"""

import re
from pathlib import Path

import yaml

# Get the project root directory
ROOT_DIR = Path(__file__).parent.parent

# --- Configuration ---
VERSION_FILE = ROOT_DIR / "VERSION"
PYPROJECT_FILE = ROOT_DIR / "pyproject.toml"
HELM_CHART_FILE = ROOT_DIR / "charts" / "kokoro-server" / "Chart.yaml"
README_FILE = ROOT_DIR / "README.md"
# --- End Configuration ---


def update_pyproject(version: str):
    """Updates the version in pyproject.toml"""
    if not PYPROJECT_FILE.exists():
        print(f"Skipping: {PYPROJECT_FILE} not found.")
        return

    try:
        content = PYPROJECT_FILE.read_text()
        # Regex to find and capture current version = "X.Y.Z" under [project]
        pattern = r'(^\[project\]\s*(?:.*\s)*?version\s*=\s*)"([^"]+)"'
        match = re.search(pattern, content, flags=re.MULTILINE)

        if not match:
            print(f"Warning: Version pattern not found in {PYPROJECT_FILE}")
            return

        current_version = match.group(2)
        if current_version == version:
            print(f"Already up-to-date: {PYPROJECT_FILE} (version {version})")
        else:
            # Perform replacement
            new_content = re.sub(
                pattern, rf'\1"{version}"', content, count=1, flags=re.MULTILINE
            )
            PYPROJECT_FILE.write_text(new_content)
            print(f"Updated {PYPROJECT_FILE} from {current_version} to {version}")

    except Exception as e:
        print(f"Error processing {PYPROJECT_FILE}: {e}")


def update_helm_chart(version: str):
    """Updates the version and appVersion in the Helm chart"""
    if not HELM_CHART_FILE.exists():
        print(f"Skipping: {HELM_CHART_FILE} not found.")
        return

    try:
        content = HELM_CHART_FILE.read_text()
        original_content = content
        updated_count = 0

        # Update 'version:' line (unquoted)
        # Looks for 'version:' followed by optional whitespace and the version number
        version_pattern = r"^(version:\s*)(\S+)"
        current_version_match = re.search(version_pattern, content, flags=re.MULTILINE)
        if current_version_match and current_version_match.group(2) != version:
            content = re.sub(
                version_pattern,
                rf"\g<1>{version}",
                content,
                count=1,
                flags=re.MULTILINE,
            )
            print(
                f"Updating 'version' in {HELM_CHART_FILE} from {current_version_match.group(2)} to {version}"
            )
            updated_count += 1
        elif current_version_match:
            print(f"Already up-to-date: 'version' in {HELM_CHART_FILE} is {version}")
        else:
            print(f"Warning: 'version:' pattern not found in {HELM_CHART_FILE}")

        # Update 'appVersion:' line — always normalize the whole line to
        # appVersion: "X.Y.Z" (quoted), regardless of current quoting.
        app_version_pattern = r"^appVersion:[ \t]*(\S+)[ \t]*$"
        current_app_version_match = re.search(
            app_version_pattern, content, flags=re.MULTILINE
        )

        if current_app_version_match:
            original_display = current_app_version_match.group(1)  # e.g. '"0.2.0"'
            target_display = f'"{version}"'
            new_line = f"appVersion: {target_display}"

            if current_app_version_match.group(0) == new_line:
                print(
                    f"Already up-to-date: 'appVersion' in {HELM_CHART_FILE} is {target_display}"
                )
            else:
                content = re.sub(
                    app_version_pattern,
                    new_line,
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
                print(
                    f"Updating 'appVersion' in {HELM_CHART_FILE} from {original_display} to {target_display}"
                )
                updated_count += 1
        else:
            print(f"Warning: 'appVersion:' pattern not found in {HELM_CHART_FILE}")

        # Write back only if changes were made
        if content != original_content:
            HELM_CHART_FILE.write_text(content)
            # Confirmation message printed above during the specific update
        elif updated_count == 0 and current_version_match and current_app_version_match:
            # If no updates were made but patterns were found, confirm it's up-to-date overall
            print(f"Already up-to-date: {HELM_CHART_FILE} (version {version})")

    except Exception as e:
        print(f"Error processing {HELM_CHART_FILE}: {e}")


def update_readme(version: str):
    """Updates pinned Docker image tags in README.md.

    Releases publish plain X.Y.Z tags (no 'v' prefix). Only version-pinned
    tags are rewritten — ':latest' references are intentional and left alone.
    """
    if not README_FILE.exists():
        print(f"Skipping: {README_FILE} not found.")
        return

    try:
        content = README_FILE.read_text()
        original_content = content

        # Pinned ghcr.io/forgeguard/kokoro-server[-variant]:X.Y.Z (or :vX.Y.Z) tags
        pattern = (
            r"(ghcr\.io/forgeguard/kokoro-server(?:-cu128|-jetson)?):(v?\d+\.\d+\.\d+)"
        )
        matches = list(re.finditer(pattern, content))  # Find all occurrences

        if matches:
            if any(match.group(2) != version for match in matches):
                content = re.sub(pattern, rf"\1:{version}", content)

        # Prose pin example, e.g.: pin a release tag (e.g. `:1.1.0`)
        prose_pattern = r"(pin a release tag \(e\.g\. `:)v?\d+\.\d+\.\d+(`\))"
        content = re.sub(prose_pattern, rf"\g<1>{version}\g<2>", content)

        if not matches and not re.search(prose_pattern, original_content):
            print(f"Warning: Docker image tag pattern not found in {README_FILE}")
        elif content != original_content:
            README_FILE.write_text(content)
            print(f"Updated Docker image tags in {README_FILE} to {version}")
        else:
            print(
                f"Already up-to-date: Docker image tags in {README_FILE} (version {version})"
            )

    except Exception as e:
        print(f"Error processing {README_FILE}: {e}")


def main():
    # Read the version from the VERSION file
    if not VERSION_FILE.exists():
        print(f"Error: {VERSION_FILE} not found.")
        return

    try:
        version = VERSION_FILE.read_text().strip()
        if not re.match(r"^\d+\.\d+\.\d+$", version):
            print(
                f"Error: Invalid version format '{version}' in {VERSION_FILE}. Expected X.Y.Z"
            )
            return
    except Exception as e:
        print(f"Error reading {VERSION_FILE}: {e}")
        return

    print(f"Read version: {version} from {VERSION_FILE}")
    print("-" * 20)

    # Update files (releases publish plain X.Y.Z tags — no 'v' prefix)
    update_pyproject(version)
    update_helm_chart(version)
    update_readme(version)

    print("-" * 20)
    print("Version update script finished.")


if __name__ == "__main__":
    main()
