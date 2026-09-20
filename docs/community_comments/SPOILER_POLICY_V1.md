# Spoiler Policy V1

## Definition

A spoiler is content that reveals plot outcomes, deaths, endings, or major
twists for a title that a reader may not have finished.

## Author controls

- Authors may mark `spoiler=true` on create.
- UI collapses spoiler bodies behind an explicit control (`aria-expanded`).

## System / moderator controls

- Heuristic `spoiler_suggested` may set the spoiler flag at create/edit.
- Moderators may `mark_spoiler` without rewriting text.
- Silent rewrite of spoiler text is forbidden.

## Display

- Spoiler bodies are not shown until the reader expands them.
- Public SEO rendering of spoiler (and all) comment bodies stays OFF
  (`COMMENTS_SEO_RENDERING_ENABLED=0`).
