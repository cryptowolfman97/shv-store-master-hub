"""
SH Vertex Master Hub
Includes: SHV Admin Panel & SHV Customer Store
Version: 2.0.0
"""
import os, json, threading, urllib.request, urllib.parse, urllib.error, io, base64
from datetime import datetime
import ssl

# --- ANDROID SSL VERIFICATION FIX ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass
# ------------------------------------

from kivy.app import App
# ... the rest of your kivy imports continue normally ...
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.uix.image import AsyncImage, Image
from kivy.core.image import Image as CoreImage
from kivy.uix.widget import Widget
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, InstructionGroup
from kivy.utils import get_color_from_hex
from kivy.properties import StringProperty
from kivy.storage.jsonstore import JsonStore

def _get_app_dir():
    """Return the app's private data directory on Android, or cwd on desktop."""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        return PythonActivity.mActivity.getFilesDir().getAbsolutePath()
    except Exception:
        return "."
APP_DIR = _get_app_dir()

def _open_url_in_browser(url):
    """Open a URL in the device browser. Works on Android and desktop."""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent         = autoclass("android.content.Intent")
        Uri            = autoclass("android.net.Uri")
        intent = Intent(Intent.ACTION_VIEW)
        intent.setData(Uri.parse(url))
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        PythonActivity.mActivity.startActivity(intent)
    except Exception:
        import webbrowser
        webbrowser.open(url)

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
SUPABASE_URL = "https://ovdxetyadfsxehwnbyuz.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_3J-H60daCgWdhSvpdXi0zw_QpPax3Dz"
APP_VERSION = "2.0.0"
FONT_PATH = "emoji.ttf"

# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
C_BG        = get_color_from_hex("#000000")
C_SURFACE   = get_color_from_hex("#0D0D0D")
C_CARD      = get_color_from_hex("#141414")
C_CARD2     = get_color_from_hex("#1A1A1A")
C_TEAL      = get_color_from_hex("#00BFA5")
C_TEAL_DARK = get_color_from_hex("#008C78")
C_SLATE     = get_color_from_hex("#546E7A")
C_ROSE      = get_color_from_hex("#EF5350")
C_AMBER     = get_color_from_hex("#F9A825")
C_TEXT      = get_color_from_hex("#FFFFFF")
C_TEXT_SEC  = get_color_from_hex("#9E9E9E")
C_TEXT_HINT = get_color_from_hex("#555555")
C_DIVIDER   = get_color_from_hex("#1F1F1F")
C_NAV       = get_color_from_hex("#0A0A0A")

# ─────────────────────────────────────────────
#  MERGED SUPABASE CLIENT
# ─────────────────────────────────────────────
class SupabaseClient:
    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.key = key
        self.access_token = None
        self.user_id = None
        self.user_email = None

    def _headers(self):
        token = self.access_token or self.key
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _req(self, method, path, data=None, params=None):
        url = self.url + path
        if params: url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read().decode()
                return (json.loads(raw) if raw else {}), r.status
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try: return json.loads(raw), e.code
            except: return {"error": raw}, e.code
        except Exception as ex:
            return {"error": str(ex)}, 0

    def sign_up(self, email, password, display_name=""):
        data = {"email": email, "password": password, "data": {"display_name": display_name}}
        return self._req("POST", "/auth/v1/signup", data=data)

    def sign_in(self, email, password):
        resp, status = self._req("POST", "/auth/v1/token?grant_type=password", data={"email": email, "password": password})
        if status == 200 and "access_token" in resp:
            self.access_token = resp["access_token"]
            self.user_id      = resp.get("user", {}).get("id")
            self.user_email   = resp.get("user", {}).get("email")
        return resp, status

    def sign_out(self):
        self._req("POST", "/auth/v1/logout")
        self.access_token = None
        self.user_id = None
        self.user_email = None

    def is_admin(self):
        if not self.user_id: return False
        resp, status = self._req("GET", "/rest/v1/profiles", params={"id": f"eq.{self.user_id}", "select": "is_admin"})
        if status == 200 and isinstance(resp, list) and resp: return bool(resp[0].get("is_admin"))
        return False

    def select(self, table, params=None):
        p = {"select": "*"}
        if params: p.update(params)
        return self._req("GET", f"/rest/v1/{table}", params=p)

    def select_all(self, table, order=None):
        p = {"select": "*"}
        if order: p["order"] = order
        return self._req("GET", f"/rest/v1/{table}", params=p)

    def select_filtered(self, table, filters, order=None, limit=None):
        p = {"select": "*"}
        p.update(filters)
        if order: p["order"] = order
        if limit: p["limit"] = limit
        return self._req("GET", f"/rest/v1/{table}", params=p)

    def insert(self, table, data):
        return self._req("POST", f"/rest/v1/{table}", data=data)

    def update(self, table, row_id, data):
        return self._req("PATCH", f"/rest/v1/{table}", data=data, params={"id": f"eq.{row_id}"})

    def delete(self, table, row_id):
        return self._req("DELETE", f"/rest/v1/{table}", params={"id": f"eq.{row_id}"})

    def increment_download(self, app_id):
        resp, _ = self._req("GET", "/rest/v1/apps", params={"id": f"eq.{app_id}", "select": "download_count"})
        if isinstance(resp, list) and resp:
            current = resp[0].get("download_count", 0)
            self._req("PATCH", "/rest/v1/apps", data={"download_count": current + 1}, params={"id": f"eq.{app_id}"})

    def get_profile(self):
        if not self.user_id: return None
        resp, status = self._req("GET", "/rest/v1/profiles", params={"id": f"eq.{self.user_id}", "select": "*"})
        if status == 200 and isinstance(resp, list) and resp: return resp[0]
        return None

    def get_contact_info(self):
        resp, status = self._req("GET", "/rest/v1/contact_info", params={"select": "*", "limit": "1"})
        if status == 200 and isinstance(resp, list) and resp:
            return resp[0]
        return {}

    def upsert_contact_info(self, data):
        # Try to fetch existing row first
        resp, status = self._req("GET", "/rest/v1/contact_info", params={"select": "id", "limit": "1"})
        if status == 200 and isinstance(resp, list) and resp:
            row_id = resp[0].get("id")
            return self._req("PATCH", "/rest/v1/contact_info", data=data, params={"id": f"eq.{row_id}"})
        else:
            return self._req("POST", "/rest/v1/contact_info", data=data)

    def get_stats(self):
        apps, _    = self._req("GET", "/rest/v1/apps", params={"select": "id,is_published,download_count"})
        news, _    = self._req("GET", "/rest/v1/news", params={"select": "id,is_published"})
        updates, _ = self._req("GET", "/rest/v1/upcoming_updates", params={"select": "id,status"})
        profiles, _= self._req("GET", "/rest/v1/profiles", params={"select": "id"})
        apps = apps if isinstance(apps, list) else []
        news = news if isinstance(news, list) else []
        updates = updates if isinstance(updates, list) else []
        profiles = profiles if isinstance(profiles, list) else []
        return {
            "total_apps":      len(apps),
            "published_apps":  sum(1 for a in apps if a.get("is_published")),
            "total_news":      len(news),
            "published_news":  sum(1 for n in news if n.get("is_published")),
            "total_updates":   len(updates),
            "in_progress":     sum(1 for u in updates if u.get("status") == "in_progress"),
            "total_users":     len(profiles),
            "total_downloads": sum(a.get("download_count", 0) for a in apps),
        }

supabase = SupabaseClient(SUPABASE_URL, SUPABASE_ANON_KEY)

# ─────────────────────────────────────────────
#  REUSABLE UI COMPONENTS
# ─────────────────────────────────────────────
def make_bg(widget, color, radius=0):
    with widget.canvas.before:
        Color(*color)
        if radius: rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
        else: rect = Rectangle(pos=widget.pos, size=widget.size)
    def _upd(*_):
        rect.pos = widget.pos
        rect.size = widget.size
    widget.bind(pos=_upd, size=_upd)

def load_remote_image(url, fallback_text="📦", size_hint_x=None, width=dp(56), height=dp(56)):
    if not url:
        lbl = Label(text=fallback_text, font_size=sp(36), font_name=FONT_PATH)
        if size_hint_x is not None: lbl.size_hint_x, lbl.width = size_hint_x, width
        lbl.size_hint_y, lbl.height = None, height
        return lbl
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SHVHub/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp: data = resp.read()
        fmt = "png"
        url_lower = url.lower()
        if ".jpg" in url_lower or ".jpeg" in url_lower: fmt = "jpg"
        elif ".gif" in url_lower: fmt = "gif"
        elif ".webp" in url_lower: fmt = "webp"
        core_img = CoreImage(io.BytesIO(data), ext=fmt)
        img = Image(texture=core_img.texture)
        img.size_hint_y, img.height = None, height
        if size_hint_x is not None: img.size_hint_x, img.width = size_hint_x, width
        img.allow_stretch, img.keep_ratio = True, True
        return img
    except Exception:
        lbl = Label(text=fallback_text, font_size=sp(36), font_name=FONT_PATH)
        if size_hint_x is not None: lbl.size_hint_x, lbl.width = size_hint_x, width
        lbl.size_hint_y, lbl.height = None, height
        return lbl

class SHVLabel(Label):
    def __init__(self, **kw):
        kw.setdefault("color", C_TEXT); kw.setdefault("font_size", sp(14))
        kw.setdefault("halign", "left"); kw.setdefault("valign", "middle")
        super().__init__(**kw)
        self.bind(size=lambda *_: setattr(self, "text_size", self.size))

class SHVTextInput(TextInput):
    def __init__(self, **kw):
        kw.setdefault("background_color", (0, 0, 0, 0)); kw.setdefault("background_normal", "")
        kw.setdefault("background_active", ""); kw.setdefault("cursor_color", C_TEAL)
        kw.setdefault("multiline", False); kw.setdefault("write_tab", False)
        kw.setdefault("font_size", sp(14)); kw.setdefault("padding", [dp(12), dp(12)])
        kw.setdefault("size_hint_y", None); kw.setdefault("height", dp(48))
        kw.setdefault("input_type", "text"); kw.setdefault("keyboard_suggestions", True)
        super().__init__(**kw)
        self.foreground_color = (1, 1, 1, 1); self.hint_text_color = (0.6, 0.6, 0.6, 1)
        self._bg_group = InstructionGroup()
        self._bg_group.add(Color(*C_TEAL))
        self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self._bg_group.add(self._border)
        self._bg_group.add(Color(*C_CARD2))
        self._bg = RoundedRectangle(pos=(self.x + dp(1), self.y + dp(1)), size=(self.width - dp(2), self.height - dp(2)), radius=[dp(7)])
        self._bg_group.add(self._bg); self._bg_group.add(Color(1, 1, 1, 1))
        self.canvas.before.insert(0, self._bg_group)
        def _upd(*_):
            self._border.pos, self._border.size = self.pos, self.size
            self._bg.pos, self._bg.size = (self.x + dp(1), self.y + dp(1)), (self.width - dp(2), self.height - dp(2))
        self.bind(pos=_upd, size=_upd)

class SHVMultiInput(TextInput):
    def __init__(self, **kw):
        kw.setdefault("background_color", (0, 0, 0, 0)); kw.setdefault("background_normal", "")
        kw.setdefault("background_active", ""); kw.setdefault("cursor_color", C_TEAL)
        kw.setdefault("multiline", True); kw.setdefault("write_tab", False)
        kw.setdefault("font_size", sp(13)); kw.setdefault("padding", [dp(12), dp(10)])
        kw.setdefault("size_hint_y", None); kw.setdefault("height", dp(120))
        
        # ---> CHANGED THIS LINE TO False <---
        kw.setdefault("input_type", "text"); kw.setdefault("keyboard_suggestions", False) 
        
        super().__init__(**kw)
        self.foreground_color = (1, 1, 1, 1); self.hint_text_color = (0.6, 0.6, 0.6, 1)
        self._bg_group = InstructionGroup()
        self._bg_group.add(Color(*C_TEAL))
        self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self._bg_group.add(self._border)
        self._bg_group.add(Color(*C_CARD2))
        self._bg = RoundedRectangle(pos=(self.x + dp(1), self.y + dp(1)), size=(self.width - dp(2), self.height - dp(2)), radius=[dp(7)])
        self._bg_group.add(self._bg); self._bg_group.add(Color(1, 1, 1, 1))
        self.canvas.before.insert(0, self._bg_group)
        def _upd(*_):
            self._border.pos, self._border.size = self.pos, self.size
            self._bg.pos, self._bg.size = (self.x + dp(1), self.y + dp(1)), (self.width - dp(2), self.height - dp(2))
        self.bind(pos=_upd, size=_upd)


class SHVButton(Button):
    def __init__(self, primary=True, danger=False, **kw):
        kw.setdefault("font_size", sp(14)); kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(48)); kw.setdefault("background_color", (0, 0, 0, 0))
        kw.setdefault("color", C_TEXT); kw.setdefault("bold", True)
        super().__init__(**kw)
        col = C_ROSE if danger else (C_TEAL if primary else C_CARD2)
        with self.canvas.before:
            Color(*col)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        def _upd(*_): self._rect.pos, self._rect.size = self.pos, self.size
        self.bind(pos=_upd, size=_upd)
    def on_press(self): self._rect.radius = [dp(6)]
    def on_release(self): self._rect.radius = [dp(10)]

class SHVCard(BoxLayout):
    def __init__(self, radius=dp(12), color=None, **kw):
        kw.setdefault("orientation", "vertical"); kw.setdefault("padding", dp(14)); kw.setdefault("spacing", dp(8))
        super().__init__(**kw)
        with self.canvas.before:
            Color(*(color or C_CARD))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        def _upd(*_): self._rect.pos, self._rect.size = self.pos, self.size
        self.bind(pos=_upd, size=_upd)

class StatusBar(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=0, padding=[dp(12), 0], spacing=dp(8), opacity=0, **kw)
        self._lbl = SHVLabel(text="", font_size=sp(12), color=C_TEXT, halign="center")
        self.add_widget(self._lbl)
        make_bg(self, C_ROSE, radius=dp(8))
    def show(self, msg, success=False, duration=3):
        col = C_TEAL_DARK if success else C_ROSE
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*col)
            rr = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        def _upd(*_): rr.pos, rr.size = self.pos, self.size
        self.bind(pos=_upd, size=_upd)
        self._lbl.text, self.height, self.opacity = msg, dp(40), 1
        Clock.schedule_once(lambda _: self.hide(), duration)
    def hide(self): self.height, self.opacity = 0, 0

class ExitOverlay(FloatLayout):
    def __init__(self, on_confirm, on_cancel, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(0, 0, 0, 0.75)
            self._scrim = Rectangle(pos=self.pos, size=self.size)
        def _upd(*_): self._scrim.pos, self._scrim.size = self.pos, self.size
        self.bind(pos=_upd, size=_upd)
        box = BoxLayout(orientation="vertical", size_hint=(0.78, None), height=dp(180), pos_hint={"center_x": 0.5, "center_y": 0.5}, padding=dp(24), spacing=dp(16))
        make_bg(box, C_CARD, radius=dp(16))
        box.add_widget(Label(text="Exit SHV Hub?", font_size=sp(17), bold=True, color=C_TEXT, size_hint_y=None, height=dp(28)))
        box.add_widget(Label(text="Are you sure you want to exit?", font_size=sp(13), color=C_TEXT_SEC, size_hint_y=None, height=dp(20)))
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))
        btn_cancel = SHVButton(text="Cancel", primary=False, height=dp(44))
        btn_exit = SHVButton(text="Exit", danger=True, height=dp(44))
        btn_cancel.bind(on_release=lambda _: on_cancel())
        btn_exit.bind(on_release=lambda _: on_confirm())
        btn_row.add_widget(btn_cancel); btn_row.add_widget(btn_exit)
        box.add_widget(btn_row)
        self.add_widget(box)

def section_label(text): return SHVLabel(text=text, font_size=sp(11), bold=True, color=C_TEAL, size_hint_y=None, height=dp(22))
def field_label(text): return SHVLabel(text=text, font_size=sp(11), color=C_TEXT_SEC, size_hint_y=None, height=dp(18))

def paste_row(label_text, text_input_widget):
    """Return a row with a field label + paste button, followed by the input widget.
    Usage: layout.add_widget(paste_row("Label", self.f_field)); layout.add_widget(self.f_field)
    Actually returns a BoxLayout header row only — add the input separately."""
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(22), spacing=dp(6))
    lbl = SHVLabel(text=label_text, font_size=sp(11), color=C_TEXT_SEC, size_hint_y=None, height=dp(18))
    row.add_widget(lbl)
    row.add_widget(Widget())  # spacer
    paste_btn = Button(
        text="📋", font_size=sp(13), font_name=FONT_PATH,
        background_color=(0, 0, 0, 0), color=C_TEAL,
        size_hint=(None, None), width=dp(28), height=dp(22)
    )
    def _do_paste(_, ti=text_input_widget):
        try:
            from kivy.core.clipboard import Clipboard
            txt = Clipboard.paste()
            if txt:
                ti.text = txt
        except Exception:
            pass
    paste_btn.bind(on_release=_do_paste)
    row.add_widget(paste_btn)
    return row
def spacer(h=8): return Widget(size_hint_y=None, height=dp(h))


# ─────────────────────────────────────────────
#  ADMIN APP COMPONENTS
# ─────────────────────────────────────────────
class AdminNavBar(BoxLayout):
    TABS = [("DB", "📊"), ("Apps", "📦"), ("News", "📰"), ("Updates", "🔔"), ("Contact", "📞"), ("Exit", "🚪")]
    def __init__(self, screen_manager, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(58), **kw)
        self.sm, self._btns = screen_manager, {}
        make_bg(self, C_NAV)
        for name, icon in self.TABS:
            btn = self._make_tab(name, icon)
            self._btns[name] = btn; self.add_widget(btn)
        with self.canvas.before:
            Color(*C_DIVIDER)
            self._line = Rectangle(pos=(self.x, self.top - dp(1)), size=(self.width, dp(1)))
        def _upd(*_): self._line.pos, self._line.size = (self.x, self.top - dp(1)), (self.width, dp(1))
        self.bind(pos=_upd, size=_upd)

    def _make_tab(self, name, icon):
        btn = BoxLayout(orientation="vertical", spacing=dp(2), padding=[0, dp(6)])
        btn.bind(on_touch_down=lambda w, t: self._pressed(name) if w.collide_point(*t.pos) else None)
        btn._icon = Label(text=icon, font_size=sp(18), size_hint_y=None, height=dp(22), color=C_TEXT_SEC, font_name=FONT_PATH)
        btn._lbl = Label(text=name.upper(), font_size=sp(14), size_hint_y=None, height=dp(18), color=C_TEXT_SEC)
        btn.add_widget(btn._icon); btn.add_widget(btn._lbl)
        return btn

    def _pressed(self, name):
        if name == "Exit":
            App.get_running_app().show_exit_confirm()
            return
        mapping = {"DB": "admin_dashboard", "Apps": "admin_apps", "News": "admin_news", "Updates": "admin_updates", "Contact": "admin_contact"}
        if name in mapping:
            self.sm.current = mapping[name]
            self.set_active(name)

    def set_active(self, name):
        for tab_name, btn in self._btns.items():
            if tab_name == "Exit":
                btn._icon.color, btn._lbl.color = C_ROSE, C_ROSE
                continue
            col = C_TEAL if tab_name == name else C_TEXT_SEC
            btn._icon.color, btn._lbl.color = col, col

class AdminScreenWithNav(Screen):
    nav_tab = StringProperty("DB")
    def build_body(self): return Widget()
    def on_pre_enter(self):
        if not self.children:
            root = BoxLayout(orientation="vertical")
            make_bg(root, C_BG)
            root.add_widget(self.build_body())
            self._nav_bar = AdminNavBar(screen_manager=self.manager)
            root.add_widget(self._nav_bar)
            self.add_widget(root)
    def on_enter(self):
        if hasattr(self, "_nav_bar"): self._nav_bar.set_active(self.nav_tab)

class AdminLoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.store = JsonStore(os.path.join(APP_DIR, "admin_auth.json"))
        self._build()

    def _build(self):
        root = FloatLayout()
        make_bg(root, C_BG)
        scroll = ScrollView(size_hint=(1, 1))
        layout = BoxLayout(orientation="vertical", padding=[dp(32), dp(70), dp(32), dp(32)], spacing=dp(16), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        brand = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(100), spacing=dp(4))
        brand.add_widget(Label(text="SHV", font_size=sp(48), bold=True, color=C_TEAL, size_hint_y=None, height=dp(60)))
        brand.add_widget(Label(text="ADMIN PANEL", font_size=sp(12), color=C_TEXT_SEC, size_hint_y=None, height=dp(20)))
        layout.add_widget(brand); layout.add_widget(spacer(20))

        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        layout.add_widget(Label(text="Admin Sign In", font_size=sp(22), bold=True, color=C_TEXT, size_hint_y=None, height=dp(36), halign="left", text_size=(Window.width - dp(64), None)))

        saved_email, saved_pass, is_rem = "", "", False
        if self.store.exists("creds"):
            c = self.store.get("creds")
            saved_email, saved_pass, is_rem = c.get("email", ""), c.get("password", ""), True

        layout.add_widget(field_label("Email"))
        self.email_ti = SHVTextInput(hint_text="admin@shvertex.com", input_type="mail", text=saved_email)
        layout.add_widget(self.email_ti)

        layout.add_widget(field_label("Password"))
        self.pass_ti = SHVTextInput(hint_text="••••••••", password=True, text=saved_pass)
        layout.add_widget(self.pass_ti)

        rem_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(12))
        rem_row.add_widget(SHVLabel(text="Remember Me", size_hint_y=None, height=dp(40), color=C_TEXT_SEC))
        self.sw_remember = Switch(active=is_rem, size_hint_x=None, width=dp(70))
        rem_row.add_widget(self.sw_remember)
        layout.add_widget(rem_row)

        layout.add_widget(spacer(8))
        btn = SHVButton(text="Sign In", primary=True)
        btn.bind(on_release=self._do_login)
        layout.add_widget(btn)
        
        back_btn = SHVButton(text="Back to Hub", primary=False)
        back_btn.bind(on_release=lambda _: setattr(self.manager, "current", "hub"))
        layout.add_widget(back_btn)

        layout.add_widget(spacer(20))
        layout.add_widget(Label(text=f"SH Vertex Technologies  •  Admin v{APP_VERSION}", font_size=sp(10), color=C_TEXT_HINT, size_hint_y=None, height=dp(20)))

        scroll.add_widget(layout); root.add_widget(scroll); self.add_widget(root)

    def _do_login(self, *_):
        email, password = self.email_ti.text.strip(), self.pass_ti.text.strip()
        if not email or not password:
            self.status.show("Please fill in all fields"); return
        self.status.show("Signing in...", success=True, duration=30)
        def _thread():
            resp, status = supabase.sign_in(email, password)
            if status != 200:
                Clock.schedule_once(lambda _: self.status.show(resp.get("error_description") or resp.get("msg") or "Login failed"))
                return
            admin = supabase.is_admin()
            def _main(*_):
                if admin:
                    if self.sw_remember.active: self.store.put("creds", email=email, password=password)
                    elif self.store.exists("creds"): self.store.delete("creds")
                    self.manager.current = "admin_dashboard"
                else:
                    supabase.sign_out()
                    self.status.show("Access denied — not an admin account")
            Clock.schedule_once(_main)
        threading.Thread(target=_thread, daemon=True).start()




class AppRowCard(SHVCard):
    def __init__(self, item, on_edit, on_delete, on_toggle, **kw):
        super().__init__(color=C_CARD, size_hint_y=None, orientation="vertical", **kw)
        top = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
        top.add_widget(SHVLabel(text=item.get("name", ""), font_size=sp(14), bold=True, size_hint_y=None, height=dp(24)))
        top.add_widget(Label(text="Live" if item.get("is_published") else "Draft", font_size=sp(10), bold=True, color=(C_TEAL if item.get("is_published") else C_SLATE), size_hint_x=None, width=dp(40)))
        self.add_widget(top)
        sub_row = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(12))
        sub_row.add_widget(SHVLabel(text=f"v{item.get('version','?')}", font_size=sp(11), color=C_TEXT_SEC, size_hint_y=None, height=dp(18)))
        sub_row.add_widget(SHVLabel(text=item.get("category",""), font_size=sp(11), color=C_TEXT_SEC, size_hint_y=None, height=dp(18)))
        sub_row.add_widget(SHVLabel(text=f"↓ {item.get('download_count', 0)}", font_size=sp(11), color=C_TEAL, size_hint_y=None, height=dp(18)))
        self.add_widget(sub_row)
        actions = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        btn_t = SHVButton(text="Unpublish" if item.get("is_published") else "Publish", primary=True, height=dp(34))
        btn_e = SHVButton(text="Edit", primary=False, height=dp(34))
        btn_d = SHVButton(text="Delete", danger=True, height=dp(34))
        btn_t.bind(on_release=lambda _: on_toggle(item)); btn_e.bind(on_release=lambda _: on_edit(item)); btn_d.bind(on_release=lambda _: on_delete(item))
        actions.add_widget(btn_t); actions.add_widget(btn_e); actions.add_widget(btn_d)
        self.add_widget(actions)
        self.bind(minimum_height=self.setter("height"))

class AppsScreen(AdminScreenWithNav):
    nav_tab = "Apps"
    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(12), 0], spacing=dp(8))
        make_bg(header, C_SURFACE)
        header.add_widget(Label(text="Apps", font_size=sp(18), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(100), None)))
        add_btn = SHVButton(text="+ Add", primary=True, height=dp(36), size_hint_x=None, width=dp(70))
        add_btn.bind(on_release=lambda _: (setattr(App.get_running_app(), "edit_item", None), setattr(self.manager, "current", "admin_app_form")))
        header.add_widget(add_btn); layout.add_widget(header)
        self.status = StatusBar(size_hint_x=1)
        scroll = ScrollView()
        self.feed = BoxLayout(orientation="vertical", padding=[dp(10), dp(10)], spacing=dp(10), size_hint_y=None)
        self.feed.bind(minimum_height=self.feed.setter("height"))
        self.feed.add_widget(SHVLabel(text="Loading...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.feed)
        layout.add_widget(self.status); layout.add_widget(scroll)
        return layout
    def on_enter(self): super().on_enter(); threading.Thread(target=self._load, daemon=True).start()
    def _load(self):
        resp, status = supabase.select_all("apps", order="created_at.desc")
        def _main(*_):
            self.feed.clear_widgets()
            if status == 200 and isinstance(resp, list) and resp:
                for item in resp: self.feed.add_widget(AppRowCard(item, on_edit=self._edit, on_delete=self._delete, on_toggle=self._toggle_publish))
            else:
                err = "No apps yet." if status == 200 else f"Error {status}"
                self.status.show(err, success=(status==200), duration=5)
                self.feed.add_widget(SHVLabel(text=err, color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        Clock.schedule_once(_main)
    def _edit(self, item): App.get_running_app().edit_item = item; self.manager.current = "admin_app_form"
    def _toggle_publish(self, item):
        threading.Thread(target=lambda: (supabase.update("apps", item["id"], {"is_published": not item.get("is_published", False)}), Clock.schedule_once(lambda _: threading.Thread(target=self._load, daemon=True).start())), daemon=True).start()
    def _delete(self, item):
        self.status.show(f"Deleting...", success=False, duration=10)
        threading.Thread(target=lambda: (supabase.delete("apps", item["id"]), Clock.schedule_once(lambda _: threading.Thread(target=self._load, daemon=True).start())), daemon=True).start()

class AppFormScreen(Screen):
    def on_enter(self):
        self.clear_widgets()
        self._item = getattr(App.get_running_app(), "edit_item", None)
        self._build()
        
    def _build(self):
        item = self._item or {}
        root = BoxLayout(orientation="vertical")
        make_bg(root, C_BG)
        
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8))
        make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "admin_apps"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text=("Edit App" if item else "New App"), font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        root.add_widget(topbar)
        
        scroll = ScrollView()
        layout = BoxLayout(orientation="vertical", padding=[dp(16), dp(12)], spacing=dp(8), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        
        # Section: Basic Info
        layout.add_widget(section_label("Basic Info"))
        self.f_name = SHVTextInput(text=item.get("name",""))
        layout.add_widget(paste_row("App Name *", self.f_name))
        layout.add_widget(self.f_name)
        
        self.f_tagline = SHVTextInput(text=item.get("tagline",""))
        layout.add_widget(paste_row("Tagline", self.f_tagline))
        layout.add_widget(self.f_tagline)
        
        self.f_version = SHVTextInput(text=item.get("version",""))
        layout.add_widget(paste_row("Version *", self.f_version))
        layout.add_widget(self.f_version)
        
        self.f_category = SHVTextInput(text=item.get("category","Utility"))
        layout.add_widget(paste_row("Category", self.f_category))
        layout.add_widget(self.f_category)
        
        # Section: Description
        layout.add_widget(spacer(4))
        layout.add_widget(section_label("Description"))
        self.f_desc = SHVMultiInput(text=item.get("description",""), height=dp(140), keyboard_suggestions=False)
        layout.add_widget(paste_row("Description", self.f_desc))
        layout.add_widget(self.f_desc)
        
        # Section: URLs & Media
        layout.add_widget(spacer(4))
        layout.add_widget(section_label("URLs & Media"))
        self.f_apk = SHVTextInput(text=item.get("apk_url",""))
        layout.add_widget(paste_row("APK Download URL", self.f_apk))
        layout.add_widget(self.f_apk)
        
        self.f_icon = SHVTextInput(text=item.get("icon_url",""))
        layout.add_widget(paste_row("Icon URL", self.f_icon))
        layout.add_widget(self.f_icon)
        
        # Process screenshots as string safely
        raw_shots = item.get("screenshots", "")
        if isinstance(raw_shots, list): raw_shots = ", ".join(str(x) for x in raw_shots)
        elif raw_shots is None: raw_shots = ""
        
        self.f_screenshots = SHVMultiInput(text=str(raw_shots), height=dp(100), keyboard_suggestions=False)
        layout.add_widget(paste_row("Screenshots (Comma URLs)", self.f_screenshots))
        layout.add_widget(self.f_screenshots)
        
        # Section: Settings
        layout.add_widget(spacer(4))
        layout.add_widget(section_label("Settings"))
        pub_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(12))
        pub_row.add_widget(SHVLabel(text="Published", size_hint_y=None, height=dp(44)))
        self.sw_published = Switch(active=item.get("is_published", False), size_hint_x=None, width=dp(70))
        pub_row.add_widget(self.sw_published)
        layout.add_widget(pub_row)
        
        lic_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(12))
        lic_row.add_widget(SHVLabel(text="Requires License", size_hint_y=None, height=dp(44)))
        self.sw_license = Switch(active=item.get("requires_license", False), size_hint_x=None, width=dp(70))
        lic_row.add_widget(self.sw_license)
        layout.add_widget(lic_row)
        
        layout.add_widget(spacer(12))
        save_btn = SHVButton(text="Save App", primary=True, height=dp(52))
        save_btn.bind(on_release=self._save)
        layout.add_widget(save_btn)
        
        if item:
            layout.add_widget(spacer(4))
            del_btn = SHVButton(text="Delete App", danger=True, height=dp(44))
            del_btn.bind(on_release=self._delete)
            layout.add_widget(del_btn)
            
        layout.add_widget(spacer(24))
        scroll.add_widget(layout)
        root.add_widget(scroll)
        self.add_widget(root)

    def _save(self, *_):
        name, version = self.f_name.text.strip(), self.f_version.text.strip()
        if not name or not version: return # Basic validation
        
        data = {
            "name": name, "tagline": self.f_tagline.text.strip(), "version": version, 
            "category": self.f_category.text.strip() or "Utility", 
            "description": self.f_desc.text.strip(), "apk_url": self.f_apk.text.strip(), 
            "icon_url": self.f_icon.text.strip(), "screenshots": self.f_screenshots.text.strip(), 
            "is_published": self.sw_published.active, "requires_license": self.sw_license.active
        }
        
        ProgressModal.show("Saving App Data...")
        def _thread():
            # Support 200 (Update), 201 (Insert), 204 (No Content)
            resp, status = supabase.update("apps", self._item["id"], data) if self._item else supabase.insert("apps", data)
            def _main(*_):
                if status in (200, 201, 204):
                    ProgressModal.success("App Successfully Saved!", lambda: setattr(self.manager, "current", "admin_apps"))
                else:
                    ProgressModal.error(f"Save Failed (Code: {status})")
            Clock.schedule_once(_main)
        threading.Thread(target=_thread, daemon=True).start()

    def _delete(self, *_):
        ProgressModal.show("Deleting App...")
        def _thread():
            resp, status = supabase.delete("apps", self._item["id"])
            Clock.schedule_once(lambda _: ProgressModal.success("App Deleted!", lambda: setattr(self.manager, "current", "admin_apps")))
        threading.Thread(target=_thread, daemon=True).start()


class AppDetailScreen(Screen):
    def on_enter(self):
        self.clear_widgets()
        self._build(getattr(App.get_running_app(), "current_app_detail", {}))

    def _build(self, item):
        root = BoxLayout(orientation="vertical")
        make_bg(root, C_BG)
        
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8))
        make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "store_catalog"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text=item.get("name", "App Detail"), font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        root.add_widget(topbar)
        
        scroll = ScrollView()
        layout = BoxLayout(orientation="vertical", padding=[dp(16), dp(16)], spacing=dp(14), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        
        # 1. Header
        icon_row = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(16))
        icon_row.add_widget(load_remote_image(item.get("icon_url") or "", fallback_text="📦", size_hint_x=None, width=dp(56), height=dp(56)))
        
        info_col = BoxLayout(orientation="vertical", spacing=dp(4))
        info_col.add_widget(SHVLabel(text=item.get("name",""), font_size=sp(18), bold=True, size_hint_y=None, height=dp(28)))
        info_col.add_widget(SHVLabel(text=item.get("tagline",""), font_size=sp(12), color=C_TEXT_SEC, size_hint_y=None, height=dp(20)))
        info_col.add_widget(SHVLabel(text=f"Version {item.get('version','')}", font_size=sp(11), color=C_TEAL, size_hint_y=None, height=dp(18)))
        icon_row.add_widget(info_col)
        layout.add_widget(icon_row)
        
        # 2. Stats
        stats = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        for label, val in [("Category", item.get("category","—")), ("Downloads", str(item.get("download_count", 0))), ("License", "Required" if item.get("requires_license") else "Free")]:
            card = SHVCard(color=C_CARD2, size_hint_x=1)
            card.add_widget(SHVLabel(text=val, font_size=sp(13), bold=True, halign="center", size_hint_y=None, height=dp(20)))
            card.add_widget(SHVLabel(text=label, font_size=sp(10), color=C_TEXT_SEC, halign="center", size_hint_y=None, height=dp(16)))
            stats.add_widget(card)
        layout.add_widget(stats)
        
        # 3. Media Carousel (FIXED LAG & IMAGES)
        raw_shots = item.get("screenshots", [])
        if isinstance(raw_shots, list):
            img_urls = [str(u).strip() for u in raw_shots if str(u).strip()]
        else:
            raw_str = str(raw_shots or "")
            img_urls = [u.strip() for u in raw_str.split(",") if u.strip()]
        
        if img_urls:
            layout.add_widget(SHVLabel(text="Preview", font_size=sp(14), bold=True, color=C_TEAL, size_hint_y=None, height=dp(24)))
            sc_scroll = ScrollView(size_hint_y=None, height=dp(220), do_scroll_x=True, do_scroll_y=False)
            sc_box = BoxLayout(orientation="horizontal", size_hint_x=None, spacing=dp(12))
            sc_box.bind(minimum_width=sc_box.setter('width'))
            
            from kivy.uix.image import AsyncImage
            for u in img_urls:
                # Native AsyncImage completely ignores bad characters and loads lag-free!
                img = AsyncImage(source=u, size_hint_x=None, width=dp(115), height=dp(220), allow_stretch=True, keep_ratio=True)
                sc_box.add_widget(img)
                
            sc_scroll.add_widget(sc_box)
            layout.add_widget(sc_scroll)
            layout.add_widget(Widget(size_hint_y=None, height=dp(4)))
        
        # 4. About
        layout.add_widget(SHVLabel(text="About", font_size=sp(14), bold=True, color=C_TEAL, size_hint_y=None, height=dp(24)))
        desc_lbl = Label(text=item.get("description", "No description."), font_size=sp(13), color=C_TEXT_SEC, size_hint_y=None, halign="left", valign="top", text_size=(Window.width - dp(32), None))
        desc_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        layout.add_widget(desc_lbl)
        
        layout.add_widget(Widget(size_hint_y=None, height=dp(8)))
        
        self.status = StatusBar(size_hint_x=1)
        layout.add_widget(self.status)
        
        # 5. Install Button
        if item.get("apk_url", ""):
            install_btn = SHVButton(text="⬇  Download & Install", primary=True, height=dp(52))
            install_btn.bind(on_release=lambda _, u=item.get("apk_url",""), i=item.get("id",""): self._open_install(u, i))
            layout.add_widget(install_btn)
            
        scroll.add_widget(layout)
        root.add_widget(scroll)
        self.add_widget(root)

    def _open_install(self, apk_url, app_id):
        try:
            if app_id: supabase.increment_download(app_id)
        except Exception: pass
        _open_url_in_browser(apk_url)
        self.status.show("Opening browser to download...", success=True, duration=4)



class NewsRowCard(SHVCard):
    def __init__(self, item, on_edit, on_delete, on_toggle, **kw):
        super().__init__(color=C_CARD, size_hint_y=None, orientation="vertical", **kw)
        top = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
        top.add_widget(SHVLabel(text=item.get("title",""), font_size=sp(13), bold=True, size_hint_y=None, height=dp(24)))
        top.add_widget(Label(text="Live" if item.get("is_published") else "Draft", font_size=sp(10), bold=True, color=(C_TEAL if item.get("is_published") else C_SLATE), size_hint_x=None, width=dp(40)))
        self.add_widget(top); self.add_widget(SHVLabel(text=item.get("created_at","")[:10], font_size=sp(10), color=C_TEXT_SEC, size_hint_y=None, height=dp(16)))
        actions = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        bt = SHVButton(text="Unpublish" if item.get("is_published") else "Publish", primary=True, height=dp(34))
        be = SHVButton(text="Edit", primary=False, height=dp(34))
        bd = SHVButton(text="Delete", danger=True, height=dp(34))
        bt.bind(on_release=lambda _: on_toggle(item)); be.bind(on_release=lambda _: on_edit(item)); bd.bind(on_release=lambda _: on_delete(item))
        actions.add_widget(bt); actions.add_widget(be); actions.add_widget(bd)
        self.add_widget(actions); self.bind(minimum_height=self.setter("height"))

class NewsScreen(AdminScreenWithNav):
    nav_tab = "News"
    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(12), 0], spacing=dp(8))
        make_bg(header, C_SURFACE)
        header.add_widget(Label(text="News", font_size=sp(18), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(100), None)))
        add_btn = SHVButton(text="+ Add", primary=True, height=dp(36), size_hint_x=None, width=dp(70))
        add_btn.bind(on_release=lambda _: (setattr(App.get_running_app(), "edit_item", None), setattr(self.manager, "current", "admin_news_form")))
        header.add_widget(add_btn); layout.add_widget(header)
        self.status = StatusBar(size_hint_x=1); scroll = ScrollView()
        self.feed = BoxLayout(orientation="vertical", padding=[dp(10), dp(10)], spacing=dp(10), size_hint_y=None)
        self.feed.bind(minimum_height=self.feed.setter("height"))
        self.feed.add_widget(SHVLabel(text="Loading...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.feed); layout.add_widget(self.status); layout.add_widget(scroll)
        return layout
    def on_enter(self): super().on_enter(); threading.Thread(target=self._load, daemon=True).start()
    def _load(self):
        resp, status = supabase.select_all("news", order="created_at.desc")
        def _main(*_):
            self.feed.clear_widgets()
            if status == 200 and isinstance(resp, list) and resp:
                for item in resp: self.feed.add_widget(NewsRowCard(item, on_edit=self._edit, on_delete=self._delete, on_toggle=self._toggle))
            else:
                self.status.show("No news yet.", success=True, duration=5)
        Clock.schedule_once(_main)
    def _edit(self, item): App.get_running_app().edit_item = item; self.manager.current = "admin_news_form"
    def _toggle(self, item): threading.Thread(target=lambda: (supabase.update("news", item["id"], {"is_published": not item.get("is_published", False)}), Clock.schedule_once(lambda _: threading.Thread(target=self._load, daemon=True).start())), daemon=True).start()
    def _delete(self, item): threading.Thread(target=lambda: (supabase.delete("news", item["id"]), Clock.schedule_once(lambda _: threading.Thread(target=self._load, daemon=True).start())), daemon=True).start()

class NewsFormScreen(Screen):
    def on_enter(self): self.clear_widgets(); self._item = getattr(App.get_running_app(), "edit_item", None); self._build()
    def _build(self):
        item = self._item or {}
        root = BoxLayout(orientation="vertical"); make_bg(root, C_BG)
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8)); make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "admin_news"))
        topbar.add_widget(back); topbar.add_widget(Label(text=("Edit News" if item else "New News"), font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        root.add_widget(topbar)
        scroll = ScrollView()
        layout = BoxLayout(orientation="vertical", padding=[dp(16), dp(12)], spacing=dp(8), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        self.f_title = SHVTextInput(text=item.get("title","")); layout.add_widget(paste_row("Title *", self.f_title)); layout.add_widget(self.f_title)
        self.f_body = SHVMultiInput(text=item.get("body",""), height=dp(200)); layout.add_widget(paste_row("Body *", self.f_body)); layout.add_widget(self.f_body)
        self.f_cover = SHVTextInput(text=item.get("cover_image_url","")); layout.add_widget(paste_row("Cover Image URL", self.f_cover)); layout.add_widget(self.f_cover)
        pub_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(12))
        pub_row.add_widget(SHVLabel(text="Published", size_hint_y=None, height=dp(44)))
        self.sw_pub = Switch(active=item.get("is_published", False), size_hint_x=None, width=dp(70))
        pub_row.add_widget(self.sw_pub); layout.add_widget(pub_row); layout.add_widget(spacer(8))
        save_btn = SHVButton(text="Save Post", primary=True, height=dp(52)); save_btn.bind(on_release=self._save); layout.add_widget(save_btn)
        if item: del_btn = SHVButton(text="Delete Post", danger=True, height=dp(44)); del_btn.bind(on_release=self._delete); layout.add_widget(del_btn)
        layout.add_widget(spacer(24)); scroll.add_widget(layout); root.add_widget(scroll); self.add_widget(root)
    def _save(self, *_):
        title, body = self.f_title.text.strip(), self.f_body.text.strip()
        if not title or not body: return self.status.show("Title and body required")
        data = {"title": title, "body": body, "cover_image_url": self.f_cover.text.strip(), "is_published": self.sw_pub.active}
        self.status.show("Saving...", success=True, duration=30)
        def _thread():
            resp, status = supabase.update("news", self._item["id"], data) if self._item else supabase.insert("news", data)
            Clock.schedule_once(lambda _: (self.status.show("Saved!", success=True), Clock.schedule_once(lambda _: setattr(self.manager, "current", "admin_news"), 1)) if status in (200, 201) else self.status.show("Save failed"))
        threading.Thread(target=_thread, daemon=True).start()
    def _delete(self, *_): threading.Thread(target=lambda: (supabase.delete("news", self._item["id"]), Clock.schedule_once(lambda _: setattr(self.manager, "current", "admin_news"))), daemon=True).start()

class UpdateRowCard(SHVCard):
    def __init__(self, item, on_edit, on_delete, **kw):
        super().__init__(color=C_CARD, size_hint_y=None, orientation="vertical", **kw)
        status = item.get("status","planned"); scol = {"planned": C_SLATE, "in_progress": C_AMBER, "released": C_TEAL}.get(status, C_SLATE)
        top = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
        top.add_widget(SHVLabel(text=f"[{item.get('app_name','')}] {item.get('title','')}", font_size=sp(13), bold=True, size_hint_y=None, height=dp(24)))
        top.add_widget(Label(text=status.replace("_"," ").title(), font_size=sp(10), bold=True, color=scol, size_hint_x=None, width=dp(80)))
        self.add_widget(top)
        if item.get("description"): self.add_widget(SHVLabel(text=item["description"], font_size=sp(11), color=C_TEXT_SEC, size_hint_y=None, height=dp(18)))
        meta = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(16))
        if item.get("target_version"): meta.add_widget(SHVLabel(text=f"v{item['target_version']}", font_size=sp(10), color=C_TEAL, size_hint_y=None, height=dp(18)))
        if item.get("expected_date"): meta.add_widget(SHVLabel(text=f"ETA: {item['expected_date']}", font_size=sp(10), color=C_TEXT_SEC, size_hint_y=None, height=dp(18)))
        self.add_widget(meta)
        actions = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        be = SHVButton(text="Edit", primary=False, height=dp(34)); bd = SHVButton(text="Delete", danger=True, height=dp(34))
        be.bind(on_release=lambda _: on_edit(item)); bd.bind(on_release=lambda _: on_delete(item))
        actions.add_widget(be); actions.add_widget(bd); self.add_widget(actions); self.bind(minimum_height=self.setter("height"))

class AdminUpdatesScreen(AdminScreenWithNav):
    nav_tab = "Updates"
    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(12), 0], spacing=dp(8)); make_bg(header, C_SURFACE)
        header.add_widget(Label(text="Roadmap", font_size=sp(18), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(100), None)))
        add_btn = SHVButton(text="+ Add", primary=True, height=dp(36), size_hint_x=None, width=dp(70))
        add_btn.bind(on_release=lambda _: (setattr(App.get_running_app(), "edit_item", None), setattr(self.manager, "current", "admin_update_form")))
        header.add_widget(add_btn); layout.add_widget(header)
        self.status = StatusBar(size_hint_x=1); scroll = ScrollView()
        self.feed = BoxLayout(orientation="vertical", padding=[dp(10), dp(10)], spacing=dp(10), size_hint_y=None)
        self.feed.bind(minimum_height=self.feed.setter("height"))
        self.feed.add_widget(SHVLabel(text="Loading...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.feed); layout.add_widget(self.status); layout.add_widget(scroll)
        return layout
    def on_enter(self): super().on_enter(); threading.Thread(target=self._load, daemon=True).start()
    def _load(self):
        resp, status = supabase.select_all("upcoming_updates", order="created_at.desc")
        def _main(*_):
            self.feed.clear_widgets()
            if status == 200 and isinstance(resp, list) and resp:
                for item in resp: self.feed.add_widget(UpdateRowCard(item, on_edit=self._edit, on_delete=self._delete))
        Clock.schedule_once(_main)
    def _edit(self, item): App.get_running_app().edit_item = item; self.manager.current = "admin_update_form"
    def _delete(self, item): threading.Thread(target=lambda: (supabase.delete("upcoming_updates", item["id"]), Clock.schedule_once(lambda _: threading.Thread(target=self._load, daemon=True).start())), daemon=True).start()

class UpdateFormScreen(Screen):
    def on_enter(self): self.clear_widgets(); self._item = getattr(App.get_running_app(), "edit_item", None); self._build()
    def _build(self):
        item = self._item or {}; root = BoxLayout(orientation="vertical"); make_bg(root, C_BG)
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8)); make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "admin_updates"))
        topbar.add_widget(back); topbar.add_widget(Label(text=("Edit Roadmap Item" if item else "New Roadmap Item"), font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        root.add_widget(topbar)
        scroll = ScrollView()
        layout = BoxLayout(orientation="vertical", padding=[dp(16), dp(12)], spacing=dp(8), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        self.f_appname = SHVTextInput(text=item.get("app_name","")); layout.add_widget(paste_row("App Name *", self.f_appname)); layout.add_widget(self.f_appname)
        self.f_title = SHVTextInput(text=item.get("title","")); layout.add_widget(paste_row("Feature Title *", self.f_title)); layout.add_widget(self.f_title)
        self.f_desc = SHVMultiInput(text=item.get("description",""), height=dp(120)); layout.add_widget(paste_row("Description", self.f_desc)); layout.add_widget(self.f_desc)
        self.f_version = SHVTextInput(text=item.get("target_version","")); layout.add_widget(paste_row("Target Version", self.f_version)); layout.add_widget(self.f_version)
        self.f_eta = SHVTextInput(text=item.get("expected_date","")); layout.add_widget(paste_row("Expected Date", self.f_eta)); layout.add_widget(self.f_eta)
        layout.add_widget(field_label("Status"))
        status_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self._status_val = item.get("status", "planned"); self._status_btns = {}
        for s in ["planned", "in_progress", "released"]:
            is_active = (s == self._status_val); col = {"planned": C_SLATE, "in_progress": C_AMBER, "released": C_TEAL}.get(s, C_SLATE)
            btn = Button(text=s.replace("_"," ").title(), font_size=sp(11), background_color=(0,0,0,0), color=(C_TEXT if is_active else C_TEXT_SEC), bold=is_active)
            with btn.canvas.before:
                Color(*(col if is_active else C_CARD2))
                btn._bg_instr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(8)])
            def _upd(w, *_): w._bg_instr.pos, w._bg_instr.size = w.pos, w.size
            btn.bind(pos=_upd, size=_upd); btn.bind(on_release=lambda _, sv=s: self._set_status(sv))
            self._status_btns[s] = btn; status_row.add_widget(btn)
        layout.add_widget(status_row); layout.add_widget(spacer(8))
        save_btn = SHVButton(text="Save Item", primary=True, height=dp(52)); save_btn.bind(on_release=self._save); layout.add_widget(save_btn)
        if item: del_btn = SHVButton(text="Delete Item", danger=True, height=dp(44)); del_btn.bind(on_release=self._delete); layout.add_widget(del_btn)
        layout.add_widget(spacer(24)); scroll.add_widget(layout); root.add_widget(scroll); self.add_widget(root)
    def _set_status(self, val):
        self._status_val = val
        for s, btn in self._status_btns.items():
            is_active = (s == val); col = {"planned": C_SLATE, "in_progress": C_AMBER, "released": C_TEAL}.get(s, C_SLATE)
            btn.canvas.before.clear()
            with btn.canvas.before:
                Color(*(col if is_active else C_CARD2))
                btn._bg_instr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(8)])
            def _upd(w, *_): w._bg_instr.pos, w._bg_instr.size = w.pos, w.size
            btn.bind(pos=_upd, size=_upd); btn.color = C_TEXT if is_active else C_TEXT_SEC; btn.bold = is_active
    def _save(self, *_):
        app_name, title = self.f_appname.text.strip(), self.f_title.text.strip()
        if not app_name or not title: return self.status.show("App name and title required")
        data = {"app_name": app_name, "title": title, "description": self.f_desc.text.strip(), "target_version": self.f_version.text.strip(), "expected_date": self.f_eta.text.strip(), "status": self._status_val}
        self.status.show("Saving...", success=True, duration=30)
        def _thread():
            resp, status = supabase.update("upcoming_updates", self._item["id"], data) if self._item else supabase.insert("upcoming_updates", data)
            Clock.schedule_once(lambda _: (self.status.show("Saved!", success=True), Clock.schedule_once(lambda _: setattr(self.manager, "current", "admin_updates"), 1)) if status in (200, 201) else self.status.show("Save failed"))
        threading.Thread(target=_thread, daemon=True).start()
    def _delete(self, *_): threading.Thread(target=lambda: (supabase.delete("upcoming_updates", self._item["id"]), Clock.schedule_once(lambda _: setattr(self.manager, "current", "admin_updates"))), daemon=True).start()

# ─────────────────────────────────────────────
#  ADMIN CONTACT SCREEN
# ─────────────────────────────────────────────
class AdminContactScreen(AdminScreenWithNav):
    nav_tab = "Contact"

    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(12), 0], spacing=dp(8))
        make_bg(header, C_SURFACE)
        header.add_widget(Label(text="Contact Info", font_size=sp(18), bold=True, color=C_AMBER,
                                halign="left", text_size=(Window.width - dp(32), None)))
        layout.add_widget(header)
        self.status = StatusBar(size_hint_x=1)
        layout.add_widget(self.status)

        scroll = ScrollView()
        self.form = BoxLayout(orientation="vertical", padding=[dp(16), dp(12)], spacing=dp(8), size_hint_y=None)
        self.form.bind(minimum_height=self.form.setter("height"))

        self.form.add_widget(SHVLabel(
            text="Edit the contact details shown to customers on the Home screen.",
            font_size=sp(12), color=C_TEXT_SEC, size_hint_y=None, height=dp(32)
        ))
        self.form.add_widget(spacer(4))

        FIELDS = [
            ("WhatsApp Number", "whatsapp", "e.g. +94771234567"),
            ("Email Address",   "email",    "e.g. hello@shvertex.com"),
            ("Discord",         "discord",  "invite code or full link"),
            ("Telegram",        "telegram", "@handle or full link"),
            ("Instagram",       "instagram","@handle or full link"),
            ("Website",         "website",  "e.g. shvertex.work.gd"),
        ]
        self._fields = {}
        for label, key, hint in FIELDS:
            ti = SHVTextInput(hint_text=hint, text="")
            self.form.add_widget(paste_row(label, ti))
            self.form.add_widget(ti)
            self._fields[key] = ti

        self.form.add_widget(spacer(12))
        save_btn = SHVButton(text="Save Contact Info", primary=True, height=dp(52))
        save_btn.bind(on_release=self._save)
        self.form.add_widget(save_btn)
        self.form.add_widget(spacer(24))

        scroll.add_widget(self.form)
        layout.add_widget(scroll)
        return layout

    def on_enter(self):
        super().on_enter()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        info = supabase.get_contact_info()
        def _main(*_):
            for key, ti in self._fields.items():
                ti.text = info.get(key, "") if info else ""
        Clock.schedule_once(_main)

    def _save(self, *_):
        data = {key: ti.text.strip() for key, ti in self._fields.items()}
        self.status.show("Saving...", success=True, duration=30)
        def _thread():
            resp, status = supabase.upsert_contact_info(data)
            def _main(*_):
                if status in (200, 201):
                    self.status.show("Contact info saved!", success=True, duration=3)
                else:
                    self.status.show(f"Save failed ({status})", duration=4)
            Clock.schedule_once(_main)
        threading.Thread(target=_thread, daemon=True).start()

class DashboardScreen(AdminScreenWithNav):
    nav_tab = "DB"
    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        
        # Header
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(16), 0], spacing=dp(8))
        make_bg(header, C_SURFACE)
        header.add_widget(Label(text="Dashboard", font_size=sp(18), bold=True, color=C_TEAL, halign="left", text_size=(Window.width - dp(80), None)))
        sign_out_btn = Button(text="Sign Out", font_size=sp(12), color=C_ROSE, background_color=(0,0,0,0), size_hint_x=None, width=dp(70))
        sign_out_btn.bind(on_release=self._sign_out)
        header.add_widget(sign_out_btn); layout.add_widget(header)

        # Content Area - Reduced padding and spacing to eliminate scrolling
        scroll = ScrollView()
        self.content = BoxLayout(orientation="vertical", padding=[dp(12), dp(8)], spacing=dp(8), size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter("height"))
        self.content.add_widget(SHVLabel(text="Loading stats...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.content)
        
        self.dash_status = StatusBar(size_hint_x=1)
        layout.add_widget(self.dash_status)
        layout.add_widget(scroll)
        return layout

    def on_enter(self):
        super().on_enter()
        threading.Thread(target=self._load_stats, daemon=True).start()

    def _sign_out(self, *_):
        supabase.sign_out(); self.manager.current = "hub"

    def _load_stats(self):
        try: stats, load_err = supabase.get_stats(), None
        except Exception as ex: stats, load_err = {k: 0 for k in ["total_apps","published_apps","total_news","published_news","total_updates","in_progress","total_users","total_downloads"]}, str(ex)
        
        def _main(*_):
            self.content.clear_widgets()
            if load_err: self.dash_status.show(f"Stats error: {load_err}", duration=6)
            
            # Welcome Text
            self.content.add_widget(Label(text=f"Welcome, {supabase.user_email or 'Admin'}", font_size=sp(13), color=C_TEXT_SEC, size_hint_y=None, height=dp(18), halign="left", text_size=(Window.width - dp(24), None)))
            
            # --- STATS GRID (8 Boxes perfectly centered) ---
            grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            
            # Shortened labels slightly to ensure they fit cleanly
            items = [
                ("Total Apps", stats["total_apps"], C_TEAL), 
                ("Published", stats["published_apps"], C_TEAL_DARK), 
                ("News Posts", stats["total_news"], C_SLATE), 
                ("Live News", stats["published_news"], C_SLATE), 
                ("Roadmap Items", stats["total_updates"], C_AMBER), 
                ("In Progress", stats["in_progress"], C_AMBER), 
                ("Total Users", stats["total_users"], C_TEXT_SEC), 
                ("Downloads", stats["total_downloads"], C_TEAL)
            ]
            
            for label, val, col in items:
                # Custom box with zero padding forces naked Labels to sit dead center
                card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(52))
                make_bg(card, C_CARD, radius=dp(10))
                card.add_widget(Label(text=str(val), font_size=sp(20), bold=True, color=col))
                card.add_widget(Label(text=label, font_size=sp(11), color=C_TEXT_SEC))
                grid.add_widget(card)
                
            self.content.add_widget(grid)
            
            # --- 1. CONTENT MANAGEMENT ---
            self.content.add_widget(SHVLabel(text="Content & Management", font_size=sp(11), bold=True, color=C_TEAL, size_hint_y=None, height=dp(16)))
            
            grid_content = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
            grid_content.bind(minimum_height=grid_content.setter("height"))
            
            grid_items = [
                ("➕", "New App", "admin_app_form"),
                ("➕", "New News", "admin_news_form"),
                ("➕", "Roadmap", "admin_update_form"),
                ("⚙️", "Contact Info", "admin_contact")
            ]
            
            for icon, label, screen in grid_items:
                btn = SHVButton(text=f"[font={FONT_PATH}]{icon}[/font]  {label}", 
                                primary=False, markup=True, font_size=sp(14), height=dp(42))
                btn.bind(on_release=lambda _, s=screen: (setattr(App.get_running_app(), "edit_item", None), setattr(self.manager, "current", s)))
                grid_content.add_widget(btn)
                
            self.content.add_widget(grid_content)

            # --- 2. AUDIENCE ENGAGEMENT ---
            self.content.add_widget(SHVLabel(text="Audience Engagement", font_size=sp(11), bold=True, color=C_TEAL, size_hint_y=None, height=dp(16)))
            
            b1 = SHVButton(text=f"[font={FONT_PATH}]📢[/font]  New Broadcast Message", primary=True, markup=True, font_size=sp(15), height=dp(44))
            b1.bind(on_release=lambda _: (setattr(App.get_running_app(), "edit_item", None), setattr(self.manager, "current", "admin_broadcast_form")))
            self.content.add_widget(b1)
            
            b2 = SHVButton(text=f"[font={FONT_PATH}]📜[/font]  Manage Sent Broadcasts", primary=False, markup=True, font_size=sp(15), height=dp(44))
            b2.bind(on_release=lambda _: setattr(self.manager, "current", "admin_broadcasts_list"))
            self.content.add_widget(b2)

            # --- 3. SYSTEM ACTIONS ---
            self.content.add_widget(SHVLabel(text="System Actions", font_size=sp(11), bold=True, color=C_TEAL, size_hint_y=None, height=dp(16)))
            
            b3 = SHVButton(text=f"[font={FONT_PATH}]🔄[/font]  Trigger Store App Update", primary=False, markup=True, font_size=sp(15), height=dp(44))
            b3.bind(on_release=lambda _: setattr(self.manager, "current", "admin_store_update_form"))
            self.content.add_widget(b3)
            
        Clock.schedule_once(_main)


class AdminBroadcastFormScreen(Screen):
    def on_enter(self): 
        self.clear_widgets()
        self._build()
        
    def _build(self):
        root = BoxLayout(orientation="vertical")
        make_bg(root, C_BG)
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8))
        make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "admin_dashboard"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text="New Broadcast", font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        root.add_widget(topbar)
        
        scroll = ScrollView()
        layout = BoxLayout(orientation="vertical", padding=[dp(16), dp(12)], spacing=dp(8), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        self.status = StatusBar(size_hint_x=1)
        layout.add_widget(self.status)
        
        layout.add_widget(SHVLabel(text="Send a message to all customer apps.", font_size=sp(12), color=C_TEXT_SEC, size_hint_y=None, height=dp(32)))
        layout.add_widget(spacer(4))
        
        self.f_title = SHVTextInput(text="")
        layout.add_widget(paste_row("Broadcast Title *", self.f_title))
        layout.add_widget(self.f_title)
        
        self.f_msg = SHVMultiInput(text="", height=dp(200))
        layout.add_widget(paste_row("Message Body *", self.f_msg))
        layout.add_widget(self.f_msg)
        
        layout.add_widget(spacer(8))
        send_btn = SHVButton(text="Send to All Users", primary=True, height=dp(52))
        send_btn.bind(on_release=self._send_broadcast)
        layout.add_widget(send_btn)
        
        layout.add_widget(spacer(24))
        scroll.add_widget(layout)
        root.add_widget(scroll)
        self.add_widget(root)
        
    def _send_broadcast(self, *_):
        title, msg = self.f_title.text.strip(), self.f_msg.text.strip()
        if not title or not msg: 
            return self.status.show("Title and message are required")
            
        data = {"title": title, "message": msg}
        self.status.show("Broadcasting...", success=True, duration=30)
        
        def _thread():
            resp, status = supabase.insert("broadcasts", data)
            Clock.schedule_once(lambda _: (self.status.show("Message Sent!", success=True), Clock.schedule_once(lambda _: setattr(self.manager, "current", "admin_dashboard"), 1.5)) if status in (200, 201) else self.status.show("Broadcast failed to send"))
            
        threading.Thread(target=_thread, daemon=True).start()

class AdminBroadcastsScreen(Screen):
    def on_enter(self):
        self.clear_widgets()
        self._build()
        threading.Thread(target=self._load_broadcasts, daemon=True).start()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        make_bg(root, C_BG)

        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8))
        make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "admin_dashboard"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text="Sent Broadcasts", font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        root.add_widget(topbar)

        self.status = StatusBar(size_hint_x=1)
        root.add_widget(self.status)

        scroll = ScrollView()
        self.list_layout = BoxLayout(orientation="vertical", padding=[dp(12), dp(12)], spacing=dp(10), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)
        self.add_widget(root)

    def _load_broadcasts(self):
        try:
            resp, status = supabase.select_filtered("broadcasts", {}, order="created_at.desc")
        except Exception:
            resp, status = [], 500
            
        def _main(*_):
            self.list_layout.clear_widgets()
            if status == 200 and isinstance(resp, list) and resp:
                for b in resp:
                    card = SHVCard(color=C_CARD, padding=dp(12), spacing=dp(8), size_hint_y=None, height=dp(120))
                    card.add_widget(SHVLabel(text=b.get("title", "No Title"), font_size=sp(15), bold=True, color=C_TEAL))
                    
                    body_preview = b.get("message", "")[:70] + "..." if len(b.get("message","")) > 70 else b.get("message","")
                    card.add_widget(SHVLabel(text=body_preview, font_size=sp(12), color=C_TEXT_SEC))
                    
                    btn_row = BoxLayout(size_hint_y=None, height=dp(32))
                    btn_row.add_widget(Widget()) 
                    
                    del_btn = Button(text="Delete Message", size_hint=(None, None), size=(dp(120), dp(32)), background_color=(0,0,0,0), color=C_ROSE, font_size=sp(12), bold=True)
                    with del_btn.canvas.before:
                        Color(0.15, 0.05, 0.05, 1)
                        del_btn._bg = RoundedRectangle(pos=del_btn.pos, size=del_btn.size, radius=[dp(6)])
                    del_btn.bind(pos=lambda w, val: setattr(w._bg, 'pos', w.pos), size=lambda w, val: setattr(w._bg, 'size', w.size))
                    
                    del_btn.bind(on_release=lambda _, bid=b["id"]: self._delete_broadcast(bid))
                    btn_row.add_widget(del_btn)
                    card.add_widget(btn_row)
                    self.list_layout.add_widget(card)
            else:
                self.list_layout.add_widget(SHVLabel(text="No broadcasts sent yet.", halign="center", color=C_TEXT_SEC, height=dp(60)))
        Clock.schedule_once(_main)

    def _delete_broadcast(self, broadcast_id):
        ProgressModal.show("Deleting Broadcast...")
        def _thread():
            try:
                resp, status = supabase.delete("broadcasts", broadcast_id)
                # FIX: Catch the silent failure!
                # If Supabase returns 200 OK but the list is empty, RLS blocked the deletion.
                if status == 200 and isinstance(resp, list) and len(resp) == 0:
                    success = False
                    err_msg = "Blocked by DB Permissions"
                else:
                    success = (status in (200, 204))
                    err_msg = "Delete failed"
            except Exception as e:
                success = False
                err_msg = "Network Error"
            
            def _done(*_):
                if success:
                    ProgressModal.success("Message Deleted!")
                    self._load_broadcasts() 
                else:
                    ProgressModal.error(err_msg)
            Clock.schedule_once(_done)
            
        threading.Thread(target=_thread, daemon=True).start()



class AdminStoreUpdateFormScreen(Screen):
    def on_enter(self):
        self.clear_widgets()
        self._build()
        threading.Thread(target=self._load_config, daemon=True).start()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        make_bg(root, C_BG)

        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8))
        make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "admin_dashboard"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text="Store App Update Config", font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        root.add_widget(topbar)

        scroll = ScrollView()
        self.form = BoxLayout(orientation="vertical", padding=[dp(16), dp(12)], spacing=dp(8), size_hint_y=None)
        self.form.bind(minimum_height=self.form.setter("height"))

        self.status = StatusBar(size_hint_x=1)
        self.form.add_widget(self.status)

        self.form.add_widget(SHVLabel(text="Push an update modal to all user devices running an older version.", font_size=sp(12), color=C_TEXT_SEC, size_hint_y=None, height=dp(32)))
        self.form.add_widget(spacer(4))

        self.f_version = SHVTextInput(text="Loading...")
        self.form.add_widget(paste_row("Latest App Version (e.g., 1.0.1) *", self.f_version))
        self.form.add_widget(self.f_version)

        self.f_url = SHVTextInput(text="Loading...")
        self.form.add_widget(paste_row("APK Download URL *", self.f_url))
        self.form.add_widget(self.f_url)

        self.f_msg = SHVMultiInput(text="Loading...", height=dp(120), keyboard_suggestions=False)
        self.form.add_widget(paste_row("Release Notes / Message", self.f_msg))
        self.form.add_widget(self.f_msg)

        self.form.add_widget(spacer(8))
        save_btn = SHVButton(text="Publish Store Update", primary=True, height=dp(52))
        save_btn.bind(on_release=self._save_config)
        self.form.add_widget(save_btn)

        self.form.add_widget(spacer(24))
        scroll.add_widget(self.form)
        root.add_widget(scroll)
        self.add_widget(root)

    def _load_config(self):
        # Admin app uses standard select
        resp, status = supabase.select("store_config", params={"limit": "1"})
        def _main(*_):
            if status == 200 and isinstance(resp, list) and resp:
                data = resp[0]
                self.f_version.text = data.get("latest_version", "")
                self.f_url.text = data.get("apk_url", "")
                self.f_msg.text = data.get("update_message", "")
            else:
                self.status.show("Failed to load current config", duration=4)
        Clock.schedule_once(_main)

    def _save_config(self, *_):
        version = self.f_version.text.strip()
        url = self.f_url.text.strip()
        msg = self.f_msg.text.strip()

        if not version or not url:
            return self.status.show("Version and URL are required!")

        data = {
            "latest_version": version,
            "apk_url": url,
            "update_message": msg
        }

        self.status.show("Updating store config...", success=True, duration=30)
        def _thread():
            # ID is hardcoded to 1 since we only have one store_config row
            resp, status = supabase.update("store_config", 1, data)
            def _main(*_):
                if status in (200, 204):
                    self.status.show("Store Update Triggered!", success=True)
                    Clock.schedule_once(lambda _: setattr(self.manager, "current", "admin_dashboard"), 1.5)
                else:
                    self.status.show("Failed to trigger update")
            Clock.schedule_once(_main)
        threading.Thread(target=_thread, daemon=True).start()



# ─────────────────────────────────────────────
#  CUSTOMER STORE COMPONENTS
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  CONTACT US MODAL (Customer-facing)
# ─────────────────────────────────────────────
class ContactUsModal:
    """Fetches contact info from Supabase and shows a tappable contact sheet."""

    CONTACTS = [
        ("WhatsApp",  "whatsapp",  "#25D366"),
        ("Email",     "email",     "#00BFA5"),
        ("Discord",   "discord",   "#5865F2"),
        ("Telegram",  "telegram",  "#0088CC"),
        ("Instagram", "instagram", "#E1306C"),
        ("Website",   "website",   "#F9A825"),
    ]

    @staticmethod
    def _build_url(key, value):
        """Convert a raw value into the correct deep-link URL for each platform."""
        value = value.strip()
        if not value:
            return None
        if key == "whatsapp":
            # Accept number with or without + country code
            number = "".join(c for c in value if c.isdigit() or c == "+")
            return f"https://wa.me/{number.lstrip('+')}"
        elif key == "email":
            if value.startswith("mailto:"):
                return value
            return f"mailto:{value}"
        elif key == "discord":
            if value.startswith("http"):
                return value
            return f"https://discord.gg/{value}"
        elif key == "telegram":
            handle = value.lstrip("@")
            if handle.startswith("http"):
                return handle
            return f"https://t.me/{handle}"
        elif key == "instagram":
            handle = value.lstrip("@")
            if handle.startswith("http"):
                return handle
            return f"https://instagram.com/{handle}"
        elif key == "website":
            if value.startswith("http"):
                return value
            return f"https://{value}"
        return value

    @classmethod
    def show(cls):
        from kivy.uix.modalview import ModalView
        view = ModalView(size_hint=(0.92, None), height=dp(480), background_color=(0, 0, 0, 0))

        root = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(14))
        make_bg(root, get_color_from_hex("#0D0D0D"), radius=dp(16))

        # Title row
        title_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        title_row.add_widget(Label(
            text="Contact Us", font_size=sp(19), bold=True, color=get_color_from_hex("#F9A825"),
            halign="left", text_size=(Window.width * 0.7, None)
        ))
        close_btn = Button(
            text="X", font_size=sp(14), bold=True, color=get_color_from_hex("#9E9E9E"),
            background_color=(0, 0, 0, 0), size_hint_x=None, width=dp(36)
        )
        close_btn.bind(on_release=lambda _: view.dismiss())
        title_row.add_widget(close_btn)
        root.add_widget(title_row)

        # Divider
        div = Widget(size_hint_y=None, height=dp(1))
        make_bg(div, get_color_from_hex("#1F1F1F"))
        root.add_widget(div)

        # Loading label — replaced once data arrives
        status_lbl = Label(
            text="Loading contact info...", font_size=sp(13),
            color=get_color_from_hex("#9E9E9E"), size_hint_y=None, height=dp(40)
        )
        btn_container = BoxLayout(
            orientation="vertical", spacing=dp(10),
            size_hint_y=None, height=dp(300)
        )
        btn_container.add_widget(status_lbl)
        root.add_widget(btn_container)
        
        # ---> THE SPACER WIDGET FIX <---
        # This invisible widget absorbs all extra vertical space, pushing everything else to the top
        root.add_widget(Widget())

        view.add_widget(root)
        view.open()

        def _load():
            info = supabase.get_contact_info()

            def _build(*_):
                btn_container.clear_widgets()
                any_contact = False
                for label, key, hex_col in cls.CONTACTS:
                    raw = info.get(key, "").strip() if info else ""
                    if not raw:
                        continue
                    url = cls._build_url(key, raw)
                    if not url:
                        continue
                    any_contact = True
                    col = get_color_from_hex(hex_col)
                    btn = Button(
                        text=label, font_size=sp(15), bold=True,
                        background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
                        size_hint_y=None, height=dp(48)
                    )
                    with btn.canvas.before:
                        Color(*col)
                        btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(10)])
                    def _upd(w, *_): w._bg.pos, w._bg.size = w.pos, w.size
                    btn.bind(pos=_upd, size=_upd)
                    btn.bind(on_press=lambda w: setattr(w, "opacity", 0.7))
                    btn.bind(on_release=lambda w, u=url: (_open_url_in_browser(u), setattr(w, "opacity", 1)))
                    btn_container.add_widget(btn)

                if not any_contact:
                    btn_container.add_widget(Label(
                        text="No contact info available yet.",
                        font_size=sp(13), color=get_color_from_hex("#9E9E9E"),
                        size_hint_y=None, height=dp(40)
                    ))

            Clock.schedule_once(_build)

        threading.Thread(target=_load, daemon=True).start()


class ProgressModal:
    _view = None
    _layout = None
    _label = None
    _bar = None
    _event = None

    @classmethod
    def show(cls, text="Processing..."):
        from kivy.uix.modalview import ModalView
        from kivy.uix.progressbar import ProgressBar
        
        if cls._view is None:
            # Create the dark-themed modal popup
            cls._view = ModalView(size_hint=(0.85, None), height=dp(120), auto_dismiss=False, background_color=(0,0,0,0.8))
            cls._layout = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
            make_bg(cls._layout, C_CARD, radius=dp(16))
            
            cls._label = Label(text="", font_size=sp(16), bold=True, color=C_TEAL)
            cls._layout.add_widget(cls._label)
            
            cls._bar = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(10))
            cls._layout.add_widget(cls._bar)
            
            cls._view.add_widget(cls._layout)
            
        cls._label.text = text
        cls._label.color = C_TEAL
        cls._bar.value = 0
        cls._bar.opacity = 1
        
        # Animate the progress bar to simulate processing
        if cls._event: cls._event.cancel()
        def _animate(dt):
            cls._bar.value += 8
            if cls._bar.value >= 85: cls._bar.value = 85 # Hold at 85% until success is confirmed
        cls._event = Clock.schedule_interval(_animate, 0.05)
        cls._view.open()

    @classmethod
    def success(cls, text="Successfully Saved!", callback=None):
        if cls._event: cls._event.cancel()
        cls._bar.value = 100
        cls._label.text = text
        cls._label.color = get_color_from_hex("#4CAF50") # Success Green
        def _close(*_):
            cls._view.dismiss()
            if callback: callback() # Auto-navigate back after closing
        Clock.schedule_once(_close, 1.2) # Show the green success text for 1.2 seconds

    @classmethod
    def error(cls, text="Action Failed"):
        if cls._event: cls._event.cancel()
        cls._bar.opacity = 0
        cls._label.text = text
        cls._label.color = get_color_from_hex("#F44336") # Error Red
        Clock.schedule_once(lambda _: cls._view.dismiss(), 2.5)



class StoreUpdateModal:
    @classmethod
    def show(cls, version, url, notes):
        from kivy.uix.modalview import ModalView
        # We make auto_dismiss=False so they can't just tap outside to close it easily.
        # They have to actively choose "Later" or "Update Now".
        view = ModalView(size_hint=(0.85, None), height=dp(280), auto_dismiss=False, background_color=(0,0,0,0.8))
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        make_bg(box, C_CARD, radius=dp(16))

        box.add_widget(Label(text="Store Update Available!", font_size=sp(18), bold=True, color=C_TEAL, size_hint_y=None, height=dp(30), halign="left", text_size=(Window.width*0.7, None)))
        box.add_widget(Label(text=f"Version {version} is now available to download.", font_size=sp(13), color=C_TEXT, size_hint_y=None, height=dp(20), halign="left", text_size=(Window.width*0.7, None)))

        scroll = ScrollView()
        notes_lbl = Label(text=notes, font_size=sp(13), color=C_TEXT_SEC, size_hint_y=None, halign="left", valign="top")
        notes_lbl.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        notes_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        scroll.add_widget(notes_lbl)
        box.add_widget(scroll)

        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))
        skip_btn = SHVButton(text="Later", primary=False)
        skip_btn.bind(on_release=lambda _: view.dismiss())
        update_btn = SHVButton(text="Update Now", primary=True)
        update_btn.bind(on_release=lambda _: (_open_url_in_browser(url), view.dismiss()))

        btn_row.add_widget(skip_btn)
        btn_row.add_widget(update_btn)
        box.add_widget(btn_row)

        view.add_widget(box)
        view.open()



class StoreNavBar(BoxLayout):
    TABS = [("Home", "🏠"), ("Store", "📦"), ("Updates", "🔔"), ("Account", "👤"), ("Exit", "🚪")]
    def __init__(self, screen_manager, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(58), **kwargs)
        self.sm, self._btns = screen_manager, {}
        make_bg(self, C_NAV)
        for name, icon in self.TABS:
            btn = self._make_tab(name, icon)
            self._btns[name] = btn; self.add_widget(btn)
        with self.canvas.before:
            Color(*C_DIVIDER)
            self._line = Rectangle(pos=(self.x, self.top - dp(1)), size=(self.width, dp(1)))
        def upd(*_): self._line.pos, self._line.size = (self.x, self.top - dp(1)), (self.width, dp(1))
        self.bind(pos=upd, size=upd)

    def _make_tab(self, name, icon):
        btn = BoxLayout(orientation="vertical", spacing=dp(2), padding=[0, dp(6)])
        btn.bind(on_touch_down=lambda w, t: self._tab_pressed(name) if w.collide_point(*t.pos) else None)
        btn._icon = Label(text=icon, font_size=sp(18), size_hint_y=None, height=dp(22), color=C_TEXT_SEC, font_name=FONT_PATH)
        btn._name_lbl = Label(text=name.upper(), font_size=sp(14), size_hint_y=None, height=dp(18), color=C_TEXT_SEC)
        btn.add_widget(btn._icon); btn.add_widget(btn._name_lbl)
        return btn

    def _tab_pressed(self, name):
        if name == "Exit":
            App.get_running_app().show_exit_confirm()
            return
        screen_map = {"Home": "store_home", "Store": "store_catalog", "Updates": "store_updates", "Account": "store_account"}
        if name in screen_map:
            self.sm.current = screen_map[name]; self.set_active(name)

    def set_active(self, name):
        for tab_name, btn in self._btns.items():
            if tab_name == "Exit":
                btn._icon.color, btn._name_lbl.color = C_ROSE, C_ROSE
                continue
            col = C_TEAL if tab_name == name else C_TEXT_SEC
            btn._icon.color, btn._name_lbl.color = col, col

class StoreScreenWithNav(Screen):
    nav_tab = StringProperty("Home")
    def build_body(self): return Widget()
    def on_pre_enter(self):
        if not self.children:
            root = BoxLayout(orientation="vertical"); make_bg(root, C_BG)
            root.add_widget(self.build_body())
            self._nav_bar = StoreNavBar(screen_manager=self.manager)
            root.add_widget(self._nav_bar); self.add_widget(root)
    def on_enter(self):
        if hasattr(self, "_nav_bar"): self._nav_bar.set_active(self.nav_tab)

class StoreLoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = JsonStore(os.path.join(APP_DIR, "store_auth.json"))
        self._build()
    def _build(self):
        root = FloatLayout(); make_bg(root, C_BG)
        scroll = ScrollView(size_hint=(1, 1))
        layout = BoxLayout(orientation="vertical", padding=[dp(32), dp(60), dp(32), dp(32)], spacing=dp(16), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        brand = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(100), spacing=dp(4))
        brand.add_widget(Label(text="SHV", font_size=sp(48), bold=True, color=C_TEAL, size_hint_y=None, height=dp(60)))
        brand.add_widget(Label(text="SH VERTEX STORE", font_size=sp(12), color=C_TEXT_SEC, size_hint_y=None, height=dp(20)))
        layout.add_widget(brand); layout.add_widget(Widget(size_hint_y=None, height=dp(20)))

        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        layout.add_widget(Label(text="Welcome back", font_size=sp(22), bold=True, color=C_TEXT, size_hint_y=None, height=dp(36), halign="left", text_size=(Window.width - dp(64), None)))

        saved_email, saved_pass, is_rem = "", "", False
        if self.store.exists("creds"):
            c = self.store.get("creds")
            saved_email, saved_pass, is_rem = c.get("email", ""), c.get("password", ""), True

        layout.add_widget(SHVLabel(text="Email", size_hint_y=None, height=dp(20), color=C_TEXT_SEC, font_size=sp(12)))
        self.email_input = SHVTextInput(hint_text="you@example.com", input_type="mail", text=saved_email); layout.add_widget(self.email_input)
        layout.add_widget(SHVLabel(text="Password", size_hint_y=None, height=dp(20), color=C_TEXT_SEC, font_size=sp(12)))
        self.pass_input = SHVTextInput(hint_text="••••••••", password=True, input_type="text", text=saved_pass); layout.add_widget(self.pass_input)

        rem_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(12))
        rem_row.add_widget(SHVLabel(text="Remember Me", size_hint_y=None, height=dp(40), color=C_TEXT_SEC))
        self.sw_remember = Switch(active=is_rem, size_hint_x=None, width=dp(70))
        rem_row.add_widget(self.sw_remember); layout.add_widget(rem_row)
        layout.add_widget(Widget(size_hint_y=None, height=dp(8)))

        btn_login = SHVButton(text="Sign In", primary=True)
        btn_login.bind(on_release=self._do_login); layout.add_widget(btn_login)

        divider_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        divider_row.add_widget(Widget()); divider_row.add_widget(Label(text="or", color=C_TEXT_SEC, font_size=sp(12), size_hint_x=None, width=dp(20))); divider_row.add_widget(Widget())
        layout.add_widget(divider_row)

        btn_reg = SHVButton(text="Create Account", primary=False)
        btn_reg.bind(on_release=lambda _: setattr(self.manager, "current", "store_register")); layout.add_widget(btn_reg)
        
        back_btn = SHVButton(text="Back to Hub", primary=False)
        back_btn.bind(on_release=lambda _: setattr(self.manager, "current", "hub"))
        layout.add_widget(back_btn)

        layout.add_widget(Widget(size_hint_y=None, height=dp(20)))
        layout.add_widget(Label(text=f"SH Vertex Technologies  •  v{APP_VERSION}", font_size=sp(10), color=C_TEXT_HINT, size_hint_y=None, height=dp(20)))
        scroll.add_widget(layout); root.add_widget(scroll); self.add_widget(root)

    def _do_login(self, *_):
        email, password = self.email_input.text.strip(), self.pass_input.text.strip()
        if not email or not password: return self.status.show("Please fill in all fields")
        self.status.show("Signing in...", success=True, duration=30)
        def _thread():
            resp, status = supabase.sign_in(email, password)
            def _main(*_):
                if status == 200:
                    if self.sw_remember.active: self.store.put("creds", email=email, password=password)
                    elif self.store.exists("creds"): self.store.delete("creds")
                    self.manager.current = "store_home"
                else: self.status.show(resp.get("error_description") or resp.get("msg") or "Login failed")
            Clock.schedule_once(_main)
        threading.Thread(target=_thread, daemon=True).start()

class RegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self._build()
    def _build(self):
        root = FloatLayout(); make_bg(root, C_BG)
        scroll = ScrollView(size_hint=(1, 1))
        layout = BoxLayout(orientation="vertical", padding=[dp(32), dp(50), dp(32), dp(32)], spacing=dp(16), size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        back_btn = Button(text="⬅️ Back", font_size=sp(13), color=C_TEAL, background_color=(0,0,0,0), size_hint_y=None, height=dp(36), halign="left", font_name=FONT_PATH)
        back_btn.bind(on_release=lambda _: setattr(self.manager, "current", "store_login")); layout.add_widget(back_btn)
        layout.add_widget(Label(text="Create Account", font_size=sp(24), bold=True, color=C_TEXT, size_hint_y=None, height=dp(40)))
        layout.add_widget(Label(text="Join SH Vertex to access our apps", font_size=sp(13), color=C_TEXT_SEC, size_hint_y=None, height=dp(24)))
        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        fields = [("Display Name", "display_name", "Your name", "text", False), ("Email", "email", "you@example.com", "mail", False), ("Password", "password", "Min 6 characters", "text", True), ("Confirm", "confirm", "Re-enter password", "text", True)]
        self._inputs = {}
        for label, key, hint, itype, is_pass in fields:
            layout.add_widget(SHVLabel(text=label, size_hint_y=None, height=dp(20), color=C_TEXT_SEC, font_size=sp(12)))
            ti = SHVTextInput(hint_text=hint, password=is_pass, input_type=itype); self._inputs[key] = ti; layout.add_widget(ti)
        layout.add_widget(Widget(size_hint_y=None, height=dp(8)))
        btn = SHVButton(text="Create Account", primary=True); btn.bind(on_release=self._do_register); layout.add_widget(btn)
        scroll.add_widget(layout); root.add_widget(scroll); self.add_widget(root)
    def _do_register(self, *_):
        name, email, password, confirm = self._inputs["display_name"].text.strip(), self._inputs["email"].text.strip(), self._inputs["password"].text.strip(), self._inputs["confirm"].text.strip()
        if not all([name, email, password, confirm]): return self.status.show("Please fill in all fields")
        if password != confirm: return self.status.show("Passwords do not match")
        if len(password) < 6: return self.status.show("Password must be at least 6 characters")
        self.status.show("Creating account...", success=True, duration=30)
        def _thread():
            resp, status = supabase.sign_up(email, password, display_name=name)
            Clock.schedule_once(lambda _: (self.status.show("Account created!", success=True, duration=4), Clock.schedule_once(lambda _: setattr(self.manager, "current", "store_login"), 2)) if status in (200, 201) else self.status.show(resp.get("msg") or "Registration failed"))
        threading.Thread(target=_thread, daemon=True).start()

class StoreNewsCard(SHVCard):
    def __init__(self, item, **kwargs):
        super().__init__(size_hint_y=None, spacing=dp(10), **kwargs)
        self.item = item
        
        # 1. Cover Image Header
        img_url = item.get("cover_image_url", "").strip()
        if img_url:
            img = load_remote_image(img_url, fallback_text="📰", height=dp(140))
            img.size_hint_y = None
            img.height = dp(140)
            self.add_widget(img)

        # 2. Date
        self.add_widget(SHVLabel(text=item.get("created_at", "")[:10], font_size=sp(10), color=C_TEAL, size_hint_y=None, height=dp(16)))
        
        # 3. Dynamic Title (Always visible, wraps text)
        title_lbl = Label(text=item.get("title", ""), font_size=sp(16), bold=True, color=C_TEXT, size_hint_y=None, halign="left", valign="middle")
        title_lbl.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        title_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        self.add_widget(title_lbl)

        # 4. Preview Body
        body = item.get("body", "")
        preview = body[:120] + ("..." if len(body) > 120 else "")
        body_lbl = Label(text=preview, font_size=sp(13), color=C_TEXT_SEC, size_hint_y=None, halign="left", valign="top")
        body_lbl.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        body_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        self.add_widget(body_lbl)
        
        # 5. Read More Button
        btn = SHVButton(text="Read Full Article", primary=False, height=dp(36))
        btn.bind(on_release=self._show_full_article)
        self.add_widget(btn)
        
        self.bind(minimum_height=self.setter("height"))

    def _show_full_article(self, *_):
        from kivy.uix.modalview import ModalView
        view = ModalView(size_hint=(0.9, 0.8), background_color=(0,0,0,0.8))
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        make_bg(box, C_CARD, radius=dp(16))
        
        scroll = ScrollView()
        content = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        title = Label(text=self.item.get("title", ""), font_size=sp(18), bold=True, color=C_TEXT, size_hint_y=None, halign="left")
        title.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        title.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        content.add_widget(title)
        
        body = Label(text=self.item.get("body", ""), font_size=sp(14), color=C_TEXT_SEC, size_hint_y=None, halign="left")
        body.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        body.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        content.add_widget(body)
        
        scroll.add_widget(content)
        box.add_widget(scroll)
        
        close_btn = SHVButton(text="Close", primary=True, height=dp(44))
        close_btn.bind(on_release=view.dismiss)
        box.add_widget(close_btn)
        
        view.add_widget(box)
        view.open()


class BroadcastMessageCard(SHVCard):
    def __init__(self, item, is_read, on_read, **kwargs):
        super().__init__(size_hint_y=None, spacing=dp(8), **kwargs)
        self.item = item
        self._on_read = on_read
        self.is_read = is_read

        top_row = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(8))
        date_str = item.get("created_at", "")[:10]
        top_row.add_widget(SHVLabel(text=date_str, font_size=sp(10), color=C_TEAL, size_hint_y=None, height=dp(18)))
        
        # New Badge if unread
        self.new_badge = None
        if not self.is_read:
            self.new_badge = Label(text="NEW", font_size=sp(9), bold=True, color=C_BG, size_hint_x=None, width=dp(40))
            with self.new_badge.canvas.before:
                Color(*C_AMBER)
                self._b_bg = RoundedRectangle(pos=self.new_badge.pos, size=self.new_badge.size, radius=[dp(6)])
            def _upd(w, *_): self._b_bg.pos, self._b_bg.size = w.pos, w.size
            self.new_badge.bind(pos=_upd, size=_upd)
            top_row.add_widget(self.new_badge)
        
        self.add_widget(top_row)
        
        # Title
        self.title_lbl = Label(
            text=item.get("title", ""), 
            font_size=sp(15), 
            bold=not self.is_read, 
            color=C_TEXT if not self.is_read else C_TEXT_SEC, 
            size_hint_y=None, halign="left", valign="middle"
        )
        self.title_lbl.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        self.title_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        self.add_widget(self.title_lbl)

        # Body Preview
        body = item.get("message", "")
        preview = body[:80] + ("..." if len(body) > 80 else "")
        self.body_lbl = Label(text=preview, font_size=sp(13), color=C_TEXT_SEC, size_hint_y=None, halign="left", valign="top")
        self.body_lbl.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        self.body_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        self.add_widget(self.body_lbl)

        btn = SHVButton(text="Read Message", primary=False, height=dp(36))
        btn.bind(on_release=self._open_message)
        self.add_widget(btn)

        self.bind(minimum_height=self.setter("height"))

    def _open_message(self, *_):
        # Mark as read locally and visually update the card immediately
        if not self.is_read:
            self.is_read = True
            self.title_lbl.bold = False
            self.title_lbl.color = C_TEXT_SEC
            if self.new_badge:
                self.new_badge.opacity = 0 
            self._on_read(self.item["id"])
        
        # Open Modal
        from kivy.uix.modalview import ModalView
        view = ModalView(size_hint=(0.9, 0.7), background_color=(0,0,0,0.8))
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        make_bg(box, C_CARD, radius=dp(16))
        
        scroll = ScrollView()
        content = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        
        title = Label(text=self.item.get("title", ""), font_size=sp(18), bold=True, color=C_TEXT, size_hint_y=None, halign="left")
        title.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        title.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        content.add_widget(title)
        
        body = Label(text=self.item.get("message", ""), font_size=sp(14), color=C_TEXT_SEC, size_hint_y=None, halign="left")
        body.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        body.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        content.add_widget(body)
        
        scroll.add_widget(content)
        box.add_widget(scroll)
        
        close_btn = SHVButton(text="Close", primary=True, height=dp(44))
        close_btn.bind(on_release=lambda _: view.dismiss())
        box.add_widget(close_btn)
        
        view.add_widget(box)
        view.open()

class StoreHomeScreen(StoreScreenWithNav):
    nav_tab = "Home"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.read_store = JsonStore(os.path.join(APP_DIR, "read_broadcasts.json"))

    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(16), dp(8)], spacing=dp(8)); make_bg(header, C_SURFACE)
        
        # Adjust width dynamically to fit both buttons
        header.add_widget(Label(text="SHV Store", font_size=sp(18), bold=True, color=C_TEAL, halign="left", text_size=(Window.width - dp(210), None)))
        
        # --- INBOX BUTTON (Dark Green) ---
        self.inbox_btn = Button(
            text="Inbox", font_size=sp(14), bold=True,
            background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
            size_hint_x=None, width=dp(80)
        )
        with self.inbox_btn.canvas.before:
            Color(*C_TEAL_DARK)
            self.inbox_btn._ibg = RoundedRectangle(pos=self.inbox_btn.pos, size=self.inbox_btn.size, radius=[dp(8)])
        def _upd_ib(*_): self.inbox_btn._ibg.pos, self.inbox_btn._ibg.size = self.inbox_btn.pos, self.inbox_btn.size
        self.inbox_btn.bind(pos=_upd_ib, size=_upd_ib)
        self.inbox_btn.bind(on_release=lambda _: setattr(self.manager, "current", "store_inbox"))
        header.add_widget(self.inbox_btn)

        # --- CONTACT BUTTON ---
        contact_btn = Button(
            text="Contact", font_size=sp(14), bold=True,
            background_color=(0, 0, 0, 0), color=(0, 0, 0, 1),
            size_hint_x=None, width=dp(80)
        )
        with contact_btn.canvas.before:
            Color(*C_AMBER)
            contact_btn._cbg = RoundedRectangle(pos=contact_btn.pos, size=contact_btn.size, radius=[dp(8)])
        def _upd_cb(*_): contact_btn._cbg.pos, contact_btn._cbg.size = contact_btn.pos, contact_btn.size
        contact_btn.bind(pos=_upd_cb, size=_upd_cb)
        contact_btn.bind(on_release=lambda _: ContactUsModal.show())
        header.add_widget(contact_btn)
        
        layout.add_widget(header)
        
        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        scroll = ScrollView()
        self.feed_layout = BoxLayout(orientation="vertical", padding=[dp(12), dp(12)], spacing=dp(10), size_hint_y=None)
        self.feed_layout.bind(minimum_height=self.feed_layout.setter("height"))
        self.feed_layout.add_widget(SHVLabel(text="Loading news...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.feed_layout); layout.add_widget(scroll)
        return layout

    def on_enter(self): 
        super().on_enter()
        threading.Thread(target=self._load_data, daemon=True).start()

    def _load_data(self):
        # Fetch News
        news_resp, news_status = supabase.select_filtered("news", {"is_published": "eq.true"}, order="created_at.desc", limit=20)
        # Fetch Broadcasts for unread count
        b_resp, b_status = supabase.select_filtered("broadcasts", {}, order="created_at.desc")
        
        # ---> THIS IS THE FIXED LINE <---
        conf_resp, conf_status = supabase.select_filtered("store_config", {}, limit=1)
        
        def _main(*_):
            # 1. Update News Feed
            self.feed_layout.clear_widgets()
            if news_status == 200 and isinstance(news_resp, list) and news_resp:
                for item in news_resp: self.feed_layout.add_widget(StoreNewsCard(item))
            else: self.status.show("No news yet.", success=True, duration=5)
            
            # 2. Check unread broadcasts
            unread_count = 0
            if b_status == 200 and isinstance(b_resp, list):
                for b in b_resp:
                    if not self.read_store.exists(str(b["id"])):
                        unread_count += 1
            
            if unread_count > 0:
                self.inbox_btn.text = f"Inbox ({unread_count})"
            else:
                self.inbox_btn.text = "Inbox"

            # 3. Check Auto-Updater logic safely
            if conf_status == 200 and isinstance(conf_resp, list) and conf_resp:
                config = conf_resp[0]
                db_ver_str = config.get("latest_version", APP_VERSION)
                
                try:
                    # Safely converts "1.0.1" into [1, 0, 1] to check if database version is mathematically higher
                    db_ver_list = [int(x) for x in db_ver_str.split(".") if x.isdigit()]
                    app_ver_list = [int(x) for x in APP_VERSION.split(".") if x.isdigit()]
                    is_newer = db_ver_list > app_ver_list
                except Exception:
                    is_newer = db_ver_str > APP_VERSION

                if is_newer:
                    StoreUpdateModal.show(
                        db_ver_str,
                        config.get("apk_url", ""),
                        config.get("update_message", "A new update is available for the SHV Store!")
                    )

        Clock.schedule_once(_main)



class StoreInboxScreen(StoreScreenWithNav):
    nav_tab = "Home" # Keep "Home" highlighted on the bottom nav
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.read_store = JsonStore(os.path.join(APP_DIR, "read_broadcasts.json"))

    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), 0], spacing=dp(8))
        make_bg(topbar, C_SURFACE)
        back = Button(text="⬅️", font_size=sp(22), color=C_TEAL, background_color=(0,0,0,0), size_hint_x=None, width=dp(40), font_name=FONT_PATH)
        back.bind(on_release=lambda _: setattr(self.manager, "current", "store_home"))
        topbar.add_widget(back)
        topbar.add_widget(Label(text="Inbox", font_size=sp(16), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(80), None)))
        layout.add_widget(topbar)

        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        scroll = ScrollView()
        self.feed = BoxLayout(orientation="vertical", padding=[dp(12), dp(12)], spacing=dp(10), size_hint_y=None)
        self.feed.bind(minimum_height=self.feed.setter("height"))
        self.feed.add_widget(SHVLabel(text="Loading messages...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.feed)
        layout.add_widget(scroll)
        return layout

    def on_enter(self):
        super().on_enter()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        resp, status = supabase.select_filtered("broadcasts", {}, order="created_at.desc")
        def _main(*_):
            self.feed.clear_widgets()
            if status == 200 and isinstance(resp, list) and resp:
                for item in resp:
                    msg_id = str(item.get("id"))
                    is_read = self.read_store.exists(msg_id)
                    self.feed.add_widget(BroadcastMessageCard(item, is_read, self._mark_read))
            else:
                self.feed.add_widget(SHVLabel(text="Inbox is empty.", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        Clock.schedule_once(_main)

    def _mark_read(self, msg_id):
        if not self.read_store.exists(str(msg_id)):
            self.read_store.put(str(msg_id), read=True)


class AppTile(BoxLayout):
    def __init__(self, item, on_tap, **kwargs):
        # Changed to horizontal and reduced height to 88dp for a sleek list view
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(88), padding=[dp(12), dp(12)], spacing=dp(16), **kwargs)
        self._item, self._on_tap = item, on_tap
        make_bg(self, C_CARD, radius=dp(12))
        
        # 1. Left: App Icon
        self.add_widget(load_remote_image(item.get("icon_url") or "", fallback_text="📦", size_hint_x=None, width=dp(64), height=dp(64)))
        
        # 2. Middle: Title and Tagline Column
        text_col = BoxLayout(orientation="vertical", spacing=dp(2))
        text_col.add_widget(SHVLabel(text=item.get("name", ""), font_size=sp(15), bold=True, size_hint_y=None, height=dp(22)))
        
        tagline_lbl = Label(text=item.get("tagline", ""), font_size=sp(11), color=C_TEXT_SEC, size_hint_y=None, halign="left", valign="top")
        tagline_lbl.bind(width=lambda w, val: setattr(w, 'text_size', (val, None)))
        tagline_lbl.bind(texture_size=lambda w, s: setattr(w, "height", min(s[1], dp(34)))) # Caps height so long text doesn't stretch the card
        text_col.add_widget(tagline_lbl)
        self.add_widget(text_col)
        
        # 3. Right: Version Number
        right_col = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(40))
        right_col.add_widget(Widget()) # Spacer to push text to middle
        right_col.add_widget(Label(text=f"v{item.get('version','?')}", font_size=sp(11), color=C_TEAL, bold=True, halign="right", size_hint_y=None, height=dp(20)))
        right_col.add_widget(Widget()) # Spacer to push text to middle
        self.add_widget(right_col)
        
        # Bind the touch event
        self.bind(on_touch_down=self._touch)
        
    def _touch(self, widget, touch):
        if self.collide_point(*touch.pos): 
            self._on_tap(self._item)


class StoreCatalogScreen(StoreScreenWithNav):
    nav_tab = "Store"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.all_apps = []
        self.current_category = "All"
        self.search_query = ""

    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        
        # 1. Header
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(16), 0])
        make_bg(header, C_SURFACE)
        header.add_widget(Label(text="App Store", font_size=sp(18), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(32), None)))
        layout.add_widget(header)

        # 2. Search Bar
        search_box = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(16), dp(8), dp(16), dp(8)])
        self.search_input = SHVTextInput(hint_text="Search apps...", multiline=False, height=dp(44))
        self.search_input.bind(text=self._on_search_text)
        search_box.add_widget(self.search_input)
        layout.add_widget(search_box)

        # 3. Category Chips (Horizontal Scroll)
        cat_scroll = ScrollView(size_hint_y=None, height=dp(50), do_scroll_y=False, do_scroll_x=True)
        self.cat_box = BoxLayout(orientation="horizontal", size_hint_x=None, padding=[dp(16), dp(8)], spacing=dp(10))
        self.cat_box.bind(minimum_width=self.cat_box.setter("width"))
        cat_scroll.add_widget(self.cat_box)
        layout.add_widget(cat_scroll)

        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        
        # 4. App Grid
        scroll = ScrollView()
        self.grid = GridLayout(cols=1, padding=[dp(10), dp(10)], spacing=dp(10), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.grid.add_widget(SHVLabel(text="Loading apps...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.grid); layout.add_widget(scroll)
        
        return layout

    def on_enter(self): 
        super().on_enter()
        threading.Thread(target=self._load_apps, daemon=True).start()

    def _load_apps(self):
        resp, status = supabase.select_filtered("apps", {"is_published": "eq.true"}, order="created_at.desc")
        def _main(*_):
            if status == 200 and isinstance(resp, list):
                self.all_apps = resp
                self._build_categories()
                self._apply_filters()
            else:
                self.grid.clear_widgets()
                self.grid.add_widget(SHVLabel(text="Failed to load apps.", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        Clock.schedule_once(_main)

    def _build_categories(self):
        self.cat_box.clear_widgets()
        # Automatically extract unique categories from your database items
        cats = ["All"] + sorted(list(set(app.get("category", "Utility") for app in self.all_apps if app.get("category"))))
        
        for cat in cats:
            btn = Button(text=cat, font_size=sp(12), bold=True, size_hint_x=None, width=dp(80), height=dp(34), size_hint_y=None)
            btn.bind(texture_size=lambda w, s: setattr(w, "width", s[0] + dp(32))) # Auto-adjust width to text
            
            is_active = (cat == self.current_category)
            btn.color = C_BG if is_active else C_TEXT_SEC
            btn.background_color = (0,0,0,0)
            
            # Draw pill-shaped background
            with btn.canvas.before:
                Color(*(C_TEAL if is_active else C_CARD2))
                btn._bg_rect = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(17)])
            def _upd(w, *_): w._bg_rect.pos, w._bg_rect.size = w.pos, w.size
            btn.bind(pos=_upd, size=_upd)
            
            btn.bind(on_release=lambda w, c=cat: self._on_cat_select(c))
            self.cat_box.add_widget(btn)

    def _on_cat_select(self, category):
        self.current_category = category
        self._build_categories() # Re-render to update the teal active color
        self._apply_filters()

    def _on_search_text(self, widget, text):
        self.search_query = text.lower()
        self._apply_filters()

    def _apply_filters(self):
        self.grid.clear_widgets()
        filtered = []
        for app in self.all_apps:
            matches_cat = (self.current_category == "All" or app.get("category", "") == self.current_category)
            matches_search = (self.search_query in app.get("name", "").lower() or self.search_query in app.get("tagline", "").lower())
            
            if matches_cat and matches_search:
                filtered.append(app)
        
        if not filtered:
            self.grid.add_widget(SHVLabel(text="No apps match your search.", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        else:
            for item in filtered:
                self.grid.add_widget(AppTile(item, on_tap=self._open_detail))

    def _open_detail(self, item):
        App.get_running_app().current_app_detail = item; self.manager.current = "store_app_detail"





class StoreUpdateCard(SHVCard):
    def __init__(self, item, **kwargs):
        super().__init__(size_hint_y=None, **kwargs)
        status = item.get("status", "planned"); scol = {"planned": C_SLATE, "in_progress": get_color_from_hex("#F9A825"), "released": C_TEAL}.get(status, C_SLATE)
        top_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
        top_row.add_widget(SHVLabel(text=item.get("app_name",""), font_size=sp(10), color=C_TEXT_SEC, size_hint_y=None, height=dp(18)))
        top_row.add_widget(Widget())
        top_row.add_widget(Label(text=f"  {status.title()}  ", font_size=sp(9), bold=True, color=scol, size_hint_x=None, width=dp(80)))
        self.add_widget(top_row); self.add_widget(SHVLabel(text=item.get("title",""), font_size=sp(14), bold=True, color=C_TEXT, size_hint_y=None, height=dp(24)))
        if item.get("description"):
            desc_lbl = Label(text=item["description"], font_size=sp(11), color=C_TEXT_SEC, size_hint_y=None, halign="left", valign="top", text_size=(Window.width - dp(64), None))
            desc_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1])); self.add_widget(desc_lbl)
        meta_row = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(16))
        if item.get("target_version"): meta_row.add_widget(SHVLabel(text=f"Target: v{item['target_version']}", font_size=sp(10), color=C_TEAL, size_hint_y=None, height=dp(18)))
        if item.get("expected_date"): meta_row.add_widget(SHVLabel(text=f"ETA: {item['expected_date']}", font_size=sp(10), color=C_TEXT_SEC, size_hint_y=None, height=dp(18)))
        self.add_widget(meta_row); self.bind(minimum_height=self.setter("height"))

class StoreUpdatesScreen(StoreScreenWithNav):
    nav_tab = "Updates"
    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(16), 0]); make_bg(header, C_SURFACE)
        header.add_widget(Label(text="Upcoming Updates", font_size=sp(17), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(32), None)))
        layout.add_widget(header)
        self.status = StatusBar(size_hint_x=1); layout.add_widget(self.status)
        scroll = ScrollView()
        self.feed = BoxLayout(orientation="vertical", padding=[dp(12), dp(12)], spacing=dp(10), size_hint_y=None)
        self.feed.bind(minimum_height=self.feed.setter("height"))
        self.feed.add_widget(SHVLabel(text="Loading...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.feed); layout.add_widget(scroll)
        return layout
    def on_enter(self): super().on_enter(); threading.Thread(target=self._load, daemon=True).start()
    def _load(self):
        resp, status = supabase.select_filtered("upcoming_updates", {}, order="created_at.desc")
        def _main(*_):
            self.feed.clear_widgets()
            if status == 200 and isinstance(resp, list) and resp:
                for item in resp: self.feed.add_widget(StoreUpdateCard(item))
        Clock.schedule_once(_main)

class AccountScreen(StoreScreenWithNav):
    nav_tab = "Account"
    def build_body(self):
        layout = BoxLayout(orientation="vertical")
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(16), 0]); make_bg(header, C_SURFACE)
        header.add_widget(Label(text="My Account", font_size=sp(18), bold=True, color=C_TEXT, halign="left", text_size=(Window.width - dp(32), None)))
        layout.add_widget(header)
        scroll = ScrollView()
        self.content = BoxLayout(orientation="vertical", padding=[dp(16), dp(16)], spacing=dp(12), size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter("height"))
        self.content.add_widget(SHVLabel(text="Loading profile...", color=C_TEXT_SEC, size_hint_y=None, height=dp(40), halign="center"))
        scroll.add_widget(self.content); self.acct_status = StatusBar(size_hint_x=1)
        layout.add_widget(self.acct_status); layout.add_widget(scroll)
        return layout
    def on_enter(self): super().on_enter(); threading.Thread(target=self._load_profile, daemon=True).start()
    def _load_profile(self):
        profile = supabase.get_profile()
        def _main(*_):
            self.content.clear_widgets()
            if profile is None: self.acct_status.show("Could not load profile", duration=4)
            avatar_row = BoxLayout(size_hint_y=None, height=dp(80), spacing=dp(16))
            avatar_row.add_widget(Label(text="👤", font_size=sp(48), size_hint_x=None, width=dp(72), font_name=FONT_PATH))
            name_col = BoxLayout(orientation="vertical", spacing=dp(4))
            name_col.add_widget(SHVLabel(text=(profile.get("display_name","") if profile else "") or "SHV User", font_size=sp(18), bold=True, size_hint_y=None, height=dp(28)))
            name_col.add_widget(SHVLabel(text=supabase.user_email or "", font_size=sp(12), color=C_TEXT_SEC, size_hint_y=None, height=dp(20)))
            avatar_row.add_widget(name_col); self.content.add_widget(avatar_row)
            div = Widget(size_hint_y=None, height=dp(1)); make_bg(div, C_DIVIDER); self.content.add_widget(div)
            self.content.add_widget(SHVLabel(text="Account Info", font_size=sp(13), bold=True, color=C_TEAL, size_hint_y=None, height=dp(24)))
            for k, v in [("User ID", supabase.user_id or "—"), ("Admin Access", "Yes" if (profile or {}).get("is_admin") else "No")]:
                row = SHVCard(color=C_CARD2, size_hint_y=None, height=dp(52), orientation="horizontal", padding=[dp(12), 0])
                row.add_widget(SHVLabel(text=k, color=C_TEXT_SEC, font_size=sp(12), size_hint_x=0.4, size_hint_y=None, height=dp(52)))
                row.add_widget(SHVLabel(text=str(v), font_size=sp(12), size_hint_x=0.6, size_hint_y=None, height=dp(52)))
                self.content.add_widget(row)
            self.content.add_widget(Widget(size_hint_y=None, height=dp(16)))
            signout_btn = SHVButton(text="Sign Out", primary=False); signout_btn.color = C_ROSE
            signout_btn.bind(on_release=lambda _: (supabase.sign_out(), setattr(self.manager, "current", "hub")))
            self.content.add_widget(signout_btn); self.content.add_widget(Widget(size_hint_y=None, height=dp(12)))
            self.content.add_widget(Label(text=f"SH Vertex Technologies  •  SHV Store v{APP_VERSION}", font_size=sp(10), color=C_TEXT_HINT, size_hint_y=None, height=dp(20)))
        Clock.schedule_once(_main)


# ─────────────────────────────────────────────
#  THE MAIN HUB SCREEN
# ─────────────────────────────────────────────
class HubScreen(Screen):
    def on_enter(self):
        self.clear_widgets()
        root = FloatLayout()
        make_bg(root, C_BG)

        box = BoxLayout(
            orientation="vertical", 
            size_hint=(0.8, None), 
            height=dp(340), 
            spacing=dp(20), 
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )

        # Branding
        brand = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(80))
        brand.add_widget(Label(text="SHV", font_size=sp(48), bold=True, color=C_TEAL))
        brand.add_widget(Label(text="MASTER HUB", font_size=sp(12), color=C_TEXT_SEC))
        box.add_widget(brand)
        box.add_widget(spacer(20))

        # Admin App Button
        btn_admin = SHVButton(text="SH Vertex Admin", primary=True)
        btn_admin.bind(on_release=lambda _: setattr(self.manager, "current", "admin_login"))
        box.add_widget(btn_admin)

        # Store App Button
        btn_store = SHVButton(text="SH Vertex Customer", primary=True)
        btn_store.bind(on_release=lambda _: setattr(self.manager, "current", "store_login"))
        box.add_widget(btn_store)

        box.add_widget(spacer(20))

        # --- THE FIXED EXIT BUTTON ---
        # Using BBCode markup to force the emoji font only on the icon
        btn_exit = SHVButton(
            text=f"[font={FONT_PATH}]🚪[/font] Exit Hub", 
            primary=False,
            markup=True
        )
        
        btn_exit.color = C_ROSE
        btn_exit.bind(on_release=lambda _: App.get_running_app().show_exit_confirm())
        
        # Redraw the button red background
        btn_exit.canvas.before.clear()
        with btn_exit.canvas.before:
            Color(*C_ROSE)
            btn_exit._rect = RoundedRectangle(pos=btn_exit.pos, size=btn_exit.size, radius=[dp(10)])
        
        def _upd_exit(*_):
            btn_exit._rect.pos  = btn_exit.pos
            btn_exit._rect.size = btn_exit.size
            
        btn_exit.bind(pos=_upd_exit, size=_upd_exit)
        btn_exit.color = C_TEXT
        
        box.add_widget(btn_exit)
        root.add_widget(box)
        self.add_widget(root)


# ─────────────────────────────────────────────
#  MASTER APP RUNNER
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
#  MASTER APP RUNNER
# ─────────────────────────────────────────────
class SHVMasterHubApp(App):
    def build(self):
        Window.clearcolor = C_BG
        self.title = "SHV Master Hub"
        
        # Shared app memory
        self.current_app_detail = {} # Used by Store side
        self.edit_item = None        # Used by Admin side

        sm = ScreenManager(transition=NoTransition())
        self.sm = sm

        # 1. The Hub
        sm.add_widget(HubScreen(name="hub"))

        # 2. Admin Screens
        sm.add_widget(AdminLoginScreen(name="admin_login"))
        sm.add_widget(DashboardScreen(name="admin_dashboard"))
        sm.add_widget(AppsScreen(name="admin_apps"))
        sm.add_widget(AppFormScreen(name="admin_app_form"))
        sm.add_widget(NewsScreen(name="admin_news"))
        sm.add_widget(NewsFormScreen(name="admin_news_form"))
        sm.add_widget(AdminUpdatesScreen(name="admin_updates"))
        sm.add_widget(UpdateFormScreen(name="admin_update_form"))
        sm.add_widget(AdminContactScreen(name="admin_contact"))
        sm.add_widget(AdminBroadcastFormScreen(name="admin_broadcast_form"))
        sm.add_widget(AdminBroadcastsScreen(name="admin_broadcasts_list"))
        sm.add_widget(AdminStoreUpdateFormScreen(name="admin_store_update_form"))

        # 3. Store Screens
        sm.add_widget(StoreLoginScreen(name="store_login"))
        sm.add_widget(RegisterScreen(name="store_register"))
        sm.add_widget(StoreHomeScreen(name="store_home"))
        sm.add_widget(StoreInboxScreen(name="store_inbox"))
        sm.add_widget(StoreCatalogScreen(name="store_catalog"))
        sm.add_widget(AppDetailScreen(name="store_app_detail"))
        sm.add_widget(StoreUpdatesScreen(name="store_updates"))
        sm.add_widget(AccountScreen(name="store_account"))

        # Start on Hub
        sm.current = "hub"
        Window.bind(on_request_close=self.on_request_close)
        Window.bind(on_keyboard=self.on_keyboard)

        root_container = FloatLayout()
        root_container.add_widget(sm)
        return root_container

    def on_keyboard(self, window, key, *args):
        if key == 27: # 27 is the Android Back Button
            # Map of sub-screens to their parent screens
            back_map = {
                "store_register": "store_login",
                "store_inbox": "store_home",
                "store_app_detail": "store_catalog",
                "admin_app_form": "admin_apps",
                "admin_news_form": "admin_news",
                "admin_update_form": "admin_updates",
                "admin_broadcast_form": "admin_dashboard",
                "admin_broadcasts_list": "admin_dashboard",
                "admin_store_update_form": "admin_dashboard"
            }
            
            current_screen = self.sm.current
            
            if current_screen in back_map:
                # Go back to the parent screen
                self.sm.current = back_map[current_screen]
            else:
                # Top-level screen, ask to exit
                self.show_exit_confirm()
            return True
        return False

    def on_request_close(self, *args, **kwargs):
        self.show_exit_confirm()
        return True

    def show_exit_confirm(self):
        if hasattr(self, "_exit_overlay") and self._exit_overlay: return
        overlay = ExitOverlay(on_confirm=self._do_exit, on_cancel=self._cancel_exit)
        overlay.size = Window.size
        self._exit_overlay = overlay
        self.root.add_widget(overlay)

    def _do_exit(self):
        self._remove_overlay()
        self.stop()

    def _cancel_exit(self):
        self._remove_overlay()

    def _remove_overlay(self):
        if hasattr(self, "_exit_overlay") and self._exit_overlay:
            try: self.root.remove_widget(self._exit_overlay)
            except Exception: pass
            self._exit_overlay = None



# --- THESE ARE THE CRITICAL LAST TWO LINES ---
if __name__ == "__main__":
    SHVMasterHubApp().run()
