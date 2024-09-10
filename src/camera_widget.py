import os
from PySide6.QtWidgets import QWidget, QMainWindow, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import *
from PySide6.QtCore import *
import cv2
from gtts import gTTS
from playsound import playsound

from MainWindow_GUI import Ui_Form
import cv2
from cvzone.HandTrackingModule import HandDetector
from cvzone.ClassificationModule import Classifier
import numpy as np
import math
from threading import Thread
import time

# Global variables
global sentence, last_detected_gesture, last_update_time
sentence = ""  # Initialize the sentence variable as an empty string
last_detected_gesture = None
last_update_time = 3


def rounded_pixmap(image_pixmap):
    pixmap = image_pixmap
    rounded_pixmap = QPixmap(pixmap.size())
    rounded_pixmap.fill(Qt.transparent)

    painter = QPainter(rounded_pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(pixmap))
    painter.setPen(Qt.NoPen)

    painter.drawRoundedRect(pixmap.rect(), 10, 10)
    painter.end()

    return rounded_pixmap


class Camera_widget(QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setGeometry(200, 200, 820, 710)
        self.setWindowTitle("ISL Translater")
        self.setFixedSize(self.size())

        Capture = cv2.VideoCapture(0)

        self.Worker1 = worker1(Capture)
        self.Worker2 = worker2(Capture)

        self.Worker1.start()
        self.Worker2.start()

        self.Worker1.ImageUpdate.connect(self.ImageUpdateSlot)
        self.Worker2.TextUpdate.connect(self.TextUpdateSlot)

        self.pushButton.clicked.connect(self.Worker2.speekbuttonclicked)

    def ImageUpdateSlot(self, Image):
        self.label.setPixmap(rounded_pixmap(QPixmap.fromImage(Image)))
        self.label.setScaledContents(True)

    def TextUpdateSlot(self, Text):
        print(type(Text))
        self.textEdit.setText(Text)

    def FeedCancel(self):
        self.Worker1.stop()


class worker1(QThread):
    ImageUpdate = Signal(QImage)

    def __init__(self, arg1, parent=None):
        super().__init__(parent)
        self.Capture = arg1

    def run(self):
        self.Thread1Active = True
        while self.Thread1Active:
            ret, frame = self.Capture.read()
            if ret:
                Image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                FlippledImage = cv2.flip(Image, 1)
                ConvertToQtFormat = QImage(FlippledImage.data, FlippledImage.shape[1], FlippledImage.shape[0],
                                           QImage.Format_RGB888)
                Pic = ConvertToQtFormat.scaled(450, 800, Qt.KeepAspectRatio)
                self.ImageUpdate.emit(Pic)

    def stop(self):
        self.Thread1Active = False
        self.quit()


class worker2(QThread):
    TextUpdate = Signal(str)

    def __init__(self, arg1, parent=None):
        super().__init__(parent)
        self.Capture = arg1

    def run(self):
        global sentence, last_detected_gesture, last_update_time
        detector = HandDetector(detectionCon=0.8, maxHands=2)  # Detect up to 2 hands
        classifier = Classifier("./Sign Language Model2_new.keras", "./labels.txt")
        offset = 20
        imgSize = 300

        labels = ['E', 'H', 'L', 'O']

        repeat_delay = 3.0  # Minimum delay (in seconds) before allowing the same letter to be added

        while True:
            success, img = self.Capture.read()
            imgOutput = img.copy()
            hands, img = detector.findHands(img)  # Detect hands

            if hands:
                # If only one hand is detected
                if len(hands) == 1:
                    hand = hands[0]
                    x, y, w, h = hand['bbox']  # Get bounding box

                    # Crop and process the hand for prediction
                    imgWhite = np.ones((imgSize, imgSize, 3), np.uint8) * 255  # Create a white background
                    imgCrop = img[y - offset:y + h + offset, x - offset:x + w + offset]  # Crop the hand image
                    aspectRatio = h / w  # Calculate aspect ratio

                    if aspectRatio > 1:
                        k = imgSize / h
                        wCal = math.ceil(k * w)
                        imgResize = cv2.resize(imgCrop, (wCal, imgSize))
                        wGap = math.ceil((imgSize - wCal) / 2)
                        imgWhite[:, wGap: wCal + wGap] = imgResize
                    else:
                        k = imgSize / w
                        hCal = math.ceil(k * h)
                        imgResize = cv2.resize(imgCrop, (imgSize, hCal))
                        hGap = math.ceil((imgSize - hCal) / 2)
                        imgWhite[hGap: hCal + hGap, :] = imgResize

                    # Time delay between predictions (in seconds)
                    prediction_delay = 2.0  # Change this to set the delay between predictions

                    # Make the prediction
                    prediction, index = classifier.getPrediction(imgWhite, draw=False)
                    label = labels[index % len(labels)]
                    current_gesture = label
                    current_time = time.time()

                    # Only allow new prediction after the specified delay
                    if current_time - last_update_time >= prediction_delay:
                        # Allow repeated letters but prevent continuous repetition
                        if current_gesture != last_detected_gesture or (
                                current_gesture == last_detected_gesture and current_time - last_update_time >= repeat_delay):
                            last_detected_gesture = current_gesture
                            last_update_time = current_time
                            sentence += current_gesture

                            # Emit the updated sentence (assuming you have a signal-slot mechanism)
                            self.TextUpdate.emit(sentence)

                        # Display the prediction and bounding box
                        cv2.rectangle(imgOutput, (x - offset, y - offset - 70), (x + 200, y - offset + 50), (0, 255, 0),
                                      cv2.FILLED)
                        cv2.putText(imgOutput, label, (x, y - 30), cv2.FONT_HERSHEY_COMPLEX, 2, (0, 0, 0), 2)
                        cv2.rectangle(imgOutput, (x - offset, y - offset), (x + w + offset, y + h + offset),
                                      (0, 255, 0), 4)

                # If two hands are detected, combine them into a single entity
                elif len(hands) == 2:
                    hand1 = hands[0]
                    hand2 = hands[1]

                    # Get the bounding box for both hands
                    x1, y1, w1, h1 = hand1['bbox']
                    x2, y2, w2, h2 = hand2['bbox']

                    # Calculate the smallest bounding box that can encompass both hands
                    x = min(x1, x2)
                    y = min(y1, y2)
                    w = max(x1 + w1, x2 + w2) - x
                    h = max(y1 + h1, y2 + h2) - y

                    # Crop and process the combined hand region for prediction
                    imgWhite = np.ones((imgSize, imgSize, 3), np.uint8) * 255  # Create a white background
                    imgCrop = img[y - offset:y + h + offset, x - offset:x + w + offset]  # Crop the region
                    aspectRatio = h / w  # Calculate aspect ratio

                    if aspectRatio > 1:
                        k = imgSize / h
                        wCal = math.ceil(k * w)
                        imgResize = cv2.resize(imgCrop, (wCal, imgSize))
                        wGap = math.ceil((imgSize - wCal) / 2)
                        imgWhite[:, wGap: wCal + wGap] = imgResize
                    else:
                        k = imgSize / w
                        hCal = math.ceil(k * h)
                        imgResize = cv2.resize(imgCrop, (imgSize, hCal))
                        hGap = math.ceil((imgSize - hCal) / 2)
                        imgWhite[hGap: hCal + hGap, :] = imgResize

                    # Time delay between predictions (in seconds)
                    prediction_delay = 2.0  # Change this to set the delay between predictions

                    # Make the prediction
                    prediction, index = classifier.getPrediction(imgWhite, draw=False)
                    label = labels[index % len(labels)]
                    current_gesture = label
                    current_time = time.time()

                    # Only allow new prediction after the specified delay
                    if current_time - last_update_time >= prediction_delay:
                        # Allow repeated letters but prevent continuous repetition
                        if current_gesture != last_detected_gesture or (
                                current_gesture == last_detected_gesture and current_time - last_update_time >= repeat_delay):
                            last_detected_gesture = current_gesture
                            last_update_time = current_time
                            sentence += current_gesture

                            # Emit the updated sentence (assuming you have a signal-slot mechanism)
                            self.TextUpdate.emit(sentence)

                        # Display the prediction and bounding box
                        cv2.rectangle(imgOutput, (x - offset, y - offset - 70), (x + 200, y - offset + 50), (0, 255, 0),
                                      cv2.FILLED)
                        cv2.putText(imgOutput, label, (x, y - 30), cv2.FONT_HERSHEY_COMPLEX, 2, (0, 0, 0), 2)
                        cv2.rectangle(imgOutput, (x - offset, y - offset), (x + w + offset, y + h + offset),
                                      (0, 255, 0), 4)

    def speekbuttonclicked(self):
        global sentence
        if sentence:  # Only speak if there's something in the sentence
            try:
                tts = gTTS(sentence)
                tts.save("sentence.mp3")
                playsound("sentence.mp3")
                os.remove("sentence.mp3")
            except Exception as e:
                print(f"Error occurred: {e}")



