# main.py - Fixcrown Zapret
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import subprocess, os, sys, json, threading, socket, time, shutil, zipfile
import webbrowser, ctypes, urllib.request, urllib.error, re, csv, io
from datetime import datetime

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False


# ==================== ФИКС ДЛЯ PyInstaller ====================
def get_base_path():
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return os.path.dirname(sys.executable), sys._MEIPASS
        return os.path.dirname(sys.executable), os.path.dirname(sys.executable)
    base = os.path.dirname(os.path.abspath(__file__))
    return base, base


DATA_PATH, RESOURCE_PATH = get_base_path()
BASE_PATH = DATA_PATH


# ==================== ПРАВА АДМИНИСТРАТОРА ====================
def is_admin():
    if sys.platform != 'win32':
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


if sys.platform == 'win32' and not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()


COLORS = {
    'bg_primary': '#1e1e1e', 'bg_secondary': '#252526', 'bg_tertiary': '#2d2d30',
    'panel_bg': '#2d2d30', 'panel_header': '#3e3e42', 'border': '#3e3e42',
    'primary': '#007acc', 'primary_hover': '#005a9e', 'secondary': '#68217a',
    'success': '#107c10', 'error': '#e51400', 'warning': '#ff8c00',
    'text_primary': '#cccccc', 'text_secondary': '#858585', 'text_muted': '#666666',
    'highlight': '#0e639c', 'scrollbar': '#424242'
}

APP_VERSION = "2.0.0"
GITHUB_REPO = "Fixcrown/Fixcrown-Zapret"
GITHUB_API_COMMITS = f"https://api.github.com/repos/{GITHUB_REPO}/commits?per_page=1"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0


# ==================== ЛОГ ИКОНКИ ====================
def icon_log(msg):
    """Пишет отладочную инфу по иконке в отдельный файл."""
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"
    try:
        p = os.path.join(DATA_PATH, "icon_debug.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    try:
        print(f"[ICON] {msg}")
    except Exception:
        pass


# ==================== ХЕЛПЕРЫ ====================
def _decode_windows_output(raw):
    if raw is None:
        return ""
    for enc in ('cp866', 'cp1251', 'utf-8'):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode('utf-8', errors='ignore')


def check_process_running(image_name):
    if sys.platform != 'win32':
        return False
    try:
        r = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {image_name}', '/NH', '/FO', 'CSV'],
                           capture_output=True, timeout=5, creationflags=_NO_WINDOW)
        return image_name.lower() in _decode_windows_output(r.stdout).lower()
    except Exception:
        return False


def kill_processes_by_image(image_name):
    if sys.platform != 'win32':
        return False
    try:
        r = subprocess.run(['taskkill', '/F', '/T', '/IM', image_name],
                           capture_output=True, timeout=10, creationflags=_NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def get_net_counters():
    if sys.platform != 'win32':
        return None
    try:
        r = subprocess.run(['netstat', '-e'], capture_output=True, timeout=5, creationflags=_NO_WINDOW)
        for line in _decode_windows_output(r.stdout).split('\n'):
            ls = line.strip()
            if ls.startswith('Bytes') or ls.startswith('Байт'):
                nums = re.findall(r'\d+', ls)
                if len(nums) >= 2:
                    return int(nums[0]), int(nums[1])
        return None
    except Exception:
        return None


def list_established_connections():
    if sys.platform != 'win32':
        return []
    result = []
    try:
        r = subprocess.run(['netstat', '-ano'], capture_output=True, timeout=5, creationflags=_NO_WINDOW)
        for line in _decode_windows_output(r.stdout).split('\n'):
            parts = line.split()
            if len(parts) >= 4 and parts[0].upper() in ('TCP', 'UDP') and 'ESTABLISHED' in line.upper():
                try:
                    result.append((parts[1], parts[2], parts[4] if len(parts) > 4 else 'N/A'))
                except Exception:
                    pass
        return result
    except Exception:
        return []


class FixcrownZapret:
    def __init__(self, root):
        try:
            p = os.path.join(DATA_PATH, "icon_debug.log")
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

        icon_log(f"=== Запуск Fixcrown Zapret ===")
        icon_log(f"frozen={getattr(sys, 'frozen', False)}  exe={sys.executable}")
        icon_log(f"DATA_PATH={DATA_PATH}")
        icon_log(f"RESOURCE_PATH={RESOURCE_PATH}")

        self.root = root
        self.root.title("Fixcrown Zapret")
        self.root.geometry("1400x800")
        self.root.configure(bg=COLORS['bg_primary'])
        self.root.minsize(1200, 700)

        self._setup_app_user_model_id()

        self._apply_window_icon()
        self.root.after(80, self._apply_window_icon)
        self.root.after(400, self._apply_window_icon)
        self.root.after(1200, self._apply_window_icon)

        self._autostart_launch = '--autostart' in sys.argv

        self.is_connected = False
        self.connection_start_time = None
        self.config_file = os.path.join(DATA_PATH, "zapret_config.json")
        self.current_tab = None
        self.winws_process = None
        self.running = True
        self.default_profile = "general.bat"
        self.was_connected = False
        self._operation_in_progress = False
        self._winws_check_cache = None
        self.prev_net_stats = None
        self.last_network_update = 0
        self.last_ping_update = 0
        self.tab_icons = {}
        self.current_tab_icon = None
        self.tab_icon_label = None
        self._game_toggle_redraw = None
        self.winws_path = os.path.join(DATA_PATH, "winws.exe")

        self.game_filter_var = tk.BooleanVar(value=False)
        self.ipset_var = tk.IntVar(value=1)
        self.auto_start_var = tk.BooleanVar(value=False)

        self.lists_dir = os.path.join(DATA_PATH, "lists")
        os.makedirs(self.lists_dir, exist_ok=True)
        self.domains_file = os.path.join(self.lists_dir, "list-general.txt")
        self.ipset_all = os.path.join(self.lists_dir, "ipset-all.txt")

        self.load_config()
        self.check_and_fix_paths()
        self.load_tab_icons()

        self.zapret_version = self.get_zapret_version()
        self._update_window_title()

        self.setup_ui()
        self.root.after(150, self._sync_ui_state)
        self.root.after(250, self._apply_window_icon)

        self.prev_net_stats = None
        self.last_network_update = time.time()
        self.start_update_tasks()

        self.check_required_files()

        if self.is_winws_running():
            self.is_connected = True
            self.connection_start_time = datetime.now()
            self.was_connected = True
            self.save_config()
            self.log("✅ Обнаружен запущенный процесс winws.exe (внешний)")
            self.root.after(500, self.update_connection_status)
        elif self._autostart_launch:
            self.log("🔧 Запуск через автозагрузку — автоматическое подключение...")
            self.root.after(2000, self.connect)
        elif self.was_connected:
            self.root.after(2000, self.connect)

        self.log("🚀 Приложение запущено")
        self.log(f"📁 Рабочая директория: {DATA_PATH}")
        if self.zapret_version:
            self.log(f"📦 Версия zapret: {self.zapret_version}")
        else:
            self.log("ℹ️ Версия zapret не определена")
        self.log(f"📋 Отладка иконки: {os.path.join(DATA_PATH, 'icon_debug.log')}")

        self.check_update_notification()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_application)

    # ==================== ИКОНКА ОКНА ====================
    def _setup_app_user_model_id(self):
        if sys.platform != 'win32':
            return
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Fixcrown.Zapret.App.1")
            icon_log("AppUserModelID установлен")
        except Exception as e:
            icon_log(f"AppUserModelID error: {e}")

    def _find_icon_file(self):
        """Ищет .ico-файлы. Приоритет: icon.ico > taskbar1.ico.
        Сначала RESOURCE_PATH (внутри exe через _MEIPASS), потом DATA_PATH."""
        for name in ("icon.ico", "Icon.ico", "taskbar1.ico", "Taskbar1.ico"):
            for base in (RESOURCE_PATH, DATA_PATH, os.path.dirname(sys.executable)):
                p = os.path.join(base, name)
                if os.path.exists(p):
                    icon_log(f"_find_icon_file: найден {p}")
                    return p
        icon_log("_find_icon_file: НИ ОДНОГО .ico не найдено")
        return None

    def _apply_window_icon(self):
        """Устанавливает иконку окна через WinAPI.
        Приоритет: файл .ico → ресурсы exe (только если frozen) → ничего."""
        if sys.platform != 'win32':
            return
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            shell32 = ctypes.windll.shell32

            user32.GetAncestor.restype = wintypes.HWND
            user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetParent.restype = wintypes.HWND
            user32.GetParent.argtypes = [wintypes.HWND]

            user32.LoadImageW.restype = wintypes.HANDLE
            user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                          wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                          wintypes.UINT]

            user32.LoadIconW.restype = wintypes.HICON
            user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]

            user32.SendMessageW.restype = wintypes.LPARAM
            user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                            wintypes.WPARAM, wintypes.LPARAM]

            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                            ctypes.c_int, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_int,
                                            wintypes.UINT]

            shell32.ExtractIconExW.restype = wintypes.UINT
            shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                                               ctypes.POINTER(wintypes.HICON),
                                               ctypes.POINTER(wintypes.HICON),
                                               wintypes.UINT]

            kernel32.GetModuleHandleW.restype = wintypes.HMODULE
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            LR_DEFAULTSIZE = 0x0040
            GA_ROOT = 2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020

            hicon_big = 0
            hicon_small = 0
            source = None

            # ПРИОРИТЕТ 1: .ico-файл рядом с программой
            icon_path = self._find_icon_file()
            if icon_path:
                try:
                    hb = user32.LoadImageW(None, icon_path, IMAGE_ICON,
                                           32, 32, LR_LOADFROMFILE)
                    hs = user32.LoadImageW(None, icon_path, IMAGE_ICON,
                                           16, 16, LR_LOADFROMFILE)
                    if not hb:
                        hb = user32.LoadImageW(None, icon_path, IMAGE_ICON,
                                               0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
                    icon_log(f"LoadImageW из файла: big={hb} small={hs}")
                    if hb:
                        hicon_big = int(hb)
                        hicon_small = int(hs) if hs else int(hb)
                        source = f"файл {os.path.basename(icon_path)}"
                except Exception as e:
                    icon_log(f"LoadImageW из файла ошибка: {e}")

            # ПРИОРИТЕТ 2: ресурсы exe — только если реально запущено из .exe
            if not hicon_big and getattr(sys, 'frozen', False):
                try:
                    hInstance = kernel32.GetModuleHandleW(None)
                    lpIconName = ctypes.cast(1, wintypes.LPCWSTR)
                    h = user32.LoadIconW(hInstance, lpIconName)
                    icon_log(f"LoadIconW из exe hInstance={hInstance} -> {h}")
                    if h:
                        hicon_big = int(h)
                        hicon_small = int(h)
                        source = "LoadIconW из ресурсов exe"
                except Exception as e:
                    icon_log(f"LoadIconW exe error: {e}")

                if not hicon_big:
                    try:
                        arr_l = (wintypes.HICON * 1)()
                        arr_s = (wintypes.HICON * 1)()
                        n = shell32.ExtractIconExW(sys.executable, 0, arr_l, arr_s, 1)
                        icon_log(f"ExtractIconExW n={n} big={arr_l[0]} small={arr_s[0]}")
                        if n >= 1 and arr_l[0]:
                            hicon_big = int(arr_l[0])
                            hicon_small = int(arr_s[0]) if arr_s[0] else int(arr_l[0])
                            source = "ExtractIconExW из exe"
                    except Exception as e:
                        icon_log(f"ExtractIconExW error: {e}")

            icon_log(f"ИТОГ: HICON big={hicon_big} small={hicon_small} source={source}")
            if not hicon_big:
                icon_log("❌ HICON не получен — иконку не установить")
                return

            hwnd_candidates = []
            try:
                wid = int(self.root.winfo_id())
                hwnd_candidates.append(wid)
                icon_log(f"winfo_id -> {wid}")
            except Exception as e:
                icon_log(f"winfo_id error: {e}")

            try:
                wid = int(self.root.winfo_id())
                parent = user32.GetParent(wid)
                if parent:
                    hwnd_candidates.append(int(parent))
                    icon_log(f"GetParent -> {parent}")
            except Exception as e:
                icon_log(f"GetParent error: {e}")

            try:
                wid = int(self.root.winfo_id())
                root_h = user32.GetAncestor(wid, GA_ROOT)
                if root_h:
                    hwnd_candidates.append(int(root_h))
                    icon_log(f"GetAncestor -> {root_h}")
            except Exception as e:
                icon_log(f"GetAncestor error: {e}")

            seen = set()
            uniq = []
            for h in hwnd_candidates:
                if h and h not in seen:
                    seen.add(h)
                    uniq.append(h)
            icon_log(f"HWND-кандидаты: {uniq}")

            sent = 0
            for hwnd in uniq:
                try:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                    if hicon_small:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE |
                                        SWP_NOZORDER | SWP_FRAMECHANGED)
                    sent += 1
                    icon_log(f"WM_SETICON → HWND {hwnd}: OK")
                except Exception as e:
                    icon_log(f"WM_SETICON → HWND {hwnd}: ошибка {e}")

            if sent:
                icon_log(f"✅ Иконка применена к {sent} HWND (источник: {source})")
                self._hicon_big = hicon_big
                self._hicon_small = hicon_small
            else:
                icon_log("❌ Ни один WM_SETICON не сработал")

        except Exception as e:
            icon_log(f"FATAL _apply_window_icon: {e}")
            import traceback
            try:
                p = os.path.join(DATA_PATH, "icon_debug.log")
                with open(p, "a", encoding="utf-8") as f:
                    traceback.print_exc(file=f)
            except Exception:
                pass

    def set_window_icon(self):
        self._setup_app_user_model_id()
        self._apply_window_icon()

    # ==================== СИНХРОНИЗАЦИЯ UI ====================
    def _sync_ui_state(self):
        try:
            self.update_ipset_buttons()
        except Exception:
            pass
        try:
            if self._game_toggle_redraw:
                self._game_toggle_redraw()
        except Exception:
            pass
        try:
            self._update_tab_indicator()
        except Exception:
            pass

    def _update_window_title(self):
        if self.zapret_version:
            self.root.title(f"Fixcrown Zapret • zapret v{self.zapret_version}")
        else:
            self.root.title("Fixcrown Zapret")

    # ==================== ВЕРСИЯ ZAPRET ====================
    def _parse_local_version_from_bat(self, bat_path):
        try:
            with open(bat_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    ls = line.strip()
                    m = re.search(r'set\s+"?LOCAL_VERSION\s*=\s*([^"\r\n]+)"?', ls, re.IGNORECASE)
                    if m:
                        vm = re.search(r'(\d+(?:\.\d+)+)', m.group(1))
                        if vm:
                            return vm.group(1)
            return None
        except Exception:
            return None

    def get_zapret_version(self):
        try:
            sp = os.path.join(DATA_PATH, "service.bat")
            if os.path.exists(sp):
                ver = self._parse_local_version_from_bat(sp)
                if ver:
                    self.log(f"✅ Версия zapret из service.bat: {ver}")
                    return ver
        except Exception:
            pass
        for path in [
            os.path.join(DATA_PATH, "zapret_version.txt"),
            os.path.join(DATA_PATH, "version.txt"),
            os.path.join(DATA_PATH, "VERSION"),
            os.path.join(DATA_PATH, "zapret", "version.txt"),
            os.path.join(DATA_PATH, "utils", "zapret_version.txt"),
            os.path.join(DATA_PATH, "utils", "version.txt"),
        ]:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        m = re.search(r'v?(\d+(?:\.\d+)+)', f.read().strip())
                    if m:
                        self.log(f"✅ Версия zapret из {os.path.basename(path)}")
                        return m.group(1)
                except Exception:
                    pass
        if sys.platform == 'win32' and os.path.exists(self.winws_path):
            try:
                cmd = f"(Get-Item -LiteralPath '{self.winws_path}').VersionInfo.FileVersion"
                r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],
                                   capture_output=True, timeout=6, creationflags=_NO_WINDOW)
                m = re.search(r'(\d+(?:\.\d+)+)', _decode_windows_output(r.stdout).strip())
                if m:
                    self.log(f"✅ Версия из ресурсов winws.exe: {m.group(1)}")
                    return m.group(1)
            except Exception:
                pass
        if os.path.exists(self.winws_path):
            for flag in ('--version', '-v', '-V'):
                try:
                    r = subprocess.run([self.winws_path, flag], capture_output=True, timeout=2,
                                       creationflags=_NO_WINDOW, stdin=subprocess.DEVNULL)
                    out = (_decode_windows_output(r.stdout) + ' ' + _decode_windows_output(r.stderr)).strip()
                    m = re.search(r'v?(\d+\.\d+(?:\.\d+)+)', out)
                    if m:
                        return m.group(1)
                except Exception:
                    continue
        try:
            for fname in os.listdir(DATA_PATH):
                if fname.lower().endswith('.bat') and fname.lower() != 'service.bat':
                    ver = self._parse_local_version_from_bat(os.path.join(DATA_PATH, fname))
                    if ver:
                        return ver
        except Exception:
            pass
        return None

    # ==================== ОБНОВЛЕНИЯ ====================
    def check_update_notification(self):
        def worker():
            try:
                req = urllib.request.Request(GITHUB_API_COMMITS,
                                              headers={'User-Agent': 'FixcrownZapret-Updater'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                self.log(f"⚠️ Не удалось проверить обновления: {e}")
                return
            if not data:
                return
            try:
                msg = data[0].get('commit', {}).get('message', '')
                m = re.search(r'[Vv]?(\d+\.\d+(?:\.\d+)*)', msg)
                if not m:
                    return
                rv = m.group(1)
            except Exception:
                return
            if self._version_tuple(rv) <= self._version_tuple(APP_VERSION):
                self.log(f"✅ Fixcrown актуален ({APP_VERSION} / {rv})")
                return
            self.log(f"⬆️ Доступно: {APP_VERSION} → {rv}")
            self.root.after(0, lambda: self.show_update_dialog(rv))
        threading.Thread(target=worker, daemon=True).start()

    def show_update_dialog(self, remote_version):
        win = tk.Toplevel(self.root)
        win.title("Доступно обновление")
        win.geometry("440x230")
        win.configure(bg=COLORS['bg_primary'])
        win.transient(self.root)
        win.grab_set()
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")
        tk.Label(win, text="Ваша версия устарела", font=('Segoe UI', 14, 'bold'),
                 bg=COLORS['bg_primary'], fg=COLORS['warning']).pack(pady=(22, 6))
        tk.Label(win, text=f"Установлена: {APP_VERSION}\nДоступна:   {remote_version}",
                 font=('Segoe UI', 10), justify='center',
                 bg=COLORS['bg_primary'], fg=COLORS['text_primary']).pack(pady=6)
        bf = tk.Frame(win, bg=COLORS['bg_primary']); bf.pack(pady=22)
        tk.Button(bf, text="⬇ Обновить",
                  command=lambda: (webbrowser.open(GITHUB_RELEASES_URL), win.destroy()),
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10, 'bold'), padx=22, pady=6,
                  borderwidth=0, cursor='hand2', activebackground=COLORS['primary_hover']
                  ).pack(side='left', padx=5)
        tk.Button(bf, text="Позже", command=win.destroy,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10), padx=22, pady=6, borderwidth=0, cursor='hand2',
                  activebackground=COLORS['panel_header']).pack(side='left', padx=5)

    @staticmethod
    def _version_tuple(v):
        try:
            return tuple(int(x) for x in v.split('.'))
        except Exception:
            return (0,)

    # ==================== ИНТЕРФЕЙС ====================
    def load_tab_icons(self):
        tab_icon_files = {
            0: "Mdashboard.ico", 1: "Mprofiles.ico",
            4: "Mlogs.ico", 5: "Msettings.ico"
        }
        for tab_index, icon_file in tab_icon_files.items():
            for icon_path in [os.path.join(RESOURCE_PATH, icon_file),
                              os.path.join(DATA_PATH, icon_file)]:
                if os.path.exists(icon_path):
                    try:
                        self.tab_icons[tab_index] = tk.PhotoImage(file=icon_path)
                        break
                    except Exception:
                        pass
            else:
                self.tab_icons[tab_index] = None

    def update_tab_icon(self, tab_index):
        if not self.tab_icon_label:
            return
        file_map = {0: "Mdashboard.ico", 1: "Mprofiles.ico",
                    4: "Mlogs.ico", 5: "Msettings.ico"}
        icon_file = file_map.get(tab_index)
        if icon_file:
            for icon_path in [os.path.join(RESOURCE_PATH, icon_file),
                              os.path.join(DATA_PATH, icon_file)]:
                if os.path.exists(icon_path):
                    try:
                        photo = tk.PhotoImage(file=icon_path)
                        self.tab_icon_label.config(image=photo, text="")
                        self.tab_icon_label.image = photo
                        return
                    except Exception:
                        continue
        self.fallback_tab_icon(tab_index)

    def fallback_tab_icon(self, tab_index):
        icons = ["📊", "📁", "🌐", "📜", "⚙️"]
        if 0 <= tab_index < len(icons):
            self.tab_icon_label.config(image="", text=icons[tab_index],
                                       font=('Segoe UI', 24),
                                       bg=COLORS['bg_secondary'], fg=COLORS['primary'])

    def check_and_fix_paths(self):
        utils_path = os.path.join(DATA_PATH, "utils")
        if not os.path.exists(utils_path):
            os.makedirs(utils_path, exist_ok=True)
            self.create_utils_files()
        if not os.path.exists(self.lists_dir):
            os.makedirs(self.lists_dir, exist_ok=True)
        self.fix_winws_location()

    def fix_winws_location(self):
        try:
            candidates = [
                os.path.join(DATA_PATH, "winws.exe"),
                os.path.join(DATA_PATH, "bin", "winws.exe"),
                os.path.join(DATA_PATH, "winws", "winws.exe"),
                os.path.join(DATA_PATH, "zapret", "winws.exe"),
                os.path.join(DATA_PATH, "zapret", "bin", "winws.exe"),
                os.path.join(os.path.dirname(DATA_PATH), "winws.exe"),
                os.path.join(os.path.dirname(DATA_PATH), "bin", "winws.exe"),
            ]
            for path in candidates:
                if os.path.exists(path):
                    self.winws_path = path
                    self.log(f"✅ Найден winws.exe: {path}")
                    return
            self.log("❌ winws.exe не найден (искал в корне, bin/, winws/, zapret/, "
                     "zapret/bin/, а также на уровень выше)")
        except Exception as e:
            self.log(f"⚠️ Ошибка поиска winws.exe: {e}")

    def create_utils_files(self):
        utils_path = os.path.join(DATA_PATH, "utils")
        for f, content in [("check_updates.enabled", "ENABLED\n"),
                           ("targets.txt", "# Хосты\ngoogle.com\ndiscord.com\nroblox.com\n")]:
            p = os.path.join(utils_path, f)
            if not os.path.exists(p):
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(content)

    def update_game_filter_file(self):
        gf = os.path.join(DATA_PATH, "utils", "game_filter.enabled")
        if self.game_filter_var.get():
            try:
                with open(gf, 'w', encoding='utf-8') as f:
                    f.write("ENABLED\n")
                self.log(f"✅ Создан {gf}")
            except Exception:
                pass
        else:
            if os.path.exists(gf):
                try:
                    os.remove(gf); self.log(f"🗑️ Удален {gf}")
                except Exception:
                    pass

    # ==================== АВТОЗАПУСК ====================
    def setup_autostart(self):
        if not WINREG_AVAILABLE:
            self.log("⚠️ winreg недоступен (не Windows?)")
            return
        try:
            if getattr(sys, 'frozen', False):
                app_cmd = f'"{sys.executable}" --autostart'
            else:
                app_cmd = f'"{sys.executable}" "{__file__}" --autostart'

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, "FixcrownZapret", 0, winreg.REG_SZ, app_cmd)
            winreg.CloseKey(key)
            self.log(f"🔧 Автозапуск включён: {app_cmd}")
        except Exception as e:
            self.log(f"⚠️ Ошибка настройки автозапуска: {e}")

    def remove_autostart(self):
        if not WINREG_AVAILABLE:
            return
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_ALL_ACCESS)
            winreg.DeleteValue(key, "FixcrownZapret")
            winreg.CloseKey(key)
            self.log("🔧 Автозапуск выключен")
        except FileNotFoundError:
            self.log("ℹ️ Автозапуск и так не был установлен")
        except Exception as e:
            self.log(f"⚠️ Ошибка удаления автозапуска: {e}")

    def on_autostart_change(self):
        if self.auto_start_var.get():
            self.setup_autostart()
            self.was_connected = True
        else:
            self.remove_autostart()
        self.save_config()

    # ==================== ФОНОВЫЕ ЗАДАЧИ ====================
    def start_update_tasks(self):
        threading.Thread(target=self.run_update_tasks, daemon=True).start()

    def run_update_tasks(self):
        while self.running:
            now = time.time()
            if now - self.last_network_update >= 2:
                self.update_network_stats(); self.last_network_update = now
            if now - self.last_ping_update >= 10:
                self.update_ping(); self.last_ping_update = now
            self.check_connection_status()
            time.sleep(0.5)

    def update_network_stats(self):
        if not self.running:
            return
        try:
            c = get_net_counters()
            if c and self.prev_net_stats:
                up = (c[1] - self.prev_net_stats[1]) / 1024 / 2
                dn = (c[0] - self.prev_net_stats[0]) / 1024 / 2
                if hasattr(self, 'upload_label') and self.running:
                    self.root.after(0, lambda u=up: self.upload_label.config(text=f"{u:.1f} KB/s ↑"))
                if hasattr(self, 'download_label') and self.running:
                    self.root.after(0, lambda d=dn: self.download_label.config(text=f"{d:.1f} KB/s ↓"))
            if c:
                self.prev_net_stats = c
            if self.is_connected and self.connection_start_time and self.running:
                ut = datetime.now() - self.connection_start_time
                h, r = divmod(int(ut.total_seconds()), 3600)
                m, s = divmod(r, 60)
                if hasattr(self, 'uptime_label'):
                    self.root.after(0, lambda hh=h, mm=m, ss=s:
                                    self.uptime_label.config(text=f"{hh:02d}:{mm:02d}:{ss:02d}"))
        except Exception:
            pass

    def check_connection_status(self):
        if not self.running or self._operation_in_progress:
            return
        try:
            r = self.is_winws_running()
            if self.is_connected != r:
                self.is_connected = r
                self.root.after(0, self.update_connection_status)
                if r and not self.connection_start_time:
                    self.connection_start_time = datetime.now()
                    self.was_connected = True
                    self.save_config()
                    self.log("✅ Обнаружен winws.exe")
                elif not r and self.connection_start_time:
                    self.connection_start_time = None
                    self.was_connected = False
                    self.save_config()
                    self.log("⚠️ winws.exe не обнаружен")
        except Exception:
            pass

    def update_ping(self):
        if not self.running or sys.platform != 'win32':
            return
        try:
            r = subprocess.run(['ping', '-n', '1', '-w', '1000', '8.8.8.8'],
                               capture_output=True, timeout=2, creationflags=_NO_WINDOW)
            out = _decode_windows_output(r.stdout)
            m = re.search(r'(?:time|время)\s*[=<]\s*(\d+)\s*(?:ms|мс)',
                          out, re.IGNORECASE)
            if self.running and hasattr(self, 'ping_label'):
                val = m.group(1) + " мс" if m else "--- мс"
                self.root.after(0, lambda v=val: self.ping_label.config(text=v))
        except Exception:
            if self.running and hasattr(self, 'ping_label'):
                self.root.after(0, lambda: self.ping_label.config(text="--- мс"))

    # ==================== РАБОТА С WINWS ====================
    def is_winws_running(self):
        now = time.time()
        if self._winws_check_cache is not None:
            v, t = self._winws_check_cache
            if now - t < 0.7:
                return v
        result = check_process_running('winws.exe')
        self._winws_check_cache = (result, now)
        return result

    def update_connection_status(self):
        if not self.running or self._operation_in_progress:
            return
        if self.is_connected:
            self.status_label.config(text="Подключено")
            self.status_indicator.config(fg=COLORS['success'])
            self.connect_btn.config(text="ОТКЛЮЧИТЬ", state='normal',
                                    bg=COLORS['error'], activebackground='#a01000')
            self.connection_info.config(text="Подключено", fg=COLORS['success'])
            if hasattr(self, 'connection_status_label'):
                self.connection_status_label.config(text="Активно", fg=COLORS['success'])
        else:
            self.status_label.config(text="Отключено")
            self.status_indicator.config(fg=COLORS['error'])
            self.connect_btn.config(text="ПОДКЛЮЧИТЬ", state='normal',
                                    bg=COLORS['primary'], activebackground=COLORS['primary_hover'])
            self.connection_info.config(text="Отключено", fg=COLORS['error'])
            if hasattr(self, 'connection_status_label'):
                self.connection_status_label.config(text="Неактивно", fg=COLORS['text_primary'])

    def check_required_files(self):
        self.fix_winws_location()
        ok = True
        if not os.path.exists(self.winws_path):
            self.log("❌ winws.exe не найден — положите его в корень или в bin/")
            ok = False
        has_profile = False
        for ext in ('.bat', '.zapret', '.conf', '.ovpn'):
            try:
                if any(f.lower().endswith(ext) for f in os.listdir(DATA_PATH)):
                    has_profile = True
                    break
            except Exception:
                pass
        if not has_profile:
            self.log("❌ Не найдено ни одного профиля (.bat / .zapret) в папке программы")
            ok = False
        if ok:
            self.log("✅ Все необходимые файлы найдены")

    # ==================== UI ====================
    def setup_ui(self):
        self.main_container = tk.Frame(self.root, bg=COLORS['bg_primary'])
        self.main_container.pack(fill='both', expand=True)
        self.main_container.grid_rowconfigure(0, weight=0)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(2, weight=0)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.create_header()
        self.create_content_area()
        self.create_footer()
        self.update_connection_status()

    def create_header(self):
        header = tk.Frame(self.main_container, bg=COLORS['bg_secondary'], height=50)
        header.grid(row=0, column=0, sticky='ew', padx=1, pady=(0, 1))
        header.grid_propagate(False)
        lf = tk.Frame(header, bg=COLORS['bg_secondary']); lf.pack(side='left', padx=20)
        logo = tk.Frame(lf, bg=COLORS['bg_secondary']); logo.pack(side='left', padx=(0, 15))
        self.tab_icon_label = tk.Label(logo, text="📊", font=('Segoe UI', 24),
                                       bg=COLORS['bg_secondary'], fg=COLORS['primary'])
        self.tab_icon_label.pack(side='left')
        tk.Label(logo, text="Fixcrown Zapret", font=('Segoe UI', 14, 'bold'),
                 bg=COLORS['bg_secondary'], fg=COLORS['text_primary']).pack(side='left', padx=10)
        rf = tk.Frame(header, bg=COLORS['bg_secondary']); rf.pack(side='right', padx=20)
        pf = tk.Frame(rf, bg=COLORS['bg_secondary']); pf.pack(side='left', padx=(0, 20))
        tk.Label(pf, text="Профиль:", font=('Segoe UI', 10),
                 bg=COLORS['bg_secondary'], fg=COLORS['text_secondary']).pack(side='left', padx=(0, 5))
        self.profile_name_label = tk.Label(pf, text=self.default_profile,
                                           font=('Segoe UI', 10, 'bold'),
                                           bg=COLORS['bg_secondary'], fg=COLORS['primary'])
        self.profile_name_label.pack(side='left')
        sf = tk.Frame(rf, bg=COLORS['bg_secondary']); sf.pack(side='left', padx=(0, 20))
        self.status_indicator = tk.Label(sf, text="●", font=('Segoe UI', 20),
                                         bg=COLORS['bg_secondary'], fg=COLORS['error'])
        self.status_indicator.pack(side='left', padx=(0, 10))
        self.status_label = tk.Label(sf, text="Отключено", font=('Segoe UI', 12),
                                     bg=COLORS['bg_secondary'], fg=COLORS['text_primary'])
        self.status_label.pack(side='left')
        self.connect_btn = tk.Button(rf, text="ПОДКЛЮЧИТЬ", command=self.toggle_connection,
                                     bg=COLORS['primary'], fg=COLORS['text_primary'],
                                     font=('Segoe UI', 11, 'bold'), padx=25, pady=8,
                                     borderwidth=0, cursor='hand2',
                                     activebackground=COLORS['primary_hover'],
                                     disabledforeground=COLORS['text_secondary'])
        self.connect_btn.pack(side='left')

    def create_content_area(self):
        cf = tk.Frame(self.main_container, bg=COLORS['bg_primary'])
        cf.grid(row=1, column=0, sticky='nsew')
        cf.grid_rowconfigure(0, weight=0); cf.grid_rowconfigure(1, weight=1)
        cf.grid_columnconfigure(0, weight=1)
        self.create_studio_tabs(cf)
        self.tab_container = tk.Frame(cf, bg=COLORS['bg_primary'])
        self.tab_container.grid(row=1, column=0, sticky='nsew')
        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)
        self.setup_tabs()
        self.switch_tab(0)

    def create_studio_tabs(self, parent):
        tf = tk.Frame(parent, bg=COLORS['bg_secondary'], height=40)
        tf.grid(row=0, column=0, sticky='ew'); tf.grid_propagate(False)
        self.tabs_frame = tf
        tabs = ["📊 ДАШБОРД", "📁 ПРОФИЛИ", "🌐 ДОМЕНЫ", "📜 ЛОГИ", "⚙️ НАСТРОЙКИ"]
        self.tab_buttons = []
        for i, t in enumerate(tabs):
            btn = tk.Button(tf, text=t, command=lambda idx=i: self.switch_tab(idx),
                            bg=COLORS['bg_secondary'], fg=COLORS['text_secondary'],
                            font=('Segoe UI', 10), padx=20, pady=10,
                            borderwidth=0, cursor='hand2', relief='flat',
                            activebackground=COLORS['panel_header'],
                            activeforeground=COLORS['text_primary'])
            btn.pack(side='left', fill='y')
            self.tab_buttons.append(btn)
        self.tab_indicator = tk.Frame(tf, bg=COLORS['primary'], height=2)
        self.tab_indicator.place(x=0, y=38, width=100, height=2)
        tf.bind('<Configure>', lambda e: self.root.after_idle(self._update_tab_indicator))

    def _update_tab_indicator(self):
        if self.current_tab is None or not self.tab_buttons:
            return
        idx = self.current_tab
        if idx < 0 or idx >= len(self.tab_buttons):
            return
        btn = self.tab_buttons[idx]
        try:
            w = btn.winfo_width()
            x = btn.winfo_x()
            if w <= 1:
                self.root.after(50, self._update_tab_indicator)
                return
            self.tab_indicator.place(x=x, y=38, width=w, height=2)
        except Exception:
            pass

    def setup_tabs(self):
        self.tab_contents = [
            self.create_dashboard_content(),
            self.create_profiles_content(),
            self.create_domains_content(),
            self.create_logs_content(),
            self.create_settings_content(),
        ]
        for t in self.tab_contents:
            t.grid_forget()

    def switch_tab(self, tab_index):
        for i, btn in enumerate(self.tab_buttons):
            if i == tab_index:
                btn.config(bg=COLORS['bg_primary'], fg=COLORS['text_primary'],
                           font=('Segoe UI', 10, 'bold'))
            else:
                btn.config(bg=COLORS['bg_secondary'], fg=COLORS['text_secondary'],
                           font=('Segoe UI', 10))
        self.update_tab_icon(tab_index)
        self.show_tab_content(tab_index)
        self.root.after_idle(self._update_tab_indicator)

    def show_tab_content(self, tab_index):
        if self.current_tab is not None:
            self.tab_contents[self.current_tab].grid_forget()
        self.tab_contents[tab_index].grid(row=0, column=0, sticky='nsew')
        self.current_tab = tab_index

    # ==================== ДАШБОРД ====================
    def create_dashboard_content(self):
        tab = tk.Frame(self.tab_container, bg=COLORS['bg_primary'])
        tab.grid_rowconfigure(0, weight=1); tab.grid_columnconfigure(0, weight=1)
        rp = tk.Frame(tab, bg=COLORS['bg_primary'])
        rp.grid(row=0, column=0, sticky='nsew', padx=1, pady=1)
        rp.grid_rowconfigure(0, weight=1); rp.grid_rowconfigure(1, weight=1)
        rp.grid_columnconfigure(0, weight=1)
        sp = self.create_studio_panel(rp, "📈 СТАТИСТИКА")
        sp.master.grid(row=0, column=0, sticky='nsew', padx=1, pady=(0, 1))
        self.create_dashboard_stats(sp)
        cp = tk.Frame(rp, bg=COLORS['bg_primary'])
        cp.grid(row=1, column=0, sticky='nsew', padx=1, pady=(1, 0))
        cp.grid_columnconfigure(0, weight=1); cp.grid_columnconfigure(1, weight=1)
        gp = self.create_studio_panel(cp, "🎮 ИГРОВОЙ РЕЖИМ")
        gp.master.grid(row=0, column=0, sticky='nsew', padx=(0, 1), pady=1)
        self.create_game_mode_controls(gp)
        ip = self.create_studio_panel(cp, "🌐 IP-SET")
        ip.master.grid(row=0, column=1, sticky='nsew', padx=(1, 0), pady=1)
        self.create_ipset_controls(ip)
        return tab

    def create_studio_panel(self, parent, title):
        panel = tk.Frame(parent, bg=COLORS['panel_bg'],
                         highlightbackground=COLORS['border'], highlightthickness=1)
        h = tk.Frame(panel, bg=COLORS['panel_header'], height=35)
        h.grid(row=0, column=0, sticky='ew'); h.grid_propagate(False)
        tk.Label(h, text=title, font=('Segoe UI', 11, 'bold'),
                 bg=COLORS['panel_header'], fg=COLORS['text_primary'],
                 padx=10).pack(side='left', fill='y')
        c = tk.Frame(panel, bg=COLORS['panel_bg'])
        c.grid(row=1, column=0, sticky='nsew', padx=2, pady=2)
        panel.grid_rowconfigure(1, weight=1); panel.grid_columnconfigure(0, weight=1)
        panel.content = c
        return panel.content

    def create_studio_button(self, parent, text, command):
        btn = tk.Button(parent, text=text, command=command,
                        bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                        font=('Segoe UI', 10), anchor='w', padx=15,
                        borderwidth=0, cursor='hand2',
                        activebackground=COLORS['panel_header'],
                        activeforeground=COLORS['text_primary'])
        btn.bind("<Enter>", lambda e: btn.config(bg=COLORS['panel_header']))
        btn.bind("<Leave>", lambda e: btn.config(bg=COLORS['bg_tertiary']))
        return btn

    def create_dashboard_stats(self, parent):
        parent.grid_columnconfigure(0, weight=1); parent.grid_columnconfigure(1, weight=2)
        stats = [
            ("Скорость передачи:", "0 KB/s ↑"),
            ("Скорость приема:", "0 KB/s ↓"),
            ("Время работы:", "--:--:--"),
            ("Статус соединения:", "Неактивно"),
            ("Текущий профиль:", self.default_profile),
            ("Пинг (Google):", "--- мс")
        ]
        for i, (l, v) in enumerate(stats):
            tk.Label(parent, text=l, font=('Segoe UI', 10),
                     bg=COLORS['panel_bg'], fg=COLORS['text_secondary'],
                     anchor='w').grid(row=i, column=0, sticky='w', padx=15, pady=5)
            vl = tk.Label(parent, text=v, font=('Segoe UI', 10, 'bold'),
                          bg=COLORS['panel_bg'], fg=COLORS['text_primary'], anchor='w')
            vl.grid(row=i, column=1, sticky='w', padx=15, pady=5)
            if "Скорость передачи" in l: self.upload_label = vl
            elif "Скорость приема" in l: self.download_label = vl
            elif "Время работы" in l: self.uptime_label = vl
            elif "Статус соединения" in l: self.connection_status_label = vl
            elif "Текущий профиль" in l: self.current_profile_label = vl
            elif "Пинг (Google)" in l: self.ping_label = vl

    def create_game_mode_controls(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        tk.Label(parent, text="Оптимизирует приложение для игр,\nснижая задержки и пинг",
                 font=('Segoe UI', 9), bg=COLORS['panel_bg'],
                 fg=COLORS['text_secondary'], justify='left'
                 ).grid(row=0, column=0, sticky='w', padx=15, pady=(15, 10))
        tf = tk.Frame(parent, bg=COLORS['panel_bg'])
        tf.grid(row=1, column=0, sticky='ew', padx=15, pady=10)
        tf.grid_columnconfigure(0, weight=1)
        tk.Label(tf, text="Игровой режим:", font=('Segoe UI', 10),
                 bg=COLORS['panel_bg'], fg=COLORS['text_primary']
                 ).grid(row=0, column=0, sticky='w')
        self.game_switch = self.create_toggle_switch(tf, self.game_filter_var)
        self.game_switch.grid(row=0, column=1, sticky='e')
        tk.Button(parent, text="⚡ Применить настройки",
                  command=self.apply_game_mode_settings,
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9, 'bold'), padx=15, pady=5,
                  borderwidth=0, cursor='hand2',
                  activebackground=COLORS['primary_hover']
                  ).grid(row=2, column=0, sticky='ew', padx=15, pady=(5, 15))

    def create_ipset_controls(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        tk.Label(parent, text="Управление списками IP-адресов\nдля фильтрации трафика",
                 font=('Segoe UI', 9), bg=COLORS['panel_bg'],
                 fg=COLORS['text_secondary'], justify='left'
                 ).grid(row=0, column=0, sticky='w', padx=15, pady=(15, 10))
        sf = tk.Frame(parent, bg=COLORS['panel_bg'])
        sf.grid(row=1, column=0, sticky='ew', padx=15, pady=5)
        tk.Label(sf, text="Статус:", font=('Segoe UI', 10),
                 bg=COLORS['panel_bg'], fg=COLORS['text_primary']).pack(side='left')
        states = ["Нет", "Любой", "Загружен"]
        cur = self.ipset_var.get()
        self.ipset_status_label = tk.Label(sf,
            text=states[cur] if 0 <= cur < len(states) else "—",
            font=('Segoe UI', 10, 'bold'), bg=COLORS['panel_bg'],
            fg=COLORS['text_primary'] if cur == 2 else COLORS['text_secondary'])
        self.ipset_status_label.pack(side='left', padx=(5, 0))
        mf = tk.Frame(parent, bg=COLORS['panel_bg'])
        mf.grid(row=2, column=0, sticky='ew', padx=15, pady=10)
        self.ipset_buttons = []
        for i, m in enumerate(["❌ Нет", "🌍 Любой", "📥 Загружен"]):
            b = tk.Button(mf, text=m, command=lambda idx=i: self.set_ipset_state(idx),
                          bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                          font=('Segoe UI', 9), padx=10, pady=5,
                          borderwidth=0, cursor='hand2',
                          activebackground=COLORS['panel_header'])
            b.pack(side='left', padx=(0, 5)); self.ipset_buttons.append(b)
        self.update_ipset_buttons()
        bf = tk.Frame(parent, bg=COLORS['panel_bg'])
        bf.grid(row=3, column=0, sticky='ew', padx=15, pady=5)
        bf.grid_columnconfigure(0, weight=1); bf.grid_columnconfigure(1, weight=1)
        tk.Button(bf, text="🔄 Обновить", command=self.update_ipset,
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9, 'bold'), padx=10, pady=5,
                  borderwidth=0, cursor='hand2',
                  activebackground=COLORS['primary_hover']
                  ).grid(row=0, column=0, sticky='ew', padx=(0, 5))
        tk.Button(bf, text="🔍 Проверить", command=self.test_ipset,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9), padx=10, pady=5,
                  borderwidth=0, cursor='hand2',
                  activebackground=COLORS['panel_header']
                  ).grid(row=0, column=1, sticky='ew', padx=(5, 0))

    def create_toggle_switch(self, parent, variable):
        frame = tk.Frame(parent, bg=parent.cget('bg'))
        canvas = tk.Canvas(frame, width=60, height=28,
                           bg=parent.cget('bg'), highlightthickness=0)
        canvas.pack()

        def draw():
            canvas.delete("all")
            if variable.get():
                canvas.create_rectangle(2, 2, 58, 26, fill=COLORS['success'],
                                        outline=COLORS['border'], width=1)
                canvas.create_oval(34, 4, 56, 24, fill=COLORS['text_primary'],
                                   outline=COLORS['border'], width=1)
                canvas.create_text(16, 14, text="ON", fill=COLORS['text_primary'],
                                   font=('Segoe UI', 9, 'bold'))
            else:
                canvas.create_rectangle(2, 2, 58, 26, fill=COLORS['bg_tertiary'],
                                        outline=COLORS['border'], width=1)
                canvas.create_oval(4, 4, 26, 24, fill=COLORS['text_secondary'],
                                   outline=COLORS['border'], width=1)
                canvas.create_text(44, 14, text="OFF", fill=COLORS['text_secondary'],
                                   font=('Segoe UI', 9))

        def toggle():
            variable.set(not variable.get())
            draw()
            self.save_config()
            self.log(f"🎮 Игровой режим: {'включен' if variable.get() else 'выключен'}")
            self.update_game_filter_file()
            self.apply_game_mode_settings()

        canvas.bind("<Button-1>", lambda e: toggle())
        draw()
        self._game_toggle_redraw = draw
        return frame

    def set_ipset_state(self, state):
        self.ipset_var.set(state)
        self.update_ipset_buttons()
        self.save_config()
        states = ["Нет", "Любой", "Загружен"]
        self.log(f"🌐 IP-Set: {states[state] if 0 <= state < len(states) else '?'}")
        self.apply_ipset_settings()

    def update_ipset_buttons(self):
        cur = self.ipset_var.get()
        states = ["Нет", "Любой", "Загружен"]
        for i, b in enumerate(self.ipset_buttons):
            if i == cur:
                b.config(bg=COLORS['primary'], fg=COLORS['text_primary'])
            else:
                b.config(bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'])
        if hasattr(self, 'ipset_status_label'):
            text = states[cur] if 0 <= cur < len(states) else "—"
            fg = COLORS['text_primary'] if cur == 2 else COLORS['text_secondary']
            self.ipset_status_label.config(text=text, fg=fg)

    # ==================== ПРОФИЛИ ====================
    def create_profiles_content(self):
        tab = tk.Frame(self.tab_container, bg=COLORS['bg_primary'])
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=3); tab.grid_columnconfigure(1, weight=1)
        lp = self.create_studio_panel(tab, "📁 ДОСТУПНЫЕ ПРОФИЛИ")
        lp.master.grid(row=0, column=0, sticky='nsew', padx=(0, 1), pady=1)
        self.create_profiles_list(lp)
        cp = self.create_studio_panel(tab, "⚡ УПРАВЛЕНИЕ")
        cp.master.grid(row=0, column=1, sticky='nsew', padx=(1, 0), pady=1)
        self.create_profile_controls(cp)
        return tab

    def create_profiles_list(self, parent):
        parent.grid_rowconfigure(0, weight=1); parent.grid_columnconfigure(0, weight=1)
        lf = tk.Frame(parent, bg=COLORS['bg_tertiary'])
        lf.grid(row=0, column=0, sticky='nsew', padx=2, pady=2)
        lf.grid_rowconfigure(0, weight=1); lf.grid_columnconfigure(0, weight=1)
        self.profile_listbox = tk.Listbox(lf, bg=COLORS['bg_tertiary'],
                                          fg=COLORS['text_primary'],
                                          selectbackground=COLORS['primary'],
                                          selectforeground=COLORS['text_primary'],
                                          font=('Consolas', 10), borderwidth=0)
        self.profile_listbox.grid(row=0, column=0, sticky='nsew', padx=1, pady=1)
        sb = tk.Scrollbar(lf, bg=COLORS['bg_tertiary'], troughcolor=COLORS['panel_bg'])
        sb.grid(row=0, column=1, sticky='ns')
        self.profile_listbox.config(yscrollcommand=sb.set)
        sb.config(command=self.profile_listbox.yview)
        self.refresh_profiles()

    def create_profile_controls(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        for i, (t, c) in enumerate([
            ("🔄 Обновить список", self.refresh_profiles),
            ("🚀 Запустить выбранный", self.run_selected_profile),
            ("⭐ Поставить по умолчанию", self.set_default_profile),
            ("➕ Создать новый", self.create_real_profile),
            ("✏️ Редактировать", self.edit_real_profile),
            ("🗑️ Удалить", self.delete_profile),
            ("📋 Экспорт профиля", self.export_real_profile),
            ("📥 Импорт профиля", self.import_real_profile),
            ("⚡ Тест профиля", self.test_profile),
        ]):
            btn = self.create_studio_button(parent, t, c)
            btn.grid(row=i, column=0, sticky='ew', padx=10, pady=5, ipady=8)

    def set_default_profile(self):
        try:
            s = self.profile_listbox.curselection()
            if not s:
                messagebox.showwarning("Внимание", "Выберите профиль"); return
            p = self.profile_listbox.get(s[0])
            self.default_profile = p
            if hasattr(self, 'profile_name_label'):
                self.profile_name_label.config(text=p)
            if hasattr(self, 'current_profile_label'):
                self.current_profile_label.config(text=p)
            self.save_config()
            self.log(f"⭐ Профиль по умолчанию: {p}")
            messagebox.showinfo("Успех", f"Профиль '{p}' установлен по умолчанию")
        except Exception as e:
            self.log(f"❌ {e}")

    def create_real_profile(self):
        name = simpledialog.askstring("Создание профиля", "Введите имя профиля:")
        if not name:
            return
        content = (f"# Fixcrown Zapret Profile: {name}\n"
                   f"# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                   f"[Settings]\nGameMode={'yes' if self.game_filter_var.get() else 'no'}\n"
                   f"IPSetMode={self.ipset_var.get()}\n")
        try:
            with open(os.path.join(DATA_PATH, f"{name}.zapret"), 'w', encoding='utf-8') as f:
                f.write(content)
            self.log(f"✅ Профиль создан: {name}.zapret")
            self.refresh_profiles()
        except Exception as e:
            self.log(f"❌ {e}")

    def edit_real_profile(self):
        try:
            s = self.profile_listbox.curselection()
            if not s:
                messagebox.showwarning("Внимание", "Выберите профиль"); return
            p = self.profile_listbox.get(s[0])
            if p.endswith('.zapret'):
                os.startfile(os.path.join(DATA_PATH, p))
                self.log(f"✏️ Открыт: {p}")
            else:
                self.log("⚠️ Только .zapret можно редактировать")
        except Exception as e:
            self.log(f"❌ {e}")

    def export_real_profile(self):
        try:
            s = self.profile_listbox.curselection()
            if not s:
                messagebox.showwarning("Внимание", "Выберите профиль"); return
            p = self.profile_listbox.get(s[0])
            dst = filedialog.asksaveasfilename(defaultextension=".zapret",
                                                filetypes=[("Zapret profiles", "*.zapret")],
                                                initialfile=p)
            if dst:
                shutil.copy2(os.path.join(DATA_PATH, p), dst)
                self.log(f"📋 Экспортирован: {dst}")
        except Exception as e:
            self.log(f"❌ {e}")

    def import_real_profile(self):
        try:
            src = filedialog.askopenfilename(filetypes=[("Zapret profiles", "*.zapret")])
            if src:
                n = os.path.basename(src)
                shutil.copy2(src, os.path.join(DATA_PATH, n))
                self.log(f"📥 Импортирован: {n}")
                self.refresh_profiles()
        except Exception as e:
            self.log(f"❌ {e}")

    def test_profile(self):
        try:
            s = self.profile_listbox.curselection()
            if not s:
                messagebox.showwarning("Внимание", "Выберите профиль"); return
            p = self.profile_listbox.get(s[0])
            if os.path.exists(os.path.join(DATA_PATH, p)):
                self.log(f"✅ Профиль '{p}' существует")
            else:
                self.log(f"❌ Профиль '{p}' не найден")
        except Exception as e:
            self.log(f"❌ {e}")

    def refresh_profiles(self):
        try:
            self.profile_listbox.delete(0, tk.END)
            profiles = []
            for ext in ['.bat', '.zapret', '.conf', '.ovpn']:
                profiles.extend([f for f in os.listdir(DATA_PATH) if f.endswith(ext)])
            sys_files = ['service.bat', 'general.bat', 'service_custom.bat', 'general_custom.bat']
            profiles = [p for p in profiles if p not in sys_files]
            if 'general.bat' not in profiles and os.path.exists(os.path.join(DATA_PATH, 'general.bat')):
                profiles.append('general.bat')
            for p in sorted(profiles):
                self.profile_listbox.insert(tk.END, p)
            self.log(f"📁 Профилей: {len(profiles)}")
        except Exception as e:
            self.log(f"❌ {e}")

    def run_selected_profile(self):
        try:
            s = self.profile_listbox.curselection()
            if not s:
                messagebox.showwarning("Внимание", "Выберите профиль"); return
            p = self.profile_listbox.get(s[0])
            self.log(f"🚀 Запуск профиля: {p}")
            threading.Thread(target=self.run_bat_profile,
                             args=(os.path.join(DATA_PATH, p), p), daemon=True).start()
        except Exception as e:
            self.log(f"❌ {e}")

    def run_bat_profile(self, path, name):
        try:
            pr = subprocess.Popen([path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   stdin=subprocess.PIPE, shell=True, text=True,
                                   encoding='utf-8', errors='ignore')
            for line in iter(pr.stdout.readline, ''):
                if line.strip():
                    self.log(f"[{name}] {line.strip()}")
            pr.stdout.close(); pr.wait()
            self.log(f"✅ Профиль {name} завершен")
        except Exception as e:
            self.log(f"❌ {name}: {e}")

    def delete_profile(self):
        try:
            s = self.profile_listbox.curselection()
            if not s:
                messagebox.showwarning("Внимание", "Выберите профиль"); return
            p = self.profile_listbox.get(s[0])
            if p == self.default_profile:
                messagebox.showwarning("Внимание", "Нельзя удалить профиль по умолчанию"); return
            if messagebox.askyesno("Подтверждение", f"Удалить профиль '{p}'?"):
                os.remove(os.path.join(DATA_PATH, p))
                self.log(f"🗑️ Удален: {p}")
                self.refresh_profiles()
        except Exception as e:
            self.log(f"❌ {e}")

    # ==================== ДОМЕНЫ ====================
    def create_domains_content(self):
        tab = tk.Frame(self.tab_container, bg=COLORS['bg_primary'])
        tab.grid_rowconfigure(0, weight=1); tab.grid_columnconfigure(0, weight=1)
        p = self.create_studio_panel(tab, "🌐 РЕДАКТОР ДОМЕНОВ (list-general.txt)")
        p.master.grid(row=0, column=0, sticky='nsew', padx=1, pady=1)
        p.grid_rowconfigure(0, weight=1); p.grid_rowconfigure(1, weight=0); p.grid_rowconfigure(2, weight=0)
        p.grid_columnconfigure(0, weight=1)
        ef = tk.Frame(p, bg=COLORS['panel_bg'])
        ef.grid(row=0, column=0, sticky='nsew', padx=2, pady=(2, 0))
        ef.grid_rowconfigure(1, weight=1); ef.grid_columnconfigure(0, weight=1)
        ir = tk.Frame(ef, bg=COLORS['panel_bg'])
        ir.grid(row=0, column=0, sticky='ew', padx=5, pady=(5, 2))
        tk.Label(ir, text="Домены и правила (по одному в строке, # — комментарий):",
                 font=('Segoe UI', 10), bg=COLORS['panel_bg'],
                 fg=COLORS['text_secondary']).pack(side='left')
        self.domains_editor_status = tk.Label(ir, text="", font=('Segoe UI', 9),
                                              bg=COLORS['panel_bg'], fg=COLORS['success'])
        self.domains_editor_status.pack(side='right')
        self.domains_editor_text = scrolledtext.ScrolledText(
            ef, bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
            font=('Consolas', 10), insertbackground=COLORS['primary'],
            borderwidth=0, wrap='none', undo=True)
        self.domains_editor_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        self.domains_editor_text.bind('<Control-s>', lambda e: (self.save_domains(), 'break')[1])
        self.domains_editor_text.bind('<Control-r>', lambda e: (self.load_domains_into_editor(), 'break')[1])
        af = tk.Frame(p, bg=COLORS['panel_header'])
        af.grid(row=1, column=0, sticky='ew', padx=2, pady=2); af.grid_columnconfigure(1, weight=1)
        tk.Label(af, text="Добавить домен:", font=('Segoe UI', 10),
                 bg=COLORS['panel_header'], fg=COLORS['text_primary']
                 ).grid(row=0, column=0, sticky='w', padx=(10, 5), pady=8)
        self.domains_add_entry = tk.Entry(af, bg=COLORS['bg_tertiary'],
                                          fg=COLORS['text_primary'],
                                          insertbackground=COLORS['primary'],
                                          font=('Consolas', 10), borderwidth=0)
        self.domains_add_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=8, ipady=4)
        self.domains_add_entry.bind('<Return>', lambda e: self.add_domain_to_list())
        tk.Button(af, text="➕ Добавить", command=self.add_domain_to_list,
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9, 'bold'), padx=15, pady=4,
                  borderwidth=0, cursor='hand2',
                  activebackground=COLORS['primary_hover']
                  ).grid(row=0, column=2, padx=5, pady=8)
        cf = tk.Frame(p, bg=COLORS['panel_bg'])
        cf.grid(row=2, column=0, sticky='ew', padx=2, pady=2)
        for c in range(5):
            cf.grid_columnconfigure(c, weight=1)
        tk.Button(cf, text="💾 Сохранить", command=self.save_domains,
                  bg=COLORS['success'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10, 'bold'), padx=15, pady=8,
                  borderwidth=0, cursor='hand2', activebackground='#0a6b0a'
                  ).grid(row=0, column=0, sticky='ew', padx=(5, 2), pady=5)
        tk.Button(cf, text="🔄 Перезагрузить", command=self.load_domains_into_editor,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10), padx=15, pady=8, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).grid(row=0, column=1, sticky='ew', padx=2, pady=5)
        tk.Button(cf, text="🧹 Убрать дубликаты", command=self.dedupe_domains,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10), padx=15, pady=8, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).grid(row=0, column=2, sticky='ew', padx=2, pady=5)
        tk.Button(cf, text="📂 Открыть в блокноте", command=self.open_domains_file,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10), padx=15, pady=8, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).grid(row=0, column=3, sticky='ew', padx=2, pady=5)
        tk.Button(cf, text="📥 Импорт файла", command=self.import_domains,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10), padx=15, pady=8, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).grid(row=0, column=4, sticky='ew', padx=(2, 5), pady=5)
        self.load_domains_into_editor()
        return tab

    def load_domains_into_editor(self):
        if not hasattr(self, 'domains_editor_text'):
            return
        try:
            c = ""
            if os.path.exists(self.domains_file):
                with open(self.domains_file, 'r', encoding='utf-8') as f:
                    c = f.read()
            self.domains_editor_text.delete("1.0", tk.END)
            self.domains_editor_text.insert("1.0", c)
            self.domains_editor_status.config(text=f"✅ Загружено ({len(c)} симв.)",
                                              fg=COLORS['success'])
        except Exception as e:
            self.log(f"❌ {e}")

    def save_domains(self):
        if not hasattr(self, 'domains_editor_text'):
            return
        try:
            c = self.domains_editor_text.get("1.0", tk.END)
            if c.endswith('\n'):
                c = c[:-1]
            os.makedirs(os.path.dirname(self.domains_file), exist_ok=True)
            with open(self.domains_file, 'w', encoding='utf-8') as f:
                f.write(c)
            self.domains_editor_status.config(text="✅ Сохранено", fg=COLORS['success'])
            self.log(f"💾 Домены сохранены ({len(c)} симв.)")
        except Exception as e:
            self.log(f"❌ {e}")

    def add_domain_to_list(self):
        if not hasattr(self, 'domains_add_entry'):
            return
        raw = self.domains_add_entry.get().strip()
        if not raw:
            return
        d = raw.replace('http://', '').replace('https://', '').split('/')[0].split(':')[0].strip().lower()
        if not d:
            return
        try:
            c = self.domains_editor_text.get("1.0", tk.END)
            if c.endswith('\n'):
                c = c[:-1]
            if c and not c.endswith('\n'):
                c += '\n'
            c += d + '\n'
            self.domains_editor_text.delete("1.0", tk.END)
            self.domains_editor_text.insert("1.0", c)
            self.domains_editor_text.see(tk.END)
            self.domains_add_entry.delete(0, tk.END)
            self.domains_editor_status.config(text=f"➕ Добавлено: {d} (сохрани)",
                                              fg=COLORS['warning'])
            self.log(f"➕ Добавлен домен: {d}")
        except Exception as e:
            self.log(f"❌ {e}")

    def dedupe_domains(self):
        if not hasattr(self, 'domains_editor_text'):
            return
        try:
            c = self.domains_editor_text.get("1.0", tk.END)
            seen, result, removed = set(), [], 0
            for line in c.split('\n'):
                s = line.strip()
                if not s:
                    if result and result[-1] == '':
                        continue
                    result.append(''); continue
                if s in seen:
                    removed += 1; continue
                seen.add(s); result.append(s)
            while result and result[-1] == '':
                result.pop()
            nc = '\n'.join(result) + ('\n' if result else '')
            self.domains_editor_text.delete("1.0", tk.END)
            self.domains_editor_text.insert("1.0", nc)
            self.domains_editor_status.config(text=f"🧹 Удалено дубликатов: {removed}",
                                              fg=COLORS['warning'])
            self.log(f"🧹 Удалено дубликатов: {removed}")
        except Exception as e:
            self.log(f"❌ {e}")

    def import_domains(self):
        try:
            fp = filedialog.askopenfilename(title="Импорт списка доменов",
                                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
            if not fp:
                return
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                c = f.read()
            self.domains_editor_text.delete("1.0", tk.END)
            self.domains_editor_text.insert("1.0", c)
            self.domains_editor_status.config(
                text=f"📥 Импортировано: {os.path.basename(fp)}",
                fg=COLORS['primary'])
            self.log(f"📥 Импортирован список: {fp}")
        except Exception as e:
            self.log(f"❌ {e}")

    # ==================== ЛОГИ ====================
    def create_logs_content(self):
        tab = tk.Frame(self.tab_container, bg=COLORS['bg_primary'])
        tab.grid_rowconfigure(0, weight=1); tab.grid_columnconfigure(0, weight=1)
        lp = self.create_studio_panel(tab, "📜 ЛОГИ СИСТЕМЫ")
        lp.master.grid(row=0, column=0, sticky='nsew', padx=1, pady=1)
        lp.grid_rowconfigure(0, weight=1); lp.grid_columnconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(lp, bg=COLORS['bg_tertiary'],
                                                   fg=COLORS['text_primary'],
                                                   font=('Consolas', 9),
                                                   insertbackground=COLORS['primary'],
                                                   borderwidth=0)
        self.log_text.grid(row=0, column=0, sticky='nsew', padx=2, pady=2)
        cf = tk.Frame(lp, bg=COLORS['panel_bg'])
        cf.grid(row=1, column=0, sticky='ew', padx=2, pady=2)
        tk.Button(cf, text="🧹 Очистить", command=self.clear_logs,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9), padx=15, pady=5, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).pack(side='left', padx=(0, 5))
        tk.Button(cf, text="💾 Сохранить", command=self.save_logs,
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9), padx=15, pady=5, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['primary_hover']
                  ).pack(side='left')
        tk.Button(cf, text="📊 Экспорт в CSV", command=self.export_logs_csv,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9), padx=15, pady=5, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).pack(side='left', padx=(5, 0))
        return tab

    # ==================== НАСТРОЙКИ ====================
    def create_settings_content(self):
        tab = tk.Frame(self.tab_container, bg=COLORS['bg_primary'])
        tab.grid_rowconfigure(0, weight=1); tab.grid_columnconfigure(0, weight=1)
        sp = self.create_studio_panel(tab, "⚙️ НАСТРОЙКИ ПРИЛОЖЕНИЯ")
        sp.master.grid(row=0, column=0, sticky='nsew', padx=1, pady=1)
        canvas = tk.Canvas(sp, bg=COLORS['panel_bg'], highlightthickness=0)
        sb = tk.Scrollbar(sp, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=COLORS['panel_bg'])
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.create_app_settings(sf)
        return tab

    def create_app_settings(self, parent):
        parent.grid_columnconfigure(0, weight=1)

        lf = tk.Frame(parent, bg=COLORS['panel_bg'])
        lf.grid(row=0, column=0, sticky='ew', padx=20, pady=(20, 10))
        tk.Label(lf, text="Домены (list-general.txt):", font=('Segoe UI', 11),
                 bg=COLORS['panel_bg'], fg=COLORS['text_primary']
                 ).pack(side='left', padx=(0, 10))
        tk.Button(lf, text="📂 Открыть", command=self.open_domains_file,
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9), padx=15, pady=3, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['primary_hover']
                  ).pack(side='left')

        tk.Label(parent, text="Инструменты", font=('Segoe UI', 14, 'bold'),
                 bg=COLORS['panel_bg'], fg=COLORS['text_primary'], anchor='w'
                 ).grid(row=1, column=0, sticky='w', padx=20, pady=(20, 10))
        tf = tk.Frame(parent, bg=COLORS['panel_bg'])
        tf.grid(row=2, column=0, sticky='ew', padx=20, pady=5)
        for c in range(3): tf.grid_columnconfigure(c, weight=1)
        tk.Button(tf, text="📂 Открыть service.bat", command=self.open_service_bat,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9), padx=15, pady=8, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).grid(row=0, column=0, sticky='ew', padx=(0, 5), ipady=4)
        tk.Button(tf, text="📦 Обновить из ZIP", command=self.update_from_zip,
                  bg=COLORS['warning'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9, 'bold'), padx=15, pady=8, borderwidth=0,
                  cursor='hand2', activebackground='#cc7000'
                  ).grid(row=0, column=1, sticky='ew', padx=5, ipady=4)
        tk.Button(tf, text="🔄 Проверить обновления", command=self.check_for_updates,
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 9, 'bold'), padx=15, pady=8, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['primary_hover']
                  ).grid(row=0, column=2, sticky='ew', padx=(5, 0), ipady=4)
        tk.Label(parent, text="Инструменты позволяют управлять службой, обновлять запрет из архива и проверять новые версии.",
                 font=('Segoe UI', 8), bg=COLORS['panel_bg'], fg=COLORS['text_muted'],
                 anchor='w', justify='left').grid(row=3, column=0, sticky='w',
                                                  padx=20, pady=(0, 15))

        tk.Label(parent, text="Параметры приложения", font=('Segoe UI', 14, 'bold'),
                 bg=COLORS['panel_bg'], fg=COLORS['text_primary'], anchor='w'
                 ).grid(row=4, column=0, sticky='w', padx=20, pady=(10, 10))
        sff = tk.Frame(parent, bg=COLORS['panel_bg'])
        sff.grid(row=5, column=0, sticky='ew', padx=20, pady=5)
        tk.Checkbutton(sff,
                       text="Автозапуск",
                       variable=self.auto_start_var,
                       command=self.on_autostart_change,
                       font=('Segoe UI', 11), bg=COLORS['panel_bg'],
                       fg=COLORS['text_primary'], selectcolor=COLORS['primary'],
                       activebackground=COLORS['panel_bg'],
                       activeforeground=COLORS['text_primary'],
                       cursor='hand2').pack(side='left', pady=5)
        tk.Label(parent,
                 text="При включении Fixcrown Zapret добавляется в автозагрузку Windows и при старте автоматически подключает winws.exe.",
                 font=('Segoe UI', 8), bg=COLORS['panel_bg'], fg=COLORS['text_muted'],
                 anchor='w', justify='left').grid(row=6, column=0, sticky='w',
                                                  padx=20, pady=(0, 15))

        bf = tk.Frame(parent, bg=COLORS['panel_bg'])
        bf.grid(row=7, column=0, sticky='ew', padx=20, pady=(30, 20))
        for c in range(3): bf.grid_columnconfigure(c, weight=1)
        tk.Button(bf, text="🔄 Сбросить", command=self.reset_all_settings,
                  bg=COLORS['bg_tertiary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10), padx=20, pady=10, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['panel_header']
                  ).grid(row=0, column=0, sticky='ew', padx=(0, 5))
        tk.Button(bf, text="💾 Сохранить", command=self.save_and_apply_settings,
                  bg=COLORS['primary'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10, 'bold'), padx=20, pady=10, borderwidth=0,
                  cursor='hand2', activebackground=COLORS['primary_hover']
                  ).grid(row=0, column=1, sticky='ew', padx=5)
        tk.Button(bf, text="⚡ Применить", command=self.apply_settings,
                  bg=COLORS['success'], fg=COLORS['text_primary'],
                  font=('Segoe UI', 10, 'bold'), padx=20, pady=10, borderwidth=0,
                  cursor='hand2', activebackground='#0a6b0a'
                  ).grid(row=0, column=2, sticky='ew', padx=(5, 0))

    def create_footer(self):
        footer = tk.Frame(self.main_container, bg=COLORS['bg_secondary'], height=30)
        footer.grid(row=2, column=0, sticky='ew', padx=1, pady=(1, 0))
        footer.grid_propagate(False)
        lf = tk.Frame(footer, bg=COLORS['bg_secondary']); lf.pack(side='left', padx=20)
        tk.Label(lf, text=f"Fixcrown Zapret • v{APP_VERSION}",
                 font=('Segoe UI', 9), bg=COLORS['bg_secondary'],
                 fg=COLORS['text_secondary']).pack(side='left')
        self.connection_info = tk.Label(lf, text="Готов к работе",
                                        font=('Segoe UI', 9), bg=COLORS['bg_secondary'],
                                        fg=COLORS['text_secondary'])
        self.connection_info.pack(side='left', padx=20)
        rf = tk.Frame(footer, bg=COLORS['bg_secondary']); rf.pack(side='right', padx=20)
        for text, cb in [("🔍 Починка роблокса в РФ", self.open_guide),
                         ("💬 Поддержка", self.open_support)]:
            lbl = tk.Label(rf, text=text, font=('Segoe UI', 9),
                           bg=COLORS['bg_secondary'], fg=COLORS['primary'], cursor='hand2')
            lbl.pack(side='left', padx=10)
            lbl.bind("<Button-1>", lambda e, f=cb: f())

    # ==================== КОНФИГ ====================
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    c = json.load(f)
                self.game_filter_var.set(c.get('game_filter', False))
                self.ipset_var.set(c.get('ipset_state', 1))
                self.auto_start_var.set(c.get('auto_start', False))
                self.default_profile = c.get('default_profile', 'general.bat')
                self.was_connected = c.get('was_connected', False)
        except Exception:
            self.log("⚠️ Ошибка загрузки конфигурации")

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'game_filter': self.game_filter_var.get(),
                    'ipset_state': self.ipset_var.get(),
                    'auto_start': self.auto_start_var.get(),
                    'default_profile': self.default_profile,
                    'was_connected': self.was_connected
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ==================== ПРИМЕНЕНИЕ НАСТРОЕК ====================
    def apply_settings(self):
        self.log("🔧 Применение настроек...")
        self.save_config()
        self.apply_game_mode_settings()
        self.apply_ipset_settings()
        self._sync_ui_state()
        self.log("✅ Все настройки применены")

    def apply_game_mode_settings(self):
        if self.game_filter_var.get():
            self.log("🎮 Игровой режим включен")
            try:
                if sys.platform == "win32":
                    gf = os.path.join(DATA_PATH, "utils", "game_filter.enabled")
                    if not os.path.exists(gf):
                        with open(gf, 'w', encoding='utf-8') as f:
                            f.write("ENABLED\n")
            except Exception:
                pass
        else:
            self.log("🎮 Игровой режим отключен")

    def apply_ipset_settings(self):
        state = self.ipset_var.get()
        try:
            os.makedirs(os.path.dirname(self.ipset_all), exist_ok=True)
            if state == 0:
                with open(self.ipset_all, 'w', encoding='utf-8') as f:
                    f.write("203.0.113.113/32\n")
                self.log("🌐 IP-Set: 'Нет'")
            elif state == 1:
                with open(self.ipset_all, 'w', encoding='utf-8') as f:
                    f.write("")
                self.log("🌐 IP-Set: 'Любой'")
            elif state == 2:
                if not os.path.exists(self.ipset_all):
                    self.update_ipset()
                self.log("🌐 IP-Set: 'Загружен'")
        except Exception as e:
            self.log(f"❌ {e}")

    def open_domains_file(self):
        path = self.domains_file
        if os.path.exists(path):
            os.startfile(path)
            self.log(f"📂 Открыт файл: {path}")
        else:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("# Fixcrown Zapret - домены\n")
                os.startfile(path)
                self.log(f"✅ Создан файл: {path}")
            except Exception:
                self.log("❌ Не удалось создать файл")

    def open_service_bat(self):
        sp = os.path.join(DATA_PATH, "service.bat")
        if not os.path.exists(sp):
            self.log("❌ service.bat не найден")
            messagebox.showerror("Ошибка", "Файл service.bat не найден")
            return
        try:
            os.startfile(sp)
            self.log("📂 Открыт service.bat")
        except Exception as e:
            self.log(f"❌ {e}")

    # ==================== ИНСТРУМЕНТЫ ====================
    def update_from_zip(self):
        zip_path = filedialog.askopenfilename(
            title="Выберите ZIP-архив с новой версией",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")])
        if not zip_path:
            return
        if not messagebox.askyesno("Обновление из ZIP",
                                    f"Обновление из:\n{zip_path}\n\nТекущий запрет будет остановлен.\nПродолжить?"):
            return

        def worker():
            try:
                self.log("⏹️ Остановка запрета...")
                self.disconnect()
                time.sleep(2)
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    self.log(f"📦 Распаковка: {zip_path}")
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            zf.extractall(tmpdir)
                    except Exception as e:
                        self.log(f"❌ {e}")
                        self.root.after(0, lambda: messagebox.showerror("Ошибка", f"ZIP:\n{e}"))
                        return
                    items = os.listdir(tmpdir)
                    sr = os.path.join(tmpdir, items[0]) if len(items) == 1 and os.path.isdir(
                        os.path.join(tmpdir, items[0])) else tmpdir
                    copied = 0
                    for root, dirs, files in os.walk(sr):
                        rel = os.path.relpath(root, sr)
                        dd = os.path.join(DATA_PATH, rel) if rel != "." else DATA_PATH
                        os.makedirs(dd, exist_ok=True)
                        for fn in files:
                            try:
                                shutil.copy2(os.path.join(root, fn), os.path.join(dd, fn))
                                copied += 1
                            except Exception as e:
                                self.log(f"⚠️ {fn}: {e}")
                    self.log(f"✅ Скопировано: {copied}")
                try:
                    self.root.after(0, self.refresh_profiles)
                    nv = self.get_zapret_version()
                    if nv:
                        self.zapret_version = nv
                        self.root.after(0, self._update_window_title)
                except Exception:
                    pass
                self.log("▶️ Запуск запрета...")
                time.sleep(1)
                self.connect()
                self.root.after(0, lambda: messagebox.showinfo(
                    "Обновление завершено", f"Скопировано файлов: {copied}"))
            except Exception as e:
                self.log(f"❌ {e}")

        threading.Thread(target=worker, daemon=True).start()

    def check_for_updates(self):
        def worker():
            self.log("🔄 Проверка Fixcrown...")
            try:
                req = urllib.request.Request(GITHUB_API_COMMITS,
                                              headers={'User-Agent': 'FixcrownZapret-Updater'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                self.log(f"❌ Сеть: {e}")
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"{e}"))
                return
            if not data:
                return
            msg = data[0].get('commit', {}).get('message', '')
            m = re.search(r'[Vv]?(\d+\.\d+(?:\.\d+)*)', msg)
            if not m:
                return
            rv = m.group(1)
            self.log(f"📡 На GitHub: {rv}")

            def show():
                if self._version_tuple(rv) > self._version_tuple(APP_VERSION):
                    if messagebox.askyesno("Доступно обновление",
                                            f"Текущая: {APP_VERSION}\nНовая: {rv}\n\nПерейти на загрузку?"):
                        webbrowser.open(GITHUB_RELEASES_URL)
                else:
                    messagebox.showinfo("Обновления не найдены",
                                        f"Актуальная версия: {APP_VERSION}\nНа GitHub: {rv}")
            self.root.after(0, show)
        threading.Thread(target=worker, daemon=True).start()

    # ==================== ПОДКЛЮЧЕНИЕ ====================
    def toggle_connection(self):
        if self._operation_in_progress:
            return
        if not self.is_connected:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        if self._operation_in_progress:
            return
        self._operation_in_progress = True
        self.connect_btn.config(text="⏳ ПОДКЛЮЧЕНИЕ...", state='disabled', bg=COLORS['bg_tertiary'])

        def worker():
            try:
                self._winws_check_cache = None
                if self.is_winws_running():
                    self.log("ℹ️ winws.exe уже запущен")
                    self.is_connected = True
                    if not self.connection_start_time:
                        self.connection_start_time = datetime.now()
                    self.was_connected = True
                    self.save_config()
                    self.root.after(0, self._finish_connect, True, "уже запущен")
                    return

                if not os.path.exists(self.winws_path):
                    self.root.after(0, self._finish_connect, False,
                                    "winws.exe не найден (положите в корень или bin/)")
                    return

                pp = os.path.join(DATA_PATH, self.default_profile)
                if not os.path.exists(pp):
                    fb = os.path.join(DATA_PATH, "general.bat")
                    if os.path.exists(fb):
                        self.default_profile = "general.bat"; pp = fb
                        self.log("📋 Используется general.bat")
                    else:
                        self.root.after(0, self._finish_connect, False, "Профиль не найден")
                        return

                self.log(f"🔗 Запуск профиля: {self.default_profile}")
                self.log(f"📄 Полный путь: {pp}")

                profile_dir = os.path.dirname(pp)
                profile_name = os.path.basename(pp)

                self._winws_check_cache = None
                self.winws_process = subprocess.Popen(
                    ['cmd', '/c', profile_name],
                    cwd=profile_dir,
                    creationflags=_NO_WINDOW,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT
                )

                threading.Thread(
                    target=self._drain_bat_output,
                    args=(self.winws_process,),
                    daemon=True
                ).start()

                for i in range(1, 16):
                    time.sleep(1)
                    if not self.running:
                        return
                    self._winws_check_cache = None
                    if self.is_winws_running():
                        self.root.after(0, self._finish_connect, True,
                                        f"winws.exe запущен ({i}/15)")
                        return
                    self.log(f"⏳ Попытка обнаружить winws.exe ({i}/15)")

                self.root.after(0, self._finish_connect, False,
                                "winws.exe не появился за 15 сек. "
                                "Смотри строки [bat] в логе — там вывод батника")
            except Exception as e:
                self.log(f"❌ Ошибка подключения: {e}")
                self.root.after(0, self._finish_connect, False, str(e))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_bat_output(self, proc):
        if not proc or not proc.stdout:
            return
        try:
            for raw in iter(proc.stdout.readline, b''):
                if not self.running:
                    break
                if not raw:
                    break
                line = _decode_windows_output(raw).rstrip()
                if line.strip():
                    self.log(f"[bat] {line}")
        except Exception:
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

    def _finish_connect(self, ok, msg):
        self._operation_in_progress = False
        self._winws_check_cache = None
        if ok:
            self.is_connected = True
            self.connection_start_time = datetime.now()
            self.was_connected = True
            self.save_config()
            self.log(f"✅ {msg}")
        else:
            self.is_connected = False
            self.connection_start_time = None
            self.was_connected = False
            self.save_config()
            self.log(f"❌ {msg}")
            messagebox.showerror("Ошибка подключения", f"Не удалось запустить запрет.\n{msg}")
        self.update_connection_status()

    def disconnect(self):
        if self._operation_in_progress:
            return
        self._operation_in_progress = True
        self.connect_btn.config(text="⏳ ОТКЛЮЧЕНИЕ...", state='disabled', bg=COLORS['bg_tertiary'])

        def worker():
            try:
                self.log("🔗 Отключение...")
                if self.winws_process is not None:
                    try:
                        if self.winws_process.poll() is None:
                            self.winws_process.terminate()
                    except Exception:
                        pass
                    finally:
                        self.winws_process = None
                self._winws_check_cache = None
                if self.is_winws_running():
                    if kill_processes_by_image('winws.exe'):
                        self.log("✅ Процессы winws.exe завершены")
                    else:
                        self.log("⚠️ taskkill не смог завершить процессы")
                else:
                    self.log("ℹ️ Процесс не был запущен")
                time.sleep(0.5)
                self._winws_check_cache = None
                still = self.is_winws_running()
                self.root.after(0, self._finish_disconnect, not still)
            except Exception as e:
                self.log(f"❌ {e}")
                self.root.after(0, self._finish_disconnect, False)
        threading.Thread(target=worker, daemon=True).start()

    def _finish_disconnect(self, ok):
        self._operation_in_progress = False
        self._winws_check_cache = None
        if ok:
            self.is_connected = False
            self.connection_start_time = None
            self.was_connected = False
            self.save_config()
            self.log("✅ Отключено")
        else:
            self.log("⚠️ Не удалось завершить winws.exe полностью")
        self.update_connection_status()

    def kill_winws_processes(self):
        return kill_processes_by_image('winws.exe')

    # ==================== СЛУЖБА / IP-SET ====================
    def install_service(self):
        sp = os.path.join(DATA_PATH, "service.bat")
        if not os.path.exists(sp):
            return
        try:
            p = subprocess.Popen([sp], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, shell=True, text=True,
                                  encoding='utf-8', errors='ignore')
            for line in iter(p.stdout.readline, ''):
                if line.strip():
                    self.log(f"[SERVICE] {line.strip()}")
            p.stdout.close(); p.wait()
        except Exception as e:
            self.log(f"❌ {e}")

    def remove_service(self):
        try:
            subprocess.run(['sc', 'stop', 'FixcrownZapret'],
                           capture_output=True, text=True, shell=True)
            subprocess.run(['sc', 'delete', 'FixcrownZapret'],
                           capture_output=True, text=True, shell=True)
            self.log("✅ Служба удалена")
        except Exception as e:
            self.log(f"❌ {e}")

    def check_service_status(self):
        try:
            r = subprocess.run(['sc', 'query', 'FixcrownZapret'],
                               capture_output=True, text=True, shell=True)
            for line in (r.stdout or '').split('\n'):
                if line.strip():
                    self.log(f"[STATUS] {line.strip()}")
        except Exception as e:
            self.log(f"❌ {e}")

    def update_ipset(self):
        self.log("🔄 Обновление IP-Set...")
        sp = os.path.join(DATA_PATH, "service.bat")
        if os.path.exists(sp):
            def run():
                try:
                    r = subprocess.run([sp, "ipset_update"], capture_output=True,
                                        text=True, shell=True, timeout=30)
                    for line in (r.stdout or '').split('\n'):
                        if line.strip():
                            self.log(f"[IPSET] {line.strip()}")
                    self.set_ipset_state(2)
                    self.log("✅ IP-Set обновлен")
                except Exception as e:
                    self.log(f"❌ {e}")
            threading.Thread(target=run, daemon=True).start()
        else:
            self.log("❌ service.bat не найден")

    def test_ipset(self):
        self.log("🔍 Тестирование IP-Set...")
        for ip in ['8.8.8.8', '1.1.1.1', '77.88.8.8']:
            try:
                socket.setdefaulttimeout(2)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, 53)); s.close()
                self.log(f"✅ IP {ip}: доступен")
            except Exception:
                self.log(f"❌ IP {ip}: недоступен")

    def run_diagnostics(self):
        self.log("🛠️ Диагностика...")
        try:
            r = subprocess.run(['ipconfig'], capture_output=True, timeout=10, creationflags=_NO_WINDOW)
            for line in _decode_windows_output(r.stdout).split('\n'):
                if 'IPv4' in line or 'адрес' in line:
                    self.log(f"[NET] {line.strip()}")
            r = subprocess.run(['nslookup', 'google.com'], capture_output=True,
                               timeout=10, creationflags=_NO_WINDOW)
            if 'Non-authoritative answer' in _decode_windows_output(r.stdout):
                self.log("✅ DNS работает")
            else:
                self.log("⚠️ Проблемы с DNS")
            self.log("✅ Диагностика завершена")
        except Exception as e:
            self.log(f"❌ {e}")

    def quick_start(self):
        self.game_filter_var.set(True)
        self.ipset_var.set(2)
        self.save_and_apply_settings()
        self.connect()

    # ==================== ЛОГИ ====================
    def clear_logs(self):
        if hasattr(self, 'log_text'):
            self.log_text.delete("1.0", tk.END)
            self.log("🧹 Логи очищены")

    def save_logs(self):
        try:
            fp = filedialog.asksaveasfilename(
                defaultextension=".txt", filetypes=[("Text files", "*.txt")],
                initialfile=f"zapret_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            if fp:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get("1.0", tk.END))
                self.log(f"💾 Логи сохранены: {fp}")
        except Exception as e:
            self.log(f"❌ {e}")

    def export_logs_csv(self):
        try:
            fp = filedialog.asksaveasfilename(
                defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                initialfile=f"zapret_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            if fp:
                logs = self.log_text.get("1.0", tk.END)
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write("Timestamp,Message\n")
                    for line in logs.split('\n'):
                        if line.strip():
                            m = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s+(.*)', line)
                            if m:
                                ts, msg = m.groups()
                                f.write(f'"{ts}","{msg}"\n')
                self.log(f"📊 Экспорт CSV: {fp}")
        except Exception as e:
            self.log(f"❌ {e}")

    # ==================== ВНЕШНИЕ ССЫЛКИ ====================
    def open_guide(self):
        try:
            webbrowser.open("https://t.me/Unblock_Roblox")
        except Exception:
            pass

    def open_support(self):
        try:
            webbrowser.open("https://web.telegram.org/a/#-1003265231345")
        except Exception:
            pass

    # ==================== СБРОС / СОХРАНЕНИЕ ====================
    def reset_all_settings(self):
        if messagebox.askyesno("Подтверждение", "Сбросить все настройки?"):
            try:
                if os.path.exists(self.config_file):
                    os.remove(self.config_file)
                self.game_filter_var.set(False)
                self.ipset_var.set(1)
                self.auto_start_var.set(False)
                self.default_profile = "general.bat"
                self.was_connected = False
                self.remove_autostart()
                self._sync_ui_state()
                if hasattr(self, 'profile_name_label'):
                    self.profile_name_label.config(text=self.default_profile)
                self.log("🔄 Настройки сброшены")
            except Exception as e:
                self.log(f"❌ {e}")

    def save_and_apply_settings(self):
        self.save_config()
        self.apply_settings()

    def get_current_ip(self):
        pass

    # ==================== ЛОГИРОВАНИЕ ====================
    def log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}\n"
        if hasattr(self, 'log_text'):
            try:
                self.log_text.insert(tk.END, entry)
                self.log_text.see(tk.END)
            except Exception:
                pass
        print(entry, end='')

    # ==================== ЗАВЕРШЕНИЕ ====================
    def quit_application(self):
        self.running = False

        if self.winws_process is not None:
            try:
                if self.winws_process.poll() is None:
                    self.winws_process.terminate()
            except Exception:
                pass
            finally:
                self.winws_process = None

        try:
            if check_process_running('winws.exe'):
                kill_processes_by_image('winws.exe')
                self.log("✅ winws.exe остановлен")
        except Exception:
            pass

        if self.root:
            try:
                self.root.quit(); self.root.destroy()
            except Exception:
                pass


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FixcrownZapret(root)
        root.mainloop()
    except Exception as e:
        icon_log(f"FATAL: {e}")
        import traceback
        try:
            p = os.path.join(DATA_PATH, "icon_debug.log")
            with open(p, "a", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise