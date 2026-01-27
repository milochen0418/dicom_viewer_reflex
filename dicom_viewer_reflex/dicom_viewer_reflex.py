import reflex as rx
from dicom_viewer_reflex.states.dicom_state import DicomViewerState
from dicom_viewer_reflex.components.loading_spinner import loading_spinner
from dicom_viewer_reflex.components.viewer import viewer_layout


def header() -> rx.Component:
    """Application header."""
    return rx.el.header(
        rx.el.div(
            rx.icon("activity", class_name="h-6 w-6 text-blue-400 mr-3"),
            rx.el.h1(
                "DICOM Viewer",
                class_name="text-xl font-bold text-slate-100 tracking-tight",
            ),
            class_name="flex items-center",
        ),
        class_name="bg-slate-900 border-b border-slate-800 px-6 py-4 shadow-sm sticky top-0 z-50",
    )


def directory_selector() -> rx.Component:
    """Component for directory input and scanning action."""
    return rx.el.div(
        rx.el.div(
            rx.el.label(
                "DICOM Directory Path",
                class_name="block text-sm font-medium text-slate-300 mb-2",
            ),
            rx.el.div(
                rx.el.input(
                    placeholder="/path/to/dicom/series",
                    on_change=DicomViewerState.set_directory,
                    class_name="flex-1 bg-slate-800 border-slate-700 text-slate-100 rounded-l-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all placeholder-slate-500 w-full",
                    default_value=DicomViewerState.directory_path,
                ),
                rx.el.button(
                    rx.icon("folder-search", class_name="h-5 w-5 mr-2"),
                    "Scan Directory",
                    on_click=DicomViewerState.scan_directory,
                    class_name="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-r-lg font-medium transition-colors flex items-center whitespace-nowrap",
                ),
                class_name="flex shadow-lg rounded-lg",
            ),
            rx.cond(
                DicomViewerState.error_message != "",
                rx.el.div(
                    rx.icon("wheat", class_name="h-4 w-4 mr-2 text-red-400"),
                    DicomViewerState.error_message,
                    class_name="mt-3 flex items-center text-red-400 text-sm bg-red-900/20 p-3 rounded-lg border border-red-900/50",
                ),
            ),
            class_name="max-w-2xl mx-auto w-full",
        ),
        class_name="py-12 px-4",
    )


def file_list_item(filename: str, index: int) -> rx.Component:
    """Individual file item in the list."""
    is_selected = DicomViewerState.current_index == index
    return rx.el.div(
        rx.el.div(
            rx.icon("file-image", class_name="h-4 w-4 mr-3 text-slate-400"),
            rx.el.span(
                filename, class_name="text-sm text-slate-300 truncate font-mono"
            ),
            class_name="flex items-center flex-1 min-w-0",
        ),
        on_click=lambda: DicomViewerState.handle_file_selection(index),
        class_name=rx.cond(
            is_selected,
            "flex items-center p-3 rounded-lg bg-blue-600/20 border border-blue-500/50 cursor-pointer transition-all",
            "flex items-center p-3 rounded-lg bg-slate-800/50 border border-slate-700 hover:bg-slate-800 cursor-pointer transition-all",
        ),
    )


def file_browser() -> rx.Component:
    """Component displaying the list of found DICOM files."""
    return rx.cond(
        DicomViewerState.has_loaded,
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.h2(
                        "Detected Series",
                        class_name="text-lg font-semibold text-slate-100",
                    ),
                    rx.el.span(
                        f"{DicomViewerState.dicom_files.length()} images",
                        class_name="text-xs font-medium bg-blue-900 text-blue-200 px-2 py-1 rounded-full",
                    ),
                    class_name="flex items-center gap-3",
                ),
                rx.el.a(
                    rx.el.button(
                        rx.icon("play", class_name="h-4 w-4 mr-2 fill-current"),
                        "Open Viewer",
                        class_name="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center shadow-lg hover:shadow-blue-500/25",
                    ),
                    href="/viewer",
                ),
                class_name="flex items-center justify-between mb-6 px-1",
            ),
            rx.el.div(
                rx.foreach(
                    DicomViewerState.file_names, lambda name, i: file_list_item(name, i)
                ),
                class_name="grid gap-2 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar",
            ),
            class_name="max-w-2xl mx-auto w-full bg-slate-900/50 p-6 rounded-xl border border-slate-800",
        ),
    )


def landing_content() -> rx.Component:
    """Main content area for the landing page."""
    return rx.el.div(
        directory_selector(),
        rx.cond(
            DicomViewerState.is_loading,
            rx.el.div(loading_spinner(), class_name="flex justify-center py-8"),
            file_browser(),
        ),
        class_name="flex-1 w-full max-w-7xl mx-auto",
    )


def index() -> rx.Component:
    return rx.el.div(
        header(),
        rx.el.main(landing_content(), class_name="flex-1 bg-slate-950 min-h-screen"),
        class_name="flex flex-col min-h-screen font-['Inter'] bg-slate-950 text-slate-100",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, route="/")
app.add_page(viewer_layout, route="/viewer")