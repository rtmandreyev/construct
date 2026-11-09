---
title: Documentation to product
summary: Placeholder, not written yet: this tutorial waits for its documentation page, so treat its steps as a rough outline only.
group: Makers and creators
needs: browser
time: about 30 minutes
status: placeholder
---

## Prompt

Teach me to turn a product's documentation into a construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/11-documentation-to-product.md"). Tell me first that this tutorial is still a placeholder.

## Steps

1. **Say it plainly.** This tutorial is a placeholder until its documentation page is written. Offer to go on with
   the general loop below, or to pick a finished tutorial instead (`01-copy-your-thing.md`, `06-cad-and-step.md`).
2. **Gather the documents.** Ask for what the user has: a datasheet, a manual, dimensioned drawings, a parts list,
   photos. Only material they are allowed to use.
3. **Facts first.** `construct_start(title=..., category="machine")` (or `object`). Each size from a document is
   `verified`, with that document as its source (title and page); each from a photo `inferred` with a note. Leave out
   what the documents do not say.
4. **Parts, check, build.** Named parts as the documents name them; `construct_check(fit=true)` until clean;
   `construct_build`, MEDIA line in the reply; **P** shows which sizes came from the documents.
5. **Export** as the user needs: `glb`, `3mf`, or `step` with FreeCAD.

**What next:** `06-cad-and-step.md`, `01-copy-your-thing.md`.

## Notes

- Placeholder: the owner will replace this file when the documentation page lands. Do not present it as a finished
  workflow.
