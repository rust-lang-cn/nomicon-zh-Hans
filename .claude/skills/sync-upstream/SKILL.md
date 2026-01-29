---
name: sync-upstream
description: Sync Chinese translation repository with upstream rust-lang/nomicon. Use when user wants to check for upstream changes, sync translations, update from upstream, or asks about differences between local translation and upstream English version. Triggers on requests like "sync upstream", "check upstream changes", "update from nomicon", or "sync translation".
---

# Sync Upstream

Synchronize nomicon-zh-Hans (Chinese translation) with upstream rust-lang/nomicon repository.

## Workflow

### Step 1: Extract Current Translation Base

Extract the commit hash from `src/intro.md`:

```
目前翻译基于 commit：<commit_hash>，基于时间：<date>。
```

Use regex pattern: `目前翻译基于 commit：([a-f0-9]+)，基于时间：(\d{4}/\d{2}/\d{2})。`

### Step 2: Fetch Upstream Latest Commit

Get the latest commit from upstream:

```bash
gh api repos/rust-lang/nomicon/commits/main --jq '.sha'
```

Compare with the extracted commit hash. If identical, report "Already up to date" and exit.

### Step 3: Get Changed Files

List files changed between the two commits:

```bash
gh api "repos/rust-lang/nomicon/compare/<base_commit>...<latest_commit>" --jq '.files[] | select(.filename | startswith("src/")) | {filename, status, patch}'
```

### Step 4: Process Each Changed File

For each changed file in `src/`:

1. **Fetch the new English content** from upstream
2. **Read the corresponding Chinese file** from local repository
3. **Translate the changes** maintaining:
   - Existing translation style and terminology
   - Markdown formatting
   - Code blocks unchanged (only translate comments if any)
   - Links and references preserved
4. **Apply the translation** to local file

Translation guidelines:
- Keep technical terms consistent with existing translations
- Preserve all code examples exactly
- Only translate prose content, not code
- Maintain the same file structure

### Step 5: Update intro.md Metadata

Update the commit and date line in `src/intro.md`:

```
目前翻译基于 commit：<new_commit>，基于时间：<current_date>。
```

Date format: `YYYY/MM/DD`

### Step 6: Output Summary

Provide a summary including:
- Previous commit vs new commit
- List of files updated with change type (added/modified/deleted)
- Brief description of significant changes
- Reminder to review changes before committing

## Example Output

```
## Sync Summary

**Upstream sync completed**

- Previous: 5b3a9d084cbc64e54da87e3eec7c7faae0e48ba9 (2026/01/02)
- Current: abc123def456... (2026/01/29)

### Changed Files (3)

| File | Status | Description |
|------|--------|-------------|
| src/intro.md | modified | Updated warning text |
| src/new-chapter.md | added | New chapter on XYZ |
| src/old-file.md | deleted | Removed deprecated content |

### Next Steps
1. Review the translated changes
2. Run `mdbook build` to verify
3. Commit with message: "sync: update to upstream commit abc123"
```
