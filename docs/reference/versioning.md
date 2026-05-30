# Versioning Strategy

Versioning and release management for agentlet-core.

## Semantic Versioning

Agentlet-core follows [Semantic Versioning 2.0.0](https://semver.org/) with the format: **MAJOR.MINOR.PATCH**

### Version Components

```
X.Y.Z
│ │ │
│ │ └─ PATCH: Bug fixes (backward-compatible)
│ └─── MINOR: New features (backward-compatible)
└───── MAJOR: Breaking changes (not backward-compatible)
```

**Examples:**
- `0.1.0 → 0.2.0`: Added MCP protocol support (new feature)
- `0.1.0 → 0.1.1`: Fixed config loading bug (bug fix)
- `0.5.0 → 1.0.0`: Stable API, production-ready (major milestone)
- `1.2.3 → 2.0.0`: Changed CLI argument structure (breaking change)

### Pre-1.0 Development (0.x.x)

**Current stage:** 0.1.0-alpha

During 0.x.x phase:
- Breaking changes are acceptable (but documented)
- MINOR bumps for significant changes
- PATCH bumps for bug fixes only
- API not considered stable until 1.0.0

### Post-1.0 Stability (1.x.x+)

After 1.0.0:
- MAJOR bumps for breaking changes
- MINOR bumps for new features
- PATCH bumps for bug fixes
- Strict backward compatibility within major version

## Version Management

### Single Source of Truth

**Version location:** `pyproject.toml` (line 3)

```toml
[project]
name = "agentlet-core"
version = "0.1.0a1"  # ONLY place to update version
```

**Runtime access:**
```python
from importlib.metadata import version

__version__ = version("agentlet-core")  # Dynamically reads from package
```

**Why this approach:**
- Avoids version sync issues
- Hatchling (build backend) reads automatically
- Industry standard (PEP 621)

### When to Bump Versions

**MAJOR (X.0.0)** - Breaking changes:
- CLI argument changes that break existing scripts
- Configuration format changes
- API signature changes (when library is stable)
- Removing deprecated features

**MINOR (0.X.0)** - New features:
- New configuration options (backward-compatible)
- New CLI flags
- New transport types (e.g., WebSocket MCP)
- New observability features

**PATCH (0.0.X)** - Bug fixes:
- Configuration loading fixes
- Error handling improvements
- Documentation fixes
- Security patches

## Release Process

**Important:** All changes to `main` must go through Pull Requests. Direct commits to `main` are not allowed.

### Quick Reference

```bash
# Complete release workflow
git checkout -b release/vX.Y.Z           # 1. Create branch
# Edit pyproject.toml + CHANGELOG.md     # 2. Update version
git commit -m "chore: bump version"      # 3. Commit
gh pr create --label "release"           # 4. Create PR
# Get approvals, merge PR                # 5. Review & merge
git checkout main && git pull            # 6. Switch to main
git tag -a vX.Y.Z -m "Release vX.Y.Z"    # 7. Create tag
git push origin vX.Y.Z                   # 8. Push tag (triggers release)
```

### 1. Create Release Branch

```bash
# Ensure you're on latest main
git checkout main
git pull origin main

# Create release branch
git checkout -b release/v0.3.0
```

### 2. Prepare Release

**Update version in pyproject.toml:**
```bash
# Edit pyproject.toml
# Change: version = "0.2.2" to version = "0.3.0"
vim pyproject.toml
```

**Update CHANGELOG.md (recommended):**
```markdown
## [0.3.0] - 2025-01-30

### Added
- New SSE transport for MCP tools
- Signal-specific OTLP endpoints for traces/metrics

### Changed
- Improved retry logic with API-suggested wait times

### Fixed
- MCP stdio process cleanup on termination
```

### 3. Commit and Create PR

```bash
# Commit version changes
git add pyproject.toml CHANGELOG.md
git commit -m "chore: bump version to 0.3.0"

# Push release branch
git push origin release/v0.3.0

# Create PR via GitHub CLI (or use GitHub UI)
gh pr create \
  --title "chore: bump version to 0.3.0" \
  --body "$(cat <<'EOF'
## Release v0.3.0

### Changes
- New SSE transport for MCP tools
- Signal-specific OTLP endpoints for traces/metrics
- Improved retry logic with API-suggested wait times
- Fixed MCP stdio process cleanup on termination

### Checklist
- [ ] Version updated in pyproject.toml
- [ ] CHANGELOG.md updated
- [ ] All CI checks passing
- [ ] Ready to tag and release
EOF
)" \
  --label "release"
```

**PR Requirements:**
- Title: `chore: bump version to X.Y.Z`
- All CI checks must pass
- Get required approvals
- Include changelog summary in description

### 4. Merge and Tag

**After PR is approved and merged:**

```bash
# Switch to main and pull the merged changes
git checkout main
git pull origin main

# Create annotated tag
git tag -a v0.3.0 -m "Release v0.3.0

- New SSE transport for MCP tools
- Signal-specific OTLP endpoints
- Improved retry logic
- Fixed stdio process cleanup
"

# Push tag (triggers release workflow)
git push origin v0.3.0
```

**Tag naming rules:**
- Always prefix with `v` (e.g., `v0.3.0`)
- Use annotated tags: `git tag -a`
- Include release notes in tag message
- Only create tag after PR is merged to main

### 5. Automated Release

The `release.yml` GitHub Actions workflow automatically triggers when a tag is pushed:

1. **Quality Checks** - Runs lint, typecheck, security scan, tests
2. **Build** - Creates Python wheel with `uv build`
3. **Docker Build** - Builds multi-platform images (linux/amd64, linux/arm64)
4. **Docker Push** - Pushes images to Docker Hub with tags:
   - `synteles/agentlet-core:0.3.0` (version tag)
   - `synteles/agentlet-core:latest` (latest tag)
5. **GitHub Release** - Creates release with wheel attached

### 6. Verify Release

After workflow completes:

```bash
# Check Docker Hub
docker pull synteles/agentlet-core:0.3.0
docker pull synteles/agentlet-core:latest

# Check GitHub Releases
open https://github.com/Synteles/agentlet/releases
```

## Version Tagging

### Production Releases

```bash
# Standard release
git tag -a v1.2.3 -m "Release v1.2.3"
```

### Pre-Releases (Optional)

```bash
# Alpha release
git tag -a v1.2.3-alpha.1 -m "Alpha release v1.2.3-alpha.1"

# Beta release
git tag -a v1.2.3-beta.1 -m "Beta release v1.2.3-beta.1"

# Release candidate
git tag -a v1.2.3-rc.1 -m "Release candidate v1.2.3-rc.1"
```

**Pre-release naming:**
- `v1.2.3-alpha.1`, `v1.2.3-alpha.2`, ...
- `v1.2.3-beta.1`, `v1.2.3-beta.2`, ...
- `v1.2.3-rc.1`, `v1.2.3-rc.2`, ...

## Docker Image Tagging

Docker images are tagged with multiple tags:

### Version-Specific Tags

```
synteles/agentlet-core:0.2.2     # Exact version
synteles/agentlet-core:0.2       # Minor version
synteles/agentlet-core:0         # Major version
```

### Rolling Tags

```
synteles/agentlet-core:latest    # Latest stable release
```

### Pre-Release Tags

```
synteles/agentlet-core:0.3.0-alpha.1    # Alpha
synteles/agentlet-core:0.3.0-rc.1       # Release candidate
```

**Usage:**
```bash
# Pin to exact version (recommended for production)
docker pull synteles/agentlet-core:0.2.2

# Use latest (for development)
docker pull synteles/agentlet-core:latest
```

## Rollback Strategy

### Quick Fix (Preferred)

If a release has issues:

```bash
# 1. Create hotfix branch
git checkout main
git pull origin main
git checkout -b hotfix/v0.3.1

# 2. Make fixes
git commit -m "fix: resolve critical issue in 0.3.0"

# 3. Update version to patch release
# Edit pyproject.toml: version = "0.3.1"
git commit -m "chore: bump version to 0.3.1"

# 4. Create PR
git push origin hotfix/v0.3.1
gh pr create --title "hotfix: v0.3.1 - resolve critical issue" --label "hotfix"

# 5. After PR merge, tag the release
git checkout main
git pull origin main
git tag -a v0.3.1 -m "Hotfix release v0.3.1"
git push origin v0.3.1
```

**Note:** For critical hotfixes, you may expedite the PR review process, but still maintain the PR workflow for audit trail.

### Docker Image Rollback

```bash
# Re-tag previous good version as latest
docker pull synteles/agentlet-core:0.2.2
docker tag synteles/agentlet-core:0.2.2 synteles/agentlet-core:latest
docker push synteles/agentlet-core:latest
```

### Delete Failed Tag

If release failed:

```bash
# Delete local tag
git tag -d v0.3.0

# Delete remote tag
git push origin :refs/tags/v0.3.0

# Fix issue and recreate tag
git tag -a v0.3.0 -m "Release v0.3.0 (retry)"
git push origin v0.3.0
```

## Branch Protection

### GitHub Branch Protection Rules

Protect the `main` branch to enforce the PR workflow:

**Settings → Branches → Branch protection rules → Add rule:**

**Required settings:**
- ✅ **Require a pull request before merging**
  - Require approvals: 1+ (adjust based on team size)
  - Dismiss stale pull request approvals when new commits are pushed
  - Require review from Code Owners (optional)
- ✅ **Require status checks to pass before merging**
  - Require branches to be up to date before merging
  - Status checks: `lint`, `typecheck`, `security`, `test`
- ✅ **Require conversation resolution before merging**
- ✅ **Require linear history** (optional, for clean git history)

**Optional settings:**
- ⚠️ **Do not** include administrators
  - Allows emergency direct commits if absolutely necessary
  - Use sparingly and document when used
- 🔒 **Restrict who can push to matching branches** (optional)
  - Limit to specific teams/users for critical branches

### Tag Protection (Optional)

Protect version tags from accidental deletion:

**Settings → Tags → Protected tags → New rule:**

**Pattern:** `v*`
- Prevents deletion or overwriting of version tags
- Only designated users can create tags matching pattern

**Alternative:** Use GitHub Environments for release approval workflow.

## Maintenance Branches

### Future Consideration

Once stable (1.0.0+), consider maintenance branches:

**Pattern:**
- `main` - Active development (2.x.x)
- `1.x-maintenance` - Bug fixes for 1.x.x users
- `0.x-maintenance` - Critical fixes for 0.x.x users (if needed)

**Example:**
```bash
# Critical bug in 1.5.2, but main is at 2.1.0

# 1. Create maintenance branch from last 1.x release
git checkout v1.5.2
git checkout -b 1.x-maintenance
git push origin 1.x-maintenance

# 2. Create fix branch
git checkout -b fix/security-issue-1.5.3

# 3. Fix bug and bump version
# Make fixes...
git commit -m "fix: critical security fix"
# Edit pyproject.toml: version = "1.5.3"
git commit -m "chore: bump version to 1.5.3"

# 4. Create PR to maintenance branch
git push origin fix/security-issue-1.5.3
gh pr create --base 1.x-maintenance --title "fix: critical security fix v1.5.3"

# 5. After PR merge, tag from maintenance branch
git checkout 1.x-maintenance
git pull origin 1.x-maintenance
git tag -a v1.5.3 -m "Security fix release v1.5.3"
git push origin v1.5.3
```

**Note:** Apply same branch protection rules to maintenance branches.

## Version Checking

### Programmatic

```python
import agentlet_core

print(agentlet_core.__version__)  # "0.1.0a1"
```

### CLI

```bash
# Check installed version
python -c "import agentlet_core; print(agentlet_core.__version__)"
```

## Automation Tools (Future)

### bump-my-version

```bash
# Install
pip install bump-my-version

# Bump version automatically
bump-my-version patch  # 0.2.2 → 0.2.3
bump-my-version minor  # 0.2.3 → 0.3.0
bump-my-version major  # 0.3.0 → 1.0.0
```

### commitizen

```bash
# Install
pip install commitizen

# Auto-bump based on commits
cz bump  # Analyzes commit messages
```

### python-semantic-release

```bash
# Install
pip install python-semantic-release

# Full automation
semantic-release version
semantic-release publish
```

**Recommendation:** Manual versioning is fine for early stage. Consider automation when:
- Multiple contributors
- Frequent releases (weekly+)
- Need automated CHANGELOG generation

## Best Practices

### DO ✅

1. **Use PR workflow for all version changes**
   - Never push directly to `main`
   - All version bumps go through Pull Requests
   - Get required approvals before merging

2. **Never skip versions**
   - Go 0.2.0 → 0.3.0, not 0.2.0 → 0.5.0

3. **Test before tagging**
   - Ensure all CI checks pass on PR
   - Only create tags after PR is merged to main

4. **Document changes**
   - Update CHANGELOG.md in version bump PR
   - Include summary in PR description
   - Use GitHub release notes

5. **Use annotated tags**
   - Include release notes: `git tag -a v0.3.0 -m "..."`
   - Create tags only from merged `main` branch

6. **Communicate breaking changes**
   - Clearly document in CHANGELOG and PR
   - Consider migration guide for major versions
   - Label PR with "breaking-change" if applicable

7. **Enable branch protection**
   - Require PRs for all changes to `main`
   - Require status checks to pass
   - Require conversation resolution

### DON'T ❌

1. **Don't commit directly to main**
   - Always use PRs, even for version bumps
   - Use branch protection to enforce this

2. **Don't change version in multiple places**
   - Only edit `pyproject.toml`

3. **Don't create tags before PR merge**
   - Tag only after version bump PR is merged to main
   - Tags trigger release workflows

4. **Don't force push tags**
   - Delete and recreate if needed: `git push origin :refs/tags/vX.Y.Z`

5. **Don't reuse version numbers**
   - If 0.3.0 is broken, release 0.3.1 (don't re-release 0.3.0)

6. **Don't skip PR reviews for "simple" version bumps**
   - Even version bumps benefit from review
   - Catches version number mistakes, CHANGELOG errors, etc.

## Version History

| Version      | Date       | Highlights |
|--------------|------------|------------|
| 0.1.0-alpha  | 2026-05-27 | First preview release |

## References

- [Semantic Versioning 2.0.0](https://semver.org/)
- [PEP 621 - Project Metadata](https://peps.python.org/pep-0621/)
- [PEP 440 - Version Identification](https://peps.python.org/pep-0440/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)

## Next Steps

- **[Deployment](deployment.md)** - Deploy agentlet-core
- **[CI/CD](ci-cd.md)** - Continuous integration and deployment
