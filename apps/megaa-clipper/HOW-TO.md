# MeGaA Clipper – how to use it

MeGaA Clipper turns a long video (podcast, stream, interview) into short **vertical 9:16 clips**
with big word-by-word captions, ready for TikTok, Reels and Shorts.

Everything runs on your PC. Nothing is uploaded anywhere.

> **New: QML edition.** Double-click **MeGaA Clipper QML** on your desktop (or **MeGaA Clipper QML.bat**).
> Same engine and same projects, but a native Qt window drawn on the GPU. It has everything in this guide,
> plus the **razor** (see "Cut the timeline" below), which only the QML edition has.
> Where things are in the QML edition: **★** in the transcript header = viral moments · the **campaign chip**,
> **$** (earnings) and **⚙** (settings) are in the top bar · **↶ ↷** = undo / redo · the **✓** on a rendered
> clip's card = mark as posted · **Export pack** / **ZIP** are in the queue header.
> Clips made in one edition open in the other.

---

## Way 1 – the app (by yourself)

1. Double-click **MeGaA Clipper** on your desktop (or **MeGaA Clipper.bat** in this folder).
   It opens in its own window. Close the window to quit.
2. Click **Open a video** (or pick one from **Recent projects**).
3. Choose the language and click **Transcribe**. A 1-hour video takes about 2–5 minutes.
4. Find a good moment in the transcript on the left:
   - **Click** a line to start the clip there, **Shift + click** a later line to end it.
   - **Double-click** a line to play from there.
   - Type in **Search** and press Enter to jump between matches.
5. Fine-tune on the waveform under the preview:
   - Drag the **cyan handles** to trim the start/end (they snap to word edges; hold Alt to stop snapping).
   - Or play the video and press **I** (start) and **O** (end).
6. The phone preview shows exactly what the clip will look like – crop, captions, hook.
   - **Crop**: fills the screen with part of the video.
   - **Fit + blur**: the whole video over a blurred background (good for 2 people).
   - **Zoom**: scroll the mouse wheel on the preview (or use the Zoom slider) to make the video bigger
     or smaller. Fit goes from 50% to 250%, Crop from 100% to 250%.
   - **Move**: drag the preview to move the video left/right/up/down. **Reset** puts it back.
   - **Safe zones** shows where TikTok's buttons and text will cover the video.
7. Add a **Hook** (text on top) and pick its look: **White box, Dark box, Red alert, Yellow,
   Outline, Neon, Meme**. Change its **size** and **height**, and choose how long it shows
   (**whole clip, 3 s, 5 s or 8 s** – it fades out). **Hook look → all clips** copies the look to the queue.
   Add a **Post caption** if you want.
8. Open the **Captions** tab to choose the caption look:
   - **Classic** – yellow spoken word · **Bold Pop** – big green word that grows
   - **Box** – spoken word on a coloured box · **Neon** – glowing outline
   - **Karaoke** – words fill in as they're said · **One Word** – one big word at a time
   - **Minimal** – clean sentence case · **Retro** – Cooper Black with orange outline
   - Change the **highlight colour**, **size** and **height on screen** – the preview updates live.
   - **Apply to all clips** gives every clip in the queue the same look.
9. Open the **Edit** tab for pro editing (the preview and the "Final length" update live):
   - **Teaser at the start** – plays a 3–5 s highlight first, then the clip from the beginning
     (the "cold open" trick). Turn it on and it auto-picks the most energetic moment, or:
     **Pick words** (click the first word, then the last word in the transcript),
     **Auto pick**, the **I / O** buttons (playhead), or type the times. **Play** shows just the teaser.
     **Flash** adds a quick white flash where the teaser ends. The teaser shows **amber** in the
     transcript and on the timeline.
   - **Remove pauses** – cuts silences automatically (jump cuts). The slider sets how long a pause must be.
   - **Cut tool ✂** – turn it on (or press **X**), then click words in the transcript to remove them
     from the clip – "um", mistakes, boring bits. Shift+click removes a run of words. Click again to bring a word back.
   - **Mute tool 🔇** – turn it on (or press **M**), then click words in the transcript to silence them
     (swear words, names). The video keeps playing – only the sound goes. Shift+click mutes a run of words.
     Pick the sound for muted words (click one to hear it): **Silence**, **Bleep** (TV-style beep for the
     whole word), or a one-shot effect that plays where the word starts: **Boom, Pop, Boing, Ding, Buzzer,
     Whoosh** – or **Custom** to use your own sound file (mp3/wav). **Effect volume** sets how loud it is.
     **Censor captions** shows muted words as "f***".
     Muted words get a violet wavy underline, and a violet bar on the waveform.
   - **Zoom punch-ins** – zooms in and out on every cut / sentence for that dynamic podcast look.
   - **Speed** – 1.1× to 1.3× makes clips snappier.
   - **Progress bar** – a coloured bar along the bottom that fills up as the clip plays.
   - **Background music** – pick an mp3/wav/m4a; it gets quieter automatically while someone talks.
   - **Watermark** – your @handle in a corner.
   - **Apply to all clips** copies these settings (not the cuts) to the whole queue.
   - Audio is always levelled to −14 LUFS, the TikTok / Reels / Shorts standard.
   - On the waveform, cut parts show **red** and zoomed parts **violet**.
10. **Cut the timeline (razor – QML edition):** the bar under the play button works like CapCut.
    - Move the playhead and press **S** (or click **Split**) – a white line cuts the clip into parts.
    - **Click a part** on the waveform to pick it (white frame), then press **Delete** (or click **Delete**) to
      remove it from the clip. It turns red with stripes. Press Delete again (**Restore**) to bring it back.
    - This works on any part – talking, silence, music – not only on words.
    - **Double-click** (or right-click) a white line to remove it.
    - **To clips** makes each part its own clip in the queue (clip_01_p1, clip_01_p2…). Every part keeps the
      captions, hook and edit settings and renders as its own video. Deleted parts are left out.
11. **Fix a misheard word:** hover a transcript line, click the ✎ pencil, type the right text, press Enter.
12. Click **Render clip** – or **Add to queue**, pick more moments, then **Render all**.
13. Click the ▶ on a clip card to watch it, or **Open folder** to get the files.

### Pro tools

- **✨ Moments** (transcript header) – finds the best clips in the video and scores them. **Find (free)** works
  offline; **AI picks** asks Claude (needs your Anthropic API key in **Settings ⚙**, about $0.10–0.20 per hour of
  video). **Preview** a moment, **Add** it, or **Add all to queue**.
- **Campaigns** (chip in the top bar) – save each Whop campaign's rules: pay per 1,000 views, min/max length,
  required tags, watermark, "no hook", "captions required", max speed. Click **Use for this video** and every
  clip is checked: the Clip tab shows a rule box, cards get a ⚠ badge, and you're warned before rendering.
- **Undo / Redo** – Ctrl+Z / Ctrl+Y (or the arrows in the top bar).
- **Keyword colours & emojis** (Captions tab) – money, numbers and strong words get their own colour,
  and a matching emoji 💰🔥🤯 pops up above the captions.
- **Pop-ups** (Edit tab) – put the playhead where you want it, **Add at playhead**, pick a picture, GIF or short
  video. Set how long it shows, its size and top / center / bottom.
- **Speaker switches** (Clip tab) – for 2-person podcasts: move the playhead to where the other person talks,
  **+ Switch here**, then drag the preview to frame them. The crop jumps at each switch.
- **Earnings tracker** ($ in the top bar) – after posting, click ✓ on the clip card, pick the platform and paste
  the link. Type in the views as they grow: it shows your estimated earnings (views × the campaign's pay rate),
  totals per campaign, and which caption style / layout / teaser gets the most views.
- **Export pack** / **ZIP** (queue) – copies every rendered clip with a clear name plus `captions.txt`
  (post captions with the campaign's required tags) into `clipper\exports\`.

### Keyboard shortcuts

| Key | Does |
|---|---|
| Space | play / pause |
| I / O | set start / end at the playhead |
| J / L | back / forward 5 seconds |
| ← / → | back / forward 1 second (Shift = 0.1 s) |
| Enter | add the clip to the queue (Shift+Enter = render it now) |
| X | cut tool on / off |
| M | mute tool on / off |
| S | split the clip at the playhead (razor, QML edition) |
| Delete | delete / restore the picked part (Esc = unpick) |
| Ctrl+Z / Ctrl+Y | undo / redo |
| / | search the transcript |

---

## Way 2 – ask Claude to pick the moments

1. Transcribe the video in the app.
2. In Claude, say something like:
   *"Pick the 10 best clips from projects/MyVideo and render them."*
3. Claude reads the transcript, chooses the strongest hooks, writes `clips.json`
   (with hook text and post captions) and renders them. They show up in the app's queue.

---

## Way 3 – command line

Run these in the `clipper` folder:

```
python clipper.py transcribe "D:\videos\podcast.mp4"
python clipper.py search "D:\videos\podcast.mp4" "money"
python clipper.py cut "D:\videos\podcast.mp4" --start 12:30 --end 13:05 --hook "This changed my life"
python clipper.py cut "D:\videos\podcast.mp4" --start 12:30 --end 13:05 --layout fit
python clipper.py render "D:\videos\podcast.mp4"
```

Times can be written as `750`, `12:30`, `12:30.5` or `1:02:03`.
`--crop-x` moves the crop: `0` = left, `0.5` = centre, `1` = right.
`--style` picks the caption look (`classic`, `bold`, `box`, `neon`, `karaoke`, `oneword`, `minimal`, `retro`)
and `--color "#39FF14"` changes its highlight colour.

---

## Where things are saved

```
clipper\projects\<video name>\
    transcript.txt      readable transcript with times
    clips.json          your clip queue
    out\                finished clips (.mp4) + post_captions.txt
```

## Rules to remember for Whop campaigns

- Follow each campaign's rules: tags, captions, length, watermarks.
- Only clip videos the campaign gives you.
- Watch every clip before posting – auto captions can mishear names.
