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
$link.Arguments = '"' + (Resolve-Path pet.pyw) + '"'
$link.WorkingDirectory = (Get-Location).Path
$link.Save()
```

This uses `pythonw`, so no console window opens.

## Stop it from starting

- Delete the shortcut from the Startup folder (`shell:startup`), or
- open Task Manager → **Startup apps** and disable it.

## Notes

- If you move the folder with `pet.pyw`, make the shortcut again.
- Claude Code must be signed in for the pet to talk. Everything else works without it.
