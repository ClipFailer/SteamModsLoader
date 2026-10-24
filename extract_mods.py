import os
import sys
import shutil
from pathlib import Path

# Обеспечиваем корректный вывод кириллицы в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = BASE_DIR / "SteamCMD" / "steamapps" / "workshop" / "content"

# Словарь известных AppID для наглядности
GAME_NAMES = {
    "108600": "Project Zomboid",
    "294100": "RimWorld",
    "107410": "Arma 3",
    "281990": "Stellaris",
    "255710": "Cities: Skylines",
    "394360": "Hearts of Iron IV",
    "236850": "Europa Universalis IV",
    "1158310": "Crusader Kings III",
    "252490": "Rust",
    "4000": "Garry's Mod",
}


def get_game_folders():
    """Находит все папки с играми (AppID) в папке content."""
    if not CONTENT_DIR.exists():
        return []
    
    folders = []
    for item in CONTENT_DIR.iterdir():
        if item.is_dir() and item.name.isdigit():
            folders.append(item)
    return sorted(folders, key=lambda x: x.name)


def main():
    print("=" * 65, flush=True)
    print("     Сборщик модов из папок SteamCMD в общую папку /mods", flush=True)
    print("=" * 65, flush=True)

    if not CONTENT_DIR.exists():
        print(f"[!] Папка с загруженным контентом не найдена:", flush=True)
        print(f"    {CONTENT_DIR}", flush=True)
        print("Сначала запустите скачивание через download_mods.py / run.bat.", flush=True)
        input("\nНажмите Enter для выхода...")
        return

    game_folders = get_game_folders()
    if not game_folders:
        print("[!] В папке content пока нет ни одной игры.", flush=True)
        input("\nНажмите Enter для выхода...")
        return

    # Выбор игры, если их несколько
    selected_game = None
    if len(game_folders) == 1:
        selected_game = game_folders[0]
        game_title = GAME_NAMES.get(selected_game.name, "Неизвестная игра")
        print(f"[*] Найдена игра: {selected_game.name} ({game_title})", flush=True)
    else:
        print("\nВыберите игру из списка:", flush=True)
        for idx, folder in enumerate(game_folders, 1):
            title = GAME_NAMES.get(folder.name, "Неизвестная игра")
            mod_count = len([x for x in folder.iterdir() if x.is_dir() and x.name.lower() != "mods"])
            print(f"  [{idx}] {folder.name} ({title}) — скачано ID: {mod_count}", flush=True)

        while True:
            try:
                choice = input(f"\nВведите номер игры (1-{len(game_folders)}) или AppID: ").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(game_folders):
                    selected_game = game_folders[num - 1]
                    break
                else:
                    matched = [f for f in game_folders if f.name == choice]
                    if matched:
                        selected_game = matched[0]
                        break
            print("[!] Неверный выбор. Попробуйте еще раз.", flush=True)

    game_id = selected_game.name
    game_title = GAME_NAMES.get(game_id, "Неизвестная игра")
    
    # Целевая общая папка mods: например, SteamCMD/steamapps/workshop/content/108600/mods
    target_mods_dir = selected_game / "mods"
    target_mods_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[*] Выбрана игра: {game_id} ({game_title})", flush=True)
    print(f"[*] Целевая папка для всех готовых модов:", flush=True)
    print(f"    {target_mods_dir}\n", flush=True)

    # Ищем все подпапки модов (числовые Workshop ID), пропуская саму 'mods'
    workshop_dirs = [
        item for item in selected_game.iterdir()
        if item.is_dir() and item.name.lower() != "mods" and item.name.isdigit()
    ]

    if not workshop_dirs:
        print("[!] В папке игры нет подпапок с модами.", flush=True)
        input("\nНажмите Enter для выхода...")
        return

    print(f"[*] Найдено {len(workshop_dirs)} папок с модами Workshop.", flush=True)
    print("Начинаем извлечение содержимого в общую папку mods...\n", flush=True)

    copied_mods = 0
    skipped = 0

    for item_dir in workshop_dirs:
        workshop_id = item_dir.name
        mods_subdir = item_dir / "mods"

        # Вариант 1: Внутри есть папка 'mods' (стандарт для Project Zomboid)
        if mods_subdir.exists() and mods_subdir.is_dir():
            sub_items = [x for x in mods_subdir.iterdir()]
            if not sub_items:
                continue

            for mod_entry in sub_items:
                dst = target_mods_dir / mod_entry.name
                if mod_entry.is_dir():
                    shutil.copytree(mod_entry, dst, dirs_exist_ok=True)
                    print(f"  [+] Извлечен мод: '{mod_entry.name}' (из воркшопа {workshop_id})", flush=True)
                    copied_mods += 1
                elif mod_entry.is_file():
                    shutil.copy2(mod_entry, dst)
                    copied_mods += 1

        # Вариант 2: Папки 'mods' нет, но сам элемент является модом (есть mod.info)
        elif (item_dir / "mod.info").exists():
            dst = target_mods_dir / item_dir.name
            shutil.copytree(item_dir, dst, dirs_exist_ok=True)
            print(f"  [+] Скопирован мод напрямую: '{item_dir.name}'", flush=True)
            copied_mods += 1
        else:
            skipped += 1

    print("\n" + "=" * 65, flush=True)
    print(f"[+] Готово! Всего собрано модов в папке: {copied_mods}", flush=True)
    print(f"[*] Все объединенные моды находятся в:")
    print(f"    {target_mods_dir}", flush=True)
    print("=" * 65, flush=True)

    # Предложение сразу открыть готовую папку в Проводнике
    try:
        open_folder = input("\nОткрыть готовую папку mods в Проводнике? (y/n): ").strip().lower()
        if open_folder in ("y", "yes", "д", "да"):
            if sys.platform == "win32":
                os.startfile(target_mods_dir)
            else:
                subprocess.run(["xdg-open", str(target_mods_dir)])
    except Exception:
        pass


if __name__ == "__main__":
    main()
