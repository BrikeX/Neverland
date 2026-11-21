---
name: diagnose-pipewire-crackle
description: Diagnose and fix Linux audio crackling, popping, or static on PipeWire when playback affects multiple outputs or appears network-related. Use when audio crackles during music, games, or video, when pw-top shows rising ERR counts or a very low graph quantum, when logs contain snd_pcm_mmap_commit "Broken pipe", or when a background ALSA client such as fluidsynth forces a small period size.
---

# Diagnose PipeWire Crackle

## Overview

Isolate audible crackle across PipeWire outputs and fix it by measuring the graph quantum and underrun rate instead of guessing at hardware, codecs, or network drivers.

## Core model

- PipeWire chooses the graph quantum from client latency requests, clamped by `clock.min-quantum` and `clock.max-quantum`, unless `clock.force-quantum` is set.
- A background client with a tiny ALSA period can pin the whole graph low. At 48 kHz, 64 frames is 1.33 ms and commonly underruns several times per second.
- Graph-level underruns happen before output routing, so they affect speakers, wired headphones, and Bluetooth alike.
- Wi-Fi or Ethernet correlation is often coincidental. Test it explicitly before pursuing driver theories.

## Triage

1. Identify affected outputs. If crackle affects independent output devices (for example, speakers and Bluetooth headphones), the fault is upstream of the codec and speaker hardware.
2. Rule out radio interference by playing a local file with the Wi-Fi radio off:
   ```
   nmcli radio wifi off   # or: sudo rfkill block wifi
   ```
   Restore with `nmcli radio wifi on` (or `sudo rfkill unblock wifi`) afterward.
3. Reproduce with a known-good tone to avoid source artifacts:
   ```
   ffmpeg -hide_banner -loglevel error -y -f lavfi \
     -i "sine=frequency=440:sample_rate=48000:duration=15" \
     -af "volume=0.1" -c:a pcm_s16le /tmp/tone48.wav
   pw-play /tmp/tone48.wav
   ```
4. Do not persist power-saving changes (`snd_hda_intel power_save=0`, Wi-Fi power save off) unless they demonstrably change the symptom. Restore them after testing.

## Measure

Run during playback:

```
pw-top -b -n 3
```

- `ERR` is cumulative per node. Compare snapshots; a static nonzero value is harmless, a rising value is not.
- The ALSA sink or driver `QUANT` is the graph quantum. Values below roughly 256 frames are suspicious; 64 frames is 1.3 ms at 48 kHz.
- Typical failure signature: sink `QUANT 64` with `ERR` rising about 10 per second.

Cross-check settings:

```
pw-metadata -n settings | grep -E 'quantum|rate'
```

`clock.quantum=1024` does not prevent clients from lowering the graph quantum down to `clock.min-quantum` (32 by default).

## Confirm the cause

Force a sane quantum at runtime:

```
pw-metadata -n settings 0 clock.force-quantum 1024
```

Replay the tone and run `pw-top` again. If the sink `ERR` stops increasing while a client still shows a very low `QUANT`, that client is forcing low latency. Forcing the quantum may make that client itself xrun, so treat this as a diagnostic, not the fix. Release the override once investigated:

```
pw-metadata -n settings 0 clock.force-quantum 0
```

## Identify the offending client

- Read `pw-top` node names, such as `alsa_playback.fluidsynth`, and note their small `QUANT`.
- Match nodes to processes: `ps -o pid,etime,args -C fluidsynth`.
- Check user services: `systemctl --user list-units | grep -i fluid`.
- Confirm the process is safe to stop before changing or disabling it.

## Fix example: fluidsynth

FluidSynth defaults to a 64-frame period and can pin the graph at 64. Stop the running service first so the test instance is the only one producing audio, then start it with a larger period:

```
fluidsynth -is -o audio.period-size=1024 /usr/share/sounds/sf3/default-GM.sf3
```

Persist through the unit's environment file. Inspect the unit first with `systemctl --user cat fluidsynth.service`; it reads `/etc/default/fluidsynth` and `~/.config/fluidsynth`, then starts `fluidsynth -is $OTHER_OPTS $SOUND_FONT`.

```
# ~/.config/fluidsynth
OTHER_OPTS="-o audio.period-size=1024"
```

Restart and verify:

```
systemctl --user restart fluidsynth.service
ps -o args -C fluidsynth
pw-top -b -n 2
```

Expect the graph to run at 1024 frames or higher (not 64), with a flat `ERR`; the fluidsynth node should show its requested 1024-frame quantum.

If the daemon is unused, disable it instead:

```
systemctl --user disable --now fluidsynth.service
```

## Verify

- Replay the tone, then music or a game, on speakers, wired headphones, and Bluetooth.
- Confirm the sink `ERR` delta is zero across snapshots and the graph quantum is stable.
- Confirm no runtime override remains (`clock.force-quantum=0`).
- Restore any temporary experiments and confirm their original values.

## Pitfalls

- Chasing `snd_pcm_mmap_commit error: Broken pipe` in isolation. These can come from idle shutdown or suspend transitions; correlate them with the `ERR` delta and the audible symptom.
- Reading `ERR` as a rate; it is cumulative.
- Setting `default.clock.quantum` and assuming it sticks; client-requested minima override it.
- Blaming the network driver. Disabling the radio is a stronger test than observing traffic correlation.
- Blaming the Realtek codec when Bluetooth is also affected.
- Adding realtime scheduling as a blind workaround. Check `systemctl --user show pipewire -p LimitRTPRIO` and `ps -L -o cls,rtprio,comm -p "$(pgrep -d, -x pipewire)"`, but fix measured underruns first.

## Case notes

- Lenovo Y7000P, Ubuntu kernel 6.8.0-142, PipeWire 1.0.5, Realtek ALC257, Intel AX211.
- Symptom: crackle during music, games, and video on speakers, wired headphones, and Bluetooth; unchanged with the Wi-Fi radio off.
- Diagnosis: sink quantum 64 with `ERR` rising about 11 per second; the enabled user unit `fluidsynth.service` was requesting a 64-frame period.
- Fix: `OTHER_OPTS="-o audio.period-size=1024"` in `~/.config/fluidsynth`; service restarted; quantum 1024; `ERR` flat.
- Wi-Fi power save and HDA runtime power saving were tested, showed no effect, and were reverted.
