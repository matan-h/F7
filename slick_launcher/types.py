from typing import TYPE_CHECKING, Callable, Generic, TypeVar

from PyQt6.QtCore import QCoreApplication, QObject
from PyQt6.QtCore import pyqtSignal as _pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

if TYPE_CHECKING:
    T = TypeVar("T")

    class pyqtSignal(
        Generic[T]
    ):  # for some reason, lint,etc. is not working with stock pyqt6.
        def __init__(self, *args, **kwargs): ...
        def connect(self, slot: Callable[[T], None]) -> None: ...
        def emit(self, *args: T) -> None: ...
        def disconnect(self, fn) -> None: ...

    class QInstance(QCoreApplication):
        focusChanged = pyqtSignal()

        def topLevelWidgets(self) -> list[QWidget]: ...

else:
    pyqtSignal = _pyqtSignal
    QInstance = QApplication.instance
