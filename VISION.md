# Trimmy Vision

Trimmy is a desktop video editor focused on turning a horizontal video into a
two-area vertical composition ready for publishing on social platforms. It must
provide a local, fast, and understandable workflow: open a video, define the
crops and timeline range, choose a target, and let FFmpeg produce the final
file.

The application is neither a web client in disguise nor a collection of remote
services. It is a desktop product: PySide6 provides the interactive experience
and FFmpeg/FFprobe perform local multimedia work. That decision does not reduce
the need for architectural boundaries; it makes the separation of the user
interface, use cases, and system integrations even more important.

## Product Goals

- Make it easy to create high-quality vertical clips from a local video source.
- Keep users in control of crops, composition ratio, timeline range, platform,
  format, and quality.
- Export predictable results through explicit presets and a replaceable
  rendering backend.
- Be usable as a graphical application and automatable through control entry
  points without duplicating business rules.
- Run locally and portably on desktop platforms supported by Python and
  PySide6.

## Architecture Model

Trimmy follows a modular hexagonal architecture. The unit protected by the
architecture is the **vertical module**, not a global technical layer. Every
business module has exactly these layers:

```text
<area>/<module>/
  domain/
  application/
  infrastructure/
```

Modules are grouped directly under business areas, without an intermediate
`contexts/` package. For example, `editing/crop` and `editing/trim` are
distinct modules inside the editing area. A module that does not need a second
level, such as `rendering` or `preferences`, uses the same three layers at its
own root.

This layout retains the CodelyTV-inspired vertical reading order—business
capability first, its layers second—and avoids a generic folder that hides the
product language.

### Domain

`domain` holds the ubiquitous language and rules that must remain valid
independently of PySide6, FFmpeg, JSON, CLI, or the filesystem:

- entities, aggregates, value objects, and specifications;
- pure domain services;
- domain events; and
- ports for repositories, gateways, and event buses when the domain needs to
  collaborate with the outside world.

The domain does not know frameworks, the graphical interface, or adapter
implementations. Values with their own rules or meaning must use explicit
types instead of ambiguous primitives.

### Application

`application` expresses user intent and coordinates the domain. Its use cases
receive ports through dependency injection, apply the required workflow, and
return results suitable for adapters. They do not create concrete backends,
repositories, system clients, or widgets.

### Infrastructure

`infrastructure` implements ports and isolates external dependencies: FFmpeg,
FFprobe, JSON files, in-memory storage, event-loop-aware buses, and other
technical integrations. Implementations can change without changing the
domain or its use cases.

## Entry Applications

The desktop UI is not a business bounded context. It is an application that
composes and consumes the modules:

```text
apps/desktop/
  bootstrap.py
  main_window.py
  views/
  widgets/
  controllers/
  presenters/
```

The desktop application can call use cases in-process; HTTP or an artificial
backend are not necessary to preserve hexagonal boundaries. The CLI and local
control are other input adapters and must invoke the same application
boundary, rather than manipulating widgets or private window state.

`bootstrap.py` is the composition root. It is the only place in an application
where the concrete adapter for each port is selected and repositories,
gateways, buses, and use cases are created. Widgets, views, workers, and
controllers receive their dependencies rather than constructing them.

## Dependency Rules

- `domain` does not depend on `application`, `infrastructure`, or `apps`.
- `application` depends on `domain` and its ports, never on infrastructure
  implementations.
- `infrastructure` can depend on `domain` and `application` to adapt ports,
  but not on `apps`.
- Applications can depend on business modules; business modules never depend
  on applications.
- Sibling modules do not import each other's internal details. Collaboration
  occurs through published contracts, events, or an explicit application
  boundary.
- `shared` contains only genuinely cross-cutting concepts and cannot depend on
  product modules.

## Source of Truth and Consistency

Business state must not live in widgets. The interface holds only ephemeral
presentation state—focus, visual selection, window geometry, or animations.
The state that defines an edit, crop, timeline range, preference, or render
belongs to the domain or an explicit application boundary and changes through
use cases.

Global user preferences are distinct from the state of an edit. Repositories
persist aggregates or configurations with a clear identity; they are not used
to hide mutable widget state.

## Design Criteria

When making design decisions, Trimmy prioritizes:

1. **Clear business language.** Names represent editing and rendering concepts,
   not accidental UI or FFmpeg details.
2. **Inward dependencies.** Core logic must be testable without starting Qt,
   FFmpeg, or the filesystem.
3. **Small, explicit modules.** A module is created when it has its own
   language, rules, or change cycle; generic packages such as `utils`,
   `common`, or `helpers` are avoided.
4. **Replaceable adapters.** FFmpeg, FFprobe, persistence, and messaging are
   represented through ports and connected in the composition root.
5. **Explicit DI.** Constructor injection is preferred over global state,
   service locators, or UI-distributed wiring.
6. **Desktop pragmatism.** Process separation is not forced when in-process
   package, contract, and dependency boundaries are sufficient.
7. **Safe evolution.** Important architecture decisions are encoded as
   executable standards, not documentation alone.

## Continuous Verification

Standards tests are part of the architectural product. They verify module and
layer structure, import direction, framework isolation from the domain,
independence between sibling modules, the one-way dependency from `apps` to
the core, and composition centralization in bootstraps.

Quality is completed by formatting, linting, static type checking, unit tests
with strict core coverage, and a check that the distributable package builds
and installs correctly. The goal is not ceremony: it is to prevent a future
feature from eroding the boundaries that keep Trimmy maintainable.
