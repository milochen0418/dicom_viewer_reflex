import reflex as rx
import os
import sys
import pydicom
from pathlib import Path
import logging
import numpy as np
from PIL import Image
import io
import base64


class DicomViewerState(rx.State):
    """State for managing DICOM file selection and loading."""
    _default_dicom_dir: str = "/Users/Shared/DICOM" if sys.platform == "darwin" else ""
    _default_browser_dir: str = _default_dicom_dir or str(Path.home())
    directory_path: str = os.getenv("PUBLIC_DICOM_DIR", _default_dicom_dir)
    directory_browser_visible: bool = False
    directory_browser_root: str = os.getenv("PUBLIC_DICOM_DIR", _default_browser_dir)
    directory_browser_path: str = directory_browser_root
    directory_browser_dirs: list[str] = []
    directory_browser_error: str = ""
    suppress_directory_dialog: bool = False
    workflow_step: str = "select"
    dicom_files: list[str] = []
    file_names: list[str] = []
    current_index: int = 0
    is_loading: bool = False
    error_message: str = ""
    has_loaded: bool = False
    current_image_base64: str = "/placeholder.svg"
    window_center: float = 40.0
    window_width: float = 400.0
    zoom_level: float = 1.0
    pan_x: int = 0
    pan_y: int = 0
    patient_name: str = "N/A"
    patient_id: str = "N/A"
    study_date: str = "N/A"
    modality: str = "N/A"
    study_description: str = "N/A"
    series_description: str = "N/A"
    image_position: str = "N/A"
    pixel_spacing: str = "N/A"
    slice_thickness: str = "N/A"
    rows: int = 0
    columns: int = 0
    show_metadata: bool = True
    metadata_unlocked: bool = False
    metadata_password_input: str = ""
    metadata_password_error: str = ""
    _cached_pixel_array: np.ndarray | None = None
    _cached_rescale_slope: float = 1.0
    _cached_rescale_intercept: float = 0.0

    _metadata_password: str = os.getenv("DICOM_METADATA_PASSWORD", "dicom")

    def _compute_slice_position(self, ds) -> float | None:
        """Compute slice position along the normal direction when possible."""
        pos = ds.get("ImagePositionPatient", None)
        iop = ds.get("ImageOrientationPatient", None)
        if pos is not None and iop is not None:
            try:
                if len(iop) >= 6 and len(pos) >= 3:
                    row = np.array([float(x) for x in iop[:3]], dtype=float)
                    col = np.array([float(x) for x in iop[3:6]], dtype=float)
                    normal = np.cross(row, col)
                    if np.linalg.norm(normal) > 0:
                        position = float(np.dot(normal, np.array(pos[:3], dtype=float)))
                        return position
            except Exception:
                pass
        if pos is not None:
            try:
                if len(pos) >= 3:
                    return float(pos[2])
            except Exception:
                pass
        slice_location = ds.get("SliceLocation", None)
        if slice_location is not None:
            try:
                return float(slice_location)
            except Exception:
                return None
        return None

    def _dicom_sort_key(self, ds, file_path: Path) -> tuple:
        """Return a stable sort key for DICOM slice ordering."""
        series_uid = str(ds.get("SeriesInstanceUID", ""))
        position = self._compute_slice_position(ds)
        instance = ds.get("InstanceNumber", None)
        try:
            instance_val = float(instance) if instance is not None else None
        except Exception:
            instance_val = None
        primary = position if position is not None else (
            instance_val if instance_val is not None else float("inf")
        )
        secondary = instance_val if instance_val is not None else float("inf")
        return (series_uid, primary, secondary, file_path.name.lower())

    @rx.var
    def total_images(self) -> int:
        return len(self.dicom_files)

    @rx.var
    def current_position_text(self) -> str:
        if not self.dicom_files:
            return "0 / 0"
        return f"{self.current_index + 1} / {self.total_images}"

    @rx.var
    def slider_max(self) -> int:
        return max(0, self.total_images - 1)

    @rx.var
    def can_go_up_directory(self) -> bool:
        current_path = self._normalize_directory_path(self.directory_browser_path)
        base_path = self._normalize_directory_path(self.directory_browser_root)
        return current_path != base_path

    @rx.event
    def set_directory(self, path: str):
        """Update the directory path state."""
        self.directory_path = path
        if self.error_message:
            self.error_message = ""

    def _normalize_directory_path(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate
        fallback = Path(self._default_browser_dir).expanduser()
        return fallback if fallback.exists() and fallback.is_dir() else Path("/")

    def _load_directory_entries(self, path: Path) -> None:
        try:
            dirs = sorted(
                [p for p in path.iterdir() if p.is_dir()],
                key=lambda p: p.name.lower(),
            )
            self.directory_browser_dirs = [str(p) for p in dirs]
            self.directory_browser_error = ""
        except PermissionError as e:
            logging.exception(f"Error scanning directory: {e}")
            self.directory_browser_dirs = []
            self.directory_browser_error = (
                "Permission denied when accessing this folder. "
                "On macOS, grant Terminal/VS Code access to Desktop or "
                "enable Full Disk Access in System Settings > Privacy & Security."
            )
        except Exception as e:
            logging.exception(f"Error scanning directory: {e}")
            self.directory_browser_dirs = []
            self.directory_browser_error = f"Error accessing directory: {str(e)}"

    @rx.event
    def suppress_directory_dialog_once(self):
        self.suppress_directory_dialog = True

    @rx.event
    def open_directory_dialog(self):
        if self.suppress_directory_dialog:
            self.suppress_directory_dialog = False
            return
        base_path = self.directory_path or self.directory_browser_path
        path = self._normalize_directory_path(base_path)
        self.directory_browser_path = str(path)
        self.directory_browser_visible = True
        self._load_directory_entries(path)

    @rx.event
    def close_directory_dialog(self):
        self.directory_browser_visible = False

    @rx.event
    def go_up_directory(self):
        if not self.can_go_up_directory:
            return
        path = self._normalize_directory_path(self.directory_browser_path).parent
        self.directory_browser_path = str(path)
        self._load_directory_entries(path)

    @rx.event
    def open_directory(self, path: str):
        next_path = self._normalize_directory_path(path)
        self.directory_browser_path = str(next_path)
        self._load_directory_entries(next_path)

    @rx.event
    def select_current_directory(self):
        self.directory_path = self.directory_browser_path
        self.directory_browser_visible = False
        if self.error_message:
            self.error_message = ""

    @rx.event(background=True)
    async def scan_directory(self):
        """Scan the specified directory for DICOM files."""
        async with self:
            self.is_loading = True
            self.error_message = ""
            self.has_loaded = False
            self.workflow_step = "select"
            self.dicom_files = []
            self.file_names = []
            self.current_image_base64 = "/placeholder.svg"
            self.metadata_unlocked = False
            self.metadata_password_input = ""
            self.metadata_password_error = ""
        try:
            if not self.directory_path:
                async with self:
                    self.error_message = "Please enter a valid directory path."
                    self.is_loading = False
                return
            path = Path(self.directory_path)
            if not path.exists() or not path.is_dir():
                async with self:
                    self.error_message = f"Directory not found: {self.directory_path}"
                    self.is_loading = False
                return
            files = sorted([f for f in path.iterdir() if f.is_file()])
            sortable_dicoms: list[tuple[tuple, Path, str]] = []
            for file_path in files:
                try:
                    ds = pydicom.dcmread(file_path, stop_before_pixels=True)
                    sort_key = self._dicom_sort_key(ds, file_path)
                    sortable_dicoms.append(
                        (sort_key, file_path.absolute(), file_path.name)
                    )
                except Exception as e:
                    logging.exception(f"Skipping invalid DICOM file {file_path}: {e}")
                    continue
            if not sortable_dicoms:
                async with self:
                    self.error_message = "No valid DICOM files found in this directory."
            else:
                sortable_dicoms.sort(key=lambda item: item[0])
                valid_dicoms = [item[1] for item in sortable_dicoms]
                valid_names = [item[2] for item in sortable_dicoms]
                async with self:
                    self.dicom_files = valid_dicoms
                    self.file_names = valid_names
                    self.has_loaded = True
                    self.current_index = 0
                    self.workflow_step = "list"
                return DicomViewerState.load_selected_image
        except PermissionError as e:
            logging.exception(f"Error scanning directory: {e}")
            async with self:
                self.error_message = (
                    "Permission denied when accessing the directory. "
                    "On macOS, grant Terminal/VS Code access to Desktop or "
                    "enable Full Disk Access in System Settings > Privacy & Security."
                )
        except Exception as e:
            logging.exception(f"Error scanning directory: {e}")
            async with self:
                self.error_message = f"Error accessing directory: {str(e)}"
        finally:
            async with self:
                self.is_loading = False

    @rx.event
    def reset_scan(self):
        """Return to directory selection step while keeping chosen path."""
        self.error_message = ""
        self.has_loaded = False
        self.workflow_step = "select"
        self.dicom_files = []
        self.file_names = []
        self.current_index = 0
        self.current_image_base64 = "/placeholder.svg"
        self.metadata_unlocked = False
        self.metadata_password_input = ""
        self.metadata_password_error = ""
        return DicomViewerState.open_directory_dialog

    @rx.event
    def open_viewer(self):
        """Navigate to viewer and mark workflow step."""
        self.workflow_step = "viewer"
        return rx.redirect("/viewer")

    @rx.event
    def back_to_results(self):
        """Navigate back to scan results."""
        self.workflow_step = "list" if self.has_loaded else "select"
        return rx.redirect("/")

    @rx.event
    def handle_file_selection(self, index: int):
        """Select a specific file from the list."""
        if 0 <= index < len(self.dicom_files):
            self.current_index = index
            return DicomViewerState.load_selected_image

    @rx.event(background=True)
    async def load_selected_image(self):
        """Load and process the currently selected DICOM image."""
        if not self.dicom_files or self.current_index >= len(self.dicom_files):
            return
        file_path = self.dicom_files[self.current_index]
        try:
            ds = pydicom.dcmread(file_path)
            async with self:
                self._cached_pixel_array = ds.pixel_array
                self._cached_rescale_slope = getattr(ds, "RescaleSlope", 1.0)
                self._cached_rescale_intercept = getattr(ds, "RescaleIntercept", 0.0)
                self._extract_metadata(ds)
                self._process_image()
        except Exception as e:
            logging.exception(f"Error loading image {file_path}: {e}")
            async with self:
                self.error_message = self._format_dicom_error(e)

    def _extract_metadata(self, ds):
        """Extract metadata from DICOM dataset."""

        @rx.event
        def get_val(tag, default="N/A"):
            return str(ds.get(tag, default))

        self.patient_name = get_val("PatientName")
        self.patient_id = get_val("PatientID")
        self.study_date = get_val("StudyDate")
        self.modality = get_val("Modality")
        self.study_description = get_val("StudyDescription")
        self.series_description = get_val("SeriesDescription")
        pos = ds.get("ImagePositionPatient", None)
        self.image_position = (
            f"[{', '.join([f'{x:.1f}' for x in pos])}]" if pos else "N/A"
        )
        spacing = ds.get("PixelSpacing", None)
        self.pixel_spacing = (
            f"{spacing[0]:.3f} x {spacing[1]:.3f} mm" if spacing else "N/A"
        )
        thickness = ds.get("SliceThickness", None)
        self.slice_thickness = f"{thickness} mm" if thickness else "N/A"
        self.rows = int(ds.get("Rows", 0))
        self.columns = int(ds.get("Columns", 0))

    @rx.event
    def toggle_metadata(self):
        self.show_metadata = not self.show_metadata

    @rx.event
    def update_metadata_password(self, value: str):
        self.metadata_password_input = value
        if self.metadata_password_error:
            self.metadata_password_error = ""

    @rx.event
    def unlock_metadata(self):
        if self.metadata_password_input == self._metadata_password:
            self.metadata_unlocked = True
            self.metadata_password_input = ""
            self.metadata_password_error = ""
        else:
            self.metadata_password_error = "Invalid password."

    @rx.event
    def lock_metadata(self):
        self.metadata_unlocked = False
        self.metadata_password_input = ""
        self.metadata_password_error = ""

    def _process_image(self):
        """Apply windowing and convert to base64."""
        if self._cached_pixel_array is None:
            return
        try:
            pixel_data = self._cached_pixel_array
            is_rgb = pixel_data.ndim == 3 and pixel_data.shape[-1] in (3, 4)
            if pixel_data.ndim >= 3 and not is_rgb:
                try:
                    pixel_data = pixel_data.reshape((-1,) + pixel_data.shape[-2:])[0]
                except Exception:
                    pixel_data = pixel_data[0]
            if is_rgb:
                rgb = pixel_data.astype(float)
                rgb = np.clip(rgb, np.min(rgb), np.max(rgb))
                if np.max(rgb) != np.min(rgb):
                    rgb = (rgb - np.min(rgb)) / (np.max(rgb) - np.min(rgb)) * 255.0
                img_uint8 = rgb.astype(np.uint8)
                pil_image = Image.fromarray(img_uint8)
                if pil_image.mode not in ("RGB", "RGBA"):
                    pil_image = pil_image.convert("RGB")
            else:
                pixel_data = pixel_data.astype(float)
                hu_image = (
                    pixel_data * self._cached_rescale_slope + self._cached_rescale_intercept
                )
                center = self.window_center
                width = self.window_width
                min_val = center - width / 2
                max_val = center + width / 2
                windowed = np.clip(hu_image, min_val, max_val)
                if max_val != min_val:
                    windowed = (windowed - min_val) / (max_val - min_val) * 255.0
                else:
                    windowed = windowed * 0
                img_uint8 = windowed.astype(np.uint8)
                pil_image = Image.fromarray(img_uint8)
                if pil_image.mode != "L":
                    pil_image = pil_image.convert("L")
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            b64_string = base64.b64encode(buffer.getvalue()).decode()
            self.current_image_base64 = f"data:image/png;base64,{b64_string}"
        except Exception as e:
            logging.exception(f"Error processing image: {e}")
            self.current_image_base64 = "/placeholder.svg"

    def _format_dicom_error(self, error: Exception) -> str:
        message = str(error)
        lowered = message.lower()
        if (
            "transfer syntax" in lowered
            or "no handler" in lowered
            or "decode" in lowered
            or "compressed" in lowered
        ):
            return (
                "Unable to decode pixel data. This DICOM appears to use a compressed "
                "transfer syntax. Install pylibjpeg (and pylibjpeg-libjpeg) or gdcm to "
                "enable decompression, then restart the app."
            )
        return f"Error loading image: {message}"

    @rx.event
    def update_window_width(self, value: str):
        try:
            self.window_width = float(value)
            self._process_image()
        except ValueError as e:
            logging.exception(f"Error updating window width: {e}")

    @rx.event
    def update_window_center(self, value: str):
        try:
            self.window_center = float(value)
            self._process_image()
        except ValueError as e:
            logging.exception(f"Error updating window center: {e}")

    @rx.event
    def next_image(self):
        if self.current_index < self.total_images - 1:
            self.current_index += 1
            return DicomViewerState.load_selected_image

    @rx.event
    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            return DicomViewerState.load_selected_image

    @rx.event
    def set_slice_index(self, value: str):
        try:
            val = int(float(value))
            if 0 <= val < self.total_images:
                self.current_index = val
                return DicomViewerState.load_selected_image
        except ValueError as e:
            logging.exception(f"Error setting slice index: {e}")

    @rx.event
    def set_zoom(self, value: float):
        """Set the zoom level within limits."""
        self.zoom_level = max(0.25, min(4.0, value))

    @rx.event
    def zoom_in(self):
        """Increase zoom level."""
        self.set_zoom(self.zoom_level + 0.25)

    @rx.event
    def zoom_out(self):
        """Decrease zoom level."""
        self.set_zoom(self.zoom_level - 0.25)

    @rx.event
    def reset_zoom(self):
        """Reset zoom and pan settings."""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0

    @rx.event
    def pan_control(self, dx: int, dy: int):
        """Update pan position."""
        self.pan_x += dx
        self.pan_y += dy

    @rx.event
    def apply_preset(self, preset_name: str):
        """Apply a predefined windowing preset."""
        presets = {
            "Soft Tissue": (40, 400),
            "Lung": (-600, 1500),
            "Bone": (300, 1500),
            "Brain": (40, 80),
            "Abdomen": (50, 400),
        }
        if preset_name in presets:
            center, width = presets[preset_name]
            self.window_center = float(center)
            self.window_width = float(width)
            self._process_image()

    @rx.event
    def reset_view(self):
        """Reset all view settings to default."""
        self.reset_zoom()
        self.window_center = 40.0
        self.window_width = 400.0
        self._process_image()

    @rx.var
    def preset_options(self) -> list[str]:
        """Available windowing presets."""
        return ["Soft Tissue", "Lung", "Bone", "Brain", "Abdomen"]