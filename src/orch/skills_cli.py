"""
Skills CLI - Agent guidance tooling.

A CLI tool for authoring, building, and deploying Claude Code skills.

Entry point: skills
Commands:
  - skills list: Show available deployed skills
  - skills build: Compile SKILL.md from templates
  - skills deploy: Install skills to ~/.claude/skills/
  - skills new: Scaffold a new skill
"""

import click
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, List
import yaml

from orch import __version__
from orch.skill_discovery import discover_skills, parse_skill_metadata


# =============================================================================
# Main CLI Group
# =============================================================================

@click.group()
@click.version_option(version=__version__, prog_name='skills')
def cli():
    """Skills CLI - Agent guidance tooling.

    Build, deploy, and manage Claude Code skills.

    \b
    Commands:
      list    Show available deployed skills
      build   Compile SKILL.md from templates
      deploy  Install skills to ~/.claude/skills/
      new     Scaffold a new skill
    """
    pass


# =============================================================================
# skills list
# =============================================================================

@cli.command('list')
@click.option('--category', '-c', help='Filter by category (worker, shared, meta, etc.)')
def list_skills(category: Optional[str]):
    """Show available deployed skills.

    Lists skills installed in ~/.claude/skills/ with their descriptions.

    \b
    Examples:
      skills list                    # List all skills
      skills list --category worker  # List only worker skills
    """
    skills = discover_skills()

    if not skills:
        click.echo("No skills found in ~/.claude/skills/")
        return

    # Filter by category if specified
    if category:
        skills = {
            name: meta for name, meta in skills.items()
            if meta.category and meta.category.lower() == category.lower()
        }
        if not skills:
            click.echo(f"No skills found in category '{category}'")
            return

    # Group by category
    by_category: Dict[str, List[tuple]] = {}
    for name, meta in sorted(skills.items()):
        cat = meta.category or 'uncategorized'
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((name, meta))

    # Display
    for cat in sorted(by_category.keys()):
        click.echo(f"\n{cat}:")
        for name, meta in by_category[cat]:
            # Get description from metadata
            desc = meta.description or ""

            if desc:
                click.echo(f"  {name} - {desc[:60]}{'...' if len(desc) > 60 else ''}")
            else:
                click.echo(f"  {name}")

    click.echo(f"\nTotal: {len(skills)} skill(s)")


# =============================================================================
# skills build
# =============================================================================

@cli.command('build')
@click.option('--source', '-s', type=click.Path(exists=True),
              help='Skills source directory (default: auto-detect)')
@click.option('--dry-run', is_flag=True, help='Show what would be built without changes')
@click.option('--check', is_flag=True, help='Check if files need rebuilding')
def build_skills(source: Optional[str], dry_run: bool, check: bool):
    """Compile SKILL.md from templates.

    Processes templated skills (those with src/SKILL.md.template) and
    expands phase templates into the final SKILL.md.

    \b
    Examples:
      skills build                        # Build from auto-detected source
      skills build --source ./skills/src  # Build from specific directory
      skills build --dry-run              # Preview changes
      skills build --check                # Check if rebuild needed
    """
    # Determine source directory
    if source:
        skills_src = Path(source)
    else:
        # Try to find skills/src in current directory or parent
        cwd = Path.cwd()
        for path in [cwd / 'skills' / 'src', cwd / 'src']:
            if path.exists():
                skills_src = path
                break
        else:
            click.echo("❌ Could not find skills source directory", err=True)
            click.echo("   Use --source to specify the path", err=True)
            raise click.Abort()

    if not skills_src.exists():
        click.echo(f"❌ Skills source not found: {skills_src}", err=True)
        raise click.Abort()

    built_count = 0
    skipped_count = 0

    # Find all templated skills
    template_files = list(skills_src.glob('*/*/src/SKILL.md.template'))

    if not template_files:
        click.echo("No templated skills found (looking for */*/src/SKILL.md.template)")
        return

    click.echo(f"📦 Found {len(template_files)} templated skill(s)")
    click.echo()

    for template_file in template_files:
        skill_dir = template_file.parent.parent
        skill_name = skill_dir.name
        category = skill_dir.parent.name

        # Load phase files
        phases_dir = template_file.parent / 'phases'
        phase_templates = {}

        if phases_dir.exists():
            for phase_file in phases_dir.glob('*.md'):
                phase_name = phase_file.stem
                try:
                    phase_templates[phase_name] = phase_file.read_text()
                except Exception as e:
                    click.echo(f"⚠️  Warning: Could not load phase {phase_name}: {e}", err=True)

        # Read template
        try:
            template_content = template_file.read_text()
        except Exception as e:
            click.echo(f"❌ Error reading {template_file}: {e}", err=True)
            continue

        # Parse and replace templates
        def replace_template(match):
            template_name = match.group(1)
            if template_name not in phase_templates:
                click.echo(f"⚠️  Warning: Phase '{template_name}' not found for {skill_name}", err=True)
                return match.group(0)

            phase_content = phase_templates[template_name]
            replacement = f'<!-- SKILL-TEMPLATE: {template_name} -->\n'
            replacement += f'<!-- Auto-generated from src/phases/{template_name}.md -->\n\n'
            replacement += phase_content.strip()
            replacement += '\n\n<!-- /SKILL-TEMPLATE -->'
            return replacement

        pattern = r'<!--\s*SKILL-TEMPLATE:\s*([a-zA-Z0-9_-]+)\s*-->(.*?)<!--\s*/SKILL-TEMPLATE\s*-->'
        new_content = re.sub(pattern, replace_template, template_content, flags=re.DOTALL)

        # Insert auto-generated header
        header_comment = (
            "<!-- AUTO-GENERATED: Do not edit this file directly. "
            "Source: src/SKILL.md.template + src/phases/*.md. "
            "Build with: skills build -->"
        )
        header_block = (
            "> AUTO-GENERATED SKILL FILE\n"
            "> Source: src/SKILL.md.template + src/phases/*.md\n"
            "> Build command: skills build\n"
            "> Do NOT edit this file directly; edit the sources and rebuild."
        )

        if "AUTO-GENERATED SKILL FILE" not in new_content:
            header = f"{header_comment}\n\n{header_block}\n\n"

            if new_content.startswith("---"):
                frontmatter_end = new_content.find("\n---", 3)
                if frontmatter_end != -1:
                    insert_pos = frontmatter_end + len("\n---")
                    before = new_content[:insert_pos]
                    after = new_content[insert_pos:]
                    new_content = before + "\n\n" + header + after.lstrip("\n")
                else:
                    new_content = header + new_content
            else:
                new_content = header + new_content

        # Output to skill directory
        output_file = skill_dir / 'SKILL.md'

        changed = True
        if output_file.exists():
            try:
                current_content = output_file.read_text()
                changed = new_content != current_content
            except:
                pass

        if check:
            if changed:
                click.echo(f"⚠️  {category}/{skill_name} - Needs rebuild")
                built_count += 1
            else:
                skipped_count += 1
        elif dry_run:
            if changed:
                click.echo(f"🔨 Would rebuild: {category}/{skill_name}")
                built_count += 1
            else:
                skipped_count += 1
        else:
            if changed:
                try:
                    output_file.write_text(new_content)
                    click.echo(f"✅ Built: {category}/{skill_name}")
                    if phase_templates:
                        click.echo(f"   Phases: {', '.join(sorted(phase_templates.keys()))}")
                    built_count += 1
                except Exception as e:
                    click.echo(f"❌ Error writing {output_file}: {e}", err=True)
            else:
                skipped_count += 1

    # Summary
    click.echo()
    if check:
        if built_count == 0:
            click.echo("✅ All skills are current")
        else:
            click.echo(f"⚠️  {built_count} skill(s) need rebuilding")
    elif dry_run:
        click.echo(f"📋 Dry-run: {built_count} would be rebuilt, {skipped_count} up-to-date")
    else:
        click.echo(f"✅ Built: {built_count}, skipped: {skipped_count}")


# =============================================================================
# skills deploy
# =============================================================================

@cli.command('deploy')
@click.option('--source', '-s', type=click.Path(exists=True),
              help='Skills source directory')
@click.option('--target', '-t', type=click.Path(),
              help='Target directory (default: ~/.claude/skills)')
@click.option('--dry-run', is_flag=True, help='Show what would be deployed')
def deploy_skills(source: Optional[str], target: Optional[str], dry_run: bool):
    """Install skills to ~/.claude/skills/.

    Copies skill directories to the target location and creates
    symlinks for Claude Code discovery.

    \b
    Examples:
      skills deploy                           # Deploy from auto-detect to ~/.claude/skills
      skills deploy --source ./skills/src     # Deploy from specific source
      skills deploy --target /path/to/target  # Deploy to specific target
      skills deploy --dry-run                 # Preview what would be deployed
    """
    # Determine source
    if source:
        skills_src = Path(source)
    else:
        cwd = Path.cwd()
        for path in [cwd / 'skills' / 'src', cwd / 'src']:
            if path.exists():
                skills_src = path
                break
        else:
            click.echo("❌ Could not find skills source directory", err=True)
            raise click.Abort()

    # Determine target
    if target:
        target_dir = Path(target)
    else:
        target_dir = Path.home() / '.claude' / 'skills'

    if not skills_src.exists():
        click.echo(f"❌ Source not found: {skills_src}", err=True)
        raise click.Abort()

    # Create target if needed
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    deployed_count = 0
    categories = ['worker', 'shared', 'utilities', 'meta', 'policy']

    click.echo(f"📦 Deploying skills from {skills_src}")
    click.echo(f"   Target: {target_dir}")
    click.echo()

    for category in categories:
        category_src = skills_src / category
        if not category_src.exists():
            continue

        for skill_dir in sorted(category_src.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            # Check for SKILL.md
            skill_md = skill_dir / 'SKILL.md'
            if not skill_md.exists():
                continue

            skill_name = skill_dir.name
            dest_category_dir = target_dir / category
            dest_skill_dir = dest_category_dir / skill_name

            if dry_run:
                click.echo(f"📦 Would deploy: {category}/{skill_name}")
                deployed_count += 1
                continue

            try:
                # Create category directory
                dest_category_dir.mkdir(parents=True, exist_ok=True)

                # Remove existing
                if dest_skill_dir.exists():
                    if dest_skill_dir.is_symlink():
                        dest_skill_dir.unlink()
                    else:
                        shutil.rmtree(dest_skill_dir)

                # Copy skill directory
                shutil.copytree(skill_dir, dest_skill_dir, dirs_exist_ok=True)

                # Make SKILL.md read-only
                dest_skill_md = dest_skill_dir / 'SKILL.md'
                if dest_skill_md.exists():
                    dest_skill_md.chmod(0o444)

                # Create top-level symlink
                alias_path = target_dir / skill_name
                if not alias_path.exists():
                    alias_path.symlink_to(dest_skill_dir.relative_to(target_dir))

                click.echo(f"✅ Deployed: {category}/{skill_name}")
                deployed_count += 1

            except Exception as e:
                click.echo(f"❌ Error deploying {skill_name}: {e}", err=True)

    click.echo()
    if dry_run:
        click.echo(f"📋 Dry-run: {deployed_count} skill(s) would be deployed")
    else:
        click.echo(f"✅ Deployed {deployed_count} skill(s)")


# =============================================================================
# skills new
# =============================================================================

@cli.command('new')
@click.argument('path')
@click.option('--output', '-o', type=click.Path(),
              help='Output directory (default: current directory)')
@click.option('--template', '-t', is_flag=True,
              help='Create templated skill with src/ and phases/')
def new_skill(path: str, output: Optional[str], template: bool):
    """Scaffold a new skill.

    PATH should be in format: category/skill-name

    \b
    Examples:
      skills new worker/my-feature      # Create simple skill
      skills new worker/complex --template  # Create templated skill
      skills new shared/helpers -o ./skills/src
    """
    # Validate path format
    if '/' not in path:
        click.echo("❌ Invalid path format. Expected: category/skill-name", err=True)
        click.echo("   Example: skills new worker/my-skill", err=True)
        raise click.Abort()

    parts = path.split('/', 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        click.echo("❌ Invalid path format. Expected: category/skill-name", err=True)
        raise click.Abort()

    category, skill_name = parts

    # Determine output directory
    if output:
        base_dir = Path(output)
    else:
        base_dir = Path.cwd()

    skill_dir = base_dir / category / skill_name

    if skill_dir.exists():
        click.echo(f"❌ Skill already exists: {skill_dir}", err=True)
        raise click.Abort()

    try:
        skill_dir.mkdir(parents=True)

        if template:
            # Create templated skill structure
            src_dir = skill_dir / 'src'
            src_dir.mkdir()

            phases_dir = src_dir / 'phases'
            phases_dir.mkdir()

            # Create template file
            (src_dir / 'SKILL.md.template').write_text(f"""---
name: {skill_name}
skill-type: procedure
audience: {category}
spawnable: true
description: TODO: Add description

deliverables:
  workspace:
    required: true
    description: "Workspace file with progress tracking"
---

# {skill_name.replace('-', ' ').title()}

TODO: Add skill guidance here.

<!-- SKILL-TEMPLATE: main -->
<!-- /SKILL-TEMPLATE -->
""")

            # Create placeholder phase
            (phases_dir / 'main.md').write_text(f"""# Main Phase

TODO: Add phase content here.

## Steps

1. First step
2. Second step
3. Third step
""")

            click.echo(f"✅ Created templated skill: {category}/{skill_name}")
            click.echo(f"   Template: {src_dir / 'SKILL.md.template'}")
            click.echo(f"   Phases: {phases_dir}/")
            click.echo()
            click.echo("Next steps:")
            click.echo("  1. Edit src/SKILL.md.template")
            click.echo("  2. Add phase files in src/phases/")
            click.echo("  3. Run: skills build")

        else:
            # Create simple skill
            (skill_dir / 'SKILL.md').write_text(f"""---
name: {skill_name}
skill-type: procedure
audience: {category}
spawnable: true
description: TODO: Add description

deliverables:
  workspace:
    required: true
    description: "Workspace file with progress tracking"
---

# {skill_name.replace('-', ' ').title()}

TODO: Add skill guidance here.

## When to Use

- Use case 1
- Use case 2

## Workflow

1. First step
2. Second step
3. Third step

## Completion Criteria

- [ ] Criterion 1
- [ ] Criterion 2
""")

            click.echo(f"✅ Created skill: {category}/{skill_name}")
            click.echo(f"   File: {skill_dir / 'SKILL.md'}")

    except Exception as e:
        click.echo(f"❌ Error creating skill: {e}", err=True)
        raise click.Abort()


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == '__main__':
    cli()
