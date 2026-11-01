import os
import time
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.graphics import Callback, Color, Ellipse, Fbo, Line, Rectangle, RoundedRectangle
from kivy.graphics.opengl import glActiveTexture, glBindTexture, glDeleteTextures, glGenTextures
from kivy.graphics.transformation import Matrix
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.properties import BooleanProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.utils import platform

IS_ANDROID = platform == "android"

if IS_ANDROID:
    from android.permissions import Permission, check_permission, request_permissions
    from jnius import JavaException, autoclass, cast

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Camera = autoclass("android.hardware.Camera")
    CameraInfo = autoclass("android.hardware.Camera$CameraInfo")
    CameraSize = autoclass("android.hardware.Camera$Size")
    CamcorderProfile = autoclass("android.media.CamcorderProfile")
    MediaRecorder = autoclass("android.media.MediaRecorder")
    AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
    VideoSource = autoclass("android.media.MediaRecorder$VideoSource")
    OutputFormat = autoclass("android.media.MediaRecorder$OutputFormat")
    VideoEncoder = autoclass("android.media.MediaRecorder$VideoEncoder")
    AudioEncoder = autoclass("android.media.MediaRecorder$AudioEncoder")
    Environment = autoclass("android.os.Environment")
    SurfaceTexture = autoclass("android.graphics.SurfaceTexture")
    JAVA_ERRORS = (JavaException,)
else:
    JAVA_ERRORS = ()

GL_TEXTURE0 = 0x84C0
GL_TEXTURE_EXTERNAL_OES = 0x8D65
CAMERA_TEXTURE_UNIT = 1

FOCUS_CONTINUOUS_VIDEO = "continuous-video"
AUDIO_BIT_RATE = 128_000
AUDIO_SAMPLE_RATE = 44_100

MODE_IDLE = "idle"
MODE_VIDEO = "video"
MODE_AUDIO = "audio"

KEY_BACK = 27
BAR_HEIGHT_DP = 150
RECORD_RED = (0.92, 0.16, 0.16, 1)
GLYPHS = ("photo", "video", "audio")

VALID_ROTATIONS = (0, 90, 180, 270)
SURFACE_ROTATION_DEGREES = {0: 0, 1: 90, 2: 180, 3: 270}
ASPECT_TOLERANCE = 0.01

# La texture della fotocamera è GL_TEXTURE_EXTERNAL_OES: un sampler2D non la legge.
PREVIEW_FRAGMENT_SHADER = """
#extension GL_OES_EGL_image_external : require
#ifdef GL_ES
    precision highp float;
#endif

varying vec4 frag_color;
varying vec2 tex_coord0;

uniform samplerExternalOES camera_texture;
uniform mat4 st_matrix;

void main()
{
    vec2 coord = (st_matrix * vec4(tex_coord0, 0.0, 1.0)).xy;
    gl_FragColor = texture2D(camera_texture, coord);
}
"""

Size = tuple[int, int]


class CameraError(ValueError):
    pass


CAMERA_ERRORS = JAVA_ERRORS + (ValueError,)


def _area(size: Size) -> int:
    return size[0] * size[1]


def _aspect(size: Size) -> float:
    return size[0] / size[1]


def _check_rotation(value: int) -> None:
    if value not in VALID_ROTATIONS:
        raise ValueError(f"rotazione non valida: {value}")


def choose_size(target: Size, candidates: list[Size]) -> Size:
    if not candidates:
        raise ValueError("nessuna dimensione supportata dalla fotocamera")
    if target in candidates:
        return target
    same_aspect = [s for s in candidates if abs(_aspect(s) - _aspect(target)) <= ASPECT_TOLERANCE]
    pool = same_aspect or candidates
    not_larger = [s for s in pool if _area(s) <= _area(target)]
    if not_larger:
        return max(not_larger, key=_area)
    return min(pool, key=_area)


def choose_preview_size(video_size: Size, preview_sizes: list[Size], preferred: Size | None) -> Size:
    if video_size in preview_sizes:
        return video_size
    if preferred is not None and preferred in preview_sizes:
        return preferred
    return choose_size(video_size, preview_sizes)


def orientation_hint(sensor_degrees: int, display_degrees: int) -> int:
    _check_rotation(sensor_degrees)
    _check_rotation(display_degrees)
    return (sensor_degrees - display_degrees) % 360


def surface_rotation_to_degrees(rotation: int) -> int:
    if rotation not in SURFACE_ROTATION_DEGREES:
        raise ValueError(f"costante Surface.ROTATION sconosciuta: {rotation}")
    return SURFACE_ROTATION_DEGREES[rotation]


def rotated_size(size: Size, rotation: int) -> Size:
    _check_rotation(rotation)
    if rotation in (90, 270):
        return size[1], size[0]
    return size


def cover_tex_coords(content: Size, box: Size) -> tuple[float, float, float, float]:
    if min(*content, *box) <= 0:
        raise ValueError(f"dimensioni non positive: contenuto={content} area={box}")
    content_aspect = _aspect(content)
    box_aspect = box[0] / box[1]
    if content_aspect > box_aspect:
        visible = box_aspect / content_aspect
        start = (1.0 - visible) / 2.0
        return start, 0.0, start + visible, 1.0
    visible = content_aspect / box_aspect
    start = (1.0 - visible) / 2.0
    return 0.0, start, 1.0, start + visible


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def media_filename(prefix: str, extension: str, moment: datetime) -> str:
    # I millisecondi evitano che due foto nello stesso secondo si sovrascrivano.
    return f"{prefix}_{moment:%Y%m%d_%H%M%S}_{moment.microsecond // 1000:03d}.{extension}"


def _remove_file(path: str | None) -> None:
    if path is None:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError:
        Logger.exception(f"Camera: impossibile eliminare {path}")


def _size_tuple(size) -> Size:
    return int(size.width), int(size.height)


def _java_sizes(java_list) -> list[Size]:
    if java_list is None:
        return []
    return [_size_tuple(cast(CameraSize, java_list.get(i))) for i in range(java_list.size())]


def _java_strings(java_list) -> list[str]:
    if java_list is None:
        return []
    items = []
    for i in range(java_list.size()):
        item = java_list.get(i)
        items.append(item if isinstance(item, str) else item.toString())
    return items


def _app_dir(activity, kind) -> str:
    directory = activity.getExternalFilesDir(kind)
    if directory is None:
        directory = activity.getFilesDir()
    path = directory.getAbsolutePath()
    os.makedirs(path, exist_ok=True)
    return path


def _stop_recorder(recorder) -> bool:
    saved = True
    try:
        recorder.stop()
    except JAVA_ERRORS:
        # MediaRecorder.stop lancia RuntimeException se non ha ricevuto dati validi.
        Logger.exception("Camera: stop registrazione fallito")
        saved = False
    try:
        recorder.reset()
        recorder.release()
    except JAVA_ERRORS:
        Logger.exception("Camera: rilascio MediaRecorder fallito")
    return saved


class CameraBackend:
    """Fotocamera, MediaRecorder e texture GL vivono tutti sul thread di Kivy, che possiede il contesto GL."""

    def __init__(self, on_frame):
        self._on_frame = on_frame
        activity = PythonActivity.mActivity
        self.photo_dir = _app_dir(activity, Environment.DIRECTORY_PICTURES)
        self.video_dir = _app_dir(activity, Environment.DIRECTORY_MOVIES)
        self.audio_dir = _app_dir(activity, Environment.DIRECTORY_MUSIC)
        self._camera = None
        self._profile = None
        self._video_size = None
        self._rotation = 0
        self.content_size = None
        self._tex_id = None
        self._surface_texture = None
        self._fbo = None
        # Lista Python: pyjnius ci ricopia dentro il float[] scritto da getTransformMatrix.
        self._st_values = [0.0] * 16
        self._last_st_values = None
        self._video_recorder = None
        self._video_path = None
        self._audio_recorder = None
        self._audio_path = None

    @property
    def is_open(self) -> bool:
        return self._camera is not None

    @property
    def texture(self):
        return self._fbo.texture if self._fbo is not None else None

    def open(self):
        if self._camera is not None:
            return
        try:
            self._open_camera()
            self._create_gl_pipeline()
            self._camera.setPreviewTexture(self._surface_texture)
            self._camera.startPreview()
        except CAMERA_ERRORS:
            self.close()
            raise
        Clock.schedule_interval(self._tick, 0)

    def close(self):
        Clock.unschedule(self._tick)
        if self._video_recorder is not None:
            self.stop_video()
        if self._camera is not None:
            camera = self._camera
            self._camera = None
            try:
                camera.stopPreview()
                camera.release()
            except JAVA_ERRORS:
                Logger.exception("Camera: rilascio fotocamera fallito")
        if self._surface_texture is not None:
            self._surface_texture.release()
            self._surface_texture = None
        if self._tex_id is not None:
            glDeleteTextures([self._tex_id])
            self._tex_id = None
        self._fbo = None
        self._last_st_values = None

    def _find_back_camera(self) -> tuple[int, int]:
        info = CameraInfo()
        for camera_id in range(Camera.getNumberOfCameras()):
            Camera.getCameraInfo(camera_id, info)
            if info.facing == CameraInfo.CAMERA_FACING_BACK:
                return camera_id, int(info.orientation)
        raise CameraError("nessuna fotocamera posteriore trovata")

    def _open_camera(self):
        camera_id, sensor_degrees = self._find_back_camera()
        self._camera = Camera.open(camera_id)
        params = self._camera.getParameters()

        profile = CamcorderProfile.get(camera_id, CamcorderProfile.QUALITY_HIGH)
        preview_sizes = _java_sizes(params.getSupportedPreviewSizes())
        video_sizes = _java_sizes(params.getSupportedVideoSizes()) or preview_sizes
        video_size = choose_size((int(profile.videoFrameWidth), int(profile.videoFrameHeight)), video_sizes)
        preferred = params.getPreferredPreviewSizeForVideo()
        preferred_size = _size_tuple(preferred) if preferred is not None else None
        preview_size = choose_preview_size(video_size, preview_sizes, preferred_size)

        params.setPreviewSize(preview_size[0], preview_size[1])
        params.setRecordingHint(True)
        if FOCUS_CONTINUOUS_VIDEO in _java_strings(params.getSupportedFocusModes()):
            params.setFocusMode(FOCUS_CONTINUOUS_VIDEO)
        self._camera.setParameters(params)

        display = PythonActivity.mActivity.getWindowManager().getDefaultDisplay()
        rotation = orientation_hint(sensor_degrees, surface_rotation_to_degrees(display.getRotation()))
        # Su SurfaceTexture la rotazione arriva nella matrice di getTransformMatrix, applicata dallo shader.
        self._camera.setDisplayOrientation(rotation)

        self._profile = profile
        self._video_size = video_size
        self._rotation = rotation
        self.content_size = rotated_size(preview_size, rotation)
        Logger.info(f"Camera: id={camera_id} video={video_size} anteprima={preview_size} rotazione={rotation}")

    def _create_gl_pipeline(self):
        width, height = self.content_size
        self._tex_id = int(glGenTextures(1)[0])
        self._surface_texture = SurfaceTexture(self._tex_id)
        fbo = Fbo(size=(width, height))
        fbo.shader.fs = PREVIEW_FRAGMENT_SHADER
        if not fbo.shader.success:
            raise CameraError("shader dell'anteprima non compilato: GL_OES_EGL_image_external non disponibile")
        with fbo:
            Callback(self._bind_camera_texture)
            Rectangle(size=(width, height))
        fbo["camera_texture"] = CAMERA_TEXTURE_UNIT
        fbo["st_matrix"] = Matrix()
        self._fbo = fbo

    def _bind_camera_texture(self, instruction):
        glActiveTexture(GL_TEXTURE0 + CAMERA_TEXTURE_UNIT)
        glBindTexture(GL_TEXTURE_EXTERNAL_OES, self._tex_id)
        glActiveTexture(GL_TEXTURE0)

    def _tick(self, dt):
        if self._surface_texture is None or self._fbo is None:
            return False
        try:
            self._surface_texture.updateTexImage()
            self._surface_texture.getTransformMatrix(self._st_values)
        except JAVA_ERRORS:
            Logger.exception("Camera: aggiornamento texture fallito")
            return None
        if any(self._st_values) and self._st_values != self._last_st_values:
            self._last_st_values = list(self._st_values)
            # Kivy carica una uniform solo se l'oggetto cambia: serve una Matrix nuova.
            matrix = Matrix()
            matrix.set(flat=self._last_st_values)
            self._fbo["st_matrix"] = matrix
        self._fbo.ask_update()
        self._fbo.draw()
        self._on_frame()
        return None

    def take_photo(self, path: str):
        if self._fbo is None:
            raise CameraError("fotocamera non aperta")
        self._fbo.texture.save(path, flipped=False)

    def _relock_camera(self):
        if self._camera is None:
            return
        try:
            self._camera.lock()
            self._camera.startPreview()
        except JAVA_ERRORS:
            Logger.exception("Camera: ripresa del controllo della fotocamera fallita")

    def start_video(self, path: str):
        if self._camera is None:
            raise CameraError("fotocamera non aperta")
        profile = self._profile
        recorder = MediaRecorder()
        try:
            self._camera.unlock()
            recorder.setCamera(self._camera)
            recorder.setAudioSource(AudioSource.CAMCORDER)
            recorder.setVideoSource(VideoSource.CAMERA)
            recorder.setOutputFormat(OutputFormat.MPEG_4)
            recorder.setVideoEncoder(VideoEncoder.H264)
            recorder.setAudioEncoder(AudioEncoder.AAC)
            recorder.setVideoSize(self._video_size[0], self._video_size[1])
            recorder.setVideoFrameRate(profile.videoFrameRate)
            recorder.setVideoEncodingBitRate(profile.videoBitRate)
            recorder.setAudioEncodingBitRate(profile.audioBitRate)
            recorder.setAudioChannels(profile.audioChannels)
            recorder.setAudioSamplingRate(profile.audioSampleRate)
            recorder.setOrientationHint(self._rotation)
            recorder.setOutputFile(path)
            recorder.prepare()
            recorder.start()
        except JAVA_ERRORS:
            recorder.reset()
            recorder.release()
            self._relock_camera()
            _remove_file(path)
            raise
        self._video_recorder = recorder
        self._video_path = path

    def stop_video(self) -> tuple[bool, str]:
        recorder, path = self._video_recorder, self._video_path
        self._video_recorder = None
        self._video_path = None
        saved = _stop_recorder(recorder)
        self._relock_camera()
        if not saved:
            _remove_file(path)
        return saved, path

    def start_audio(self, path: str):
        recorder = MediaRecorder()
        try:
            recorder.setAudioSource(AudioSource.MIC)
            recorder.setOutputFormat(OutputFormat.MPEG_4)
            recorder.setAudioEncoder(AudioEncoder.AAC)
            recorder.setAudioEncodingBitRate(AUDIO_BIT_RATE)
            recorder.setAudioSamplingRate(AUDIO_SAMPLE_RATE)
            recorder.setAudioChannels(1)
            recorder.setOutputFile(path)
            recorder.prepare()
            recorder.start()
        except JAVA_ERRORS:
            recorder.reset()
            recorder.release()
            _remove_file(path)
            raise
        self._audio_recorder = recorder
        self._audio_path = path

    def stop_audio(self) -> tuple[bool, str]:
        recorder, path = self._audio_recorder, self._audio_path
        self._audio_recorder = None
        self._audio_path = None
        saved = _stop_recorder(recorder)
        if not saved:
            _remove_file(path)
        return saved, path


class CameraPreview(Widget):
    def __init__(self, on_tap, **kwargs):
        super().__init__(**kwargs)
        self._on_tap = on_tap
        self._content_size = None
        with self.canvas:
            Color(0, 0, 0, 1)
            self._background = Rectangle()
            self._frame_color = Color(1, 1, 1, 0)
            self._frame = Rectangle()
            self._flash_color = Color(1, 1, 1, 0)
            self._flash = Rectangle()
        self._message = Label(halign="center", valign="middle", font_size="16sp")
        self.add_widget(self._message)
        self.bind(pos=self._relayout, size=self._relayout)

    def set_source(self, texture, content_size):
        self._content_size = content_size
        self._frame.texture = texture
        self._frame_color.a = 1
        self._message.text = ""
        self._relayout()

    def clear_source(self):
        self._content_size = None
        self._frame.texture = None
        self._frame_color.a = 0

    def show_message(self, text):
        self.clear_source()
        self._message.text = text

    def refresh(self):
        self.canvas.ask_update()

    def flash(self):
        self._flash_color.a = 0.75
        Clock.schedule_once(lambda dt: setattr(self._flash_color, "a", 0), 0.12)

    def _relayout(self, *_):
        for rect in (self._background, self._frame, self._flash):
            rect.pos = self.pos
            rect.size = self.size
        self._message.pos = self.pos
        self._message.size = self.size
        self._message.text_size = (self.width * 0.85, None)
        if self._content_size is not None and self.width > 0 and self.height > 0:
            u0, v0, u1, v1 = cover_tex_coords(self._content_size, (self.width, self.height))
            self._frame.tex_coords = (u0, v0, u1, v0, u1, v1, u0, v1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_tap()
            return True
        return super().on_touch_down(touch)


class RoundButton(ButtonBehavior, Widget):
    active = BooleanProperty(False)

    def __init__(self, glyph, **kwargs):
        if glyph not in GLYPHS:
            raise ValueError(f"glifo sconosciuto: {glyph}")
        super().__init__(**kwargs)
        self.glyph = glyph
        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw, active=self._redraw, disabled=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.opacity = 0.35 if self.disabled else 1.0
        cx, cy = self.center
        radius = min(self.size) / 2.0
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 0.3 if self.state == "down" else 0.12)
            Ellipse(pos=(cx - radius, cy - radius), size=(radius * 2, radius * 2))
            Color(1, 1, 1, 1)
            Line(circle=(cx, cy, radius - dp(2)), width=dp(2))
            if self.active:
                self._draw_stop(cx, cy, radius)
            elif self.glyph == "photo":
                self._draw_disc(cx, cy, radius * 0.62, (1, 1, 1, 1))
            elif self.glyph == "video":
                self._draw_disc(cx, cy, radius * 0.6, RECORD_RED)
            else:
                self._draw_microphone(cx, cy, radius)

    def _draw_disc(self, cx, cy, r, rgba):
        Color(*rgba)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))

    def _draw_stop(self, cx, cy, radius):
        side = radius * 0.72
        Color(*RECORD_RED)
        RoundedRectangle(pos=(cx - side / 2, cy - side / 2), size=(side, side), radius=[dp(6)])

    def _draw_microphone(self, cx, cy, radius):
        Color(1, 1, 1, 1)
        mic_w = radius * 0.36
        mic_h = radius * 0.62
        mic_bottom = cy - radius * 0.18
        RoundedRectangle(pos=(cx - mic_w / 2, mic_bottom), size=(mic_w, mic_h), radius=[mic_w / 2])
        arc_cy = mic_bottom + mic_w / 2
        arc_r = mic_w / 2 + radius * 0.12
        Line(circle=(cx, arc_cy, arc_r, 90, 270), width=dp(1.6))
        stem_top = arc_cy - arc_r
        stem_bottom = stem_top - radius * 0.14
        Line(points=[cx, stem_top, cx, stem_bottom], width=dp(1.6))
        Line(points=[cx - radius * 0.15, stem_bottom, cx + radius * 0.15, stem_bottom], width=dp(1.6))


class BlinkDot(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._event = None
        with self.canvas:
            self._color = Color(*RECORD_RED)
            self._dot = Ellipse()
        self.bind(pos=self._relayout, size=self._relayout)

    def _relayout(self, *_):
        diameter = min(self.size)
        self._dot.size = (diameter, diameter)
        self._dot.pos = (self.center_x - diameter / 2, self.center_y - diameter / 2)

    def start(self):
        self.stop()
        self._event = Clock.schedule_interval(self._toggle, 0.5)

    def stop(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None
        self._color.a = 1

    def _toggle(self, dt):
        self._color.a = 0.0 if self._color.a > 0.5 else 1.0


class RecordingBadge(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint=(None, None),
            size=(dp(132), dp(40)),
            padding=(dp(14), dp(8)),
            spacing=dp(10),
            **kwargs,
        )
        with self.canvas.before:
            Color(0, 0, 0, 0.55)
            self._background = RoundedRectangle(radius=[dp(20)])
        self.bind(pos=self._relayout, size=self._relayout)
        self.dot = BlinkDot(size_hint=(None, 1), width=dp(14))
        self.time_label = Label(text=format_duration(0), font_size="18sp", bold=True)
        self.add_widget(self.dot)
        self.add_widget(self.time_label)
        self.opacity = 0

    def _relayout(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def show(self):
        self.set_elapsed(0)
        self.opacity = 1
        self.dot.start()

    def hide(self):
        self.dot.stop()
        self.opacity = 0

    def set_elapsed(self, seconds):
        self.time_label.text = format_duration(seconds)


class Toast(Label):
    def __init__(self, **kwargs):
        super().__init__(
            size_hint=(None, None),
            halign="center",
            valign="middle",
            font_size="14sp",
            padding=(dp(14), dp(10)),
            **kwargs,
        )
        self._hide_event = None
        with self.canvas.before:
            Color(0, 0, 0, 0.65)
            self._background = RoundedRectangle(radius=[dp(12)])
        self.bind(pos=self._relayout, size=self._relayout, texture_size=self._fit)
        self.opacity = 0

    def _relayout(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def _fit(self, *_):
        self.size = self.texture_size
        if self.parent is not None:
            self.center_x = self.parent.center_x

    def show(self, text, max_width, duration=3.5):
        self.text_size = (max_width, None)
        self.text = text
        self.opacity = 1
        self._fit()
        if self._hide_event is not None:
            self._hide_event.cancel()
        self._hide_event = Clock.schedule_once(self._hide, duration)

    def _hide(self, dt):
        self.opacity = 0
        self._hide_event = None


class GiocoCameraApp(App):
    title = "Gioco"

    def build(self):
        from kivy.core.window import Window

        self._window = Window
        Window.clearcolor = (0, 0, 0, 1)
        self._backend = None
        self._mode = MODE_IDLE
        self._record_started = 0.0
        self._timer_event = None
        self._camera_allowed = False
        self._mic_allowed = False

        root = FloatLayout()
        self._preview = CameraPreview(on_tap=self._on_preview_tap)
        root.add_widget(self._preview)

        top = AnchorLayout(anchor_x="center", anchor_y="top", padding=dp(20))
        self._badge = RecordingBadge()
        top.add_widget(self._badge)
        root.add_widget(top)

        self._toast = Toast()
        self._toast.y = dp(BAR_HEIGHT_DP) + dp(16)
        root.add_widget(self._toast)

        root.add_widget(self._build_bottom_bar())
        Window.bind(on_keyboard=self._on_keyboard)

        if IS_ANDROID:
            self._backend = CameraBackend(on_frame=self._preview.refresh)
        else:
            self._preview.show_message("Anteprima disponibile solo su Android")
        self._refresh_controls()
        return root

    def _build_bottom_bar(self):
        bar = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(BAR_HEIGHT_DP),
            pos_hint={"x": 0, "y": 0},
            padding=(dp(24), dp(12), dp(24), dp(18)),
        )
        with bar.canvas.before:
            Color(0, 0, 0, 0.5)
            background = Rectangle()
        bar.bind(pos=lambda w, value: setattr(background, "pos", value))
        bar.bind(size=lambda w, value: setattr(background, "size", value))

        self._photo_button = RoundButton("photo", size_hint=(None, None), size=(dp(64), dp(64)))
        self._video_button = RoundButton("video", size_hint=(None, None), size=(dp(80), dp(80)))
        self._audio_button = RoundButton("audio", size_hint=(None, None), size=(dp(64), dp(64)))
        self._photo_button.bind(on_release=lambda *_: self._take_photo())
        self._video_button.bind(on_release=lambda *_: self._toggle_video())
        self._audio_button.bind(on_release=lambda *_: self._toggle_audio())

        for button, caption in (
            (self._photo_button, "Foto"),
            (self._video_button, "Video"),
            (self._audio_button, "Audio"),
        ):
            slot = BoxLayout(orientation="vertical", spacing=dp(6))
            holder = AnchorLayout(anchor_x="center", anchor_y="center")
            holder.add_widget(button)
            slot.add_widget(holder)
            slot.add_widget(Label(text=caption, font_size="13sp", size_hint_y=None, height=dp(18)))
            bar.add_widget(slot)
        return bar

    def notify(self, text):
        self._toast.show(text, max_width=self._window.width * 0.85)

    def _refresh_controls(self):
        camera_ready = self._backend is not None and self._backend.is_open
        self._photo_button.disabled = not camera_ready
        self._video_button.disabled = not (
            camera_ready and self._mic_allowed and self._mode in (MODE_IDLE, MODE_VIDEO)
        )
        self._audio_button.disabled = not (
            self._backend is not None and self._mic_allowed and self._mode in (MODE_IDLE, MODE_AUDIO)
        )
        self._video_button.active = self._mode == MODE_VIDEO
        self._audio_button.active = self._mode == MODE_AUDIO

    def on_start(self):
        if IS_ANDROID:
            self._request_permissions()

    def _request_permissions(self):
        request_permissions([Permission.CAMERA, Permission.RECORD_AUDIO], self._on_permissions_result)

    @mainthread
    def _on_permissions_result(self, permissions, grant_results):
        self._apply_permissions()

    def _apply_permissions(self):
        # Rilette ogni volta: l'utente può revocarle dalle impostazioni mentre l'app è in pausa.
        self._camera_allowed = check_permission(Permission.CAMERA)
        self._mic_allowed = check_permission(Permission.RECORD_AUDIO)
        if self._camera_allowed:
            self._open_camera()
        else:
            self._preview.show_message("Permesso fotocamera negato.\nTocca qui per chiederlo di nuovo.")
        if not self._mic_allowed:
            self.notify("Microfono negato: video e audio disattivati")
        self._refresh_controls()

    def _open_camera(self):
        if self._backend.is_open:
            return
        try:
            self._backend.open()
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: apertura fallita")
            self._preview.show_message(f"Errore apertura fotocamera:\n{exc}")
            return
        self._preview.set_source(self._backend.texture, self._backend.content_size)

    def _on_preview_tap(self):
        if IS_ANDROID and not self._camera_allowed:
            self._request_permissions()

    def _take_photo(self):
        if self._backend is None or not self._backend.is_open:
            return
        path = os.path.join(self._backend.photo_dir, media_filename("IMG", "png", datetime.now()))
        try:
            self._backend.take_photo(path)
        except Exception as exc:
            # I provider immagine di Kivy sollevano eccezioni di tipo diverso a seconda del backend.
            Logger.exception("Camera: salvataggio foto fallito")
            self.notify(f"Errore foto: {exc}")
            return
        self._preview.flash()
        self.notify(f"Foto salvata:\n{path}")

    def _toggle_video(self):
        if self._mode == MODE_VIDEO:
            self._stop_recording()
            return
        if self._mode != MODE_IDLE or self._backend is None or not self._backend.is_open:
            return
        path = os.path.join(self._backend.video_dir, media_filename("VID", "mp4", datetime.now()))
        try:
            self._backend.start_video(path)
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: avvio video fallito")
            self.notify(f"Errore avvio video: {exc}")
            return
        self._enter_recording(MODE_VIDEO)

    def _toggle_audio(self):
        if self._mode == MODE_AUDIO:
            self._stop_recording()
            return
        if self._mode != MODE_IDLE or self._backend is None:
            return
        path = os.path.join(self._backend.audio_dir, media_filename("AUD", "m4a", datetime.now()))
        try:
            self._backend.start_audio(path)
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: avvio audio fallito")
            self.notify(f"Errore avvio audio: {exc}")
            return
        self._enter_recording(MODE_AUDIO)

    def _enter_recording(self, mode):
        self._mode = mode
        self._record_started = time.monotonic()
        self._badge.show()
        self._timer_event = Clock.schedule_interval(self._update_timer, 0.25)
        self._refresh_controls()

    def _update_timer(self, dt):
        self._badge.set_elapsed(time.monotonic() - self._record_started)

    def _stop_recording(self):
        mode = self._mode
        if mode == MODE_VIDEO:
            saved, path = self._backend.stop_video()
            label = "Video"
        elif mode == MODE_AUDIO:
            saved, path = self._backend.stop_audio()
            label = "Audio"
        else:
            return
        self._mode = MODE_IDLE
        if self._timer_event is not None:
            self._timer_event.cancel()
            self._timer_event = None
        self._badge.hide()
        self._refresh_controls()
        if saved:
            self.notify(f"{label} salvato:\n{path}")
        else:
            self.notify("Registrazione troppo breve: file scartato")

    def _release_everything(self):
        if self._mode != MODE_IDLE:
            self._stop_recording()
        if self._backend is not None:
            self._backend.close()
            self._preview.clear_source()
        self._refresh_controls()

    def _on_keyboard(self, window, key, *args):
        if key != KEY_BACK:
            return False
        if self._mode != MODE_IDLE:
            self._stop_recording()
            return True
        if IS_ANDROID:
            PythonActivity.mActivity.moveTaskToBack(True)
            return True
        return False

    def on_pause(self):
        self._release_everything()
        return True

    def on_resume(self):
        if IS_ANDROID:
            self._apply_permissions()

    def on_stop(self):
        self._release_everything()


if __name__ == "__main__":
    GiocoCameraApp().run()
