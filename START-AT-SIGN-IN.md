# Start Mini Claude when you sign in

Windows starts everything in your Startup folder when you sign in. Put a shortcut to `pet.pyw` there.

## The easy way

1. Press **Win+R**, type `shell:startup`, and press Enter. Your Startup folder opens.
2. In another window, open the folder with `pet.pyw`.
3. Hold **Alt** and drag `pet.pyw` into the Startup folder. This makes a shortcut, not a copy.
4. Sign out and back in to try it.

## With PowerShell

Open PowerShell in the folder with `pet.pyw`, then run:

```powershell
$link = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Startup'))\Mini Claude.lnk")
$link.TargetPath = (Get-Command pythonw).Source
$link.Arguments = '"' + (Resolve-Path pet.pyw) + '" --update-memory'
$link.WorkingDirectory = (Get-Location).Path
$link.Save()
```

This uses `pythonw`, so no console window opens. It also turns on the memory update below; remove ` --update-memory` from the second-to-last line if you don't want it.

## Update its memory at sign-in

With `--update-memory`, the pet asks big Claude to refresh what it knows about you about 20 seconds after it starts, so each day begins with fresh notes.

- **First, set it up once:** type `/workspace` to choose your notes folder, then `/update` to try it. Without a notes folder, the flag does nothing.
- **Once a day:** if the memory was already updated today, it skips it, so signing in again costs nothing.
- **Quietly:** it runs in the background while the pet plays. The old memory is kept as `pet-memory.previous.md`.
- **Add it to a shortcut you made the easy way:** right-click the shortcut in the Startup folder → **Properties**. At the end of **Target**, after `pet.pyw`, add a space and `--update-memory`. Click OK.
- **Without the flag** the pet still refreshes by itself once a day, but only when the memory is over 2 days old.
- Each update is one Claude Code call and counts toward your plan's usage.

## Stop it from starting

- Delete the shortcut from the Startup folder (`shell:startup`), or
- open Task Manager → **Startup apps** and disable it.

## Notes

- If you move the folder with `pet.pyw`, make the shortcut again.
- Claude Code must be signed in for the pet to talk and update its memory. Everything else works without it.
