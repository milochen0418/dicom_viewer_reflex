import reflex as rx
from dicom_viewer_reflex.states.dicom_state import DicomViewerState


def control_section_header(title: str) -> rx.Component:
    return rx.el.h3(
        title,
        class_name="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4",
    )


def metadata_row(label: str, value: str, icon_name: str) -> rx.Component:
    """Row for a single metadata item."""
    return rx.el.div(
        rx.el.div(
            rx.icon(icon_name, class_name="h-3.5 w-3.5 mr-2 text-slate-500"),
            rx.el.span(label, class_name="text-xs text-slate-400 font-medium"),
            class_name="flex items-center mb-1",
        ),
        rx.el.p(value, class_name="text-sm text-slate-200 font-mono pl-5.5 break-all"),
        class_name="mb-3",
    )


def metadata_panel() -> rx.Component:
    """Left sidebar displaying DICOM metadata."""
    return rx.cond(
        DicomViewerState.show_metadata,
        rx.el.div(
            rx.el.div(
                rx.el.h3("Metadata", class_name="text-sm font-semibold text-slate-100"),
                rx.el.button(
                    rx.icon("x", class_name="h-4 w-4 text-slate-400 hover:text-white"),
                    on_click=DicomViewerState.toggle_metadata,
                    class_name="p-1 rounded hover:bg-slate-800 transition-colors",
                ),
                class_name="flex items-center justify-between mb-6 pb-4 border-b border-slate-800",
            ),
            rx.el.div(
                control_section_header("Patient Info"),
                metadata_row("Name", DicomViewerState.patient_name, "user"),
                metadata_row("ID", DicomViewerState.patient_id, "id-card"),
                class_name="mb-6",
            ),
            rx.el.div(
                control_section_header("Study Details"),
                metadata_row("Date", DicomViewerState.study_date, "calendar"),
                metadata_row("Modality", DicomViewerState.modality, "scan"),
                metadata_row("Study", DicomViewerState.study_description, "file-text"),
                metadata_row("Series", DicomViewerState.series_description, "layers"),
                class_name="mb-6",
            ),
            rx.el.div(
                control_section_header("Image Data"),
                metadata_row(
                    "Resolution",
                    f"{DicomViewerState.columns} x {DicomViewerState.rows}",
                    "maximize",
                ),
                metadata_row("Spacing", DicomViewerState.pixel_spacing, "ruler"),
                metadata_row(
                    "Thickness", DicomViewerState.slice_thickness, "align-justify"
                ),
                metadata_row("Position", DicomViewerState.image_position, "crosshair"),
                class_name="mb-6",
            ),
            class_name="w-72 bg-slate-900 border-r border-slate-800 p-5 flex-shrink-0 overflow-y-auto custom-scrollbar transition-all duration-300 ease-in-out",
        ),
    )


def viewer_sidebar() -> rx.Component:
    """The controls sidebar."""
    return rx.el.div(
        rx.el.div(
            control_section_header("Navigation"),
            rx.el.div(
                rx.el.button(
                    rx.icon("chevron-left", class_name="h-6 w-6"),
                    on_click=DicomViewerState.prev_image,
                    disabled=DicomViewerState.current_index == 0,
                    class_name="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed text-slate-300 transition-colors",
                ),
                rx.el.div(
                    rx.el.input(
                        type="range",
                        min="0",
                        max=DicomViewerState.slider_max,
                        key=DicomViewerState.current_index,
                        default_value=DicomViewerState.current_index,
                        on_change=DicomViewerState.set_slice_index.throttle(50),
                        class_name="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500",
                    ),
                    class_name="flex-1 px-3",
                ),
                rx.el.button(
                    rx.icon("chevron-right", class_name="h-6 w-6"),
                    on_click=DicomViewerState.next_image,
                    disabled=DicomViewerState.current_index
                    == DicomViewerState.total_images - 1,
                    class_name="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed text-slate-300 transition-colors",
                ),
                class_name="flex items-center justify-between mb-2",
            ),
            class_name="p-6 border-b border-slate-800",
        ),
        rx.el.div(
            control_section_header("Windowing"),
            rx.el.div(
                rx.el.label(
                    "Preset",
                    class_name="block text-xs font-medium text-slate-400 mb-1.5",
                ),
                rx.el.select(
                    rx.el.option(
                        "Select Preset...", value="", disabled=True, selected=True
                    ),
                    rx.foreach(
                        DicomViewerState.preset_options,
                        lambda x: rx.el.option(x, value=x),
                    ),
                    on_change=DicomViewerState.apply_preset,
                    class_name="w-full bg-slate-800 text-slate-200 text-sm rounded-lg border border-slate-700 px-3 py-2 outline-none focus:ring-1 focus:ring-blue-500 mb-4 appearance-none",
                ),
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.label(
                        "Level (Center)",
                        class_name="text-xs font-medium text-slate-300",
                    ),
                    rx.el.span(
                        DicomViewerState.window_center.to_string(),
                        class_name="text-xs text-blue-400 font-mono",
                    ),
                    class_name="flex justify-between mb-2",
                ),
                rx.el.input(
                    type="range",
                    min="-1000",
                    max="3000",
                    key=DicomViewerState.window_center,
                    default_value=DicomViewerState.window_center,
                    on_change=DicomViewerState.update_window_center.throttle(100),
                    class_name="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer hover:bg-slate-600 transition-colors accent-blue-500",
                ),
                class_name="mb-4",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.label(
                        "Width", class_name="text-xs font-medium text-slate-300"
                    ),
                    rx.el.span(
                        DicomViewerState.window_width.to_string(),
                        class_name="text-xs text-blue-400 font-mono",
                    ),
                    class_name="flex justify-between mb-2",
                ),
                rx.el.input(
                    type="range",
                    min="1",
                    max="4000",
                    key=DicomViewerState.window_width,
                    default_value=DicomViewerState.window_width,
                    on_change=DicomViewerState.update_window_width.throttle(100),
                    class_name="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer hover:bg-slate-600 transition-colors accent-blue-500",
                ),
            ),
            class_name="p-6 border-b border-slate-800",
        ),
        rx.el.div(
            control_section_header("Zoom & Pan"),
            rx.el.div(
                rx.el.div(
                    rx.el.button(
                        rx.icon("minus", class_name="h-4 w-4"),
                        on_click=DicomViewerState.zoom_out,
                        disabled=DicomViewerState.zoom_level <= 0.25,
                        class_name="p-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50",
                    ),
                    rx.el.span(
                        f"{(DicomViewerState.zoom_level * 100).to_string()}%",
                        class_name="text-sm font-mono text-blue-400 w-16 text-center",
                    ),
                    rx.el.button(
                        rx.icon("plus", class_name="h-4 w-4"),
                        on_click=DicomViewerState.zoom_in,
                        disabled=DicomViewerState.zoom_level >= 4.0,
                        class_name="p-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50",
                    ),
                    class_name="flex items-center justify-between mb-4 bg-slate-900/50 p-2 rounded-lg border border-slate-800",
                ),
                rx.el.div(
                    rx.el.button(
                        rx.icon("arrow-up", class_name="h-5 w-5"),
                        on_click=lambda: DicomViewerState.pan_control(0, 50),
                        class_name="p-2 bg-slate-800 hover:bg-slate-700 rounded-t-lg mx-auto block text-slate-300",
                    ),
                    rx.el.div(
                        rx.el.button(
                            rx.icon("arrow-left", class_name="h-5 w-5"),
                            on_click=lambda: DicomViewerState.pan_control(50, 0),
                            class_name="p-2 bg-slate-800 hover:bg-slate-700 rounded-l-lg text-slate-300",
                        ),
                        rx.el.button(
                            rx.icon("maximize", class_name="h-4 w-4"),
                            on_click=DicomViewerState.reset_zoom,
                            class_name="p-2 bg-slate-700 hover:bg-slate-600 text-blue-400",
                            title="Reset View",
                        ),
                        rx.el.button(
                            rx.icon("arrow-right", class_name="h-5 w-5"),
                            on_click=lambda: DicomViewerState.pan_control(-50, 0),
                            class_name="p-2 bg-slate-800 hover:bg-slate-700 rounded-r-lg text-slate-300",
                        ),
                        class_name="flex justify-center gap-1 my-1",
                    ),
                    rx.el.button(
                        rx.icon("arrow-down", class_name="h-5 w-5"),
                        on_click=lambda: DicomViewerState.pan_control(0, -50),
                        class_name="p-2 bg-slate-800 hover:bg-slate-700 rounded-b-lg mx-auto block text-slate-300",
                    ),
                    class_name="mb-6",
                ),
                rx.el.button(
                    "Reset All",
                    on_click=DicomViewerState.reset_view,
                    class_name="w-full py-2 px-4 bg-slate-800 hover:bg-red-900/30 text-slate-400 hover:text-red-400 text-xs font-medium uppercase tracking-wider rounded-lg transition-colors border border-slate-800 hover:border-red-900/50",
                ),
                class_name="flex flex-col",
            ),
            class_name="p-6",
        ),
        class_name="w-80 bg-slate-900 border-l border-slate-800 flex flex-col z-20 shadow-xl overflow-y-auto custom-scrollbar",
    )


def viewer_layout() -> rx.Component:
    """The main viewer layout with image and controls."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.a(
                    rx.icon("arrow-left", class_name="h-4 w-4 mr-2"),
                    "Back to Library",
                    href="/",
                    class_name="flex items-center text-slate-400 hover:text-white transition-colors text-sm font-medium",
                ),
                rx.el.div(
                    rx.el.button(
                        rx.icon("info", class_name="h-4 w-4 mr-2"),
                        rx.cond(
                            DicomViewerState.show_metadata, "Hide Info", "Show Info"
                        ),
                        on_click=DicomViewerState.toggle_metadata,
                        class_name="flex items-center text-slate-400 hover:text-blue-400 transition-colors text-sm font-medium ml-6",
                    ),
                    class_name="border-l border-slate-700 ml-6 pl-6",
                ),
                class_name="flex items-center",
            ),
            rx.el.div(
                rx.icon("scan-eye", class_name="h-4 w-4 mr-2 text-blue-400"),
                rx.el.span(
                    DicomViewerState.current_position_text,
                    class_name="font-mono text-sm text-slate-300",
                ),
                class_name="flex items-center bg-slate-800 px-3 py-1.5 rounded-full border border-slate-700",
            ),
            class_name="bg-slate-900 border-b border-slate-800 p-4 flex justify-between items-center z-10 sticky top-0 shrink-0",
        ),
        rx.el.div(
            metadata_panel(),
            rx.el.div(
                rx.image(
                    src=DicomViewerState.current_image_base64,
                    style={
                        "transform": f"translate({DicomViewerState.pan_x}px, {DicomViewerState.pan_y}px) scale({DicomViewerState.zoom_level})",
                        "transition": "transform 0.1s ease-out",
                    },
                    class_name="max-h-full max-w-full object-contain pointer-events-none select-none",
                    alt="DICOM Image",
                ),
                class_name="flex-1 bg-black relative flex items-center justify-center overflow-hidden w-full",
            ),
            viewer_sidebar(),
            class_name="flex flex-1 overflow-hidden min-h-0",
        ),
        class_name="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 font-['Inter'] overflow-hidden",
    )