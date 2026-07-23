# Platform and framework port reference

## Listener inspection

- macOS/Linux with `lsof`:
  `lsof -nP -iTCP:<port> -sTCP:LISTEN`
- Linux with `ss`: `ss -ltnp 'sport = :<port>'`
- Windows PowerShell:
  `Get-NetTCPConnection -LocalPort <port> -State Listen`
- Windows command prompt:
  `netstat -ano | findstr :<port>`

Always resolve the PID to its full command and working directory before sending
a signal.

## Vite

Check `server.port`, `server.strictPort`, proxy targets, and environment
variables. Set `strictPort: true` when silently moving to the next free port
would confuse dependent services. Configure `server.hmr.clientPort` only when a
proxy or port-forwarding layer exposes a different browser-facing port.

## Next.js

The development port usually comes from `next dev -p <port>`, the package
script, or `PORT`. Public backend URLs normally use a `NEXT_PUBLIC_*` variable
and require a dev-server restart after changes.

## Python and Node.js

Check CLI flags before `.env` because launch arguments commonly win. Confirm
whether a process manager or reload parent will respawn the child after it is
stopped.

## Docker Compose

In `HOST:CONTAINER`, only `HOST` consumes the local machine's port. Changing the
host mapping does not require changing the application's container listener,
but every host-side consumer must use the new host port.

## WSL and VS Code

Check Linux listeners, Windows listeners, and VS Code's forwarded-port panel.
A forwarded port can be stale even when the service inside WSL is correct.
