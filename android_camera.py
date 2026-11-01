import os
from datetime import datetime

from android.runnable import run_on_ui_thread
from jnius import JavaException, PythonJavaClass, autoclass, cast, java_method
from kivy.logger import Logger

from geometry import (
    choose_preview_size,
    choose_size,
    cover_size,
    orientation_hint,
    rotated_size,
    surface_rotation_to_degrees,
    video_filename,
)

# autoclass solo a import-time: dal thread UI di Android FindClass non vede le classi dell'app.
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
DisplayMetrics = autoclass("android.util.DisplayMetrics")
Color = autoclass("android.graphics.Color")
Gravity = autoclass("android.view.Gravity")
SurfaceView = autoclass("android.view.SurfaceView")
ViewGroup = autoclass("android.view.ViewGroup")
ViewGroupLayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
FrameLayout = autoclass("android.widget.FrameLayout")
FrameLayoutParams = autoclass("android.widget.FrameLayout$LayoutParams")
Button = autoclass("android.widget.Button")
JString = autoclass("java.lang.String")

FOCUS_CONTINUOUS_VIDEO = "continuous-video"
BUTTON_MARGIN_DP = 32

CAMERA_ERRORS = (JavaException, ValueError)


class CameraError(ValueError):
    pass


def _run_logged(callback, *args):
    # Un'eccezione Python che risale in un callback Java abbatte il processo.
    try:
        callback(*args)
    except Exception:
        Logger.exception("Camera: errore nel callback Java")


class _ClickListener(PythonJavaClass):
    __javainterfaces__ = ["android/view/View$OnClickListener"]
    __javacontext__ = "app"

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    @java_method("(Landroid/view/View;)V")
    def onClick(self, view):
        _run_logged(self._callback)


class _SurfaceCallback(PythonJavaClass):
    __javainterfaces__ = ["android/view/SurfaceHolder$Callback"]
    __javacontext__ = "app"

    def __init__(self, on_created, on_destroyed):
        super().__init__()
        self._on_created = on_created
        self._on_destroyed = on_destroyed

    @java_method("(Landroid/view/SurfaceHolder;)V")
    def surfaceCreated(self, holder):
        _run_logged(self._on_created)

    @java_method("(Landroid/view/SurfaceHolder;III)V")
    def surfaceChanged(self, holder, pixel_format, width, height):
        Logger.debug(f"Camera: superficie {width}x{height} formato {pixel_format}")

    @java_method("(Landroid/view/SurfaceHolder;)V")
    def surfaceDestroyed(self, holder):
        _run_logged(self._on_destroyed)


def _size_tuple(size) -> tuple[int, int]:
    return int(size.width), int(size.height)


def _java_sizes(java_list) -> list[tuple[int, int]]:
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


def _remove_file(path: str | None) -> None:
    if path is None:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError:
        Logger.exception(f"Camera: impossibile eliminare {path}")


class CameraRecorder:
    """Tutti i metodi che toccano Camera, MediaRecorder o View girano sul thread UI di Android."""

    def __init__(self, on_status):
        self._on_status = on_status
        activity = PythonActivity.mActivity
        movies = activity.getExternalFilesDir(Environment.DIRECTORY_MOVIES)
        base = movies if movies is not None else activity.getFilesDir()
        self.output_dir = base.getAbsolutePath()
        self._camera = None
        self._profile = None
        self._video_size = None
        self._preview_size = None
        self._rotation = 0
        self._preview_running = False
        self._recorder = None
        self._output_path = None
        self._layout = None
        self._holder = None
        self._surface_callback = None
        self._record_button = None
        # pyjnius non trattiene i proxy Python: se il GC li raccoglie, Java chiama memoria liberata.
        self._java_refs = []

    @property
    def is_open(self) -> bool:
        return self._layout is not None

    @run_on_ui_thread
    def open(self):
        if self._layout is not None:
            return
        try:
            self._open_camera()
            self._build_views()
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: apertura fallita")
            self._teardown()
            self._on_status(f"Errore apertura fotocamera: {exc}")
            return
        self._on_status("Fotocamera aperta")

    @run_on_ui_thread
    def close(self):
        self._close_now()

    def _close_now(self):
        was_recording = self._recorder is not None
        self._teardown()
        if not was_recording:
            self._on_status("Fotocamera chiusa")

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
        self._camera.setDisplayOrientation(rotation)

        self._profile = profile
        self._video_size = video_size
        self._preview_size = preview_size
        self._rotation = rotation
        Logger.info(f"Camera: id={camera_id} video={video_size} anteprima={preview_size} rotazione={rotation}")

    def _make_button(self, activity, label, callback, gravity):
        button = Button(activity)
        button.setText(JString(label))
        listener = _ClickListener(callback)
        button.setOnClickListener(listener)
        self._java_refs.append(listener)
        params = FrameLayoutParams(
            ViewGroupLayoutParams.WRAP_CONTENT, ViewGroupLayoutParams.WRAP_CONTENT, gravity
        )
        density = activity.getResources().getDisplayMetrics().density
        margin = int(BUTTON_MARGIN_DP * density + 0.5)
        params.setMargins(margin, margin, margin, margin)
        return button, params

    def _build_views(self):
        activity = PythonActivity.mActivity
        metrics = DisplayMetrics()
        activity.getWindowManager().getDefaultDisplay().getRealMetrics(metrics)
        screen = (int(metrics.widthPixels), int(metrics.heightPixels))
        width, height = cover_size(rotated_size(self._preview_size, self._rotation), screen)

        self._java_refs = []
        layout = FrameLayout(activity)
        layout.setBackgroundColor(Color.BLACK)

        surface_view = SurfaceView(activity)
        # Sopra la SurfaceView di SDL, sotto i pulsanti nativi.
        surface_view.setZOrderMediaOverlay(True)
        holder = surface_view.getHolder()
        surface_callback = _SurfaceCallback(self._on_surface_created, self._on_surface_destroyed)
        holder.addCallback(surface_callback)
        self._java_refs.append(surface_callback)
        # Più grande dello schermo e centrata: riempie senza deformare, i bordi in eccesso vengono tagliati.
        layout.addView(surface_view, FrameLayoutParams(width, height, Gravity.CENTER))

        record_button, record_params = self._make_button(
            activity, "Registra", self._toggle_recording, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL
        )
        layout.addView(record_button, record_params)
        close_button, close_params = self._make_button(
            activity, "Chiudi", self._close_now, Gravity.TOP | Gravity.END
        )
        layout.addView(close_button, close_params)

        activity.addContentView(
            layout, ViewGroupLayoutParams(ViewGroupLayoutParams.MATCH_PARENT, ViewGroupLayoutParams.MATCH_PARENT)
        )
        self._layout = layout
        self._holder = holder
        self._surface_callback = surface_callback
        self._record_button = record_button

    def _on_surface_created(self):
        if self._camera is None or self._holder is None:
            return
        try:
            self._camera.setPreviewDisplay(self._holder)
            self._camera.startPreview()
        except JavaException as exc:
            Logger.exception("Camera: avvio anteprima fallito")
            self._on_status(f"Errore anteprima: {exc}")
            return
        self._preview_running = True

    def _on_surface_destroyed(self):
        if self._recorder is not None:
            self._stop_recording()
        if self._camera is not None and self._preview_running:
            try:
                self._camera.stopPreview()
            except JavaException:
                Logger.exception("Camera: stopPreview fallito")
        self._preview_running = False

    def _toggle_recording(self):
        if self._recorder is not None:
            self._stop_recording()
        else:
            self._start_recording()

    def _set_record_label(self, label):
        if self._record_button is not None:
            self._record_button.setText(JString(label))

    def _relock_camera(self):
        if self._camera is None:
            return
        try:
            self._camera.lock()
            self._camera.startPreview()
        except JavaException:
            Logger.exception("Camera: ripresa del controllo della fotocamera fallita")

    def _release_recorder(self, recorder):
        try:
            recorder.reset()
            recorder.release()
        except JavaException:
            Logger.exception("Camera: rilascio MediaRecorder fallito")

    def _start_recording(self):
        if self._camera is None or not self._preview_running:
            self._on_status("Anteprima non ancora pronta")
            return
        path = os.path.join(self.output_dir, video_filename(datetime.now()))
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
            recorder.setPreviewDisplay(self._holder.getSurface())
            recorder.prepare()
            recorder.start()
        except JavaException as exc:
            Logger.exception("Camera: avvio registrazione fallito")
            self._release_recorder(recorder)
            self._relock_camera()
            _remove_file(path)
            self._on_status(f"Errore avvio registrazione: {exc}")
            return
        self._recorder = recorder
        self._output_path = path
        self._set_record_label("Stop")
        self._on_status("Registrazione in corso")

    def _stop_recording(self):
        recorder, path = self._recorder, self._output_path
        self._recorder = None
        self._output_path = None
        saved = True
        try:
            recorder.stop()
        except JavaException:
            # MediaRecorder.stop lancia RuntimeException se non ha ricevuto dati validi.
            Logger.exception("Camera: stop registrazione fallito")
            saved = False
        self._release_recorder(recorder)
        self._relock_camera()
        self._set_record_label("Registra")
        if saved:
            self._on_status(f"Video salvato: {path}")
        else:
            _remove_file(path)
            self._on_status("Registrazione troppo breve: file scartato")

    def _teardown(self):
        if self._recorder is not None:
            self._stop_recording()
        if self._camera is not None:
            camera = self._camera
            self._camera = None
            try:
                if self._preview_running:
                    camera.stopPreview()
                camera.release()
            except JavaException:
                Logger.exception("Camera: rilascio fotocamera fallito")
        self._preview_running = False
        if self._holder is not None and self._surface_callback is not None:
            self._holder.removeCallback(self._surface_callback)
        if self._layout is not None:
            parent = self._layout.getParent()
            if parent is not None:
                cast(ViewGroup, parent).removeView(self._layout)
        self._layout = None
        self._holder = None
        self._surface_callback = None
        self._record_button = None
