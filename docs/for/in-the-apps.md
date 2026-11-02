# Construct in the Claude or ChatGPT app

You don't need a terminal or any code. If you have the Claude app or the ChatGPT app on a Mac or a PC, with a paid
plan, the app does the work: you give it a folder, some photos and one message, and it comes back with a
construct, a page you open in your browser.

Tested in November 2026: in the Claude app with **Cowork** (Claude Opus 5.5), and in the ChatGPT app with **Codex**
(GPT-6.1 Sol). Both built the same chair from two photos in masterpiece mode, the Claude app in about half an hour
of work, the ChatGPT app in about an hour.

## Once: get Construct

1. On [Construct's GitHub page](https://github.com/rtmandreyev/construct), click the green **Code** button, then
   **Download ZIP**.
2. Double-click the zip to unpack it. You get a folder called `construct-main`. Leave it in Documents or anywhere
   you like.
3. Inside it, make a new folder for your thing, say `my-chair`, and put your photos in it.

## In the Claude app: Cowork

1. Open the Claude app and choose **Cowork** (beside **Chat**, next to the send button).
2. When it asks which folder to work in, choose the `construct-main` folder.
3. Paste your message (each [use case](../../README.md#find-your-path) has one to copy), starting with:
   *"Read skills/construct/SKILL.md in this folder and use the Construct skill to make..."*
4. Leave it working. It may stop for a while if you reach your plan's usage limit, and carry on when the limit
   resets.

Cowork keeps its working files in the app's own space, so the message asks it to save the result into your folder
(*"Save it as my-chair/my-chair.html"*).

## In the ChatGPT app: Codex

1. Open the ChatGPT app and go to **Codex**. Start a task in the `construct-main` folder.
2. The first time only, send:
   *"Install the skill in skills/construct for yourself: copy it to ~/.codex/skills/construct. Tell me when it is
   done."*
3. Start a **new** task in the same folder (so it picks up the skill) and paste your message, starting with
   *"Using the construct skill, make..."*

## When it is done

Double-click the `.html` file it saved: it opens in your browser. Drag to turn it, scroll to zoom, **R** replays it
being built, **P** shows how each part is known (measured, read from your photos, or guessed), **S** shows it as a
solid.

Then just ask, in the same chat, in plain words:

- *"Make it a file I can 3D print, 20 cm tall."*
- *"Make it a model kit at 1:12, with a booklet."*
- *"Give me a STEP file for CAD"* or *"a file for Blender."*
- *"Change the seat to green leather"*, *"make the shed 2 m wider"*.

## Good to know

- **Masterpiece or fast.** Masterpiece (rounds judged by a second, independent model) takes 30 to 60 minutes and
  is worth it for anything you care about; fast takes about 10 minutes.
- **Give each thing its own file name.** Two runs in one folder that both save `construct.html` overwrite each other.
- **It is a model, not a survey.** What you measured and what the maker publishes are marked as such; everything
  read from photos or designed is marked too (press **P**). Check the measurements that matter before you cut,
  order or print a part to fit.
- **Your photos go to the AI service** you use, like anything you send it. Leave out what you would not share.
- **Work or school accounts** may not allow everything (custom skills, code); the routes above worked on an
  account where uploading a skill was not allowed.
