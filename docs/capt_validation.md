# Capt HUD validation example

The user identified `Hase Faze` as their in-game name and labelled the
00:55–00:57 encounter in a local Majestic recording as a successful peek and kill.
The video and extracted frames are not committed.

Observed sequence:

| Time | Visible evidence |
| --- | --- |
| 00:55 | Player beside cover; ammo 38/357. |
| 00:56 | Opponent in red visible beyond the low barrier; ammo 33/352. |
| 00:56.5 | Damage numbers are visible near the opponent; ammo 28/347. |
| 00:57 | Ammo 24/343; kill feed reads `Hase Faze → Joe Forbes`. |

The capt HUD reader should find 14 rounds used, one confirmed personal kill,
and a limited 8.5/10 outcome/efficiency score for this encounter. A different
player's kill-feed entry in the same clip must not count as the sender's kill.
The transparent provisional rubric is `clamp(10 - 0.15 × max(rounds - 4, 0), 5, 9)`
for a kill with a visible ammo decrease in the preceding four seconds. It is
shown only when the supplied player name matches the killer in the feed.
The score does not validate aim tracking, the damage source, whether the peek
was safe, or overall capt performance. Training such judgments requires many
independently labelled encounters and held-out recordings.

On the full 6:00 source recording, the reader found at least two exact-name
kill-feed entries: `Hase Faze → Joe Forbes` at 00:57 and
`Hase Faze → Parker Forbes` at 05:32. The latter was manually checked in a
frame. The two limited encounter scores average to 7.8/10; this is still not
a score for the full capt. OCR may miss other entries, so counts are lower
bounds rather than a complete match record.
