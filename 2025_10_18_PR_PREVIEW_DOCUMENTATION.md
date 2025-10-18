# PR Preview Documentation System

**Date**: 2025-10-18
**Status**: Proposed
**Author**: Documentation Team
**Purpose**: Automatically generate and deploy documentation previews for each PR

---

## Overview

Enable reviewers to see documentation changes **before** merging by automatically deploying PR-specific doc previews.

### Benefits

- 🔍 **Review docs alongside code** - See how docstring changes render in Mintlify
- 🐛 **Catch MDX errors early** - Find parsing issues before they hit production
- ✅ **Verify examples work** - Ensure code examples display correctly
- 🚀 **No manual steps** - Automatic deployment on PR creation/update

---

## Current Infrastructure (Ready to Use!)

We already have the pieces in place:

1. ✅ **`make docs-dev`** - Builds from current directory and deploys to dev branch
2. ✅ **Commit hash versioning** - Each deployment creates unique snapshot at `/sdk/{commit_hash}/`
3. ✅ **Path rewriting in `deploy_docs_dev.py`** - Updates `docs.json` to point to correct paths
4. ✅ **`pixeltable-docs-www` repo** - Separate repo for hosting generated docs
5. ✅ **Mintlify dev site** - `https://pixeltable-dev.mintlify.app/`

---

## Proposed Architecture

### 1. GitHub Actions Workflow

**Trigger**: On PR open, update, or synchronize
**File**: `.github/workflows/deploy-pr-preview.yml`

```yaml
name: Deploy PR Docs Preview

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - 'pixeltable/**/*.py'
      - 'docs/**'

jobs:
  deploy-preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --group extra-dev

      - name: Generate documentation
        run: |
          python -m doctools.mintlifier.mintlifier

      - name: Deploy to PR preview branch
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Clone docs repo
          git clone https://github.com/pixeltable/pixeltable-docs-www.git docs-repo
          cd docs-repo

          # Create/checkout pr-previews branch
          git checkout pr-previews || git checkout -b pr-previews

          # Create PR directory
          PR_DIR="pr-${{ github.event.pull_request.number }}"
          rm -rf "$PR_DIR"
          mkdir -p "$PR_DIR"

          # Copy generated docs
          cp -r ../docs/target/* "$PR_DIR/"

          # Update docs.json paths to point to PR directory
          # This is the key: rewrite sdk/latest/ to pr-123/sdk/latest/
          cd "$PR_DIR"
          python -c "
import json
with open('docs.json', 'r') as f:
    config = json.load(f)
docs_str = json.dumps(config)
docs_str = docs_str.replace('sdk/latest/', 'pr-${{ github.event.pull_request.number }}/sdk/latest/')
config = json.loads(docs_str)
with open('docs.json', 'w') as f:
    json.dump(config, f, indent=2)
"
          cd ..

          # Commit and push
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .
          git commit -m "Deploy preview for PR #${{ github.event.pull_request.number }}"
          git push origin pr-previews

      - name: Comment on PR with preview URL
        uses: actions/github-script@v6
        with:
          script: |
            const prNumber = context.issue.number;
            const url = `https://pixeltable-dev.mintlify.app/pr-${prNumber}/`;

            github.rest.issues.createComment({
              issue_number: prNumber,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `📚 **Documentation preview deployed!**\n\n🔗 View at: ${url}\n\n*Preview updates automatically when you push new commits.*`
            });
```

### 2. Directory Structure

```
pixeltable-docs-www/
├── pr-previews branch
│   ├── pr-123/
│   │   ├── docs.json          # Paths rewritten to pr-123/sdk/latest/
│   │   ├── sdk/
│   │   │   └── latest/
│   │   │       ├── table.mdx
│   │   │       ├── pixeltable.mdx
│   │   │       └── ...
│   │   ├── overview/
│   │   ├── examples/
│   │   └── ...
│   ├── pr-456/
│   └── ...
```

### 3. URL Structure

- **Dev deployment**: `https://pixeltable-dev.mintlify.app/sdk/{commit_hash}/`
- **PR preview**: `https://pixeltable-dev.mintlify.app/pr-123/`

Each PR gets its own isolated preview at `/pr-{number}/`.

---

## Implementation Steps

### Phase 1: Basic Workflow (30 min)

1. Create `.github/workflows/deploy-pr-preview.yml`
2. Test on a sample PR
3. Verify preview URL works

### Phase 2: Cleanup (15 min)

Add workflow to delete stale previews after PR merge/close:

```yaml
name: Cleanup PR Preview

on:
  pull_request:
    types: [closed]

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          repository: pixeltable/pixeltable-docs-www
          ref: pr-previews
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Remove PR preview directory
        run: |
          rm -rf "pr-${{ github.event.pull_request.number }}"
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .
          git commit -m "Remove preview for closed PR #${{ github.event.pull_request.number }}" || true
          git push origin pr-previews
```

### Phase 3: Enhancements (optional)

- **Status checks**: Add GitHub status check showing preview deployment status
- **Size limits**: Warn if docs size is too large
- **Error reporting**: Post MDX parsing errors as PR comments
- **Diff view**: Show what changed compared to main branch docs

---

## Alternative: Vercel/Netlify Deploy Previews

Instead of custom GitHub Actions, could use Vercel/Netlify which have built-in PR previews:

### Pros
- Automatic PR preview URLs
- Built-in deployment management
- No custom scripts needed

### Cons
- Need to configure Mintlify to work with Vercel/Netlify
- May have different URL structure
- Additional service dependency

**Recommendation**: Start with GitHub Actions since we already have `make docs-dev` working.

---

## Path Rewriting Logic

**Key insight**: The `docs.json` file contains navigation that references SDK paths. We need to rewrite these for each PR preview.

### Example Transformation

**Original `docs.json`:**
```json
{
  "navigation": {
    "tabs": [
      {
        "tab": "SDK",
        "groups": [
          {
            "pages": ["sdk/latest/table", "sdk/latest/pixeltable"]
          }
        ]
      }
    ]
  }
}
```

**Rewritten for PR 123:**
```json
{
  "navigation": {
    "tabs": [
      {
        "tab": "SDK",
        "groups": [
          {
            "pages": ["pr-123/sdk/latest/table", "pr-123/sdk/latest/pixeltable"]
          }
        ]
      }
    ]
  }
}
```

We already have this logic in `deploy_docs_dev.py` (lines 190-196):

```python
# Update all SDK paths from sdk/latest/ to sdk/{commit_hash}/
docs_str = json.dumps(docs_config)
docs_str = docs_str.replace('sdk/latest/', f'sdk/{commit_hash}/')
docs_config = json.loads(docs_str)
```

Just adapt it to use `pr-{number}/sdk/latest/` instead of `sdk/{commit_hash}/`.

---

## Testing Plan

### Manual Testing

1. Create a test PR with docstring changes
2. Trigger workflow manually
3. Verify preview URL works: `https://pixeltable-dev.mintlify.app/pr-{number}/`
4. Check that navigation works
5. Verify SDK pages render correctly

### Automated Testing

- Add workflow that validates generated `docs.json`
- Check for MDX parsing errors
- Verify all internal links resolve

---

## Security Considerations

### Secrets Needed

- `GITHUB_TOKEN` - Built-in, already has write access to repos
- No additional secrets required (we're pushing to public repo)

### Branch Protection

- Use separate `pr-previews` branch (not `main` or `dev`)
- Only bot can push to `pr-previews`
- Previews are isolated from production docs

### Malicious PRs

- Previews are on separate domain (`pixeltable-dev.mintlify.app`)
- Can't affect production docs
- Auto-cleanup on PR close prevents accumulation

---

## Estimated Costs

- **GitHub Actions minutes**: ~5 min per PR update × average 3 updates per PR = 15 min/PR
- **Storage in docs repo**: ~10 MB per preview × max 10 open PRs = 100 MB
- **Mintlify hosting**: No additional cost (same dev instance)

**Total**: Negligible (within free tier)

---

## Open Questions

1. **Should we deploy on every commit?** Or only when explicitly requested?
   - **Recommendation**: Every commit to catch issues early

2. **How long to keep stale previews?** After PR close?
   - **Recommendation**: Delete immediately on PR close/merge

3. **What about PR preview for docs-only changes?** (no code changes)
   - **Recommendation**: Support it, still useful to preview formatting

4. **Rate limiting?** If we get many PRs at once
   - **Recommendation**: Start without limits, add if needed

---

## Success Metrics

After implementation, track:

- 📊 **MDX errors caught before merge** - How many parsing issues found in preview
- ⏱️ **Time to review docs changes** - Does it speed up reviews?
- 🐛 **Production doc issues** - Does it reduce bugs in deployed docs?
- 👥 **Adoption rate** - Do reviewers actually use previews?

---

## References

- **Existing `make docs-dev`**: `/Users/lux/repos/pixeltable/Makefile` line 195-198
- **Path rewriting logic**: `/Users/lux/repos/pixeltable-doctools/doctools/deploy/deploy_docs_dev.py` line 190-196
- **GitHub Actions docs**: https://docs.github.com/en/actions
- **Mintlify dev site**: https://pixeltable-dev.mintlify.app/

---

## Next Steps

1. ✅ Document the idea (this file)
2. ⏳ Create GitHub Actions workflow
3. ⏳ Test on sample PR
4. ⏳ Add cleanup workflow
5. ⏳ Update CONTRIBUTING.md with PR preview info
6. ⏳ Add status badge to PR template

---

## Notes from 2025-10-18 Session

- We already have commit hash versioning working in `make docs-dev`
- The key challenge is path rewriting in `docs.json` - already solved!
- Mintlify dev site is already set up and working
- This would help catch MDX errors we discovered today (missing `...`, code outside blocks, etc.)
- Low effort, high value - just needs GitHub Actions workflow

**Time estimate**: 1 hour to implement basic version, 2 hours for full version with cleanup.
