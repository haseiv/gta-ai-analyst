# Majestic HUD validation examples

These observations came from a user-provided 5:06 Majestic gameplay recording.
The video and extracted frames are **not** included in the repository.

| Time in clip | Human-visible evidence | Expected automated HUD result |
| --- | --- | --- |
| 01:00.5–01:04.5 | Ammo falls 32→8; kill counter remains 13; a player is visible by a blue dumpster. | Observe 24 rounds spent and no kill-counter increase. Do **not** call it a confirmed miss or failure to finish that player. |
| 04:00–04:01 | Kill counter rises 52→53 during a firefight. | Observe a kill-counter increase. Do **not** infer which player died from the counter alone. |

The current OCR is evidence extraction, not model training. To teach the bot
"did not finish the target," future annotations need target boxes/identities,
crosshair position, damage numbers, and death confirmation across consecutive
frames. The existing two examples are insufficient to validate that classifier.
