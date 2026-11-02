# Render job preparation

GUI and CLI capture source path, trim range, crop selection, split ratio and
source FPS into an `EditSnapshot`. The rendering application expands the
selected targets into stable `RenderQueueItem` values, resolving each format's
duration limit at preparation time. Later editor changes do not change jobs.

One target uses the selected GUI filename or the required CLI `--output` path.
Multiple targets use the chosen GUI folder or required CLI `--output-dir` with
`<source>[_<queue-number>]_<platform>_<format>_<quality>.mp4` names.
Target order is preserved.

GUI preparation numbers occupied names with `_1`, `_2`, etc. It considers
existing files, queued reservations and earlier jobs in the same preparation.
Reservations include the base path and every `_partN.mp4` path for split jobs.
CLI paths deliberately retain explicit overwrite intent, including generated
names in an explicitly selected output directory: existing files and queued
paths do not cause renaming. FFmpeg's existing overwrite behavior is preserved.
Reservations are advisory local checks, not atomic filesystem locks; another
process may create a file between preparation and rendering.

CLI queue-add is idempotent only for identical ordered jobs: source, output
path, trim, both crops, split ratio, target (including quality), source FPS and
duration limit must all match. Different crops or quality are different jobs.
The GUI allows deliberately queuing the same cut again with a newly reserved
output name. CLI entries with different cuts and the same explicit output path
remain allowed and can overwrite each other when rendered sequentially.
