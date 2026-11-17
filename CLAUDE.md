# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`taw` (Tiny Amazon ec2 Wrapper) is a deliberately-simplified command-line wrapper over `boto3` for Amazon EC2, S3, and Route 53. It targets researchers and small labs who are *not* AWS experts, so the design bias is: expose a small number of high-level operations with sane defaults, accept human-friendly names instead of AWS IDs, and hide the low-level API surface. When adding features, prefer that ergonomic bias over completeness.

## Commands

The project is managed with **uv** (`pyproject.toml`, PEP 621; hatchling build backend). There is **no automated test suite** — changes are validated manually against a live AWS account, so use `--dryrun` (supported by state-changing commands) when exercising them.

```bash
uv sync                          # create ./.venv + install taw (editable) from the lockfile
uv sync --extra dev              # also install ruff (lint)
uv run taw <args>                # run the CLI (entry point taw.main:main)
uv run python -m taw.main <args> # equivalent (main.py has a __main__ guard)

uv run ruff check .              # lint (config in pyproject.toml [tool.ruff])
```

`.envrc` (direnv) activates `./.venv`; `.python-version` pins the interpreter (3.12) for uv. The lockfile `uv.lock` is committed — update deps via `uv add` / `uv lock`, not by hand-editing `pyproject.toml` pins.

Shell completion uses Click's native mechanism — run `taw completion` and it prints the correct `eval "$(_TAW_COMPLETE=... taw)"` line for the current shell. (`taw_completion.sh` is the legacy pre-Click-8 approach.)

## Architecture

**Entry / registration.** `taw/main.py` imports every subcommand module (`instance`, `bucket`, `zone`, `vpc`, `subnet`, `sg`, `keypair`, `ip`, `image`, `list`, `sshlike`, `shell`, `completion`) purely for their decorator side effects — importing a module attaches its commands to the shared Click group. `main()` wraps the root `taw()` invocation in botocore exception handling (friendly message for connection errors; treats the "DryRun flag is set" `ClientError` as success and exits 0).

**Root group.** `taw/taw.py` defines the `@click.group` named `taw` plus all **global options** (`--region/-r`, `--profile/-p`, `--format/-f`, `--noheader`, `--noless/-n`, `--debug`, `--dryrun`, `--subprocess`). It builds a `GlobalParameters` object into `ctx.obj`. Subcommands receive it by decorating with `@pass_global_parameters` and read `params.output_format`, `params.output_header`, `params.output_noless`, `params.aws_dryrun`, and `params.global_opt_str`.

> **Critical import rule:** every module ends its imports with `from taw.taw import *  # This must be the end of imports`. This must stay last, because it pulls in the `taw` group object that the module's decorators attach to.

**Shared library.** `taw/util.py` (~1400 lines) holds nearly all shared logic:
- **boto3 client/resource singletons** (`get_ec2_connection`, `get_s3_client`, `get_r53_connection`, …) — lazily created per region and **reset to `None` whenever `set_aws_region`/`set_aws_profile` changes the target**. Never cache a boto3 handle across a region switch.
- **Name↔ID resolution** — `convert_host_name_to_instance`, `convert_vpc_name_to_vpc`, `convert_subnet_name_to_subnet`, `convert_sg_name_to_sg`, `convert_ami_name_to_ami`, `convert_zone_name_to_zone_id`, `convert_eip_name_to_eip_id`. Each accepts *either* a raw AWS ID (matched by regex like `^i-[0-9a-f]+$`) *or* a `Name` tag, and errors on "not found" / "ambiguous". This is the core UX convention — new commands that take a resource should route user input through these.
- **Region nicknames** — `region_name_to_region_nickname` maps `ap-northeast-1`↔`tokyo`, etc. Nicknames are accepted anywhere a region is.
- **Output** — `output_table(params, header, rows, coloring=None)` is the universal renderer for `csv`/`tsv`/`json`/`simple`/`simple_with_color`. It auto-pipes to `less -S` when output exceeds the terminal (unless `--noless`). `coloring` is a list of functions, each taking a row and returning `{column_index: color}` (or `{-1: color}` for the whole row).
- Instance-type catalog, `/etc/services`-backed port parsing (`parse_protocol_port_string`), CIDR helpers (`expand_cidr_string` resolves `self` to your public IP via Google DNS), and the Marketplace AMI database (sqlite at `~/.aws/ami_db.sqlite3`).

**Resource modules.** Each AWS resource is one module exposing a `@taw.group(...)` with subcommands (see `instance.py` for the canonical pattern). `sshlike.py` implements `ssh`/`mosh`/`rssh`/`rsync`/`scp` (resolves host → instance, finds the `.pem` key in `~/.ssh/`, uses the instance's `root` tag for the login user). `shell.py` provides `taw shell py` (IPython embed). `list.py` implements the unified `taw list <restype>` which dispatches by *unambiguous prefix* via `call_function_by_unambiguous_prefix`.

## Key cross-cutting mechanisms

- **Command redirection via subprocess.** Some commands re-invoke `taw` as a child process rather than call a function. E.g. `taw list instance` shells out to `taw instance list`; `--allregions` fans out one child per region (through GNU `parallel`/`sem` if available, else serial). `params.global_opt_str` is the reconstructed list of global options that gets threaded to the child. The internal `--subprocess` flag makes the child print a region "fence" header so multi-region output stays labeled.
- **Dry run.** `--dryrun` sets `params.aws_dryrun`, passed straight to boto3 calls as `DryRun=`. AWS raises a `ClientError` saying the request *would* have succeeded; `main.py` detects that and exits 0.
- **Completion cache.** Running `taw instance list` / `taw zone list` writes name caches under `~/.taw/<profile>/`. The shell-completion callbacks (`click_complete_for_instances`, etc.) read those files, so tab-completion of instance names only works after a list has populated the cache.
- **`list` extras.** `taw list <type> --argdoc` opens the relevant boto3 docs page; `--attr/-a <name>` adds an arbitrary boto3 attribute as an extra column; `--verbose/-v` reveals the non-default columns.

## Conventions & gotchas

- **Version is single-sourced in `pyproject.toml`** (`version = "2.0.0"`). `taw.py` reads it at runtime via `importlib.metadata.version("tiny-amazon-wrapper")` for `--version`, falling back to `"0.0.0"` only when run from an uninstalled source tree. Bump the version in `pyproject.toml`.
- **Python 3.11+ only.** The old Python-2 scaffolding (`from __future__`, `six`, `ConfigParser` fallbacks) has been removed; `requires-python = ">=3.11"` (3.9 was dropped because botocore pins the vulnerable `urllib3 1.26.x` there; 3.10 was dropped because dnspython >= 2.9 — which fixes CVEs — requires 3.11). Don't reintroduce compat shims — use plain 3.x idioms and `import configparser` directly.
- **Errors exit, they don't raise.** Use `error_exit(msg)` (prints red, `sys.exit(2)`), `print_warning`, `print_info` for user-facing messaging rather than exceptions — matches how the whole codebase reports problems.
- **Linting is tuned, not strict.** `[tool.ruff.lint]` deliberately ignores the project's idioms (star imports `F403/F405`, semicolon/one-line imports, bare `except:`), but keeps the high-signal rules live — unused imports/locals (`F401`/`F841`), undefined names in non-star modules, and invalid regex escapes (`W605`). Keep new code passing `uv run ruff check .`.
