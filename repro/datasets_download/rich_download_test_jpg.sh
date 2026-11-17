#!/bin/bash
# Download the RICH test-split JPG images (JPG_images/test.tar.gz, 242,598,234,351 bytes) to
#   $H3R_DATA/_archives/RICH/test_jpg.tar.gz
# with YOUR OWN RICH account. You must first register at https://rich.is.tue.mpg.de and accept the
# RICH licence; this script does not bypass the login and nothing is redistributed.
# Same method as the official RICH download scripts (authenticated POST), plus a cookie jar and
# resume. ONE connection only: the server allows at most 2 concurrent downloads per account and
# blocks the file for the account (HTTP 403, for hours) if that is exceeded.
# Resumable: re-run the script if it gets interrupted. Extraction: rich_extract.sbatch.
#
# Run in your own terminal inside `screen` or `tmux` so it survives disconnects:
#   H3R_DATA=/path/to/data bash repro/datasets_download/rich_download_test_jpg.sh
# Credentials are read from the terminal, never put on a command line, never written to disk.
# Note: for this study the archive was fetched with a 2-connection byte-range variant of this
# script (same URL, same bytes; SHA256 in SHA256SUMS.txt). This single-connection version was
# only run on a partial download.
set -euo pipefail
umask 077

OUT=${H3R_DATA:?set H3R_DATA to the data root}/_archives/RICH
F="$OUT/test_jpg.tar.gz"
URL='https://download.is.tue.mpg.de/download.php?domain=rich&resume=1&sfile=JPG_images/test.tar.gz'
mkdir -p "$OUT"

read -rp  "RICH login email: " RICH_USER
read -rsp "RICH password: "    RICH_PASS; echo

EXPECTED=242598234351   # bytes, from the server's Content-Range (2026-11-14)

# The server answers the authenticated POST with a 302 to download2.php, which only works
# with the PHP session cookie -> curl needs a cookie jar (wget keeps cookies automatically).
JAR=$(mktemp); trap 'rm -f "$JAR"' EXIT

if [ -s "$F" ] && [ "$(stat -c %s "$F")" -ge "$EXPECTED" ]; then
    echo "Already complete: $F"; exit 0
fi
echo "Downloading to $F (resumes if partial) ..."
attempt=0
until curl -fL -c "$JAR" -b "$JAR" --retry 10 --retry-delay 30 -C - -o "$F" \
          --data-urlencode "username@"<(printf %s "$RICH_USER") \
          --data-urlencode "password@"<(printf %s "$RICH_PASS") \
          "$URL"; do
    rc=$?
    if [ $rc -eq 22 ] && [ $attempt -eq 0 ]; then
        echo "Server returned an HTTP error on the first try (401 = wrong email/password). Stopping."
        exit 1
    fi
    attempt=$((attempt+1))
    [ $attempt -ge 20 ] && { echo "Giving up after $attempt attempts"; exit 1; }
    echo "curl failed (attempt $attempt), retrying in 60 s ..."; sleep 60
done
unset RICH_PASS

SZ=$(stat -c %s "$F")
echo "Done: $SZ bytes"
if [ "$SZ" -lt 1000000 ]; then
    echo "File is tiny -> login/redirect failed (server returned a web page, not the archive)."
    mv "$F" "$F.failed"; exit 1
fi
if [ "$SZ" -ne "$EXPECTED" ]; then
    echo "Size mismatch: got $SZ, expected $EXPECTED. Re-run this script to resume."; exit 1
fi
echo "JPG_images/test.tar.gz (RICH download page), $SZ bytes, finished $(date -Is)" >> "$OUT/DOWNLOADED_AT"
echo "Next: sbatch repro/datasets_download/rich_extract.sbatch"
