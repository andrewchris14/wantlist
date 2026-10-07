# Local-only Worker foundation

There is deliberately no deploy script, Wrangler remote binding, account ID,
database ID, credential, public route, or frontend integration. The handler
refuses non-loopback hosts and requires `FOUNDATION_MODE=local-test`.

Tests exercise the D1 prepare/bind/batch interface using Node's built-in SQLite.
They do NOT establish that this runs in Cloudflare workerd or remote D1.
The Python reference uses the same SQLite schema for full-baseline testing.

Before deployment, verify current Cloudflare crypto support and measure the
600,000-iteration Web Crypto PBKDF2-SHA256 verifier on the actual free runtime.
Cloudflare runtimes may impose an iteration ceiling and/or CPU budget that
precludes it. Do not lower the work factor to make it fit. If incompatible,
stop and review a maintained, supported verifier or managed identity approach.
No real owner credentials should be provisioned until that gate passes.

Session entropy is 256 bits. Only a SHA-256 hash of the opaque token is stored.
Remembered sessions expire absolutely after 90 days; regular sessions after
8 hours. There is no silent indefinite renewal. A regular cookie has no
Max-Age, though browsers with session restoration may retain it; server expiry
still applies. Remembered cookies persist browser/computer restarts unless
the browser clears cookies or private browsing is used. Writes require an
exact Origin match; cookies are Secure, HttpOnly, SameSite=Strict and __Host-.

No browser storage receives passwords or tokens. Login counts all attempts:
5 per IP and 25 globally per 15-minute bucket. These provisional limits require
real-device testing and allow temporary denial of service under attack;
Cloudflare-level abuse protection must be evaluated before production.
