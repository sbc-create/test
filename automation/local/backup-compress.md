# Verified publish backup compression

`backup-compress.py` replaces the one-off 2026-10-29 compressor with a rolling
policy. It does not delete restore points or change the existing retention
planner. It accepts only complete catalog/details pairs with a valid daily run
ID, keeps the seven latest actual dates and the two latest full pairs per site
uncompressed, and ignores symlinks, unknown names and existing `.gz` files.

Run without `--apply` to preview. Applying streams gzip at level 1, verifies CRC
and SHA-256 against the source, checks that the source did not change, commits
the archive without overwriting an existing file and fsyncs before unlinking
the raw file. A failure stops the run and preserves the source. Old daily files
are expected to be immutable. At least 1 GiB free reserve is required.

Install the Python file as root-owned mode 0644 at
`/usr/local/lib/site-factory/backup-compress.py` and the supplied units under
`/etc/systemd/system/`. Validate with `systemd-analyze verify`, reload systemd,
run the service once, inspect its result, then enable the timer. The service
runs as claude with 128 MiB RAM, no swap, 0.5 CPU and a 30-minute timeout.
The timer runs daily at 01:15 UTC plus up to 15 minutes jitter.

Validation: `python3 -m unittest -v test_backup_compress.py` in this directory.
To restore, decompress the selected `.gz` to a separate staging file and use
the normal restore procedure; do not overwrite a live catalog blindly.
To stop automatic compression: `systemctl disable --now site-factory-backup-compress.timer`.
