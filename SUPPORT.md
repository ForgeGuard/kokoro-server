# Support

Thanks for using ForgeGuard Kokoro Server. This page explains where to get help and what
is in scope.

## Where to go

| I want to… | Use |
|---|---|
| Report a bug or request a feature | [GitHub Issues](https://github.com/forgeguard-ai/kokoro-server/issues) |
| Report a security vulnerability | [SECURITY.md](./SECURITY.md) (private reporting — not a public issue) |
| Read how to deploy and operate | [Documentation](./docs/site/index.md) |
| Set up a development environment | [`docs/maintainers/development/environment.md`](./docs/maintainers/development/environment.md) |

## Filing a good issue

Before opening an issue, please:

- Search existing issues to avoid duplicates.
- Include the **image tag / version** (`curl http://localhost:8880/system`), how you run
  it (container, Compose, or Helm), and your hardware (GPU model or CPU).
- Include exact reproduction steps, the request you sent, and the response or logs you
  got. Redact any secrets (do not paste an `API_KEY`).

## Scope

- This repository supports the **ForgeGuard** distribution of the server: its images, Helm
  chart, deployment, security, and operational features.
- Issues specific to ForgeGuard changes should be filed here, not with upstream
  Kokoro-FastAPI. Conversely, questions about the underlying Kokoro-82M model belong with
  the model's maintainers.
- There is no private or paid support commitment. Best-effort help is provided through the
  channels above.

## Responsible use

Text-to-speech is synthetic-media generation. Please review
[Responsible use](./docs/site/concepts/responsible-use.md) before deploying publicly.
