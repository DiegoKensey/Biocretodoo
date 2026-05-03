# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running Odoo

```bash
# Start the server
python odoo-bin -d <database> --addons-path=addons,odoo/addons

# Start with a config file
python odoo-bin -c /path/to/odoo.conf
```

## Running Tests

```bash
# Run all tests for a module
python odoo-bin -d <database> --test-enable -u <module> --stop-after-init

# Run a specific test class
python odoo-bin -d <database> --test-enable --test-tags /module_name:TestClass --stop-after-init

# Run a specific test method
python odoo-bin -d <database> --test-enable --test-tags /module_name:TestClass.test_method --stop-after-init
```

## Linting

```bash
# Ruff (primary linter — config in ruff.toml)
ruff check .
ruff check --fix .

# Flake8 (secondary — config in setup.cfg)
flake8 .
```

Import order follows the Odoo convention (enforced by ruff isort):
`future` → `standard-library` → `third-party` → `first-party (odoo)` → `local-folder (odoo.addons)`

## Architecture Overview

### Repository Layout

- `odoo/` — Core framework (ORM, HTTP, CLI, tools)
- `addons/` — First-party Odoo apps/modules
- `odoo/addons/` — Core modules bundled with the framework (base, web, mail…)
- `odoo-bin` — Entry point; delegates to `odoo.cli` commands

### ORM Layer (`odoo/orm/`)

The ORM is the heart of the framework. Key files:

- `models.py` — `BaseModel`, `Model`, `AbstractModel` base classes
- `models_transient.py` — `TransientModel` (wizard/temporary records)
- `environments.py` — `Environment` (registry + cursor + uid + context)
- `decorators.py` — `@api.depends`, `@api.constrains`, `@api.onchange`, `@api.model`, etc.
- `fields.py` + `fields_*.py` — Field type definitions
- `domains.py` — Domain expression evaluation
- `registry.py` — Per-database model registry (`Registry`)
- `table_objects.py` — `Index`, `Constraint`, `UniqueIndex` declarative DB constraints

`odoo/models/` and `odoo/api/` are thin re-export shims to avoid merge conflicts — the real code lives in `odoo/orm/`.

### Module System (`odoo/modules/`)

- `loading.py` — Module install/upgrade pipeline
- `registry/` — Registry lifecycle (per-database model class merging)
- `module.py` — Module path resolution and manifest parsing

Each addon must have a `__manifest__.py` dict and an `__init__.py`. The manifest declares `depends`, `data` XML/CSV files, `assets`, etc.

### HTTP Layer (`odoo/http.py`)

Routes are registered via `@http.route(...)` on controller methods. Controllers inherit from `odoo.http.Controller`. JSON-RPC (`type='json'`) and regular HTTP (`type='http'`) routes coexist.

### CLI (`odoo/cli/`)

Each subcommand (server, shell, scaffold, db, deploy, …) is a `Command` subclass. The command name must match the module filename.

### Testing (`odoo/tests/`)

- `TransactionCase` — each test runs in a transaction that is rolled back
- `SavepointCase` — tests share one transaction with savepoints between them (faster)
- `HttpCase` — spins up a full HTTP server; supports `browser_js` for tour tests
- `Form` — programmatic form view interaction helper for write-path tests

Tag tests with `@tagged('tag1', 'tag2')` and filter with `--test-tags`.

### Inheritance Patterns

Odoo uses three inheritance types declared in `__manifest__.py` / model class:

- `_name` (new model) — creates a new DB table
- `_inherit` without `_name` (in-place extension) — adds fields/methods to existing model
- `_inherit` with `_name` (prototype/delegation inheritance) — copies behavior to a new model
