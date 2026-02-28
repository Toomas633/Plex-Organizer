# FAQ

## Migrating from v5.0 to v6.0

Version 6.0 changed how Plex Organizer is installed and updated. The old method of cloning the repo and running `run.sh` / `update.sh` is no longer supported.

### What changed?

|                     | v5.0 (old)                      | v6.0 (new)                                                           |
| ------------------- | ------------------------------- | -------------------------------------------------------------------- |
| **Install**         | `git clone` + `run.sh`          | `pipx install git+https://github.com/Toomas633/Plex-Organizer.git`   |
| **Update**          | `./update.sh`                   | `pipx upgrade plex-organizer`                                        |
| **Run**             | `sudo bash run.sh <dir> [hash]` | `sudo plex-organizer <dir> [hash]`                                   |
| **Kill**            | —                               | `sudo plex-organizer-kill`                                           |
| **Config location** | Repo directory                  | `/root/.config/plex-organizer/` (override with `PLEX_ORGANIZER_DIR`) |

### Migration steps

1. **Install pipx** (if you don't have it):

   ```bash
   sudo apt install pipx
   pipx ensurepath
   ```

2. **Install Plex Organizer**:

   ```bash
   pipx install git+https://github.com/Toomas633/Plex-Organizer.git
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
