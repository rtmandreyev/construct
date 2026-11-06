---
title: A film to music
summary: A construct assembling across a piece of music, pausing in quiet passages and surging in loud ones, as a video.
group: Makers and creators
example: sainte-chapelle
needs: browser, ffmpeg
time: about 15 minutes, then the render (about an hour for four minutes of music)
status: ready
---

## Prompt

Teach me to make a film of a construct assembling to music, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/08-film-to-music.md"). Start by showing me the Sainte-Chapelle example.

## Steps

1. **Show the example.** `construct_start(example="sainte-chapelle")` and `construct_build`; MEDIA line in the
   reply. Ask the user to replay the assembly: that build is what the film stretches across the music.
2. **Can it film here?** A film needs a Chromium-family browser and ffmpeg; `construct_start()` with no arguments
   says which are found. Without them, say so plainly; Construct never installs them.
3. **A short test first.** `construct_film(project=<id>, seconds=12, camera="steady")`, no music: it returns a
   `job_id` at once. Say what is running, then `construct_job(job_id, wait_seconds=...)` until done, and put its MEDIA
   line in the reply.
4. **The music.** Ask for a music file of their own (any format ffmpeg reads) and, optionally, a separate vocal
   stem. Warn before starting: about 1 to 2 frames a second, so about an hour for four minutes of music.
5. **The film.** Keep the scene's own assembly at most 20 s (the film stretches it). Then
   `construct_film(project=<id>, track="/path/track.wav", camera="steady")`, with `voice="/path/vocals.wav"` if
   they gave a stem (it shimmers while the voice is present); `size="1920x1080"` only if they ask. Follow it with
   `construct_job`. Change `reactivity` only when they ask for calmer (0.5) or stronger (1.5).
6. **Look before handing over.** When it is done, look at a few frames if you can: the build should visibly move
   on with the music and end whole. Report the length, the camera and the reactivity, and put the MEDIA line in
   the reply.
7. **The user's own construct.** Any construct films the same way: one from another tutorial, or a new one.
   `camera="tour"` plays the scene's own camera flights instead of a steady view.

**What next:** `09-invent-from-real-designs.md` (design something for a film), `16-netlogo-film-and-plates.md`
(a NetLogo run as a film).

## Notes

- Use music the user has the right to use; the film carries the track.
- A film is rendered in the background and stops if the plugin unloads; `construct_job(job_id, cancel=true)` stops it.
