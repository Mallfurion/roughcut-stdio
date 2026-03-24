# Project Manifesto

## Core Idea

This project exists for one reason:

`there is too much footage to watch manually`

The tool should help an editor move from a large pile of raw videos to a usable shortlist of strong moments without having to scrub every clip from start to finish.

It is not trying to replace editing.
It is trying to remove the most repetitive and expensive part of editing:

- reviewing everything
- remembering where the good moments are
- finding the visually strong shots again later
- building the first rough selection from a large volume of media

## Problem Statement

When a project contains many videos, the bottleneck is not export or final polish.
The bottleneck is attention.

The editor has to answer questions like:

- which parts of this footage are actually worth watching closely?
- where are the good shots?
- which segments have a clear subject?
- which shots have useful motion, composition, or energy?
- which moments feel visually interesting enough to keep?
- how can those moments be assembled into a first rough timeline?

This project should answer those questions as early and as reliably as possible.

## Product Mission

Find the good parts of the footage.

More specifically, the system should:

- scan a large set of videos
- detect candidate segments inside each clip
- identify the visually strong or editorially useful moments
- prefer shots with subject, motion, composition, clarity, and interest
- grade and explain those moments
- assemble them into a rough timeline the editor can inspect and refine

The first promise of the product is not "storytelling intelligence".
The first promise is:

`show me the parts of the footage that are actually worth my time`

## What Counts As A Good Segment

A good segment is usually one that has some combination of:

- a readable subject
- clear framing
- meaningful motion
- visual interest
- useful composition
- change or energy inside the shot
- editorial usability as a cutaway, bridge, opener, payoff, or texture shot

Not every good segment needs dialogue.
Not every good segment needs explicit narrative meaning.

For many projects, especially b-roll-heavy ones, a good shot is simply:

- visually strong
- usable in an edit
- better than the surrounding footage

## Product Philosophy

### 1. Reduce Viewing Burden

The main job is to reduce how much footage the editor must watch.

The system should act like an intelligent first-pass screener:

- narrow the search space
- surface promising moments
- avoid wasting the editor's attention on weak footage

### 2. Optimize For Editorial Usefulness

The system should not chase generic computer-vision outputs for their own sake.

The standard is not:

- "can it label objects in a frame?"

The standard is:

- "does this help an editor choose shots faster and better?"

### 3. Visual Strength Before Narrative Complexity

The first layer of value is shot selection, not full story construction.

The tool should become excellent at:

- good shots
- interesting segments
- subject + motion
- composition + usability

before it tries to become ambitious about larger-scale narrative assembly.

### 4. AI Should Help, Not Obscure

Every recommendation should be inspectable.

The system should be able to show:

- what segment it selected
- why it selected it
- how strong it thinks that segment is
- what visual traits made it interesting

If the user cannot understand why a segment was surfaced, trust will collapse.

### 5. The Editor Stays In Control

The system proposes.
The editor decides.

This project should accelerate editorial judgment, not replace it.

## Scope

The project should do four things well:

1. ingest large amounts of footage
2. surface the best-looking or most usable segments
3. grade and explain those segments
4. assemble a rough timeline from them

Everything else is secondary.

That means the product is fundamentally:

- a footage screening tool
- a shot selection tool
- a rough-cut assistant

It is not a full nonlinear editor.

## Non-Goals

This project is not primarily about:

- final creative authorship
- color grading
- advanced finishing
- replacing DaVinci Resolve
- fully autonomous editing

Those may connect to the workflow later, but they are not the product core.

## Success Criteria

The project is successful if it makes these statements true:

- "I no longer have to watch every second of footage."
- "The tool reliably surfaces the shots I would probably keep."
- "I can find the interesting parts of a clip quickly."
- "I can build a first rough timeline from shortlisted moments instead of from raw footage."
- "The output is good enough to continue editing in Resolve."

## Product Description

This is a local-first AI-assisted footage screening and rough-cut tool.

It analyzes a large set of videos, finds the strongest visual segments, grades them based on qualities like subject, motion, composition, and interest, and assembles those selections into a first-pass timeline.

Its purpose is to help editors avoid scrubbing through all raw footage manually and move faster from media ingestion to usable shot selection.

At its best, the product behaves like a smart assistant that says:

`these are the parts of the footage you should look at first`

and then:

`here is a rough timeline built from those strongest moments`
