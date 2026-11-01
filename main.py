from kivy.app import App
from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.utils import platform

if platform == "android":
    from android.permissions import Permission, check_permission, request_permissions
    from jnius import autoclass

    from android_camera import CameraRecorder

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    REQUIRED_PERMISSIONS = [Permission.CAMERA, Permission.RECORD_AUDIO]

KEY_BACK = 27


class GiocoApp(App):
    title = "Gioco"

    def build(self):
        self._camera = None
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))
        self._status = Label(halign="center", valign="middle")
        self._status.bind(size=lambda label, size: setattr(label, "text_size", size))
        self._open_button = Button(text="Apri fotocamera", size_hint_y=None, height=dp(64))
        self._open_button.bind(on_release=self._on_open_pressed)
        root.add_widget(self._status)
        root.add_widget(self._open_button)

        if platform == "android":
            self._camera = CameraRecorder(on_status=self.set_status)
            self.set_status(f"I video vengono salvati in\n{self._camera.output_dir}")
        else:
            self._open_button.disabled = True
            self.set_status("La fotocamera funziona solo su Android")

        Window.bind(on_keyboard=self._on_keyboard)
        return root

    @mainthread
    def set_status(self, text):
        self._status.text = text

    def _on_open_pressed(self, *_):
        if self._camera is None:
            return
        if all(check_permission(p) for p in REQUIRED_PERMISSIONS):
            self._camera.open()
        else:
            request_permissions(REQUIRED_PERMISSIONS, self._on_permissions_result)

    def _on_permissions_result(self, permissions, grant_results):
        # Lista vuota se l'utente chiude il dialogo senza scegliere.
        if grant_results and all(grant_results):
            self._camera.open()
            return
        denied = [p for p, granted in zip(permissions, grant_results) if not granted] or list(permissions)
        names = ", ".join(p.rsplit(".", 1)[-1] for p in denied)
        self.set_status(f"Permessi negati: {names}")

    def _on_keyboard(self, window, key, *args):
        if key != KEY_BACK:
            return False
        if self._camera is not None and self._camera.is_open:
            self._camera.close()
            return True
        if platform == "android":
            PythonActivity.mActivity.moveTaskToBack(True)
            return True
        return False

    def on_pause(self):
        if self._camera is not None:
            self._camera.close()
        return True

    def on_stop(self):
        if self._camera is not None:
            self._camera.close()


if __name__ == "__main__":
    GiocoApp().run()
