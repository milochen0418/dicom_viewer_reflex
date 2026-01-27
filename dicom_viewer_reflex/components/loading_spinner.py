import reflex as rx


def loading_spinner() -> rx.Component:
    """A consistent loading spinner component."""
    return rx.el.div(
        rx.el.div(
            class_name="animate-spin rounded-full h-8 w-8 border-b-2 border-white"
        ),
        rx.el.span("Scanning directory...", class_name="ml-3 text-white font-medium"),
        class_name="flex items-center justify-center bg-blue-600/90 px-6 py-3 rounded-lg shadow-lg",
    )