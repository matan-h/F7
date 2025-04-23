import sys
import ollama
from slick_launcher.clip import get_selected_text

from PyQt6.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal
from PyQt6.QtGui import ( QKeyEvent, QFont, 
                         QTextCursor)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit,
                            QTextEdit, QVBoxLayout, QWidget, QLabel,
                            QFrame)

# Configuration
ai_model_name = "qwen2.5-coder:1.5b"  # Updated model name for Ollama
ai_model_name = "phi3"  # Updated model name for Ollama


# system_prompt = "You're a program that processes text based on user instructions. Respond with the result only — no explanations, no extra text."
system_prompt = """
You are a smart text-processing program. For each request, perform the operation on the given text and output **exactly** the result.nothing more. put the final answer in codeblock.
"""


def ai(msg, text):
    response = ollama.chat(
        model=ai_model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{msg}\ntext:```\n{text}\n```"}
        ],
        stream=True
    )
    for chunk in response:
        content = chunk['message']['content']
        if content is not None:
            yield content

class AIStreamWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_occurred = pyqtSignal(str)  # New error signal

    def __init__(self, msg, text):
        super().__init__()
        self.msg = msg
        self.text = text

    def run(self):
        full_response = ""
        try:
            for chunk in ai(self.msg, self.text):
                self.chunk_received.emit(chunk)
                full_response += chunk
            self.finished_signal.emit(full_response)
        except Exception as e:
            import traceback;traceback.print_exc()
            self.error_occurred.emit(f"AI Error: {str(e)}")

class SlickLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_text = ""
        self.ai_worker = None
        self.initUI()
        self.selected_text = get_selected_text()
        self.resetStatus()
        self.ai_execute_result = ""
        self.is_first_chunk = True  # Track first chunk for preview

    def initUI(self):
        # Window configuration
        self.setWindowTitle("Slick Launcher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                           Qt.WindowType.WindowStaysOnTopHint |
                           Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main widget
        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainWidget")
        self.setCentralWidget(self.main_widget)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        self.main_widget.setLayout(layout)

        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter Python expression or !command...")
        self.input_field.setObjectName("InputField")
        self.input_field.installEventFilter(self)
        layout.addWidget(self.input_field)
        
        # Preview output
        self.preview_output = QTextEdit()
        self.preview_output.setObjectName("PreviewOutput")
        self.preview_output.setReadOnly(True)
        self.preview_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_output.setFrameStyle(QFrame.Shape.NoFrame)
        self.preview_output.setMaximumHeight(150)
        self.preview_output.hide()
        layout.addWidget(self.preview_output)
        
        # Status bar
        self.status_bar = QLabel()
        self.status_bar.setObjectName("StatusBar")
        layout.addWidget(self.status_bar)
        
        # Style setup
        self.setStyleSheet("""
            #MainWidget {
                background: rgba(40, 44, 52, 0.98);
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.12);
            }
            #InputField {
                font-size: 16px;
                padding: 8px 12px;
                background: rgba(30, 34, 42, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #abb2bf;
                margin-bottom: 4px;
            }
            #PreviewOutput {
                font-family: 'Fira Code', monospace;
                font-size: 13px;
                background: rgba(30, 34, 42, 0.9);
                color: #abb2bf;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 4px;
                padding: 4px 8px;
            }
            #StatusBar {
                color: #5c6370;
                font-size: 11px;
                padding: 2px 4px;
                margin-top: 4px;
            }
        """)
        
        # Geometry
        self.resize(500, 1)
        self.centerWindow()
                
        # Signals
        self.input_field.textChanged.connect(self.updatePreview)
        QApplication.instance().focusChanged.connect(self.on_focus_changed)
        
    def centerWindow(self):
        frame = self.frameGeometry()
        center = self.screen().availableGeometry().center()
        frame.moveCenter(center)
        self.move(frame.topLeft())
        
    def setupClipboard(self):
        # QTimer.singleShot(100, self.captureSelection)
        self.selected_text = get_selected_text()
    
    def resetStatus(self):
        self.status_bar.setText(f"✂️ Selected text ({len(self.selected_text)} chars)")

                
    def eventFilter(self, obj, event):
        if obj is self.input_field and event.type() == QKeyEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                if self.input_field.text().startswith("!"):
                    if modifiers & Qt.KeyboardModifier.ControlModifier:
                        self.generateCommandPreview()
                    else:
                        self.executeCommand()
                else:
                    self.executeCommand()
                return True
            elif key == Qt.Key.Key_Escape:
                self.quit()
                return True
        return super().eventFilter(obj, event)
        
    def updatePreview(self):
        command = self.input_field.text().strip()
        self.preview_output.hide()
        
        if not command:
            self.adjustHeight()
            self.resetStatus()
            return
            
        if command.startswith("!"):
            self.status_bar.setText("💻 Command mode - Ctrl+Enter to preview, Enter to execute")
            self.adjustHeight()
            return
            
        try:
            lines = self.selected_text.split('\n')
            context = {
                'text': self.selected_text,
                'lines': lines,
                # '__builtins__': {}
            }
            
            result = eval(command, context)
            result_str = '\n'.join(map(str, result)) if isinstance(result, list) else str(result)
            self.preview_output.setPlainText(result_str)
            self.preview_output.show()
            self.status_bar.setText("✅ Valid Python expression")
        except Exception as e:
            self.preview_output.setPlainText(f"🚨 Error: {str(e)}")
            self.preview_output.show()
            self.status_bar.setText("❌ Invalid expression")
        
        self.adjustHeight()
    def generateCommandPreview(self):
        self.adjustHeight()
        command = self.input_field.text().strip()[1:]
        self.is_first_chunk = True
        self.preview_output.setPlainText("AI Response: Generating...")
        self.preview_output.show()

        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.terminate()

        self.ai_worker = AIStreamWorker(command, self.selected_text)
        self.ai_worker.chunk_received.connect(self.updatePreviewText)
        self.ai_worker.finished_signal.connect(self.handlePreviewFinished)
        self.ai_worker.error_occurred.connect(self.handleAIError)
        self.ai_worker.start()

    def updatePreviewText(self, chunk):
        cursor = self.preview_output.textCursor()
        
        if self.is_first_chunk:
            # Clear "Generating..." message on first chunk
            self.preview_output.setPlainText("AI Response: ")
            self.is_first_chunk = False
            
        # Insert new chunk at the end
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        
        # Auto-scroll to bottom
        self.preview_output.ensureCursorVisible()

    def handlePreviewFinished(self, full_response):
        self.status_bar.setText("AI preview complete - Ctrl+Enter to re-generate")
    def handleAIError(self, error_msg):
        self.preview_output.setPlainText(error_msg)
        self.status_bar.setText("AI Error occurred")
    def adjustHeight(self):
        base_height = self.input_field.sizeHint().height() + self.status_bar.sizeHint().height() + 20
        if self.preview_output.isVisible():
            doc_height = self.preview_output.document().size().height()
            preview_height = min(int(doc_height) + 10, 150)
            self.preview_output.setFixedHeight(preview_height)
            base_height += preview_height
        self.resize(QSize(self.width(), base_height))
        self.centerWindow()
    def focusOutEvent(self, event):
        self.quit()
    def quit(self):
        QApplication.quit()

    def executeCommand(self):
        command = self.input_field.text().strip()
        if command.startswith("!"):
            self.handleAICommand(command[1:])
        else:
            self.handlePythonCommand(command)

    def handleAICommand(self, command):
        self.status_bar.setText("💻 Processing AI command...")
        self.ai_worker = AIStreamWorker(command, self.selected_text)
        self.ai_execute_result = ""
        
        self.ai_worker.chunk_received.connect(self.accumulateAIResult)
        self.ai_worker.finished_signal.connect(self.finalizeAICommand)
        self.ai_worker.start()

    def accumulateAIResult(self, chunk):
        self.ai_execute_result += chunk

    def finalizeAICommand(self, result):
        clipboard = QApplication.clipboard()
        clipboard.setText(result)
        self.status_bar.setText(f"📋 AI result copied to clipboard ({len(result)} chars)")
        QTimer.singleShot(2000, self.quit)

    def handlePythonCommand(self, command):
        try:
            lines = self.selected_text.split('\n')
            context = {'text': self.selected_text, 'lines': lines}
            result = eval(command, {'__builtins__': {}, **context})
            
            clipboard = QApplication.clipboard()
            clipboard.setText(str(result))
            self.status_bar.setText(f"📋 Result copied: {str(result)[:50]}...")
            self.quit()
        except Exception as e:
            self.status_bar.setText(f"💥 Error: {str(e)}")
    
    def on_focus_changed(self, old, now):
        # If the window is no longer the active window, close it
        if not self.isActiveWindow():
            self.quit()
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Fira Code", 10))
    launcher = SlickLauncher()
    launcher.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main()