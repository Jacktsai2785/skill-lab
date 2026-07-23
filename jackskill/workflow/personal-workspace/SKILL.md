---
name: personal-workspace
description: >-
  Initialize and maintain a portable Obsidian-style personal Markdown workspace
  with indexes, templates, decision records, interviews, meetings, and safe
  archival. Use when creating a personal vault or organizing notes into this
  structure. Do not reorganize an existing workspace, move notes, initialize
  Git, or configure cloud sync without explicit scope and a reviewed preview.
---

# Maintain a personal Markdown workspace

Use an explicit target path. Preserve existing files and preview every archival
move before applying it.

## Initialize

1. Confirm the target directory, preferred ASCII or emoji folder names, existing
   content, privacy requirements, and backup strategy.
2. Prefer the portable ASCII structure:

   ```text
   workspace/
   ├── README.md
   ├── notes/
   ├── decisions/
   ├── interviews/
   ├── meetings/
   ├── archive/
   └── .metadata/
   ```

3. Preview initialization:

   ```bash
   python3 scripts/workspace.py init /absolute/path/to/workspace
   ```

4. Apply only after reviewing the target:

   ```bash
   python3 scripts/workspace.py init /absolute/path/to/workspace --apply
   ```

   Initialization refuses a non-empty target unless `--merge` is supplied and
   never overwrites an existing file.

5. Customize copied templates in `templates/`. Keep Obsidian links quoted in
   YAML arrays, for example `links: ["[[related-note]]"]`.

## Archive

1. Ensure notes use a parseable frontmatter `date: YYYY-MM-DD` and `status`.
   Never infer archival age from filesystem mtime.
2. Preview the complete move plan:

   ```bash
   python3 scripts/workspace.py archive /absolute/path/to/workspace
   ```

3. Review every source and destination. Resolve missing metadata and destination
   collisions; the script fails closed rather than overwriting.
4. Apply the reviewed plan:

   ```bash
   python3 scripts/workspace.py archive /absolute/path/to/workspace --apply
   ```

   Applied moves are appended to `.metadata/archive-log.jsonl`.

## Git and sync

- Treat Git initialization, remote creation, commits, pushes, cron jobs, and
  cloud synchronization as separate user-authorized operations.
- Inspect notes for personal, interview, compensation, credential, and client
  data before adding a remote. A private repository reduces exposure but is not
  a substitute for secret scanning or access control.
- Stage explicit paths. Do not install an automatic `git add -A` job.
- Avoid two independent synchronization engines writing the same vault unless
  their conflict behavior has been tested.

## Completion criteria

- The target structure matches its README links.
- Existing files were not overwritten.
- Templates contain valid YAML frontmatter.
- Archive preview contains only intended notes and has no collisions.
- Applied archive operations have a local audit log.
- Any Git or cloud operation was separately authorized.

## Resources

- Run [scripts/workspace.py](scripts/workspace.py) for safe initialization and
  archival.
- Copy output templates from [assets/vault](assets/vault); do not recreate them
  inline.
