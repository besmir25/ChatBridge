# Security

## Reporting a problem
If you find something that could put a user's data at risk — for example a way for a website or another program to read or send
chats through ChatBridge — please **don't open a public issue**. Use GitHub's private route instead:
**Security → Report a vulnerability** on this repository.

## What's worth knowing
- ChatBridge runs only on your PC and has no server.
- The browser extension talks to a local receiver on `127.0.0.1`. It needs a pairing code, and it refuses requests that come from
  ordinary web pages.
- ChatBridge never presses Enter and never sends a message on your behalf.
- Releases list SHA-256 checksums so downloads can be verified.
