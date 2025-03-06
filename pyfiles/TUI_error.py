from textual.screen import Screen
from textual.widgets import Static
from textual.app import ComposeResult
from textual.widgets import Button

# current debug method: prints passed error to a new screen

class ErrorScreen(Screen):
    def __init__(self, error_message: str):
        super().__init__()
        self.error_message = error_message
    
    def compose(self) -> ComposeResult:
        yield Static(f"Error: {self.error_message}")
        yield Button("Return to previous screen")
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()
        