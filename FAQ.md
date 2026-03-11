# FAQ

## Migrating from v5.0 to v6.0

Version 6.0 changed how Plex Organizer is installed and updated. The old method of cloning the repo and running `run.sh` / `update.sh` is no longer supported.

### What changed?

|                     | v5.0 (old)                      | v6.0 (new)                                                           |
| ------------------- | ------------------------------- | -------------------------------------------------------------------- |
| **Install**         | `git clone` + `run.sh`          | `pipx install git+https://github.com/Toomas633/Plex-Organizer.git`   |
| **Update**          | `./update.sh`                   | `pipx upgrade plex-organizer`                                        |
| **Run**             | `sudo bash run.sh <dir> [hash]` | `sudo plex-organizer <dir> [hash]`                                   |
| **Kill**            | —                               | `sudo plex-organizer --manage` → option 5                            |
| **Config location** | Repo directory                  | `/root/.config/plex-organizer/` (override with `PLEX_ORGANIZER_DIR`) |

### Migration steps

1. **Install pipx** (if you don't have it):

   ```bash
   sudo apt install pipx
   sudo pipx ensurepath
   ```

2. **Install Plex Organizer** (as root, so the command is on root's PATH):

   ```bash
   sudo pipx install git+https://github.com/Toomas633/Plex-Organizer.git
   ```

3. **Move your config** from the old repo directory to the new default location:

   ```bash
   mkdir -p /root/.config/plex-organizer
   cp /path/to/old/Plex-Organizer/config.ini /root/.config/plex-organizer/
   ```

4. **Update any automation** (e.g. qBittorrent "Run external program on torrent finished") to use the new command:

   ```
   sudo plex-organizer "%D" "%I"
   ```

5. **Remove the old clone** once everything works:

   ```bash
   rm -rf /path/to/old/Plex-Organizer
   ```

### Do I still need root?

Yes — `sudo` is still required to run the organizer.

## Migrating TV indexes to the root TV folder

Starting with the latest version, Plex Organizer stores a single `.plex_organizer.index` file in the TV library root (`tv/`) instead of one per show (`tv/<Show>/`). If you are upgrading from a version that used per-show indexes, run the migration tool to merge them:

```bash
plex-organizer --manage
# Select option 7: "Migrate TV indexes to root"
# Enter your TV root folder (e.g. /media/tv)
```

This will:

1. Find all `.plex_organizer.index` files inside show sub-directories.
2. Merge their entries into a single index at the TV root.
3. Remove the old per-show index files.

Already-processed episodes will continue to be skipped after migration — no re-processing occurs.
