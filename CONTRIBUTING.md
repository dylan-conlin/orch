# Contributing to orch-cli

## Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for changelog generation.

**Format:** `type(scope): description`

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `refactor` - Code refactoring (no feature/fix)
- `test` - Adding/updating tests
- `chore` - Maintenance tasks
- `perf` - Performance improvements

**Examples:**
```
feat: add --parallel flag to spawn command
fix: handle missing workspace directory gracefully
docs: update README installation instructions
refactor(registry): simplify agent lookup logic
```

**Breaking changes:** Add `!` after type or `BREAKING CHANGE:` in body:
```
feat!: change spawn output format
```

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0) - Breaking changes
- **MINOR** (0.2.0) - New features, backward compatible
- **PATCH** (0.1.1) - Bug fixes, backward compatible

## Releasing

1. **Generate changelog:**
   ```bash
   git-cliff -o CHANGELOG.md --tag v0.X.0
   ```

2. **Review and commit:**
   ```bash
   git add CHANGELOG.md
   git commit -m "chore(release): prepare for v0.X.0"
   ```

3. **Tag and push:**
   ```bash
   git tag v0.X.0
   git push origin main --tags
   ```

## Development

```bash
# Install in dev mode
pip install -e .

# Run tests
pytest

# Type checking
mypy src/
```
