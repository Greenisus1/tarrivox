# Tarrivox

Encrypted local directory/system snapshots with optional private GitHub upload. Rebuilt with approval from the full-Pi-backup experiment in microsoftcopilotcodeusedonpi; original repository untouched. The old script created its tar outside the Git staging folder, so it didn't upload the actual backup. Tarrivox writes and verifies the encrypted archive locally first.

## Run

Use the Pi App Store, or from an extracted checkout:

```sh
bash app-store.sh install
bash app-store.sh run
```

Requires Python3.9+, tar and GPG; sudo for a root snapshot. Encryption passphrase is collected by GPG's own pinentry prompt, never stored by Tarrivox. Use an interactive terminal. Keep the passphrase separately: losing it means losing the backup. No passphrase, token or card belongs in chat.

The terminal menu defaults to local backups. You can instead pass a command:

```sh
python3 tarrivox.py backup --source / --output ~/tarrivox-backups
```

Review the source and destination, then confirm. Output directory is private0700 and encrypted archive0600. Plain tar data passes directly to GPG through a pipe, never a disk file. Encryption uses GPG's AES256 symmetric format. Partial encrypted outputs are removed when tar/encryption fails. Existing archives aren't overwritten.

## What is and isn't backed up

A root snapshot includes only the root filesystem, not a full disk image. It excludes proc/sys/dev/run/tmp/media/mnt, the output directory and other filesystem mounts. External disks, separate boot partitions and other mounts aren't included. Do not call it complete bare-metal recovery. Run a separate directory backup for mounted data you need.

A live filesystem may change during backup. Stop important writers first; tar warnings/failure stop the backup and remove partial output. No snapshot consistency guarantee. Ensure plenty of free space for the encrypted archive. For important data use established filesystem snapshot/disk-image tools too.

## Optional GitHub upload

Install GitHub CLI and authenticate locally with `gh auth login`. Tarrivox does not prompt for a PAT or write one into git config. The CLI manages its own credentials. Never check tokens into this repo.

Choose menu option3 or:

```sh
python3 tarrivox.py upload /path/to/tarrivox-backup.tar.gz.gpg YOUR-ACCOUNT/NEW-BACKUP-REPO
```

The archive must be a nonempty .tar.gz.gpg file, no larger than90 MiB. The destination must be a new repository under the currently authenticated GitHub user. You review archive name/size, owner and PRIVATE destination before choosing upload. Tarrivox creates the repository private, verifies that setting, uploads only the encrypted archive as a release asset, then checks asset name/size. It does not upload plaintext/home/etc contents directly. A filename and upload timing still go to GitHub, and encryption isn't a reason to share a sensitive backup publicly.

If upload fails, local backup stays. A partial/empty private repository or release may remain: inspect it before retrying. Nothing is automatically deleted. Larger backups stay local; no splitting or public fallback. Upload tests are mocked, not a real GitHub transfer.

## Restore

No automatic restore is included. Use GPG to decrypt into a separate trusted directory, inspect tar contents, then extract there. Don't run a root-overwrite command copied from historical restore notes. Encryption checks do not make a live-system restore safe. Practice recovery before relying on a backup.

## Validation

```sh
python3 test_packaging.py
```

15 tests cover packaging, headless menu, real tiny tar/GPG encryption roundtrip and wrong-password rejection, cancellation, failed encryption cleanup, private destination/owner/size gates and mocked upload. No whole-system archive, privilege escalation, real token access or GitHub upload executed during tests. Linux tested on tiny disposable directories; Raspberry Pi hardware and non-Linux systems untested.

Version1.0.0. This redesign intentionally replaces automatic cloud upload with confirmed local backup plus separate opt-in upload.

## Fullscreen Store launch

Version 1.0.1 adds a full-terminal interface when launched through the Store. Python 3 with curses and an interactive terminal are required. The original source remains available directly. Arrow keys select, Enter opens, and Q/Esc returns. Original commands temporarily take over the terminal for their prompts and output, then return to the full-terminal menu. Nested original prompts remain plain; they are not captured or rewritten. Passwords, sudo, confirmations, package changes and original limitations retain their old behavior. No administrative/package/transfer action ran during validation. Linux terminal checks passed; physical Raspberry Pi and non-Linux systems are untested.
