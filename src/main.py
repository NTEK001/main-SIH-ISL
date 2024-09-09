import sys
from PySide6.QtWidgets import QApplication, QWidget
from camera_widget import Camera_widget

app = QApplication(sys.argv)
window = Camera_widget()
window.show()
app.exec()