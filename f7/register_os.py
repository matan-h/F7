### linux:
#   register a desktop file
### windows
# register a startup reg
### macos
# TODO
#!/usr/bin/env python3
import os
import platform
import shutil
import stat
import sys
from pathlib import Path


def xdg(env_var: str, default: str) -> Path:
    """
    Return Path from $env_var, or fallback to ~/<default>.
    """
    p = os.environ.get(env_var)
    return Path(p) if p else (Path.home() / default)


def delete(path: Path):
    if path.exists():
        path.unlink()
        print(f"Deleted: {path}")


def write_desktop_file(
    path: Path, exec_cmd: str, icon: Path, name: str, hidden: bool = False
):
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Exec={exec_cmd}",
        f"Icon={icon}",
        "Terminal=false",
        "StartupNotify=false",
        "Categories=Utility;",
    ]
    if hidden:
        # hides it from the “Applications” menu, but still auto-starts
        lines.append("NoDisplay=true")

    path.write_text("\n".join(lines))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    print(f"Wrote: {path}")


def register_linux(script_path: str, icon_path: Path, unregister: bool = False):
    user_autostart = xdg("XDG_CONFIG_HOME", ".config") / "autostart"

    user_apps = xdg("XDG_DATA_HOME", ".local/share") / "applications"

    desktop_file = user_apps / "f7.desktop"
    autostart_file = user_autostart / "f7-autostart.desktop"

    if unregister:
        delete(desktop_file)
        delete(autostart_file)
        return

    if not user_apps.exists():
        print("it looks like the apps folder", user_apps, "doesnt exist")
        exit(1)

    exec_path = str(Path(script_path).resolve())

    print("register desktop file")

    write_desktop_file(
        desktop_file,
        exec_cmd=f"{exec_path} show",
        icon=icon_path,
        name="F7",
    )

    uinp = (
        input("do you want to register autostart file (make app startup faster)? (Y/n)")
        .lower()
        .strip()
    )
    if uinp.startswith("y") or not uinp:
        # 2) Autostart (background only)
        write_desktop_file(
            autostart_file,
            exec_cmd=exec_path,
            icon=icon_path,
            name="F7 (autostart)",
            hidden=True,
        )
        print("registered autostart file")
    else:
        print("not registered autostart file")
    print("you'll need to configure a shortcut to the f7 app in the shortcut settings")


def register_windows(script_path: str, unregister: bool = False):
    import winreg

    key_name = "F7"

    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, run_key) as key:  # type: ignore[reportAttributeAccessIssue]
        if unregister:
            try:
                winreg.DeleteValue(key, key_name)  # type: ignore[reportAttributeAccessIssue]
                print(f"Unregistered '{key_name}' from Windows startup.")
            except FileNotFoundError:
                print(
                    f"'{key_name}' not found in Windows startup (already unregistered)."
                )
            return

        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, f'"{script_path}"')  # type: ignore[reportAttributeAccessIssue]

    print("Registered in Windows App Paths")


def register_macos(script_path, icon_path, unregister: bool = False):
    print(
        "MacOS is not yet supported. UNTESTED but maybe try following https://support.apple.com/en-il/guide/shortcuts-mac/apd84c576f8c/mac with 'f7 show' command?"
    )
    exit(1)


def register_os(unregister: bool = False):
    script_path = sys.argv[0]
    if not "f7" in Path(script_path).name:
        print("it look like register was not invoked from console script; exiting")
        exit(1)
    icon_path = Path(__file__).parent / "assets" / "icon.png"

    if not icon_path.exists():
        print(f"ERROR: Icon not found at {icon_path}", file=sys.stderr)
        # no need to exit here as it should still work

    system = platform.system().lower()
    if system == "linux":
        register_linux(script_path, icon_path, unregister)
    elif system == "windows":
        register_windows(os.path.abspath(script_path), unregister)
    elif system == "darwin":
        register_macos(script_path, icon_path, unregister)
    else:
        print(f"Unsupported OS: {system}", file=sys.stderr)
        sys.exit(1)
