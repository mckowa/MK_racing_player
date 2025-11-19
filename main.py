import sys
import os
from PySide6.QtCore import Qt, QUrl, QSizeF
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QSlider, QLabel, QFileDialog, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtGui import QPainter, QPixmap


def format_time(ms):
    """Convert milliseconds to mm:ss or hh:mm:ss."""
    seconds = int(ms / 1000)
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    if h:
        return f"{h:02}:{m:02}:{s:02}"
    else:
        return f"{m:02}:{s:02}"


class VideoPlayer(QWidget):
    def __init__(self, parent, path: str):
        super().__init__()

        self.parent1 = parent


        # --- Scene setup ---
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)

        # --- Player setup ---
        self.audio = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_item)
        self.player.setSource(QUrl.fromLocalFile(path))

        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.view.setRenderHint(QPainter.Antialiasing, True)

        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.setPlaybackRate(1.0)


        # --- Logo setup ---
        logo_path = "assets/logo.png"
        # Load the ORIGINAL logo image (do NOT scale it here)
        self.original_logo_pixmap = QPixmap(logo_path)

        # Set the scale percentage
        self.logo_scale_percent = 0.10

        # Create and Add the Logo Item (Set it with the original to start)
        self.logo_item = QGraphicsPixmapItem(self.original_logo_pixmap)
        self.logo_item.setOpacity(0.5)

        self.scene.addItem(self.logo_item)

        # --- Controls ---
        self.play_btn = QPushButton("Play >")
        self.pause_btn = QPushButton("Pause ||")
        self.prev_frame_btn = QPushButton("<| Frame")
        self.next_frame_btn = QPushButton("Frame |>")
        self.back5_btn = QPushButton("<- 5s")
        self.forward5_btn = QPushButton("-> 5s")

        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.pause)
        self.prev_frame_btn.clicked.connect(self.prev_frame)
        self.next_frame_btn.clicked.connect(self.next_frame)
        self.back5_btn.clicked.connect(self.back_5s)
        self.forward5_btn.clicked.connect(self.forward_5s)

        # --- Slider + label ---
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.time_label = QLabel("00:00 / 00:00")

        self.slider.sliderPressed.connect(self.slider_pressed)
        self.slider.sliderReleased.connect(self.slider_released)

        # --- Layouts ---
        button_row = QHBoxLayout()
        button_row.addWidget(self.play_btn)
        button_row.addWidget(self.pause_btn)
        button_row.addWidget(self.prev_frame_btn)
        button_row.addWidget(self.next_frame_btn)
        button_row.addWidget(self.back5_btn)
        button_row.addWidget(self.forward5_btn)

        slider_row = QHBoxLayout()
        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.time_label)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(button_row)
        layout.addLayout(slider_row)
        self.setLayout(layout)

        # --- Internal state ---
        self._duration = 0
        self._dragging = False
        self._was_playing = False

        # --- Markers ---
        self._markers = [] ##will store markers in miliseconds, has to be cleared on file change

        # --- Signals ---
        self.player.positionChanged.connect(self.update_slider)
        self.player.durationChanged.connect(self.set_duration)
        self.player.mediaStatusChanged.connect(self.media_status)

    # ------------------- Core Controls -------------------
    def play(self):
        self.player.play()
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.play_btn.setVisible(False)
        self.pause_btn.setVisible(True)

    def pause(self):
        self.player.pause()
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.play_btn.setVisible(True)
        self.pause_btn.setVisible(False)

    # ------------------- Slider Logic -------------------
    def slider_pressed(self):
        self._dragging = True
        self._was_playing = (
            self.player.playbackState() == QMediaPlayer.PlayingState
        )
        self.pause()

    def slider_released(self):
        self._dragging = False
        if self._duration > 0:
            target = self.slider.value() / self.slider.maximum() * self._duration
            self.player.setPosition(int(target))
        if self._was_playing:
            self.play()
        else:
            self.pause()

    def update_slider(self, pos):
        if not self._dragging and self._duration > 0:
            val = int(pos / self._duration * self.slider.maximum())
            self.slider.blockSignals(True)
            self.slider.setValue(val)
            self.slider.blockSignals(False)

        # Update current time label
        self.time_label.setText(f"{format_time(pos)} / {format_time(self._duration)}")

    def set_duration(self, dur):
        self._duration = dur
        self.time_label.setText(f"00:00 / {format_time(dur)}")

    # ------------------- Resize / EOF -------------------
    def resizeEvent(self, event):
        self.fit_best_size()
        super().resizeEvent(event)

    def update_logo_position(self):
        # 1. Get the video item's bounding rectangle in the scene
        video_rect = self.video_item.boundingRect()
        if video_rect.isEmpty():
            return

        # --- SCALING LOGIC ---
        # Calculate the desired width based on the video width percentage
        new_logo_width = int(video_rect.width() * self.logo_scale_percent)

        # Scale the pixmap while maintaining the original aspect ratio
        scaled_pixmap = self.original_logo_pixmap.scaledToWidth(
            new_logo_width,
            # Ensure smooth transformation is used for best quality
            Qt.TransformationMode.SmoothTransformation
        )

        # Apply the new scaled pixmap to the item
        self.logo_item.setPixmap(scaled_pixmap)
        # --- END SCALING LOGIC ---

        # 2. Get the new scaled logo dimensions
        logo_width = scaled_pixmap.width()
        logo_height = scaled_pixmap.height()

        # 3. Define margin (which should also scale proportionally,
        # but using a fixed pixel margin for simplicity is common)
        margin = 10  # You could also make this a percentage of the video width if preferred.

        # 4. Calculate the Bottom-Right Position
        x_pos = video_rect.right() - logo_width - margin
        y_pos = video_rect.bottom() - logo_height - margin

        # 5. Set the logo's position
        self.logo_item.setPos(x_pos, y_pos)

    def fit_best_size(self):
        print("fit")
        w, h = self.view.viewport().width(), self.view.viewport().height()
        self.scene.setSceneRect(0, 0, w, h)
        self.video_item.setSize(QSizeF(w, h))
        self.update_logo_position()

    def media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.player.setPosition(0)

    # ------------------- Frame-by-Frame -------------------
    def prev_frame(self):
        if self._duration == 0:
            return
        pos = self.player.position() - 40
        self.player.setPosition(max(pos, 0))
        self.pause()

    def next_frame(self):
        if self._duration == 0:
            return
        pos = self.player.position() + 40
        self.player.setPosition(min(pos, self._duration))
        self.pause()

    def back_5s(self):
        """Move 5 seconds back."""
        if self._duration == 0:
            return
        self.move(-5000)

    def forward_5s(self):
        if self._duration == 0:
            return
        self.move(5000)

    def move(self, move_ms):
        pos = max(0, self.player.position() + move_ms)
        pos = min(pos, self._duration)
        was_playing = (self.player.playbackState() == QMediaPlayer.PlayingState)
        self.player.setPosition(pos)
        if not was_playing:
            self.pause()

    def on_marker(self):
        time = self.player.position()
        if (time > 0) and (time < self._duration):
            self.handle_marker(time)
        print(self._markers)

    def move_to_marker(self, next=True):
        time = self.player.position()
        marker_time = -1

        if next:
            for marker in self._markers:
                if marker > time:
                    marker_time = marker
                    break
        else:
            for marker in reversed(self._markers):
                if marker < time:
                    marker_time = marker
                    break

        if (marker_time < self._duration) and (marker_time >= 0):
            self.pause()
            self.player.setPosition(marker_time)


    def handle_marker(self, time):
        marker_index = -1
        tolerance_ms = 500
        for i in range(len(self._markers)):
            if abs(time - self._markers[i]) < tolerance_ms:
                marker_index = i
                break

        if marker_index >= 0:
            del self._markers[i]
        else:
            self._markers.append(time)
            self._markers.sort()

    def pause_play(self):
        if self.player.isPlaying():
            self.pause()
        else:
            self.play()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_A:
            self.prev_frame()
        elif event.key() == Qt.Key_D:
            self.next_frame()
        elif event.key() == Qt.Key_P: ##Qt.Key_Space Jebane QT xD
            self.pause_play()
        elif event.key() == Qt.Key_B:
            self.back_5s()
        elif event.key() == Qt.Key_F:
            self.parent1.show_fullscreen(self) ##thats convoluted but works!
        elif event.key() == Qt.Key_M:
            self.on_marker()
        elif event.key() == Qt.Key_L:
            self.move_to_marker(True)
        elif event.key() == Qt.Key_J:
            self.move_to_marker(False)
        else:
            super().keyPressEvent(event)


class DualPlayer(QWidget):
    def __init__(self, path1=None, path2=None):
        #TODO Layout - you have to resize for players to fill the space - especially when you have one video
        super().__init__()
        self.setWindowTitle("Dual Video Player")
        self.resize(1200, 600)

        self.isFullscreen = False

        # --- File selection ---
        if not path1 or not os.path.exists(path1):
            path1, _ = QFileDialog.getOpenFileName(
                self, "Select Left Video", "", "Video Files (*.mp4 *.mov *.avi *.mkv)"
            )

        if not path1:
            raise RuntimeError("No Videos Selected.")

        if not path2 or not os.path.exists(path2):
            path2, _ = QFileDialog.getOpenFileName(
                self, "Select Right Video", "", "Video Files (*.mp4 *.mov *.avi *.mkv)"
            )

        self.has_two_videos = False
        if path2:
            self.has_two_videos = True

        # --- Controls ---
        self.play_both_btn = QPushButton("Play Both")
        self.pause_both_btn = QPushButton("Pause Both")
        self.play_both_btn.clicked.connect(self.play_both)
        self.pause_both_btn.clicked.connect(self.pause_both)
        # --- Layout ---
        videos = QHBoxLayout()
        # --- Video Players ---
        self.left = VideoPlayer(self, path1)

        videos.addWidget(self.left)
        if self.has_two_videos:
            self.right = VideoPlayer(self, path2)
            videos.addWidget(self.right)

        controls = QHBoxLayout()
        controls.addWidget(self.play_both_btn)
        controls.addWidget(self.pause_both_btn)

        layout = QVBoxLayout()
        layout.addLayout(videos)
        layout.addLayout(controls)
        self.setLayout(layout)

        self.play_both()
        self.pause_both()

        # self.left.fit_best_size()
        # if self.has_two_videos:
        #     self.right.fit_best_size()

    def play_both(self):
        self.left.play()
        if self.has_two_videos:
            self.right.play()

    def pause_both(self):
        self.left.pause()
        if self.has_two_videos:
            self.right.pause()

    def show_fullscreen(self, child):
        if self.has_two_videos:
            isLeft = child == self.left
            if self.isFullscreen:
                self.isFullscreen = False
                if isLeft:
                    self.right.show()
                else:
                    self.left.show()
            else:
                self.isFullscreen = True
                if isLeft:
                    self.right.hide()
                else:
                    self.left.hide()
            self.left.fit_best_size()
            self.right.fit_best_size()

    def keyPressEvent(self, event):
        print(event.key())
        if event.key() == Qt.Key_1:
            self.changeFile(True)
        elif event.key() == Qt.Key_2:
            self.changeFile(False)
        elif event.key() == Qt.Key_3:
            self.changeTempo(True)
        elif event.key() == Qt.Key_4:
            self.changeTempo(False)
        else:
            super().keyPressEvent(event)

    def changeFile(self, is_left):

        ##TODO: we should default all things like markers, playback rate etc
        self.pause_both()
        if is_left:
            path1, _ = QFileDialog.getOpenFileName(
                self, "Select Left Video", "", "Video Files (*.mp4 *.mov *.avi *.mkv)"
            )
            self.left.player.setSource(path1)
            self.left.play()
            self.left.pause()
        else:
            path2, _ = QFileDialog.getOpenFileName(
                self, "Select Left Video", "", "Video Files (*.mp4 *.mov *.avi *.mkv)"
            )
            self.right.player.setSource(path2)
            self.has_two_videos = True
            self.right.play()
            self.right.pause()

    def changeTempo(self, speed_up):
        #TODO
        #errorproofing
        correction = 0.5
        if speed_up:
            correction = 2

        max_speed = 8
        min_speed = 0.25
        rateToSet = self.left.player.playbackRate() * correction
        print(rateToSet)

        if (rateToSet <= max_speed) and (rateToSet >= min_speed):
            self.left.player.setPlaybackRate(rateToSet)
            if self.has_two_videos:
                self.right.player.setPlaybackRate(rateToSet)

if __name__ == "__main__":
    # Optional debug paths
    debug = False
    #VIDEO1 = r"C:\Users\Michał\Documents\MK_Racing_Lab\Colin_Lonato.mp4"
    VIDEO1 = ""
    VIDEO2 = ""
    if debug:
        ##VIDEO1 = r"C:\test_karting\video1.mp4"
        VIDEO1 = r"C:\Users\Michał\Documents\MK_Racing_Lab\Colin_Lonato.mp4"
        VIDEO2 = r"C:\test_karting\video2.mp4"

    app = QApplication(sys.argv)
    win = DualPlayer(VIDEO1, VIDEO2)
    win.show()
    sys.exit(app.exec())
