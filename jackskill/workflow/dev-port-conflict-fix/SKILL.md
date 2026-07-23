---
name: dev-port-conflict-fix
description: >-
  Diagnose and fix local development port conflicts across Vite, Next.js,
  Node.js, Python, Docker, and WSL. Use when a listener reports EADDRINUSE,
  a dev server cannot bind, or a frontend still targets a moved backend.
  Do not use for general production outages, DNS failures, or unrelated HTTP
  4xx/5xx responses unless evidence first confirms a local port mismatch.
---

# Fix local development port conflicts

Resolve the listener conflict without killing unrelated processes or committing
unrelated work.

## Workflow

1. Identify the failing service, requested port, launch command, and repository.
2. Confirm the conflict with a listener-scoped command:

   ```bash
   lsof -nP -iTCP:8080 -sTCP:LISTEN
   ```

   If `lsof` is unavailable, use `ss -ltnp` on Linux or the platform-specific
   command in [references/platform-and-frameworks.md](references/platform-and-frameworks.md).

3. Inspect each returned PID before changing anything:

   ```bash
   ps -p 12345 -o pid=,ppid=,user=,cwd=,args=
   ```

   Verify the command, owner, working directory, and whether the process belongs
   to the current project. Treat a `503` response as a reachable server error,
   not proof of a port conflict.

4. Locate the project's port source of truth. Prefer checked-in configuration,
   `.env.example`, Compose files, start scripts, or project documentation.
   Consult `~/PORTS.md` only if it exists and the project actually adopts it.

5. Choose the smallest coherent repair:

   - Stop a stale listener when the exact process is verified.
   - Move the service to its assigned port.
   - Update every consumer of the moved endpoint.
   - Correct Docker host mappings separately from container ports.

6. Before stopping a process, show the exact PID and command. If the user's task
   did not explicitly authorize restarting local services, ask first. Send
   `SIGTERM`, wait briefly, and recheck the listener. Use `SIGKILL` only after
   the same verified PID fails to exit; never use a broad `pkill -f` pattern.

7. Restart only the affected services and verify:

   - the expected PID owns the expected port;
   - the health endpoint returns the expected response;
   - the frontend uses the new API origin;
   - Vite HMR or Next.js refresh reconnects.

8. Review the diff for hard-coded ports and stale documentation. Do not commit
   unless requested. When committing, stage explicit paths rather than
   `git add -A`.

## Search checklist

Use `rg` before editing:

```bash
rg -n 'localhost:[0-9]+|127\.0\.0\.1:[0-9]+|PORT=|API_BASE_URL|server:\s*\{' .
```

Check configuration precedence. A shell export may override `.env`; a CLI flag
may override both; a reverse proxy may make the browser-facing port different
from the application listener.

## Gotchas

- A client connecting to the old port after a backend move is a configuration
  drift problem, not a second listener conflict.
- `server.hmr.port` is not universally required to equal `server.port`; reverse
  proxies may require `clientPort`. Read the Vite section of the reference.
- Removing `node_modules/.vite` is a cache reset, not a port repair. Do it only
  after listener and HMR configuration are correct.
- WSL and Windows can each own listeners. Inspect both sides when the Linux view
  does not explain the conflict.

## References

Read [references/platform-and-frameworks.md](references/platform-and-frameworks.md)
only for the detected operating system or framework.
