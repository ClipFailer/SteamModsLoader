import os
import re
import sys
import json
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

# Обеспечиваем корректный вывод кириллицы в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Папка скрипта
BASE_DIR = Path(__file__).resolve().parent

# Путь к steamcmd.exe
STEAMCMD_EXE = BASE_DIR / "SteamCMD" / "steamcmd.exe"

# Файлы конфигурации и списков
MODS_FILE = BASE_DIR / "mods.txt"
SCRIPT_FILE = BASE_DIR / "steamcmd_script.txt"

# По умолчанию вход анонимный.
# Если для какой-то игры (например, RimWorld, Arma 3) требуется купленная игра,
# можно заменить 'anonymous' на ваш логин Steam.
STEAM_USER = "anonymous"

API_DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
API_COLLECTION_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"


def make_sample_mods_file():
    """Создает файл mods.txt с примером, если его еще нет."""
    sample_content = (
        "# Вставьте сюда ссылки на моды или их ID (по одному на строку).\n"
        "# Строки, начинающиеся с #, игнорируются.\n"
        "#\n"
        "# Примеры:\n"
        "# 3814398576\n"
        "# https://steamcommunity.com/sharedfiles/filedetails/?id=3814398576\n"
        "# (Также поддерживаются ссылки на коллекции Steam!)\n\n"
        "3814398576\n"
    )
    MODS_FILE.write_text(sample_content, encoding="utf-8")
    print(f"[+] Создан файл с примером: {MODS_FILE.name}")


def extract_ids_from_file(file_path):
    """Извлекает числовые ID модов из файла со ссылками или номерами."""
    ids = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            # Ищем ID в ссылке (?id=...) или просто число
            match = re.search(r"(?:id=)?(\d{6,12})", line)
            if match:
                mod_id = match.group(1)
                if mod_id not in ids:
                    ids.append(mod_id)
    return ids


def check_and_expand_collections(mod_ids):
    """Проверяет переданные ID на то, не являются ли они коллекциями.
    Если это коллекция, автоматически распаковывает ID всех модов из нее."""
    expanded_ids = []
    
    for mod_id in mod_ids:
        # Проверяем, коллекция ли это
        data = urllib.parse.urlencode({
            "collectioncount": 1,
            "publishedfileids[0]": mod_id
        }).encode("utf-8")
        
        req = urllib.request.Request(
            API_COLLECTION_URL,
            data=data,
            headers={"User-Agent": "SteamCMDModDownloader/1.0"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                collections = result.get("response", {}).get("collectiondetails", [])
                if collections and "children" in collections[0]:
                    children = collections[0]["children"]
                    print(f"[*] ID {mod_id} — это коллекция! Найдено {len(children)} модов внутри.")
                    for child in children:
                        child_id = str(child.get("publishedfileid"))
                        if child_id and child_id not in expanded_ids:
                            expanded_ids.append(child_id)
                    continue
        except Exception:
            pass

        # Если не коллекция — добавляем как обычный мод
        if mod_id not in expanded_ids:
            expanded_ids.append(mod_id)

    return expanded_ids


def fetch_mod_details(mod_ids, chunk_size=50):
    """Пакетно запрашивает данные о модах (название, AppID) через официальный API Steam."""
    all_details = []
    
    for i in range(0, len(mod_ids), chunk_size):
        chunk = mod_ids[i:i + chunk_size]
        data = {"itemcount": len(chunk)}
        for idx, mod_id in enumerate(chunk):
            data[f"publishedfileids[{idx}]"] = mod_id

        encoded_data = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            API_DETAILS_URL,
            data=encoded_data,
            headers={"User-Agent": "SteamCMDModDownloader/1.0"}
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                details = res.get("response", {}).get("publishedfiledetails", [])
                all_details.extend(details)
        except Exception as e:
            print(f"[!] Ошибка при запросе к Steam API: {e}")

    return all_details


def main():
    print("=" * 65)
    print("        Steam Workshop Batch Downloader (SteamCMD)")
    print("=" * 65)

    if not STEAMCMD_EXE.exists():
        print(f"[ОШИБКА] Не найден файл: {STEAMCMD_EXE}")
        print("Убедитесь, что папка SteamCMD с файлом steamcmd.exe лежит рядом со скриптом.")
        input("\nНажмите Enter для выхода...")
        return

    if not MODS_FILE.exists():
        make_sample_mods_file()
        print(f"\nОткройте файл '{MODS_FILE.name}', добавьте нужные ссылки или ID модов и запустите скрипт снова.")
        input("\nНажмите Enter для выхода...")
        return

    raw_ids = extract_ids_from_file(MODS_FILE)
    if not raw_ids:
        print(f"[!] В файле '{MODS_FILE.name}' нет ни одного ID мода.")
        print("Добавьте ссылки или номера модов в файл и запустите скрипт.")
        input("\nНажмите Enter для выхода...")
        return

    print(f"[*] Считано записей: {len(raw_ids)}. Проверяем коллекции и зависимости...")
    mod_ids = check_and_expand_collections(raw_ids)

    print(f"[*] Запрашиваем информацию о {len(mod_ids)} модах из базы Steam...")
    items = fetch_mod_details(mod_ids)

    valid_mods = []
    for item in items:
        mod_id = item.get("publishedfileid")
        app_id = item.get("consumer_app_id")
        title = item.get("title", "<Без названия>").strip()
        result = item.get("result", 0)

        if result == 1 and app_id:
            valid_mods.append((str(app_id), str(mod_id), title))
            print(f"  [+] Игра AppID {app_id:<7} | Мод {mod_id:<11} | {title}")
        else:
            print(f"  [-] Мод {mod_id} недоступен или скрыт в Steam (код: {result})")

    if not valid_mods:
        print("[!] Нет доступных модов для загрузки.")
        input("\nНажмите Enter для выхода...")
        return

    # Формируем скрипт команд для SteamCMD
    commands = [f"login {STEAM_USER}"]
    for app_id, mod_id, _ in valid_mods:
        commands.append(f"workshop_download_item {app_id} {mod_id}")
    commands.append("")
    commands.append("quit")
    commands.append("")

    SCRIPT_FILE.write_text("\n".join(commands), encoding="utf-8")
    print(f"\n[+] Сформирован файл команд: {SCRIPT_FILE.name}")
    print(f"[*] Готово к скачиванию: {len(valid_mods)} модов.")

    # Запуск SteamCMD
    print("\n" + "-" * 65)
    print("Запускаем SteamCMD...")
    print("-" * 65 + "\n")

    # Запуск SteamCMD (напрямую в консоль без буферизации, чтобы был виден весь прогресс в реальном времени)
    subprocess.run([str(STEAMCMD_EXE), "+runscript", str(SCRIPT_FILE)])

    print("\n" + "=" * 65)
    print("[+] Загрузка завершена!")
    
    # Показываем, куда сохранились моды
    app_ids = sorted(list(set(app_id for app_id, _, _ in valid_mods)))
    for app_id in app_ids:
        content_dir = BASE_DIR / "SteamCMD" / "steamapps" / "workshop" / "content" / app_id
        if content_dir.exists():
            print(f"[*] Моды для игры {app_id} сохранены в:")
            print(f"    {content_dir}")
    print("=" * 65)

    try:
        input("\nНажмите Enter для завершения...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
