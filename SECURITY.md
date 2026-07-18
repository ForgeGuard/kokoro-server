# Security policy

## Reporting a vulnerability

Please report suspected security vulnerabilities **privately** — do not open a public
issue, pull request, or discussion for them.

Use GitHub's private vulnerability reporting for this repository:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability** (GitHub Security Advisories).
3. Provide a clear description, affected version(s), reproduction steps or a
   proof-of-concept, and the impact you observed.

This opens a private advisory visible only to the maintainers and you. If private
reporting is not available to you, open a minimal public issue that says only that you
have a security report and asks a maintainer to open a private channel — do **not**
include details, exploit code, or affected endpoints in that public issue.

Please do not disclose the issue publicly until a fix has been released and you have
coordinated a disclosure timeline with the maintainers.

## What to expect

- We will acknowledge a valid report and work with you on a remediation and disclosure
  plan.
- Fixes are released as new versioned images and, where applicable, an updated Helm chart.
- We credit reporters in the release notes unless you prefer to remain anonymous.

## Supported versions

Security fixes are delivered in new releases. The **latest released minor version**
receives security updates; older versions do not receive backports. Because images are
distributed with immutable version tags, remediation means upgrading to a patched release.

| Version | Supported |
|---|---|
| Latest release (1.1.x) | ✅ |
| Older releases | ❌ (upgrade to the latest release) |

Pin a released version tag and track new releases so you can apply security updates
promptly. See the [upgrade guidance](./docs/site/operations/upgrades.md).

## Operational hardening

This is self-hosted software; much of its security posture is a deployment
responsibility. Authentication is optional and off until you set `API_KEY`, and some
endpoints are intentionally open. Review
[Security hardening](./docs/site/operations/security-hardening.md) before exposing the
server.
