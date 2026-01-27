import reflex as rx
import os
import pydicom
from pathlib import Path
import logging
import numpy as np
from PIL import Image
import io
import base64


class DicomViewerState(rx.State):
    """State for managing DICOM file selection and loading."""

    directory_path: str = ""
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
    _cached_pixel_array: np.ndarray | None = None
    _cached_rescale_slope: float = 1.0
    _cached_rescale_intercept: float = 0.0

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

    @rx.event
    def set_directory(self, path: str):
        """Update the directory path state."""
        self.directory_path = path
        if self.error_message:
            self.error_message = ""

    @rx.event(background=True)
    async def scan_directory(self):
        """Scan the specified directory for DICOM files."""
        async with self:
            self.is_loading = True
            self.error_message = ""
            self.has_loaded = False
            self.dicom_files = []
            self.file_names = []
            self.current_image_base64 = "/placeholder.svg"
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
            valid_dicoms = []
            valid_names = []
            for file_path in files:
                try:
                    pydicom.dcmread(file_path, stop_before_pixels=True)
                    valid_dicoms.append(file_path.absolute())
                    valid_names.append(file_path.name)
                except Exception as e:
                    logging.exception(f"Skipping invalid DICOM file {file_path}: {e}")
                    continue
            if not valid_dicoms:
                async with self:
                    self.error_message = "No valid DICOM files found in this directory."
            else:
                async with self:
                    self.dicom_files = valid_dicoms
                    self.file_names = valid_names
                    self.has_loaded = True
                    self.current_index = 0
                await self.load_selected_image()
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
                self.error_message = f"Error loading image: {str(e)}"

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

    def _process_image(self):
        """Apply windowing and convert to base64."""
        if self._cached_pixel_array is None:
            return
        try:
            pixel_data = self._cached_pixel_array.astype(float)
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