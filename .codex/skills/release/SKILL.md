---
name: release
description: Perform a semantic-versioned release for this repo. Use when the user wants to cut a major, minor, or patch release, update CHANGELOG.md from commits since the last tag, and create the version commit and git tag.
---

Perform a proper release using semantic versioning.

**Input**

- One argument: `major`, `minor`, or `patch`

**Workflow**

1. Validate the input.
   Stop unless the requested release type is exactly `major`, `minor`, or `patch`.

2. Read the current version from `package.json`.

3. Compute the next version without tagging first:

   ```bash
   npm version <type> --no-git-tag-version
   ```

4. Generate changelog content.

   Determine the last tag:

   ```bash
   git describe --tags --abbrev=0
   ```

   Get commit subjects since that tag:

   ```bash
   git log --pretty=format:%s <last_tag>..HEAD
   ```

   Parse commits into:

   - `### 🚀 Features`: subjects starting with `feat` or `(feature)`
   - `### 🛠 Fixes & Improvements`: subjects starting with `fix`, `(fix)`, `refactor`, `perf`, `chore`, or `docs`
   - `### 📦 Other`: everything else

   Format the new entry exactly like:

   ```markdown
   ## [<new_version>] - <YYYY-MM-DD>

   ### 🚀 Features
   - ...

   ### 🛠 Fixes & Improvements
   - ...

   ### 📦 Other
   - ...
   ```

   Keep the changelog concise. Omit empty sections.

5. Update `CHANGELOG.md`.

   - If the file has a title at the top, insert the new entry after the title block.
   - Otherwise prepend the new entry at the top.
   - Preserve all existing content below the inserted entry.

6. Finalize the version:

   ```bash
   npm version <type>
   ```

   This must create:

   - the final version update
   - the version commit
   - the git tag

7. Ensure `CHANGELOG.md` is included in the version commit.

   If the changelog was not captured by the version commit:

   ```bash
   git add CHANGELOG.md
   git commit --amend --no-edit
   ```

8. Report:

   - new version
   - number of commits included
   - path to `CHANGELOG.md`

**Constraints**

- Do not modify unrelated files.
- Do not push to remote.
- Keep the changelog human-readable.

**Notes**

- Prefer non-interactive git commands only.
- If `git describe --tags --abbrev=0` fails because there is no prior tag, use all commits reachable from `HEAD` for the first changelog entry and note that there was no previous tag.
