import sys
import openai
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QClipboard, QKeyEvent, QFont, QAction, QTextDocument
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit, 
                            QTextEdit, QVBoxLayout, QWidget, QLabel, 
                            QFrame)
from PyQt6.QtGui import QShortcut

# TODO: config
ai_model_name = "phi3.5"
system_prompt = "You're a program that processes text based on user instructions. Respond with the result only — no explanations, no extra text."

client = openai.OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Dummy key; required by the SDK but not used by Ollama
)

# TODO: config
def ai(msg,text):
    response = client.chat.completions.create(
    model=ai_model_name,  # Replace with the model you've loaded in Ollama
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content":msg+"\ntext:```\n"+text+"\n```"}
    ]
)
    return response.choices[0].message.content


class SlickLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_text = ""
        self.initUI()
        self.setupClipboard()
        
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
        
        # Shortcuts
        QShortcut("Ctrl+C", self).activated.connect(self.quit)
        
        # Signals
        self.input_field.textChanged.connect(self.updatePreview)
        
    def centerWindow(self):
        frame = self.frameGeometry()
        center = self.screen().availableGeometry().center()
        frame.moveCenter(center)
        self.move(frame.topLeft())
        
    def setupClipboard(self):
        QTimer.singleShot(100, self.captureSelection)
        
    def captureSelection(self):
        clipboard = QApplication.clipboard()
        self.selected_text = clipboard.text(mode=QClipboard.Mode.Selection)
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
            elif key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
                self.quit()
                return True
        return super().eventFilter(obj, event)
        
    def updatePreview(self):
        command = self.input_field.text().strip()
        self.preview_output.hide()
        
        if not command:
            self.adjustHeight()
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
                '__builtins__': {}
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
        command = self.input_field.text().strip()
        if command.startswith("!"):
            self.preview_output.setPlainText(f"Command preview: {command[1:]}")
            self.preview_output.show()
            self.status_bar.setText("👀 Previewing command - Press Enter to execute")
            self.adjustHeight()
        
    def adjustHeight(self):
        base_height = self.input_field.sizeHint().height() + self.status_bar.sizeHint().height() + 20
        if self.preview_output.isVisible():
            doc_height = self.preview_output.document().size().height()
            preview_height = min(int(doc_height) + 10, 150)
            self.preview_output.setFixedHeight(preview_height)
            base_height += preview_height
        self.resize(QSize(self.width(), base_height))
        self.centerWindow()
    
    def quit(self):
        QApplication.quit()

    def executeCommand(self):
        command = self.input_field.text().strip()
        if command.startswith("!"):
            try:
                result = ai(command[1:],self.selected_text)
                self.status_bar.setText(f"💬 Ollama Response: {result}")
                
                # Copy to clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(result)
                
                # Close after 2 seconds
                QTimer.singleShot(2000, self.quit)
            except Exception as e:
                self.status_bar.setText(f"🌐 Ollama Error: {str(e)}")
                import traceback
                traceback.print_exc()
        else: 
            try:
                lines = self.selected_text.split('\n')
                context = {'text': self.selected_text, 'lines': lines}
                result = eval(command, {'__builtins__': {}, **context})
                print("EVAL RESULT:", result)
                
                # Copy to clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(str(result))
                
                self.status_bar.setText(f"📋 Result copied to clipboard: {str(result)}")
                self.quit()
            except Exception as e:
                self.status_bar.setText(f"💥 Execution error: {str(e)}")

    def focusOutEvent(self, event):
        self.quit()
        super().focusOutEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Fira Code", 10))
    
    launcher = SlickLauncher()
    launcher.show()
    
    sys.exit(app.exec())